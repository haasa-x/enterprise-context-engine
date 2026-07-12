"""Transforms Jira webhook payloads into the universal event schema.

Mapping rules:
  jira:issue_created  -> create_issue, category "create"
  jira:issue_updated  -> inspect changelog.items[].field:
                           "status"   -> update_issue_status, "update"
                           "assignee" -> assign_issue, "update"
                           anything else (e.g. "Rank") is ignored
  jira:issue_deleted  -> delete_issue, category "delete"
  comment_created     -> add_comment, category "create"
  sprint_started      -> start_sprint, category "update"
  sprint_closed       -> close_sprint, category "update"

Unrecognized webhook events, and events missing the fields needed to build a
valid universal event, are ignored (transform returns None) rather than
raising, since Jira instances vary in which fields they populate.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

CONNECTOR_NAME = "jira-connector"
CONNECTOR_VERSION = "1.0.0"

_CHANGELOG_FIELD_ACTIONS: dict[str, tuple[str, str]] = {
    "status": ("update_issue_status", "update"),
    "assignee": ("assign_issue", "update"),
}

_ISSUE_EVENTS = {"jira:issue_created", "jira:issue_updated", "jira:issue_deleted"}
_SPRINT_EVENTS = {"sprint_started", "sprint_closed"}


def transform(
    payload: dict[str, Any],
    tenant_id: str,
    application_instance_id: str,
    environment: str = "production",
) -> dict[str, Any] | None:
    """Map a Jira webhook payload to a universal event, or None to ignore it."""
    webhook_event = payload.get("webhookEvent")

    action = _resolve_action(webhook_event, payload)
    if action is None:
        return None

    actor = _resolve_actor(payload)
    if actor is None:
        return None

    obj = _resolve_object(webhook_event, payload)
    if obj is None:
        return None

    action_type, action_category = action
    return {
        "schemaVersion": "1.0.0",
        "eventId": str(uuid.uuid4()),
        "tenantId": tenant_id,
        "applicationId": "jira",
        "applicationInstanceId": application_instance_id,
        "environment": environment,
        "eventTimestamp": _resolve_timestamp(payload),
        "actor": actor,
        "action": {"type": action_type, "category": action_category},
        "object": obj,
        "source": {"connector": CONNECTOR_NAME, "connectorVersion": CONNECTOR_VERSION},
    }


def _resolve_action(webhook_event: Any, payload: dict[str, Any]) -> tuple[str, str] | None:
    if webhook_event == "jira:issue_created":
        return "create_issue", "create"
    if webhook_event == "jira:issue_deleted":
        return "delete_issue", "delete"
    if webhook_event == "jira:issue_updated":
        return _resolve_issue_updated_action(payload)
    if webhook_event == "comment_created":
        return "add_comment", "create"
    if webhook_event == "sprint_started":
        return "start_sprint", "update"
    if webhook_event == "sprint_closed":
        return "close_sprint", "update"
    return None


def _resolve_issue_updated_action(payload: dict[str, Any]) -> tuple[str, str] | None:
    items = (payload.get("changelog") or {}).get("items") or []
    for item in items:
        mapped = _CHANGELOG_FIELD_ACTIONS.get(item.get("field"))
        if mapped is not None:
            return mapped
    return None


def _resolve_actor(payload: dict[str, Any]) -> dict[str, Any] | None:
    user = payload.get("user")
    if not user:
        return None
    email = user.get("emailAddress")
    if email:
        return {"nativeUserId": email, "userIdType": "email"}
    account_id = user.get("accountId")
    if account_id:
        return {"nativeUserId": account_id, "userIdType": "app_native_id"}
    return None


def _resolve_object(webhook_event: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
    if webhook_event in _ISSUE_EVENTS:
        return _resolve_issue_object(payload)
    if webhook_event == "comment_created":
        return _resolve_comment_object(payload)
    if webhook_event in _SPRINT_EVENTS:
        return _resolve_sprint_object(payload)
    return None


def _resolve_issue_object(payload: dict[str, Any]) -> dict[str, Any] | None:
    issue = payload.get("issue")
    if not issue:
        return None
    issue_key = issue.get("key") or issue.get("id")
    if not issue_key:
        return None
    return {"objectType": "issue", "objectId": str(issue_key)}


def _resolve_comment_object(payload: dict[str, Any]) -> dict[str, Any] | None:
    comment = payload.get("comment")
    if not comment or comment.get("id") is None:
        return None
    obj: dict[str, Any] = {"objectType": "comment", "objectId": str(comment["id"])}
    issue = payload.get("issue")
    if issue and issue.get("key"):
        obj["objectDetails"] = {"issueKey": issue["key"]}
    return obj


def _resolve_sprint_object(payload: dict[str, Any]) -> dict[str, Any] | None:
    sprint = payload.get("sprint")
    if not sprint or sprint.get("id") is None:
        return None
    return {"objectType": "sprint", "objectId": str(sprint["id"])}


def _resolve_timestamp(payload: dict[str, Any]) -> str:
    raw = payload.get("timestamp")
    if isinstance(raw, int | float):
        return datetime.fromtimestamp(raw / 1000, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()
