# Building a connector

A connector translates a third-party application's native event format
(webhooks, polling, exports — whatever the app offers) into the
[universal event schema](schema-guide.md) and forwards it to
`POST /v1/events`. `connectors/jira/` is the reference implementation.

## Anatomy of a connector

A connector is two things:

1. **A transformer** — a pure function, `payload -> event | None`, with no
   I/O. Given a native payload, it either returns a valid universal event
   dict or `None` if the payload doesn't map to anything actionable (an
   unrecognized webhook type, a field change nobody cares about, or a
   payload missing data the event needs). Keeping this pure makes it
   trivial to unit test against real sample payloads without a live
   connection to anything.
2. **A handler** — the thin, stateful layer around the transformer that
   receives the native payload (a webhook POST, a polled record, whatever)
   and forwards the transformed event to the ingestion API, handling
   idempotent retries and connectivity errors.

See `connectors/jira/transformer.py` and `connectors/jira/webhook_handler.py`.

## Writing the transformer

- **Return `None`, don't raise, for anything you can't map.** Real-world
  webhook payloads are inconsistent — fields go missing, event types you
  don't recognize show up, apps batch unrelated changes into one payload.
  A connector that raises on the first unfamiliar shape stops ingesting
  everything behind it; one that returns `None` just skips that one event.
- **One native event type can map to zero, one, or many action types.**
  Jira's `jira:issue_updated` webhook fires for *any* field change,
  including ones nobody wants tracked (Jira's internal backlog-order
  `"Rank"` field changes constantly). Inspect the payload's own diff/
  changelog to decide the actual `action.type`, and return `None` when
  nothing in it maps to something meaningful.
- **Prefer `email` as `userIdType` when the source payload has one.** Exact
  email matching is how identity resolution (`core/identity.py`) links a
  user across applications in v1 — an actor stamped with `app_native_id`
  when an email was available in the payload can never be linked.
- **Generate `eventId` yourself** (a fresh UUID per event) unless the
  source system already provides a genuinely unique ID you can reuse for
  idempotency.

## Writing the handler

- Forward to `POST /v1/events` with the tenant's `X-Tenant-Id` header set.
- Treat `409 Conflict` from the ingestion API as success, not an error — it
  means the event was already ingested (the source system retried the
  webhook, you're replaying a queue, etc.).
- Don't retry client errors (`4xx` other than `409`) — a malformed event
  isn't going to become valid on the next attempt without a code change.

## Testing a connector

Write the transformer tests against real sample payloads (capture them from
the actual application if you can) — see `tests/test_jira_connector.py` for
the shape: one test per native event type, one for "ignored" fields, one for
missing/partial data. The handler needs only a couple of tests using
`httpx.MockTransport` to verify forwarding, duplicate handling, and error
propagation — the interesting logic lives in the transformer.
