"""Tests for the SAP / Salesforce / Oracle shop seed generators.

These guard three properties the demo relies on:

1. every generated event validates against the universal event JSON Schema
   (the same schema the ingestion API enforces),
2. generation is deterministic for a fixed seed, and
3. the profiler's pattern detector actually finds the seeded cross-application
   sequences and active objects.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from context_engine.core.schema_validator import SchemaValidator
from context_engine.profiler.pattern_detector import PatternDetector
from samples.shops import oracle, salesforce, sap
from samples.shops.framework import Shop, generate_shop_events

_START = date(2026, 1, 12)
_END = date(2026, 7, 11)
_SEED = 42
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas/event/v1.0.0/event.schema.json"

_SHOPS = (sap.SHOP, salesforce.SHOP, oracle.SHOP)


@pytest.fixture(scope="module")
def validator() -> SchemaValidator:
    # The seed data is historical/static, so disable the future-clock guard.
    return SchemaValidator(_SCHEMA_PATH, max_future_seconds=10**9)


def _events(shop: Shop) -> list[dict[str, Any]]:
    return generate_shop_events(shop, _START, _END, _SEED)


def _rows(events: list[dict[str, Any]], user_id: str) -> list[dict[str, Any]]:
    """Flatten events into the row shape the pattern detector consumes."""
    return [
        {
            "applicationId": e["applicationId"],
            "actionType": e["action"]["type"],
            "objectType": e["object"]["objectType"],
            "objectId": e["object"]["objectId"],
            "eventTimestamp": datetime.fromisoformat(e["eventTimestamp"]),
            "metadata": e["action"].get("metadata"),
        }
        for e in events
        if e["actor"]["nativeUserId"] == user_id
    ]


@pytest.mark.parametrize("shop", _SHOPS, ids=lambda s: s.key)
def test_every_event_is_schema_valid(shop: Shop, validator: SchemaValidator) -> None:
    events = _events(shop)
    assert events, "generator produced no events"
    for event in events:
        validator.validate(event)  # raises on any violation


@pytest.mark.parametrize("shop", _SHOPS, ids=lambda s: s.key)
def test_generation_is_deterministic(shop: Shop) -> None:
    first = generate_shop_events(shop, _START, _END, _SEED)
    second = generate_shop_events(shop, _START, _END, _SEED)
    assert [e["eventTimestamp"] for e in first] == [e["eventTimestamp"] for e in second]
    assert len(first) == len(second)


@pytest.mark.parametrize("shop", _SHOPS, ids=lambda s: s.key)
def test_all_products_and_modules_are_represented(shop: Shop) -> None:
    events = _events(shop)
    suites = {e["action"]["metadata"]["suite"] for e in events}
    modules = {e["action"]["metadata"]["module"] for e in events}
    apps = {e["applicationId"] for e in events}
    # Every shop spans multiple products, many modules, and module-grain apps.
    assert len(suites) >= 4
    assert len(modules) >= 10
    assert len(apps) >= 10


@pytest.mark.parametrize("shop", _SHOPS, ids=lambda s: s.key)
def test_identity_types_are_product_appropriate(shop: Shop) -> None:
    events = _events(shop)
    id_types = {e["actor"]["userIdType"] for e in events}
    allowed = {"email", "sso_subject", "app_native_id", "employee_id"}
    assert id_types <= allowed
    assert id_types, "expected at least one identity type"


@pytest.mark.parametrize("shop", _SHOPS, ids=lambda s: s.key)
def test_cross_app_sequences_are_detected(shop: Shop) -> None:
    events = _events(shop)
    detector = PatternDetector.__new__(PatternDetector)  # pure detection, no graph
    user_ids = {e["actor"]["nativeUserId"] for e in events}

    detected: set[tuple[str, str]] = set()
    for user_id in user_ids:
        for seq in detector._detect_sequences(_rows(events, user_id)):
            detected.add((seq.trigger_app, seq.follow_app))

    # Each shop defines several single-persona cross-app links; they must surface.
    expected = {
        (link.first.module.application_id, link.then.module.application_id)
        for link in shop.cross_app
    }
    missing = expected - detected
    assert not missing, f"cross-app sequences not detected: {missing}"


@pytest.mark.parametrize("shop", _SHOPS, ids=lambda s: s.key)
def test_active_objects_are_detected(shop: Shop) -> None:
    events = _events(shop)
    detector = PatternDetector.__new__(PatternDetector)
    user_ids = {e["actor"]["nativeUserId"] for e in events}
    total_active = sum(
        len(detector._detect_active_objects(_rows(events, user_id))) for user_id in user_ids
    )
    assert total_active > 0, "expected pooled objects to surface as active objects"
