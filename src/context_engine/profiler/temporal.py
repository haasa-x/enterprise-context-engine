"""Deterministic temporal heuristics used by the pattern detector.

These are pure functions over lists of timestamps — no graph access, no LLM —
so they are cheap to test in isolation and produce stable, explainable output.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

DAILY_MAX_GAP_DAYS = 1.5
WEEKLY_MAX_GAP_DAYS = 10.0
MONTHLY_MAX_GAP_DAYS = 45.0

_SECONDS_PER_DAY = 86400.0
_CONFIDENCE_SAMPLE_TARGET = 8.0


def as_aware(value: datetime) -> datetime:
    """Assume UTC for naive datetimes, which some Neo4j drivers return."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def classify_frequency(timestamps: list[datetime]) -> tuple[str, float]:
    """Classify a cadence as daily/weekly/monthly/sporadic with a confidence.

    Confidence rewards regular spacing (low variability) and larger samples.
    """
    if len(timestamps) < 2:
        return "sporadic", 0.3 if timestamps else 0.0

    ordered = sorted(as_aware(t) for t in timestamps)
    span_days = (ordered[-1] - ordered[0]).total_seconds() / _SECONDS_PER_DAY
    if span_days <= 0:
        return "sporadic", 0.3

    average_gap_days = span_days / (len(ordered) - 1)
    if average_gap_days <= DAILY_MAX_GAP_DAYS:
        label = "daily"
    elif average_gap_days <= WEEKLY_MAX_GAP_DAYS:
        label = "weekly"
    elif average_gap_days <= MONTHLY_MAX_GAP_DAYS:
        label = "monthly"
    else:
        label = "sporadic"

    return label, _regularity_confidence(ordered)


def _regularity_confidence(ordered: list[datetime]) -> float:
    """Confidence in [0, 1]: regular gaps and more samples score higher."""
    gaps = [
        (later - earlier).total_seconds()
        for earlier, later in zip(ordered, ordered[1:], strict=False)
    ]
    mean_gap = sum(gaps) / len(gaps)
    if mean_gap <= 0:
        return 0.5
    variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
    coefficient_of_variation = (variance**0.5) / mean_gap
    regularity = max(0.0, 1.0 - coefficient_of_variation)
    sample_factor = min(len(ordered) / _CONFIDENCE_SAMPLE_TARGET, 1.0)
    return float(round(regularity * sample_factor, 2))


def describe_time_of_day(timestamps: list[datetime]) -> str:
    """Describe the most common hour of day, e.g. '9-10 AM'."""
    if not timestamps:
        return "no typical time"
    hours = [as_aware(t).hour for t in timestamps]
    most_common_hour = Counter(hours).most_common(1)[0][0]
    return _format_hour_range(most_common_hour)


def _format_hour_range(hour: int) -> str:
    """Render an hour and the following hour as a human range, e.g. '9-10 AM'."""
    end_hour = (hour + 1) % 24
    start_suffix = "AM" if hour < 12 else "PM"
    end_suffix = "AM" if end_hour < 12 else "PM"
    start_12 = hour % 12 or 12
    end_12 = end_hour % 12 or 12
    if start_suffix == end_suffix:
        return f"{start_12}-{end_12} {start_suffix}"
    return f"{start_12} {start_suffix}-{end_12} {end_suffix}"


def describe_gap(gap_minutes: list[float]) -> str:
    """Describe a set of transition gaps as 'within N minutes' using the median."""
    ordered = sorted(gap_minutes)
    median = ordered[len(ordered) // 2]
    return f"within {max(1, round(median))} minutes"
