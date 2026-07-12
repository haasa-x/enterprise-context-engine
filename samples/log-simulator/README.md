# Log Simulator — Path 3 (log listener)

This sample demonstrates the **log listener** ingestion path. Many legacy
enterprise systems cannot push events and have no API to poll, but they *do*
write audit logs. A log listener tails those logs, parses each line, transforms
it into the Context Engine universal event schema, and POSTs it to the engine.

```
┌────────────────┐  writes   ┌───────────┐  tails/parses  ┌──────────────┐
│ log_generator  │ ────────► │ audit.log │ ─────────────► │ log_listener │
│ (legacy app)   │           └───────────┘                └──────┬───────┘
└────────────────┘                                                │ POST /v1/events
                                                                  ▼
                                                          Context Engine
```

## How a log listener works

1. **Follow the file.** The listener opens the log and (by default) seeks to the
   end, so only *new* lines are processed. Use `--from-start` to replay history.
2. **Parse each line.** The legacy format here is space-separated `key=value`
   pairs: `2026-01-05T09:03:00Z user=emp001 action=view_report object=report:Q1 app=legacy-erp`.
3. **Transform to the universal schema.** `to_event()` maps log fields onto the
   event contract — `user` → `actor.nativeUserId` (`userIdType: app_native_id`),
   the action verb prefix → `action.category` (e.g. `view_*` → `read`,
   `approve_*` → `approve`), and `object` (`type:id`) → `object.objectType` /
   `object.objectId`. A fresh `eventId` UUID makes ingestion idempotent.
4. **POST to the engine.** Each event is sent to `POST /v1/events` with an
   `X-Tenant-Id` header. `201` and `409` (duplicate) both count as success.

## Run it

Start the Context Engine first (`docker compose up` from the repo root).

In one terminal, generate a continuous stream of audit log lines:

```bash
python samples/log-simulator/log_generator.py --follow --interval 2
```

In another terminal, tail the log and forward events to the engine:

```bash
python samples/log-simulator/log_listener.py --base-url http://localhost:8000 --tenant acme-corp
```

You should see `forwarded emp003 approve_invoice invoice:2026-07` lines from the
listener as events flow into the engine.

### One-shot mode

To write a fixed number of lines and replay the whole file once:

```bash
python samples/log-simulator/log_generator.py --count 100
python samples/log-simulator/log_listener.py --from-start
```

## Options

| Script | Flag | Default | Purpose |
| --- | --- | --- | --- |
| `log_generator.py` | `--count` | `50` | Lines to write when not following. |
| `log_generator.py` | `--follow` | off | Append one line per `--interval`. |
| `log_generator.py` | `--interval` | `2.0` | Seconds between lines in follow mode. |
| `log_listener.py` | `--base-url` | `http://localhost:8000` | Engine base URL. |
| `log_listener.py` | `--tenant` | `acme-corp` | Tenant id + `X-Tenant-Id` header. |
| `log_listener.py` | `--from-start` | off | Replay existing lines before following. |

Both scripts default to `samples/log-simulator/audit.log`; override with `--path`.
