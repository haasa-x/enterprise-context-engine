# ADR 001: Neo4j over alternatives

## Status

Accepted.

## Context

Context Engine needs to store a temporal knowledge graph: users, business
objects, and applications as nodes, and "who did what to what, and when" as
edges, queried in two very different ways:

1. **Write-heavy, simple ingestion** — one edge per event, upserting a
   handful of nodes, at a p99 target of 20ms.
2. **Read-heavy, relationship-shaped queries** — "what has this user done
   recently, across every application they're linked to" and "has this
   native user id been linked to a canonical cross-app identity" — both of
   which are graph traversals, not table joins, at a p99 target of 100ms.

The system also has to run fully self-contained (`docker compose up`, no
managed cloud dependency) and multi-tenant from day one.

## Options considered

**PostgreSQL with recursive CTEs.** Would satisfy the self-contained
requirement and is a technology most teams already operate. But modeling
"traverse PERFORMED edges across possibly-linked User nodes, filtered by
tenant and a time window" as recursive CTEs over adjacency tables is
exactly the kind of query relational databases make you fight for, and it
only gets worse once identity resolution adds a second hop (User ->
SAME_PERSON -> User -> PERFORMED). A graph database expresses this as a
two-line Cypher pattern.

**A dedicated temporal-graph library (e.g. Graphiti).** Graphiti is built
around LLM-driven entity extraction from unstructured text — exactly the
capability this project explicitly doesn't need, since every event field
is already structured and typed by the universal event schema. Pulling in
Graphiti (or a similar library) would mean paying its LLM-extraction
dependency weight for a feature we never call, and building the
non-LLM structured writer either way. Writing directly against Neo4j's
Python driver gets the temporal-edge modeling Graphiti also uses under the
hood, without the extraction pipeline.

**A document store or key-value store with manual adjacency lists (e.g.
DynamoDB, MongoDB).** Would require hand-rolling index maintenance for
every traversal pattern the prediction service needs, and cross-tenant
isolation would depend on every query author remembering to filter
correctly — there's no single enforcement point analogous to a query
helper that can refuse to run an unscoped query.

## Decision

Use Neo4j Community Edition directly via the official Python driver, with
no framework layered on top. Structured events map onto an explicit,
hand-written node/relationship model (`User`, `BusinessObject`,
`Application`, `PERFORMED`, `SAME_PERSON`, `BELONGS_TO`, `CONTAINS` — see
[architecture.md](../architecture.md)), and all Cypher is funneled through
one helper (`tenant_query` in `src/context_engine/core/graph.py`) that
enforces a `tenantId` filter on every query.

## Consequences

- Traversal-shaped queries (recent history, cross-app history via
  `SAME_PERSON`, occurrence counts for behavioral scoring) are simple,
  readable Cypher instead of recursive SQL.
- Neo4j Community Edition (not Enterprise) is sufficient for v1: relationship
  property uniqueness constraints and composite indexes, which this project
  relies on for `eventId` idempotency and tenant-scoped lookups, are
  available in Community.
- No LLM or embedding dependency enters the storage layer at all — the
  graph writer only ever reads fields the schema already declares.
- The tradeoff: Neo4j is one more piece of infrastructure to operate
  compared to "just use the Postgres we already have." `docker-compose.yml`
  absorbs that cost for local development and evaluation; production
  operators take on running (or paying for a managed) Neo4j instance.
