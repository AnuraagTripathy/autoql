# Legacy-to-AgentQL Migrator

CLI tool that statically analyzes brittle Playwright scripts and migrates
CSS/XPath locators into semantic AgentQL queries.

## Status

- Done: `sample_legacy.py` fixture, deps/env stubs, **`parser.py`** AST extractor
- Next: `translator.py` (OpenAI gpt-4o-mini → snake_case AgentQL names + fallbacks)

## Quick check

```bash
python parser.py sample_legacy.py
python -m unittest test_parser.py
```
