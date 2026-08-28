# Contributing to ns-lite

Thanks for your interest in contributing.

## Setup

```bash
git clone https://github.com/Salar-prog/netscan-lite.git
cd netscan-lite
pip install -e ".[xlsx,test]"
```

## Development

```bash
# Run tests
pytest -v

# Lint
ruff check .
ruff format .
```

## Pull Requests

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure `pytest -v` passes
5. Open a PR against `main`

Keep PRs focused — one feature or fix per PR.

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, ns-lite version)
