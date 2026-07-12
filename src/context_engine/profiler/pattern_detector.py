"""Detect recurring behavioural patterns from a user's graph history.

Reads a user's PERFORMED events (no LLM, no ML) and derives:

* per-application recurring action patterns (cadence + typical time),
* cross-application action sequences (A in app X then B in app Y),
* currently active business objects,
* the most common parameter values per action type.

The output :class:`UserPatterns` is the sole input to the profile generators.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from context_engine.core.interfaces import PatternReader
from context_engine.profiler.temporal import (
    as_aware,
    classify_frequency,
    describe_gap,
    describe_time_of_day,
)

PROFILING_WINDOW_DAYS = 180
_SEQUENCE_GAP_MINUTES = 30.0
_MIN_SEQUENCE_OCCURRENCES = 2
_ACTIVE_OBJECT_WINDOW_DAYS = 14
_MIN_ACTIVE_OBJECT_INTERACTIONS = 2
_MAX_ACTIVE_OBJECTS = 10


@dataclass
class ActionPattern:
    """A recurring action a user performs within a single application."""

    action_type: str
    frequency: str  # "daily", "weekly", "monthly", "sporadic"
    typical_time: str  # e.g. "9-10 AM"
    count_in_period: int
    confidence: float


@dataclass
class SequencePattern:
    """An action in one application that is typically followed by another."""

    trigger_app: str
    trigger_action: str
    follow_app: str
    follow_action: str
    typical_gap: str  # e.g. "within 30 minutes"
    confidence: float


@dataclass
class ActiveObject:
    """A business object the user is currently, repeatedly interacting with."""

    application_id: str
    object_type: str
    object_id: str
    interaction_count: int
    last_activity: datetime


@dataclass
class UserPatterns:
    """The full behavioural fingerprint of one user across their applications."""

    user_id: str
    total_events: int
    by_application: dict[str, list[ActionPattern]] = field(default_factory=dict)
    cross_app_sequences: list[SequencePattern] = field(default_factory=list)
    active_objects: list[ActiveObject] = field(default_factory=list)
    parameter_defaults: dict[str, dict[str, str]] = field(default_factory=dict)


class PatternDetector:
    """Derives :class:`UserPatterns` from a user's stored graph history."""

    def __init__(self, graph: PatternReader) -> None:
        """Bind the detector to a pattern-reading graph store."""
        self._graph = graph

    async def detect(self, tenant_id: str, user_id: str) -> UserPatterns:
        """Read the user's history and derive their behavioural patterns."""
        events = await self._graph.get_user_history(
            tenant_id, user_id, days=PROFILING_WINDOW_DAYS
        )
        total_events = await self._graph.get_user_event_count(tenant_id, user_id)
        return UserPatterns(
            user_id=user_id,
            total_events=total_events,
            by_application=self._detect_action_patterns(events),
            cross_app_sequences=self._detect_sequences(events),
            active_objects=self._detect_active_objects(events),
            parameter_defaults=self._detect_parameter_defaults(events),
        )

    @staticmethod
    def _detect_action_patterns(
        events: list[dict[str, Any]],
    ) -> dict[str, list[ActionPattern]]:
        grouped: dict[str, dict[str, list[datetime]]] = {}
        for event in events:
            app = event["applicationId"]
            action_type = event["actionType"]
            grouped.setdefault(app, {}).setdefault(action_type, []).append(
                event["eventTimestamp"]
            )

        patterns: dict[str, list[ActionPattern]] = {}
        for app, actions in grouped.items():
            app_patterns = [
                _build_action_pattern(action_type, timestamps)
                for action_type, timestamps in actions.items()
            ]
            app_patterns.sort(key=lambda pattern: pattern.count_in_period, reverse=True)
            patterns[app] = app_patterns
        return patterns

    def _detect_sequences(self, events: list[dict[str, Any]]) -> list[SequencePattern]:
        ordered = sorted(events, key=lambda event: as_aware(event["eventTimestamp"]))
        action_totals = Counter(
            (event["applicationId"], event["actionType"]) for event in events
        )
        transitions: dict[tuple[str, str, str, str], list[float]] = {}
        for previous, current in zip(ordered, ordered[1:], strict=False):
            gap_minutes = self._cross_app_gap_minutes(previous, current)
            if gap_minutes is None:
                continue
            key = (
                previous["applicationId"],
                previous["actionType"],
                current["applicationId"],
                current["actionType"],
            )
            transitions.setdefault(key, []).append(gap_minutes)

        sequences = [
            _build_sequence(key, gaps, action_totals[(key[0], key[1])])
            for key, gaps in transitions.items()
            if len(gaps) >= _MIN_SEQUENCE_OCCURRENCES
        ]
        sequences.sort(key=lambda sequence: sequence.confidence, reverse=True)
        return sequences

    @staticmethod
    def _cross_app_gap_minutes(
        previous: dict[str, Any], current: dict[str, Any]
    ) -> float | None:
        if previous["applicationId"] == current["applicationId"]:
            return None
        gap_seconds = (
            as_aware(current["eventTimestamp"]) - as_aware(previous["eventTimestamp"])
        ).total_seconds()
        gap_minutes = gap_seconds / 60.0
        if 0 <= gap_minutes <= _SEQUENCE_GAP_MINUTES:
            return gap_minutes
        return None

    @staticmethod
    def _detect_active_objects(events: list[dict[str, Any]]) -> list[ActiveObject]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_ACTIVE_OBJECT_WINDOW_DAYS)
        stats: dict[tuple[str, str, str], dict[str, Any]] = {}
        for event in events:
            timestamp = as_aware(event["eventTimestamp"])
            key = (event["applicationId"], event["objectType"], event["objectId"])
            entry = stats.setdefault(key, {"count": 0, "last": timestamp})
            entry["count"] += 1
            entry["last"] = max(entry["last"], timestamp)

        active = [
            ActiveObject(app, object_type, object_id, entry["count"], entry["last"])
            for (app, object_type, object_id), entry in stats.items()
            if entry["last"] >= cutoff
            and entry["count"] >= _MIN_ACTIVE_OBJECT_INTERACTIONS
        ]
        active.sort(
            key=lambda obj: (obj.interaction_count, obj.last_activity), reverse=True
        )
        return active[:_MAX_ACTIVE_OBJECTS]

    @staticmethod
    def _detect_parameter_defaults(
        events: list[dict[str, Any]],
    ) -> dict[str, dict[str, str]]:
        counters: dict[str, dict[str, Counter[str]]] = {}
        for event in events:
            metadata = event.get("metadata")
            if not isinstance(metadata, dict):
                continue
            action_type = event["actionType"]
            for name, value in metadata.items():
                if not isinstance(value, (str, int, float, bool)):
                    continue
                counters.setdefault(action_type, {}).setdefault(name, Counter())[
                    str(value)
                ] += 1

        return {
            action_type: {
                name: counter.most_common(1)[0][0] for name, counter in params.items()
            }
            for action_type, params in counters.items()
        }


def _build_action_pattern(
    action_type: str, timestamps: list[datetime]
) -> ActionPattern:
    frequency, confidence = classify_frequency(timestamps)
    return ActionPattern(
        action_type=action_type,
        frequency=frequency,
        typical_time=describe_time_of_day(timestamps),
        count_in_period=len(timestamps),
        confidence=confidence,
    )


def _build_sequence(
    key: tuple[str, str, str, str], gaps: list[float], trigger_total: int
) -> SequencePattern:
    trigger_app, trigger_action, follow_app, follow_action = key
    confidence = round(min(len(gaps) / trigger_total, 1.0), 2) if trigger_total else 0.0
    return SequencePattern(
        trigger_app=trigger_app,
        trigger_action=trigger_action,
        follow_app=follow_app,
        follow_action=follow_action,
        typical_gap=describe_gap(gaps),
        confidence=confidence,
    )
