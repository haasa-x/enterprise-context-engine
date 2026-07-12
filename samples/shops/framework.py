"""Declarative framework for synthesizing realistic multi-module shop events.

A shop is defined by a set of :class:`Routine` objects (recurring, single-module
activity by a persona group) and :class:`CrossAppLink` objects (a two-step
workflow that crosses a product/module boundary). :func:`generate_shop_events`
expands those definitions into universal-schema event dictionaries.

The design keeps each shop file small and readable: shop authors describe *what*
happens (actions, objects, cadence, personas) and this module handles *how* it
becomes a schema-conformant event with realistic identifiers, sessions, trace
correlation, and calendar placement.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from samples.data.recurrence import (
    mondays_between,
    month_end_workdays_between,
    workdays_between,
)

# ---------------------------------------------------------------------------
# Domain definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Persona:
    """A named user of one or more modules within a shop.

    ``user_id_type`` mirrors how the source product actually issues identity
    (employee_id for SAP/Oracle HR, email for Concur, sso_subject for
    Salesforce), which also exercises the engine's identity resolution.
    """

    native_user_id: str
    display_name: str
    roles: tuple[str, ...]
    user_id_type: str = "email"


@dataclass(frozen=True)
class Module:
    """One module of a product, addressable as a distinct application.

    ``application_id`` is deliberately module-grain (e.g.
    ``sap_successfactors_learning``) so the profiler renders a node per module
    and detects cross-module sequences.
    """

    application_id: str
    instance_id: str
    connector: str
    connector_version: str
    suite: str
    module: str


@dataclass(frozen=True)
class Activity:
    """A single action a persona performs, expanded into one event.

    ``details`` produces free-form ``object.objectDetails``. ``metadata``
    produces extra ``action.metadata`` (merged with suite/module labels).
    ``id_pool`` makes the activity reuse a stable set of object ids so the
    "active objects" detector has recurring interactions to work with.
    """

    action_type: str
    category: str
    object_type: str
    id_prefix: str
    id_pool: tuple[str, ...] | None = None
    details: Callable[[random.Random], dict[str, Any]] | None = None
    metadata: Callable[[random.Random], dict[str, Any]] | None = None


# Cadence keywords accepted by routines and cross-app links.
CADENCES = ("daily", "weekday", "weekly", "monthly_end")


@dataclass(frozen=True)
class Routine:
    """Recurring single-module activity performed by a group of personas."""

    module: Module
    personas: tuple[Persona, ...]
    cadence: str
    hour: int
    activities: tuple[Activity, ...]
    minute: int = 0
    jitter: int = 25
    occurrences: tuple[int, int] = (1, 1)
    step_minutes: tuple[int, int] = (1, 6)
    device_mix: tuple[str, ...] = ("desktop",)


@dataclass(frozen=True)
class Step:
    """One end of a cross-application workflow link (actor supplied by the link)."""

    module: Module
    action_type: str
    category: str
    object_type: str
    id_prefix: str
    details: Callable[[random.Random], dict[str, Any]] | None = None


@dataclass(frozen=True)
class CrossAppLink:
    """A two-step workflow that crosses a product/module boundary.

    The two steps are performed by the **same persona** spanning two modules —
    the shape the engine's sequence detector recognizes, since it derives
    sequences from one user's own timeline. They are emitted within
    ``gap_minutes`` (kept under the detector's 30-minute window) on a weekly
    cadence, so the sequence recurs well past the 2-occurrence threshold and
    surfaces as a high-confidence cross-app pattern.

    ``hour`` defaults to the evening, after the day's routines, so the pair is
    temporally isolated in the user's timeline and produces exactly one clean
    cross-app transition per occurrence (no routine event falls within the
    30-minute window). ``share_object`` makes the follow-on step reference the
    first step's object, modeling an object that flows across systems.
    """

    name: str
    persona: Persona
    first: Step
    then: Step
    hour: int = 18
    gap_minutes: tuple[int, int] = (3, 15)
    probability: float = 0.85
    share_object: bool = False
    cadence: str = "weekly"


@dataclass(frozen=True)
class Shop:
    """A tenant and the full set of routines and cross-app links that drive it."""

    key: str
    tenant_id: str
    display_name: str
    routines: tuple[Routine, ...]
    cross_app: tuple[CrossAppLink, ...]
    country: str = "US"
    region: str = "CA"


# ---------------------------------------------------------------------------
# Event construction
# ---------------------------------------------------------------------------


@dataclass
class _EventFactory:
    """Builds schema-conformant event dicts and owns per-object-id counters."""

    tenant_id: str
    country: str
    region: str
    _counters: dict[str, int] = field(default_factory=dict)

    def next_object_id(self, prefix: str) -> str:
        """Return a stable, monotonically increasing id for ``prefix``."""
        value = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = value
        return f"{prefix}{value:06d}"

    def build(
        self,
        *,
        persona: Persona,
        module: Module,
        action_type: str,
        category: str,
        object_type: str,
        object_id: str,
        timestamp: datetime,
        action_metadata: dict[str, Any],
        object_details: dict[str, Any] | None,
        session_id: str,
        correlation_id: str | None,
        device: str,
    ) -> dict[str, Any]:
        """Assemble one universal-schema event dictionary."""
        actor: dict[str, Any] = {
            "nativeUserId": persona.native_user_id,
            "userIdType": persona.user_id_type,
            "roles": list(persona.roles),
        }
        action: dict[str, Any] = {"type": action_type, "category": category}
        metadata = {"suite": module.suite, "module": module.module, **action_metadata}
        action["metadata"] = metadata
        obj: dict[str, Any] = {"objectType": object_type, "objectId": object_id}
        if object_details is not None:
            obj["objectDetails"] = object_details
        context: dict[str, Any] = {
            "sessionId": session_id,
            "device": device,
            "geo": {"country": self.country, "region": self.region},
        }
        if correlation_id is not None:
            context["correlationId"] = correlation_id
        return {
            "schemaVersion": "1.0.0",
            "eventId": str(uuid.uuid4()),
            "tenantId": self.tenant_id,
            "applicationId": module.application_id,
            "applicationInstanceId": module.instance_id,
            "environment": "production",
            "eventTimestamp": timestamp.isoformat(),
            "actor": actor,
            "action": action,
            "object": obj,
            "source": {
                "connector": module.connector,
                "connectorVersion": module.connector_version,
            },
            "context": context,
        }


def _at(day: date, hour: int, minute: int, jitter: int, rng: random.Random) -> datetime:
    """Return a UTC datetime on ``day`` near ``hour:minute`` with random jitter."""
    base = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=timezone.utc)
    return base + timedelta(minutes=rng.randint(-jitter, jitter))


def _dates_for_cadence(cadence: str, start: date, end: date) -> list[date]:
    """Resolve a cadence keyword into the concrete dates it fires on."""
    if cadence == "daily":
        return list(_every_day(start, end))
    if cadence == "weekday":
        return list(workdays_between(start, end))
    if cadence == "weekly":
        return list(mondays_between(start, end))
    if cadence == "monthly_end":
        return list(month_end_workdays_between(start, end))
    raise ValueError(f"unknown cadence: {cadence!r}")


def _every_day(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _object_id_for(activity: Activity, factory: _EventFactory, rng: random.Random) -> str:
    """Pick a pooled id when the activity defines one, else mint a fresh id."""
    if activity.id_pool is not None:
        return rng.choice(activity.id_pool)
    return factory.next_object_id(activity.id_prefix)


def _emit_routine(
    routine: Routine, factory: _EventFactory, start: date, end: date, rng: random.Random
) -> list[dict[str, Any]]:
    """Expand one routine into events across its cadence dates and personas."""
    events: list[dict[str, Any]] = []
    for day in _dates_for_cadence(routine.cadence, start, end):
        for persona in routine.personas:
            for _ in range(rng.randint(*routine.occurrences)):
                session = f"sess-{uuid.uuid4().hex[:12]}"
                device = rng.choice(routine.device_mix)
                moment = _at(day, routine.hour, routine.minute, routine.jitter, rng)
                for activity in routine.activities:
                    events.append(
                        factory.build(
                            persona=persona,
                            module=routine.module,
                            action_type=activity.action_type,
                            category=activity.category,
                            object_type=activity.object_type,
                            object_id=_object_id_for(activity, factory, rng),
                            timestamp=moment,
                            action_metadata=activity.metadata(rng) if activity.metadata else {},
                            object_details=activity.details(rng) if activity.details else None,
                            session_id=session,
                            correlation_id=None,
                            device=device,
                        )
                    )
                    moment = moment + timedelta(minutes=rng.randint(*routine.step_minutes))
    return events


def _emit_cross_app(
    link: CrossAppLink, factory: _EventFactory, start: date, end: date, rng: random.Random
) -> list[dict[str, Any]]:
    """Expand one cross-app link into paired, trace-correlated events."""
    events: list[dict[str, Any]] = []
    for day in _dates_for_cadence(link.cadence, start, end):
        if rng.random() > link.probability:
            continue
        session = f"sess-{uuid.uuid4().hex[:12]}"
        correlation = f"corr-{uuid.uuid4().hex[:16]}"
        # Small jitter and an evening hour keep the pair isolated from the day's
        # routines, so exactly one clean cross-app transition is produced.
        first_time = _at(day, link.hour, 0, 8, rng)
        first_object = factory.next_object_id(link.first.id_prefix)
        events.append(
            factory.build(
                persona=link.persona,
                module=link.first.module,
                action_type=link.first.action_type,
                category=link.first.category,
                object_type=link.first.object_type,
                object_id=first_object,
                timestamp=first_time,
                action_metadata={"workflow": link.name},
                object_details=link.first.details(rng) if link.first.details else None,
                session_id=session,
                correlation_id=correlation,
                device="desktop",
            )
        )
        then_object = (
            first_object if link.share_object else factory.next_object_id(link.then.id_prefix)
        )
        then_time = first_time + timedelta(minutes=rng.randint(*link.gap_minutes))
        events.append(
            factory.build(
                persona=link.persona,
                module=link.then.module,
                action_type=link.then.action_type,
                category=link.then.category,
                object_type=link.then.object_type,
                object_id=then_object,
                timestamp=then_time,
                action_metadata={"workflow": link.name},
                object_details=link.then.details(rng) if link.then.details else None,
                session_id=session,
                correlation_id=correlation,
                device="desktop",
            )
        )
    return events


def generate_shop_events(
    shop: Shop, start: date, end: date, seed: int
) -> list[dict[str, Any]]:
    """Generate all events for ``shop`` in chronological order (deterministic)."""
    rng = random.Random(seed)
    factory = _EventFactory(tenant_id=shop.tenant_id, country=shop.country, region=shop.region)
    events: list[dict[str, Any]] = []
    for routine in shop.routines:
        events.extend(_emit_routine(routine, factory, start, end, rng))
    for link in shop.cross_app:
        events.extend(_emit_cross_app(link, factory, start, end, rng))
    events.sort(key=lambda event: str(event["eventTimestamp"]))
    return events


# ---------------------------------------------------------------------------
# Shared value helpers for realistic payloads
# ---------------------------------------------------------------------------


def money(rng: random.Random, low: float, high: float, currency: str = "USD") -> dict[str, Any]:
    """Return an ``{amount, currency}`` detail block with a rounded amount."""
    return {"amount": round(rng.uniform(low, high), 2), "currency": currency}


def pick(rng: random.Random, *values: str) -> str:
    """Return one of ``values`` at random (thin wrapper for readability)."""
    return rng.choice(values)
