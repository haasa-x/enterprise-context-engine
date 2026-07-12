"""Tests for the read-only admin routes backing the graph-viewer UI.

Collaborators are injected, so a fake graph store lets these run without Neo4j.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest_asyncio

from context_engine.api.app import create_app
from context_engine.api.dependencies import get_graph_store
from context_engine.config import Settings

_NOW = datetime.now(timezone.utc)


class _FakeGraph:
    async def get_active_users(self, tenant_id: str, since_days: int = 7) -> list[str]:
        return ["hr_manager001", "engineer007"]

    async def get_user_history(
        self, tenant_id: str, user_id: str, days: int = 14, limit: int | None = None
    ) -> list[dict[str, Any]]:
        return [
            {
                "eventId": "e1",
                "applicationId": "jira",
                "actionType": "update_issue_status",
                "actionCategory": "update",
                "eventTimestamp": _NOW.isoformat(),
                "metadata": None,
                "objectType": "issue",
                "objectId": "PROJ-1",
            }
        ]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings=Settings())
    app.dependency_overrides[get_graph_store] = _FakeGraph
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_list_users_returns_tenant_users(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/admin/users", headers={"X-Tenant-Id": "acme"})

    assert response.status_code == 200
    assert response.json()["users"] == ["hr_manager001", "engineer007"]


async def test_list_user_events_returns_events(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/admin/users/hr_manager001/events", headers={"X-Tenant-Id": "acme"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["userId"] == "hr_manager001"
    assert body["events"][0]["actionType"] == "update_issue_status"
    # Bounded read exposes the cap and whether the window held more.
    assert body["limit"] >= 1
    assert body["truncated"] is False


async def test_list_user_events_rejects_out_of_range_limit(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/admin/users/hr_manager001/events",
        params={"limit": 0},
        headers={"X-Tenant-Id": "acme"},
    )
    assert response.status_code == 400


async def test_admin_users_requires_tenant_header(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/admin/users")

    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"
