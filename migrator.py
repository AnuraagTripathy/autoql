"""
Rich CLI orchestrator for Legacy-to-AgentQL migration.

Wires ``parser`` → ``translator`` → ``generator`` into a single entrypoint
with progress spinners, a locator summary table, and a success panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from generator import GeneratedScript
from parser import ParsedLocator
from translator import TranslatedLocator

DEFAULT_OUTPUT_SUFFIX = "_agentql.py"


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """End-to-end migration artifact for one legacy script.

    Attributes:
        source_path: Path of the brittle Playwright/Selenium input.
        locators: AST-extracted locators from ``parser.parse_file``.
        translations: Semantic AgentQL names from ``translator``.
        script: Generated AgentQL + sync_playwright module.
        output_path: Where ``script.python_source`` was written, if any.
    """

    source_path: str
    locators: tuple[ParsedLocator, ...]
    translations: tuple[TranslatedLocator, ...]
    script: GeneratedScript
    output_path: str | None = None


def default_output_path(source: str | Path) -> Path:
    """Return ``<stem>_agentql.py`` next to *source*."""
    path = Path(source)
    return path.with_name(f"{path.stem}{DEFAULT_OUTPUT_SUFFIX}")


def migrate_file(
    path: str | Path,
    *,
    output: str | Path | None = None,
    url: str | None = None,
    function_name: str = "run_migrated_flow",
    headless: bool = True,
    force_fallback: bool = False,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    write: bool = True,
) -> MigrationResult:
    """Parse → translate → generate for *path* (implemented next)."""
    raise NotImplementedError("migrate_file orchestration lands in the next commit")


def migration_as_dict(result: MigrationResult) -> dict[str, object]:
    """Serialize a :class:`MigrationResult` for JSON / tooling (stub)."""
    raise NotImplementedError("migration_as_dict lands with orchestration")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint (wired after Rich helpers land)."""
    raise NotImplementedError("Rich CLI wiring lands in a later commit")


if __name__ == "__main__":
    raise SystemExit(main())
