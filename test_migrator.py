"""Unit tests for the Legacy-to-AgentQL Rich CLI migrator."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

from migrator import (
    build_success_panel,
    build_translation_table,
    default_output_path,
    main,
    migrate_file,
    migration_as_dict,
    run_migration_with_status,
)

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample_legacy.py"


class DefaultOutputPathTests(unittest.TestCase):
    def test_stem_agentql_suffix(self) -> None:
        self.assertEqual(
            default_output_path("sample_legacy.py"),
            Path("sample_legacy_agentql.py"),
        )
        self.assertEqual(
            default_output_path(Path("/tmp/flow.py")),
            Path("/tmp/flow_agentql.py"),
        )


class MigrateFileTests(unittest.TestCase):
    def test_migrate_sample_legacy_without_write(self) -> None:
        result = migrate_file(SAMPLE, force_fallback=True, write=False)
        self.assertEqual(result.output_path, None)
        self.assertEqual(len(result.locators), 4)
        self.assertEqual(len(result.translations), 4)
        self.assertEqual(
            list(result.script.field_names),
            ["user_input", "icon_eye_button", "pwd_input", "btn_primary_button"],
        )
        self.assertEqual(result.script.url, "https://example.com/login")
        compile(result.script.python_source, "<generated>", "exec")

    def test_migrate_file_writes_default_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "legacy.py"
            src.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
            result = migrate_file(src, force_fallback=True, write=True)
            out = Path(tmp) / "legacy_agentql.py"
            self.assertEqual(result.output_path, str(out))
            self.assertTrue(out.is_file())
            self.assertIn("query_elements", out.read_text(encoding="utf-8"))

    def test_migrate_file_url_override(self) -> None:
        result = migrate_file(
            SAMPLE,
            force_fallback=True,
            write=False,
            url="https://example.com/custom",
        )
        self.assertEqual(result.script.url, "https://example.com/custom")

    def test_migration_as_dict_json_round_trip(self) -> None:
        result = migrate_file(SAMPLE, force_fallback=True, write=False)
        payload = migration_as_dict(result)
        decoded = json.loads(json.dumps(payload))
        self.assertEqual(decoded["locator_count"], 4)
        self.assertEqual(decoded["script"]["field_names"][0], "user_input")
        self.assertEqual(decoded["translations"][0]["source"], "fallback")


class RichHelperTests(unittest.TestCase):
    def test_translation_table_and_success_panel_render(self) -> None:
        result = migrate_file(SAMPLE, force_fallback=True, write=False)
        console = Console(file=io.StringIO(), width=100, force_terminal=False)
        console.print(build_translation_table(result))
        console.print(build_success_panel(result))
        text = console.file.getvalue()
        self.assertIn("user_input", text)
        self.assertIn("Migration complete", text)
        self.assertIn("https://example.com/login", text)

    def test_run_migration_with_status(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=False)
        result = run_migration_with_status(
            console,
            SAMPLE,
            force_fallback=True,
            write=False,
        )
        self.assertEqual(len(result.translations), 4)


class MainCliTests(unittest.TestCase):
    def test_main_missing_file(self) -> None:
        self.assertEqual(main(["does-not-exist.py"]), 1)

    def test_main_fallback_json(self) -> None:
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(SAMPLE), "--fallback", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["locator_count"], 4)
        self.assertIsNone(payload["output_path"])

    def test_main_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "migrated.py"
            code = main([str(SAMPLE), "--fallback", "-o", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.is_file())
            text = out.read_text(encoding="utf-8")
            compile(text, str(out), "exec")
            self.assertIn("query_elements", text)
            self.assertIn("user_input", text)

    def test_main_stdout_mode(self) -> None:
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([str(SAMPLE), "--fallback", "--stdout"])
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("agentql.wrap", text)
        compile(text, "<stdout>", "exec")


if __name__ == "__main__":
    unittest.main()
