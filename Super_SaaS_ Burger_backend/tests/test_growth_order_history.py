from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_billing_phase2 import db
from app.core.database import get_db
from app.deps import require_admin_user
from app.models.order import Order
from app.routers.orders import router
from app.services.order_history import history_page, history_overview


def add_order(db, *, tenant=1, number=1, status="RECEBIDO", name="João", created=None, payment="PIX"):
    order = Order(tenant_id=tenant, daily_order_number=number, status=status,
                  cliente_nome=name, cliente_telefone="11999999999", itens="Item", endereco="",
                  valor_total=1000, total_cents=1000, tipo_entrega="RETIRADA", forma_pagamento=payment,
                  created_at=created or datetime(2026, 10, 23, 12))
    db.add(order)
    db.flush()
    return order


def test_bounded_pages_have_stable_ties_and_do_not_leak_tenants(db):
    ids = [add_order(db, number=i).id for i in range(1, 24)]
    add_order(db, tenant=2)
    db.commit()
    seen = []
    for page in range(1, 4):
        rows, total = history_page(db, 1, page=page)
        assert total == 23 and len(rows) <= 8
        assert all(row.tenant_id == 1 for row in rows)
        seen.extend(row.id for row in rows)
    assert seen == list(reversed(ids)) and len(set(seen)) == 23


def test_filters_cover_history_not_only_the_current_page(db):
    target = add_order(db, number=77, name="José da Silva", status="PREPARANDO", payment="DINHEIRO")
    for i in range(20):
        add_order(db, number=i, name="Outro", status="ENTREGUE")
    db.commit()
    rows, count = history_page(db, 1, customer="jose", order_number="77", status="EM_PREPARO",
        payment="DINHEIRO", delivery="RETIRADA", created_on=date(2026, 10, 23))
    assert count == 1 and rows[0].id == target.id
    assert history_page(db, 1, customer="%")[1] == 0
    assert history_page(db, 1, customer="_")[1] == 0
    assert history_page(db, 1, created_on=date(2026, 10, 22))[1] == 0


def test_summary_uses_entire_tenant_history_and_browser_day(db):
    add_order(db, status="ENTREGUE", created=datetime(2026, 10, 22))
    add_order(db, created=datetime(2026, 10, 23, 2, 59))  # Previous day in UTC-3.
    add_order(db, status="PREPARING", created=datetime(2026, 10, 23, 3))
    add_order(db, status="IN_TRANSIT", created=datetime(2026, 10, 24, 2, 59))
    add_order(db, tenant=2, status="ENTREGUE")
    db.commit()
    result = history_overview(db, 1, today=date(2026, 10, 23), utc_offset_minutes=180)
    assert result["total"] == 4
    assert result["summary"] == dict(today=2, pending=1, preparing=1, delivering=1, completed=1)
    assert result["payments"] == ["PIX"] and result["deliveries"] == ["RETIRADA"]
    assert history_page(db, 1, page_size=1)[1] == 4


def test_api_requires_auth_and_validates_bounds_and_cross_tenant(db):
    add_order(db)
    add_order(db, tenant=2)
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/api/orders/1/search").status_code in (401, 403)
        app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(id=1, tenant_id=1, role="owner")
        result = client.get("/api/orders/1/search?page_size=1")
        assert result.status_code == 200 and len(result.json()["items"]) == 1
        assert client.get("/api/orders/2/search").status_code == 403
        assert client.get("/api/orders/2/overview?today=2026-10-23").status_code == 403
        for query in ("page_size=101", "page=0", "created_on=bad", "customer=" + "x" * 121):
            assert client.get("/api/orders/1/search?" + query).status_code == 422


def test_empty_overview_and_pages(db):
    assert history_page(db, 1) == ([], 0)
    result = history_overview(db, 1, today=date(2026, 10, 23))
    assert result["total"] == 0 and not any(result["summary"].values())
    assert result["payments"] == result["deliveries"] == []
