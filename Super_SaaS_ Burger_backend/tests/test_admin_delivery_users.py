from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
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
