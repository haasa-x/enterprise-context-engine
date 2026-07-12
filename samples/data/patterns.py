"""Temporal-pattern generators that emit thick, recognizable behavioral trails.

Each function returns a list of event dictionaries for one recurring pattern:
daily sprint checks, weekly leave approvals, monthly expense submissions, and a
cross-application leave-approval-to-capacity-planning sequence.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from typing import Any

from samples.data.catalog import (
    ALICE,
    CONCUR,
    DEVELOPERS,
    ERIN,
    EXPENSE_SUBMITTERS,
    JIRA,
    SUCCESSFACTORS,
)
from samples.data.event_builder import EventBuilder, EventSpec, at_time
from samples.data.recurrence import (
    mondays_between,
    month_end_workdays_between,
    workdays_between,
)


def daily_sprint_checks(
    builder: EventBuilder, start: date, end: date, rng: random.Random
) -> list[dict[str, Any]]:
    """Developers open the sprint board and update issues on weekday mornings ~9 AM."""
    events: list[dict[str, Any]] = []
    for workday in workdays_between(start, end):
        sprint_id = f"SPRINT-{workday.isocalendar().week:02d}"
        for developer in DEVELOPERS:
            session = f"sess-{uuid.uuid4().hex[:12]}"
            board_time = at_time(workday, 9, 0, 25, rng)
            events.append(
                builder.build(
                    EventSpec(
                        developer, JIRA, "view_sprint_board", "read", "sprint", sprint_id,
                        board_time, metadata={"board": "engineering"}, session_id=session,
                    )
                )
            )
            issue_id = f"ENG-{rng.randint(1000, 1400)}"
            events.append(
                builder.build(
                    EventSpec(
                        developer, JIRA, "update_issue_status", "update", "issue", issue_id,
                        board_time + timedelta(minutes=rng.randint(2, 12)),
                        metadata={"to_status": rng.choice(["in_progress", "in_review", "done"])},
                        session_id=session,
                    )
                )
            )
    return events


def weekly_leave_approvals(
    builder: EventBuilder, start: date, end: date, rng: random.Random
) -> list[dict[str, Any]]:
    """The HR manager approves several leave requests each Monday morning."""
    events: list[dict[str, Any]] = []
    for monday in mondays_between(start, end):
        session = f"sess-{uuid.uuid4().hex[:12]}"
        for _ in range(rng.randint(2, 4)):
            request_id = f"LR-{uuid.uuid4().hex[:8]}"
            events.append(
                builder.build(
                    EventSpec(
                        ALICE, SUCCESSFACTORS, "approve_leave_request", "approve",
                        "leave_request", request_id, at_time(monday, 9, 30, 40, rng),
                        metadata={"leave_type": rng.choice(["annual", "sick", "parental"])},
                        session_id=session,
                    )
                )
            )
    return events


def monthly_expense_submissions(
    builder: EventBuilder, start: date, end: date, rng: random.Random
) -> list[dict[str, Any]]:
    """Employees submit expense reports on the last workday of each month."""
    events: list[dict[str, Any]] = []
    for month_end in month_end_workdays_between(start, end):
        for submitter in EXPENSE_SUBMITTERS:
            report_id = f"EXP-{month_end.strftime('%Y%m')}-{submitter.native_user_id[:3]}"
            amount = round(rng.uniform(120.0, 2400.0), 2)
            events.append(
                builder.build(
                    EventSpec(
                        submitter, CONCUR, "submit_expense_report", "create",
                        "expense_report", report_id, at_time(month_end, 16, 0, 60, rng),
                        metadata={"amount_usd": amount, "currency": "USD"},
                        object_details={"line_items": rng.randint(3, 14)},
                    )
                )
            )
    return events


def cross_app_leave_to_capacity(
    builder: EventBuilder, start: date, end: date, rng: random.Random
) -> list[dict[str, Any]]:
    """A project manager approves leave then updates Jira capacity within ~10 minutes."""
    events: list[dict[str, Any]] = []
    for monday in mondays_between(start, end):
        if rng.random() > 0.7:
            continue
        session = f"sess-{uuid.uuid4().hex[:12]}"
        request_id = f"LR-{uuid.uuid4().hex[:8]}"
        approval_time = at_time(monday, 10, 15, 30, rng)
        events.append(
            builder.build(
                EventSpec(
                    ERIN, SUCCESSFACTORS, "approve_leave_request", "approve",
                    "leave_request", request_id, approval_time,
                    metadata={"leave_type": "annual"}, session_id=session,
                )
            )
        )
        events.append(
            builder.build(
                EventSpec(
                    ERIN, JIRA, "update_capacity_plan", "update", "sprint",
                    f"SPRINT-{monday.isocalendar().week:02d}",
                    approval_time + timedelta(minutes=rng.randint(3, 10)),
                    metadata={"reason": "team_member_on_leave"}, session_id=session,
                )
            )
        )
    return events


ALL_PATTERNS = (
    daily_sprint_checks,
    weekly_leave_approvals,
    monthly_expense_submissions,
    cross_app_leave_to_capacity,
)
