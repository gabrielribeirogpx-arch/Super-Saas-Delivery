from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.ifood_connection import IFoodConnection
from app.models.ifood_event import IFoodEvent
from app.models.ifood_order import IFoodOrder
from app.models.tenant import Tenant
from app.routers import admin_ifood_orders, admin_store
from app.services.ifood_connections import production_oauth, refresh_production_access
from app.services.ifood_orders import import_ifood_orders


def test_owner_connects_restaurant_and_uses_production_orders(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ifood-production.db'}")
    for model in (Tenant, IFoodConnection, IFoodEvent, IFoodOrder):
        model.__table__.create(engine)
    now = datetime.now(timezone.utc)
    merchant_id, order_id = uuid4(), str(uuid4())
    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="store"), Tenant(id=2, slug="other")])
        db.commit()

    for key, value in {
        "IFOOD_PRODUCTION_TENANT_IDS": "1,2",
        "IFOOD_PILOT_TENANT_ID": "3",
        "IFOOD_CLIENT_ID": "app",
        "IFOOD_CLIENT_SECRET": "secret",
        "IFOOD_CONNECTION_KEY": Fernet.generate_key().decode(),
    }.items():
        monkeypatch.setenv(key, value)

    grants = []
    def upstream(request):
        if request.url.path.endswith("/userCode"):
            return httpx.Response(200, json={
                "userCode": "user-code", "authorizationCodeVerifier": "verifier", "expiresIn": 600,
            })
        if request.url.path.endswith("/token"):
            form = parse_qs(request.content.decode())
            grants.append(form)
            refresh = form["grantType"] == ["refresh_token"]
            return httpx.Response(200, json={
                "accessToken": "new-access" if refresh else "access",
                "refreshToken": "new-refresh" if refresh else "refresh",
                "expiresIn": 3600,
            })
        if request.url.path.endswith(f"/merchants/{merchant_id}"):
            assert request.headers["Authorization"] == "Bearer access"
            return httpx.Response(200, json={"id": str(merchant_id), "name": "Loja conectada"})
        assert request.url.path.endswith(f"/orders/{order_id}")
        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(200, json={
            "id": order_id, "merchant": {"id": str(merchant_id)}, "category": "FOOD",
            "isTest": False, "createdAt": now.isoformat(), "displayId": "0001", "orderType": "DELIVERY",
            "total": {"orderAmount": 30}, "items": [], "delivery": {"deliveredBy": "IFOOD"},
        })

    original_client = httpx.Client
    transport = httpx.MockTransport(upstream)
    monkeypatch.setattr(admin_store.httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs))

    def open_db():
        with Session(engine) as db:
            yield db

    app = FastAPI()
    app.include_router(admin_store.router)
    app.include_router(admin_ifood_orders.router)
    user = AdminUser(id=1, tenant_id=1, role="owner")
    app.dependency_overrides[get_db] = open_db
    app.dependency_overrides[require_admin_user] = lambda: user
    path = "/api/admin/store/integrations/ifood"
    with TestClient(app) as client:
        started = client.post(f"{path}/authorize")
        assert started.status_code == 200
        assert started.json()["url"] == "https://portal.ifood.com.br/apps/code?c=user-code"
        params = {
            "challenge": started.json()["challenge"], "authorization_code": "owner-code",
            "merchant_id": str(merchant_id),
        }
        user.tenant_id = 2
        assert client.post(f"{path}/connect", json=params).status_code == 400
        assert not grants
        user.tenant_id = 1
        assert client.post(f"{path}/connect", json=params).status_code == 200
        assert grants[0]["authorizationCodeVerifier"] == ["verifier"]
        with Session(engine) as db, original_client(transport=transport) as remote:
            connection = db.get(IFoodConnection, 1)
            assert "access" not in connection.encrypted_tokens
            connection.expires_at = now - timedelta(seconds=1)
            db.add(IFoodEvent(
                event_id=str(uuid4()), tenant_id=1, order_id=order_id, merchant_id=str(merchant_id),
                code="PLACED", occurred_at=now,
            ))
            db.commit()
            token, bound_merchant = refresh_production_access(remote, db, 1, production_oauth(1))
            assert bound_merchant == str(merchant_id)
            assert grants[1]["refreshToken"] == ["refresh"]
            assert import_ifood_orders(remote, db, token, 1, merchant_id, test_orders=False) == 1
        listing = client.get("/api/admin/ifood-orders").json()
        assert listing["pilot"] is False
        assert listing["orders"][0]["can_confirm"] is True
        assert client.get("/api/admin/ifood-orders/deliveries").json()["deliveries"][0]["order_id"] == order_id
        user.tenant_id = 2
        assert client.get("/api/admin/ifood-orders").json()["orders"] == []
