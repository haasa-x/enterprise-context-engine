"""Tests for GET /v1/users/{userId}/profile.

The route's collaborators are injected, so we override them with fakes and
drive the ASGI app directly — no Neo4j container or lifespan startup needed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import pytest_asyncio

from context_engine.api.app import create_app
from context_engine.api.dependencies import (
    get_graph_store,
    get_pattern_detector,
    get_profile_generator,
    get_settings,
)
from context_engine.config import Settings
from context_engine.profiler.pattern_detector import ActionPattern, UserPatterns
from context_engine.profiler.template_generator import TemplateProfileGenerator

_NOW = datetime.now(timezone.utc)


def _patterns(total_events: int) -> UserPatterns:
    return UserPatterns(
        user_id="hr_manager001",
        total_events=total_events,
        by_application={
            "jira": [
                ActionPattern(
                    action_type="update_issue_status",
                    frequency="daily",
                    typical_time="9-10 AM",
                    count_in_period=total_events,
                    confidence=0.9,
                )
            ]
        },
    )


class _FakeDetector:
    def __init__(self, patterns: UserPatterns) -> None:
        self._patterns = patterns

    async def detect(self, tenant_id: str, user_id: str) -> UserPatterns:
        return self._patterns


class _FakeGraph:
    def __init__(self, stored: dict[str, Any] | None) -> None:
        self._stored = stored

    async def get_user_profile(
        self, tenant_id: str, user_id: str
    ) -> dict[str, Any] | None:
        return self._stored


@pytest_asyncio.fixture
async def _client_factory() -> AsyncIterator[Any]:
    apps: list[Any] = []

    def _build(
        patterns: UserPatterns, stored: dict[str, Any] | None
    ) -> httpx.AsyncClient:
        app = create_app(settings=Settings())
        app.dependency_overrides[get_settings] = lambda: Settings()
        app.dependency_overrides[get_pattern_detector] = lambda: _FakeDetector(patterns)
        app.dependency_overrides[get_graph_store] = lambda: _FakeGraph(stored)
        app.dependency_overrides[get_profile_generator] = TemplateProfileGenerator
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    yield _build
    for app in apps:
        app.dependency_overrides.clear()


async def test_returns_stored_profile_with_patterns(_client_factory: Any) -> None:
    stored = {
        "nlqProfile": "User hr_manager001 checks Jira daily.",
        "profileGeneratedAt": _NOW,
        "profileVersion": 3,
    }
    async with _client_factory(_patterns(50), stored) as client:
        response = await client.get(
            "/v1/users/hr_manager001/profile",
            headers={"X-Tenant-Id": "acme-corp"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["userId"] == "hr_manager001"
    assert body["profile"] == "User hr_manager001 checks Jira daily."
    assert body["version"] == 3
    assert body["totalEvents"] == 50
    assert body["byApplication"]["jira"][0]["actionType"] == "update_issue_status"


async def test_generates_on_the_fly_when_no_stored_profile(
    _client_factory: Any,
) -> None:
    async with _client_factory(_patterns(50), None) as client:
        response = await client.get(
            "/v1/users/hr_manager001/profile",
            headers={"X-Tenant-Id": "acme-corp"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "update_issue_status" in body["profile"]
    assert body["version"] is None


async def test_returns_404_insufficient_data_for_sparse_user(
    _client_factory: Any,
) -> None:
    async with _client_factory(_patterns(3), None) as client:
        response = await client.get(
            "/v1/users/hr_manager001/profile",
            headers={"X-Tenant-Id": "acme-corp"},
        )

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "insufficient_data"
    assert "at least 10 events" in body["detail"]
    assert "requestId" in body


async def test_requires_tenant_header(_client_factory: Any) -> None:
    async with _client_factory(_patterns(50), None) as client:
        response = await client.get("/v1/users/hr_manager001/profile")

    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


@pytest.mark.parametrize("version", [1, 2, 7])
async def test_echoes_stored_version(_client_factory: Any, version: int) -> None:
    stored = {
        "nlqProfile": "text",
        "profileGeneratedAt": _NOW,
        "profileVersion": version,
    }
    async with _client_factory(_patterns(20), stored) as client:
        response = await client.get(
            "/v1/users/u1/profile", headers={"X-Tenant-Id": "acme-corp"}
        )

    assert response.json()["version"] == version
