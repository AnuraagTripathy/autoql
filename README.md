# Legacy-to-AgentQL Migrator

CLI tool that statically analyzes brittle Playwright scripts and migrates
CSS/XPath locators into semantic AgentQL queries.

## Status

- Done: `sample_legacy.py` fixture, deps/env stubs, **`parser.py`**, **`translator.py`**
- Next: `generator.py` (emit AgentQL + sync_playwright script from translated names)

## Quick check

```bash
python parser.py sample_legacy.py
python translator.py sample_legacy.py --fallback
python -m unittest test_parser.py test_translator.py
```

`translator.py` uses OpenAI `gpt-4o-mini` when `OPENAI_API_KEY` is set
(see `.env.example`); pass `--fallback` for offline heuristic names.
