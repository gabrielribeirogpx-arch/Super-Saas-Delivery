from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_delivery_user
from app.models.admin_user import AdminUser
from app.models.ifood_driver_delivery import IFoodDriverDelivery
from app.models.ifood_event import IFoodEvent
from app.models.ifood_order import IFoodOrder
from app.models.order import Order
from app.models.tenant import Tenant
from app.routers import admin_ifood_orders, driver_api
from app.services.ifood_orders import ORDERS_URL, import_pilot_orders


def test_ifood_own_delivery_uses_existing_driver_routes(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'driver.db'}")
    for model in (Tenant, AdminUser, Order, IFoodOrder, IFoodDriverDelivery, IFoodEvent):
        model.__table__.create(engine)
    merchant_id, order_id = uuid4(), str(uuid4())
    now = datetime.now(timezone.utc)
    for key, value in {
        "IFOOD_PILOT_ENABLED": "true", "IFOOD_PILOT_TENANT_ID": "1",
        "IFOOD_PILOT_MERCHANT_ID": str(merchant_id), "IFOOD_PILOT_ACCESS_TOKEN": "test-token",
    }.items():
        monkeypatch.setenv(key, value)

    def order_event(code):
        with Session(engine) as db:
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, merchant_id=str(merchant_id), order_id=order_id,
                code=code, occurred_at=datetime.now(timezone.utc),
            ))
            db.commit()

    dispatches = []
    def upstream(request):
        assert request.headers["authorization"] == "Bearer test-token"
        if request.method == "GET":
            assert str(request.url) == f"{ORDERS_URL}/{order_id}"
            return httpx.Response(200, json={
                "id": order_id, "merchant": {"id": str(merchant_id)}, "category": "FOOD", "isTest": True,
                "createdAt": now.isoformat(), "displayId": "2449", "orderType": "DELIVERY",
                "total": {"orderAmount": 27}, "items": [],
                "delivery": {"deliveredBy": "MERCHANT", "deliveryAddress": {
                    "formattedAddress": "Rua de Teste, 10",
                    "coordinates": {"latitude": -23.5, "longitude": -46.6},
                }},
            })
        dispatches.append(str(request.url))
        return httpx.Response(202)

    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="pilot"), Tenant(id=2, slug="other")])
        db.commit()
    order_event("PLACED")
    remote_client = httpx.Client
    transport = httpx.MockTransport(upstream)
    with Session(engine) as db, remote_client(transport=transport) as remote:
        assert import_pilot_orders(remote, db, "test-token", 1, merchant_id) == 1
        assert import_pilot_orders(remote, db, "test-token", 1, merchant_id) == 0
        assert db.query(Order).count() == 0

    monkeypatch.setattr(admin_ifood_orders.httpx, "Client", lambda **kwargs: remote_client(transport=transport, **kwargs))

    def get_session():
        with Session(engine) as db:
            yield db

    user = AdminUser(id=1, tenant_id=1, role="delivery")
    app = FastAPI()
    app.include_router(driver_api.router)
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_current_delivery_user] = lambda: user
    with TestClient(app) as client:
        path = "/api/driver"
        assert client.get(f"{path}/state").json()["available_orders"] == []
        order_event("READY_TO_PICKUP")
        delivery = client.get(f"{path}/state").json()["available_orders"][0]
        assert delivery["daily_order_number"] == 2449 and delivery["address"] == "Rua de Teste, 10"
        delivery_id = delivery["id"]
        actions = f"{path}/orders/{delivery_id}"
        user.tenant_id = 2
        assert client.post(f"{actions}/accept").status_code == 404
        user.tenant_id = 1
        assert client.post(f"{actions}/start").status_code == 409
        assert client.post(f"{actions}/accept").json()["status"] == "DRIVER_ASSIGNED"
        user.id = 2
        assert client.post(f"{actions}/accept").status_code == 404
        user.id = 1
        assert client.post(f"{actions}/start").json()["status"] == "OUT_FOR_DELIVERY"
        assert client.post(f"{actions}/start").json()["status"] == "OUT_FOR_DELIVERY"
        assert dispatches == [f"{ORDERS_URL}/{order_id}/dispatch"]
        order_event("DISPATCHED")
        assert client.get(f"{path}/state").json()["active_delivery"]["status"] == "OUT_FOR_DELIVERY"
        assert client.post(f"{actions}/complete").json()["status"] == "DELIVERED"
        assert client.get(f"{path}/state").json()["completed_today"] == 1
    engine.dispose()
