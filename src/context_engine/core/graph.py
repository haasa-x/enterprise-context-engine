"""Neo4j-backed temporal knowledge graph storage.

Every read and write is scoped to a `tenantId` to guarantee multi-tenant data
isolation. `tenant_query` is the only sanctioned way to run Cypher in this
module — it refuses to execute any query that does not reference `tenantId`.
The Cypher text itself lives in :mod:`context_engine.core.graph_queries`.
"""

from __future__ import annotations

import json
from typing import Any

import neo4j
import structlog
from neo4j.exceptions import ConstraintError

from context_engine.core import graph_queries as queries
from context_engine.core.exceptions import DuplicateEventError

logger = structlog.get_logger(__name__)

# Backward-compatible alias: this module historically raised
# ``EventAlreadyExistsError``. The canonical name now lives in ``core.exceptions``.
EventAlreadyExistsError = DuplicateEventError


def _to_native_datetime(value: Any) -> Any:
    """Convert a neo4j.time.DateTime to a stdlib datetime; pass through anything else."""
    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        result: Any = to_native()
        return result
    return value


async def tenant_query(
    tx: neo4j.AsyncManagedTransaction, query: str, tenant_id: str, **params: Any
) -> neo4j.AsyncResult:
    """Execute a Cypher query with mandatory tenant scoping.

    This is the only permitted way to run Cypher against the graph in this
    codebase; direct `tx.run()` calls are not allowed, so a query written
    without a `tenantId` filter fails loudly instead of silently leaking
    data across tenants.
    """
    if "tenantId" not in query:
        raise ValueError("Query must include tenantId filter")
    return await tx.run(query, tenantId=tenant_id, **params)


class GraphStore:
    """Async wrapper around the Neo4j driver exposing tenant-scoped graph operations."""

    def __init__(self, driver: neo4j.AsyncDriver, database: str) -> None:
        """Bind this store to a driver and target database."""
        self._driver = driver
        self._database = database

    async def initialize(self) -> None:
        """Create indexes and constraints. Safe to call repeatedly."""
        async with self._driver.session(database=self._database) as session:
            for statement in queries.INIT_STATEMENTS:
                await session.run(statement)
        logger.info("graph.initialized")

    async def write_event(self, event: dict[str, Any]) -> None:
        """Upsert the actor, application, and object nodes, then record a PERFORMED edge.

        Raises DuplicateEventError if `event['eventId']` has already been written.
        """
        actor = event["actor"]
        action = event["action"]
        obj = event["object"]
        context = event.get("context") or {}
        tenant_id = event["tenantId"]
        params = {
            "applicationId": event["applicationId"],
            "applicationInstanceId": event["applicationInstanceId"],
            "nativeUserId": actor["nativeUserId"],
            "userIdType": actor["userIdType"],
            "canonicalUserId": actor.get("canonicalUserId"),
            "roles": actor.get("roles") or [],
            "objectType": obj["objectType"],
            "objectId": obj["objectId"],
            "eventId": event["eventId"],
            "actionType": action["type"],
            "actionCategory": action["category"],
            "eventTimestamp": event["eventTimestamp"],
            "metadata": json.dumps(action.get("metadata")) if action.get("metadata") else None,
            "environment": event["environment"],
            "sessionId": context.get("sessionId"),
            "correlationId": context.get("correlationId"),
            "device": context.get("device"),
        }

        async def _write(tx: neo4j.AsyncManagedTransaction) -> None:
            result = await tenant_query(tx, queries.WRITE_EVENT, tenant_id, **params)
            await result.consume()

        async with self._driver.session(database=self._database) as session:
            try:
                await session.execute_write(_write)
            except ConstraintError as exc:
                raise DuplicateEventError(event["eventId"]) from exc

    async def get_user_history(
        self, tenant_id: str, user_id: str, days: int = 14, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Return PERFORMED events for a single native user, most recent first.

        Pass ``limit`` to cap the result to the most recent N events — used by
        read-only admin/graph views. Profiling leaves it unset so pattern
        detection always sees the user's full history.
        """

        async def _read(tx: neo4j.AsyncManagedTransaction) -> list[dict[str, Any]]:
            if limit is None:
                result = await tenant_query(
                    tx, queries.USER_HISTORY, tenant_id, userId=user_id, days=days
                )
            else:
                result = await tenant_query(
                    tx,
                    queries.USER_HISTORY_LIMITED,
                    tenant_id,
                    userId=user_id,
                    days=days,
                    limit=limit,
                )
            return [record.data() async for record in result]

        async with self._driver.session(database=self._database) as session:
            records = await session.execute_read(_read)
        return [self._deserialize_history_record(r) for r in records]

    async def get_cross_app_history(
        self, tenant_id: str, canonical_user_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        """Return PERFORMED events across all applications for a resolved identity."""

        async def _read(tx: neo4j.AsyncManagedTransaction) -> list[dict[str, Any]]:
            result = await tenant_query(
                tx,
                queries.CROSS_APP_HISTORY,
                tenant_id,
                canonicalUserId=canonical_user_id,
                days=days,
            )
            return [record.data() async for record in result]

        async with self._driver.session(database=self._database) as session:
            records = await session.execute_read(_read)
        return [self._deserialize_history_record(r) for r in records]

    async def find_user_patterns(
        self, tenant_id: str, user_id: str, action_type: str
    ) -> dict[str, Any]:
        """Return how often and how recently a user has performed a given action type."""

        async def _read(tx: neo4j.AsyncManagedTransaction) -> dict[str, Any]:
            result = await tenant_query(
                tx, queries.USER_ACTION_PATTERN, tenant_id, userId=user_id, actionType=action_type
            )
            record = await result.single()
            return record.data() if record else {"occurrenceCount": 0, "lastOccurred": None}

        async with self._driver.session(database=self._database) as session:
            data = await session.execute_read(_read)
        return {
            "actionType": action_type,
            "occurrenceCount": data.get("occurrenceCount", 0),
            "lastOccurred": _to_native_datetime(data.get("lastOccurred")),
        }

    async def get_canonical_user_id(self, tenant_id: str, user_id: str) -> str | None:
        """Return the resolved cross-app identity for a native user id, if one exists."""

        async def _read(tx: neo4j.AsyncManagedTransaction) -> str | None:
            result = await tenant_query(tx, queries.CANONICAL_USER_ID, tenant_id, userId=user_id)
            record = await result.single()
            return record["canonicalUserId"] if record else None

        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(_read)

    async def link_identities(
        self,
        tenant_id: str,
        user_a: str,
        app_a: str,
        user_b: str,
        app_b: str,
        method: str,
        confidence: float,
    ) -> None:
        """Create a SAME_PERSON edge linking two per-application user identities."""

        async def _write(tx: neo4j.AsyncManagedTransaction) -> None:
            result = await tenant_query(
                tx,
                queries.LINK_IDENTITIES,
                tenant_id,
                userA=user_a,
                appA=app_a,
                userB=user_b,
                appB=app_b,
                method=method,
                confidence=confidence,
            )
            await result.consume()

        async with self._driver.session(database=self._database) as session:
            await session.execute_write(_write)

    async def get_active_users(self, tenant_id: str, since_days: int = 7) -> list[str]:
        """Return native user ids seen within the last `since_days` days."""

        async def _read(tx: neo4j.AsyncManagedTransaction) -> list[str]:
            result = await tenant_query(
                tx, queries.ACTIVE_USERS, tenant_id, days=since_days
            )
            return [record["userId"] async for record in result]

        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(_read)

    async def get_user_event_count(self, tenant_id: str, user_id: str) -> int:
        """Return the total number of PERFORMED events for a native user."""

        async def _read(tx: neo4j.AsyncManagedTransaction) -> int:
            result = await tenant_query(
                tx, queries.USER_EVENT_COUNT, tenant_id, userId=user_id
            )
            record = await result.single()
            return int(record["eventCount"]) if record else 0

        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(_read)

    async def update_user_profile(
        self, tenant_id: str, user_id: str, profile_text: str, version: int
    ) -> None:
        """Store the generated NLQ profile text and version on the user's nodes."""

        async def _write(tx: neo4j.AsyncManagedTransaction) -> None:
            result = await tenant_query(
                tx,
                queries.UPDATE_USER_PROFILE,
                tenant_id,
                userId=user_id,
                profileText=profile_text,
                version=version,
            )
            await result.consume()

        async with self._driver.session(database=self._database) as session:
            await session.execute_write(_write)

    async def get_user_profile(self, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        """Return the stored NLQ profile for a user, or None if none has been generated."""

        async def _read(tx: neo4j.AsyncManagedTransaction) -> dict[str, Any] | None:
            result = await tenant_query(
                tx, queries.GET_USER_PROFILE, tenant_id, userId=user_id
            )
            record = await result.single()
            return record.data() if record else None

        async with self._driver.session(database=self._database) as session:
            data = await session.execute_read(_read)
        if data is None:
            return None
        data["profileGeneratedAt"] = _to_native_datetime(data.get("profileGeneratedAt"))
        return data

    async def verify_connectivity(self) -> None:
        """Raise if Neo4j is unreachable. Used by the readiness probe."""
        await self._driver.verify_connectivity()

    async def close(self) -> None:
        """Close the underlying driver connection pool."""
        await self._driver.close()

    @staticmethod
    def _deserialize_history_record(record: dict[str, Any]) -> dict[str, Any]:
        metadata = record.get("metadata")
        if isinstance(metadata, str):
            record["metadata"] = json.loads(metadata)
        record["eventTimestamp"] = _to_native_datetime(record.get("eventTimestamp"))
        return record
