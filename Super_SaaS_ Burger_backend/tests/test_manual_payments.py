"""Manual collection is an authenticated accounting action, never a native charge."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.finance import CashMovement, OrderPayment
from app.models.inventory import InventoryItem, MenuItemIngredient, InventoryMovement
from app.models.menu_item import MenuItem
from app.models.native_payment import NativePaymentIntent
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.tenant import Tenant
from app.routers import payments, finance


@pytest.fixture
def scenario():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([Tenant(id=1, slug="alpha"), Tenant(id=2, slug="beta")])
    db.add_all([AdminUser(id=1, tenant_id=1, email="owner@test", name="Operador", password_hash="test", role="owner"), AdminUser(id=2, tenant_id=2, email="other@test", name="Outro", password_hash="test", role="owner")])
    db.flush()
    db.add_all([Order(id=1, tenant_id=1, daily_order_number=4, cliente_telefone="test", itens="Burger", total_cents=2990, status="DELIVERED", payment_method="money"), Order(id=2, tenant_id=2, cliente_telefone="test", itens="Other", total_cents=2990, payment_method="pix")])
    db.flush()
    db.add_all([OrderPayment(id=1, tenant_id=1, order_id=1, method="cash", amount_cents=2990, fee_cents=0, status="pending"), OrderPayment(id=2, tenant_id=2, order_id=2, method="pix", amount_cents=2990, fee_cents=0, status="pending")])
    db.commit()
    actor = SimpleNamespace(user=db.get(AdminUser, 1))
    app = FastAPI(); app.include_router(payments.router); app.include_router(finance.router)
    app.dependency_overrides[get_db] = lambda: db
    def current_user():
        if actor.user is None: raise HTTPException(401, "Sem sessão")
        return actor.user
    app.dependency_overrides[require_admin_user] = current_user
    @app.middleware("http")
    async def tenant_context(request, call_next):
        request.state.tenant = db.get(Tenant, 1)
        return await call_next(request)
    yield SimpleNamespace(db=db, client=TestClient(app, raise_server_exceptions=False), actor=actor)
    db.close(); engine.dispose()


def confirm(s, status="paid", payment_id=1, order_id=1):
    return s.client.post(f"/api/orders/{order_id}/payments/{payment_id}/status", json={"status": status, "amount_cents": 1, "tenant_id": 2})


def listing(s, **params):
    return s.client.get("/api/finance/manual-payments", params={"from": "2020-01-01", "to": "2099-12-31", **params})


@pytest.mark.parametrize("role", ["owner", "admin", "cashier"])
@pytest.mark.parametrize("method", ["cash", "money", "pix", "card"])
def test_confirm_once_with_audit_and_server_amount(scenario, role, method):
    s=scenario; s.actor.user.role=role; s.db.get(OrderPayment, 1).method=method; s.db.commit()
    r=confirm(s); assert r.status_code==200, r.text
    first=r.json(); assert first["paid_at"] and first["status"]=="paid"
    assert confirm(s).json()["paid_at"]==first["paid_at"]
    movement=s.db.query(CashMovement).one()
    assert (movement.type, movement.category, movement.amount_cents)==("in", "sale", 2990)
    audit=s.db.query(AdminAuditLog).one()
    assert audit.user_id==1 and audit.tenant_id==1 and audit.action=="confirm_manual_payment"
    assert json.loads(audit.meta_json)["amount_cents"]==2990
    assert s.db.get(Order, 1).status=="DELIVERED"
    entry=listing(s,status="paid").json()["items"][0]
    assert entry["confirmed_by"]=="Operador" and not entry["can_confirm"] and entry["order_number"]==4


@pytest.mark.parametrize("role", ["operator", "delivery", "driver", "kitchen", "viewer"])
def test_role_denied_for_list_and_confirmation(scenario,role):
    s=scenario; s.actor.user.role=role; s.db.commit()
    assert confirm(s).status_code==403
    assert listing(s).status_code==403
    assert s.db.query(CashMovement).count()==0


def test_no_session(scenario):
    scenario.actor.user=None
    assert confirm(scenario).status_code==401
    assert listing(scenario).status_code==401


def test_cross_tenant_and_payment_id_cannot_be_substituted(scenario):
    s=scenario
    assert confirm(s,payment_id=2,order_id=2).status_code==403
    assert confirm(s,payment_id=2,order_id=1).status_code==404
    assert listing(s,tenant_id=2).status_code==403
    result=listing(s).json(); assert result["total"]==1 and result["pending_cents"]==2990
    assert result["items"][0]["order_id"]==1
    assert s.db.query(CashMovement).count()==0


@pytest.mark.parametrize("state", ["CANCELED", "cancelado", "CANCELLED"])
def test_canceled_order_cannot_be_collected(scenario,state):
    s=scenario; s.db.get(Order,1).status=state;s.db.commit()
    assert confirm(s).status_code==409
    assert listing(s).json()["items"][0]["can_confirm"] is False
    assert s.db.query(CashMovement).count()==0


@pytest.mark.parametrize("state", ["canceled", "refunded"])
def test_terminal_payment_cannot_be_reopened(scenario,state):
    s=scenario;s.db.get(OrderPayment,1).status=state;s.db.commit()
    assert confirm(s).status_code==409
    assert confirm(s,status="pending").status_code==409
    assert s.db.query(CashMovement).count()==0


def test_paid_cannot_go_back_pending_or_be_refunded_twice(scenario):
    s=scenario;assert confirm(s).status_code==200
    assert confirm(s,status="pending").status_code==409
    assert confirm(s,status="refunded").status_code==200
    assert confirm(s,status="refunded").status_code==200
    assert confirm(s,status="paid").status_code==409
    assert s.db.query(CashMovement).filter_by(category="refund").count()==1
    assert s.db.query(CashMovement).count()==2
    assert s.db.query(AdminAuditLog).count()==2


def test_pending_cannot_generate_refund_without_receipt(scenario):
    assert confirm(scenario,status="refunded").status_code==409
    assert scenario.db.query(CashMovement).count()==0


@pytest.mark.parametrize("native_source", ["method", "order", "intent"])
def test_native_payments_cannot_be_confirmed_or_created_manually(scenario,native_source):
    s=scenario
    if native_source=="method": s.db.get(OrderPayment,1).method="native_pix"
    elif native_source=="order": s.db.get(Order,1).payment_method="native_card"
    else:
        s.db.add(NativePaymentIntent(tenant_id=1,order_id=1,public_id="sim",total_cents=2990,platform_fee_cents=0,merchant_before_psp_cents=2990,snapshot={},snapshot_hash="0"*64))
    s.db.commit()
    assert confirm(s).status_code==409
    r=s.client.post("/api/orders/1/payments",json={"method":"native_pix","amount_cents":2990})
    assert r.status_code==400
    assert s.db.query(CashMovement).count()==0


def test_duplicate_payment_registration_cannot_double_allocate(scenario):
    s=scenario
    r=s.client.post("/api/orders/1/payments",json={"method":"cash","amount_cents":2990})
    assert r.status_code==400
    assert s.db.query(OrderPayment).filter_by(order_id=1).count()==1


def test_confirmation_audit_failure_rolls_back_all_financial_writes(scenario,monkeypatch):
    import app.services.admin_audit as audit
    def broken(*args,**kwargs): raise RuntimeError("audit unavailable")
    monkeypatch.setattr(audit,"log_admin_action",broken)
    assert confirm(scenario).status_code==500
    scenario.db.expire_all()
    p=scenario.db.get(OrderPayment,1)
    assert p.status=="pending" and p.paid_at is None
    assert scenario.db.query(CashMovement).count()==0


def test_confirm_deducts_stock_only_once(scenario):
    s=scenario
    s.db.add(MenuItem(id=1,tenant_id=1,name="Burger",price_cents=2990));s.db.flush()
    s.db.add(InventoryItem(id=1,tenant_id=1,name="Pão",unit="un",current_stock=10,min_stock_level=0));s.db.flush()
    s.db.add(MenuItemIngredient(tenant_id=1,menu_item_id=1,inventory_item_id=1,quantity=1))
    s.db.add(OrderItem(order_id=1,tenant_id=1,menu_item_id=1,name="Burger",quantity=2,unit_price_cents=1495,subtotal_cents=2990));s.db.commit()
    assert confirm(s).status_code==200
    assert confirm(s).status_code==200
    assert s.db.get(InventoryItem,1).current_stock==8
    assert s.db.query(InventoryMovement).count()==1


def test_listing_pagination_date_and_totals(scenario):
    s=scenario
    s.db.add(OrderPayment(tenant_id=1,order_id=1,method="pix",amount_cents=100,status="canceled",created_at=datetime(2020,1,1)))
    s.db.commit()
    r=listing(s,status="all",limit=1).json()
    assert r["total"]==2 and len(r["items"])==1 and r["pending_cents"]==2990 and r["paid_cents"]==0
    assert listing(s,status="all",offset=1,limit=1).json()["items"][0]["status"]=="canceled"
    assert listing(s,**{"from":"2020-01-02","to":"2020-02-01"}).json()["total"]==0
    assert listing(s,**{"from":"2025-01-01","to":"2024-01-01"}).status_code==400
    assert listing(s,status="anything").status_code==400
