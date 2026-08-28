# Contributing to ns-lite

Thanks for your interest in contributing.

## Setup

```bash
git clone https://github.com/Salar-prog/netscan-lite.git
cd netscan-lite
pip install -e ".[xlsx,test,docs]"
```

This installs ns-lite with XLSX support, test dependencies, and MkDocs for docs.

## Development

```bash
# Run tests
pytest -v

# Lint
ruff check .

# Format
ruff format .

# Build docs locally
mkdocs serve
# Open http://localhost:8000
```

## Project Structure

```
netscan_lite/
  scanner/
    runner.py       # nmap wrapper, XML parsing
    classifier.py   # quarantine state machine
    service.py      # scan orchestration (called by CLI + API)
  models.py         # Group, IPAddress (SQLModel)
  db.py             # SQLModel engine + session
  config.py         # pydantic-settings configuration
  importer.py       # CSV/XLSX parser
  cli.py            # Click CLI (ns-lite binary)
  api.py            # FastAPI REST endpoints
  main.py           # app entrypoint
tests/
  conftest.py       # shared fixtures (in-memory SQLite)
  test_*.py         # test suites
docs/               # MkDocs Material site
```

## Running Tests

```bash
pytest -v                    # all tests
pytest tests/test_cli.py     # single file
pytest -k test_import        # by name pattern
```

Tests use in-memory SQLite (no nmap required — scanner is mocked).

## Code Style

- Type hints on all function signatures
- Ruff for linting and formatting (line length: 120)
- Keep functions small and focused
- Follow existing patterns in the codebase
- No new dependencies without discussion

## Pull Requests

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure `pytest -v` passes
5. Ensure `ruff check .` and `ruff format --check .` pass
6. Open a PR against `main`

Keep PRs focused — one feature or fix per PR.

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, ns-lite version, nmap version)

## Architecture Decisions

If you're making a change that affects the quarantine logic, scanner behavior, or API contract, please open an issue first to discuss the approach. These are the critical paths — changes here need careful review.
