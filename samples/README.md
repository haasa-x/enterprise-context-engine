# Context Engine — Sample Applications

These samples show the three ingestion paths in action and give you thick,
demo-ready data without waiting months for real activity to accumulate. Start
the engine first (`docker compose up` from the repo root), then pick a sample.

| Sample | Path | What it demonstrates |
| --- | --- | --- |
| [`data/`](./data) | Seed data | Generates ~6 months of realistic events (5 users, 3 apps) and bulk-loads them via `POST /v1/events/batch`. |
| [`task-tracker/`](./task-tracker) | Path 1 — SDK push | A FastAPI app that emits an event through the Python SDK on every task action. |
| [`log-simulator/`](./log-simulator) | Path 3 — log listener | A generator that writes legacy audit logs and a listener that tails, transforms, and POSTs them to `/v1/events`. |

## Seed data quick start

```bash
# Generate the JSON file (deterministic; default tenant "acme-corp")
python -m samples.data.seed_events generate

# Load it into a running engine in batches of 100
python -m samples.data.seed_events load --base-url http://localhost:8000 --tenant acme-corp
```

The seed generator produces recognizable temporal patterns so the graph shows
thick edges immediately:

- **Daily sprint checks** — developers open the Jira sprint board and update
  issues on weekday mornings (~9 AM).
- **Weekly leave approvals** — the HR manager approves leave requests in
  SuccessFactors on Monday mornings.
- **Monthly expense submissions** — employees submit Concur expense reports on
  the last workday of each month.
- **Cross-app sequence** — a project manager approves a leave request in
  SuccessFactors and, within ~10 minutes, updates the Jira capacity plan.

See each sample's own README for full details and options.
