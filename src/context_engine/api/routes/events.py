"""POST /v1/events and POST /v1/events/batch — event ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.responses import JSONResponse

from context_engine.api.dependencies import get_graph_store, get_schema_validator
from context_engine.api.metrics import events_ingested_total
from context_engine.core.graph import EventAlreadyExistsError, GraphStore
from context_engine.core.models import BatchEventResult, BatchIngestResponse, EventIngestResponse
from context_engine.core.schema_validator import EventValidationError, SchemaValidator

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["events"])

_MAX_BATCH_SIZE = 100
_MAX_BATCH_FAILURE_RATIO = 0.10


def _error_body(error: str, detail: str, request: Request) -> dict[str, str]:
    return {
        "error": error,
        "detail": detail,
        "requestId": getattr(request.state, "request_id", ""),
    }


async def _ingest_one(
    event: dict[str, Any], validator: SchemaValidator, graph_store: GraphStore
) -> None:
    """Validate an event and persist it, stamping the ingestion time on receipt."""
    validator.validate(event)
    event["ingestionTimestamp"] = datetime.now(timezone.utc).isoformat()
    await graph_store.write_event(event)
    events_ingested_total.inc()


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def ingest_event(
    request: Request,
    event: dict[str, Any] = Body(...),
    validator: SchemaValidator = Depends(get_schema_validator),
    graph_store: GraphStore = Depends(get_graph_store),
) -> JSONResponse:
    """Validate, store, and acknowledge a single event."""
    try:
        await _ingest_one(event, validator, graph_store)
    except EventValidationError as exc:
        logger.info("event.validation_failed", errors=exc.errors)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body("validation_error", "; ".join(exc.errors), request),
        )
    except EventAlreadyExistsError as exc:
        logger.info("event.duplicate", event_id=exc.event_id)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body("duplicate_event", str(exc), request),
        )

    response = EventIngestResponse(eventId=event["eventId"])
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response.model_dump(by_alias=True),
    )


@router.post("/events/batch")
async def ingest_events_batch(
    request: Request,
    body: dict[str, Any] = Body(...),
    validator: SchemaValidator = Depends(get_schema_validator),
    graph_store: GraphStore = Depends(get_graph_store),
) -> JSONResponse:
    """Ingest up to 100 events. Rejects the whole batch if more than 10% fail validation."""
    events = body.get("events", [])
    if len(events) > _MAX_BATCH_SIZE:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body(
                "batch_too_large", f"batch exceeds max size of {_MAX_BATCH_SIZE}", request
            ),
        )

    # Validate the whole batch before writing anything, so a batch that exceeds
    # the failure threshold is rejected atomically — nothing is persisted.
    validated, validation_failures = _validate_batch(events, validator)
    if events and validation_failures / len(events) > _MAX_BATCH_FAILURE_RATIO:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(
                "batch_rejected",
                "more than 10% of events in the batch failed validation",
                request,
            ),
        )

    results = await _persist_batch(validated, graph_store)
    accepted = sum(1 for result in results if result.status == "accepted")
    response = BatchIngestResponse(
        results=results,
        acceptedCount=accepted,
        rejectedCount=len(results) - accepted,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=response.model_dump(by_alias=True))


def _validate_batch(
    events: list[dict[str, Any]], validator: SchemaValidator
) -> tuple[list[tuple[dict[str, Any], str | None]], int]:
    """Validate every event without writing. Returns (event, error) pairs + failure count."""
    validated: list[tuple[dict[str, Any], str | None]] = []
    failures = 0
    for event in events:
        try:
            validator.validate(event)
            validated.append((event, None))
        except EventValidationError as exc:
            failures += 1
            validated.append((event, "; ".join(exc.errors)))
    return validated, failures


async def _persist_batch(
    validated: list[tuple[dict[str, Any], str | None]], graph_store: GraphStore
) -> list[BatchEventResult]:
    """Persist the events that passed validation; report per-event status."""
    results: list[BatchEventResult] = []
    for event, error in validated:
        if error is not None:
            results.append(
                BatchEventResult(eventId=event.get("eventId"), status="rejected", error=error)
            )
            continue
        results.append(await _persist_batch_event(event, graph_store))
    return results


async def _persist_batch_event(
    event: dict[str, Any], graph_store: GraphStore
) -> BatchEventResult:
    """Write one already-validated event, reporting a duplicate as rejected."""
    try:
        event["ingestionTimestamp"] = datetime.now(timezone.utc).isoformat()
        await graph_store.write_event(event)
        events_ingested_total.inc()
        return BatchEventResult(eventId=event.get("eventId"), status="accepted")
    except EventAlreadyExistsError as exc:
        return BatchEventResult(eventId=event.get("eventId"), status="rejected", error=str(exc))
