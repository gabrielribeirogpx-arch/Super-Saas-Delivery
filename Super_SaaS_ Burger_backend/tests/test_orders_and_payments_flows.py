from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers.orders import (
    OrderCreate,
    StatusUpdate,
    complete_delivery_order,
    create_order,
    start_delivery_order,
    update_status,
)
from app.routers.payments import _ensure_order
from app.services.orders import create_order_items
from tests.fixtures_data import HAPPY_PATH_ORDER_PAYLOAD, PAYMENT_ACCESS_DENIED


class FakeOrdersDb:
    def __init__(self):
        self.order = None
        self.committed = False

    def add(self, order):
        self.order = order

    def flush(self):
        self.order.id = 123

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None

    def rollback(self):
        return None


class FakeUpdateStatusQuery:
    def __init__(self, order):
        self._order = order

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._order


class FakeUpdateStatusDb:
    def __init__(self, order):
        self._order = order
        self.committed = False

    def query(self, _model):
        return FakeUpdateStatusQuery(self._order)

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None


class FakeEnsureOrderQuery:
    def __init__(self, order):
        self._order = order

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._order


class FakeEnsureOrderDb:
    def __init__(self, order):
        self._order = order

    def query(self, _model):
        return FakeEnsureOrderQuery(self._order)


def test_create_order_happy_path_persists_and_returns_order():
    db = FakeOrdersDb()
    payload = OrderCreate(**HAPPY_PATH_ORDER_PAYLOAD)

    with (
        patch("app.routers.orders.create_order_items"),
        patch("app.routers.orders.maybe_create_payment_for_order"),
        patch("app.routers.orders.emit_order_created"),
        patch("app.routers.orders.auto_print_if_possible"),
        patch("app.routers.orders.get_print_settings", return_value={}),
    ):
        response = create_order(tenant_id=1, payload=payload, db=db)

    assert db.committed is True
    assert response["id"] == 123
    assert response["status"] == "RECEBIDO"
    assert response["tenant_id"] == 1
    assert response["total_cents"] > 0


def test_update_order_status_happy_path_changes_status():
    order = SimpleNamespace(id=10, status="RECEBIDO")
    db = FakeUpdateStatusDb(order)
    background = BackgroundTasks()

    result = update_status(
        order_id=10,
        body=StatusUpdate(status="pronto"),
        background_tasks=background,
        db=db,
    )

    assert db.committed is True
    assert result["ok"] is True
    assert result["status"] == "PRONTO"
    assert order.status == "PRONTO"


def test_ensure_order_denies_cross_tenant_access():
    order = SimpleNamespace(id=99, tenant_id=PAYMENT_ACCESS_DENIED["order_tenant_id"])
    db = FakeEnsureOrderDb(order)
    user = SimpleNamespace(id=7, tenant_id=PAYMENT_ACCESS_DENIED["user_tenant_id"])

    with pytest.raises(HTTPException) as exc:
        _ensure_order(db, order_id=99, user=user)

    assert exc.value.status_code == PAYMENT_ACCESS_DENIED["expected_status_code"]
    assert exc.value.detail == PAYMENT_ACCESS_DENIED["expected_detail"]


class FakeMenuItemRowsQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return []


class FakeModifierOptionQuery:
    def __init__(self, options_by_id):
        self._options_by_id = options_by_id
        self._filters = {}

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *expressions, **_kwargs):
        for expr in expressions:
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            if left is None or right is None:
                continue
            column_name = getattr(left, "name", None)
            value = getattr(right, "value", None)
            if column_name is not None and value is not None:
                self._filters[column_name] = value
        return self

    def first(self):
        option_id = self._filters.get("id")
        group_id = self._filters.get("group_id")
        tenant_id = self._filters.get("tenant_id")
        option = self._options_by_id.get(option_id)
        if not option:
            return None
        if group_id is not None and option.group_id != group_id:
            return None
        if tenant_id is not None and option.tenant_id != tenant_id:
            return None
        return option


class FakeCreateItemsDb:
    def __init__(self, options_by_id):
        self.options_by_id = options_by_id

    def query(self, *entities):
        if len(entities) == 2:
            return FakeMenuItemRowsQuery()
        return FakeModifierOptionQuery(self.options_by_id)

    def add(self, _obj):
        return None


def test_create_order_items_resolves_selected_modifiers_internally():
    db = FakeCreateItemsDb(
        {
            100: SimpleNamespace(id=100, group_id=10, tenant_id=1, name="Grande", price_delta=3.5),
        }
    )

    created = create_order_items(
        db,
        tenant_id=1,
        order_id=321,
        items_structured=[
            {
                "menu_item_id": 1,
                "name": "X-Burger",
                "quantity": 2,
                "unit_price_cents": 2500,
                "subtotal_cents": 5700,
                "selected_modifiers": [{"group_id": 10, "option_id": 100}],
            }
        ],
    )

    assert created[0].modifiers == [
        {
            "name": "Grande",
            "price_delta": 3.5,
            "price_cents": 350,
            "option_id": 100,
            "group_id": 10,
        }
    ]


def test_create_order_items_keeps_modifiers_empty_when_selection_is_invalid():
    db = FakeCreateItemsDb(
        {
            100: SimpleNamespace(id=100, group_id=10, tenant_id=2, name="Grande", price_delta=3.5),
        }
    )

    created = create_order_items(
        db,
        tenant_id=1,
        order_id=321,
        items_structured=[
            {
                "menu_item_id": 1,
                "name": "X-Burger",
                "quantity": 1,
                "unit_price_cents": 2500,
                "subtotal_cents": 2500,
                "selected_modifiers": [{"group_id": 10, "option_id": 100}],
            }
        ],
    )

    assert created[0].modifiers == []


def test_create_order_items_preserves_payload_modifiers_when_selection_lookup_fails():
    db = FakeCreateItemsDb({})

    created = create_order_items(
        db,
        tenant_id=1,
        order_id=321,
        items_structured=[
            {
                "menu_item_id": 1,
                "name": "X-Burger",
                "quantity": 1,
                "unit_price_cents": 2500,
                "subtotal_cents": 2500,
                "selected_modifiers": [{"group_id": 10, "option_id": 100}],
                "modifiers": [
                    {
                        "group_id": 10,
                        "option_id": 100,
                        "group_name": "Tamanho",
                        "option_name": "Grande",
                        "name": "Grande",
                        "price_cents": 350,
                    }
                ],
            }
        ],
    )

    assert created[0].modifiers == [
        {
            "group_id": 10,
            "option_id": 100,
            "group_name": "Tamanho",
            "option_name": "Grande",
            "name": "Grande",
            "price_delta": 3.5,
            "price_cents": 350,
        }
    ]


def test_create_order_items_does_not_share_modifier_references_with_payload():
    db = FakeCreateItemsDb({})
    payload_modifier = {
        "group_id": 10,
        "option_id": 100,
        "group_name": "Tamanho",
        "option_name": "Grande",
        "name": "Grande",
        "price_cents": 350,
    }

    created = create_order_items(
        db,
        tenant_id=1,
        order_id=321,
        items_structured=[
            {
                "menu_item_id": 1,
                "name": "X-Burger",
                "quantity": 1,
                "unit_price_cents": 2500,
                "subtotal_cents": 2500,
                "modifiers": [payload_modifier],
            }
        ],
    )

    payload_modifier["name"] = "Mutado"
    assert created[0].modifiers[0]["name"] == "Grande"


class FakeDeliveryQuery:
    def __init__(self, order):
        self._order = order

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._order


class FakeDeliveryDb:
    def __init__(self, order):
        self._order = order
        self.committed = False

    def query(self, _model):
        return FakeDeliveryQuery(self._order)

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None


def test_start_delivery_changes_status_from_ready():
    order = SimpleNamespace(id=50, tenant_id=1, status="READY")
    db = FakeDeliveryDb(order)

    with (
        patch("app.routers.orders.require_admin_tenant_access"),
        patch("app.routers.orders.emit_order_status_changed"),
    ):
        result = start_delivery_order(request=SimpleNamespace(), order_id=50, tenant_id=1, db=db, user=SimpleNamespace(id=1))

    assert db.committed is True
    assert result["ok"] is True
    assert result["status"] == "OUT_FOR_DELIVERY"
    assert order.status == "OUT_FOR_DELIVERY"


def test_complete_delivery_changes_status_from_out_for_delivery():
    order = SimpleNamespace(id=51, tenant_id=1, status="OUT_FOR_DELIVERY")
    db = FakeDeliveryDb(order)

    with (
        patch("app.routers.orders.require_admin_tenant_access"),
        patch("app.routers.orders.emit_order_status_changed"),
    ):
        result = complete_delivery_order(request=SimpleNamespace(), order_id=51, tenant_id=1, db=db, user=SimpleNamespace(id=1))

    assert db.committed is True
    assert result["ok"] is True
    assert result["status"] == "DELIVERED"
    assert order.status == "DELIVERED"


def test_start_delivery_requires_ready_status():
    order = SimpleNamespace(id=52, tenant_id=1, status="RECEBIDO")
    db = FakeDeliveryDb(order)

    with (
        patch("app.routers.orders.require_admin_tenant_access"),
        pytest.raises(HTTPException) as exc,
    ):
        start_delivery_order(request=SimpleNamespace(), order_id=52, tenant_id=1, db=db, user=SimpleNamespace(id=1))

    assert exc.value.status_code == 409
