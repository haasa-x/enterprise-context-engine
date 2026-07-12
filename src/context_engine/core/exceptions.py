"""Custom domain exceptions for the Context Engine.

Every error the platform raises intentionally derives from
:class:`ContextEngineError`, so callers can catch the whole domain with a
single ``except`` while still discriminating specific failures. The API layer
maps these to structured JSON error responses; nothing here carries a stack
trace across the process boundary.
"""

from __future__ import annotations


class ContextEngineError(Exception):
    """Base class for every Context Engine domain error."""


class SchemaValidationError(ContextEngineError):
    """Raised when an event fails schema or semantic validation.

    Carries every failure found, not just the first, so callers can report all
    of them back to the client in a single response.
    """

    def __init__(self, errors: list[str]) -> None:
        """Store the list of human-readable validation error messages."""
        self.errors = errors
        super().__init__("; ".join(errors))


class DuplicateEventError(ContextEngineError):
    """Raised when an event with an already-seen ``eventId`` is written again."""

    def __init__(self, event_id: str) -> None:
        """Store the offending eventId."""
        self.event_id = event_id
        super().__init__(f"event '{event_id}' already exists")


class TenantMismatchError(ContextEngineError):
    """Raised when the ``X-Tenant-Id`` header disagrees with the body ``tenantId``."""


class UserNotFoundError(ContextEngineError):
    """Raised when a requested user does not exist within the tenant's graph."""

    def __init__(self, user_id: str) -> None:
        """Store the missing user id."""
        self.user_id = user_id
        super().__init__(f"user '{user_id}' not found")


class InsufficientDataError(ContextEngineError):
    """Raised when a user has too few events for a profile to be generated."""

    def __init__(self, user_id: str, event_count: int, minimum: int) -> None:
        """Store the user id, how many events exist, and how many are required."""
        self.user_id = user_id
        self.event_count = event_count
        self.minimum = minimum
        super().__init__(
            f"user '{user_id}' has {event_count} events; "
            f"profile generation requires at least {minimum}"
        )
