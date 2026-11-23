from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.rate_limiter import InMemoryRateLimiterService
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.tenant import Tenant
from app.models.wazza_mcp import WazzaMcpAuditLog, WazzaMcpCredential
from app.routers import wazza_mcp as wazza_router
from app.services.wazza_mcp_auth import issue_credential


@pytest.fixture
def mcp(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    for table in (
        Tenant.__table__,
        MenuCategory.__table__,
        MenuItem.__table__,
        ModifierGroup.__table__,
        ModifierOption.__table__,
        WazzaMcpCredential.__table__,
        WazzaMcpAuditLog.__table__,
    ):
        table.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all(
            [
                Tenant(id=1, name="Burger Um", business_name="Burger Um", slug="burger-um", delivery_fee=Decimal("5.50")),
                Tenant(id=2, name="Pizza Dois", business_name="Pizza Dois", slug="pizza-dois", delivery_fee=Decimal("8.00")),
                MenuCategory(id=10, tenant_id=1, name="Lanches", sort_order=1, active=True),
                MenuCategory(id=20, tenant_id=2, name="Pizzas", sort_order=1, active=True),
                MenuItem(id=100, tenant_id=1, category_id=10, name="X-Burger", description="Artesanal", price_cents=2590, active=True),
                MenuItem(id=101, tenant_id=1, category_id=10, name="Item oculto", price_cents=100, active=False),
                MenuItem(id=200, tenant_id=2, category_id=20, name="Pizza secreta", price_cents=4990, active=True),
                ModifierGroup(id=300, tenant_id=1, product_id=100, name="Adicionais", required=False, min_selection=0, max_selection=2, active=True),
                ModifierOption(id=400, group_id=300, name="Bacon", price_delta=Decimal("4.50"), is_active=True),
            ]
        )
        db.commit()
        first = issue_credential(db, tenant_id=1, name="Wazza tenant 1", scopes=("menu:read",))
        second = issue_credential(db, tenant_id=2, name="Wazza tenant 2", scopes=("menu:read",))
        no_menu = issue_credential(db, tenant_id=1, name="Sem menu", scopes=("order:read",))
        db.commit()

    app = FastAPI()
    app.include_router(wazza_router.router)

    def session_dep():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = session_dep
    monkeypatch.setattr(wazza_router.config, "WAZZA_MCP_ENABLED", True)
    monkeypatch.setattr(wazza_router, "_rate_limiter", InMemoryRateLimiterService(limit=120, window_seconds=60))
    with TestClient(app) as client:
        yield client, sessions, first.token, second.token, no_menu.token
    engine.dispose()


def _post(client: TestClient, token: str | None, method: str, params=None, request_id="req-1", headers=None):
    request_headers = dict(headers or {})
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/api/integrations/wazza/mcp",
        headers=request_headers,
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
    )


def test_discovery_matches_wazza_json_rpc_client_and_exposes_only_safe_reads(mcp):
    client, _sessions, token, _other, _no_menu = mcp
    response = _post(client, token, "tools/list", request_id="discover")
    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == "discover"
    tools = body["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {"restaurant_get_status", "menu_list_categories", "menu_search_items", "menu_get_item"}
    assert not any("customer" in name or "order" in name or "tracking" in name for name in names)
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools)
    assert all(tool["inputSchema"].get("additionalProperties") is False for tool in tools)


def test_search_and_item_result_use_structured_content_expected_by_wazza(mcp):
    client, _sessions, token, _other, _no_menu = mcp
    status = _post(
        client,
        token,
        "tools/call",
        {"name": "restaurant_get_status", "arguments": {}},
        request_id="status",
    )
    restaurant = status.json()["result"]["structuredContent"]["data"]["restaurant"]
    assert restaurant == {
        "name": "Burger Um",
        "slug": "burger-um",
        "accepting_orders": True,
        "estimated_prep_time": None,
        "delivery_fee_cents": 550,
    }

    search = _post(
        client,
        token,
        "tools/call",
        {"name": "menu_search_items", "arguments": {"query": "x burger", "limit": 3}},
    )
    assert search.status_code == 200
    result = search.json()["result"]
    structured = result["structuredContent"]
    assert structured["ok"] is True and structured["tool"] == "menu_search_items"
    assert structured["data"]["items"][0]["name"] == "X-Burger"
    assert structured["data"]["items"][0]["price_cents"] == 2590
    assert result["content"][0]["type"] == "text" and result["isError"] is False

    detail = _post(client, token, "tools/call", {"name": "menu_get_item", "arguments": {"item_id": 100}}, request_id="detail")
    item = detail.json()["result"]["structuredContent"]["data"]["item"]
    assert item["modifier_groups"][0]["options"][0] == {
        "id": 400,
        "name": "Bacon",
        "description": None,
        "price_delta_cents": 450,
        "is_default": False,
    }


def test_credential_tenant_is_the_only_source_of_restaurant_scope(mcp):
    client, _sessions, first, second, _no_menu = mcp
    first_result = _post(client, first, "tools/call", {"name": "menu_search_items", "arguments": {"query": "pizza"}})
    second_result = _post(client, second, "tools/call", {"name": "menu_search_items", "arguments": {"query": "pizza"}})
    assert first_result.json()["result"]["structuredContent"]["data"]["items"] == []
    assert second_result.json()["result"]["structuredContent"]["data"]["items"][0]["name"] == "Pizza secreta"

    injected = _post(client, first, "tools/call", {"name": "menu_search_items", "arguments": {"query": "pizza", "tenant_id": 2}})
    assert injected.json()["error"]["code"] == -32602


def test_missing_invalid_disabled_and_insufficient_credentials_fail_closed(mcp, monkeypatch):
    client, _sessions, token, _other, no_menu = mcp
    assert _post(client, None, "tools/list").status_code == 401
    assert _post(client, "invalid", "tools/list").status_code == 401

    discovery = _post(client, no_menu, "tools/list")
    assert discovery.json()["result"]["tools"] == []
    denied = _post(client, no_menu, "tools/call", {"name": "menu_search_items", "arguments": {"query": "burger"}})
    assert denied.json()["error"]["code"] == -32003

    monkeypatch.setattr(wazza_router.config, "WAZZA_MCP_ENABLED", False)
    disabled = _post(client, token, "tools/list")
    assert disabled.status_code == 503 and disabled.json()["error"]["message"] == "Integração indisponível."


def test_tool_calls_are_audited_without_argument_values(mcp):
    client, sessions, token, _other, _no_menu = mcp
    query = "x burger dado sensível não deve ir ao log"
    response = _post(
        client,
        token,
        "tools/call",
        {"name": "menu_search_items", "arguments": {"query": query, "limit": 2}},
        request_id="audit-request",
        headers={"X-Wazza-Conversation-ID": "opaque-conversation"},
    )
    assert response.status_code == 200
    with sessions() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="audit-request").one()
        assert audit.tenant_id == 1
        assert audit.conversation_id == "opaque-conversation"
        assert audit.argument_keys_json == ["limit", "query"]
        assert query not in str(audit.argument_keys_json)


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": ""},
        {"query": "burger", "limit": 1000},
        {"query": "burger", "customer_phone": "5511999999999"},
    ],
)
def test_invalid_arguments_are_generic_and_audited(mcp, arguments):
    client, sessions, token, _other, _no_menu = mcp
    response = _post(client, token, "tools/call", {"name": "menu_search_items", "arguments": arguments}, request_id="invalid-args")
    assert response.status_code == 200
    assert response.json()["error"] == {"code": -32602, "message": "A ferramenta não pôde concluir a consulta."}
    with sessions() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="invalid-args").one()
        assert audit.outcome == "error" and audit.error_code == "invalid_arguments"


def test_initialize_body_limit_and_per_credential_rate_limit(mcp, monkeypatch):
    client, _sessions, token, _other, _no_menu = mcp
    initialized = _post(client, token, "initialize")
    assert initialized.json()["result"]["capabilities"] == {"tools": {"listChanged": False}}

    oversized = client.post(
        "/api/integrations/wazza/mcp",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        content=b"x" * (wazza_router.MAX_BODY_BYTES + 1),
    )
    assert oversized.status_code == 413

    monkeypatch.setattr(wazza_router, "_rate_limiter", InMemoryRateLimiterService(limit=1, window_seconds=60))
    assert _post(client, token, "tools/list", request_id="rate-1").status_code == 200
    limited = _post(client, token, "tools/list", request_id="rate-2")
    assert limited.status_code == 429 and limited.headers["Retry-After"]
