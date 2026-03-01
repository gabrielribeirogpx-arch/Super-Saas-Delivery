from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers.orders import OrderCreate, StatusUpdate, create_order, update_status
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
        self._option_id = None

    def filter(self, expr, *_args, **_kwargs):
        self._option_id = getattr(getattr(expr, "right", None), "value", None)
        return self

    def first(self):
        return self._options_by_id.get(self._option_id)


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
            100: SimpleNamespace(id=100, group_id=10, name="Grande", price_delta=3.5),
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
            "price": 3.5,
            "price_cents": 350,
            "option_id": 100,
            "group_id": 10,
        }
    ]
