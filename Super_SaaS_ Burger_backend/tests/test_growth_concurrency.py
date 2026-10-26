import asyncio
import threading
from types import SimpleNamespace

from app.routers import public_menu
import pytest
from fastapi import HTTPException
from test_billing_phase2 import db, make_subscription
from app.models.tenant import Tenant


def test_blocking_persistence_does_not_block_other_async_requests(monkeypatch):
    async def scenario():
        entered = threading.Event()
        release = threading.Event()
        geocoded = False
        main_thread = threading.get_ident()
        async def geocode(_):
            nonlocal geocoded
            geocoded = True
            return -23.5, -46.6
        def persist(*args):
            assert threading.get_ident() != main_thread
            assert geocoded and args[-1] == (-23.5, -46.6)
            entered.set()
            assert release.wait(3)
            return "saved"
        monkeypatch.setattr(public_menu, "geocode_address", geocode)
        monkeypatch.setattr(public_menu, "_persist_order_for_tenant", persist)
        payload = public_menu.PublicOrderPayload(order_type="pickup", delivery_type="RETIRADA",
            street="Rua A", number="1", city="São Paulo", items=[{"item_id": 1, "quantity": 1}])
        task = asyncio.create_task(public_menu._create_order_for_tenant(object(), SimpleNamespace(id=1), payload))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(.005)
            assert entered.is_set()
            # Another request on this loop still runs while persistence waits.
            assert await asyncio.wait_for(asyncio.sleep(.01, result="responsive"), .5) == "responsive"
        finally:
            release.set()
        assert await asyncio.wait_for(task, 2) == "saved"
    asyncio.run(scenario())


def test_inactive_store_is_rejected_before_external_geocoding(db, monkeypatch):
    make_subscription(db, tenant_id=1, provider="hotmart")
    calls = []
    async def geocode(_):
        calls.append("external")
        return None, None
    monkeypatch.setattr(public_menu, "geocode_address", geocode)
    payload = public_menu.PublicOrderPayload(order_type="pickup", delivery_type="RETIRADA",
        street="Rua A", number="1", items=[{"item_id": 1, "quantity": 1}])
    with pytest.raises(HTTPException) as error:
        asyncio.run(public_menu._create_order_for_tenant(db, db.get(Tenant, 1), payload))
    assert error.value.status_code == 403 and calls == []
