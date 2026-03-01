from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers.orders import OrderCreate, StatusUpdate, create_order, update_status
from app.routers.payments import _ensure_order
from tests.fixtures_data import HAPPY_PATH_ORDER_PAYLOAD, PAYMENT_ACCESS_DENIED


class FakeOrdersDb:
    def __init__(self, option=None):
        self.order = None
        self.committed = False
        self.option = option

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

    def query(self, _model):
        return FakeModifierOptionQuery(self.option)


class FakeModifierOptionQuery:
    def __init__(self, option):
        self.option = option

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.option


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


def test_create_order_converts_selected_modifiers_before_persisting():
    option = SimpleNamespace(id=1, group_id=1, name="Bacon", price_delta=3)
    db = FakeOrdersDb(option=option)
    payload = OrderCreate(
        cliente_nome="João",
        cliente_telefone="11999990000",
        itens=[
            {
                "menu_item_id": 101,
                "nome": "Burger Classic",
                "qtd": 1,
                "preco": 18.5,
                "selected_modifiers": [{"group_id": 1, "option_id": 1}],
            }
        ],
        endereco="Rua Principal, 100",
        observacao="",
        tipo_entrega="delivery",
        forma_pagamento="pix",
        valor_total=21.5,
    )

    with (
        patch("app.routers.orders.create_order_items") as create_items_mock,
        patch("app.routers.orders.maybe_create_payment_for_order"),
        patch("app.routers.orders.emit_order_created"),
        patch("app.routers.orders.auto_print_if_possible"),
        patch("app.routers.orders.get_print_settings", return_value={}),
    ):
        create_order(tenant_id=1, payload=payload, db=db)

    items_structured = create_items_mock.call_args.kwargs["items_structured"]
    assert items_structured[0]["modifiers"] == [
        {"name": "Bacon", "price": 3.0, "price_cents": 300, "group_id": 1, "option_id": 1}
    ]
