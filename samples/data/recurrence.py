"""Date-recurrence helpers for placing events on realistic calendar schedules."""

from __future__ import annotations

import calendar
from collections.abc import Iterator
from datetime import date, timedelta

_MONDAY = 0
_SATURDAY = 5


def workdays_between(start: date, end: date) -> Iterator[date]:
    """Yield every Monday-to-Friday date in the inclusive range ``[start, end]``."""
    current = start
    while current <= end:
        if current.weekday() < _SATURDAY:
            yield current
        current += timedelta(days=1)


def mondays_between(start: date, end: date) -> Iterator[date]:
    """Yield every Monday in the inclusive range ``[start, end]``."""
    current = start
    while current <= end:
        if current.weekday() == _MONDAY:
            yield current
        current += timedelta(days=1)


def month_end_workdays_between(start: date, end: date) -> Iterator[date]:
    """Yield the last workday of each month touched by ``[start, end]``."""
    for year, month in _months_between(start, end):
        last_workday = _last_workday_of_month(year, month)
        if start <= last_workday <= end:
            yield last_workday


def _months_between(start: date, end: date) -> Iterator[tuple[int, int]]:
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1


def _last_workday_of_month(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    candidate = date(year, month, last_day)
    while candidate.weekday() >= _SATURDAY:
        candidate -= timedelta(days=1)
    return candidate
