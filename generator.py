"""
AgentQL code generator for Legacy-to-AgentQL migration.

Turns a batch of ``TranslatedLocator`` records into an AgentQL query
string and a runnable ``sync_playwright`` script that wraps the page,
calls ``query_elements``, and replays the original interactions.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Sequence

from parser import Interaction
from translator import TranslatedLocator, is_valid_agentql_name

DEFAULT_URL = "https://example.com"
DEFAULT_FUNCTION_NAME = "run_migrated_flow"

_INTERACTION_METHODS: dict[Interaction, str] = {
    Interaction.CLICK: "click",
    Interaction.FILL: "fill",
    Interaction.TYPE: "type",
    Interaction.CHECK: "check",
    Interaction.SELECT: "select_option",
    Interaction.HOVER: "hover",
    Interaction.WAIT: "wait_for",
}

_VALUE_INTERACTIONS = frozenset(
    {
        Interaction.FILL,
        Interaction.TYPE,
        Interaction.SELECT,
    }
)


@dataclass(frozen=True, slots=True)
class GeneratedAction:
    """One interaction line in the generated AgentQL script.

    Attributes:
        name: AgentQL response field (snake_case).
        interaction: Playwright-style action to invoke.
        fill_value: Literal argument for fill/type/select when known.
        source_lineno: Line in the legacy script this action came from.
    """

    name: str
    interaction: Interaction
    fill_value: str | None = None
    source_lineno: int | None = None


@dataclass(frozen=True, slots=True)
class GeneratedScript:
    """Complete AgentQL migration artifact for one legacy file.

    Attributes:
        query: AgentQL query text passed to ``page.query_elements``.
        python_source: Full generated Python module.
        url: Navigation target used in ``page.goto``.
        field_names: Ordered AgentQL field names in the query.
        actions: Ordered interaction steps after the query.
        source_path: Optional path of the legacy script that was migrated.
    """

    query: str
    python_source: str
    url: str
    field_names: tuple[str, ...]
    actions: tuple[GeneratedAction, ...]
    source_path: str | None = None


def _python_string_literal(value: str) -> str:
    """Render *value* as a safely escaped Python string literal."""
    return repr(value)


def build_agentql_query(translations: Sequence[TranslatedLocator]) -> str:
    """Build an AgentQL query block from translated field names.

    Emits a multi-line query such as::

        {
            user_input
            submit_button
        }

    Duplicate names are kept once (first occurrence wins) so the query
    stays valid even if uniqueness slipped upstream.
    """
    seen: set[str] = set()
    fields: list[str] = []
    for item in translations:
        name = item.name.strip()
        if not name or name in seen:
            continue
        if not is_valid_agentql_name(name):
            continue
        seen.add(name)
        fields.append(name)

    if not fields:
        return "{\n}"

    body = "\n".join(f"    {name}" for name in fields)
    return "{\n" + body + "\n}"


def action_statement(action: GeneratedAction, *, response_var: str = "elements") -> str:
    """Return one Python statement that performs *action* on *response_var*.

    Value-bearing interactions (fill / type / select_option) include a
    safely quoted literal. Unsupported / none interactions become a
    comment so generation never invents a bogus Playwright call.
    """
    method = _INTERACTION_METHODS.get(action.interaction)
    target = f"{response_var}.{action.name}"

    if method is None:
        return (
            f"# skip {action.name}: unsupported interaction "
            f"{action.interaction.value!r}"
        )

    if action.interaction in _VALUE_INTERACTIONS:
        literal = _python_string_literal(action.fill_value or "")
        return f"{target}.{method}({literal})"

    return f"{target}.{method}()"


def generate_script(
    translations: Sequence[TranslatedLocator],
    *,
    url: str = DEFAULT_URL,
    function_name: str = DEFAULT_FUNCTION_NAME,
    headless: bool = True,
    source_path: str | None = None,
) -> GeneratedScript:
    """Emit an AgentQL + sync_playwright script (stub)."""
    raise NotImplementedError("script generator not yet implemented")
