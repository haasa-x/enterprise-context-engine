import assert from "node:assert/strict";
import { test } from "node:test";

import { ContextEngineClient, EventValidationError, HttpError } from "../src/index.ts";

const BASE_EVENT = {
  tenantId: "acme-corp",
  applicationId: "my-app",
  applicationInstanceId: "my-app-prod",
  environment: "production",
  actor: { nativeUserId: "user@acme.com", userIdType: "email" },
  action: { type: "update_issue_status", category: "update" },
  object: { objectType: "issue", objectId: "PROJ-123" },
  source: { connector: "native-sdk", connectorVersion: "1.0.0" },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(
  fetchFn: typeof fetch,
  sleeps: number[] = [],
): ContextEngineClient {
  return new ContextEngineClient({
    baseUrl: "http://ingest",
    fetchFn,
    sleepFn: async (ms: number) => {
      sleeps.push(ms);
    },
  });
}

test("emit fills in defaults and succeeds", async () => {
  let capturedBody: Record<string, unknown> | undefined;
  const fetchFn = (async (_url: string, init?: RequestInit) => {
    capturedBody = JSON.parse(init!.body as string);
    return jsonResponse(201, { eventId: "x", status: "accepted" });
  }) as typeof fetch;

  const client = makeClient(fetchFn);
  const result = await client.emit({ ...BASE_EVENT });

  assert.deepEqual(result, { eventId: "x", status: "accepted" });
  assert.ok(capturedBody);
  assert.ok("eventId" in capturedBody!);
  assert.ok("eventTimestamp" in capturedBody!);
  assert.equal(capturedBody!.schemaVersion, "1.0.0");
});

test("emit preserves explicit event id", async () => {
  const fetchFn = (async () =>
    jsonResponse(201, { eventId: "explicit-id", status: "accepted" })) as typeof fetch;

  const client = makeClient(fetchFn);
  const result = await client.emit({ ...BASE_EVENT, eventId: "explicit-id" });
  assert.equal(result.eventId, "explicit-id");
});

test("emit rejects missing required field", async () => {
  const client = makeClient((async () => jsonResponse(201, {})) as typeof fetch);
  const event = { ...BASE_EVENT } as Record<string, unknown>;
  delete event.applicationId;

  await assert.rejects(() => client.emit(event), EventValidationError);
});

test("emit rejects missing nested field", async () => {
  const client = makeClient((async () => jsonResponse(201, {})) as typeof fetch);
  const event = { ...BASE_EVENT, actor: { nativeUserId: "user@acme.com" } };

  await assert.rejects(() => client.emit(event), EventValidationError);
});

test("emit treats 409 as success", async () => {
  const fetchFn = (async () => jsonResponse(409, { error: "duplicate_event" })) as typeof fetch;
  const client = makeClient(fetchFn);
  const result = await client.emit({ ...BASE_EVENT });
  assert.deepEqual(result, { error: "duplicate_event" });
});

test("emit retries on server error then succeeds", async () => {
  let attempts = 0;
  const fetchFn = (async () => {
    attempts += 1;
    if (attempts < 3) return jsonResponse(500, { error: "internal" });
    return jsonResponse(201, { eventId: "x", status: "accepted" });
  }) as typeof fetch;

  const sleeps: number[] = [];
  const client = makeClient(fetchFn, sleeps);
  const result = await client.emit({ ...BASE_EVENT });

  assert.equal(result.status, "accepted");
  assert.equal(attempts, 3);
  assert.deepEqual(sleeps, [1000, 2000]);
});

test("emit gives up after max retries", async () => {
  const fetchFn = (async () => jsonResponse(500, { error: "internal" })) as typeof fetch;
  const sleeps: number[] = [];
  const client = makeClient(fetchFn, sleeps);

  await assert.rejects(() => client.emit({ ...BASE_EVENT }), HttpError);
  assert.deepEqual(sleeps, [1000, 2000, 4000]);
});

test("emit does not retry on client error", async () => {
  let attempts = 0;
  const fetchFn = (async () => {
    attempts += 1;
    return jsonResponse(400, { error: "validation_error" });
  }) as typeof fetch;

  const sleeps: number[] = [];
  const client = makeClient(fetchFn, sleeps);

  await assert.rejects(() => client.emit({ ...BASE_EVENT }), HttpError);
  assert.equal(attempts, 1);
  assert.deepEqual(sleeps, []);
});
