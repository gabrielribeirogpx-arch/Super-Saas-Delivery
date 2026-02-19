from unittest.mock import patch
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.middleware.tenant_context import TenantMiddleware
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.routers.admin_auth import router as admin_auth_router
from app.routers.public_menu import router as public_menu_router
from app.services.passwords import hash_password


def _build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    tenant = Tenant(id=1, slug="box", business_name="Box")
    db.add(tenant)
    db.add(
        AdminUser(
            id=1,
            tenant_id=1,
            email="admin@box.com",
            name="Admin",
            role="owner",
            active=True,
            password_hash=hash_password("123456"),
        )
    )
    db.commit()

    app = FastAPI()
    app.state.session_factory = TestingSessionLocal
    app.add_middleware(TenantMiddleware)
    app.include_router(admin_auth_router)
    app.include_router(public_menu_router)

    @app.get("/dashboard")
    def dashboard(request: Request):
        tenant = request.state.tenant
        if tenant is None:
            return {"detail": "missing"}
        return {"tenant": tenant.slug}

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_login_via_subdomain():
    client = _build_client()
    with patch("app.routers.admin_auth.create_admin_session", return_value="token"):
        response = client.post(
            "/api/admin/auth/login",
            headers={"host": "box.servicedelivery.com.br"},
            json={"email": "admin@box.com", "password": "123456"},
        )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == 1


def test_dashboard_via_subdomain():
    client = _build_client()
    response = client.get("/dashboard", headers={"host": "box.servicedelivery.com.br"})
    assert response.status_code == 200
    assert response.json()["tenant"] == "box"


def test_public_menu_via_subdomain():
    client = _build_client()
    response = client.get("/public/menu", headers={"host": "box.servicedelivery.com.br"})
    assert response.status_code == 200
    assert response.json()["slug"] == "box"


def test_missing_slug_returns_404():
    client = _build_client()
    response = client.get("/public/menu", headers={"host": "inexistente.servicedelivery.com.br"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant não encontrado"
