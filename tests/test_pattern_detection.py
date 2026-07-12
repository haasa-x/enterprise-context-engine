"""Tests for the profiler's pattern detection.

These exercise :class:`PatternDetector` against an in-memory fake graph, plus
the pure temporal heuristics, so they run without a Neo4j container.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from context_engine.profiler.pattern_detector import PatternDetector
from context_engine.profiler.temporal import (
    classify_frequency,
    describe_time_of_day,
)

_NOW = datetime.now(timezone.utc)


def _event(
    *,
    application_id: str,
    action_type: str,
    timestamp: datetime,
    object_type: str = "issue",
    object_id: str = "PROJ-1",
    metadata: dict[str, Any] | None = None,
    category: str = "update",
) -> dict[str, Any]:
    """Build an event shaped like GraphStore.get_user_history output."""
    return {
        "eventId": f"{action_type}-{timestamp.isoformat()}",
        "applicationId": application_id,
        "actionType": action_type,
        "actionCategory": category,
        "eventTimestamp": timestamp,
        "metadata": metadata,
        "objectType": object_type,
        "objectId": object_id,
    }


class _FakePatternReader:
    """In-memory PatternReader returning a fixed event list."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    async def get_user_history(
        self, tenant_id: str, user_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        return list(self._events)

    async def get_user_event_count(self, tenant_id: str, user_id: str) -> int:
        return len(self._events)


def test_classify_frequency_labels_daily_cadence_as_daily() -> None:
    timestamps = [_NOW - timedelta(days=offset) for offset in range(10)]
    label, confidence = classify_frequency(timestamps)
    assert label == "daily"
    assert confidence > 0.5


def test_classify_frequency_labels_weekly_cadence_as_weekly() -> None:
    timestamps = [_NOW - timedelta(weeks=offset) for offset in range(8)]
    label, _confidence = classify_frequency(timestamps)
    assert label == "weekly"


def test_classify_frequency_with_single_event_is_sporadic() -> None:
    label, confidence = classify_frequency([_NOW])
    assert label == "sporadic"
    assert confidence == pytest.approx(0.3)


def test_describe_time_of_day_reports_dominant_hour_range() -> None:
    nine_am = _NOW.replace(hour=9, minute=15)
    timestamps = [nine_am - timedelta(days=offset) for offset in range(5)]
    assert describe_time_of_day(timestamps) == "9-10 AM"


async def test_detect_finds_daily_action_pattern() -> None:
    events = [
        _event(
            application_id="jira",
            action_type="update_issue_status",
            timestamp=_NOW.replace(hour=9) - timedelta(days=offset),
        )
        for offset in range(14)
    ]
    detector = PatternDetector(_FakePatternReader(events))

    patterns = await detector.detect("acme", "user1")

    assert patterns.total_events == 14
    jira_patterns = patterns.by_application["jira"]
    assert jira_patterns[0].action_type == "update_issue_status"
    assert jira_patterns[0].frequency == "daily"
    assert jira_patterns[0].typical_time == "9-10 AM"


async def test_detect_finds_cross_app_sequence() -> None:
    events: list[dict[str, Any]] = []
    for offset in range(6):
        base = _NOW - timedelta(days=offset)
        events.append(
            _event(
                application_id="successfactors",
                action_type="approve_leave_request",
                timestamp=base,
                object_type="leave_request",
                object_id=f"LR-{offset}",
            )
        )
        events.append(
            _event(
                application_id="calendar",
                action_type="check_calendar",
                timestamp=base + timedelta(minutes=5),
                object_type="calendar",
                object_id="cal-1",
            )
        )
    detector = PatternDetector(_FakePatternReader(events))

    patterns = await detector.detect("acme", "user1")

    assert patterns.cross_app_sequences, "expected a cross-app sequence"
    sequence = patterns.cross_app_sequences[0]
    assert sequence.trigger_app == "successfactors"
    assert sequence.trigger_action == "approve_leave_request"
    assert sequence.follow_app == "calendar"
    assert sequence.follow_action == "check_calendar"
    assert sequence.confidence > 0.0


async def test_detect_computes_parameter_defaults() -> None:
    events = [
        _event(
            application_id="concur",
            action_type="submit_expense",
            timestamp=_NOW - timedelta(days=offset),
            metadata={"currency": "USD", "category": "travel"},
        )
        for offset in range(5)
    ]
    events.append(
        _event(
            application_id="concur",
            action_type="submit_expense",
            timestamp=_NOW - timedelta(days=6),
            metadata={"currency": "EUR", "category": "travel"},
        )
    )
    detector = PatternDetector(_FakePatternReader(events))

    patterns = await detector.detect("acme", "user1")

    defaults = patterns.parameter_defaults["submit_expense"]
    assert defaults["currency"] == "USD"
    assert defaults["category"] == "travel"


async def test_detect_lists_active_objects() -> None:
    events = [
        _event(
            application_id="jira",
            action_type="update_issue_status",
            timestamp=_NOW - timedelta(days=offset),
            object_type="sprint",
            object_id="SPRINT-42",
        )
        for offset in range(3)
    ]
    detector = PatternDetector(_FakePatternReader(events))

    patterns = await detector.detect("acme", "user1")

    assert patterns.active_objects
    active = patterns.active_objects[0]
    assert active.object_type == "sprint"
    assert active.object_id == "SPRINT-42"
    assert active.interaction_count == 3


async def test_detect_with_no_events_returns_empty_patterns() -> None:
    detector = PatternDetector(_FakePatternReader([]))

    patterns = await detector.detect("acme", "user1")

    assert patterns.total_events == 0
    assert patterns.by_application == {}
    assert patterns.cross_app_sequences == []
    assert patterns.active_objects == []
    assert patterns.parameter_defaults == {}
