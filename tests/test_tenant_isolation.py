"""Tenant isolation tests.

Data written under one tenant must never be visible to another. The
``tenant_query`` guard test runs without Neo4j; the end-to-end isolation tests
use the shared Neo4j container.
"""

from __future__ import annotations

import uuid

import pytest

from context_engine.core.graph import GraphStore, tenant_query


async def test_tenant_query_rejects_query_without_tenant_filter() -> None:
    with pytest.raises(ValueError, match="tenantId"):
        await tenant_query(
            tx=object(),  # type: ignore[arg-type]
            query="MATCH (n) RETURN n",
            tenant_id="acme-corp",
        )


async def test_user_history_is_isolated_by_tenant(
    graph_store: GraphStore, tenant_id, make_event
) -> None:
    other_tenant = f"other-{uuid.uuid4().hex[:12]}"
    event = make_event(
        tenantId=tenant_id,
        actor={"nativeUserId": "shared_user", "userIdType": "employee_id"},
    )
    await graph_store.write_event(event)

    own = await graph_store.get_user_history(tenant_id, "shared_user", days=30)
    leaked = await graph_store.get_user_history(other_tenant, "shared_user", days=30)

    assert len(own) == 1
    assert leaked == []


async def test_event_counts_are_isolated_by_tenant(
    graph_store: GraphStore, tenant_id, make_event
) -> None:
    other_tenant = f"other-{uuid.uuid4().hex[:12]}"
    await graph_store.write_event(
        make_event(
            tenantId=tenant_id,
            actor={"nativeUserId": "shared_user", "userIdType": "employee_id"},
        )
    )

    assert await graph_store.get_user_event_count(tenant_id, "shared_user") == 1
    assert await graph_store.get_user_event_count(other_tenant, "shared_user") == 0


async def test_profiles_are_isolated_by_tenant(
    graph_store: GraphStore, tenant_id, make_event
) -> None:
    other_tenant = f"other-{uuid.uuid4().hex[:12]}"
    await graph_store.write_event(
        make_event(
            tenantId=tenant_id,
            actor={"nativeUserId": "shared_user", "userIdType": "employee_id"},
        )
    )
    await graph_store.update_user_profile(
        tenant_id, "shared_user", "profile text", version=1
    )

    assert await graph_store.get_user_profile(tenant_id, "shared_user") is not None
    assert await graph_store.get_user_profile(other_tenant, "shared_user") is None


async def test_active_users_are_isolated_by_tenant(
    graph_store: GraphStore, tenant_id, make_event
) -> None:
    other_tenant = f"other-{uuid.uuid4().hex[:12]}"
    await graph_store.write_event(
        make_event(
            tenantId=tenant_id,
            actor={"nativeUserId": "shared_user", "userIdType": "employee_id"},
        )
    )

    assert "shared_user" in await graph_store.get_active_users(tenant_id, since_days=30)
    assert await graph_store.get_active_users(other_tenant, since_days=30) == []
