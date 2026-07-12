# context-engine-sdk

Python SDK for emitting user-activity events to a Context Engine instance.

```python
from context_engine_sdk import ContextEngineClient

client = ContextEngineClient(base_url="http://localhost:8000")

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

`eventId`, `eventTimestamp`, and `schemaVersion` are filled in automatically if
omitted. Required fields are validated locally before the request is sent.
Requests are retried up to 3 times with exponential backoff (1s, 2s, 4s) on
server errors or transport failures.
