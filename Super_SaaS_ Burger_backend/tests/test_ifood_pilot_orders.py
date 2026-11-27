from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.ifood_event import IFoodEvent
from app.models.ifood_order import IFoodOrder
from app.models.tenant import Tenant
from app.routers import admin_ifood_orders
from app.services.ifood_orders import ORDERS_URL, import_pilot_orders


def test_order_import_retry_deduplicates_and_waits_for_confirmation_event(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ifood-orders.db'}")
    for model in (Tenant, IFoodEvent, IFoodOrder):
        model.__table__.create(engine)
    now = datetime.now(timezone.utc)
    merchant_id = uuid4()
    order_id = str(uuid4())
    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="pilot"), Tenant(id=2, slug="other")])
        db.add(IFoodEvent(
            event_id=str(uuid4()), tenant_id=1, order_id=order_id,
            merchant_id=str(merchant_id), code="PLACED", occurred_at=now,
        ))
        db.commit()

    request_count = 0

    def details(request):
        nonlocal request_count
        request_count += 1
        assert str(request.url) == f"{ORDERS_URL}/{order_id}"
        if request_count == 1:
            return httpx.Response(404)
        return httpx.Response(200, json={
            "id": order_id, "merchant": {"id": str(merchant_id)},
            "category": "FOOD", "isTest": request_count != 2,
            "createdAt": now.isoformat(), "displayId": "001",
            "orderType": "DELIVERY", "total": {"orderAmount": 29.90},
            "delivery": {"deliveredBy": "IFOOD"},
            "items": [{"name": "Burger", "quantity": 1, "options": [{"name": "Bacon", "quantity": 1}]}],
            "payments": {"methods": [{"method": "PIX", "type": "ONLINE", "transaction": {"secret": True}}]},
        })

    with Session(engine) as db, httpx.Client(transport=httpx.MockTransport(details)) as client:
        args = (client, db, "pilot-token", 1, merchant_id)
        assert import_pilot_orders(*args) == 0
        assert import_pilot_orders(*args) == 0
        assert import_pilot_orders(*args) == 1
        assert import_pilot_orders(*args) == 0
        assert request_count == 3

    monkeypatch.setenv("IFOOD_PILOT_ENABLED", "true")
    monkeypatch.setenv("IFOOD_PILOT_ACCESS_TOKEN", "pilot-token")
    monkeypatch.setenv("IFOOD_PILOT_MERCHANT_ID", str(merchant_id))
    monkeypatch.setenv("IFOOD_PILOT_TENANT_ID", "1")
    remote_calls = []

    def order_action(request):
        remote_calls.append(request)
        assert request.method == "POST"
        assert str(request.url) in {f"{ORDERS_URL}/{order_id}/confirm", f"{ORDERS_URL}/{order_id}/readyToPickup"}
        assert request.headers["authorization"] == "Bearer pilot-token"
        if len(remote_calls) == 2:
            return httpx.Response(503)
        return httpx.Response(202)

    transport = httpx.MockTransport(order_action)
    http_client = httpx.Client
    monkeypatch.setattr(admin_ifood_orders.httpx, "Client", lambda **kwargs: http_client(transport=transport, **kwargs))

    def open_session():
        with Session(engine) as db:
            yield db

    user = AdminUser(id=1, tenant_id=1, role="operator")
    app = FastAPI()
    app.include_router(admin_ifood_orders.router)
    app.dependency_overrides[get_db] = open_session
    app.dependency_overrides[require_admin_user] = lambda: user
    path = "/api/admin/ifood-orders"
    with TestClient(app) as client:
        order = client.get(path).json()["orders"][0]
        assert order["can_confirm"] is True
        assert order["can_mark_ready"] is False
        assert order["delivered_by"] == "IFOOD"
        assert client.post(f"{path}/{order_id}/ready").status_code == 409
        assert order["payment"] == [{"method": "PIX", "type": "ONLINE"}]
        with Session(engine) as db:
            db.get(IFoodOrder, order_id).created_at = now - timedelta(minutes=9)
            db.commit()
        assert client.post(f"{path}/{order_id}/confirm").status_code == 409
        assert not remote_calls
        with Session(engine) as db:
            db.get(IFoodOrder, order_id).created_at = now
            db.commit()
        assert client.post(f"{path}/{order_id}/confirm").status_code == 202
        assert client.post(f"{path}/{order_id}/confirm").status_code == 202
        assert len(remote_calls) == 1
        order = client.get(path).json()["orders"][0]
        assert order["state"] == "PLACED" and order["confirmation_pending"] is True
        with Session(engine) as db:
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, order_id=order_id, merchant_id=str(merchant_id),
                code="CONFIRMED", occurred_at=now + timedelta(seconds=1),
            ))
            db.commit()
        order = client.get(path).json()["orders"][0]
        assert order["state"] == "CONFIRMED" and order["confirmation_pending"] is False
        assert order["can_mark_ready"] is True
        assert client.post(f"{path}/{order_id}/ready").status_code == 502
        assert client.get(path).json()["orders"][0]["can_mark_ready"] is True
        assert client.post(f"{path}/{order_id}/ready").json() == {"ready_pending": True}
        assert client.post(f"{path}/{order_id}/ready").json() == {"ready_pending": True}
        assert [request.url.path.rsplit("/", 1)[-1] for request in remote_calls] == [
            "confirm", "readyToPickup", "readyToPickup",
        ]
        order = client.get(path).json()["orders"][0]
        assert order["state"] == "CONFIRMED" and order["ready_pending"] is True
        assert order["can_mark_ready"] is False
        with Session(engine) as db:
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, order_id=order_id, merchant_id=str(merchant_id),
                code="READY_TO_PICKUP", occurred_at=now + timedelta(seconds=2),
            ))
            db.commit()
        order = client.get(path).json()["orders"][0]
        assert order["state"] == "READY_TO_PICKUP" and order["ready_pending"] is False
        assert client.post(f"{path}/{order_id}/ready").json() == {"ready_pending": False}
        assert len(remote_calls) == 3
        deliveries_path = f"{path}/deliveries"
        tracking_path = f"{path}/{order_id}/tracking"
        assert client.get(deliveries_path).json()["deliveries"] == [{
            "order_id": order_id, "display_id": "001", "state": "READY_TO_PICKUP",
            "driver_assigned": False, "can_track": False,
        }]
        assert client.get(tracking_path).status_code == 404
        with Session(engine) as db:
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, order_id=order_id, merchant_id=str(merchant_id),
                code="ASSIGN_DRIVER", occurred_at=now + timedelta(seconds=3),
            ))
            own_order = IFoodOrder(
                order_id=str(uuid4()), tenant_id=1, merchant_id=str(merchant_id), created_at=now,
                details={"display_id": "002", "order_type": "DELIVERY", "delivered_by": "MERCHANT"},
            )
            db.add(own_order)
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, order_id=own_order.order_id,
                merchant_id=str(merchant_id), code="READY_TO_PICKUP", occurred_at=now,
            ))
            db.commit()
        partner = client.get(deliveries_path).json()["deliveries"]
        assert len(partner) == 1 and partner[0]["can_track"] is True
        def tracking(token, requested_id):
            assert (token, requested_id) == ("pilot-token", order_id)
            return {"latitude": -23.55, "longitude": -46.63}
        monkeypatch.setattr(admin_ifood_orders, "fetch_ifood_tracking", tracking)
        assert client.get(tracking_path).json() == {"tracking": {"latitude": -23.55, "longitude": -46.63}}
        with Session(engine) as db:
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, order_id=order_id, merchant_id=str(merchant_id),
                code="DELIVERED", occurred_at=now + timedelta(seconds=4),
            ))
            db.commit()
        assert client.get(deliveries_path).json()["deliveries"][0]["state"] == "DELIVERED"
        assert client.get(tracking_path).status_code == 404
        user.tenant_id = 2
        assert client.get(deliveries_path).json() == {"enabled": False, "deliveries": []}
        assert client.get(tracking_path).status_code == 404
        assert client.get(path).json()["orders"] == []
        assert client.post(f"{path}/{order_id}/confirm").status_code == 404
        assert client.post(f"{path}/{order_id}/ready").status_code == 404
    engine.dispose()
