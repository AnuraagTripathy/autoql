# Legacy-to-AgentQL Migrator

CLI tool that statically analyzes brittle Playwright scripts and migrates
CSS/XPath locators into semantic AgentQL queries.

## Status

- Done: `sample_legacy.py` fixture, deps/env stubs, **`parser.py`**, **`translator.py`**, **`generator.py`**
- Next: `migrator.py` (Rich CLI orchestrating parse → translate → generate)

## Quick check

```bash
python parser.py sample_legacy.py
python translator.py sample_legacy.py --fallback
python generator.py sample_legacy.py --fallback
python -m unittest test_parser.py test_translator.py test_generator.py
```

`translator.py` / `generator.py` use OpenAI `gpt-4o-mini` when `OPENAI_API_KEY`
is set (see `.env.example`); pass `--fallback` for offline heuristic names.
Generated scripts need `AGENTQL_API_KEY` at runtime.
