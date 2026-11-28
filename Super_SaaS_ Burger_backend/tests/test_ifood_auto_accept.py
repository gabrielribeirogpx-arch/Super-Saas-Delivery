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
from app.models.ifood_auto_accept import IFoodAutoAccept
from app.models.ifood_event import IFoodEvent
from app.models.ifood_order import IFoodOrder
from app.models.tenant import Tenant
from app.routers import admin_ifood_orders, admin_store
from app.services.ifood_auto_accept import auto_accept_ifood_orders
from app.services.ifood_orders import ORDERS_URL


def test_owner_can_auto_accept_only_new_eligible_ifood_orders(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'auto-accept.db'}")
    for model in (Tenant, IFoodEvent, IFoodOrder, IFoodAutoAccept):
        model.__table__.create(engine)
    merchant = uuid4()
    monkeypatch.setenv("IFOOD_PILOT_ENABLED", "true")
    monkeypatch.setenv("IFOOD_PILOT_TENANT_ID", "1")
    monkeypatch.setenv("IFOOD_PILOT_MERCHANT_ID", str(merchant))
    monkeypatch.setenv("IFOOD_PILOT_ACCESS_TOKEN", "pilot-token")

    def get_session():
        with Session(engine) as db:
            yield db

    def add_order(state="PLACED", created_at=None, order_merchant=merchant, cancelling=False):
        order_id = str(uuid4())
        when = created_at or datetime.now(timezone.utc)
        with Session(engine) as db:
            db.add(IFoodOrder(
                order_id=order_id, tenant_id=1, merchant_id=str(order_merchant),
                created_at=when, imported_at=datetime.now(timezone.utc), details={"display_id": "01"},
                cancellation_requested_at=when if cancelling else None,
            ))
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, merchant_id=str(order_merchant),
                order_id=order_id, code=state, occurred_at=when,
            ))
            db.commit()
        return order_id

    with Session(engine) as db:
        db.add(Tenant(id=1, slug="store"))
        db.commit()
    add_order()
    calls = []

    def upstream(request):
        assert request.method == "POST"
        assert request.headers["authorization"] == "Bearer pilot-token"
        calls.append(str(request.url))
        return httpx.Response(503 if len(calls) == 1 else 202)

    client_class = httpx.Client
    monkeypatch.setattr(admin_ifood_orders.httpx, "Client", lambda **kwargs: client_class(
        transport=httpx.MockTransport(upstream), **kwargs,
    ))

    def run_worker():
        with Session(engine) as db:
            return auto_accept_ifood_orders(db, "pilot-token", 1, merchant)

    app = FastAPI()
    app.include_router(admin_store.router)
    auth_user = AdminUser(id=1, tenant_id=1, role="owner")
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[require_admin_user] = lambda: auth_user
    base = "/api/admin/store/integrations/ifood"
    with TestClient(app) as client:
        assert client.get(base).json()["auto_accept_enabled"] is False
        assert run_worker() == 0 and calls == []
        auth_user.role = "operator"
        assert client.patch(f"{base}/auto-accept", json={"enabled": True}).status_code == 403
        auth_user.role = "owner"
        assert client.patch(f"{base}/auto-accept", json={"enabled": True}).json() == {"enabled": True}
        included = add_order()
        add_order(state="CANCELLED")
        add_order(created_at=datetime.now(timezone.utc) - timedelta(minutes=9))
        add_order(order_merchant=uuid4())
        add_order(cancelling=True)
        assert run_worker() == 0 and calls == []
        with Session(engine) as db:
            for order in db.query(IFoodOrder):
                order.imported_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            db.commit()
        assert run_worker() == 0
        assert run_worker() == 1
        assert run_worker() == 0
        assert calls == [f"{ORDERS_URL}/{included}/confirm"] * 2
        with Session(engine) as db:
            assert db.get(IFoodOrder, included).confirmation_requested_at is not None
        assert client.patch(f"{base}/auto-accept", json={"enabled": False}).json() == {"enabled": False}
        add_order()
        assert run_worker() == 0
    engine.dispose()
