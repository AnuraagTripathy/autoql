# Legacy-to-AgentQL Migrator

CLI tool that statically analyzes brittle Playwright scripts and migrates
CSS/XPath locators into semantic AgentQL queries.

## Status

- Done: `sample_legacy.py` fixture, deps/env stubs, **`parser.py`**, **`translator.py`**, **`generator.py`**, **`migrator.py`**
- Architecture complete for the agreed module set — further runs polish only

## Quick check

```bash
python migrator.py sample_legacy.py --fallback
python migrator.py sample_legacy.py --fallback --stdout
python parser.py sample_legacy.py
python translator.py sample_legacy.py --fallback
python generator.py sample_legacy.py --fallback
python -m unittest test_parser.py test_translator.py test_generator.py test_migrator.py
```

`migrator.py` orchestrates parse → translate → generate with a Rich table
and success panel. Pass `--fallback` for offline heuristic names; set
`OPENAI_API_KEY` (see `.env.example`) for gpt-4o-mini naming. Generated
scripts need `AGENTQL_API_KEY` at runtime.
