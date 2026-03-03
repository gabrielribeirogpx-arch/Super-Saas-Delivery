from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.delivery_log import DeliveryLog
from app.routers.admin_delivery_users import router as admin_delivery_users_router


def _build_client(user):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(admin_delivery_users_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: user

    return TestClient(app), TestingSessionLocal


def test_create_delivery_user_success(monkeypatch):
    monkeypatch.setattr("app.routers.admin_delivery_users.log_admin_action", lambda *args, **kwargs: None)

    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, session_local = _build_client(auth_user)

    response = client.post(
        "/api/admin/1/delivery-users",
        json={"name": "Rider One", "email": "RIDER@EXAMPLE.COM", "password": "secret123"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["tenant_id"] == 1
    assert payload["role"] == "DELIVERY"
    assert payload["email"] == "rider@example.com"

    db = session_local()
    try:
        created = db.query(AdminUser).filter(AdminUser.email == "rider@example.com").first()
        assert created is not None
        assert created.role == "DELIVERY"
        assert created.password_hash != "secret123"
    finally:
        db.close()


def test_create_delivery_user_enforces_tenant_isolation(monkeypatch):
    monkeypatch.setattr("app.routers.admin_delivery_users.log_admin_action", lambda *args, **kwargs: None)

    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, _ = _build_client(auth_user)

    response = client.post(
        "/api/admin/2/delivery-users",
        json={"name": "Rider", "email": "rider@example.com", "password": "secret123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant não autorizado"


def test_create_delivery_user_rejects_duplicate_email_per_tenant(monkeypatch):
    monkeypatch.setattr("app.routers.admin_delivery_users.log_admin_action", lambda *args, **kwargs: None)

    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, session_local = _build_client(auth_user)

    db = session_local()
    db.add(
        AdminUser(
            tenant_id=1,
            email="rider@example.com",
            name="Existing",
            password_hash="hashed",
            role="DELIVERY",
            active=True,
        )
    )
    db.commit()
    db.close()

    response = client.post(
        "/api/admin/1/delivery-users",
        json={"name": "Rider", "email": "rider@example.com", "password": "secret123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email já cadastrado"


def test_create_delivery_user_not_exposed_in_openapi():
    app = FastAPI()
    app.include_router(admin_delivery_users_router)

    schema = app.openapi()

    assert "/api/admin/{tenant_id}/delivery-users" not in schema.get("paths", {})


def test_delivery_user_locations_returns_latest_location_per_delivery_user():
    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, session_local = _build_client(auth_user)

    now = datetime.now(timezone.utc)

    db = session_local()
    db.add_all(
        [
            DeliveryLog(
                tenant_id=1,
                order_id=1001,
                delivery_user_id=101,
                event_type="location_update",
                latitude=-23.0,
                longitude=-46.0,
                created_at=now - timedelta(minutes=2),
            ),
            DeliveryLog(
                tenant_id=1,
                order_id=1002,
                delivery_user_id=101,
                event_type="location_update",
                latitude=-23.1,
                longitude=-46.1,
                created_at=now - timedelta(minutes=1),
            ),
            DeliveryLog(
                tenant_id=1,
                order_id=1003,
                delivery_user_id=202,
                event_type="location_update",
                latitude=-22.9,
                longitude=-46.2,
                created_at=now - timedelta(minutes=3),
            ),
            DeliveryLog(
                tenant_id=1,
                order_id=1004,
                delivery_user_id=202,
                event_type="started",
                created_at=now,
            ),
            DeliveryLog(
                tenant_id=2,
                order_id=2001,
                delivery_user_id=101,
                event_type="location_update",
                latitude=-20.0,
                longitude=-40.0,
                created_at=now,
            ),
        ]
    )
    db.commit()
    db.close()

    response = client.get("/api/admin/1/delivery-users/locations")

    assert response.status_code == 200
    payload = response.json()
    assert [entry["delivery_user_id"] for entry in payload] == [101, 202]

    location_by_user = {entry["delivery_user_id"]: entry for entry in payload}
    assert location_by_user[101]["lat"] == -23.1
    assert location_by_user[101]["lng"] == -46.1
    assert location_by_user[202]["lat"] == -22.9
    assert location_by_user[202]["lng"] == -46.2


def test_delivery_user_locations_enforces_tenant_isolation():
    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, _ = _build_client(auth_user)

    response = client.get("/api/admin/2/delivery-users/locations")

    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant não autorizado"




def test_delivery_user_stats_returns_aggregated_metrics():
    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, session_local = _build_client(auth_user)

    now = datetime.now(timezone.utc)
    today_started = now - timedelta(minutes=45)
    today_completed = now - timedelta(minutes=30)
    yesterday_started = now - timedelta(days=1, minutes=40)
    yesterday_completed = now - timedelta(days=1, minutes=20)

    db = session_local()
    db.add(AdminUser(tenant_id=1, email="rider@example.com", name="Rider", password_hash="h", role="DELIVERY", active=True))
    db.flush()
    delivery_user_id = db.query(AdminUser).filter(AdminUser.email == "rider@example.com").first().id

    db.add_all(
        [
            DeliveryLog(tenant_id=1, order_id=1001, delivery_user_id=delivery_user_id, event_type="started", created_at=today_started),
            DeliveryLog(tenant_id=1, order_id=1001, delivery_user_id=delivery_user_id, event_type="completed", created_at=today_completed),
            DeliveryLog(tenant_id=1, order_id=1002, delivery_user_id=delivery_user_id, event_type="started", created_at=yesterday_started),
            DeliveryLog(tenant_id=1, order_id=1002, delivery_user_id=delivery_user_id, event_type="completed", created_at=yesterday_completed),
            DeliveryLog(tenant_id=1, order_id=1003, delivery_user_id=delivery_user_id, event_type="started", created_at=now - timedelta(minutes=10)),
            DeliveryLog(tenant_id=1, order_id=1004, delivery_user_id=9999, event_type="completed", created_at=now - timedelta(minutes=5)),
            DeliveryLog(tenant_id=2, order_id=2001, delivery_user_id=delivery_user_id, event_type="completed", created_at=now - timedelta(minutes=5)),
        ]
    )
    db.commit()
    db.close()

    response = client.get(f"/api/admin/1/delivery-users/{delivery_user_id}/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_deliveries"] == 2
    assert payload["today_deliveries"] == 1
    assert payload["avg_time_minutes"] == 17.5
    assert payload["completion_rate"] == 2 / 3


def test_delivery_user_stats_enforces_tenant_isolation():
    auth_user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    client, session_local = _build_client(auth_user)

    db = session_local()
    db.add(AdminUser(tenant_id=2, email="rider2@example.com", name="Rider 2", password_hash="h", role="DELIVERY", active=True))
    db.commit()
    other_tenant_user_id = db.query(AdminUser).filter(AdminUser.email == "rider2@example.com").first().id
    db.close()

    response = client.get(f"/api/admin/2/delivery-users/{other_tenant_user_id}/stats")

    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant não autorizado"


def test_delivery_user_stats_not_exposed_in_openapi():
    app = FastAPI()
    app.include_router(admin_delivery_users_router)

    schema = app.openapi()

    paths = schema.get("paths", {})
    assert "/api/admin/{tenant_id}/delivery-users/{delivery_user_id}/stats" not in paths
    assert "/api/admin/{tenant_id}/delivery-users/locations" not in paths
