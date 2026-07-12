# Admin UI guide — the graph viewer

The **graph viewer** (`admin/graph-viewer/`) is a browser-based inspection tool
for a single tenant's behavioural graph. It is not part of the ingestion or
prediction path — it is a read-only lens over the same data the
[API](protocol-guide.md) exposes, meant for debugging connector/SDK
integrations and for *seeing* the patterns the profiler describes in prose.

It runs as its own Docker service on **port 3000** and talks to the Context
Engine API over HTTP.

## What it shows

The viewer is scoped to one tenant and one user at a time, and presents six
panels:

| Panel | What it shows |
|---|---|
| **User selector** | A dropdown / search box to pick a user within the tenant. Everything else on the page reacts to this selection. |
| **Graph view** | The selected user's nodes and edges — `User`, `BusinessObject`, `Application`, and the `PERFORMED` edges between them. **Edge thickness encodes pattern frequency:** an edge traversed many times (a repeated action) is drawn thicker than a one-off. This is the "patterns thicken over time" idea made visible. |
| **Timeline view** | A horizontal timeline showing *when* actions cluster — Monday-morning bursts of leave approvals, last-Friday spikes of timesheet submissions, empty weekends. It surfaces the temporal structure the profiler's pattern detector reads. |
| **Pattern list** | Cards for each detected pattern with its confidence, e.g. "Daily sprint check (94%)", "Monthly timesheet (91%)", "Cross-app: leave approval → calendar check (78%)". These correspond to the `ActionPattern` and `SequencePattern` output of `src/context_engine/profiler/pattern_detector.py`. |
| **NLQ profile** | The generated natural-language behavioural profile for the selected user — the same text returned by `GET /v1/users/{userId}/profile` and produced by the [profile generator](adr/004-template-vs-llm-profiler.md). |
| **Event feed** | A refreshable list of recent events for the user, for debugging that a connector or SDK is actually delivering events in the expected shape. |

The graph view uses a client-side graph-visualisation library (vis.js,
d3-force, or cytoscape.js) to lay out and render nodes and edges; thickness is
driven by the per-edge traversal count.

## How it gets its data

The viewer is a pure API client. It reads from the same public endpoints any
consumer uses:

- `GET /v1/users/{userId}/profile` (with the `X-Tenant-Id` header) for the NLQ
  profile, the dominant per-application `ActionPattern`s, the cross-app
  `SequencePattern`s, and the active objects that populate the pattern list and
  parts of the graph.
- The event and history data behind the graph, timeline, and event-feed panels.

Because it only reads through the API, the viewer is subject to the same
tenant scoping as everything else — it can never display data outside the
tenant whose `X-Tenant-Id` it sends.

## Running it

The graph viewer is a separate service in
[`../docker-compose.yml`](../docker-compose.yml). Bringing up the stack starts
it alongside Neo4j and the API:

```bash
docker compose up
```

Then open <http://localhost:3000>.

The service is configured with one environment variable that points it at the
API:

| Variable | Default (compose) | Purpose |
|---|---|---|
| `API_URL` | `http://api:8000` | Base URL of the Context Engine API the viewer queries |

Inside the compose network the API is reachable at `http://api:8000`; the same
API is published on the host at `http://localhost:8000`. To point the viewer at
an API running elsewhere, override `API_URL`.

## Seeing patterns immediately

A brand-new graph is thin — every edge has been traversed once. To see thick
edges, dense timeline clusters, and high-confidence pattern cards right after
setup, load the seed dataset (`samples/data/seed_events.py`), which generates
several months of realistic activity for a handful of users across multiple
applications and loads it via `POST /v1/events/batch`. Then run the profiler
(`python -m context_engine.profiler.scheduler <tenant-id>`) so the NLQ profile
panel has text to show, and select a seeded user in the viewer.
