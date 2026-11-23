from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
from threading import Barrier
import time

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.rate_limiter import InMemoryRateLimiterService
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.tenant import Tenant
from app.models.customer import Customer
from app.models.admin_user import AdminUser
from app.models.customer_points import CustomerPoints
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.models.finance import CashMovement, OrderPayment
from app.models.order_durability import OrderOutbox, OrderSubmission
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.wazza_mcp import WazzaMcpAuditLog, WazzaMcpCredential, WazzaOrderDraft
from app.routers import wazza_mcp as wazza_router, public_menu
from app.services.wazza_mcp_auth import issue_credential
from app.services.wazza_mcp_identity import CONTEXT_HEADER, SIGNATURE_HEADER
from app.services import wazza_mcp_customer_tools


@pytest.fixture
def mcp(monkeypatch, tmp_path):
    engine = sa.create_engine(
        f"sqlite:///{tmp_path / 'wazza.db'}",
        connect_args={"check_same_thread": False},
    )

    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with sessions() as db:
        db.add_all(
            [
                Tenant(id=1, name="Burger Um", business_name="Burger Um", slug="burger-um", delivery_fee=Decimal("5.50")),
                Tenant(id=2, name="Pizza Dois", business_name="Pizza Dois", slug="pizza-dois", delivery_fee=Decimal("8.00")),
            ]
        )
        db.flush()
        db.add_all(
            [
                MenuCategory(id=10, tenant_id=1, name="Lanches", sort_order=1, active=True),
                MenuCategory(id=20, tenant_id=2, name="Pizzas", sort_order=1, active=True),
                MenuItem(id=100, tenant_id=1, category_id=10, name="X-Burger", description="Artesanal", price_cents=2590, active=True),
                MenuItem(id=101, tenant_id=1, category_id=10, name="Item oculto", price_cents=100, active=False),
                MenuItem(id=200, tenant_id=2, category_id=20, name="Pizza secreta", price_cents=4990, active=True),
                ModifierGroup(id=300, tenant_id=1, product_id=100, name="Adicionais", required=False, min_selection=0, max_selection=2, active=True),
                ModifierOption(id=400, group_id=300, name="Bacon", price_delta=Decimal("4.50"), is_active=True),
                AdminUser(id=99, tenant_id=1, email="driver@example.com", name="Entregador", password_hash="not-used", role="delivery", active=True),
                Customer(id=500, tenant_id=1, name="Cliente Um", phone="+5511999999999", phone_normalized="+5511999999999", email="cliente@example.com", is_active=True),
                Customer(id=600, tenant_id=2, name="Cliente Dois", phone="+5511999999999", phone_normalized="+5511999999999", is_active=True),
                CustomerPoints(id=700, tenant_id=1, customer_id=500, available_points=120, lifetime_points=450),
                Order(id=501, daily_order_number=1, tenant_id=1, customer_id=500, cliente_nome="Cliente Um", cliente_telefone="5511999999999", itens="Burger", endereco="Rua A", observacao="", tipo_entrega="ENTREGA", forma_pagamento="PIX", total_cents=2590, status="DELIVERED", tracking_expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
                Order(id=502, daily_order_number=2, tenant_id=1, customer_id=500, cliente_nome="Cliente Um", cliente_telefone="5511999999999", itens="Burger", endereco="Rua A", observacao="", tipo_entrega="ENTREGA", forma_pagamento="PIX", total_cents=3090, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=99, tracking_token="tracking-customer-one", tracking_expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
                Order(id=601, daily_order_number=1, tenant_id=2, customer_id=600, cliente_nome="Cliente Dois", cliente_telefone="5511999999999", itens="Pizza", endereco="Rua B", observacao="", tipo_entrega="ENTREGA", forma_pagamento="PIX", total_cents=4990, status="RECEBIDO", tracking_expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
                Order(id=503, daily_order_number=3, tenant_id=1, cliente_nome="Outra Pessoa", cliente_telefone="5511888888888", itens="Oculto", endereco="Rua C", observacao="", tipo_entrega="ENTREGA", forma_pagamento="PIX", total_cents=9990, status="RECEBIDO", tracking_expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
            ]
        )
        db.flush()
        db.add(DeliveryTracking(id=800, order_id=502, delivery_user_id=99, estimated_duration_seconds=900, expected_delivery_at=datetime.now(timezone.utc) + timedelta(minutes=15), route_distance_meters=2500, route_duration_seconds=780))
        db.commit()
        read_scopes = ("menu:read", "customer:read", "order:read", "order:draft", "order:create", "order:edit", "order:cancel")
        first = issue_credential(db, tenant_id=1, name="Wazza tenant 1", scopes=read_scopes)
        second = issue_credential(db, tenant_id=2, name="Wazza tenant 2", scopes=read_scopes)
        no_menu = issue_credential(db, tenant_id=1, name="Sem leitura", scopes=("order:draft",))
        db.commit()

    app = FastAPI()
    app.include_router(wazza_router.router)

    def session_dep():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = session_dep
    monkeypatch.setattr(wazza_router.config, "WAZZA_MCP_ENABLED", True)
    monkeypatch.setattr(wazza_router.config, "WAZZA_MCP_ORDER_CONFIRM_ENABLED", False)
    monkeypatch.delenv("CHECKOUT_POLICY_ENABLED", raising=False)
    monkeypatch.setattr(wazza_router, "_rate_limiter", InMemoryRateLimiterService(limit=120, window_seconds=60))
    monkeypatch.setattr(wazza_mcp_customer_tools, "feature_allowed", lambda *_args: True)
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


def _identity_headers(
    token: str,
    *,
    request_id: str,
    phone: str = "5511999999999",
    conversation_id: str = "opaque-conversation",
    now: int | None = None,
) -> dict[str, str]:
    issued_at = int(time.time() if now is None else now)
    claims = {
        "aud": "fomizero-mcp",
        "cid": conversation_id,
        "exp": issued_at + 60,
        "iat": issued_at,
        "iss": "wazza",
        "rid": request_id,
        "sub": phone,
        "v": 1,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    key = hashlib.sha256(token.encode()).digest()
    signature = base64.urlsafe_b64encode(
        hmac.new(key, encoded.encode("ascii"), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return {CONTEXT_HEADER: encoded, SIGNATURE_HEADER: signature}


def test_discovery_matches_wazza_json_rpc_client_and_exposes_implemented_tools(mcp):
    client, _sessions, token, _other, _no_menu = mcp
    response = _post(client, token, "tools/list", request_id="discover")
    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == "discover"
    tools = body["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {
        "restaurant_get_status",
        "menu_list_categories",
        "menu_search_items",
        "menu_get_item",
        "customer_get_profile",
        "customer_get_points",
        "order_list_recent",
        "order_get_status",
        "order_get_tracking",
        "order_draft_create",
        "order_draft_add_item",
        "order_draft_update_item",
        "order_draft_remove_item",
        "order_draft_set_delivery",
        "order_draft_set_payment",
        "order_draft_quote",
    }
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["order_draft_quote"]["annotations"]["readOnlyHint"] is True
    assert by_name["order_draft_add_item"]["annotations"]["readOnlyHint"] is False
    assert all(tool["annotations"]["destructiveHint"] is False for tool in tools)
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
    assert {tool["name"] for tool in discovery.json()["result"]["tools"]} == {
        "order_draft_create",
        "order_draft_add_item",
        "order_draft_update_item",
        "order_draft_remove_item",
        "order_draft_set_delivery",
        "order_draft_set_payment",
        "order_draft_quote",
    }
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
        headers=_identity_headers(token, request_id="audit-request"),
    )
    assert response.status_code == 200
    with sessions() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="audit-request").one()
        assert audit.tenant_id == 1
        assert audit.conversation_id == "opaque-conversation"
        assert audit.argument_keys_json == ["limit", "query"]
        assert query not in str(audit.argument_keys_json)


def test_customer_context_rejects_tampering_expiry_and_request_replay(mcp):
    client, _sessions, token, _other, _no_menu = mcp
    headers = _identity_headers(token, request_id="bound-request")
    valid = _post(client, token, "tools/list", request_id="bound-request", headers=headers)
    assert valid.status_code == 200

    replayed = _post(client, token, "tools/list", request_id="other-request", headers=headers)
    assert replayed.status_code == 401
    assert replayed.json()["error"] == {"code": -32005, "message": "Identidade do cliente inválida."}

    tampered = dict(headers)
    tampered[CONTEXT_HEADER] = tampered[CONTEXT_HEADER][:-1] + (
        "A" if tampered[CONTEXT_HEADER][-1] != "A" else "B"
    )
    assert _post(client, token, "tools/list", request_id="bound-request", headers=tampered).status_code == 401

    expired = _identity_headers(token, request_id="expired", now=int(time.time()) - 300)
    assert _post(client, token, "tools/list", request_id="expired", headers=expired).status_code == 401


def test_signed_customer_can_read_profile_points_and_only_own_orders(mcp):
    client, _sessions, token, _other, _no_menu = mcp

    def customer_call(name, arguments=None, request_id=None):
        call_id = request_id or name
        return _post(
            client,
            token,
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            request_id=call_id,
            headers=_identity_headers(token, request_id=call_id),
        ).json()["result"]["structuredContent"]["data"]

    profile = customer_call("customer_get_profile")
    assert profile["customer"] == {
        "registered": True,
        "name": "Cliente Um",
        "phone_masked": "+55******99",
        "email_masked": "c***@example.com",
        "member_since": profile["customer"]["member_since"],
    }
    points = customer_call("customer_get_points")
    assert points["loyalty"] == {"enabled": True, "available_points": 120, "lifetime_points": 450}

    orders = customer_call("order_list_recent", {"limit": 10})["orders"]
    assert [order["order_id"] for order in orders] == [502, 501]
    assert not any(order["order_id"] in {503, 601} for order in orders)
    assert orders[0]["status"] == "SAIU_PARA_ENTREGA"
    assert orders[1]["status"] == "ENTREGUE"


def test_order_status_and_tracking_require_ownership_and_active_route(mcp):
    client, sessions, token, _other, _no_menu = mcp

    def call(name, order_id, request_id):
        response = _post(
            client,
            token,
            "tools/call",
            {"name": name, "arguments": {"order_id": order_id}},
            request_id=request_id,
            headers=_identity_headers(token, request_id=request_id),
        )
        assert response.status_code == 200
        return response.json()["result"]["structuredContent"]["data"]

    active = call("order_get_tracking", 502, "tracking-active")
    assert active["tracking"]["available"] is True
    assert active["tracking"]["tracking_url"].endswith("/pedido/tracking-customer-one")
    assert active["tracking"]["remaining_seconds"] == 780

    with sessions() as db:
        db.query(Order).filter(Order.id == 502).update({"tipo_entrega": "RETIRADA"})
        db.commit()
    legacy_pickup = call("order_get_tracking", 502, "tracking-legacy-pickup")
    assert legacy_pickup["tracking"]["available"] is False
    assert legacy_pickup["tracking"]["tracking_url"] is None

    delivered = call("order_get_tracking", 501, "tracking-delivered")
    assert delivered["tracking"]["available"] is False
    assert delivered["tracking"]["status"] == "ENTREGUE"
    assert delivered["tracking"]["tracking_url"] is None

    not_owned = call("order_get_status", 503, "status-not-owned")
    other_tenant = call("order_get_status", 601, "status-other-tenant")
    assert not_owned == {"found": False, "order": None}
    assert other_tenant == {"found": False, "order": None}


def test_personal_tools_require_signed_identity_even_with_scope(mcp):
    client, sessions, token, _other, _no_menu = mcp
    response = _post(
        client,
        token,
        "tools/call",
        {"name": "order_list_recent", "arguments": {}},
        request_id="missing-customer",
    )
    assert response.status_code == 200
    assert response.json()["error"] == {
        "code": -32006,
        "message": "A ferramenta não pôde concluir a consulta.",
    }
    with sessions() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="missing-customer").one()
        assert audit.outcome == "error"
        assert audit.error_code == "customer_identity_required"


@pytest.mark.parametrize(
    "arguments",
    [
        {"customer_phone": "5511888888888"},
        {"tenant_id": 2},
    ],
)
def test_personal_tools_reject_identity_or_tenant_overrides(mcp, arguments):
    client, sessions, token, _other, _no_menu = mcp
    request_id = f"personal-override-{next(iter(arguments))}"
    response = _post(
        client,
        token,
        "tools/call",
        {"name": "order_list_recent", "arguments": arguments},
        request_id=request_id,
        headers=_identity_headers(token, request_id=request_id),
    )
    assert response.status_code == 200
    assert response.json()["error"] == {
        "code": -32602,
        "message": "A ferramenta não pôde concluir a consulta.",
    }
    with sessions() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id=request_id).one()
        assert audit.outcome == "error"
        assert audit.error_code == "invalid_arguments"


def test_order_draft_builds_server_priced_quote_without_creating_order(mcp):
    client, sessions, token, _other, _no_menu = mcp

    def call(name, arguments, request_id):
        response = _post(
            client, token, "tools/call", {"name": name, "arguments": arguments},
            request_id=request_id, headers=_identity_headers(token, request_id=request_id),
        )
        assert response.status_code == 200, response.text
        assert "error" not in response.json(), response.text
        return response.json()["result"]["structuredContent"]

    before = None
    with sessions() as db:
        before = db.query(Order).count()
    created = call("order_draft_create", {"idempotency_key": "create-order-draft-001"}, "draft-create")
    assert created["type"] == "write_result"
    draft_id = created["data"]["draft"]["draft_id"]
    added = call(
        "order_draft_add_item",
        {"draft_id": draft_id, "idempotency_key": "add-order-line-0001", "item_id": 100, "quantity": 2, "modifier_option_ids": [400], "notes": "Sem cebola"},
        "draft-add",
    )["data"]["draft"]
    line_id = added["items"][0]["line_id"]
    assert added["items"][0]["unit_price_cents"] == 3040
    assert added["subtotal_cents"] == 6080
    replayed = call(
        "order_draft_add_item",
        {"draft_id": draft_id, "idempotency_key": "add-order-line-0001", "item_id": 100, "quantity": 2, "modifier_option_ids": [400], "notes": "Sem cebola"},
        "draft-add-replay",
    )["data"]["draft"]
    assert len(replayed["items"]) == 1
    assert replayed["version"] == added["version"]

    updated = call(
        "order_draft_update_item",
        {"draft_id": draft_id, "idempotency_key": "update-order-line-01", "line_id": line_id, "quantity": 1},
        "draft-update",
    )["data"]["draft"]
    assert updated["subtotal_cents"] == 3040
    call(
        "order_draft_set_delivery",
        {"draft_id": draft_id, "idempotency_key": "delivery-choice-001", "fulfillment_type": "delivery", "address": {"zip": "01001000", "street": "Rua A", "number": "10", "neighborhood": "Centro", "city": "São Paulo", "state": "SP"}},
        "draft-delivery",
    )
    call(
        "order_draft_set_payment",
        {"draft_id": draft_id, "idempotency_key": "payment-choice-0001", "payment_method": "pix"},
        "draft-payment",
    )
    quote = call("order_draft_quote", {"draft_id": draft_id}, "draft-quote")
    assert quote["type"] == "read_result"
    data = quote["data"]["quote"]
    assert data["subtotal_cents"] == 3040
    assert data["delivery_fee_cents"] == 550
    assert data["total_cents"] == 3590
    assert data["ready_to_confirm"] is True
    assert data["creates_order"] is False
    with sessions() as db:
        assert db.query(Order).count() == before
        assert db.query(WazzaOrderDraft).filter_by(public_id=draft_id).one().status == "active"
        audits = {row.request_id: row for row in db.query(WazzaMcpAuditLog).filter(WazzaMcpAuditLog.request_id.like("draft-%")).all()}
        assert audits["draft-add"].risk == "write"
        assert audits["draft-quote"].risk == "read"


def test_order_draft_is_private_and_rejects_client_prices(mcp):
    client, _sessions, token, other_token, _no_menu = mcp

    def request(call_token, name, arguments, request_id, phone="5511999999999"):
        return _post(
            client, call_token, "tools/call", {"name": name, "arguments": arguments},
            request_id=request_id,
            headers=_identity_headers(call_token, request_id=request_id, phone=phone),
        )

    created = request(token, "order_draft_create", {"idempotency_key": "private-create-0001"}, "private-create").json()
    draft_id = created["result"]["structuredContent"]["data"]["draft"]["draft_id"]
    other_customer = request(token, "order_draft_quote", {"draft_id": draft_id}, "private-other", phone="5511888888888").json()
    other_tenant = request(other_token, "order_draft_quote", {"draft_id": draft_id}, "private-tenant").json()
    assert other_customer["error"]["code"] == -32004
    assert other_tenant["error"]["code"] == -32004
    injected = request(
        token, "order_draft_add_item",
        {"draft_id": draft_id, "idempotency_key": "private-add-item-01", "item_id": 100, "quantity": 1, "unit_price_cents": 1},
        "private-price",
    ).json()
    assert injected["error"]["code"] == -32602

    first = request(
        token, "order_draft_add_item",
        {"draft_id": draft_id, "idempotency_key": "conflicting-add-key", "item_id": 100, "quantity": 1},
        "idempotency-first",
    ).json()
    assert "result" in first
    conflict = request(
        token, "order_draft_add_item",
        {"draft_id": draft_id, "idempotency_key": "conflicting-add-key", "item_id": 100, "quantity": 2},
        "idempotency-conflict",
    ).json()
    assert conflict["error"]["code"] == -32004


def test_order_draft_remove_item_and_requires_signed_identity(mcp):
    client, _sessions, token, _other, _no_menu = mcp
    create_id = "remove-create"
    created = _post(
        client, token, "tools/call", {"name": "order_draft_create", "arguments": {"idempotency_key": "remove-create-0001"}},
        request_id=create_id, headers=_identity_headers(token, request_id=create_id),
    ).json()
    draft_id = created["result"]["structuredContent"]["data"]["draft"]["draft_id"]
    add_id = "remove-add"
    added = _post(
        client, token, "tools/call", {"name": "order_draft_add_item", "arguments": {"draft_id": draft_id, "idempotency_key": "remove-add-item-01", "item_id": 100}},
        request_id=add_id, headers=_identity_headers(token, request_id=add_id),
    ).json()
    line_id = added["result"]["structuredContent"]["data"]["draft"]["items"][0]["line_id"]
    remove_id = "remove-line"
    removed = _post(
        client, token, "tools/call", {"name": "order_draft_remove_item", "arguments": {"draft_id": draft_id, "idempotency_key": "remove-line-item-01", "line_id": line_id}},
        request_id=remove_id, headers=_identity_headers(token, request_id=remove_id),
    ).json()
    assert removed["result"]["structuredContent"]["data"]["draft"]["items"] == []
    unsigned = _post(client, token, "tools/call", {"name": "order_draft_quote", "arguments": {"draft_id": draft_id}}, request_id="draft-unsigned").json()
    assert unsigned["error"]["code"] == -32006


def test_unsigned_conversation_header_is_not_trusted_for_audit(mcp):
    client, sessions, token, _other, _no_menu = mcp
    response = _post(
        client,
        token,
        "tools/call",
        {"name": "restaurant_get_status", "arguments": {}},
        request_id="unsigned-conversation",
        headers={"X-Wazza-Conversation-ID": "must-not-be-trusted"},
    )
    assert response.status_code == 200
    with sessions() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="unsigned-conversation").one()
        assert audit.conversation_id is None


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


@pytest.fixture
def confirmation(mcp, monkeypatch):
    monkeypatch.setattr(wazza_router.config, "WAZZA_MCP_ORDER_CONFIRM_ENABLED", True)
    monkeypatch.setattr(wazza_router.config, "JWT_SECRET_KEY", "test-only-quote-signing-secret")

    async def geocode(_address):
        return -23.55, -46.63

    monkeypatch.setattr(public_menu, "geocode_address", geocode)
    return mcp


def _draft_call(mcp, suffix, arguments, request_id, *, tenant=0, phone="5511999999999", signed=True):
    client, _, token, other, _ = mcp
    token = other if tenant else token
    headers = _identity_headers(token, request_id=request_id, phone=phone) if signed else None
    return _post(client, token, "tools/call", {"name": f"order_draft_{suffix}", "arguments": arguments},
                 request_id=request_id, headers=headers).json()


def _data(body):
    assert "error" not in body, body
    return body["result"]["structuredContent"]["data"]


def _quote_for_confirmation(mcp, *, payment="pix", address=None, label="initial"):
    draft_id = _data(_draft_call(mcp, "create", {"idempotency_key": f"confirmation-cart-{label}"}, "create-" + label))["draft"]["draft_id"]
    for suffix, details in (
        ("add_item", {"item_id": 100, "quantity": 2, "modifier_option_ids": [400], "notes": "Sem cebola"}),
        ("set_delivery", {"fulfillment_type": "delivery", "address": address} if address else {"fulfillment_type": "pickup"}),
        ("set_payment", {"payment_method": payment}),
    ):
        _data(_draft_call(mcp, suffix, {
            "draft_id": draft_id, "idempotency_key": f"confirmation-{label}-{suffix}", **details,
        }, suffix + "-" + label))
    quote = _data(_draft_call(mcp, "quote", {"draft_id": draft_id}, "quote-" + label))["quote"]
    return quote, {
        "draft_id": draft_id, "confirmation_token": quote.get("confirmation_token"),
        "idempotency_key": "confirmation-attempt-001",
    }


def _assert_no_confirmation(mcp):
    _, sessions, *_ = mcp
    with sessions() as db:
        assert db.query(Order).count() == 4
        assert db.query(OrderPayment).count() == 0
        assert db.query(OrderSubmission).count() == 0
        assert db.query(OrderOutbox).count() == 0
        assert db.query(CashMovement).count() == 0
        assert db.query(WazzaOrderDraft).filter_by(status="confirmed").count() == 0


def _error_reason(body):
    return body["error"]["data"]["reason"]


def test_confirmation_requires_separate_opt_in(mcp):
    quote, args = _quote_for_confirmation(mcp)
    assert "confirmation_token" not in quote
    result = _draft_call(mcp, "confirm", args, "disabled-confirm")
    assert _error_reason(result) == "tool_not_found"
    _assert_no_confirmation(mcp)


@pytest.mark.parametrize(("preference", "financial_method"), [
    ("pix", "pix"), ("cash", "cash"), ("credit_card", "card"), ("debit_card", "card"),
])
def test_confirmation_persists_pending_finance_and_replays(confirmation, preference, financial_method):
    client, sessions, token, *_ = confirmation
    quote, args = _quote_for_confirmation(confirmation, payment=preference)
    methods = _post(client, token, "tools/list").json()["result"]["tools"]
    confirm = next(entry for entry in methods if entry["name"] == "order_draft_confirm")
    assert confirm["annotations"] == {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True}
    assert quote["total_cents"] == 6080
    assert quote["creates_order"] is False
    _assert_no_confirmation(confirmation)

    # Discard the first response as a caller losing the connection would.
    _draft_call(confirmation, "confirm", args, "first-confirm")
    with sessions.begin() as db:
        order = db.query(Order).filter_by(channel="wazza_mcp").one()
        order_id = order.id
        assert order.customer_id == 500
        assert order.payment_method == preference
        assert order.status == "pending"
        assert order.total_cents == quote["total_cents"]
        assert "Sem cebola" in order.observacao
        payment = db.query(OrderPayment).one()
        assert (payment.order_id, payment.status, payment.method, payment.amount_cents) == (
            order_id, "pending", financial_method, 6080,
        )
        assert payment.paid_at is None
        assert db.query(CashMovement).count() == 0
        assert db.query(OrderOutbox).filter_by(order_id=order_id).count() > 0
        draft = db.query(WazzaOrderDraft).filter_by(public_id=args["draft_id"]).one()
        assert (draft.status, draft.confirmed_order_id) == ("confirmed", order_id)
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="first-confirm").one()
        assert (audit.tool_name, audit.risk, audit.outcome) == ("order_draft_confirm", "destructive", "success")
        assert audit.argument_keys_json == ["confirmation_token", "draft_id", "idempotency_key"]

    expected = {"draft_id": args["draft_id"], "order_id": order_id}
    assert _data(_draft_call(confirmation, "confirm", args, "replay-confirm")) == expected
    wrong_token = {**args, "confirmation_token": "1." + "0" * 64}
    assert _error_reason(_draft_call(confirmation, "confirm", wrong_token, "conflicting-confirm")) == "idempotency_conflict"
    another = {**args, "idempotency_key": "confirmation-attempt-002"}
    assert _error_reason(_draft_call(confirmation, "confirm", another, "already-confirmed")) == "draft_already_confirmed"

    with sessions.begin() as db:
        db.query(OrderSubmission).delete()
    assert _data(_draft_call(confirmation, "confirm", args, "replay-after-retention")) == expected
    with sessions() as db:
        assert db.query(Order).filter_by(channel="wazza_mcp").count() == 1
        assert db.query(OrderPayment).count() == 1
        assert db.query(CashMovement).count() == 0


def test_confirmation_requires_signed_owner_and_strict_arguments(confirmation):
    _, args = _quote_for_confirmation(confirmation)
    for options in ({"tenant": 1}, {"phone": "5511888888888"}):
        assert _error_reason(_draft_call(confirmation, "confirm", args, "foreign", **options)) == "draft_not_found"
    missing = {**args, "draft_id": "f" * 32}
    assert _error_reason(_draft_call(confirmation, "confirm", missing, "missing")) == "draft_not_found"
    assert _error_reason(_draft_call(confirmation, "confirm", args, "unsigned", signed=False)) == "customer_identity_required"
    client, _, _, _, draft_only = confirmation
    denied_id = "credential-with-only-draft-scope"
    denied = _post(
        client, draft_only, "tools/call", {"name": "order_draft_confirm", "arguments": args},
        request_id=denied_id, headers=_identity_headers(draft_only, request_id=denied_id),
    ).json()
    assert _error_reason(denied) == "insufficient_scope"
    tools = _post(client, draft_only, "tools/list").json()["result"]["tools"]
    assert "order_draft_confirm" not in {tool["name"] for tool in tools}
    injected = {
        **args, "tenant_id": 2, "customer_phone": "5511888888888", "price": 1,
        "status": "paid", "confirmed": True, "5511888888888": "untrusted-key",
    }
    assert _error_reason(_draft_call(confirmation, "confirm", injected, "authority")) == "invalid_arguments"
    with confirmation[1]() as db:
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="authority").one()
        assert audit.argument_keys_json == ["confirmation_token", "draft_id", "idempotency_key"]
    _assert_no_confirmation(confirmation)


@pytest.mark.parametrize(("change", "error"), [
    ("price", "quote_changed"), ("modifier_price", "quote_changed"),
    ("item_disabled", "item_not_found"), ("modifier_disabled", "invalid_modifiers"),
    ("modifier_removed", "invalid_modifiers"), ("closed", "checkout_rejected"),
    ("inactive", "checkout_rejected"), ("draft_expired", "draft_expired"),
    ("payment", "quote_changed"), ("version", "quote_changed"),
    ("draft_item", "quote_changed"), ("fee", "quote_changed"),
])
def test_confirmation_revalidates_quote_and_availability(confirmation, change, error):
    address = {"zip": "01001000", "street": "Rua A", "number": "10", "neighborhood": "Centro", "city": "São Paulo", "state": "SP"}
    _, args = _quote_for_confirmation(confirmation, address=address if change == "fee" else None)
    if change == "draft_item":
        _data(_draft_call(confirmation, "add_item", {
            "draft_id": args["draft_id"], "idempotency_key": "new-explicit-line-01", "item_id": 100,
        }, "edit-after-quote"))
    else:
        with confirmation[1].begin() as db:
            item = db.get(MenuItem, 100)
            option = db.get(ModifierOption, 400)
            tenant = db.get(Tenant, 1)
            draft = db.query(WazzaOrderDraft).filter_by(public_id=args["draft_id"]).one()
            if change == "price":
                item.price_cents += 100
            elif change == "modifier_price":
                option.price_delta += Decimal("1.00")
            elif change == "item_disabled":
                item.active = False
            elif change == "modifier_disabled":
                option.is_active = False
            elif change == "modifier_removed":
                db.delete(option)
            elif change == "closed":
                tenant.manual_open_status = False
            elif change == "inactive":
                tenant.is_active = False
            elif change == "draft_expired":
                draft.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            elif change == "payment":
                draft.payment_json = {"method": "cash"}
            elif change == "version":
                draft.version += 1
            elif change == "fee":
                tenant.delivery_fee += Decimal("1.00")
    assert _error_reason(_draft_call(confirmation, "confirm", args, "revalidation")) == error
    _assert_no_confirmation(confirmation)


def test_confirmation_rejects_expired_token_and_accepts_a_new_quote(confirmation, monkeypatch):
    from app.services import wazza_mcp_confirmation as service

    monkeypatch.setattr(service, "QUOTE_TTL_SECONDS", 0)
    _, args = _quote_for_confirmation(confirmation)
    assert _error_reason(_draft_call(confirmation, "confirm", args, "expired-token")) == "confirmation_expired"
    _assert_no_confirmation(confirmation)
    monkeypatch.setattr(service, "QUOTE_TTL_SECONDS", 300)
    new_quote = _data(_draft_call(confirmation, "quote", {"draft_id": args["draft_id"]}, "fresh-quote"))["quote"]
    assert "order_id" in _data(_draft_call(confirmation, "confirm", {
        **args, "confirmation_token": new_quote["confirmation_token"],
    }, "new-confirmation"))


def test_confirmation_rejects_invalid_delivery(confirmation):
    address = {"zip": "nao-e-cep", "street": "Rua A", "number": "10", "neighborhood": "Centro", "city": "São Paulo", "state": "SP"}
    _, args = _quote_for_confirmation(confirmation, address=address)
    assert _error_reason(_draft_call(confirmation, "confirm", args, "invalid-address")) == "invalid_delivery_address"
    _assert_no_confirmation(confirmation)


def test_confirmation_rejects_disallowed_payment_under_official_policy(confirmation, monkeypatch):
    monkeypatch.setenv("CHECKOUT_POLICY_ENABLED", "1")
    monkeypatch.setenv("CHECKOUT_POLICY_TENANT_IDS", "1")
    monkeypatch.setattr("app.services.checkout_policy.ENV_NORMALIZED", "test")
    with confirmation[1].begin() as db:
        plan = Plan(code="free", name="Free", active=True)
        db.add(plan)
        db.flush()
        db.add(Subscription(tenant_id=1, plan_id=plan.id, status=SubscriptionStatus.ACTIVE, provider="manual"))
    _, args = _quote_for_confirmation(confirmation, payment="credit_card")
    assert _error_reason(_draft_call(confirmation, "confirm", args, "payment-policy")) == "checkout_rejected"
    _assert_no_confirmation(confirmation)


@pytest.mark.parametrize(("status", "limit"), [(SubscriptionStatus.CANCELED, 100), (SubscriptionStatus.ACTIVE, 1)])
def test_confirmation_enforces_plan_and_monthly_capacity(confirmation, status, limit):
    with confirmation[1].begin() as db:
        plan = Plan(code="test", name="Test", active=True)
        db.add(plan)
        db.flush()
        db.add(PlanEntitlement(plan_id=plan.id, feature_code="orders_monthly", enabled=True, limit_value=limit, reset_period="monthly"))
        db.add(Subscription(tenant_id=1, plan_id=plan.id, status=status, provider="stripe"))
    _, args = _quote_for_confirmation(confirmation)
    assert _error_reason(_draft_call(confirmation, "confirm", args, "plan-guard")) == "checkout_rejected"
    _assert_no_confirmation(confirmation)


def test_confirmation_rolls_back_payment_and_order_on_failure(confirmation, monkeypatch):
    official = public_menu.create_order_payment

    def fail_after_payment(*args, **kwargs):
        official(*args, **kwargs)
        raise RuntimeError("simulated finance failure")

    _, args = _quote_for_confirmation(confirmation)
    with monkeypatch.context() as patch:
        patch.setattr(public_menu, "create_order_payment", fail_after_payment)
        assert _error_reason(_draft_call(confirmation, "confirm", args, "failed-finance")) == "checkout_failed"
    _assert_no_confirmation(confirmation)
    assert "order_id" in _data(_draft_call(confirmation, "confirm", args, "retry-finance"))


def test_concurrent_confirmation_with_distinct_keys_creates_one_order(confirmation):
    _, args = _quote_for_confirmation(confirmation)
    barrier = Barrier(2)

    def confirm(index):
        barrier.wait(timeout=10)
        return _draft_call(confirmation, "confirm", {
            **args, "idempotency_key": f"concurrent-confirmation-{index}",
        }, f"concurrent-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(confirm, (1, 2)))
    assert sum("result" in response for response in responses) == 1
    assert [_error_reason(response) for response in responses if "error" in response] == ["draft_already_confirmed"]
    with confirmation[1]() as db:
        assert db.query(Order).filter_by(channel="wazza_mcp").count() == 1
        assert db.query(OrderPayment).count() == 1


def test_confirmation_uses_delivery_price_and_official_address_fields(confirmation):
    address = {"zip": "01001-000", "street": "Rua A", "number": "10", "neighborhood": "Centro", "city": "São Paulo", "state": "SP"}
    quote, args = _quote_for_confirmation(confirmation, address=address)
    assert quote["delivery_fee_cents"] == 550
    order_id = _data(_draft_call(confirmation, "confirm", args, "delivery-confirm"))["order_id"]
    with confirmation[1]() as db:
        order = db.get(Order, order_id)
        assert order.order_type == "delivery"
        assert order.total_cents == quote["total_cents"] == 6630
        assert order.delivery_address_json["zip"] == "01001-000"
        assert order.delivery_address_json["coordinates"] == {"lat": -23.55, "lng": -46.63}


def test_idempotency_key_cannot_confirm_a_second_draft(confirmation):
    _, first = _quote_for_confirmation(confirmation, label="first")
    _, second = _quote_for_confirmation(confirmation, label="second")
    _data(_draft_call(confirmation, "confirm", first, "confirm-first-draft"))
    assert _error_reason(_draft_call(confirmation, "confirm", second, "confirm-second-draft")) == "idempotency_conflict"
    with confirmation[1]() as db:
        assert db.query(Order).filter_by(channel="wazza_mcp").count() == 1
        assert db.query(OrderPayment).count() == 1


@pytest.fixture
def mutations(confirmation, monkeypatch):
    monkeypatch.setattr(wazza_router.config, "WAZZA_MCP_ORDER_MUTATION_ENABLED", True)
    with confirmation[1].begin() as db:
        db.get(Tenant, 1).points_enabled = False
    return confirmation


def _mutation_call(mcp, action, args, request_id, phone="5511999999999"):
    client, _, token, *_ = mcp
    return _post(
        client, token, "tools/call", {"name": "order_request_" + action, "arguments": args},
        request_id=request_id, headers=_identity_headers(token, request_id=request_id, phone=phone),
    ).json()


def _mutation_order(mcp):
    _, args = _quote_for_confirmation(mcp)
    result = _data(_draft_call(mcp, "confirm", args, "confirm-for-mutation"))
    return result["order_id"]


def _mutation_quote(mcp, order_id, action):
    args = {"order_id": order_id, "idempotency_key": "mutation-customer-00001"}
    if action == "edit":
        args["items"] = [{"item_id": 100, "quantity": 1, "modifier_option_ids": [400]}]
    quote = _data(_mutation_call(mcp, action, args, "mutation-quote"))
    return {**args, "confirmation_token": quote["confirmation_token"]}


@pytest.mark.parametrize("action", ["edit", "cancel"])
def test_wazza_applies_and_replays_safe_mutation(mutations, action):
    from app.models.wazza_mcp import WazzaOrderMutation

    order_id = _mutation_order(mutations)
    args = _mutation_quote(mutations, order_id, action)
    assert _error_reason(_mutation_call(mutations, action, args, "wrong-owner", phone="5511888888888")) == "order_not_found"
    result = _data(_mutation_call(mutations, action, args, "apply-change"))
    assert result["state"] == "applied"
    assert _data(_mutation_call(mutations, action, args, "replay-change")) == result
    with mutations[1]() as db:
        order = db.get(Order, order_id)
        payment = db.query(OrderPayment).filter_by(order_id=order_id).one()
        if action == "edit":
            assert order.total_cents == payment.amount_cents == 3040
            assert payment.status == "pending"
        else:
            assert order.status == "CANCELADO" and payment.status == "canceled"
        assert db.query(CashMovement).count() == 0
        assert db.query(WazzaOrderMutation).count() == 1
        audit = db.query(WazzaMcpAuditLog).filter_by(request_id="apply-change").one()
        assert audit.risk == "destructive"


def test_wazza_operator_authorization_then_official_verification(mutations):
    from app.services.wazza_order_mutations import decide
    from app.services.finance import transition_manual_payment

    order_id = _mutation_order(mutations)
    with mutations[1].begin() as db:
        order = db.get(Order, order_id)
        order.channel = "public_menu"
        payment = db.query(OrderPayment).filter_by(order_id=order_id).one()
        transition_manual_payment(db, order, payment, "paid", user_id=99)
    args = _mutation_quote(mutations, order_id, "cancel")
    result = _data(_mutation_call(mutations, "cancel", args, "queue-change"))
    assert result["state"] == "pending_review"
    with mutations[1].begin() as db:
        first = decide(db, 1, 99, result["request_id"], "approve", "Operador revisou a solicitação")
        assert first["state"] == "manual_resolution"
        assert db.get(Order, order_id).status == "pending"
        assert db.query(OrderPayment).filter_by(order_id=order_id).one().status == "paid"
    with mutations[1].begin() as db:
        order = db.get(Order, order_id)
        payment = db.query(OrderPayment).filter_by(order_id=order_id).one()
        transition_manual_payment(db, order, payment, "refunded", user_id=99, reason="Estorno manual")
        order.status = "CANCELADO"
    with mutations[1].begin() as db:
        verified = decide(db, 1, 99, result["request_id"], "verify", "Conferido no financeiro")
        assert verified["state"] == "applied"
        assert verified["decided_by"] == verified["resolved_by"] == 99
        assert verified["evidence"]["payments"] == [[payment.id, "refunded"]]


def test_wazza_terminal_status_blocks_pending_proposal(mutations):
    order_id = _mutation_order(mutations)
    args = _mutation_quote(mutations, order_id, "cancel")
    with mutations[1].begin() as db:
        db.get(Order, order_id).status = "PRONTO"
    assert _error_reason(_mutation_call(mutations, "cancel", args, "terminal-order")) == "mutation_denied"


def test_wazza_benefits_wait_for_resolution_and_unverified_attempt_fails(mutations):
    from app.services.wazza_order_mutations import decide

    with mutations[1].begin() as db:
        db.get(Tenant, 1).points_enabled = True
    order_id = _mutation_order(mutations)
    args = _mutation_quote(mutations, order_id, "edit")
    result = _data(_mutation_call(mutations, "edit", args, "queue-benefits"))
    with mutations[1].begin() as db:
        review = decide(db, 1, 99, result["request_id"], "approve", "Revisado pela loja")
        assert review["state"] == "manual_resolution"
        assert review["reason"] == "benefits_or_stock"
        assert db.get(Order, order_id).total_cents == 6080
    with mutations[1].begin() as db:
        failed = decide(db, 1, 99, result["request_id"], "verify", "Ainda não houve alteração")
        assert failed["state"] == "failed"
        assert decide(db, 1, 99, result["request_id"], "verify", "Tentativa repetida") == failed
        assert db.get(Order, order_id).total_cents == 6080


def test_wazza_concurrent_cancellation_replays_one_change(mutations):
    order_id = _mutation_order(mutations)
    args = _mutation_quote(mutations, order_id, "cancel")
    barrier = Barrier(2)

    def submit(index):
        barrier.wait(timeout=10)
        return _data(_mutation_call(mutations, "cancel", args, f"concurrent-mutation-{index}"))

    with ThreadPoolExecutor(max_workers=2) as workers:
        first, second = workers.map(submit, (1, 2))
    assert first == second
    with mutations[1]() as db:
        assert db.query(OrderOutbox).filter_by(order_id=order_id, effect="whatsapp.wazza_cancel").count() == 1
        assert db.query(OrderPayment).filter_by(order_id=order_id).one().status == "canceled"


def test_wazza_financial_failure_rolls_back_mutation(mutations, monkeypatch):
    from app.models.wazza_mcp import WazzaOrderMutation
    from app.services import wazza_order_mutations

    order_id = _mutation_order(mutations)
    args = _mutation_quote(mutations, order_id, "cancel")
    transition = wazza_order_mutations.transition_manual_payment

    def fail_after_payment(*args, **kwargs):
        transition(*args, **kwargs)
        raise RuntimeError("failure after payment transition")

    monkeypatch.setattr(wazza_order_mutations, "transition_manual_payment", fail_after_payment)
    assert _error_reason(_mutation_call(mutations, "cancel", args, "rollback-cancel")) == "checkout_failed"
    with mutations[1]() as db:
        assert db.query(WazzaOrderMutation).count() == 0
        assert db.get(Order, order_id).status == "pending"
        assert db.query(OrderPayment).filter_by(order_id=order_id).one().status == "pending"
        assert db.query(OrderOutbox).filter_by(order_id=order_id, effect="whatsapp.wazza_cancel").count() == 0


def test_wazza_review_rejection_keeps_order_and_payment(mutations):
    from fastapi import HTTPException
    from app.services.wazza_order_mutations import decide

    order_id = _mutation_order(mutations)
    with mutations[1].begin() as db:
        db.get(Order, order_id).status = "EM_PREPARO"
    args = _mutation_quote(mutations, order_id, "edit")
    request = _data(_mutation_call(mutations, "edit", args, "rejectable-change"))
    with mutations[1].begin() as db:
        with pytest.raises(HTTPException) as error:
            decide(db, 2, 99, request["request_id"], "reject", "Tenant incorreto")
        assert error.value.status_code == 404
        result = decide(db, 1, 99, request["request_id"], "reject", "Não autorizada pela loja")
        assert result["state"] == "rejected"
        assert db.get(Order, order_id).total_cents == 6080
        assert db.query(OrderPayment).filter_by(order_id=order_id).one().amount_cents == 6080
