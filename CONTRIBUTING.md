# Contributing to Context Engine

Thanks for your interest in contributing.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d neo4j
```

## Before opening a pull request

- `ruff check src tests` — must pass with zero errors
- `mypy --strict src` — must pass with zero errors
- `pytest` — all tests must pass, coverage stays at or above 80% for `src/`

## Engineering standards

All code must follow the project's [engineering standards](docs/ENGINEERING_STANDARDS.md)
— Clean Architecture's dependency rule, SOLID, naming and code-size limits,
error handling, logging, security, and testing. They are enforced in CI. Read
that document before opening a pull request; the highlights below are a
reminder, not a replacement.

## Guidelines

- No `# TODO` / `# FIXME` comments — open an issue instead.
- No commented-out code.
- No `print()` — use `structlog` for logging.
- Every public function needs a docstring.
- All configuration goes through `src/context_engine/config.py` via environment
  variables — never hardcode config values.
- Keep pull requests scoped to a single change; describe the "why" in the
  description, not in code comments.

## Reporting issues

Use the issue templates under `.github/ISSUE_TEMPLATE/`.

## License

By contributing, you agree that your contributions will be licensed under the
Apache License 2.0.
