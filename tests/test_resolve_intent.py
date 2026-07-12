"""Integration tests for POST /v1/resolve-intent."""

from __future__ import annotations

import httpx


async def test_resolve_intent_with_no_history_returns_empty_predictions(
    api_client: httpx.AsyncClient, tenant_id
):
    response = await api_client.post(
        "/v1/resolve-intent",
        json={
            "tenantId": tenant_id,
            "userId": "nobody",
            "userIdType": "employee_id",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["predictions"] == []
    assert body["userId"] == "nobody"


async def test_resolve_intent_boosts_matching_keyword(api_client, tenant_id, make_event):
    user_id = "hr_manager_intent_1"
    event = make_event(
        tenantId=tenant_id,
        actor={"nativeUserId": user_id, "userIdType": "employee_id"},
        action={"type": "view_sprint_board", "category": "read"},
        object={"objectType": "sprint", "objectId": "SPRINT-1"},
    )
    ingest = await api_client.post("/v1/events", json=event)
    assert ingest.status_code == 201

    response = await api_client.post(
        "/v1/resolve-intent",
        json={
            "tenantId": tenant_id,
            "userId": user_id,
            "userIdType": "employee_id",
            "trigger": {"source": "email", "text": "Sprint closes tomorrow"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["predictions"]) == 1
    prediction = body["predictions"][0]
    assert prediction["actionType"] == "view_sprint_board"
    assert prediction["applicationId"] == "jira"
    assert prediction["objectType"] == "sprint"
    assert any(s["type"] == "keyword_match" for s in prediction["signals"])
    assert prediction["confidence"] > 0.7


async def test_resolve_intent_without_trigger_uses_history_only(api_client, tenant_id, make_event):
    user_id = "hr_manager_intent_2"
    event = make_event(
        tenantId=tenant_id,
        actor={"nativeUserId": user_id, "userIdType": "employee_id"},
        action={"type": "approve_leave_request", "category": "approve"},
        object={"objectType": "leave_request", "objectId": "LR-9"},
    )
    await api_client.post("/v1/events", json=event)

    response = await api_client.post(
        "/v1/resolve-intent",
        json={"tenantId": tenant_id, "userId": user_id, "userIdType": "employee_id"},
    )
    assert response.status_code == 200
    predictions = response.json()["predictions"]
    assert len(predictions) == 1
    assert predictions[0]["actionType"] == "approve_leave_request"
    assert not any(s["type"] == "keyword_match" for s in predictions[0]["signals"])


async def test_resolve_intent_respects_max_predictions(api_client, tenant_id, make_event):
    user_id = "hr_manager_intent_3"
    action_types = ["approve_leave_request", "submit_timesheet", "close_sprint"]
    for action_type in action_types:
        event = make_event(
            tenantId=tenant_id,
            actor={"nativeUserId": user_id, "userIdType": "employee_id"},
            action={"type": action_type, "category": "update"},
            object={"objectType": "misc", "objectId": f"OBJ-{action_type}"},
        )
        await api_client.post("/v1/events", json=event)

    response = await api_client.post(
        "/v1/resolve-intent",
        json={
            "tenantId": tenant_id,
            "userId": user_id,
            "userIdType": "employee_id",
            "maxPredictions": 2,
        },
    )
    assert response.status_code == 200
    assert len(response.json()["predictions"]) == 2


async def test_resolve_intent_tenant_isolation(api_client, tenant_id, make_event):
    other_tenant = f"{tenant_id}-other"
    user_id = "shared-user"
    event = make_event(
        tenantId=other_tenant,
        actor={"nativeUserId": user_id, "userIdType": "employee_id"},
        action={"type": "view_sprint_board", "category": "read"},
        object={"objectType": "sprint", "objectId": "SPRINT-2"},
    )
    await api_client.post("/v1/events", json=event)

    response = await api_client.post(
        "/v1/resolve-intent",
        json={"tenantId": tenant_id, "userId": user_id, "userIdType": "employee_id"},
    )
    assert response.status_code == 200
    assert response.json()["predictions"] == []


async def test_resolve_intent_invalid_body_returns_400(api_client, tenant_id):
    response = await api_client.post(
        "/v1/resolve-intent", json={"tenantId": tenant_id, "userIdType": "employee_id"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"
