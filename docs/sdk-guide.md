# SDK guide

The native SDKs (`sdk/python/`, `sdk/node/`) let an application push events
directly to Context Engine without going through a connector — use this
path when you control the application's code and can add a few lines at the
point where a user action happens, rather than waiting on the app's own
webhook/export support.

Both SDKs are deliberately minimal: one runtime dependency each (`httpx` for
Python, the native `fetch` API for Node), the same behavior, and no
framework lock-in.

## Common behavior

- **Fills in `eventId`, `eventTimestamp`, and `schemaVersion`** if you don't
  supply them, so callers only need to describe the actor/action/object.
- **Validates locally before sending** — a missing required field raises
  immediately (`EventValidationError`) instead of round-tripping to the
  server to find out.
- **Retries on failure**, up to 3 times, with exponential backoff (1s, 2s,
  4s). Retries only server errors (`5xx`) and transport failures — a
  `4xx` response means the request itself is wrong and won't succeed by
  resending it.
- **Treats `409 Conflict` as success** — it means the event was already
  ingested (you emitted it before, or something upstream retried).

## Python

```python
from context_engine_sdk import ContextEngineClient

with ContextEngineClient(base_url="http://localhost:8000") as client:
    client.emit({
        "tenantId": "acme-corp",
        "applicationId": "my-app",
        "applicationInstanceId": "my-app-prod",
        "environment": "production",
        "actor": {"nativeUserId": "user@acme.com", "userIdType": "email"},
        "action": {"type": "update_issue_status", "category": "update"},
        "object": {"objectType": "issue", "objectId": "PROJ-123"},
        "source": {"connector": "native-sdk", "connectorVersion": "1.0.0"},
    })
```

Install from source: `pip install -e sdk/python`.

## Node

```ts
import { ContextEngineClient } from "context-engine-sdk";

const client = new ContextEngineClient({ baseUrl: "http://localhost:8000" });

await client.emit({
  tenantId: "acme-corp",
  applicationId: "my-app",
  applicationInstanceId: "my-app-prod",
  environment: "production",
  actor: { nativeUserId: "user@acme.com", userIdType: "email" },
  action: { type: "update_issue_status", category: "update" },
  object: { objectType: "issue", objectId: "PROJ-123" },
  source: { connector: "native-sdk", connectorVersion: "1.0.0" },
});
```

Build from source: `cd sdk/node && npm install && npm run build`.

## Choosing between the SDK and a connector

Use the SDK when you own the application's code — it's the lowest-latency,
lowest-overhead path. Use a connector (see the
[connector guide](connector-guide.md)) when you don't own the code and the
application only exposes events via webhooks, polling, or exports.
