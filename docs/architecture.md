# Architecture

Context Engine is a vendor-neutral context resolution service. It collects
structured user-activity events from enterprise applications, stores them in
a temporal knowledge graph, and answers a single question for any calling
LLM or agent: **given this user and this trigger, what are they most likely
trying to do right now?**

```
┌──────────────────┐   ┌──────────────────┐
│  Connectors      │   │  Native SDK      │
│  (pull/translate)│   │  (push directly) │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         v                      v
┌─────────────────────────────────────────────────────┐
│                Context Engine Platform               │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │         FastAPI Ingestion Service            │    │
│  │  POST /v1/events — validate, route, store   │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│                     v                                │
│  ┌─────────────────────────────────────────────┐    │
│  │         Structured Graph Writer              │    │
│  │  Reads known JSON fields -> nodes + edges   │    │
│  │  No LLM, no embeddings, no ML               │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│                     v                                │
│  ┌─────────────────────────────────────────────┐    │
│  │         Neo4j (graph database)               │    │
│  │  Temporal edges, tenant-scoped, Cypher       │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│  ┌─────────────────────────────────────────────┐    │
│  │         Prediction Service                   │    │
│  │  Graph traversal + keyword lookup table     │    │
│  │  No LLM, no ML                              │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│  ┌─────────────────────────────────────────────┐    │
│  │         MCP Server                           │    │
│  │  Wraps resolve-intent as MCP tool           │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │                                │
│  ┌──────────────────┴──────────────────────────┐    │
│  │      Identity Resolution Service             │    │
│  │  Links same user across apps (async)         │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
└─────────────────────────────────────────────────────┘
         │
         v
┌──────────────────┐
│  LLM / Agents /  │
│  Enterprise Apps │
└──────────────────┘
```

## Design constraints

- **Zero LLM dependencies.** Events are structured JSON; entity extraction is
  unnecessary because entities are already declared in the schema fields.
  Nothing in the ingestion or prediction path calls an LLM, embedding model,
  or vector store.
- **Zero external API dependencies.** The system runs fully self-contained —
  no API keys, no managed cloud services required. `docker compose up` is
  enough.
- **Multi-tenant by design.** Every node and edge in the graph carries a
  `tenantId`. All Cypher queries go through `tenant_query`
  (`src/context_engine/core/graph.py`), which refuses to run a query that
  doesn't reference `tenantId` — there is no code path that can silently
  cross a tenant boundary.

## Request flow

**Ingestion** (`POST /v1/events`): validate the event against the JSON
Schema in `schemas/event/v1.0.0/`, stamp an ingestion timestamp, then upsert
`User`, `Application`, and `BusinessObject` nodes and create a `PERFORMED`
edge recording what happened, when. A uniqueness constraint on `eventId`
makes ingestion idempotent — retried events return `409 Conflict`.

**Intent resolution** (`POST /v1/resolve-intent`): pull the user's recent
`PERFORMED` history (default 14-day window, across applications once
identity resolution has linked them), score each distinct action type the
user has actually performed by keyword match against the trigger text,
recency (3-day half-life exponential decay), and frequency, and return the
top-N by confidence. There is no generative step — predictions are always
grounded in things the user has actually done.

## Components

| Component | Location | Responsibility |
|---|---|---|
| Ingestion API | `src/context_engine/api/routes/events.py` | Validates and persists events |
| Graph store | `src/context_engine/core/graph.py` | The only code allowed to run Cypher |
| Intent scorer | `src/context_engine/prediction/scorer.py` | Rules-based confidence scoring |
| Intent API | `src/context_engine/api/routes/intent.py` | `POST /v1/resolve-intent` |
| MCP server | `src/context_engine/mcp/server.py` | Exposes the same scorer as an MCP tool |
| Identity resolver | `src/context_engine/core/identity.py` | Exact-email cross-app identity linking |
| Jira connector | `connectors/jira/` | Webhook -> universal event translation |
| SDKs | `sdk/python/`, `sdk/node/` | Push events directly from an application |

## Multi-tenancy

Tenant isolation is enforced at the lowest layer that can run a query: see
`tenant_query` in `src/context_engine/core/graph.py`. Every `GraphStore`
method threads `tenant_id` into its Cypher `MATCH`/`MERGE` clauses, and
`tenant_query` raises `ValueError` if a query is ever written without a
`tenantId` filter. The `X-Tenant-Id` header (see
`src/context_engine/api/middleware/tenant.py`) is a defense-in-depth check
for callers that already carry a verified tenant identity; it is the
integration point for the auth layer described in
[Security](#security-integration-point), not a substitute for it.

## Security integration point

There is no authentication in v1 — Context Engine is meant to run as an
internal service behind something that authenticates callers (a gateway, a
service mesh, or middleware in front of this API). The
`TenantValidationMiddleware` is the integration point: once a gateway
verifies a caller's identity, it should set `X-Tenant-Id` from that verified
identity, and the middleware will reject any request whose body disagrees.
