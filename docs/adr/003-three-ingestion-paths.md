# ADR 003: Three ingestion paths (SDK push, connector pull, log listener)

## Status

Accepted.

## Context

Context Engine is only as useful as the breadth of activity it can observe.
Enterprise applications differ enormously in how much access they give an
integrator:

- Some are **yours** — internal apps whose source you control.
- Some are **third-party but cooperative** — they expose webhooks, a polling
  API, or scheduled exports.
- Some are **closed** — legacy or vendor systems you can neither modify nor
  call, whose only observable output is a log file on disk.

A single ingestion mechanism would strand whole categories of software. An
SDK-only design ignores every app you cannot recompile. A connector-only design
ignores apps with no API surface at all. But all three categories can, one way
or another, produce the same [universal event](../protocol-guide.md) — so the
question is only *how* each hands its events to the platform, not *what* it
hands over.

## Decision

Support **three ingestion paths**, all converging on the same contract and the
same `POST /v1/events` endpoint:

| Path | Mechanism | Use when | Guide |
|---|---|---|---|
| **1 — SDK push** | The app calls a native SDK (`sdk/python/`, `sdk/node/`) at the point an action happens | You control the app's code | [sdk-guide.md](../sdk-guide.md) |
| **2 — Connector pull/translate** | A connector receives webhooks / polls / reads exports and translates them (`connectors/jira/`) | You don't own the code but the app exposes events | [connector-guide.md](../connector-guide.md) |
| **3 — Log listener** | A listener tails a log file, parses lines, and transforms them | The app offers only a log on disk | [log-listener-guide.md](../log-listener-guide.md) |

The paths are deliberately **not** mutually exclusive alternatives that a
project picks between — they are three doors into the *same* pipeline, chosen
per source system by how much access that system grants. Downstream of
`POST /v1/events`, the origin of an event is invisible: the graph writer, the
intent scorer, and the profiler cannot tell (and do not care) whether an event
arrived via SDK, connector, or log listener.

## Consequences

- **Coverage.** Nearly any enterprise system can be onboarded: if you can run
  its code you push (Path 1); if it talks you translate (Path 2); if it only
  writes logs you tail (Path 3).
- **One contract, tested once.** Because all three paths must produce a valid
  universal event, schema conformance is enforced in exactly one place
  (`src/context_engine/core/schema_validator.py`), and everything downstream is
  path-agnostic.
- **Shared conventions.** All three paths share the same producer rules —
  UUID `eventId` for idempotency, `409 Conflict` treated as success, prefer
  `email` as `userIdType` for cross-app identity resolution. The transform step
  of a connector and of a log listener are the same shape (`input -> event |
  None`), so lessons transfer between them.
- **Maintenance surface.** Three producer mechanisms is more to document and
  maintain than one. That cost is bounded because the paths share the contract
  and differ only at their edges; the platform core does not grow with the
  number of paths.
- **v1 scope.** Only the Jira connector ships in v1 (execution plan Part 16);
  the connector and log-listener *guides* exist so third parties can build more
  without changes to the core.
