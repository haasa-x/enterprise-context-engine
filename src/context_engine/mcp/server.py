"""MCP server exposing `resolve_user_intent` as a tool.

Wraps the same `IntentScorer` used by the REST API's `POST /v1/resolve-intent`
endpoint, so any MCP-aware client gets identical predictions with no custom
integration work. Run as:

    python -m context_engine.mcp.server --transport stdio
"""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import neo4j
import structlog
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from context_engine.config import Settings, get_settings
from context_engine.core.graph import GraphStore
from context_engine.prediction.keyword_table import KeywordTable
from context_engine.prediction.scorer import IntentScorer
from context_engine.profiler.factory import build_profile_generator
from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.pattern_detector import PatternDetector, UserPatterns

logger = structlog.get_logger(__name__)


@dataclass
class AppContext:
    """Resources shared across tool calls for the lifetime of the server."""

    graph_store: GraphStore
    scorer: IntentScorer
    pattern_detector: PatternDetector
    profile_generator: ProfileGenerator
    min_events: int


def _build_lifespan(
    settings: Settings,
) -> Callable[[FastMCP], AbstractAsyncContextManager[AppContext]]:
    """Build a lifespan context manager bound to a specific Settings instance."""

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
        driver = neo4j.AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
        )
        graph_store = GraphStore(driver, database=settings.neo4j_database)
        await graph_store.initialize()
        scorer = IntentScorer(graph_store, KeywordTable())

        try:
            yield AppContext(
                graph_store=graph_store,
                scorer=scorer,
                pattern_detector=PatternDetector(graph_store),
                profile_generator=build_profile_generator(
                    settings.profile_generator_backend
                ),
                min_events=settings.profile_min_events_to_generate,
            )
        finally:
            await graph_store.close()

    return lifespan


def create_server(settings: Settings | None = None) -> FastMCP:
    """Build the Context Engine MCP server, registering its tools."""
    settings = settings or get_settings()
    server = FastMCP(name="context-engine", lifespan=_build_lifespan(settings))

    @server.tool()
    async def resolve_user_intent(
        ctx: Context[ServerSession, AppContext, Any],
        tenant_id: str,
        user_id: str,
        trigger_text: str,
        max_predictions: int = 3,
    ) -> dict[str, Any]:
        """Predict the user's most likely next action given a trigger text.

        Args:
            tenant_id: Platform customer identifier, used for data isolation.
            user_id: The user's native identifier in the triggering application.
            trigger_text: Free text describing what prompted this lookup (e.g.
                an email subject or chat message).
            max_predictions: Maximum number of predictions to return.

        Returns:
            A dict with a "predictions" list. Each prediction has
            applicationId, actionType, objectType, suggestedFilters,
            confidence (0.0-1.0), and signals explaining the score.
        """
        app_context = ctx.request_context.lifespan_context
        predictions = await app_context.scorer.score(
            tenant_id=tenant_id,
            user_id=user_id,
            trigger_text=trigger_text,
            max_results=max_predictions,
        )
        return {"predictions": [p.model_dump(by_alias=True) for p in predictions]}

    @server.tool()
    async def get_user_profile(
        ctx: Context[ServerSession, AppContext, Any],
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Return a natural-language summary of the user's behavioural patterns.

        Args:
            tenant_id: Platform customer identifier, used for data isolation.
            user_id: The user's native identifier.

        Returns:
            A dict with the NLQ "profile" text, its "version" and
            "generatedAt", plus the detected dominant patterns. If the user
            has too few events, returns {"error": "insufficient_data", ...}.
        """
        app_context = ctx.request_context.lifespan_context
        patterns = await app_context.pattern_detector.detect(tenant_id, user_id)
        if patterns.total_events < app_context.min_events:
            return {
                "error": "insufficient_data",
                "detail": (
                    f"User has fewer than {app_context.min_events} events. "
                    f"Profile generation requires at least {app_context.min_events} events."
                ),
            }
        stored = await app_context.graph_store.get_user_profile(tenant_id, user_id)
        if stored is not None:
            generated_at = stored.get("profileGeneratedAt")
            return _profile_payload(
                user_id,
                stored["nlqProfile"],
                generated_at.isoformat() if generated_at else None,
                stored.get("profileVersion"),
                patterns,
            )
        profile_text = await app_context.profile_generator.generate(patterns)
        return _profile_payload(user_id, profile_text, None, None, patterns)

    return server


def _profile_payload(
    user_id: str,
    profile_text: str,
    generated_at: str | None,
    version: int | None,
    patterns: UserPatterns,
) -> dict[str, Any]:
    """Serialise a profile and its dominant patterns for an MCP client."""
    return {
        "userId": user_id,
        "profile": profile_text,
        "generatedAt": generated_at,
        "version": version,
        "totalEvents": patterns.total_events,
        "applications": {
            app: [pattern.action_type for pattern in app_patterns]
            for app, app_patterns in patterns.by_application.items()
        },
    }


mcp = create_server()


def main() -> None:
    """Parse CLI args and run the MCP server."""
    parser = argparse.ArgumentParser(description="Context Engine MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport to serve over (default: stdio)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
