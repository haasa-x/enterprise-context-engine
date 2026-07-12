"""Tests for context_engine_sdk.client.ContextEngineClient."""

from __future__ import annotations

import httpx
import pytest
from context_engine_sdk import ContextEngineClient, EventValidationError

BASE_EVENT = {
    "tenantId": "acme-corp",
    "applicationId": "my-app",
    "applicationInstanceId": "my-app-prod",
    "environment": "production",
    "actor": {"nativeUserId": "user@acme.com", "userIdType": "email"},
    "action": {"type": "update_issue_status", "category": "update"},
    "object": {"objectType": "issue", "objectId": "PROJ-123"},
    "source": {"connector": "native-sdk", "connectorVersion": "1.0.0"},
}


def _client_with_responder(responder, sleeps=None):
    transport = httpx.MockTransport(responder)
    http_client = httpx.Client(transport=transport, base_url="http://ingest")
    sleeps = sleeps if sleeps is not None else []
    return ContextEngineClient(
        "http://ingest", http_client=http_client, sleep_fn=sleeps.append
    )


def test_emit_fills_in_defaults_and_succeeds():
    captured = {}

    def responder(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"eventId": "x", "status": "accepted"})

    client = _client_with_responder(responder)
    result = client.emit(dict(BASE_EVENT))

    assert result == {"eventId": "x", "status": "accepted"}
    assert "eventId" in captured["body"]
    assert "eventTimestamp" in captured["body"]
    assert captured["body"]["schemaVersion"] == "1.0.0"


def test_emit_preserves_explicit_event_id():
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"eventId": "explicit-id", "status": "accepted"})

    client = _client_with_responder(responder)
    event = dict(BASE_EVENT)
    event["eventId"] = "explicit-id"
    result = client.emit(event)
    assert result["eventId"] == "explicit-id"


def test_emit_rejects_missing_required_field():
    client = _client_with_responder(lambda request: httpx.Response(201, json={}))
    event = dict(BASE_EVENT)
    del event["applicationId"]

    with pytest.raises(EventValidationError, match="applicationId"):
        client.emit(event)


def test_emit_rejects_missing_nested_field():
    client = _client_with_responder(lambda request: httpx.Response(201, json={}))
    event = dict(BASE_EVENT)
    event["actor"] = {"nativeUserId": "user@acme.com"}

    with pytest.raises(EventValidationError, match="actor.userIdType"):
        client.emit(event)


def test_emit_treats_409_as_success():
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "duplicate_event"})

    client = _client_with_responder(responder)
    result = client.emit(dict(BASE_EVENT))
    assert result == {"error": "duplicate_event"}


def test_emit_retries_on_server_error_then_succeeds():
    attempts = {"count": 0}

    def responder(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(500, json={"error": "internal"})
        return httpx.Response(201, json={"eventId": "x", "status": "accepted"})

    sleeps: list[float] = []
    client = _client_with_responder(responder, sleeps=sleeps)
    result = client.emit(dict(BASE_EVENT))

    assert result["status"] == "accepted"
    assert attempts["count"] == 3
    assert sleeps == [1.0, 2.0]


def test_emit_gives_up_after_max_retries():
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    sleeps: list[float] = []
    client = _client_with_responder(responder, sleeps=sleeps)

    with pytest.raises(httpx.HTTPStatusError):
        client.emit(dict(BASE_EVENT))

    assert sleeps == [1.0, 2.0, 4.0]


def test_emit_does_not_retry_on_client_error():
    attempts = {"count": 0}

    def responder(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, json={"error": "validation_error"})

    sleeps: list[float] = []
    client = _client_with_responder(responder, sleeps=sleeps)

    with pytest.raises(httpx.HTTPStatusError):
        client.emit(dict(BASE_EVENT))

    assert attempts["count"] == 1
    assert sleeps == []


def test_context_manager_closes_owned_client():
    with ContextEngineClient("http://ingest") as client:
        assert client._owns_client is True
    assert client._client.is_closed


def test_context_manager_does_not_close_injected_client():
    transport = httpx.MockTransport(lambda request: httpx.Response(201, json={}))
    injected = httpx.Client(transport=transport, base_url="http://ingest")
    with ContextEngineClient("http://ingest", http_client=injected):
        pass
    assert injected.is_closed is False
    injected.close()
