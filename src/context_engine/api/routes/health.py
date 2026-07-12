"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from context_engine.api.dependencies import get_graph_store
from context_engine.core.graph import GraphStore

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    """Return 200 if the API process is running. Checks no dependencies."""
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(
    response: Response, graph_store: GraphStore = Depends(get_graph_store)
) -> dict[str, str]:
    """Return 200 if Neo4j is reachable, 503 otherwise."""
    try:
        await graph_store.verify_connectivity()
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ready"}
