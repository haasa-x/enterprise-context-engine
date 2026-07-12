/** Node SDK for emitting user-activity events to a Context Engine instance. */

const DEFAULT_TIMEOUT_MS = 5000;
const DEFAULT_MAX_RETRIES = 3;
const BACKOFF_MS = [1000, 2000, 4000];

const REQUIRED_TOP_LEVEL_FIELDS = [
  "tenantId",
  "applicationId",
  "applicationInstanceId",
  "environment",
  "actor",
  "action",
  "object",
  "source",
];
const REQUIRED_ACTOR_FIELDS = ["nativeUserId", "userIdType"];
const REQUIRED_ACTION_FIELDS = ["type", "category"];
const REQUIRED_OBJECT_FIELDS = ["objectType", "objectId"];
const REQUIRED_SOURCE_FIELDS = ["connector", "connectorVersion"];

export type EventPayload = Record<string, unknown>;
export type EmitResult = Record<string, unknown>;

/** Raised when an event is missing required fields before it is sent. */
export class EventValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EventValidationError";
  }
}

/** Raised when the ingestion API returns a non-retryable HTTP error. */
export class HttpError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(`HTTP ${status}: ${message}`);
    this.name = "HttpError";
    this.status = status;
  }
}

export interface ContextEngineClientOptions {
  baseUrl: string;
  timeoutMs?: number;
  maxRetries?: number;
  fetchFn?: typeof fetch;
  sleepFn?: (ms: number) => Promise<void>;
}

/** A minimal client for emitting events to a Context Engine instance. */
export class ContextEngineClient {
  private readonly baseUrl: string;
  private readonly maxRetries: number;
  private readonly timeoutMs: number;
  private readonly fetchFn: typeof fetch;
  private readonly sleepFn: (ms: number) => Promise<void>;

  constructor(options: ContextEngineClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchFn = options.fetchFn ?? fetch;
    this.sleepFn =
      options.sleepFn ?? ((ms: number) => new Promise((resolve) => setTimeout(resolve, ms)));
  }

  /**
   * Fill in defaults, validate, and send a single event.
   *
   * Returns the parsed JSON response body. Throws EventValidationError if the
   * event is missing required fields, or HttpError if the request ultimately
   * fails after retries.
   */
  async emit(event: EventPayload): Promise<EmitResult> {
    const prepared = prepareEvent(event);
    validateEvent(prepared);
    return this.sendWithRetry(prepared);
  }

  private async sendWithRetry(event: EventPayload): Promise<EmitResult> {
    const totalAttempts = this.maxRetries + 1;
    let lastError: unknown;

    for (let attempt = 0; attempt < totalAttempts; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

      try {
        const response = await this.fetchFn(`${this.baseUrl}/v1/events`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-Id": String(event.tenantId),
          },
          body: JSON.stringify(event),
          signal: controller.signal,
        });

        if (response.status === 409) {
          return (await response.json()) as EmitResult;
        }
        if (response.ok) {
          return (await response.json()) as EmitResult;
        }

        const error = new HttpError(response.status, await safeText(response));
        if (response.status < 500) {
          throw error;
        }
        lastError = error;
      } catch (err) {
        if (err instanceof HttpError && err.status < 500) {
          throw err;
        }
        lastError = err;
      } finally {
        clearTimeout(timeout);
      }

      if (attempt < totalAttempts - 1) {
        await this.sleepFn(BACKOFF_MS[attempt]);
      }
    }

    throw lastError;
  }
}

async function safeText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

function prepareEvent(event: EventPayload): EventPayload {
  const prepared: EventPayload = { ...event };
  if (!("schemaVersion" in prepared)) prepared.schemaVersion = "1.0.0";
  if (!("eventId" in prepared)) prepared.eventId = crypto.randomUUID();
  if (!("eventTimestamp" in prepared)) prepared.eventTimestamp = new Date().toISOString();
  return prepared;
}

function validateEvent(event: EventPayload): void {
  const errors: string[] = [];
  for (const field of REQUIRED_TOP_LEVEL_FIELDS) {
    if (!(field in event)) errors.push(`missing required field: ${field}`);
  }

  validateNested(event, "actor", REQUIRED_ACTOR_FIELDS, errors);
  validateNested(event, "action", REQUIRED_ACTION_FIELDS, errors);
  validateNested(event, "object", REQUIRED_OBJECT_FIELDS, errors);
  validateNested(event, "source", REQUIRED_SOURCE_FIELDS, errors);

  if (errors.length > 0) {
    throw new EventValidationError(errors.join("; "));
  }
}

function validateNested(
  event: EventPayload,
  key: string,
  requiredFields: string[],
  errors: string[],
): void {
  const value = event[key];
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    errors.push(`missing required field: ${key}`);
    return;
  }
  const record = value as Record<string, unknown>;
  for (const field of requiredFields) {
    if (!(field in record)) errors.push(`missing required field: ${key}.${field}`);
  }
}
