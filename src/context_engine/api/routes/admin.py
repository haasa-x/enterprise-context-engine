"""Read-only admin endpoints backing the graph-viewer UI.

These expose tenant-scoped reads the admin UI composes into a graph view,
timeline, and event feed. Everything is derived from existing graph reads —
no new write surface, no cross-tenant access (the tenant comes from the
required ``X-Tenant-Id`` header).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query

from context_engine.api.dependencies import get_graph_store
from context_engine.core.graph import GraphStore

router = APIRouter(prefix="/v1/admin", tags=["admin"])

_ALL_USERS_WINDOW_DAYS = 3650
_DEFAULT_EVENT_WINDOW_DAYS = 180
_DEFAULT_EVENT_LIMIT = 500
_MAX_EVENT_LIMIT = 5000


@router.get("/users")
async def list_users(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    days: int = Query(_ALL_USERS_WINDOW_DAYS, ge=1),
    graph: GraphStore = Depends(get_graph_store),
) -> dict[str, list[str]]:
    """List native user ids seen in the tenant within the given window."""
    users = await graph.get_active_users(x_tenant_id, since_days=days)
    return {"users": users}


@router.get("/users/{user_id}/events")
async def list_user_events(
    user_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    days: int = Query(_DEFAULT_EVENT_WINDOW_DAYS, ge=1),
    limit: int = Query(_DEFAULT_EVENT_LIMIT, ge=1, le=_MAX_EVENT_LIMIT),
    graph: GraphStore = Depends(get_graph_store),
) -> dict[str, Any]:
    """Return a user's most recent events (bounded) for the graph and feed.

    ``limit`` caps how many of the most-recent events are returned so busy
    users don't overload the read or the client-side graph render. ``truncated``
    signals the window holds more events than were returned.
    """
    events = await graph.get_user_history(x_tenant_id, user_id, days=days, limit=limit)
    return {
        "userId": user_id,
        "events": events,
        "limit": limit,
        "truncated": len(events) >= limit,
    }
