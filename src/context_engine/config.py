"""Application configuration, sourced entirely from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Context Engine service.

    All fields are overridable via environment variables prefixed with `CE_`,
    e.g. `CE_NEO4J_URI`.
    """

    model_config = SettingsConfigDict(env_prefix="CE_")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    log_level: str = "info"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "context-engine-dev"
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50

    prediction_history_days: int = 14
    prediction_max_results: int = 5

    schema_path: str = "schemas/event/v1.0.0/event.schema.json"
    max_future_seconds: int = 300

    events_rate_limit_per_minute: int = 1000
    intent_rate_limit_per_minute: int = 100

    profile_generator_backend: str = "template"  # "template" (default) or "llm"
    profile_schedule_interval_hours: int = 24
    profile_min_events_to_generate: int = 10

    # Comma-separated allowed origins for the admin UI (CORS). "*" allows any.
    cors_allow_origins: str = "*"


def get_settings() -> Settings:
    """Build a fresh Settings instance from the current environment."""
    return Settings()
