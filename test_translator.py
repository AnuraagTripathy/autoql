"""Unit tests for the Legacy-to-AgentQL OpenAI / heuristic translator."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from parser import Interaction, LocatorKind, ParsedLocator, parse_file
from translator import (
    TranslationSource,
    ensure_unique,
    heuristic_name,
    is_valid_agentql_name,
    main,
    to_snake_case,
    translate_locator,
    translate_locators,
    translations_as_dicts,
)

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample_legacy.py"


def _loc(
    selector: str,
    *,
    interaction: Interaction = Interaction.CLICK,
    kind: LocatorKind = LocatorKind.CSS,
    fill_value: str | None = None,
) -> ParsedLocator:
    return ParsedLocator(
        selector=selector,
        kind=kind,
        interaction=interaction,
        lineno=1,
        col_offset=0,
        fill_value=fill_value,
        raw_call=interaction.value,
    )


class SnakeCaseTests(unittest.TestCase):
    def test_to_snake_case_and_validation(self) -> None:
        self.assertEqual(to_snake_case("ShowPassword"), "show_password")
        self.assertEqual(to_snake_case("btn-primary"), "btn_primary")
        self.assertEqual(to_snake_case("123go"), "el_123go")
        self.assertEqual(to_snake_case("!!!"), "element")
        self.assertTrue(is_valid_agentql_name("user_input"))
        self.assertFalse(is_valid_agentql_name("UserInput"))
        self.assertFalse(is_valid_agentql_name(""))

    def test_ensure_unique_suffixes(self) -> None:
        used: set[str] = set()
        self.assertEqual(ensure_unique("button", used), "button")
        self.assertEqual(ensure_unique("button", used), "button_2")
        self.assertEqual(ensure_unique("button", used), "button_3")


class HeuristicTests(unittest.TestCase):
    def test_prefers_name_attr_over_form_class(self) -> None:
        loc = _loc(
            "div#app > form.login-form > input[name='user']",
            interaction=Interaction.FILL,
        )
        self.assertEqual(heuristic_name(loc), "user_input")

    def test_password_testid_and_xpath_button(self) -> None:
        pwd = _loc(
            "input[type='password'][data-testid='pwd']",
            interaction=Interaction.FILL,
        )
        btn = _loc(
            "//div[@id='footer']//button[contains(@class, 'btn-primary')]",
            kind=LocatorKind.XPATH,
            interaction=Interaction.CLICK,
        )
        self.assertEqual(heuristic_name(pwd), "pwd_input")
        self.assertEqual(heuristic_name(btn), "btn_primary_button")


class TranslateTests(unittest.TestCase):
    def test_force_fallback_skips_openai(self) -> None:
        loc = _loc("input[name='email']", interaction=Interaction.FILL)
        with patch("translator._openai_name_for") as mocked:
            result = translate_locator(loc, force_fallback=True, api_key="sk-test")
        mocked.assert_not_called()
        self.assertEqual(result.source, TranslationSource.FALLBACK)
        self.assertEqual(result.name, "email_input")

    def test_openai_success_path(self) -> None:
        loc = _loc("button.x", interaction=Interaction.CLICK)
        with patch(
            "translator._openai_name_for",
            return_value=("submit_button", "primary CTA"),
        ):
            result = translate_locator(loc, api_key="sk-test")
        self.assertEqual(result.source, TranslationSource.OPENAI)
        self.assertEqual(result.name, "submit_button")
        self.assertEqual(result.rationale, "primary CTA")

    def test_openai_failure_falls_back(self) -> None:
        loc = _loc("input[name='user']", interaction=Interaction.FILL)
        with patch("translator._openai_name_for", return_value=None):
            result = translate_locator(loc, api_key="sk-test")
        self.assertEqual(result.source, TranslationSource.FALLBACK)
        self.assertEqual(result.name, "user_input")
        self.assertIn("heuristic", result.rationale or "")

    def test_batch_uniqueness(self) -> None:
        locs = [
            _loc("button.save", interaction=Interaction.CLICK),
            _loc("button.save", interaction=Interaction.CLICK),
        ]
        with patch(
            "translator._openai_name_for",
            return_value=("save_button", "dup"),
        ):
            results = translate_locators(locs, api_key="sk-test")
        self.assertEqual([r.name for r in results], ["save_button", "save_button_2"])


class SampleFixtureTests(unittest.TestCase):
    def test_sample_legacy_fallback_names(self) -> None:
        translations = translate_locators(parse_file(SAMPLE), force_fallback=True)
        self.assertEqual(len(translations), 4)
        self.assertEqual(
            [t.name for t in translations],
            ["user_input", "icon_eye_button", "pwd_input", "btn_primary_button"],
        )
        self.assertTrue(all(t.source is TranslationSource.FALLBACK for t in translations))

    def test_json_serialization_round_trip(self) -> None:
        rows = translations_as_dicts(
            translate_locators(parse_file(SAMPLE), force_fallback=True)
        )
        decoded = json.loads(json.dumps(rows))
        self.assertEqual(decoded[0]["name"], "user_input")
        self.assertEqual(decoded[0]["locator"]["interaction"], "fill")


class MainCliTests(unittest.TestCase):
    def test_main_fallback_on_sample(self) -> None:
        self.assertEqual(main([str(SAMPLE), "--fallback"]), 0)

    def test_main_missing_file(self) -> None:
        self.assertEqual(main(["does-not-exist.py"]), 1)

    def test_openai_helper_parses_mock_client(self) -> None:
        from translator import _openai_name_for

        loc = _loc("#submit", interaction=Interaction.CLICK)
        fake_response = MagicMock()
        fake_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {"name": "submit_button", "rationale": "footer CTA"}
                    )
                )
            )
        ]
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        with patch("openai.OpenAI", return_value=fake_client):
            result = _openai_name_for(loc, api_key="sk-test", model="gpt-4o-mini")

        self.assertEqual(result, ("submit_button", "footer CTA"))


if __name__ == "__main__":
    unittest.main()
