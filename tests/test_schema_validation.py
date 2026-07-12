"""Tests for context_engine.core.schema_validator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from context_engine.core.schema_validator import EventValidationError, SchemaValidator


@pytest.fixture
def validator(event_schema_path):
    return SchemaValidator(event_schema_path)


def test_valid_event_passes(validator, make_event):
    validator.validate(make_event())


def test_missing_required_field_rejected(validator, make_event):
    event = make_event()
    del event["tenantId"]
    with pytest.raises(EventValidationError) as exc_info:
        validator.validate(event)
    assert "tenantId" in str(exc_info.value)


def test_invalid_tenant_id_pattern_rejected(validator, make_event):
    event = make_event(tenantId="not a valid tenant!")
    with pytest.raises(EventValidationError):
        validator.validate(event)


def test_unknown_action_category_rejected(validator, make_event):
    event = make_event(action={"type": "do_thing", "category": "teleport"})
    with pytest.raises(EventValidationError):
        validator.validate(event)


def test_unknown_environment_rejected(validator, make_event):
    event = make_event(environment="prod")
    with pytest.raises(EventValidationError):
        validator.validate(event)


def test_additional_properties_rejected(validator, make_event):
    event = make_event()
    event["unexpectedField"] = "surprise"
    with pytest.raises(EventValidationError):
        validator.validate(event)


def test_future_timestamp_beyond_skew_rejected(validator, make_event):
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    event = make_event(eventTimestamp=future.isoformat())
    with pytest.raises(EventValidationError) as exc_info:
        validator.validate(event)
    assert "future" in str(exc_info.value)


def test_future_timestamp_within_skew_allowed(validator, make_event):
    near_future = datetime.now(timezone.utc) + timedelta(minutes=2)
    event = make_event(eventTimestamp=near_future.isoformat())
    validator.validate(event)


def test_all_errors_reported_not_just_first(validator, make_event):
    event = make_event()
    del event["tenantId"]
    del event["applicationId"]
    with pytest.raises(EventValidationError) as exc_info:
        validator.validate(event)
    assert len(exc_info.value.errors) >= 2


def test_optional_fields_accepted(validator, make_event):
    event = make_event(
        actor={
            "nativeUserId": "hr_manager001",
            "userIdType": "employee_id",
            "canonicalUserId": "canon-123",
            "roles": ["manager"],
        },
        context={
            "sessionId": "sess-1",
            "correlationId": "corr-1",
            "device": "desktop",
            "geo": {"country": "US", "region": "CA"},
        },
        onBehalfOf={"nativeUserId": "other_user", "userIdType": "email"},
    )
    validator.validate(event)


def test_schema_is_draft_2020_12(event_schema_path):
    import json

    schema = json.loads(event_schema_path.read_text())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
