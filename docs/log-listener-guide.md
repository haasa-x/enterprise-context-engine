# Building a log listener (ingestion Path 3)

A **log listener** is the third ingestion path. Use it for a legacy or
third-party application that you cannot instrument with the SDK (Path 1) and
that offers no webhook or API to build a connector against (Path 2) — but that
*does* write an audit or activity log. The listener tails that log, parses each
new line, transforms it into the [universal event contract](protocol-guide.md),
and POSTs it to `POST /v1/events`.

The worked example ships in `samples/log-simulator/`:

- `samples/log-simulator/log_generator.py` — writes realistic audit log lines
  to a file, simulating a legacy enterprise app.
- `samples/log-simulator/log_listener.py` — watches that file, parses new
  lines, transforms them into universal events, and pushes them to the API.

## When to choose a log listener

| You have… | Use |
|---|---|
| Control of the app's source code | [SDK push (Path 1)](sdk-guide.md) |
| Webhooks, polling, or an export API | [Connector (Path 2)](connector-guide.md) |
| Only an audit/activity log on disk | **Log listener (Path 3)** |

Path 3 is the fallback for systems you can neither modify nor call — the log is
the only signal they emit. It is documented as a first-class path because a
large share of real enterprise software falls into exactly this category. See
[ADR 003](adr/003-three-ingestion-paths.md) for why all three paths exist.

## Anatomy of a log listener

A log listener has three responsibilities, and it is worth keeping them as
three separable pieces so each can be tested on its own:

1. **Tail** — follow the log file, yielding new lines as they are appended,
   and remembering how far it has read so a restart does not re-ingest or skip
   lines. In the sample this is a simple offset/seek loop; a production
   listener should persist the last-read offset.
2. **Parse** — turn one raw log line into structured fields. Real logs are
   messy: skip blank lines, headers, and lines that do not match the expected
   format rather than crashing on them.
3. **Transform** — map the parsed fields onto a valid universal event, then
   POST it. This mirrors a connector's transformer (a pure
   `parsed line -> event | None` function), and the same conformance rules
   apply.

## Parsing and transforming

Parsing is application-specific — split on the log's delimiter, match a regex,
or parse JSON lines. Whatever the format, the output of the transform step must
satisfy the [protocol guide](protocol-guide.md) in full. In particular:

- **`eventId`** — generate a fresh UUID per line (a log line rarely carries a
  usable unique id). This makes re-ingestion idempotent: if the listener
  restarts and replays a few lines, the ingestion API returns `409 Conflict`
  for the duplicates.
- **`eventTimestamp`** — parse the timestamp *out of the log line*, not the
  wall clock. The line records when the action actually happened; using
  `now()` would flatten every temporal pattern the profiler depends on. Emit
  it as ISO 8601. (Note the 5-minute future-timestamp rule from the protocol
  guide — historical log lines are always in the past, so this is only a
  concern for badly-clocked source systems.)
- **`actor.userIdType`** — prefer `email` when the log carries one, so
  identity resolution can link this user across applications.
- **`source.connector`** — name it after the listener (for example
  `"log-listener"`), with a `connectorVersion`.
- **Skip, don't crash** — a line you cannot map should be dropped (log a
  warning), not raised. One unparseable line must never stop the tail.

## Forwarding to the API

- POST each transformed event to `POST /v1/events` with the tenant's
  `X-Tenant-Id` header set (it must match the body's `tenantId`).
- Treat `409 Conflict` as success — the line was already ingested.
- Do not retry other `4xx` responses; a malformed event will not become valid
  by resending it. Retry `5xx` and transport errors with backoff.
- For a backfill of an existing log, batch lines through
  `POST /v1/events/batch` (up to 100 events per call) instead of one-at-a-time.

## Running the sample

Bring up the platform first (`docker compose up` — see
[architecture.md](architecture.md) and the repository README), then run the
generator and listener from `samples/log-simulator/` per that directory's
README. Watch events arrive with the [admin graph viewer](admin-ui-guide.md)'s
event feed, or by requesting a user's [profile](protocol-guide.md) once enough
lines have accumulated.
