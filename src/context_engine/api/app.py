"""FastAPI application factory."""

from __future__ import annotations

import logging
import sys
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import neo4j
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j.exceptions import ServiceUnavailable
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from context_engine.api.middleware.rate_limit import RateLimitMiddleware
from context_engine.api.middleware.tenant import TenantValidationMiddleware
from context_engine.api.routes import admin, events, health, intent, profile
from context_engine.config import Settings, get_settings
from context_engine.core.exceptions import InsufficientDataError
from context_engine.core.graph import GraphStore
from context_engine.core.schema_validator import SchemaValidator
from context_engine.prediction.keyword_table import KeywordTable
from context_engine.prediction.scorer import IntentScorer
from context_engine.profiler.factory import build_profile_generator
from context_engine.profiler.pattern_detector import PatternDetector

logger = structlog.get_logger(__name__)


def configure_logging(log_level: str) -> None:
    """Configure structlog (and stdlib logging) to emit structured JSON lines."""
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=log_level.upper()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns a request id to every request, for correlation across log lines."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Bind a fresh request id to the request and to the structlog context."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


def _resolve_schema_path(schema_path: str) -> Path:
    path = Path(schema_path)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _make_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build a lifespan context manager bound to a specific Settings instance."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await _startup(app, settings)
        yield
        await app.state.graph_store.close()
        logger.info("app.shutdown_complete")

    return lifespan


async def _startup(app: FastAPI, settings: Settings) -> None:
    """Create shared Neo4j-backed services on startup."""
    configure_logging(settings.log_level)

    driver = neo4j.AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        max_connection_pool_size=settings.neo4j_max_connection_pool_size,
    )
    graph_store = GraphStore(driver, database=settings.neo4j_database)
    await graph_store.initialize()

    validator = SchemaValidator(
        _resolve_schema_path(settings.schema_path),
        max_future_seconds=settings.max_future_seconds,
    )
    scorer = IntentScorer(graph_store, KeywordTable())

    app.state.settings = settings
    app.state.graph_store = graph_store
    app.state.schema_validator = validator
    app.state.intent_scorer = scorer
    app.state.pattern_detector = PatternDetector(graph_store)
    app.state.profile_generator = build_profile_generator(settings.profile_generator_backend)

    logger.info("app.startup_complete")


def _error_content(error: str, detail: str, request: Request) -> dict[str, str]:
    return {
        "error": error,
        "detail": detail,
        "requestId": getattr(request.state, "request_id", ""),
    }


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _on_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_content("validation_error", errors, request),
        )

    @app.exception_handler(InsufficientDataError)
    async def _on_insufficient_data(
        request: Request, exc: InsufficientDataError
    ) -> JSONResponse:
        detail = (
            f"User has fewer than {exc.minimum} events. Profile generation "
            f"requires at least {exc.minimum} events."
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_content("insufficient_data", detail, request),
        )

    @app.exception_handler(ServiceUnavailable)
    async def _on_neo4j_unavailable(request: Request, exc: ServiceUnavailable) -> JSONResponse:
        logger.error("neo4j.unavailable", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_content("service_unavailable", "graph database is unreachable", request),
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(Exception)
    async def _on_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("request.unhandled_exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_content("internal_error", "an unexpected error occurred", request),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the Context Engine FastAPI application."""
    settings = settings or get_settings()
    app = FastAPI(title="Context Engine", version="0.1.0", lifespan=_make_lifespan(settings))

    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(intent.router)
    app.include_router(profile.router)
    app.include_router(admin.router)
    app.mount("/metrics", make_asgi_app())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(",")],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantValidationMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        events_limit=settings.events_rate_limit_per_minute,
        intent_limit=settings.intent_rate_limit_per_minute,
    )
    app.add_middleware(RequestIdMiddleware)

    _register_exception_handlers(app)
    return app


app = create_app()
