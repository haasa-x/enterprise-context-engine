"""Tests for the Context Engine MCP server."""

from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session

from context_engine.config import Settings
from context_engine.core.graph import GraphStore
from context_engine.mcp.server import create_server


async def test_both_tools_are_registered(app_settings: Settings) -> None:
    server = create_server(settings=app_settings)
    async with create_connected_server_and_client_session(server) as session:
        await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "resolve_user_intent" in names
        assert "get_user_profile" in names


async def test_resolve_user_intent_returns_empty_predictions_for_unknown_user(
    app_settings: Settings,
) -> None:
    server = create_server(settings=app_settings)
    async with create_connected_server_and_client_session(server) as session:
        await session.initialize()
        result = await session.call_tool(
            "resolve_user_intent",
            {
                "tenant_id": "mcp-test-tenant",
                "user_id": "nobody",
                "trigger_text": "anything",
            },
        )

    assert result.isError is False
    assert result.structuredContent == {"predictions": []}


async def test_get_user_profile_reports_insufficient_data_for_unknown_user(
    app_settings: Settings,
) -> None:
    server = create_server(settings=app_settings)
    async with create_connected_server_and_client_session(server) as session:
        await session.initialize()
        result = await session.call_tool(
            "get_user_profile",
            {"tenant_id": "mcp-test-tenant", "user_id": "nobody"},
        )

    assert result.isError is False
    assert result.structuredContent["error"] == "insufficient_data"


async def test_resolve_user_intent_boosts_matching_keyword(
    app_settings: Settings, graph_store: GraphStore, tenant_id, make_event
) -> None:
    user_id = "mcp-user-1"
    event = make_event(
        tenantId=tenant_id,
        actor={"nativeUserId": user_id, "userIdType": "employee_id"},
        action={"type": "view_sprint_board", "category": "read"},
        object={"objectType": "sprint", "objectId": "SPRINT-99"},
    )
    await graph_store.write_event(event)

    server = create_server(settings=app_settings)
    async with create_connected_server_and_client_session(server) as session:
        await session.initialize()
        result = await session.call_tool(
            "resolve_user_intent",
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "trigger_text": "Sprint closes tomorrow",
            },
        )

    assert result.isError is False
    predictions = result.structuredContent["predictions"]
    assert len(predictions) == 1
    assert predictions[0]["actionType"] == "view_sprint_board"
    assert any(s["type"] == "keyword_match" for s in predictions[0]["signals"])
