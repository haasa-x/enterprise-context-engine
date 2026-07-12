"""Keyword-to-action-type lookup table for trigger text.

This is a plain substring/prefix lookup, not an ML model: trigger text is
lowercased and scanned for each keyword as a word-boundary prefix (so
"sprints" and "sprinting" both match "sprint").
"""

from __future__ import annotations

import re

DEFAULT_MAPPINGS: dict[str, list[str]] = {
    "sprint": ["view_sprint_board", "close_sprint", "create_sprint"],
    "review": ["submit_performance_review", "view_performance_review"],
    "leave": ["approve_leave_request", "submit_leave_request", "view_leave_balance"],
    "bug": ["log_bug", "update_issue_status", "view_issue"],
    "timesheet": ["submit_timesheet", "approve_timesheet", "view_timesheet"],
    "travel": ["create_travel_request", "submit_expense_report"],
    "expense": ["submit_expense_report", "approve_expense_report"],
    "hire": ["create_requisition", "review_application", "schedule_interview"],
    "candidate": ["review_application", "shortlist_candidate"],
    "deploy": ["create_release", "merge_pull_request"],
    "incident": ["create_incident", "escalate_incident", "resolve_incident"],
}


class KeywordTable:
    """Maps trigger text to candidate action types via keyword matching."""

    def __init__(self, mappings: dict[str, list[str]] | None = None) -> None:
        """Use the given mappings, or DEFAULT_MAPPINGS if none are provided."""
        self._mappings = mappings if mappings is not None else DEFAULT_MAPPINGS

    def match(self, trigger_text: str | None) -> dict[str, str]:
        """Return {action_type: matched_keyword} for every keyword found in trigger_text."""
        if not trigger_text:
            return {}
        lowered = trigger_text.lower()
        matches: dict[str, str] = {}
        for keyword, action_types in self._mappings.items():
            if re.search(rf"\b{re.escape(keyword)}\w*", lowered):
                for action_type in action_types:
                    matches.setdefault(action_type, keyword)
        return matches
