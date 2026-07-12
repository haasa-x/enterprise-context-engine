"""Rules-based intent scoring: no LLM, no ML — graph history plus keyword matching.

Candidates are the distinct action types a user has actually performed in
their recent history (within any linked application); each candidate is
scored by how well it matches the trigger text, how recently it was last
performed, and how often it has been performed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from context_engine.core.interfaces import HistoryReader
from context_engine.core.models import Prediction, Signal
from context_engine.prediction.keyword_table import KeywordTable

_KEYWORD_WEIGHT = 0.4
_RECENCY_WEIGHT = 0.3
_FREQUENCY_WEIGHT = 0.3
_RECENCY_HALF_LIFE_DAYS = 3.0
_FREQUENCY_SATURATION_COUNT = 5


class IntentScorer:
    """Scores candidate user intents against a trigger using graph history."""

    def __init__(self, graph: HistoryReader, keyword_table: KeywordTable) -> None:
        """Bind this scorer to a history reader and a keyword lookup table."""
        self._graph = graph
        self._keyword_table = keyword_table

    async def score(
        self,
        tenant_id: str,
        user_id: str,
        trigger_text: str | None,
        max_results: int = 5,
        history_days: int = 14,
    ) -> list[Prediction]:
        """Return up to `max_results` predictions, most confident first."""
        history = await self._collect_history(tenant_id, user_id, history_days)
        if not history:
            return []

        candidates = self._group_by_action_type(history)
        keyword_matches = self._keyword_table.match(trigger_text)
        now = datetime.now(timezone.utc)

        predictions = [
            self._score_candidate(action_type, candidate, keyword_matches, now, history_days)
            for action_type, candidate in candidates.items()
        ]
        predictions = [p for p in predictions if p.confidence > 0.0]
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        return predictions[:max_results]

    async def _collect_history(
        self, tenant_id: str, user_id: str, days: int
    ) -> list[dict[str, Any]]:
        history = await self._graph.get_user_history(tenant_id, user_id, days=days)

        canonical_id = await self._graph.get_canonical_user_id(tenant_id, user_id)
        if canonical_id is not None:
            cross_app_history = await self._graph.get_cross_app_history(
                tenant_id, canonical_id, days=days
            )
            seen_event_ids = {record["eventId"] for record in history}
            history.extend(
                record for record in cross_app_history if record["eventId"] not in seen_event_ids
            )

        return history

    @staticmethod
    def _group_by_action_type(
        history: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        for record in history:
            action_type = record["actionType"]
            candidate = candidates.setdefault(
                action_type,
                {
                    "count": 0,
                    "mostRecent": record,
                    "applicationId": record["applicationId"],
                    "objectType": record["objectType"],
                },
            )
            candidate["count"] += 1
            if record["eventTimestamp"] > candidate["mostRecent"]["eventTimestamp"]:
                candidate["mostRecent"] = record
                candidate["applicationId"] = record["applicationId"]
                candidate["objectType"] = record["objectType"]
        return candidates

    @staticmethod
    def _score_candidate(
        action_type: str,
        candidate: dict[str, Any],
        keyword_matches: dict[str, str],
        now: datetime,
        history_days: int,
    ) -> Prediction:
        signals: list[Signal] = []

        keyword_score = 0.0
        matched_keyword = keyword_matches.get(action_type)
        if matched_keyword is not None:
            keyword_score = _KEYWORD_WEIGHT
            signals.append(
                Signal(type="keyword_match", detail=f"trigger text matched '{matched_keyword}'")
            )

        last_seen = candidate["mostRecent"]["eventTimestamp"]
        age_days = max((now - _as_aware(last_seen)).total_seconds() / 86400.0, 0.0)
        recency_score = _RECENCY_WEIGHT * (0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS))
        signals.append(
            Signal(
                type="recency",
                detail=f"last performed on {candidate['applicationId']} {age_days:.1f} day(s) ago",
            )
        )

        count = candidate["count"]
        frequency_score = _FREQUENCY_WEIGHT * min(count / _FREQUENCY_SATURATION_COUNT, 1.0)
        signals.append(
            Signal(
                type="behavior_pattern",
                detail=f"performed {count} time(s) in the last {history_days} days",
            )
        )

        confidence = round(keyword_score + recency_score + frequency_score, 4)

        return Prediction(
            applicationId=candidate["applicationId"],
            actionType=action_type,
            objectType=candidate["objectType"],
            suggestedFilters={},
            confidence=min(confidence, 1.0),
            signals=signals,
        )


def _as_aware(value: datetime) -> datetime:
    """Neo4j returns naive-looking datetimes in some drivers; assume UTC if so."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
