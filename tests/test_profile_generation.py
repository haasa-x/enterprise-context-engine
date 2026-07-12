"""Tests for the deterministic template profile generator.

Build UserPatterns directly and assert on the rendered prose — no Neo4j needed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from context_engine.profiler.pattern_detector import (
    ActionPattern,
    ActiveObject,
    SequencePattern,
    UserPatterns,
)
from context_engine.profiler.template_generator import TemplateProfileGenerator

_NOW = datetime.now(timezone.utc)


async def test_generate_summarizes_overview_and_cadence() -> None:
    patterns = UserPatterns(
        user_id="hr_manager001",
        total_events=120,
        by_application={
            "jira": [
                ActionPattern(
                    action_type="update_issue_status",
                    frequency="daily",
                    typical_time="9-10 AM",
                    count_in_period=90,
                    confidence=0.9,
                )
            ]
        },
    )

    profile = await TemplateProfileGenerator().generate(patterns)

    assert "hr_manager001" in profile
    assert "120 actions" in profile
    assert "jira" in profile
    assert "update_issue_status" in profile
    assert "daily" in profile
    assert "9-10 AM" in profile


async def test_generate_describes_cross_app_sequences() -> None:
    patterns = UserPatterns(
        user_id="u1",
        total_events=40,
        cross_app_sequences=[
            SequencePattern(
                trigger_app="successfactors",
                trigger_action="approve_leave_request",
                follow_app="calendar",
                follow_action="check_calendar",
                typical_gap="within 5 minutes",
                confidence=0.78,
            )
        ],
    )

    profile = await TemplateProfileGenerator().generate(patterns)

    assert "approve_leave_request" in profile
    assert "check_calendar" in profile
    assert "78%" in profile


async def test_generate_omits_low_confidence_sequences() -> None:
    patterns = UserPatterns(
        user_id="u1",
        total_events=40,
        cross_app_sequences=[
            SequencePattern(
                trigger_app="a",
                trigger_action="x",
                follow_app="b",
                follow_action="y",
                typical_gap="within 20 minutes",
                confidence=0.1,
            )
        ],
    )

    profile = await TemplateProfileGenerator().generate(patterns)

    assert "usually followed by" not in profile


async def test_generate_describes_active_objects_and_defaults() -> None:
    patterns = UserPatterns(
        user_id="u1",
        total_events=30,
        active_objects=[
            ActiveObject(
                application_id="jira",
                object_type="sprint",
                object_id="SPRINT-42",
                interaction_count=8,
                last_activity=_NOW,
            )
        ],
        parameter_defaults={"submit_expense": {"currency": "USD"}},
    )

    profile = await TemplateProfileGenerator().generate(patterns)

    assert "SPRINT-42" in profile
    assert "submit_expense" in profile
    assert "currency=USD" in profile


async def test_generate_with_no_activity_states_so() -> None:
    patterns = UserPatterns(user_id="ghost", total_events=0)

    profile = await TemplateProfileGenerator().generate(patterns)

    assert profile == "User ghost has no recorded activity yet."
