"""Integration tests for event ingestion: POST /v1/events, /v1/events/batch, and health."""

from __future__ import annotations

import httpx
import pytest


async def test_healthz(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_ingest_event_returns_201(api_client, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    response = await api_client.post("/v1/events", json=event)
    assert response.status_code == 201
    assert response.json() == {"eventId": event["eventId"], "status": "accepted"}


async def test_ingest_duplicate_event_returns_409(api_client, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    first = await api_client.post("/v1/events", json=event)
    assert first.status_code == 201

    second = await api_client.post("/v1/events", json=event)
    assert second.status_code == 409
    body = second.json()
    assert body["error"] == "duplicate_event"
    assert "requestId" in body


async def test_ingest_event_missing_field_returns_400(api_client, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    del event["applicationId"]

    response = await api_client.post("/v1/events", json=event)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_error"
    assert "applicationId" in body["detail"]


async def test_ingest_event_tenant_header_mismatch_returns_403(api_client, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    response = await api_client.post(
        "/v1/events", json=event, headers={"X-Tenant-Id": "some-other-tenant"}
    )
    assert response.status_code == 403
    assert response.json()["error"] == "tenant_mismatch"


async def test_ingest_event_tenant_header_match_succeeds(api_client, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    response = await api_client.post("/v1/events", json=event, headers={"X-Tenant-Id": tenant_id})
    assert response.status_code == 201


async def test_batch_ingestion_mixed_results(api_client, tenant_id, make_event):
    good_events = [make_event(tenantId=tenant_id) for _ in range(9)]
    bad_event = make_event(tenantId=tenant_id)
    del bad_event["source"]

    response = await api_client.post(
        "/v1/events/batch", json={"events": [*good_events, bad_event]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["acceptedCount"] == 9
    assert body["rejectedCount"] == 1
    statuses = {r["status"] for r in body["results"]}
    assert statuses == {"accepted", "rejected"}


async def test_batch_ingestion_over_size_limit_rejected(api_client, tenant_id, make_event):
    events = [make_event(tenantId=tenant_id) for _ in range(101)]
    response = await api_client.post("/v1/events/batch", json={"events": events})
    assert response.status_code == 400
    assert response.json()["error"] == "batch_too_large"


async def test_batch_ingestion_over_failure_threshold_rejected(api_client, tenant_id, make_event):
    events = []
    for i in range(10):
        event = make_event(tenantId=tenant_id)
        if i < 3:
            del event["actor"]
        events.append(event)

    response = await api_client.post("/v1/events/batch", json={"events": events})
    assert response.status_code == 422
    assert response.json()["error"] == "batch_rejected"


async def test_batch_over_threshold_persists_nothing(
    api_client, graph_store, tenant_id, make_event
):
    user_id = "atomic-batch-user"
    events = []
    for i in range(10):
        event = make_event(
            tenantId=tenant_id,
            actor={"nativeUserId": user_id, "userIdType": "employee_id"},
        )
        if i < 3:  # 30% invalid -> whole batch must be rejected atomically
            del event["actor"]
        events.append(event)

    response = await api_client.post("/v1/events/batch", json={"events": events})

    assert response.status_code == 422
    history = await graph_store.get_user_history(tenant_id, user_id, days=30)
    assert history == [], "a rejected batch must not persist any of its valid events"


@pytest.mark.parametrize("path", ["/v1/events", "/v1/events/batch"])
async def test_malformed_json_body_returns_400(api_client, path):
    response = await api_client.post(
        path, content=b"not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
