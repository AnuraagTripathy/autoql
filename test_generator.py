"""Unit tests for the Legacy-to-AgentQL sync_playwright code generator."""

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from generator import (
    GeneratedAction,
    action_statement,
    build_agentql_query,
    extract_goto_url,
    field_names,
    generate_from_file,
    generate_script,
    main,
    script_as_dict,
    translations_to_actions,
)
from parser import Interaction, LocatorKind, ParsedLocator, parse_file
from translator import TranslationSource, TranslatedLocator, translate_locators

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample_legacy.py"


def _translated(
    name: str,
    *,
    selector: str = "button",
    interaction: Interaction = Interaction.CLICK,
    fill_value: str | None = None,
    lineno: int = 1,
) -> TranslatedLocator:
    return TranslatedLocator(
        locator=ParsedLocator(
            selector=selector,
            kind=LocatorKind.CSS,
            interaction=interaction,
            lineno=lineno,
            col_offset=0,
            fill_value=fill_value,
            raw_call=interaction.value,
        ),
        name=name,
        source=TranslationSource.FALLBACK,
        rationale="test",
    )


class QueryBuilderTests(unittest.TestCase):
    def test_build_agentql_query_dedupes_and_skips_invalid(self) -> None:
        translations = [
            _translated("user_input"),
            _translated("user_input"),
            _translated("NotValid"),
            _translated("submit_button"),
        ]
        query = build_agentql_query(translations)
        self.assertEqual(
            query,
            "{\n    user_input\n    submit_button\n}",
        )
        self.assertEqual(field_names(translations), ("user_input", "submit_button"))

    def test_empty_query(self) -> None:
        self.assertEqual(build_agentql_query([]), "{\n}")


class ActionStatementTests(unittest.TestCase):
    def test_click_and_fill(self) -> None:
        click = GeneratedAction("submit_button", Interaction.CLICK)
        fill = GeneratedAction("user_input", Interaction.FILL, "demo_user")
        self.assertEqual(action_statement(click), "elements.submit_button.click()")
        self.assertEqual(
            action_statement(fill),
            "elements.user_input.fill('demo_user')",
        )

    def test_escapes_quotes_in_fill_value(self) -> None:
        action = GeneratedAction("note_input", Interaction.FILL, "it's \"quoted\"")
        statement = action_statement(action)
        self.assertIn("elements.note_input.fill(", statement)
        value_repr = statement[len("elements.note_input.fill(") : -1]
        self.assertEqual(ast.literal_eval(value_repr), "it's \"quoted\"")

    def test_unsupported_interaction_becomes_comment(self) -> None:
        action = GeneratedAction("mystery", Interaction.NONE)
        self.assertTrue(action_statement(action).startswith("# skip"))


class GenerateScriptTests(unittest.TestCase):
    def test_generate_script_compiles_and_contains_actions(self) -> None:
        translations = [
            _translated(
                "user_input",
                selector="input[name='user']",
                interaction=Interaction.FILL,
                fill_value="demo_user",
            ),
            _translated("submit_button", interaction=Interaction.CLICK, lineno=2),
        ]
        script = generate_script(
            translations,
            url="https://example.com/login",
            source_path="fixture.py",
        )
        self.assertEqual(script.field_names, ("user_input", "submit_button"))
        self.assertEqual(len(script.actions), 2)
        compile(script.python_source, "<generated>", "exec")
        self.assertIn("agentql.wrap", script.python_source)
        self.assertIn("page.query_elements(QUERY)", script.python_source)
        self.assertIn("elements.user_input.fill('demo_user')", script.python_source)
        self.assertIn("elements.submit_button.click()", script.python_source)
        self.assertIn("https://example.com/login", script.python_source)

    def test_translations_to_actions_preserves_order(self) -> None:
        translations = [
            _translated("a_button", lineno=10),
            _translated("b_input", interaction=Interaction.FILL, fill_value="x", lineno=20),
        ]
        actions = translations_to_actions(translations)
        self.assertEqual([a.name for a in actions], ["a_button", "b_input"])
        self.assertEqual(actions[1].fill_value, "x")
        self.assertEqual(actions[0].source_lineno, 10)


class GotoExtractionTests(unittest.TestCase):
    def test_extract_goto_url_literal(self) -> None:
        source = 'page.goto("https://example.com/login")\npage.click("x")\n'
        self.assertEqual(extract_goto_url(source), "https://example.com/login")

    def test_extract_goto_url_skips_dynamic(self) -> None:
        source = "page.goto(base + '/login')\n"
        self.assertIsNone(extract_goto_url(source))


class SampleFixtureTests(unittest.TestCase):
    def test_generate_from_sample_legacy(self) -> None:
        script = generate_from_file(SAMPLE, force_fallback=True)
        self.assertEqual(
            list(script.field_names),
            ["user_input", "icon_eye_button", "pwd_input", "btn_primary_button"],
        )
        self.assertEqual(script.url, "https://example.com/login")
        self.assertEqual(len(script.actions), 4)
        compile(script.python_source, "<generated>", "exec")

        # End-to-end: parser count matches generated actions.
        self.assertEqual(len(parse_file(SAMPLE)), 4)
        self.assertEqual(
            len(translate_locators(parse_file(SAMPLE), force_fallback=True)),
            4,
        )

    def test_script_as_dict_json_round_trip(self) -> None:
        script = generate_from_file(SAMPLE, force_fallback=True)
        payload = script_as_dict(script)
        decoded = json.loads(json.dumps(payload))
        self.assertEqual(decoded["field_names"][0], "user_input")
        self.assertEqual(decoded["actions"][0]["interaction"], "fill")


class MainCliTests(unittest.TestCase):
    def test_main_fallback_stdout(self) -> None:
        self.assertEqual(main([str(SAMPLE), "--fallback"]), 0)

    def test_main_missing_file(self) -> None:
        self.assertEqual(main(["does-not-exist.py"]), 1)

    def test_main_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "migrated.py"
            code = main([str(SAMPLE), "--fallback", "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.is_file())
            text = out.read_text(encoding="utf-8")
            compile(text, str(out), "exec")
            self.assertIn("query_elements", text)


if __name__ == "__main__":
    unittest.main()
