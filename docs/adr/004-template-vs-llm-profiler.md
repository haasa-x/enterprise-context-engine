# ADR 004: Template-based profiler is the v1 default; LLM backend is an interchangeable v1.5 option

## Status

Accepted.

## Context

The profiler turns a user's detected behavioural patterns
(`src/context_engine/profiler/pattern_detector.py` produces a `UserPatterns`
of per-application action cadences, cross-app sequences, active objects, and
parameter defaults) into a natural-language summary — the "NLQ profile"
returned by `GET /v1/users/{userId}/profile` and shown in the
[admin UI](../admin-ui-guide.md).

There are two obvious ways to write that prose. Fill fixed templates from the
structured patterns (deterministic, free, instant), or hand the patterns to an
LLM and let it narrate (richer, more fluent, but requiring an external model,
an API key, network calls, and non-deterministic output). Both consume the
*same* `UserPatterns` input and produce the *same* kind of output — a string —
so the choice is a swappable implementation detail, not an architectural fork.

This must also respect the project-wide constraint that v1 has **zero external
API dependencies** and no LLM on any hot path (see
[ADR 002](002-no-llm-in-ingestion.md)).

## Decision

Define a single abstract interface and make the template backend the v1
default:

- **`ProfileGenerator`** (`src/context_engine/profiler/generator.py`) — an ABC
  with one method, `async generate(patterns: UserPatterns) -> str`. The
  scheduler and the profile API depend only on this interface.
- **`TemplateProfileGenerator`** (`.../template_generator.py`) — the v1
  default. Deterministic string templates over `UserPatterns`. Fast, free,
  predictable, and the baseline any other backend must stay faithful to.
- **`LLMProfileGenerator`** (`.../llm_generator.py`) — the documented v1.5
  option. It already renders `UserPatterns` into a prompt but deliberately does
  **not** call any model in v1; its `_call_model` raises `NotImplementedError`.
- **`build_profile_generator(backend)`** (`.../factory.py`) selects the backend
  from configuration. `CE_PROFILE_GENERATOR_BACKEND` (default `"template"`)
  chooses; `"llm"` is reserved and currently raises until v1.5 wires it in.

The two backends are **Liskov-substitutable**: anywhere a `ProfileGenerator` is
expected, either one can be dropped in without touching the scheduler, the API
route, or the pattern detector. Adding the LLM backend in v1.5 is
**open/closed** — a new subclass plus a branch in the factory, with no existing
generator modified.

## Consequences

- **Deterministic, free default.** Out of the box, profile text is reproducible
  and costs nothing, so it can be asserted exactly in tests and generated for
  every active user on a daily schedule without a bill.
- **No LLM on any request path.** Profiles are generated on a schedule
  (`src/context_engine/profiler/scheduler.py`), and the default backend is
  LLM-free — so even choosing the LLM backend later never adds latency to
  ingestion or intent resolution (consistent with [ADR 002](002-no-llm-in-ingestion.md)).
- **Clean upgrade path.** Teams that want richer prose set
  `CE_PROFILE_GENERATOR_BACKEND=llm` and supply a key in v1.5 — no schema
  change, no API change, no consumer change. The `UserPatterns` contract is the
  stable seam between pattern detection and prose generation.
- **Faithfulness constraint.** The LLM backend must summarise the same
  `UserPatterns` the template backend already renders; it may reword, not
  invent. The template output is the ground truth it is checked against.
- **v1 scope.** The LLM backend is explicitly out of scope for v1 (execution
  plan Part 16) — implemented as an interface and a prompt builder, wired up in
  v1.5.
