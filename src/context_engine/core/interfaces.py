"""Narrow capability interfaces for the graph store (Interface Segregation).

Consumers depend on the slice of behaviour they actually use rather than the
full :class:`~context_engine.core.graph.GraphStore`. ``GraphStore`` satisfies
all of these structurally — they are :class:`typing.Protocol` types, so no
explicit inheritance is required and no cyclic import is introduced.
"""

from __future__ import annotations

from typing import Any, Protocol


class HistoryReader(Protocol):
    """Read access to a user's action history, used by the prediction scorer."""

    async def get_user_history(
        self, tenant_id: str, user_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        """Return a user's recent PERFORMED events, most recent first."""
        ...

    async def get_canonical_user_id(self, tenant_id: str, user_id: str) -> str | None:
        """Return the resolved cross-app identity for a native user id, if any."""
        ...

    async def get_cross_app_history(
        self, tenant_id: str, canonical_user_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        """Return PERFORMED events across all applications for a resolved identity."""
        ...


class EventWriter(Protocol):
    """Write access for ingesting events, used by the ingestion routes."""

    async def write_event(self, event: dict[str, Any]) -> None:
        """Persist a single validated event into the graph."""
        ...


class PatternReader(Protocol):
    """Read access used by the profiler's pattern detector."""

    async def get_user_history(
        self, tenant_id: str, user_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        """Return a user's PERFORMED events within the given window."""
        ...

    async def get_user_event_count(self, tenant_id: str, user_id: str) -> int:
        """Return the total number of PERFORMED events for a user."""
        ...


class ProfileStore(Protocol):
    """Read/write access to generated profiles, used by the profiler and API."""

    async def get_active_users(self, tenant_id: str, since_days: int = 7) -> list[str]:
        """Return native user ids seen within the recent window."""
        ...

    async def update_user_profile(
        self, tenant_id: str, user_id: str, profile_text: str, version: int
    ) -> None:
        """Store the generated NLQ profile text and version for a user."""
        ...

    async def get_user_profile(self, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        """Return the stored NLQ profile for a user, or None if not generated."""
        ...
