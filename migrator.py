"""
Rich CLI orchestrator for Legacy-to-AgentQL migration.

Wires ``parser`` → ``translator`` → ``generator`` into a single entrypoint
with progress spinners, a locator summary table, and a success panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from generator import (
    DEFAULT_FUNCTION_NAME,
    GeneratedScript,
    extract_goto_url,
    generate_script,
    script_as_dict,
)
from parser import ParsedLocator, parse_file
from translator import (
    DEFAULT_MODEL,
    TranslatedLocator,
    translate_locators,
    translations_as_dicts,
)

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
    function_name: str = DEFAULT_FUNCTION_NAME,
    headless: bool = True,
    force_fallback: bool = False,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    write: bool = True,
) -> MigrationResult:
    """Parse → translate → generate for a legacy Python script on disk.

    Args:
        path: Brittle Playwright/Selenium script to migrate.
        output: Destination for generated Python; defaults to
            ``<stem>_agentql.py`` beside *path* when *write* is true.
        url: Override ``page.goto`` target; otherwise first literal goto.
        function_name: Entrypoint def name in the generated module.
        headless: Whether Chromium launches headless in the output.
        force_fallback: Skip OpenAI and use heuristic translator names.
        api_key: Optional OpenAI key; defaults to ``OPENAI_API_KEY``.
        model: Chat model id (default: ``gpt-4o-mini``).
        write: When true, persist ``script.python_source`` to disk.

    Returns:
        :class:`MigrationResult` with locators, translations, and script.
    """
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    locators = parse_file(file_path)
    translations = translate_locators(
        locators,
        api_key=api_key,
        model=model,
        force_fallback=force_fallback,
    )
    resolved_url = url or extract_goto_url(source) or "https://example.com"
    script = generate_script(
        translations,
        url=resolved_url,
        function_name=function_name,
        headless=headless,
        source_path=str(file_path),
    )

    output_path: str | None = None
    if write:
        out = Path(output) if output is not None else default_output_path(file_path)
        out.write_text(script.python_source, encoding="utf-8")
        output_path = str(out)

    return MigrationResult(
        source_path=str(file_path),
        locators=tuple(locators),
        translations=tuple(translations),
        script=script,
        output_path=output_path,
    )


def migration_as_dict(result: MigrationResult) -> dict[str, object]:
    """Serialize a :class:`MigrationResult` for JSON / tooling."""
    return {
        "source_path": result.source_path,
        "output_path": result.output_path,
        "locator_count": len(result.locators),
        "translation_count": len(result.translations),
        "translations": translations_as_dicts(result.translations),
        "script": script_as_dict(result.script),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint (wired after Rich helpers land)."""
    raise NotImplementedError("Rich CLI wiring lands in a later commit")


if __name__ == "__main__":
    raise SystemExit(main())
