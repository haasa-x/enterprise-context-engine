# Admin Graph Viewer

A self-contained admin UI for the Context Engine. It connects to the engine's
REST API and gives you, per user within a tenant:

- **User selector** — pick a user from the tenant's active users.
- **Behavioural profile** — the generated natural-language (NLQ) profile.
- **Activity graph** — user → application → business-object nodes. Edge
  thickness scales with how many times an action was performed, so recurring
  patterns literally thicken over time (Cytoscape.js).
- **Detected patterns** — cards for recurring actions and cross-app sequences,
  each with a confidence bar.
- **Activity timeline** — a per-day bar chart so clustering is obvious
  (Monday-morning leave approvals, month-end timesheets, empty weekends).
- **Event feed** — a refreshable list of the user's recent events, newest first.

## Stack

Plain HTML + CSS + vanilla JavaScript. **No build step, no npm, no bundler.**
The only third-party dependency is [Cytoscape.js](https://js.cytoscape.org/),
loaded from a CDN via a `<script>` tag. The Docker image just serves the three
static files with Python's built-in HTTP server, so it needs no toolchain.

## Run it (via docker compose)

From the repository root:

```bash
docker compose up --build
```

This starts three services: **neo4j**, the **api** (port 8000), and this
**admin** UI (port 3000).

Then open <http://localhost:3000> and, in the top bar:

- **API base URL** — `http://localhost:8000` (the default)
- **Tenant ID** — `acme-corp` (the default)

Click **Load users**, pick a user, and the graph, timeline, patterns, profile,
and event feed populate.

### Seed data first

A fresh engine has no activity, so the user list will be empty. Generate and
load six months of realistic patterned events before opening the UI:

```bash
# generate the JSON fixture (once)
python -m samples.data.seed_events generate

# load it into the running engine
python -m samples.data.seed_events load --base-url http://localhost:8000 --tenant acme-corp
```

Reload the UI and click **Load users** — you'll see thick edges immediately.

## Important: host-reachable URL, not the container URL

This is a **browser** app. The fetch calls run on your machine, not inside the
Docker network, so the API base must be a **host-reachable** URL
(`http://localhost:8000`).

Do **not** use `http://api:8000` here — that hostname only resolves *inside* the
Docker network (it is the value of the `API_URL` env var passed to the container
for reference), and your browser cannot resolve it. The default in the input box
is already the correct host URL.

## API contract

Every request sends the header `X-Tenant-Id: <tenant>`. Endpoints consumed:

| # | Method & path | Used for |
|---|---------------|----------|
| 1 | `GET /v1/admin/users` | user selector |
| 2 | `GET /v1/admin/users/{userId}/events?days=180` | graph, timeline, event feed |
| 3 | `GET /v1/users/{userId}/profile` | NLQ profile + pattern cards |

A `404 {"error": "insufficient_data"}` from endpoint 3 is handled gracefully
with a "Not enough activity yet" message rather than an error.

## Run it without Docker

Any static file server works, e.g.:

```bash
cd admin/graph-viewer
python -m http.server 3000
```

Then open <http://localhost:3000>. (Opening `index.html` directly via `file://`
also works, but serving over HTTP avoids browser quirks.)
