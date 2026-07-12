# Task Tracker — Path 1 (SDK push)

A minimal FastAPI task tracker that emits an event to the Context Engine for
every action, using the **Python SDK** (`context_engine_sdk.ContextEngineClient`).
This is the SDK-push ingestion path: the application itself is instrumented and
pushes events as they happen.

```
HTTP request ──► task-tracker endpoint ──► ContextEngineClient.emit() ──► POST /v1/events ──► Context Engine
```

## Endpoints

| Method & path | Action type | Category | Object |
| --- | --- | --- | --- |
| `POST /tasks` | `create_task` | `create` | `task` |
| `PATCH /tasks/{id}/status` | `update_task_status` | `update` | `task` |
| `POST /tasks/{id}/assign` | `assign_task` | `update` | `task` |

Tasks are stored in memory only, so they reset when the app restarts. The point
of the sample is the event stream, not durable storage. Events are emitted with
`applicationId: "task-tracker"`.

## Run it alongside the engine

1. Start the Context Engine (`docker compose up` from the repo root). It listens
   on `http://localhost:8000`.
2. Point the sample at the engine and start it on a different port:

   ```bash
   export TASK_TRACKER_ENGINE_URL=http://localhost:8000
   export TASK_TRACKER_TENANT_ID=acme-corp
   uvicorn samples.task-tracker.app:app --port 8100
   ```

   > The SDK endpoint and tenant are read from `TASK_TRACKER_ENGINE_URL` and
   > `TASK_TRACKER_TENANT_ID` (defaults: `http://localhost:8000`, `acme-corp`).

3. Exercise the endpoints and watch events flow into the engine:

   ```bash
   # Create a task
   curl -X POST http://localhost:8100/tasks \
     -H 'Content-Type: application/json' \
     -d '{"title": "Ship the demo", "creator_id": "erin.wong@acme-corp.example"}'
   # => {"taskId":"TASK-1","status":"open"}

   # Update its status
   curl -X PATCH http://localhost:8100/tasks/TASK-1/status \
     -H 'Content-Type: application/json' \
     -d '{"status": "in_progress", "actor_id": "erin.wong@acme-corp.example"}'

   # Assign it
   curl -X POST http://localhost:8100/tasks/TASK-1/assign \
     -H 'Content-Type: application/json' \
     -d '{"assignee_id": "carol.singh@acme-corp.example", "actor_id": "erin.wong@acme-corp.example"}'
   ```

4. Query the engine to confirm the events landed — for example fetch the user
   profile once enough events exist:

   ```bash
   curl http://localhost:8000/v1/users/erin.wong@acme-corp.example/profile \
     -H 'X-Tenant-Id: acme-corp'
   ```

If the engine is unreachable the SDK raises after retrying, so start the engine
before hitting the task-tracker endpoints.
