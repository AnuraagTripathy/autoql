# AGENTS.md

## Cursor Cloud specific instructions

This is a small Python 3.12 CLI project (Legacy-to-AgentQL Migrator). The migrator CLI is still being built incrementally; today the only runnable file is `sample_legacy.py`, a Playwright fixture that represents the "brittle legacy script" the future migrator will consume.

### Environment
- Dependencies are installed into a virtualenv at `.venv/` (created by the startup update script). Activate it before running anything: `source .venv/bin/activate`.
- Playwright browser binaries (Chromium) are installed via `python -m playwright install chromium`. The system-level browser libraries are already present in the VM image; if a fresh VM ever lacks them, run `python -m playwright install-deps chromium` (needs sudo).
- Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` and `AGENTQL_API_KEY` for real end-to-end migration runs. These are external SaaS keys and are not required just to run the Playwright fixture.

### Run / lint / test / build
- Run the fixture: `python sample_legacy.py`. Note: it navigates to the live `https://example.com/login` and intentionally times out on the first `.fill()` because example.com has no such form — this is expected fixture behavior (the selectors are deliberately brittle), not an environment failure.
- Lint: no linter is configured in the repo. Use `python -m py_compile <file>` for a basic syntax check.
- Tests: no test suite exists yet. `pytest` is installed (pulled in by `agentql`); `python -m pytest` currently collects 0 tests.
- Build: none — this is a plain (non-packaged) Python project with no build step.
