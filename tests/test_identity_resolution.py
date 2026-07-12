"""Tests for context_engine.core.identity.IdentityResolver."""

from __future__ import annotations

from context_engine.core.graph import GraphStore
from context_engine.core.identity import AppIdentity, IdentityResolver


async def test_attempt_link_matches_exact_email(graph_store: GraphStore, tenant_id, make_event):
    jira_event = make_event(
        tenantId=tenant_id,
        applicationId="jira",
        actor={"nativeUserId": "person@acme.com", "userIdType": "email"},
    )
    sf_event = make_event(
        tenantId=tenant_id,
        applicationId="successfactors",
        actor={"nativeUserId": "Person@Acme.com", "userIdType": "email"},
        action={"type": "approve_leave_request", "category": "approve"},
        object={"objectType": "leave_request", "objectId": "LR-1"},
    )
    await graph_store.write_event(jira_event)
    await graph_store.write_event(sf_event)

    resolver = IdentityResolver(graph_store)
    linked = await resolver.attempt_link(
        tenant_id,
        AppIdentity("person@acme.com", "jira", "email"),
        AppIdentity("Person@Acme.com", "successfactors", "email"),
    )

    assert linked is True
    canonical_id = await resolver.resolve(tenant_id, "person@acme.com")
    assert canonical_id is not None


async def test_attempt_link_matches_exact_sso_subject(
    graph_store: GraphStore, tenant_id, make_event
):
    event_a = make_event(
        tenantId=tenant_id,
        applicationId="jira",
        actor={"nativeUserId": "sso|abc123", "userIdType": "sso_subject"},
    )
    event_b = make_event(
        tenantId=tenant_id,
        applicationId="successfactors",
        actor={"nativeUserId": "sso|abc123", "userIdType": "sso_subject"},
        action={"type": "approve_leave_request", "category": "approve"},
        object={"objectType": "leave_request", "objectId": "LR-9"},
    )
    await graph_store.write_event(event_a)
    await graph_store.write_event(event_b)

    resolver = IdentityResolver(graph_store)
    linked = await resolver.attempt_link(
        tenant_id,
        AppIdentity("sso|abc123", "jira", "sso_subject"),
        AppIdentity("sso|abc123", "successfactors", "sso_subject"),
    )

    assert linked is True
    assert await resolver.resolve(tenant_id, "sso|abc123") is not None


async def test_attempt_link_rejects_mismatched_email(
    graph_store: GraphStore, tenant_id, make_event
):
    event_a = make_event(
        tenantId=tenant_id,
        applicationId="jira",
        actor={"nativeUserId": "alice@acme.com", "userIdType": "email"},
    )
    event_b = make_event(
        tenantId=tenant_id,
        applicationId="successfactors",
        actor={"nativeUserId": "bob@acme.com", "userIdType": "email"},
        action={"type": "approve_leave_request", "category": "approve"},
        object={"objectType": "leave_request", "objectId": "LR-2"},
    )
    await graph_store.write_event(event_a)
    await graph_store.write_event(event_b)

    resolver = IdentityResolver(graph_store)
    linked = await resolver.attempt_link(
        tenant_id,
        AppIdentity("alice@acme.com", "jira", "email"),
        AppIdentity("bob@acme.com", "successfactors", "email"),
    )

    assert linked is False
    assert await resolver.resolve(tenant_id, "alice@acme.com") is None


async def test_attempt_link_rejects_weak_id_types(
    graph_store: GraphStore, tenant_id, make_event
):
    event_a = make_event(
        tenantId=tenant_id,
        applicationId="jira",
        actor={"nativeUserId": "jira-native-1", "userIdType": "app_native_id"},
    )
    event_b = make_event(
        tenantId=tenant_id,
        applicationId="successfactors",
        actor={"nativeUserId": "jira-native-1", "userIdType": "employee_id"},
        action={"type": "approve_leave_request", "category": "approve"},
        object={"objectType": "leave_request", "objectId": "LR-3"},
    )
    await graph_store.write_event(event_a)
    await graph_store.write_event(event_b)

    resolver = IdentityResolver(graph_store)
    linked = await resolver.attempt_link(
        tenant_id,
        AppIdentity("jira-native-1", "jira", "app_native_id"),
        AppIdentity("jira-native-1", "successfactors", "employee_id"),
    )

    assert linked is False


async def test_resolve_returns_none_when_unresolved(graph_store: GraphStore, tenant_id):
    resolver = IdentityResolver(graph_store)
    assert await resolver.resolve(tenant_id, "nobody@acme.com") is None
