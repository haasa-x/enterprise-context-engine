# Engineering standards

These are the non-negotiable engineering rules for Context Engine. They are
enforced by the [CI pipeline](#ci-pipeline); a change that violates one does
not merge. This document is linked from [CONTRIBUTING.md](../CONTRIBUTING.md)
and is the single source of truth for "how we write code here".

## Clean Architecture — the dependency rule

Inner layers never import outer layers. Dependencies point inward only. This is
enforced automatically by `tests/test_architecture.py`.

```
        api/  ──────────────► core/
          │                     ▲
          ├───► prediction/ ────┤
          │                     │
          └───► profiler/  ─────┘
```

| Layer | May import from | May **not** import from |
|---|---|---|
| `api/` | `core/`, `prediction/`, `profiler/` | — |
| `prediction/` | `core/` | `api/`, `profiler/` |
| `profiler/` | `core/` | `api/`, `prediction/` |
| `core/` | (standard library, third-party) | `api/`, `prediction/`, `profiler/` |

`core/` is the innermost layer and imports none of the others. This is why the
narrow capability interfaces live in `core/interfaces.py` as
`typing.Protocol`s: `prediction/` and `profiler/` depend on those protocols,
and `core/graph.py`'s `GraphStore` satisfies them structurally, so no inward
layer ever has to import a concrete class from an outer layer.

## SOLID principles, as they appear in this codebase

- **Single Responsibility.** One class, one job. `SchemaValidator`
  (`core/schema_validator.py`) only validates. `GraphStore` (`core/graph.py`)
  only stores. `IntentScorer` (`prediction/scorer.py`) only scores.
  `PatternDetector` (`profiler/pattern_detector.py`) only detects patterns.
- **Open/Closed.** Adding a profile-generator backend means adding a
  `ProfileGenerator` subclass plus one branch in
  `profiler/factory.py::build_profile_generator` — no existing generator is
  edited. Adding a connector never modifies the ingestion core.
- **Liskov Substitution.** `TemplateProfileGenerator` and
  `LLMProfileGenerator` are fully interchangeable behind the `ProfileGenerator`
  ABC (`profiler/generator.py`); the scheduler and profile route depend only on
  the interface. See [ADR 004](adr/004-template-vs-llm-profiler.md).
- **Interface Segregation.** Consumers depend on the narrow slice of behaviour
  they use, not the fat `GraphStore`. `core/interfaces.py` defines
  `HistoryReader` (used by the scorer), `EventWriter` (used by the ingestion
  route), `PatternReader` (used by the pattern detector), and `ProfileStore`
  (used by the profiler and profile API). `GraphStore` implements all of them
  structurally.
- **Dependency Inversion.** `IntentScorer.__init__` receives a `HistoryReader`,
  not a concrete `GraphStore`. `PatternDetector` receives a `PatternReader`.
  High-level policy depends on abstractions, not on the Neo4j-backed
  implementation.

## Naming conventions

- **Modules:** lowercase, underscores, descriptive nouns. **No** `utils.py`,
  `helpers.py`, `misc.py`, `common.py`.
- **Functions:** verb + noun. `write_event()`, `get_user_history()`,
  `build_profile_generator()`. **Never** `process()`, `handle()`, `do_stuff()`.
- **Variables:** descriptive, no abbreviations. `tenant_id`, not `t`;
  `user_history`, not `uh`.
- **Constants:** `UPPER_SNAKE_CASE` (e.g. `_KEYWORD_WEIGHT`,
  `PROFILING_WINDOW_DAYS`).
- **Classes:** `PascalCase`, descriptive noun. `GraphStore`, `IntentScorer` —
  not `Manager`, `Helper`, `Handler`-as-a-catch-all.

## Code limits

- **No file exceeds 300 lines.**
- **No function exceeds 30 lines.**
- **No function takes more than 5 parameters.**
- **No circular imports.**
- **No global mutable state.**
- **No commented-out code.**
- **No `# TODO` / `# FIXME`** — open an issue instead.
- **No wildcard imports** (`from x import *`).
- **Full type annotations on every function signature**, enforced by
  `mypy --strict`.

## Error handling

- **Never swallow exceptions silently.**
- **Use custom domain exceptions** from `core/exceptions.py`. Every one derives
  from `ContextEngineError`, so callers can catch the whole domain with one
  `except` while still discriminating: `SchemaValidationError` (carries the
  full list of failures), `DuplicateEventError`, `TenantMismatchError`,
  `UserNotFoundError`, `InsufficientDataError`.
- **Never expose stack traces in API responses.** The API maps domain
  exceptions to a structured JSON body:

  ```json
  { "error": "validation_error", "detail": "...", "requestId": "..." }
  ```

  See `_error_body` in `api/routes/events.py` and the middleware error
  responses.

## Logging

- Use **`structlog`** for structured JSON logging. No `print()`.
- Every log line carries: `timestamp`, `level`, `tenant_id`, `request_id`, and
  the `event` name (e.g. `"profiler.run_once.completed"`,
  `"tenant.header_mismatch"`).
- **Never log event payloads at `INFO`** — they may contain PII. Payload-level
  detail belongs at `DEBUG` only.

## Security

- **Tenant scoping is enforced at the lowest layer that runs a query.**
  `tenant_query` in `core/graph.py` is the only sanctioned way to run Cypher
  and **raises `ValueError` on any query that does not reference `tenantId`**.
  Direct `tx.run()` calls are banned and caught by `tests/test_architecture.py`.
- **`X-Tenant-Id` header must match the body `tenantId`.**
  `TenantValidationMiddleware` (`api/middleware/tenant.py`) rejects a mismatch
  with `403` before it reaches a handler.
- **Rate limits per tenant:** 1000 events/min and 100 queries/min, via
  `RateLimitMiddleware` (`api/middleware/rate_limit.py`), configurable through
  `CE_EVENTS_RATE_LIMIT_PER_MINUTE` and `CE_INTENT_RATE_LIMIT_PER_MINUTE`.
- **All secrets and configuration come from environment variables** (the `CE_`
  prefix, `config.py`). No credentials in code.

## Testing

- **80% coverage minimum for `src/`**, enforced in CI (`--cov-fail-under=80`).
- **Test names describe behaviour**, e.g.
  `test_event_with_missing_tenant_id_returns_validation_error()`.
- **Arrange–Act–Assert** structure.
- **`testcontainers`** runs a real, disposable Neo4j in integration tests —
  no mocking the database.
- **Tests must not depend on execution order.**
- **Tenant isolation is explicitly tested** (`tests/test_tenant_isolation.py`).

## CI pipeline

Every pull request must pass all of the following (see
[`../.github/workflows/ci.yml`](../.github/workflows/ci.yml)):

```
├── ruff check .                              # lint
├── mypy --strict src/                        # full static typing
├── pytest --cov=src/ --cov-fail-under=80     # tests + coverage gate
├── test_architecture.py                      # dependency-rule enforcement
└── doc-link-check                            # no broken/orphaned doc links
```

All must pass. No exceptions. The architecture test and the doc-link check run
as part of the suite, so a layering violation or a broken relative link in
`docs/` fails CI the same way a failing unit test does.
