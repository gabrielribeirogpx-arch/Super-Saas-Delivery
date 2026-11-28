import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.ifood_event import IFoodEvent
from app.models.tenant import Tenant
from app.routers.admin_store import router as admin_store_router
from app.services.ifood_events import poll_ifood_events


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ifood.db'}")
    Tenant.__table__.create(engine)
    IFoodEvent.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="pilot"), Tenant(id=2, slug="other")])
        db.commit()
        yield engine, db
    engine.dispose()


def test_poll_persists_before_ack_and_handles_replay(database):
    engine, db = database
    merchant = uuid4()
    event = {
        "id": str(uuid4()),
        "merchantId": str(merchant),
        "orderId": str(uuid4()),
        "createdAt": "2026-11-27T13:00:00Z",
        "fullCode": "PLACED",
    }
    another = {**event, "id": str(uuid4()), "merchantId": str(uuid4())}
    acks = []

    def handle(request):
        assert request.headers["authorization"] == "Bearer pilot-token"
        if request.method == "GET":
            assert request.headers["x-polling-merchants"] == str(merchant)
            assert request.url.params["categories"] == "FOOD"
            return httpx.Response(200, json=[event, event, another])
        with Session(engine) as verify:
            assert verify.get(IFoodEvent, event["id"]).tenant_id == 1
            assert verify.get(IFoodEvent, another["id"]) is None
        acks.append(json.loads(request.content))
        return httpx.Response(500 if len(acks) == 1 else 202)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        kwargs = dict(access_token="pilot-token", tenant_id=1, merchant_id=merchant)
        with pytest.raises(httpx.HTTPStatusError):
            poll_ifood_events(http, db, **kwargs)
        assert poll_ifood_events(http, db, **kwargs) == 1
        with pytest.raises(ValueError, match="different tenant"):
            poll_ifood_events(http, db, **{**kwargs, "tenant_id": 2})
    assert db.query(IFoodEvent).count() == 1
    assert acks == [[{"id": event["id"]}], [{"id": event["id"]}]]


def test_no_new_events_does_not_ack(database):
    _, db = database

    def handle(request):
        assert request.method == "GET"
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        assert poll_ifood_events(
            http, db, access_token="pilot-token", tenant_id=1, merchant_id=uuid4(),
        ) == 0
    assert db.query(IFoodEvent).count() == 0


def test_admin_status_only_returns_latest_event_for_the_signed_in_store(database, monkeypatch):
    engine, db = database
    admin = AdminUser(id=1, tenant_id=1, role="owner")
    timestamp = datetime(2026, 11, 27, 13, tzinfo=timezone.utc)
    for tenant_id, hour, code in [(1, 12, "PLACED"), (1, 13, "CONFIRMED"), (2, 14, "PLACED")]:
        db.add(IFoodEvent(
            event_id=str(uuid4()),
            tenant_id=tenant_id,
            merchant_id=str(uuid4()),
            code=code,
            occurred_at=timestamp,
            received_at=timestamp.replace(hour=hour),
        ))
    db.commit()

    def open_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(admin_store_router)
    app.dependency_overrides[get_db] = open_session
    app.dependency_overrides[require_admin_user] = lambda: admin

    with TestClient(app) as client:
        path = "/api/admin/store/integrations/ifood"
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "last_event": {"code": "CONFIRMED", "received_at": "2026-11-27T13:00:00Z"}
        }
        assert client.get(path, params={"tenant_id": 2}).status_code == 403
        admin.role = "operator"
        assert client.get(path).status_code == 403
        admin.role = "admin"
        db.query(IFoodEvent).filter_by(tenant_id=1).delete()
        db.commit()
        assert client.get(path).json() == {"last_event": None}

        merchant_id = str(uuid4())
        monkeypatch.setenv("IFOOD_PILOT_TENANT_ID", "1")
        monkeypatch.setenv("IFOOD_PILOT_MERCHANT_ID", merchant_id)
        monkeypatch.setenv("IFOOD_PILOT_ENABLED", "true")
        monkeypatch.setenv("IFOOD_PILOT_ACCESS_TOKEN", jwt.encode({"exp": 1}, "fixture", algorithm="HS256"))
        assert client.get(path).json() == {
            "last_event": None,
            "environment": "test",
            "connection_status": "expired",
            "merchant_id": merchant_id,
        }
