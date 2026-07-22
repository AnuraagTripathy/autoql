"""
AgentQL code generator for Legacy-to-AgentQL migration.

Turns a batch of ``TranslatedLocator`` records into an AgentQL query
string and a runnable ``sync_playwright`` script that wraps the page,
calls ``query_elements``, and replays the original interactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from parser import Interaction
from translator import TranslatedLocator

DEFAULT_URL = "https://example.com"
DEFAULT_FUNCTION_NAME = "run_migrated_flow"


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


def build_agentql_query(translations: Sequence[TranslatedLocator]) -> str:
    """Build an AgentQL query block from translated field names (stub)."""
    raise NotImplementedError("AgentQL query builder not yet implemented")


def action_statement(action: GeneratedAction, *, response_var: str = "elements") -> str:
    """Return one Python statement for *action* (stub)."""
    raise NotImplementedError("action statement emitter not yet implemented")


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
