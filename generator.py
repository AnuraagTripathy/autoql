"""
AgentQL code generator for Legacy-to-AgentQL migration.

Turns a batch of ``TranslatedLocator`` records into an AgentQL query
string and a runnable ``sync_playwright`` script that wraps the page,
calls ``query_elements``, and replays the original interactions.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from parser import Interaction, parse_file
from translator import (
    TranslatedLocator,
    is_valid_agentql_name,
    translate_locators,
)

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


def field_names(translations: Sequence[TranslatedLocator]) -> tuple[str, ...]:
    """Return ordered unique valid AgentQL field names from *translations*."""
    query = build_agentql_query(translations)
    names = [
        line.strip()
        for line in query.splitlines()
        if line.strip() and line.strip() not in {"{", "}"}
    ]
    return tuple(names)


def translations_to_actions(
    translations: Sequence[TranslatedLocator],
) -> tuple[GeneratedAction, ...]:
    """Project translations into ordered :class:`GeneratedAction` steps."""
    actions: list[GeneratedAction] = []
    for item in translations:
        if not is_valid_agentql_name(item.name):
            continue
        actions.append(
            GeneratedAction(
                name=item.name,
                interaction=item.locator.interaction,
                fill_value=item.locator.fill_value,
                source_lineno=item.locator.lineno,
            )
        )
    return tuple(actions)


def _render_python_module(
    *,
    query: str,
    actions: Sequence[GeneratedAction],
    url: str,
    function_name: str,
    headless: bool,
    source_path: str | None,
) -> str:
    """Assemble a complete sync_playwright + AgentQL Python module."""
    origin = source_path or "legacy script"
    url_lit = _python_string_literal(url)
    headless_lit = "True" if headless else "False"
    # Keep QUERY as a triple-quoted string with the AgentQL block indented.
    query_literal = '"""\n' + query + '\n"""'

    action_lines = [
        f"        {action_statement(action)}" for action in actions
    ]
    if action_lines:
        actions_block = "\n".join(action_lines)
    else:
        actions_block = "        pass  # no interactions discovered"

    return f'''\
"""
Auto-generated AgentQL migration of {origin}.

Regenerate with ``python generator.py`` — do not hand-edit locators here.
Requires AGENTQL_API_KEY (see .env.example).
"""

import agentql
from playwright.sync_api import sync_playwright

QUERY = {query_literal}


def {function_name}() -> None:
    """Run the migrated flow with semantic AgentQL selectors."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless={headless_lit})
        page = agentql.wrap(browser.new_page())
        page.goto({url_lit})

        elements = page.query_elements(QUERY)
{actions_block}

        browser.close()


if __name__ == "__main__":
    {function_name}()
'''


def generate_script(
    translations: Sequence[TranslatedLocator],
    *,
    url: str = DEFAULT_URL,
    function_name: str = DEFAULT_FUNCTION_NAME,
    headless: bool = True,
    source_path: str | None = None,
) -> GeneratedScript:
    """Emit an AgentQL query plus a runnable sync_playwright script.

    Args:
        translations: Named locators from ``translator.translate_locators``.
        url: Target for ``page.goto`` (caller may override or detect).
        function_name: Entrypoint def name in the generated module.
        headless: Whether Chromium launches headless.
        source_path: Optional legacy path recorded in the module docstring.
    """
    query = build_agentql_query(translations)
    names = field_names(translations)
    actions = translations_to_actions(translations)
    python_source = _render_python_module(
        query=query,
        actions=actions,
        url=url,
        function_name=function_name,
        headless=headless,
        source_path=source_path,
    )
    return GeneratedScript(
        query=query,
        python_source=python_source,
        url=url,
        field_names=names,
        actions=actions,
        source_path=source_path,
    )


def extract_goto_url(source: str) -> str | None:
    """Return the first literal ``page.goto("...")`` URL in *source*, if any.

    Only constant string arguments are accepted — dynamic URLs are ignored
    so the generator never invents a navigation target from expressions.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "goto":
            continue
        if not node.args:
            continue
        arg0 = node.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            return arg0.value
    return None


def generate_from_file(
    path: str | Path,
    *,
    url: str | None = None,
    function_name: str = DEFAULT_FUNCTION_NAME,
    headless: bool = True,
    force_fallback: bool = False,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
) -> GeneratedScript:
    """Parse → translate → generate for a legacy Python script on disk.

    When *url* is omitted, the first ``page.goto`` literal in the file is
    used; otherwise :data:`DEFAULT_URL`.
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
    resolved_url = url or extract_goto_url(source) or DEFAULT_URL
    return generate_script(
        translations,
        url=resolved_url,
        function_name=function_name,
        headless=headless,
        source_path=str(file_path),
    )


def script_as_dict(script: GeneratedScript) -> dict[str, object]:
    """Serialize a :class:`GeneratedScript` for JSON / migrator wiring."""
    return {
        "query": script.query,
        "python_source": script.python_source,
        "url": script.url,
        "field_names": list(script.field_names),
        "source_path": script.source_path,
        "actions": [
            {
                "name": action.name,
                "interaction": action.interaction.value,
                "fill_value": action.fill_value,
                "source_lineno": action.source_lineno,
            }
            for action in script.actions
        ],
    }


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
            "Generate an AgentQL + sync_playwright script from a brittle "
            "Playwright/Selenium legacy file (parse → translate → emit)."
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
        help="Write generated Python to this path (default: stdout)",
    )
    parser.add_argument(
        "--url",
        help="Override page.goto URL (default: first literal goto, else example.com)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (query + source + actions)",
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
        "--function-name",
        default=DEFAULT_FUNCTION_NAME,
        help=f"Generated entrypoint name (default: {DEFAULT_FUNCTION_NAME})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint: parse → translate → generate AgentQL Playwright code."""
    args = _build_arg_parser().parse_args(argv)
    path = Path(args.script)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    _load_dotenv_if_present()
    script = generate_from_file(
        path,
        url=args.url,
        function_name=args.function_name,
        headless=not args.headed,
        force_fallback=args.fallback,
    )

    if args.json:
        print(json.dumps(script_as_dict(script), indent=2))
        return 0

    if args.output:
        out = Path(args.output)
        out.write_text(script.python_source, encoding="utf-8")
        print(
            f"Wrote {len(script.field_names)} field(s) / "
            f"{len(script.actions)} action(s) → {out}",
            file=sys.stderr,
        )
        return 0

    print(script.python_source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
