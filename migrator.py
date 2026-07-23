"""
Rich CLI orchestrator for Legacy-to-AgentQL migration.

Wires ``parser`` → ``translator`` → ``generator`` into a single entrypoint
with progress spinners, a locator summary table, and a success panel.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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


def build_translation_table(result: MigrationResult) -> Table:
    """Build a Rich table summarizing migrated locators and AgentQL names."""
    table = Table(
        title="Migrated locators",
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("Line", justify="right", style="dim", width=5)
    table.add_column("Action", style="cyan", min_width=8)
    table.add_column("Source", style="magenta", min_width=8)
    table.add_column("AgentQL name", style="green", min_width=16)
    table.add_column("Selector", overflow="fold")

    for item in result.translations:
        table.add_row(
            str(item.locator.lineno),
            item.locator.interaction.value,
            item.source.value,
            item.name,
            item.locator.selector,
        )
    return table


def build_success_panel(result: MigrationResult) -> Panel:
    """Build a Rich success panel summarizing the migration outcome."""
    lines = [
        f"Source:  {result.source_path}",
        f"Fields:  {len(result.script.field_names)}",
        f"Actions: {len(result.script.actions)}",
        f"URL:     {result.script.url}",
    ]
    if result.output_path:
        lines.append(f"Wrote:   {result.output_path}")
    else:
        lines.append("Wrote:   (stdout / not persisted)")

    body = Text("\n".join(lines))
    return Panel(
        body,
        title="[bold green]Migration complete[/bold green]",
        border_style="green",
        expand=False,
    )


def run_migration_with_status(
    console: Console,
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
    """Run :func:`migrate_file` under a Rich status spinner.

    Parameters mirror :func:`migrate_file`; the console only drives the
    spinner label while work runs.
    """
    label = f"Migrating {path}…"
    with console.status(label, spinner="dots"):
        return migrate_file(
            path,
            output=output,
            url=url,
            function_name=function_name,
            headless=headless,
            force_fallback=force_fallback,
            api_key=api_key,
            model=model,
            write=write,
        )


def _load_dotenv_if_present() -> None:
    """Best-effort ``.env`` load so local OpenAI keys work without exporting."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate a brittle Playwright/Selenium script to AgentQL via "
            "parse → translate → generate, with a Rich progress UI."
        ),
    )
    parser.add_argument(
        "script",
        nargs="?",
        default="sample_legacy.py",
        help="Legacy Python file to migrate (default: sample_legacy.py)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write generated Python here (default: <stem>_agentql.py)",
    )
    parser.add_argument(
        "--url",
        help="Override page.goto URL (default: first literal goto, else example.com)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the Rich UI",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Skip OpenAI naming and use heuristic translator names only",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Generate Chromium launch with headless=False",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print generated Python to stdout and skip writing a file",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI chat model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--function-name",
        default=DEFAULT_FUNCTION_NAME,
        help=f"Generated entrypoint name (default: {DEFAULT_FUNCTION_NAME})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint: Rich-orchestrated parse → translate → generate."""
    args = _build_arg_parser().parse_args(argv)
    path = Path(args.script)
    console = Console(stderr=True)

    if not path.is_file():
        console.print(f"[red]error:[/red] file not found: {path}")
        return 1

    _load_dotenv_if_present()
    if args.stdout:
        write = False
    elif args.json:
        write = args.output is not None
    else:
        write = True

    result = run_migration_with_status(
        console,
        path,
        output=args.output,
        url=args.url,
        function_name=args.function_name,
        headless=not args.headed,
        force_fallback=args.fallback,
        model=args.model,
        write=write,
    )

    if args.json:
        print(json.dumps(migration_as_dict(result), indent=2))
        return 0

    if args.stdout:
        # Generated module on stdout; Rich chrome stays on stderr.
        sys.stdout.write(result.script.python_source)
        if not result.script.python_source.endswith("\n"):
            sys.stdout.write("\n")

    console.print()
    console.print(build_translation_table(result))
    console.print()
    console.print(build_success_panel(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
