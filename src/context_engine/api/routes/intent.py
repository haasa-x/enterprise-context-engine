"""POST /v1/resolve-intent — rules-based user intent resolution."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from context_engine.api.dependencies import get_intent_scorer, get_settings
from context_engine.api.metrics import resolve_intent_duration_seconds, resolve_intent_total
from context_engine.config import Settings
from context_engine.core.models import ResolveIntentRequest, ResolveIntentResponse
from context_engine.prediction.scorer import IntentScorer

router = APIRouter(prefix="/v1", tags=["intent"])


@router.post("/resolve-intent", response_model=ResolveIntentResponse, response_model_by_alias=True)
async def resolve_intent(
    body: ResolveIntentRequest,
    scorer: IntentScorer = Depends(get_intent_scorer),
    settings: Settings = Depends(get_settings),
) -> ResolveIntentResponse:
    """Predict what a user is most likely trying to do, given a trigger."""
    resolve_intent_total.inc()
    trigger_text = body.trigger.text if body.trigger else None

    start = time.perf_counter()
    predictions = await scorer.score(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        trigger_text=trigger_text,
        max_results=body.max_predictions,
        history_days=settings.prediction_history_days,
    )
    resolve_intent_duration_seconds.observe(time.perf_counter() - start)

    return ResolveIntentResponse(
        predictions=predictions,
        userId=body.user_id,
        resolvedAt=datetime.now(timezone.utc),
    )
