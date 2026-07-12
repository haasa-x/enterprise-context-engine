"""Tests for context_engine.core.models."""

from __future__ import annotations

from context_engine.core.models import (
    Event,
    Prediction,
    ResolveIntentRequest,
    ResolveIntentResponse,
)


def test_event_parses_from_wire_format(make_event):
    event = Event.model_validate(make_event())
    assert event.tenant_id == "acme-corp"
    assert event.actor.native_user_id == "hr_manager001"
    assert event.action.category.value == "update"


def test_event_round_trips_by_alias(make_event):
    payload = make_event()
    event = Event.model_validate(payload)
    dumped = event.model_dump(by_alias=True, exclude_none=True)
    assert dumped["tenantId"] == payload["tenantId"]
    assert dumped["actor"]["nativeUserId"] == payload["actor"]["nativeUserId"]


def test_resolve_intent_request_defaults():
    req = ResolveIntentRequest.model_validate(
        {
            "tenantId": "acme-corp",
            "userId": "hr_manager001",
            "userIdType": "employee_id",
        }
    )
    assert req.max_predictions == 3
    assert req.trigger is None


def test_resolve_intent_request_with_trigger():
    req = ResolveIntentRequest.model_validate(
        {
            "tenantId": "acme-corp",
            "userId": "hr_manager001",
            "userIdType": "employee_id",
            "trigger": {
                "source": "email",
                "text": "Sprint Q3 2024 closes tomorrow",
                "timestamp": "2024-08-18T08:00:00Z",
            },
            "maxPredictions": 5,
        }
    )
    assert req.trigger is not None
    assert req.trigger.text == "Sprint Q3 2024 closes tomorrow"
    assert req.max_predictions == 5


def test_prediction_confidence_bounds_by_alias():
    prediction = Prediction.model_validate(
        {
            "applicationId": "jira",
            "actionType": "view_sprint_board",
            "objectType": "sprint",
            "confidence": 0.87,
            "signals": [{"type": "keyword_match", "detail": "sprint closing"}],
        }
    )
    dumped = prediction.model_dump(by_alias=True)
    assert dumped["applicationId"] == "jira"
    assert dumped["confidence"] == 0.87


def test_resolve_intent_response_serialization():
    response = ResolveIntentResponse.model_validate(
        {
            "predictions": [],
            "userId": "hr_manager001",
            "resolvedAt": "2024-08-18T08:00:01Z",
        }
    )
    dumped = response.model_dump(by_alias=True)
    assert dumped["userId"] == "hr_manager001"
