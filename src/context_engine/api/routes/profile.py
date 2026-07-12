"""GET /v1/users/{userId}/profile — the pre-generated behavioural profile.

The tenant is taken from the required ``X-Tenant-Id`` header (this route has no
body). When a user has too few events for a profile, the route responds 404
with ``{"error": "insufficient_data", ...}``.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header

from context_engine.api.dependencies import (
    get_graph_store,
    get_pattern_detector,
    get_profile_generator,
    get_settings,
)
from context_engine.config import Settings
from context_engine.core.exceptions import InsufficientDataError
from context_engine.core.graph import GraphStore
from context_engine.core.models import (
    ActionPatternOut,
    ActiveObjectOut,
    SequencePatternOut,
    UserProfileResponse,
)
from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.pattern_detector import PatternDetector, UserPatterns

router = APIRouter(prefix="/v1", tags=["profile"])


@router.get(
    "/users/{user_id}/profile",
    response_model=UserProfileResponse,
    response_model_by_alias=True,
)
async def get_user_profile(
    user_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    graph: GraphStore = Depends(get_graph_store),
    detector: PatternDetector = Depends(get_pattern_detector),
    generator: ProfileGenerator = Depends(get_profile_generator),
    settings: Settings = Depends(get_settings),
) -> UserProfileResponse:
    """Return the user's NLQ profile plus their dominant behavioural patterns."""
    patterns = await detector.detect(x_tenant_id, user_id)
    if patterns.total_events < settings.profile_min_events_to_generate:
        raise InsufficientDataError(
            user_id, patterns.total_events, settings.profile_min_events_to_generate
        )

    stored = await graph.get_user_profile(x_tenant_id, user_id)
    if stored is not None:
        profile_text = stored["nlqProfile"]
        generated_at = stored.get("profileGeneratedAt")
        version = stored.get("profileVersion")
    else:
        profile_text = await generator.generate(patterns)
        generated_at = None
        version = None

    return _to_response(user_id, profile_text, generated_at, version, patterns)


def _to_response(
    user_id: str,
    profile_text: str,
    generated_at: datetime | None,
    version: int | None,
    patterns: UserPatterns,
) -> UserProfileResponse:
    return UserProfileResponse(
        userId=user_id,
        profile=profile_text,
        generatedAt=generated_at,
        version=version,
        totalEvents=patterns.total_events,
        byApplication={
            app: [
                ActionPatternOut(
                    actionType=pattern.action_type,
                    frequency=pattern.frequency,
                    typicalTime=pattern.typical_time,
                    countInPeriod=pattern.count_in_period,
                    confidence=pattern.confidence,
                )
                for pattern in app_patterns
            ]
            for app, app_patterns in patterns.by_application.items()
        },
        crossAppSequences=[
            SequencePatternOut(
                triggerApp=sequence.trigger_app,
                triggerAction=sequence.trigger_action,
                followApp=sequence.follow_app,
                followAction=sequence.follow_action,
                typicalGap=sequence.typical_gap,
                confidence=sequence.confidence,
            )
            for sequence in patterns.cross_app_sequences
        ],
        activeObjects=[
            ActiveObjectOut(
                applicationId=obj.application_id,
                objectType=obj.object_type,
                objectId=obj.object_id,
                interactionCount=obj.interaction_count,
                lastActivity=obj.last_activity,
            )
            for obj in patterns.active_objects
        ],
    )
