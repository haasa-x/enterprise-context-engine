"""Tests for context_engine.core.graph.GraphStore, backed by a disposable Neo4j."""

from __future__ import annotations

import pytest

from context_engine.core.graph import EventAlreadyExistsError, GraphStore, tenant_query


async def test_write_event_then_appears_in_history(graph_store: GraphStore, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    await graph_store.write_event(event)

    history = await graph_store.get_user_history(tenant_id, event["actor"]["nativeUserId"])

    assert len(history) == 1
    assert history[0]["eventId"] == event["eventId"]
    assert history[0]["actionType"] == event["action"]["type"]
    assert history[0]["objectId"] == event["object"]["objectId"]


async def test_duplicate_event_id_rejected(graph_store: GraphStore, tenant_id, make_event):
    event = make_event(tenantId=tenant_id)
    await graph_store.write_event(event)

    with pytest.raises(EventAlreadyExistsError):
        await graph_store.write_event(event)


async def test_metadata_round_trips_through_json(graph_store: GraphStore, tenant_id, make_event):
    event = make_event(
        tenantId=tenant_id,
        action={
            "type": "update_issue_status",
            "category": "update",
            "metadata": {"from": "open", "to": "closed"},
        },
    )
    await graph_store.write_event(event)

    history = await graph_store.get_user_history(tenant_id, event["actor"]["nativeUserId"])

    assert history[0]["metadata"] == {"from": "open", "to": "closed"}


async def test_tenant_isolation(graph_store: GraphStore, tenant_id, make_event):
    other_tenant = f"{tenant_id}-other"
    shared_user = "shared-user-id"

    actor = {"nativeUserId": shared_user, "userIdType": "employee_id"}
    event_a = make_event(tenantId=tenant_id, actor=actor)
    event_b = make_event(tenantId=other_tenant, actor=actor)

    await graph_store.write_event(event_a)
    await graph_store.write_event(event_b)

    history_a = await graph_store.get_user_history(tenant_id, shared_user)
    history_b = await graph_store.get_user_history(other_tenant, shared_user)

    assert {h["eventId"] for h in history_a} == {event_a["eventId"]}
    assert {h["eventId"] for h in history_b} == {event_b["eventId"]}


async def test_history_respects_days_window(graph_store: GraphStore, tenant_id, make_event):
    from datetime import datetime, timedelta, timezone

    old_event = make_event(
        tenantId=tenant_id,
        eventTimestamp=(datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    )
    await graph_store.write_event(old_event)

    history = await graph_store.get_user_history(
        tenant_id, old_event["actor"]["nativeUserId"], days=14
    )

    assert history == []


async def test_find_user_patterns_counts_occurrences(
    graph_store: GraphStore, tenant_id, make_event
):
    user_id = "pattern-user"
    for _ in range(3):
        event = make_event(
            tenantId=tenant_id,
            actor={"nativeUserId": user_id, "userIdType": "employee_id"},
            action={"type": "view_sprint_board", "category": "read"},
        )
        await graph_store.write_event(event)

    patterns = await graph_store.find_user_patterns(tenant_id, user_id, "view_sprint_board")

    assert patterns["occurrenceCount"] == 3
    assert patterns["lastOccurred"] is not None


async def test_find_user_patterns_no_history(graph_store: GraphStore, tenant_id):
    patterns = await graph_store.find_user_patterns(tenant_id, "nobody", "close_sprint")
    assert patterns["occurrenceCount"] == 0
    assert patterns["lastOccurred"] is None


async def test_link_identities_enables_cross_app_history(
    graph_store: GraphStore, tenant_id, make_event
):
    jira_event = make_event(
        tenantId=tenant_id,
        applicationId="jira",
        actor={"nativeUserId": "jira-user-1", "userIdType": "app_native_id"},
    )
    sf_event = make_event(
        tenantId=tenant_id,
        applicationId="successfactors",
        actor={"nativeUserId": "sf-user-1", "userIdType": "employee_id"},
        action={"type": "approve_leave_request", "category": "approve"},
        object={"objectType": "leave_request", "objectId": "LR-1"},
    )
    await graph_store.write_event(jira_event)
    await graph_store.write_event(sf_event)

    await graph_store.link_identities(
        tenant_id,
        user_a="jira-user-1",
        app_a="jira",
        user_b="sf-user-1",
        app_b="successfactors",
        method="exact_email_match",
        confidence=0.95,
    )

    async def _get_canonical_id(tx):
        result = await tenant_query(
            tx,
            "MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId}) "
            "RETURN u.canonicalUserId AS cid",
            tenant_id,
            userId="jira-user-1",
        )
        record = await result.single()
        return record["cid"]

    async with graph_store._driver.session(database=graph_store._database) as session:
        canonical_id = await session.execute_read(_get_canonical_id)

    assert canonical_id is not None

    history = await graph_store.get_cross_app_history(tenant_id, canonical_id)
    event_ids = {h["eventId"] for h in history}
    assert jira_event["eventId"] in event_ids
    assert sf_event["eventId"] in event_ids


async def test_tenant_query_rejects_query_without_tenant_filter(graph_store: GraphStore, tenant_id):
    async def _read(tx):
        return await tenant_query(tx, "MATCH (n) RETURN n LIMIT 1", tenant_id)

    with pytest.raises(ValueError, match="tenantId"):
        async with graph_store._driver.session(database=graph_store._database) as session:
            await session.execute_read(_read)
