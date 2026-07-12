"""Deterministic, LLM-free profile generation.

Reads a :class:`UserPatterns` and emits structured English prose by filling
fixed templates. Fast, free, and predictable — the default backend, and the
baseline the optional LLM backend must stay faithful to.
"""

from __future__ import annotations

from collections.abc import Iterable

from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.pattern_detector import (
    ActionPattern,
    SequencePattern,
    UserPatterns,
)

_MAX_ACTIONS_PER_APP = 3
_MAX_SEQUENCES = 3
_MAX_ACTIVE_OBJECTS = 3
_MAX_DEFAULT_ACTIONS = 3
_MIN_SEQUENCE_CONFIDENCE = 0.3


class TemplateProfileGenerator(ProfileGenerator):
    """Renders a behavioural profile using deterministic string templates."""

    async def generate(self, patterns: UserPatterns) -> str:
        """Assemble a profile paragraph from the detected patterns."""
        sections = [
            self._describe_overview(patterns),
            self._describe_applications(patterns),
            self._describe_sequences(patterns),
            self._describe_active_objects(patterns),
            self._describe_defaults(patterns),
        ]
        return " ".join(section for section in sections if section)

    @staticmethod
    def _describe_overview(patterns: UserPatterns) -> str:
        apps = list(patterns.by_application)
        if not apps:
            return f"User {patterns.user_id} has no recorded activity yet."
        return (
            f"User {patterns.user_id} has performed {patterns.total_events} actions "
            f"across {len(apps)} application(s): {_join(apps)}."
        )

    @staticmethod
    def _describe_applications(patterns: UserPatterns) -> str:
        clauses = []
        for app, app_patterns in patterns.by_application.items():
            recurring = _recurring_actions(app_patterns)
            if not recurring:
                continue
            described = [
                f"{pattern.action_type} ({pattern.frequency}, around {pattern.typical_time})"
                for pattern in recurring
            ]
            clauses.append(f"In {app} they regularly {_join(described)}.")
        return " ".join(clauses)

    @staticmethod
    def _describe_sequences(patterns: UserPatterns) -> str:
        strong = _strong_sequences(patterns.cross_app_sequences)
        if not strong:
            return ""
        described = [
            f"{sequence.trigger_action} in {sequence.trigger_app} is usually followed by "
            f"{sequence.follow_action} in {sequence.follow_app} "
            f"({sequence.typical_gap}, {round(sequence.confidence * 100)}% of the time)"
            for sequence in strong
        ]
        return "Across applications, " + "; ".join(described) + "."

    @staticmethod
    def _describe_active_objects(patterns: UserPatterns) -> str:
        if not patterns.active_objects:
            return ""
        described = [
            f"{obj.object_type} {obj.object_id} in {obj.application_id}"
            for obj in patterns.active_objects[:_MAX_ACTIVE_OBJECTS]
        ]
        return f"They are currently active on {_join(described)}."

    @staticmethod
    def _describe_defaults(patterns: UserPatterns) -> str:
        if not patterns.parameter_defaults:
            return ""
        clauses = []
        for action_type, params in list(patterns.parameter_defaults.items())[
            :_MAX_DEFAULT_ACTIONS
        ]:
            pairs = _join([f"{name}={value}" for name, value in params.items()])
            clauses.append(f"when performing {action_type} they typically use {pairs}")
        return "By default, " + "; ".join(clauses) + "."


def _recurring_actions(app_patterns: list[ActionPattern]) -> list[ActionPattern]:
    recurring = [pattern for pattern in app_patterns if pattern.frequency != "sporadic"]
    return recurring[:_MAX_ACTIONS_PER_APP]


def _strong_sequences(sequences: list[SequencePattern]) -> list[SequencePattern]:
    strong = [
        sequence
        for sequence in sequences
        if sequence.confidence >= _MIN_SEQUENCE_CONFIDENCE
    ]
    return strong[:_MAX_SEQUENCES]


def _join(items: Iterable[str]) -> str:
    """Join names in readable Oxford style: 'a', 'a and b', 'a, b, and c'."""
    values = list(items)
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"
