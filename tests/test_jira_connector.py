"""Tests for the Jira connector: transformer.py and webhook_handler.py."""

from __future__ import annotations

import httpx
import pytest

from connectors.jira.transformer import transform
from connectors.jira.webhook_handler import JiraWebhookHandler

TENANT_ID = "acme-corp"
APP_INSTANCE_ID = "acme-jira-01"


def _base_user(email: str = "user@acme.com") -> dict:
    return {"accountId": "acc-1", "emailAddress": email, "displayName": "A User"}


def test_issue_created_maps_to_create_issue():
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
        "timestamp": 1723968000000,
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)

    assert event is not None
    assert event["action"] == {"type": "create_issue", "category": "create"}
    assert event["object"] == {"objectType": "issue", "objectId": "PROJ-1"}
    assert event["actor"] == {"nativeUserId": "user@acme.com", "userIdType": "email"}
    assert event["applicationId"] == "jira"
    assert event["tenantId"] == TENANT_ID


def test_issue_deleted_maps_to_delete_issue():
    payload = {
        "webhookEvent": "jira:issue_deleted",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"] == {"type": "delete_issue", "category": "delete"}


def test_issue_updated_status_change_maps_to_update_issue_status():
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
        "changelog": {"items": [{"field": "status", "fromString": "Open", "toString": "Done"}]},
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"] == {"type": "update_issue_status", "category": "update"}


def test_issue_updated_assignee_change_maps_to_assign_issue():
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
        "changelog": {"items": [{"field": "assignee", "toString": "Bob"}]},
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"] == {"type": "assign_issue", "category": "update"}


def test_issue_updated_rank_only_change_is_ignored():
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
        "changelog": {"items": [{"field": "Rank", "toString": "0|i0007z:"}]},
    }
    assert transform(payload, TENANT_ID, APP_INSTANCE_ID) is None


def test_issue_updated_rank_and_status_change_uses_status():
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
        "changelog": {
            "items": [
                {"field": "Rank", "toString": "0|i0007z:"},
                {"field": "status", "toString": "Done"},
            ]
        },
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"]["type"] == "update_issue_status"


def test_issue_updated_missing_changelog_is_ignored():
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": _base_user(),
    }
    assert transform(payload, TENANT_ID, APP_INSTANCE_ID) is None


def test_comment_created_maps_to_add_comment():
    payload = {
        "webhookEvent": "comment_created",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "comment": {"id": "5001", "body": "Looks good"},
        "user": _base_user(),
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"] == {"type": "add_comment", "category": "create"}
    assert event["object"] == {
        "objectType": "comment",
        "objectId": "5001",
        "objectDetails": {"issueKey": "PROJ-1"},
    }


def test_sprint_started_maps_to_start_sprint():
    payload = {
        "webhookEvent": "sprint_started",
        "sprint": {"id": 7, "name": "Sprint 7"},
        "user": _base_user(),
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"] == {"type": "start_sprint", "category": "update"}
    assert event["object"] == {"objectType": "sprint", "objectId": "7"}


def test_sprint_closed_maps_to_close_sprint():
    payload = {
        "webhookEvent": "sprint_closed",
        "sprint": {"id": 7, "name": "Sprint 7"},
        "user": _base_user(),
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["action"] == {"type": "close_sprint", "category": "update"}


def test_unrecognized_webhook_event_is_ignored():
    payload = {"webhookEvent": "jira:something_unknown", "user": _base_user()}
    assert transform(payload, TENANT_ID, APP_INSTANCE_ID) is None


def test_missing_user_is_ignored():
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {"id": "10001", "key": "PROJ-1"},
    }
    assert transform(payload, TENANT_ID, APP_INSTANCE_ID) is None


def test_missing_issue_is_ignored():
    payload = {"webhookEvent": "jira:issue_created", "user": _base_user()}
    assert transform(payload, TENANT_ID, APP_INSTANCE_ID) is None


def test_actor_falls_back_to_account_id_without_email():
    payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {"id": "10001", "key": "PROJ-1"},
        "user": {"accountId": "acc-1"},
    }
    event = transform(payload, TENANT_ID, APP_INSTANCE_ID)
    assert event is not None
    assert event["actor"] == {"nativeUserId": "acc-1", "userIdType": "app_native_id"}


async def test_webhook_handler_forwards_transformed_event():
    captured: dict = {}

    async def responder(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return httpx.Response(201, json={"eventId": "x", "status": "accepted"})

    transport = httpx.MockTransport(responder)
    async with httpx.AsyncClient(transport=transport, base_url="http://ingest") as client:
        handler = JiraWebhookHandler(client, "/v1/events", TENANT_ID, APP_INSTANCE_ID)
        payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {"id": "10001", "key": "PROJ-1"},
            "user": _base_user(),
        }
        result = await handler.handle(payload)

    assert result["status"] == "forwarded"
    assert captured["headers"]["x-tenant-id"] == TENANT_ID


async def test_webhook_handler_ignores_unmapped_event():
    async def responder(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not forward an ignored event")

    transport = httpx.MockTransport(responder)
    async with httpx.AsyncClient(transport=transport, base_url="http://ingest") as client:
        handler = JiraWebhookHandler(client, "/v1/events", TENANT_ID, APP_INSTANCE_ID)
        result = await handler.handle({"webhookEvent": "jira:something_unknown"})

    assert result == {"status": "ignored"}


async def test_webhook_handler_treats_409_as_duplicate():
    async def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "duplicate_event"})

    transport = httpx.MockTransport(responder)
    async with httpx.AsyncClient(transport=transport, base_url="http://ingest") as client:
        handler = JiraWebhookHandler(client, "/v1/events", TENANT_ID, APP_INSTANCE_ID)
        payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {"id": "10001", "key": "PROJ-1"},
            "user": _base_user(),
        }
        result = await handler.handle(payload)

    assert result["status"] == "duplicate"


async def test_webhook_handler_raises_on_other_errors():
    async def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal_error"})

    transport = httpx.MockTransport(responder)
    async with httpx.AsyncClient(transport=transport, base_url="http://ingest") as client:
        handler = JiraWebhookHandler(client, "/v1/events", TENANT_ID, APP_INSTANCE_ID)
        payload = {
            "webhookEvent": "jira:issue_created",
            "issue": {"id": "10001", "key": "PROJ-1"},
            "user": _base_user(),
        }
        with pytest.raises(httpx.HTTPStatusError):
            await handler.handle(payload)
