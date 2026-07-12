"""Dependency injection providers for the API layer.

Shared singletons (the Neo4j-backed GraphStore, the compiled SchemaValidator,
and Settings) are created once at application startup and attached to
`app.state`; these functions just hand them to route handlers.
"""

from __future__ import annotations

from fastapi import Request

from context_engine.config import Settings
from context_engine.core.graph import GraphStore
from context_engine.core.schema_validator import SchemaValidator
from context_engine.prediction.scorer import IntentScorer
from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.pattern_detector import PatternDetector


def get_settings(request: Request) -> Settings:
    """Return the Settings instance attached to the app at startup."""
    settings: Settings = request.app.state.settings
    return settings


def get_graph_store(request: Request) -> GraphStore:
    """Return the shared GraphStore instance attached to the app at startup."""
    graph_store: GraphStore = request.app.state.graph_store
    return graph_store


def get_schema_validator(request: Request) -> SchemaValidator:
    """Return the shared SchemaValidator instance attached to the app at startup."""
    validator: SchemaValidator = request.app.state.schema_validator
    return validator


def get_intent_scorer(request: Request) -> IntentScorer:
    """Return the shared IntentScorer instance attached to the app at startup."""
    scorer: IntentScorer = request.app.state.intent_scorer
    return scorer


def get_pattern_detector(request: Request) -> PatternDetector:
    """Return the shared PatternDetector instance attached to the app at startup."""
    detector: PatternDetector = request.app.state.pattern_detector
    return detector


def get_profile_generator(request: Request) -> ProfileGenerator:
    """Return the shared ProfileGenerator instance attached to the app at startup."""
    generator: ProfileGenerator = request.app.state.profile_generator
    return generator
