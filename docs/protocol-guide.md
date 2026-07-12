# Protocol guide — the universal event contract

This is the **canonical protocol specification** for Context Engine. Every
connector (Path 2), log listener (Path 3), and SDK (Path 1) must produce
events that conform to this contract, byte-for-byte, before they reach
`POST /v1/events`. The contract is expressed as a JSON Schema (Draft 2020-12)
at [`../schemas/event/v1.0.0/event.schema.json`](../schemas/event/v1.0.0/event.schema.json)
and is enforced at ingestion by `src/context_engine/core/schema_validator.py`.

If you want a gentler, tutorial-style tour of the same fields, see the
[event schema guide](schema-guide.md); this document is the authoritative
reference and wins on any point of disagreement.

> **Why a protocol, not a per-app format.** Jira, SuccessFactors, Concur, and
> every other enterprise app describe "what happened" differently. Context
> Engine translates once — at the edge, in a connector or SDK — into this one
> shape. Everything downstream (the graph writer, the intent scorer, the
> profiler, the MCP server) only ever sees this schema. The protocol is the
> single integration boundary of the whole system.

## Versioning

- **`$id`** — `https://context-engine.dev/schemas/event/v1.0.0/event.schema.json`.
  This is the stable, resolvable identifier of the contract. Tooling that
  caches or references the schema should key off `$id`.
- **`$schema`** — `https://json-schema.org/draft/2020-12/schema`. The contract
  is a Draft 2020-12 document and must be validated with a Draft 2020-12
  validator.
- **Semver in the path.** The schema lives under
  `schemas/event/v<major>.<minor>.<patch>/`. The `schemaVersion` field in every
  event (`const: "1.0.0"`) must equal the version in the path it validates
  against.
  - A **backward-compatible** change (adding a new *optional* field) may ship
    inside the current version directory.
  - A **breaking** change (removing a field, making an optional field required,
    tightening an enum) requires a new **major** version directory. During the
    migration window, `SchemaValidator` can be configured to accept more than
    one version so producers can upgrade independently of consumers.

## Required top-level fields

Every event **must** include all eleven of these. `additionalProperties` is
`false` at the top level — any field not defined here is rejected.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | string | Must equal `"1.0.0"` (JSON Schema `const`) |
| `eventId` | string | `format: uuid` — a UUID. Used for idempotent ingestion; re-sending the same `eventId` returns `409 Conflict` |
| `tenantId` | string | Must match `^[a-zA-Z0-9_-]+$`, `minLength: 1`. The data-isolation key |
| `applicationId` | string | `minLength: 1`. Source app class, e.g. `"jira"`, `"successfactors"`, `"concur"` |
| `applicationInstanceId` | string | `minLength: 1`. A specific deployed instance (a tenant may run several of the same app) |
| `environment` | enum | One of `production`, `sandbox`, `staging`, `test` |
| `eventTimestamp` | string | `format: date-time` (ISO 8601). When the action happened in the source system. Rejected if too far in the future — see [Validation rules](#validation-rules-beyond-the-json-schema) |
| `actor` | object | See [`actor`](#actor) |
| `action` | object | See [`action`](#action) |
| `object` | object | See [`object`](#object) |
| `source` | object | See [`source`](#source) |

### `actor`

Who performed the action. `additionalProperties: false`.

| Field | Required | Type | Rule |
|---|---|---|---|
| `nativeUserId` | yes | string | `minLength: 1`. The user id as the source app knows it |
| `userIdType` | yes | enum | `email`, `sso_subject`, `app_native_id`, or `employee_id` |
| `canonicalUserId` | no | string \| null | Cross-app identity; `null` until identity resolution runs |
| `roles` | no | array of string | Roles held **at the time of the event**, not current roles |

> **Conformance tip.** Prefer `userIdType: "email"` when the source payload has
> an email. In v1, identity resolution (`src/context_engine/core/identity.py`)
> links a user across applications by exact email match; an actor stamped with
> `app_native_id` when an email was available can never be cross-app linked.

### `action`

What was done. `additionalProperties: false`.

| Field | Required | Type | Rule |
|---|---|---|---|
| `type` | yes | string | `minLength: 1`. A specific action, e.g. `"approve_leave_request"`, `"update_issue_status"` |
| `category` | yes | enum | One of `create`, `read`, `update`, `delete`, `approve`, `reject`, `navigate`, `search` |
| `metadata` | no | object | Free-form, connector-specific fields. Persisted as a JSON string on the `PERFORMED` edge and mined by the profiler for parameter defaults |

`action.type` is the free-text discriminator the system keys most behaviour
off — the intent scorer groups history by `action.type`, and the keyword
table maps trigger words to `action.type` values. Keep it stable and specific
per connector.

### `object`

What the action was performed on. `additionalProperties: false`.

| Field | Required | Type | Rule |
|---|---|---|---|
| `objectType` | yes | string | `minLength: 1`, e.g. `"leave_request"`, `"issue"`, `"sprint"` |
| `objectId` | yes | string | `minLength: 1`. Identifier of the specific instance |
| `objectDetails` | no | object | Free-form details about the object |

### `source`

Which producer emitted the event. `additionalProperties: false`.

| Field | Required | Type | Rule |
|---|---|---|---|
| `connector` | yes | string | `minLength: 1`, e.g. `"jira-connector"`, `"native-sdk"` |
| `connectorVersion` | yes | string | `minLength: 1`. Semver of the connector or SDK |

## Optional top-level fields

| Field | Type | Rule |
|---|---|---|
| `ingestionTimestamp` | ISO 8601 string | **Set by the platform on receipt.** Producers must not set it; the ingestion route stamps it |
| `onBehalfOf` | object | Set when the actor acts on another user's behalf. Requires `nativeUserId` + `userIdType` (same enum as `actor`); `additionalProperties: false` |
| `context.sessionId` | string | Groups events in the same user session |
| `context.correlationId` | string | Trace id linking events across systems |
| `context.device` | enum | `desktop`, `mobile`, or `tablet` |
| `context.geo.country` | string | Coarse location only |
| `context.geo.region` | string | State/province level |

`context` and `context.geo` are both `additionalProperties: false`.

## Validation rules beyond the JSON Schema

`SchemaValidator` (`src/context_engine/core/schema_validator.py`) applies the
JSON Schema plus rules the schema itself cannot express:

1. **UUID `eventId`.** Enforced by `format: uuid` in the schema.
2. **`tenantId` pattern.** Enforced by `pattern: ^[a-zA-Z0-9_-]+$`.
3. **Future-timestamp rejection.** `eventTimestamp` must not be more than
   `max_future_seconds` (default **300s / 5 minutes**, configurable via
   `CE_MAX_FUTURE_SECONDS`) ahead of the server's clock. This tolerates clock
   skew between producer and platform without accepting garbage timestamps.
   Timestamps in the past are always accepted.
4. **All failures reported together.** Validation does not stop at the first
   error. A request with three bad fields gets one `400` response listing all
   three, via `SchemaValidationError` (see
   `src/context_engine/core/exceptions.py`).

Idempotency (`eventId` uniqueness) is enforced one layer down, at write time,
by a Neo4j uniqueness constraint on the `PERFORMED` edge — a duplicate
`eventId` surfaces as `409 Conflict`, not a validation error.

## How producers must conform

Any producer — SDK, connector, or log listener — is conformant when it:

1. Emits every required field with a value that passes the schema **and** the
   extra validation rules above.
2. Sets `schemaVersion` to the version it validated against.
3. Generates a fresh UUID `eventId` per logical event (or reuses a genuinely
   unique upstream id) so retries are idempotent.
4. Leaves `ingestionTimestamp` unset — the platform owns it.
5. Treats `409 Conflict` from `POST /v1/events` as success (the event was
   already ingested), and does **not** retry `4xx` responses other than `409`.

The three producer paths document their specifics:

- **Path 1 — SDK push:** [sdk-guide.md](sdk-guide.md)
- **Path 2 — connector pull/translate:** [connector-guide.md](connector-guide.md)
- **Path 3 — log listener:** [log-listener-guide.md](log-listener-guide.md)

For where these events land and how they are queried, see
[architecture.md](architecture.md). For why the ingestion path carries no LLM
or ML dependency, see [ADR 002](adr/002-no-llm-in-ingestion.md).
