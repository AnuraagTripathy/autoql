"""Unit tests for the Legacy-to-AgentQL AST parser."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from parser import (
    Interaction,
    LocatorKind,
    classify_selector,
    locators_as_dicts,
    main,
    parse_file,
    parse_source,
    summarize,
)

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample_legacy.py"


class ClassifySelectorTests(unittest.TestCase):
    def test_css_and_xpath_heuristics(self) -> None:
        self.assertEqual(classify_selector("div.login > input"), LocatorKind.CSS)
        self.assertEqual(classify_selector("//button[@type='submit']"), LocatorKind.XPATH)
        self.assertEqual(classify_selector("xpath=//nav//a"), LocatorKind.XPATH)
        self.assertEqual(classify_selector(""), LocatorKind.UNKNOWN)


class ParseSourceTests(unittest.TestCase):
    def test_chained_locator_fill_and_click(self) -> None:
        source = """
page.locator("input.email").fill("a@b.com")
page.locator("//button").click()
"""
        locators = parse_source(source)
        self.assertEqual(len(locators), 2)
        self.assertEqual(locators[0].interaction, Interaction.FILL)
        self.assertEqual(locators[0].fill_value, "a@b.com")
        self.assertEqual(locators[0].kind, LocatorKind.CSS)
        self.assertEqual(locators[1].interaction, Interaction.CLICK)
        self.assertEqual(locators[1].kind, LocatorKind.XPATH)

    def test_page_direct_actions(self) -> None:
        source = """
page.fill("#user", "demo")
page.click("button.submit")
"""
        locators = parse_source(source)
        self.assertEqual([loc.interaction for loc in locators], [Interaction.FILL, Interaction.CLICK])
        self.assertEqual(locators[0].selector, "#user")
        self.assertEqual(locators[0].fill_value, "demo")

    def test_selenium_find_element(self) -> None:
        source = """
from selenium.webdriver.common.by import By
driver.find_element(By.CSS_SELECTOR, "a.nav")
driver.find_element(By.XPATH, "//footer")
"""
        locators = parse_source(source)
        self.assertEqual(len(locators), 2)
        self.assertEqual(locators[0].kind, LocatorKind.CSS)
        self.assertEqual(locators[0].interaction, Interaction.NONE)
        self.assertEqual(locators[1].kind, LocatorKind.XPATH)
        self.assertEqual(locators[1].raw_call, "find_element")

    def test_ignores_non_literal_selectors(self) -> None:
        source = """
sel = "div.x"
page.locator(sel).click()
page.click(get_selector())
"""
        self.assertEqual(parse_source(source), [])


class SampleFixtureTests(unittest.TestCase):
    def test_sample_legacy_extracts_expected_locators(self) -> None:
        locators = parse_file(SAMPLE)
        self.assertEqual(len(locators), 4)
        self.assertEqual(summarize(locators), {"fill": 2, "click": 2})
        self.assertTrue(any(loc.kind is LocatorKind.XPATH for loc in locators))
        self.assertEqual(locators[0].fill_value, "demo_user")
        self.assertEqual(locators[2].fill_value, "s3cret!")

    def test_json_cli_round_trip(self) -> None:
        # Capture via locators_as_dicts to ensure serialization stays stable.
        payload = locators_as_dicts(parse_file(SAMPLE))
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        self.assertEqual(len(decoded), 4)
        self.assertEqual(decoded[1]["interaction"], "click")


class MainCliTests(unittest.TestCase):
    def test_main_defaults_to_sample_and_succeeds(self) -> None:
        self.assertEqual(main([str(SAMPLE)]), 0)

    def test_main_missing_file(self) -> None:
        self.assertEqual(main(["does-not-exist.py"]), 1)


if __name__ == "__main__":
    unittest.main()
