"""Receives Jira webhook POSTs and forwards translated events to Context Engine."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Request

from connectors.jira.transformer import transform

logger = structlog.get_logger(__name__)


class JiraWebhookHandler:
    """Translates Jira webhook payloads and forwards them to the ingestion API."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        events_url: str,
        tenant_id: str,
        application_instance_id: str,
    ) -> None:
        """Bind this handler to an HTTP client, target ingestion URL, and tenant."""
        self._http_client = http_client
        self._events_url = events_url
        self._tenant_id = tenant_id
        self._application_instance_id = application_instance_id

    async def handle(self, payload: dict[str, Any]) -> dict[str, str]:
        """Transform a Jira webhook payload and forward it, if it maps to an event."""
        event = transform(payload, self._tenant_id, self._application_instance_id)
        if event is None:
            logger.info("jira.webhook_ignored", webhook_event=payload.get("webhookEvent"))
            return {"status": "ignored"}

        try:
            response = await self._http_client.post(
                self._events_url,
                json=event,
                headers={"X-Tenant-Id": self._tenant_id},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                return {"status": "duplicate", "eventId": event["eventId"]}
            raise

        return {"status": "forwarded", "eventId": event["eventId"]}


def build_router(handler: JiraWebhookHandler) -> APIRouter:
    """Build a FastAPI router exposing POST /webhooks/jira, bound to the given handler."""
    router = APIRouter(tags=["connectors"])

    @router.post("/webhooks/jira")
    async def receive_jira_webhook(request: Request) -> dict[str, str]:
        payload = await request.json()
        return await handler.handle(payload)

    return router
