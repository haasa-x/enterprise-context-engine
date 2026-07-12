# Event schema guide

> **Looking for the authoritative spec?** The
> [protocol guide](protocol-guide.md) is the canonical reference for the
> universal event contract — field-by-field rules, enums, versioning, and
> producer conformance. This page is a friendlier, tutorial-style tour of the
> same schema; where the two ever disagree, the protocol guide wins.

Every event ingested by Context Engine — whether pushed by the native SDK or
translated by a connector — must conform to the universal event schema at
[`schemas/event/v1.0.0/event.schema.json`](../schemas/event/v1.0.0/event.schema.json),
a JSON Schema Draft 2020-12 document.

## Why one schema for every application

Jira, SAP SuccessFactors, Concur, and every other enterprise app describe
"what happened" differently. Context Engine doesn't try to understand each
app's native format at query time — connectors and the SDK translate once,
at ingestion, into this shared shape. Everything downstream (the graph
writer, the scorer, the MCP tool) only ever deals with one schema.

## Required fields

| Field | Type | Notes |
|---|---|---|
| `schemaVersion` | string | Always `"1.0.0"` for this schema version |
| `eventId` | UUID string | Globally unique; re-sending the same `eventId` for a tenant returns `409 Conflict` |
| `tenantId` | string | Must match `^[a-zA-Z0-9_-]+$` |
| `applicationId` | string | Source app class, e.g. `"jira"` |
| `applicationInstanceId` | string | A specific deployed instance (a tenant may run more than one) |
| `environment` | enum | `production` \| `sandbox` \| `staging` \| `test` |
| `eventTimestamp` | ISO 8601 string | When the action happened in the source system; rejected if more than 5 minutes in the future |
| `actor` | object | See below |
| `action` | object | See below |
| `object` | object | See below |
| `source` | object | See below |

### `actor`

- `nativeUserId` (required) — the user ID as the source app knows it
- `userIdType` (required) — `email` \| `sso_subject` \| `app_native_id` \| `employee_id`
- `canonicalUserId` (optional) — set once identity resolution links this
  user across applications; null until then
- `roles` (optional) — roles held *at the time of the event*, not current roles

### `action`

- `type` (required) — a specific action, e.g. `"approve_leave_request"`
- `category` (required) — a normalized verb: `create` \| `read` \| `update` \|
  `delete` \| `approve` \| `reject` \| `navigate` \| `search`
- `metadata` (optional) — free-form, connector-specific fields

### `object`

- `objectType` (required) — e.g. `"leave_request"`, `"issue"`, `"sprint"`
- `objectId` (required) — the identifier of the specific object instance
- `objectDetails` (optional) — free-form details about the object

### `source`

- `connector` (required) — e.g. `"jira-connector"`, `"native-sdk"`
- `connectorVersion` (required) — semver of the connector or SDK

## Optional top-level fields

- `ingestionTimestamp` — set by the platform on receipt; clients should not set this
- `onBehalfOf` — set when the actor performed the action on someone else's behalf
- `context.sessionId` / `context.correlationId` — groups and traces events
- `context.device` — `desktop` \| `mobile` \| `tablet`
- `context.geo.country` / `context.geo.region` — coarse location only

## Validation rules enforced beyond the JSON Schema

`src/context_engine/core/schema_validator.py` adds one rule the JSON Schema
itself can't express: `eventTimestamp` must not be more than 5 minutes in
the future (configurable via `CE_MAX_FUTURE_SECONDS`), to tolerate clock
skew without accepting garbage timestamps. All validation failures are
collected and returned together — a request with three bad fields gets one
`400` response listing all three, not just the first.

## Extending the schema

The schema is versioned (`schemas/event/v<major>.<minor>.<patch>/`). A
backward-compatible addition (a new optional field) can go into the current
version. A breaking change (removing a field, tightening a required field)
needs a new major version directory, with both versions supported by
`SchemaValidator` during the migration window.
