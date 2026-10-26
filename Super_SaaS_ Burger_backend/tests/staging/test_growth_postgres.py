"""Owned loopback PostgreSQL only; no external calls, messages or payments."""
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException

from sqlalchemy import select, text
from app.models.tenant import Tenant
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.services.subscriptions import SubscriptionService
from app.routers import public_menu
from app.services.order_history import history_page, history_overview


@pytest.mark.parametrize("capacity", [1, 2])
def test_pg_public_orders_wait_for_quota_without_blocking_event_loop(pg, monkeypatch, capacity):
    _, _, sessions = pg
    now = datetime.now(timezone.utc)
    with sessions() as db, db.begin():
        plan = db.query(Plan).filter_by(code="pro").one()
        db.query(PlanEntitlement).filter_by(plan_id=plan.id, feature_code="orders_monthly").one().limit_value = capacity
        service = SubscriptionService(db)
        sub = service.create_subscription(1, plan.id, provider="hotmart")
        service.activate_subscription(1, sub.id, current_period_end=now + timedelta(days=30))
        item = MenuItem(tenant_id=1, name="Synthetic item", price_cents=1500, active=True)
        db.add(item)
        db.flush()
        item_id = item.id
    async def scenario():
        entered_geo = 0
        geocoding_ready = asyncio.Event()
        finish_geocoding = asyncio.Event()
        async def geocode(_):
            nonlocal entered_geo
            entered_geo += 1
            if entered_geo == 2:
                geocoding_ready.set()
            await finish_geocoding.wait()
            return -23.5, -46.6
        monkeypatch.setattr(public_menu, "geocode_address", geocode)
        first, second, blocker = sessions(), sessions(), sessions()
        tasks = []
        try:
            tenants = [first.get(Tenant, 1), second.get(Tenant, 1)]
            for session in (first, second):
                session.execute(text("SET LOCAL lock_timeout = '3s'"))
            for i, (session, tenant) in enumerate(zip((first, second), tenants)):
                payload = public_menu.PublicOrderPayload(customer_name=f"Synthetic {i}", customer_phone=f"1198888000{i}",
                    order_type="pickup", delivery_type="RETIRADA", payment_method="money",
                    street="Rua A", number="1", city="São Paulo", items=[{"item_id": item_id, "quantity": 1}])
                tasks.append(asyncio.create_task(public_menu._create_order_for_tenant(session, tenant, payload)))
            await asyncio.wait_for(geocoding_ready.wait(), 3)
            # While geocoding is in flight, this lock must still be obtainable.
            blocker.execute(select(Tenant).where(Tenant.id == 1).with_for_update(nowait=True)).scalar_one()
            finish_geocoding.set()
            # Both persistence calls may now wait for this lock, but the ASGI
            # loop must remain responsive to an unrelated request.
            assert await asyncio.wait_for(asyncio.sleep(.1, result="alive"), .5) == "alive"
            blocker.commit()
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
            saved = [result for result in results if not isinstance(result, BaseException)]
            rejected = [result for result in results if isinstance(result, BaseException)]
            assert {result.daily_order_number for result in saved} == set(range(1, capacity + 1))
            assert len(rejected) == 2 - capacity
            assert all(isinstance(result, HTTPException) and result.status_code == 403 for result in rejected)
        finally:
            blocker.rollback()
            finish_geocoding.set()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for session in (first, second, blocker):
                session.close()
    asyncio.run(scenario())
    with sessions() as db:
        assert db.query(Order).filter_by(tenant_id=1).count() == capacity
        assert db.query(Order).filter_by(tenant_id=2).count() == 0
        assert all(row.customer_lat == -23.5 for row in db.query(Order).all())
        assert history_page(db, 1, customer="synthetic", page_size=1)[1] == capacity
        assert history_overview(db, 1, today=now.date())["total"] == capacity
