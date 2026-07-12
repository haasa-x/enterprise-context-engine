"""Shared pytest fixtures for the Context Engine test suite."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import neo4j
import pytest
import pytest_asyncio
from testcontainers.neo4j import Neo4jContainer

from context_engine.api.app import create_app
from context_engine.config import Settings
from context_engine.core.graph import GraphStore

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_SCHEMA_PATH = REPO_ROOT / "schemas" / "event" / "v1.0.0" / "event.schema.json"

NEO4J_IMAGE = "neo4j:5-community"
NEO4J_PASSWORD = "context-engine-test"


@pytest.fixture(scope="session")
def neo4j_container() -> Iterator[Neo4jContainer]:
    """A disposable Neo4j instance shared across the whole test session."""
    with Neo4jContainer(image=NEO4J_IMAGE, password=NEO4J_PASSWORD) as container:
        yield container


@pytest_asyncio.fixture(scope="session")
async def graph_store(neo4j_container: Neo4jContainer) -> AsyncIterator[GraphStore]:
    """A GraphStore bound to the disposable Neo4j container, indexes already created."""
    driver = neo4j.AsyncGraphDatabase.driver(
        neo4j_container.get_connection_url(),
        auth=(neo4j_container.username, neo4j_container.password),
    )
    store = GraphStore(driver, database="neo4j")
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def tenant_id() -> str:
    """A fresh tenant id per test so tests don't see each other's graph data."""
    return f"test-tenant-{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="session")
def app_settings(neo4j_container: Neo4jContainer) -> Settings:
    """Settings pointing the API at the disposable test Neo4j container."""
    return Settings(
        neo4j_uri=neo4j_container.get_connection_url(),
        neo4j_user=neo4j_container.username,
        neo4j_password=neo4j_container.password,
        neo4j_database="neo4j",
        schema_path=str(EVENT_SCHEMA_PATH),
    )


@pytest_asyncio.fixture(scope="session")
async def api_client(app_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """An httpx client wired directly to the FastAPI app via ASGI transport."""
    app = create_app(settings=app_settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def event_schema_path() -> Path:
    """Path to the v1.0.0 universal event JSON Schema."""
    return EVENT_SCHEMA_PATH


@pytest.fixture
def make_event() -> Callable[..., dict[str, Any]]:
    """Factory for a minimal, schema-valid event, with overridable fields."""

    def _make_event(**overrides: Any) -> dict[str, Any]:
        event: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "eventId": str(uuid.uuid4()),
            "tenantId": "acme-corp",
            "applicationId": "jira",
            "applicationInstanceId": "acme-jira-01",
            "environment": "production",
            "eventTimestamp": datetime.now(timezone.utc).isoformat(),
            "actor": {
                "nativeUserId": "hr_manager001",
                "userIdType": "employee_id",
            },
            "action": {
                "type": "update_issue_status",
                "category": "update",
            },
            "object": {
                "objectType": "issue",
                "objectId": "PROJ-123",
            },
            "source": {
                "connector": "jira-connector",
                "connectorVersion": "1.0.0",
            },
        }
        event.update(overrides)
        return event

    return _make_event
