"""JSON Schema validation for incoming events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from context_engine.core.exceptions import SchemaValidationError

# Backward-compatible alias: this module historically raised
# ``EventValidationError``. The canonical name now lives in ``core.exceptions``.
EventValidationError = SchemaValidationError


class SchemaValidator:
    """Validates events against the universal event JSON Schema."""

    def __init__(self, schema_path: str | Path, max_future_seconds: int = 300) -> None:
        """Load and compile the event schema from disk.

        Raises jsonschema.exceptions.SchemaError if the schema file itself
        is not a valid Draft 2020-12 document.
        """
        self._max_future_seconds = max_future_seconds
        schema = json.loads(Path(schema_path).read_text())
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(schema)

    def validate(self, event: dict[str, Any]) -> None:
        """Validate an event, raising EventValidationError with all failures found."""
        errors = [self._format_error(e) for e in self._validator.iter_errors(event)]

        timestamp_error = self._validate_timestamp(event)
        if timestamp_error is not None:
            errors.append(timestamp_error)

        if errors:
            raise SchemaValidationError(errors)

    def _validate_timestamp(self, event: dict[str, Any]) -> str | None:
        """Reject timestamps further in the future than the configured clock skew."""
        raw_timestamp = event.get("eventTimestamp")
        if not isinstance(raw_timestamp, str):
            return None
        try:
            event_time = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if event_time - now > timedelta(seconds=self._max_future_seconds):
            return f"eventTimestamp '{raw_timestamp}' is too far in the future"
        return None

    @staticmethod
    def _format_error(error: JSONSchemaValidationError) -> str:
        location = "/".join(str(part) for part in error.path) or "<root>"
        return f"{location}: {error.message}"
