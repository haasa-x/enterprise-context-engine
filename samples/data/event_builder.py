"""Constructs universal-schema event dictionaries from compact specifications."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from samples.data.catalog import Application, User


@dataclass
class EventSpec:
    """A compact description of a single action, expanded into a full event."""

    user: User
    app: Application
    action_type: str
    category: str
    object_type: str
    object_id: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None
    object_details: dict[str, Any] | None = None
    session_id: str | None = None
    device: str = "desktop"


@dataclass
class EventBuilder:
    """Expands :class:`EventSpec` values into schema-conformant event dicts."""

    tenant_id: str
    environment: str = "production"
    _rng: random.Random = field(default_factory=lambda: random.Random(1))

    def build(self, spec: EventSpec) -> dict[str, Any]:
        """Produce a fully-populated event dictionary for one action."""
        actor: dict[str, Any] = {
            "nativeUserId": spec.user.native_user_id,
            "userIdType": "email",
            "roles": list(spec.user.roles),
        }
        action: dict[str, Any] = {"type": spec.action_type, "category": spec.category}
        if spec.metadata is not None:
            action["metadata"] = spec.metadata
        obj: dict[str, Any] = {"objectType": spec.object_type, "objectId": spec.object_id}
        if spec.object_details is not None:
            obj["objectDetails"] = spec.object_details
        return {
            "schemaVersion": "1.0.0",
            "eventId": str(uuid.uuid4()),
            "tenantId": self.tenant_id,
            "applicationId": spec.app.application_id,
            "applicationInstanceId": spec.app.instance_id,
            "environment": self.environment,
            "eventTimestamp": spec.timestamp.isoformat(),
            "actor": actor,
            "action": action,
            "object": obj,
            "source": {
                "connector": spec.app.connector,
                "connectorVersion": spec.app.connector_version,
            },
            "context": {
                "sessionId": spec.session_id or f"sess-{uuid.uuid4().hex[:12]}",
                "device": spec.device,
            },
        }


def at_time(day: date, hour: int, minute: int, jitter_minutes: int, rng: random.Random) -> datetime:
    """Return a UTC datetime on ``day`` near ``hour:minute`` with random jitter."""
    base = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=timezone.utc)
    offset = rng.randint(-jitter_minutes, jitter_minutes)
    return base + timedelta(minutes=offset)
