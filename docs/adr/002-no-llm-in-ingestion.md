# ADR 002: No LLM, embeddings, or external APIs on the ingestion and prediction path

## Status

Accepted.

## Context

Context Engine ingests user-activity events and answers two questions —
"what is this user trying to do right now?" (`resolve-intent`) and "who is this
user?" (`get-profile`). A tempting default for a 2020s system like this would
be to reach for an LLM or an embedding model somewhere on the hot path: extract
entities from event text, embed actions for similarity search, or have a model
rank candidate intents.

Every event this system ingests, however, is **already structured**. The
[universal event contract](../protocol-guide.md) declares the actor, action
type, action category, object type, object id, and timestamp as typed fields.
There is nothing to *extract* — the entities are handed to us. The two hot
paths have hard latency targets (ingestion **p99 < 20ms**, intent resolution
p99 < 100ms), run in multi-tenant enterprise environments where data may not
leave the boundary, and must come up with `docker compose up` and no secrets.

## Decision

**No LLM, no embedding model, no vector store, and no external API call sits on
the ingestion path or the prediction path.**

- **Ingestion** (`src/context_engine/api/routes/events.py` →
  `src/context_engine/core/graph.py`) reads known JSON fields and writes nodes
  and edges. Validation is JSON Schema plus a timestamp check
  (`src/context_engine/core/schema_validator.py`). No model is loaded.
- **Prediction** (`src/context_engine/prediction/scorer.py`) scores candidate
  actions with a deterministic formula: keyword match (0.4) + recency decay,
  3-day half-life (0.3) + frequency (0.3). The keyword table
  (`src/context_engine/prediction/keyword_table.py`) is a plain word-boundary
  lookup, not an ML model. Predictions are always grounded in actions the user
  has actually performed.
- **Profiling** (`src/context_engine/profiler/pattern_detector.py`) derives
  cadence, sequences, and defaults by counting and grouping — no model.

### The one optional LLM touchpoint

The *only* place an LLM may ever appear is the **profile generator backend**,
and even there it is optional and off the hot path. The v1 default,
`TemplateProfileGenerator`, is fully deterministic and LLM-free. An
`LLMProfileGenerator` is defined as the documented v1.5 extension point behind
the same interface, selected by `CE_PROFILE_GENERATOR_BACKEND`. Profile
generation runs on a schedule (default daily), not per request, so even the
LLM backend never touches ingestion or intent-resolution latency. See
[ADR 004](004-template-vs-llm-profiler.md) for that decision in full.

## Consequences

- **Determinism.** The same events always produce the same graph, the same
  scores, and (with the template backend) the same profile text. This makes the
  system testable with exact assertions and reproducible in CI.
- **Cost.** No per-event or per-query inference cost. The system's marginal
  cost is Neo4j and CPU.
- **Privacy.** No event data is sent to a third-party model or API. The system
  runs fully self-contained (see the "zero external API dependencies"
  constraint in [architecture.md](../architecture.md)).
- **Latency.** Meeting **ingestion p99 < 20ms** is achievable because the write
  path is a validate-and-store with no model in the loop; there is no inference
  tail to blow the budget.
- **Tradeoff.** The prediction and template-profile output is only as rich as
  structured counting allows — it cannot infer intent from free-form prose it
  was never given. Anything requiring generative language is confined to the
  optional, scheduled, interchangeable profile backend, never the hot path.
  Trained sequence models (Markov/LSTM/Transformer) are explicitly out of scope
  for v1 (execution plan Part 16).
