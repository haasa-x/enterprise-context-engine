"""In-memory per-tenant rate limiting middleware.

Counts requests in fixed one-minute windows, keyed by tenant and endpoint
class (ingestion vs. intent resolution). This is intentionally process-local
— no Redis dependency — which is sufficient for a single API instance; a
horizontally scaled deployment would need a shared store instead.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

_EVENTS_PATHS = {"/v1/events", "/v1/events/batch"}
_INTENT_PATHS = {"/v1/resolve-intent"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces per-tenant requests-per-minute limits for ingestion and query endpoints."""

    def __init__(self, app: ASGIApp, events_limit: int = 1000, intent_limit: int = 100) -> None:
        """Configure per-minute limits for the events and intent-resolution endpoint classes."""
        super().__init__(app)
        self._events_limit = events_limit
        self._intent_limit = intent_limit
        self._counts: dict[tuple[str, int], int] = defaultdict(int)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Reject with 429 once a tenant exceeds its per-minute request budget."""
        limit, bucket = self._bucket_for(request.url.path)
        if limit is None:
            return await call_next(request)

        tenant_id = await self._extract_tenant_id(request, bucket)
        if tenant_id is None:
            return await call_next(request)

        window = int(time.time() // 60)
        key = (f"{tenant_id}:{bucket}", window)
        self._prune(window)
        self._counts[key] += 1

        if self._counts[key] > limit:
            logger.warning("rate_limit.exceeded", tenant_id=tenant_id, bucket=bucket)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "detail": f"rate limit exceeded for {bucket}",
                    "request_id": getattr(request.state, "request_id", ""),
                },
                headers={"Retry-After": "60"},
            )

        return await call_next(request)

    @staticmethod
    async def _extract_tenant_id(request: Request, bucket: str) -> str | None:
        header_tenant_id = request.headers.get("x-tenant-id")
        if header_tenant_id:
            return header_tenant_id

        body = await request.body()
        try:
            payload: Any = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None

        if bucket == "events" and request.url.path == "/v1/events/batch":
            events = payload.get("events") or []
            first = events[0] if events and isinstance(events[0], dict) else {}
            tenant_id = first.get("tenantId")
        else:
            tenant_id = payload.get("tenantId")
        return tenant_id if isinstance(tenant_id, str) else None

    def _bucket_for(self, path: str) -> tuple[int | None, str]:
        if path in _EVENTS_PATHS:
            return self._events_limit, "events"
        if path in _INTENT_PATHS:
            return self._intent_limit, "intent"
        return None, ""

    def _prune(self, current_window: int) -> None:
        stale_keys = [key for key in self._counts if key[1] != current_window]
        for key in stale_keys:
            del self._counts[key]
