"""Pydantic models for events, predictions, and API request/response bodies.

Incoming events are authoritatively validated against the JSON Schema in
`schemas/event/v1.0.0/event.schema.json` via `SchemaValidator`, not by the
`Event` model below. `Event` exists so internal code (connectors, the SDK,
tests) can build and pass around events with type checking rather than bare
dicts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserIdType(str, Enum):
    """How an actor's identifier should be interpreted."""

    EMAIL = "email"
    SSO_SUBJECT = "sso_subject"
    APP_NATIVE_ID = "app_native_id"
    EMPLOYEE_ID = "employee_id"


class ActionCategory(str, Enum):
    """Normalized verb for an action, independent of the source application."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    NAVIGATE = "navigate"
    SEARCH = "search"


class Environment(str, Enum):
    """Deployment environment an event originated from."""

    PRODUCTION = "production"
    SANDBOX = "sandbox"
    STAGING = "staging"
    TEST = "test"


class Device(str, Enum):
    """Coarse device class for event context."""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class Actor(BaseModel):
    """Who performed the action."""

    model_config = ConfigDict(extra="forbid")

    native_user_id: str = Field(alias="nativeUserId")
    user_id_type: UserIdType = Field(alias="userIdType")
    canonical_user_id: str | None = Field(default=None, alias="canonicalUserId")
    roles: list[str] | None = None


class OnBehalfOf(BaseModel):
    """Set when the actor performed the action on another user's behalf."""

    model_config = ConfigDict(extra="forbid")

    native_user_id: str = Field(alias="nativeUserId")
    user_id_type: UserIdType = Field(alias="userIdType")


class Action(BaseModel):
    """What was done."""

    model_config = ConfigDict(extra="forbid")

    type: str
    category: ActionCategory
    metadata: dict[str, Any] | None = None


class BusinessObjectRef(BaseModel):
    """What was acted upon."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    object_type: str = Field(alias="objectType")
    object_id: str = Field(alias="objectId")
    object_details: dict[str, Any] | None = Field(default=None, alias="objectDetails")


class EventSource(BaseModel):
    """Which connector or SDK emitted this event."""

    model_config = ConfigDict(extra="forbid")

    connector: str
    connector_version: str = Field(alias="connectorVersion")


class Geo(BaseModel):
    """Coarse location context."""

    model_config = ConfigDict(extra="forbid")

    country: str | None = None
    region: str | None = None


class EventContext(BaseModel):
    """Optional grouping and device/location context for an event."""

    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, alias="sessionId")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    device: Device | None = None
    geo: Geo | None = None


class Event(BaseModel):
    """The universal event contract. Mirrors `schemas/event/v1.0.0/event.schema.json`."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion", default="1.0.0")
    event_id: str = Field(alias="eventId")
    tenant_id: str = Field(alias="tenantId")
    application_id: str = Field(alias="applicationId")
    application_instance_id: str = Field(alias="applicationInstanceId")
    environment: Environment
    event_timestamp: datetime = Field(alias="eventTimestamp")
    ingestion_timestamp: datetime | None = Field(default=None, alias="ingestionTimestamp")
    actor: Actor
    on_behalf_of: OnBehalfOf | None = Field(default=None, alias="onBehalfOf")
    action: Action
    object: BusinessObjectRef
    source: EventSource
    context: EventContext | None = None


class EventIngestResponse(BaseModel):
    """Response for a single successfully ingested event."""

    event_id: str = Field(alias="eventId")
    status: str = "accepted"

    model_config = ConfigDict(populate_by_name=True)


class BatchEventResult(BaseModel):
    """Per-event outcome within a batch ingestion request."""

    event_id: str | None = Field(default=None, alias="eventId")
    status: str
    error: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class BatchIngestResponse(BaseModel):
    """Response for a batch event ingestion request."""

    results: list[BatchEventResult]
    accepted_count: int = Field(alias="acceptedCount")
    rejected_count: int = Field(alias="rejectedCount")

    model_config = ConfigDict(populate_by_name=True)


class Trigger(BaseModel):
    """The signal that prompted an intent resolution request."""

    model_config = ConfigDict(extra="forbid")

    source: str
    text: str | None = None
    timestamp: datetime | None = None


class ResolveIntentRequest(BaseModel):
    """Request body for POST /v1/resolve-intent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tenant_id: str = Field(alias="tenantId")
    user_id: str = Field(alias="userId")
    user_id_type: UserIdType = Field(alias="userIdType")
    trigger: Trigger | None = None
    max_predictions: int = Field(default=3, alias="maxPredictions", ge=1, le=20)


class Signal(BaseModel):
    """One piece of evidence backing a prediction's confidence score."""

    type: str
    detail: str


class Prediction(BaseModel):
    """A single predicted user intent."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(alias="applicationId")
    action_type: str = Field(alias="actionType")
    object_type: str = Field(alias="objectType")
    suggested_filters: dict[str, Any] = Field(default_factory=dict, alias="suggestedFilters")
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[Signal] = Field(default_factory=list)


class ResolveIntentResponse(BaseModel):
    """Response body for POST /v1/resolve-intent."""

    model_config = ConfigDict(populate_by_name=True)

    predictions: list[Prediction]
    user_id: str = Field(alias="userId")
    resolved_at: datetime = Field(alias="resolvedAt")


class ActionPatternOut(BaseModel):
    """A recurring action within one application, for the profile response."""

    model_config = ConfigDict(populate_by_name=True)

    action_type: str = Field(alias="actionType")
    frequency: str
    typical_time: str = Field(alias="typicalTime")
    count_in_period: int = Field(alias="countInPeriod")
    confidence: float


class SequencePatternOut(BaseModel):
    """A cross-application action sequence, for the profile response."""

    model_config = ConfigDict(populate_by_name=True)

    trigger_app: str = Field(alias="triggerApp")
    trigger_action: str = Field(alias="triggerAction")
    follow_app: str = Field(alias="followApp")
    follow_action: str = Field(alias="followAction")
    typical_gap: str = Field(alias="typicalGap")
    confidence: float


class ActiveObjectOut(BaseModel):
    """A currently-active business object, for the profile response."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(alias="applicationId")
    object_type: str = Field(alias="objectType")
    object_id: str = Field(alias="objectId")
    interaction_count: int = Field(alias="interactionCount")
    last_activity: datetime = Field(alias="lastActivity")


class UserProfileResponse(BaseModel):
    """Response body for GET /v1/users/{userId}/profile."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    profile: str
    generated_at: datetime | None = Field(default=None, alias="generatedAt")
    version: int | None = None
    total_events: int = Field(alias="totalEvents")
    by_application: dict[str, list[ActionPatternOut]] = Field(
        default_factory=dict, alias="byApplication"
    )
    cross_app_sequences: list[SequencePatternOut] = Field(
        default_factory=list, alias="crossAppSequences"
    )
    active_objects: list[ActiveObjectOut] = Field(
        default_factory=list, alias="activeObjects"
    )


class ErrorResponse(BaseModel):
    """Structured error body returned for all failed requests."""

    error: str
    detail: str
    request_id: str = Field(alias="requestId")

    model_config = ConfigDict(populate_by_name=True)
