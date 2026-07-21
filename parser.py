"""
Static AST parser for brittle Playwright / Selenium locators.

Walks a Python source file and extracts locator strings plus the
interaction that follows them (click, fill, etc.) so the translator
and generator can migrate each call into AgentQL.
"""

from __future__ import annotations

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


def parse_source(source: str, *, filename: str = "<string>") -> list[ParsedLocator]:
    """Parse *source* and return every locator the visitor recognizes."""
    raise NotImplementedError("AST visitor not yet implemented")


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
