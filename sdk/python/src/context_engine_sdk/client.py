"""Client for emitting user-activity events to a Context Engine instance."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_RETRIES = 3
BACKOFF_SECONDS = (1.0, 2.0, 4.0)

_REQUIRED_ACTOR_FIELDS = ("nativeUserId", "userIdType")
_REQUIRED_ACTION_FIELDS = ("type", "category")
_REQUIRED_OBJECT_FIELDS = ("objectType", "objectId")
_REQUIRED_SOURCE_FIELDS = ("connector", "connectorVersion")
_REQUIRED_TOP_LEVEL_FIELDS = (
    "tenantId",
    "applicationId",
    "applicationInstanceId",
    "environment",
    "actor",
    "action",
    "object",
    "source",
)


class EventValidationError(ValueError):
    """Raised when an event is missing required fields before it is sent."""


class ContextEngineClient:
    """A minimal client for emitting events to a Context Engine instance."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        """Configure the target instance, retry budget, and (for tests) sleep function."""
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None
        self._sleep = sleep_fn

    def emit(self, event: dict[str, Any]) -> dict[str, Any]:
        """Fill in defaults, validate, and send a single event.

        Returns the parsed JSON response body. Raises EventValidationError if
        the event is missing required fields, or httpx.HTTPError if the
        request ultimately fails after retries.
        """
        prepared = _prepare_event(event)
        _validate_event(prepared)
        return self._send_with_retry(prepared)

    def close(self) -> None:
        """Close the underlying HTTP client, if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ContextEngineClient:
        """Support use as a context manager."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the client on context manager exit."""
        self.close()

    def _send_with_retry(self, event: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        total_attempts = self._max_retries + 1

        for attempt in range(total_attempts):
            try:
                response = self._client.post(
                    f"{self._base_url}/v1/events",
                    json=event,
                    headers={"X-Tenant-Id": event["tenantId"]},
                )
                if response.status_code == 409:
                    return dict(response.json())
                response.raise_for_status()
                return dict(response.json())
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise
                last_error = exc
            except httpx.TransportError as exc:
                last_error = exc

            if attempt < total_attempts - 1:
                self._sleep(BACKOFF_SECONDS[attempt])

        assert last_error is not None
        raise last_error


def _prepare_event(event: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(event)
    prepared.setdefault("schemaVersion", "1.0.0")
    prepared.setdefault("eventId", str(uuid.uuid4()))
    prepared.setdefault("eventTimestamp", datetime.now(timezone.utc).isoformat())
    return prepared


def _validate_event(event: dict[str, Any]) -> None:
    errors: list[str] = []
    for field in _REQUIRED_TOP_LEVEL_FIELDS:
        if field not in event:
            errors.append(f"missing required field: {field}")

    _validate_nested(event, "actor", _REQUIRED_ACTOR_FIELDS, errors)
    _validate_nested(event, "action", _REQUIRED_ACTION_FIELDS, errors)
    _validate_nested(event, "object", _REQUIRED_OBJECT_FIELDS, errors)
    _validate_nested(event, "source", _REQUIRED_SOURCE_FIELDS, errors)

    if errors:
        raise EventValidationError("; ".join(errors))


def _validate_nested(
    event: dict[str, Any], key: str, required_fields: tuple[str, ...], errors: list[str]
) -> None:
    value = event.get(key)
    if not isinstance(value, dict):
        errors.append(f"missing required field: {key}")
        return
    for field in required_fields:
        if field not in value:
            errors.append(f"missing required field: {key}.{field}")
