"""Tests for the profile scheduler against an in-memory fake graph.

No Neo4j required: a fake ProfilingGraph supplies history and records profile
writes so we can assert on generation, skipping, and version increments.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from context_engine.config import Settings
from context_engine.profiler.scheduler import ProfileScheduler
from context_engine.profiler.template_generator import TemplateProfileGenerator

_NOW = datetime.now(timezone.utc)


def _events(user_id: str, count: int) -> list[dict[str, Any]]:
    return [
        {
            "eventId": f"{user_id}-{index}",
            "applicationId": "jira",
            "actionType": "update_issue_status",
            "actionCategory": "update",
            "eventTimestamp": _NOW - timedelta(days=index),
            "metadata": None,
            "objectType": "issue",
            "objectId": "PROJ-1",
        }
        for index in range(count)
    ]


class _FakeGraph:
    """In-memory ProfilingGraph: per-user history plus stored profiles."""

    def __init__(self, histories: dict[str, list[dict[str, Any]]]) -> None:
        self._histories = histories
        self.profiles: dict[str, dict[str, Any]] = {}

    async def get_active_users(self, tenant_id: str, since_days: int = 7) -> list[str]:
        return list(self._histories)

    async def get_user_history(
        self, tenant_id: str, user_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        return list(self._histories.get(user_id, []))

    async def get_user_event_count(self, tenant_id: str, user_id: str) -> int:
        return len(self._histories.get(user_id, []))

    async def update_user_profile(
        self, tenant_id: str, user_id: str, profile_text: str, version: int
    ) -> None:
        self.profiles[user_id] = {
            "nlqProfile": profile_text,
            "profileVersion": version,
        }

    async def get_user_profile(
        self, tenant_id: str, user_id: str
    ) -> dict[str, Any] | None:
        return self.profiles.get(user_id)


def _scheduler(graph: _FakeGraph) -> ProfileScheduler:
    return ProfileScheduler(graph, TemplateProfileGenerator(), Settings())


async def test_run_once_generates_profiles_for_users_over_threshold() -> None:
    graph = _FakeGraph({"active_user": _events("active_user", 15)})

    generated = await _scheduler(graph).run_once("acme")

    assert generated == 1
    assert "active_user" in graph.profiles
    assert graph.profiles["active_user"]["profileVersion"] == 1
    assert "update_issue_status" in graph.profiles["active_user"]["nlqProfile"]


async def test_run_once_skips_users_below_event_threshold() -> None:
    graph = _FakeGraph({"quiet_user": _events("quiet_user", 3)})

    generated = await _scheduler(graph).run_once("acme")

    assert generated == 0
    assert graph.profiles == {}


async def test_run_once_increments_profile_version_on_regeneration() -> None:
    graph = _FakeGraph({"active_user": _events("active_user", 15)})
    scheduler = _scheduler(graph)

    await scheduler.run_once("acme")
    await scheduler.run_once("acme")

    assert graph.profiles["active_user"]["profileVersion"] == 2


async def test_run_once_counts_only_generated_profiles() -> None:
    graph = _FakeGraph(
        {
            "busy": _events("busy", 20),
            "quiet": _events("quiet", 2),
        }
    )

    generated = await _scheduler(graph).run_once("acme")

    assert generated == 1
