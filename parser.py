"""
Static AST parser for brittle Playwright / Selenium locators.

Walks a Python source file and extracts locator strings plus the
interaction that follows them (click, fill, etc.) so the translator
and generator can migrate each call into AgentQL.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence


class LocatorKind(str, Enum):
    """How the locator string was expressed in the source."""

    CSS = "css"
    XPATH = "xpath"
    UNKNOWN = "unknown"


class Interaction(str, Enum):
    """Downstream action applied to the located element."""

    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    CHECK = "check"
    SELECT = "select_option"
    HOVER = "hover"
    WAIT = "wait_for"
    OTHER = "other"
    NONE = "none"


_INTERACTION_MAP: dict[str, Interaction] = {
    "click": Interaction.CLICK,
    "fill": Interaction.FILL,
    "type": Interaction.TYPE,
    "check": Interaction.CHECK,
    "select_option": Interaction.SELECT,
    "hover": Interaction.HOVER,
    "wait_for": Interaction.WAIT,
}

_PAGE_DIRECT_ACTIONS = frozenset(_INTERACTION_MAP)
_CHAIN_ACTIONS = frozenset(_INTERACTION_MAP)
_LOCATOR_BUILDERS = frozenset({"locator", "query_selector", "query_selector_all"})
_FIND_ELEMENT_METHODS = frozenset({"find_element", "find_elements"})

_XPATH_PREFIX = re.compile(r"^\s*(//|\(\s*\.?/|\./)")


@dataclass(frozen=True, slots=True)
class ParsedLocator:
    """One locator occurrence discovered in a legacy script."""

    selector: str
    kind: LocatorKind
    interaction: Interaction
    lineno: int
    col_offset: int
    fill_value: str | None = None
    raw_call: str | None = None


def classify_selector(selector: str) -> LocatorKind:
    """Best-effort CSS vs XPath classification for a selector string."""
    if not selector or not selector.strip():
        return LocatorKind.UNKNOWN
    if selector.lstrip().startswith(("xpath=", "xpath=")) or _XPATH_PREFIX.match(selector):
        return LocatorKind.XPATH
    if selector.startswith("/") and not selector.startswith("//"):
        # Bare absolute path is uncommon for CSS; treat as XPath-ish.
        return LocatorKind.XPATH
    return LocatorKind.CSS


def _literal_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _attr_chain(node: ast.AST) -> list[str]:
    """Return dotted attribute names from the outside in, e.g. page.locator -> [locator, page]."""
    names: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        names.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        names.append(current.id)
    return names


class LocatorVisitor(ast.NodeVisitor):
    """Collect Playwright/Selenium locator usages from an AST."""

    def __init__(self) -> None:
        self.locators: list[ParsedLocator] = []

    def visit_Call(self, node: ast.Call) -> None:
        handled = (
            self._try_chained_locator(node)
            or self._try_page_direct_action(node)
            or self._try_find_element(node)
        )
        if not handled:
            self.generic_visit(node)

    def _try_chained_locator(self, node: ast.Call) -> bool:
        """Match page.locator(...).click()/fill() style chains."""
        if not isinstance(node.func, ast.Attribute):
            return False
        action_name = node.func.attr
        if action_name not in _CHAIN_ACTIONS:
            return False

        receiver = node.func.value
        if not isinstance(receiver, ast.Call) or not isinstance(receiver.func, ast.Attribute):
            return False
        if receiver.func.attr not in _LOCATOR_BUILDERS:
            return False
        if not receiver.args:
            return False

        selector = _literal_str(receiver.args[0])
        if selector is None:
            return False

        fill_value = None
        interaction = _INTERACTION_MAP[action_name]
        if interaction in {Interaction.FILL, Interaction.TYPE} and node.args:
            fill_value = _literal_str(node.args[0])

        self.locators.append(
            ParsedLocator(
                selector=selector,
                kind=classify_selector(selector),
                interaction=interaction,
                lineno=receiver.lineno,
                col_offset=receiver.col_offset,
                fill_value=fill_value,
                raw_call=action_name,
            )
        )
        return True

    def _try_page_direct_action(self, node: ast.Call) -> bool:
        """Match page.click(selector) / page.fill(selector, value)."""
        if not isinstance(node.func, ast.Attribute):
            return False
        action_name = node.func.attr
        if action_name not in _PAGE_DIRECT_ACTIONS:
            return False
        # Skip if this is already a chained locator().action()
        if isinstance(node.func.value, ast.Call):
            return False
        if not node.args:
            return False

        selector = _literal_str(node.args[0])
        if selector is None:
            return False

        fill_value = None
        interaction = _INTERACTION_MAP[action_name]
        if interaction in {Interaction.FILL, Interaction.TYPE} and len(node.args) >= 2:
            fill_value = _literal_str(node.args[1])

        self.locators.append(
            ParsedLocator(
                selector=selector,
                kind=classify_selector(selector),
                interaction=interaction,
                lineno=node.lineno,
                col_offset=node.col_offset,
                fill_value=fill_value,
                raw_call=action_name,
            )
        )
        return True

    def _try_find_element(self, node: ast.Call) -> bool:
        """Match driver.find_element(By.CSS_SELECTOR, '...') patterns."""
        if not isinstance(node.func, ast.Attribute):
            return False
        if node.func.attr not in _FIND_ELEMENT_METHODS:
            return False
        if len(node.args) < 2:
            return False

        selector = _literal_str(node.args[1])
        if selector is None:
            return False

        kind = LocatorKind.UNKNOWN
        strategy = node.args[0]
        if isinstance(strategy, ast.Attribute):
            strategy_name = strategy.attr.upper()
            if "XPATH" in strategy_name:
                kind = LocatorKind.XPATH
            elif any(token in strategy_name for token in ("CSS", "ID", "NAME", "CLASS", "TAG")):
                kind = LocatorKind.CSS
        if kind is LocatorKind.UNKNOWN:
            kind = classify_selector(selector)

        self.locators.append(
            ParsedLocator(
                selector=selector,
                kind=kind,
                interaction=Interaction.NONE,
                lineno=node.lineno,
                col_offset=node.col_offset,
                fill_value=None,
                raw_call=node.func.attr,
            )
        )
        return True


def parse_source(source: str, *, filename: str = "<string>") -> list[ParsedLocator]:
    """Parse *source* and return every locator the visitor recognizes."""
    tree = ast.parse(source, filename=filename)
    visitor = LocatorVisitor()
    visitor.visit(tree)
    return visitor.locators


def parse_file(path: str | Path) -> list[ParsedLocator]:
    """Read *path* from disk and parse its locators."""
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    return parse_source(source, filename=str(file_path))


def summarize(locators: Sequence[ParsedLocator]) -> dict[str, int]:
    """Return simple counts keyed by interaction name."""
    counts: dict[str, int] = {}
    for locator in locators:
        key = locator.interaction.value
        counts[key] = counts.get(key, 0) + 1
    return counts
