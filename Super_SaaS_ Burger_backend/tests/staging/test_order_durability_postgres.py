"""Public HTTP retries, leases and atomic effects on owned PostgreSQL schemas."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.customer_stats import CustomerStats
from app.models.order_durability import OrderSubmission, OrderOutbox, OrderEffectReceipt
from app.services.subscriptions import SubscriptionService
from app.services.order_outbox import enqueue_order_created, enqueue_order_status_changed
from app.services import order_outbox_worker as worker
from app.routers import public_menu

KEY = "synthetic-attempt-key-0000000000000001"


def setup(pg, monkeypatch, *, capacity=1):
    _, _, sessions = pg
    now = datetime.now(timezone.utc)
    with sessions() as db, db.begin():
        plan = db.query(Plan).filter_by(code="pro").one()
        db.query(PlanEntitlement).filter_by(plan_id=plan.id, feature_code="orders_monthly").one().limit_value = capacity
        for tenant in (1, 2):
            sub = SubscriptionService(db).create_subscription(tenant, plan.id, provider="hotmart")
            SubscriptionService(db).activate_subscription(tenant, sub.id, current_period_end=now + timedelta(days=30))
            db.add(MenuItem(id=tenant, tenant_id=tenant, name=f"Synthetic {tenant}", price_cents=1500))
    async def geocode(_):
        await asyncio.sleep(.05)
        return -23.5, -46.6
    monkeypatch.setattr(public_menu, "geocode_address", geocode)
    app = FastAPI()
    app.include_router(public_menu.router)
    def session_dep():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = session_dep
    @app.middleware("http")
    async def tenant(request, next_call):
        with sessions() as db:
            request.state.tenant = db.get(Tenant, int(request.query_params.get("store", "1")))
        return await next_call(request)
    return sessions, app


def body(tenant=1, **changes):
    return dict(customer_name="Pessoa sintética", customer_phone=f"1199999000{tenant}",
        order_type="pickup", delivery_type="RETIRADA", payment_method="money",
        street="Rua A", number="1", city="São Paulo", items=[{"item_id": tenant, "quantity": 1}], **changes)


def post(app, data=None, key=KEY, tenant=1):
    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://local.test") as client:
            return await client.post(f"/public/orders?store={tenant}", json=data or body(tenant),
                headers={"Idempotency-Key": key} if key is not None else {})
    return asyncio.run(call())


def test_pg_concurrent_http_retries_and_lost_response_consume_one_quota(pg, monkeypatch):
    sessions, app = setup(pg, monkeypatch)
    async def parallel():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://local.test") as client:
            return await asyncio.gather(*(client.post("/public/orders", json=body(),
                headers={"Idempotency-Key": KEY}) for _ in range(2)))
    responses = asyncio.run(parallel())
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    # New HTTP client/process, now with exhausted capacity: still replay success.
    replayed = post(app)
    assert replayed.status_code == 200 and replayed.json() == responses[0].json()
    assert post(app, key=KEY + "2").status_code == 403
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == db.query(OrderOutbox).count() == 1


def test_pg_same_key_different_body_conflicts_and_cross_store_reuse_is_scoped(pg, monkeypatch):
    sessions, app = setup(pg, monkeypatch)
    assert post(app).status_code == 200
    assert post(app, body(notes="changed")).status_code == 409
    assert post(app, tenant=2).status_code == 200
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == 2
        assert {row.tenant_id for row in db.query(OrderOutbox)} == {1, 2}
    assert post(app, key="short").status_code == 422


def test_pg_concurrent_distinct_attempts_preserve_numbering_without_fk_lock_deadlock(pg, monkeypatch):
    sessions, app = setup(pg, monkeypatch, capacity=2)
    async def parallel():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://local.test") as client:
            return await asyncio.gather(*(client.post("/public/orders", json=body(customer_email=f"synthetic{i}@example.test"),
                headers={"Idempotency-Key": KEY + str(i)}) for i in range(2)))
    results = asyncio.run(parallel())
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert {r.json()["daily_order_number"] for r in results} == {1, 2}
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == db.query(OrderOutbox).count() == 2


def test_pg_multiple_consumers_claim_distinct_jobs_and_recover_expired_owner(pg, monkeypatch):
    sessions, app = setup(pg, monkeypatch, capacity=3)
    assert post(app).status_code == 200
    assert post(app, tenant=2).status_code == 200
    now = datetime.now(timezone.utc) + timedelta(seconds=1)
    barrier = Barrier(2)
    def claim():
        barrier.wait(timeout=5)
        return worker.claim_one(sessions, now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = [f.result(timeout=10) for f in [pool.submit(claim), pool.submit(claim)]]
    assert all(claims) and len({claim.id for claim in claims}) == 2
    assert worker.claim_one(sessions, now) is None
    sent = []
    monkeypatch.setattr(worker, "send_whatsapp_message", lambda db, **kw: sent.append(kw["order_id"]) or SimpleNamespace(status="sent", error=None))
    later = now + worker.LEASE + timedelta(seconds=1)
    assert worker.run_cycle(sessions, clock=lambda: later)["done"] == 2
    assert len(sent) == len(set(sent)) == 2
    for stale in claims:
        assert worker.dispatch(sessions, stale, lambda: later) is False
    with sessions() as db:
        assert db.query(OrderOutbox).filter_by(status="done").count() == 2


def test_pg_receipts_and_stats_rollback_together_on_ack_failure(pg, monkeypatch):
    sessions, app = setup(pg, monkeypatch)
    assert post(app).status_code == 200
    monkeypatch.setattr(worker, "send_whatsapp_message", lambda *a, **kw: SimpleNamespace(status="sent", error=None))
    with sessions() as db, db.begin():
        order = db.query(Order).one()
        order.status = "DELIVERED"
        enqueue_order_status_changed(db, order, "OUT_FOR_DELIVERY")
    original = worker._done
    def broken(db, claim, now):
        if claim.effect == "customer.delivered":
            raise RuntimeError("synthetic crash before acknowledgement")
        return original(db, claim, now)
    monkeypatch.setattr(worker, "_done", broken)
    now = datetime.now(timezone.utc) + timedelta(seconds=1)
    assert worker.run_cycle(sessions, clock=lambda: now)["retry"] == 1
    with sessions() as db:
        assert db.query(CustomerStats).count() == 0
        assert db.query(OrderEffectReceipt).filter_by(effect_key="customer.delivered").count() == 0
    monkeypatch.setattr(worker, "_done", original)
    later = now + timedelta(minutes=1)
    assert worker.run_cycle(sessions, clock=lambda: later)["done"] == 1
    with sessions() as db:
        assert db.query(CustomerStats).one().total_orders == 1
        assert db.query(OrderEffectReceipt).filter_by(effect_key="customer.delivered").count() == 1


def test_pg_order_scope_fk_rejects_queue_and_receipt_for_another_tenant(pg, monkeypatch):
    sessions, app = setup(pg, monkeypatch)
    assert post(app).status_code == 200
    with sessions() as db:
        order_id = db.query(Order.id).scalar()
    for value in (OrderOutbox(tenant_id=2, order_id=order_id, event_key="x" * 32,
                            effect="customer.delivered", stream="stats", payload={"status": "ENTREGUE"}),
                  OrderEffectReceipt(tenant_id=2, order_id=order_id, effect_key="customer.delivered")):
        with sessions() as db:
            db.add(value)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
