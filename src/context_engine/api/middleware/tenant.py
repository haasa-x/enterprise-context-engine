"""Tenant validation middleware.

If a caller sends an `X-Tenant-Id` header, it must match the `tenantId`
declared in the request body for tenant-scoped routes; a mismatch is rejected
with 403 before the request reaches a route handler. The header is optional
in v1 (there is no authentication yet — see `docs/architecture.md` for the
integration point); once a gateway authenticates callers, it would set this
header from the verified identity rather than trusting the caller.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

_TENANT_SCOPED_PATHS = {"/v1/events", "/v1/events/batch", "/v1/resolve-intent"}


class TenantValidationMiddleware(BaseHTTPMiddleware):
    """Rejects requests where X-Tenant-Id does not match the body's declared tenantId(s)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Compare the X-Tenant-Id header against the body's tenantId, if both are present."""
        header_tenant_id = request.headers.get("x-tenant-id")
        if header_tenant_id is None or request.url.path not in _TENANT_SCOPED_PATHS:
            return await call_next(request)

        body = await request.body()
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return await call_next(request)

        body_tenant_ids = self._extract_tenant_ids(request.url.path, payload)
        if body_tenant_ids and any(tid != header_tenant_id for tid in body_tenant_ids):
            logger.warning("tenant.header_mismatch", path=request.url.path)
            return JSONResponse(
                status_code=403,
                content={
                    "error": "tenant_mismatch",
                    "detail": "X-Tenant-Id header does not match tenantId in request body",
                    "requestId": getattr(request.state, "request_id", ""),
                },
            )

        return await call_next(request)

    @staticmethod
    def _extract_tenant_ids(path: str, payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            return []
        if path == "/v1/events/batch":
            events = payload.get("events") or []
            return [e["tenantId"] for e in events if isinstance(e, dict) and "tenantId" in e]
        tenant_id = payload.get("tenantId")
        return [tenant_id] if tenant_id else []
