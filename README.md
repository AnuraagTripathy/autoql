# AutoQL

Takes a Playwright or Selenium script full of brittle CSS and XPath selectors and rewrites it into semantic AgentQL queries.

**Live demo: [autoql-demo.vercel.app](https://autoql-demo.vercel.app)**

## What is actually interesting here

The obvious approach is to hand the whole script to a model and ask for a rewrite. That produces plausible code that silently drops call sites, which is the one failure mode a migration tool cannot have.

So the pipeline is static first and generative last, in three stages:

1. **`parser.py`** walks the Python AST and finds locator call sites structurally: `page.locator(...)`, `driver.find_element(By.XPATH, ...)`, and friends. It knows where each one is and what it does with the result, which means nothing gets missed and nothing outside a locator gets touched.
2. **`translator.py`** is the only stage that needs a model, and it does one narrow job: name the control that a selector refers to. `div.cta-btn-primary > span` becomes `submit_button`. Because the task is naming rather than code generation, the offline heuristic fallback is genuinely usable, and `--fallback` runs the whole tool with no API key at all.
3. **`generator.py`** emits an AgentQL `query_elements` module from the structured result, not from model output. The generated script is deterministic given the same parse and names.

The web demo is not a wrapper around the CLI. `web/lib/parser.ts`, `translator.ts`, and `generator.ts` are a TypeScript reimplementation of the same three stages running client-side, which is why the demo works instantly with no backend and no key, and matches `python migrator.py --fallback` exactly.

## Stack

Python 3 with the standard library `ast` module, Rich for the CLI, and OpenAI (`gpt-4o-mini`) for naming when a key is present. Targets Playwright, Selenium, and AgentQL. The demo is Next.js and TypeScript on Vercel. Tests are `unittest`.

## Running it locally

```bash
pip install -r requirements.txt
python migrator.py sample_legacy.py --fallback            # writes sample_legacy_agentql.py
python migrator.py sample_legacy.py --fallback --stdout   # print instead
```

`--fallback` uses the offline heuristic namer. Drop it and set `OPENAI_API_KEY` (see `.env.example`) to use the model instead. Either way, the *generated* script needs `AGENTQL_API_KEY` at runtime, since that is what AgentQL itself requires.

Each stage runs standalone, which is the fastest way to see what it does:

```bash
python parser.py sample_legacy.py
python translator.py sample_legacy.py --fallback
python generator.py sample_legacy.py --fallback
```

Tests:

```bash
python -m unittest test_parser.py test_translator.py test_generator.py test_migrator.py
```

The web demo:

```bash
cd web && npm install && npm run dev
```

## What is unfinished

- Python input only. The AST parser has no equivalent for JavaScript or TypeScript Playwright scripts, which is most of the real-world corpus.
- The translator names a selector from the selector string and its surrounding call, without ever loading the page. A class name like `.x-1a2b3c` from a compiled stylesheet gives it nothing to work with, and the heuristic fallback degrades badly there.
- Generated scripts are not verified against a live page. Nothing checks that the emitted AgentQL query actually resolves.
- Async Playwright and page object patterns are not handled; the generator emits `sync_playwright` structure.
- `sample_legacy.py` is the only fixture, so coverage of unusual locator shapes is thin.
