from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.tenant import Tenant
from app.routers.admin_auth import router as admin_auth_router
from app.routers.public_menu import router as public_menu_router


def _build_public_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    tenant = Tenant(id=1, slug="burger", business_name="Burger House", custom_domain="burger.test")
    tenant2 = Tenant(id=2, slug="pasteldojoao", business_name="Pastel do João", custom_domain="pastel.test")
    db.add(tenant)
    db.add(tenant2)
    db.add(MenuCategory(id=1, tenant_id=1, name="Lanches", sort_order=1, active=True))
    db.add(
        MenuItem(
            id=1,
            tenant_id=1,
            category_id=1,
            name="X-Burger",
            description="Carne e queijo",
            price_cents=2500,
            active=True,
        )
    )
    db.add(MenuCategory(id=2, tenant_id=2, name="Pastéis", sort_order=1, active=True))
    db.add(
        MenuItem(
            id=2,
            tenant_id=2,
            category_id=2,
            name="Pastel de Queijo",
            description="Queijo minas",
            price_cents=1800,
            active=True,
        )
    )
    db.commit()

    app = FastAPI()
    app.include_router(public_menu_router)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _build_admin_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://servicedelivery.com.br"],
        allow_origin_regex=r"^https://([a-z0-9-]+\.)?servicedelivery\.com\.br$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(admin_auth_router)

    user = SimpleNamespace(
        id=7,
        tenant_id=1,
        email="admin@example.com",
        name="Admin",
        role="owner",
        active=True,
        password_hash="hashed",
    )

    class _FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return user

    class _FakeDb:
        def query(self, model):
            return _FakeQuery()

        def commit(self):
            return None

    app.dependency_overrides[get_db] = lambda: _FakeDb()
    return TestClient(app)


def test_public_tenant_resolution_by_slug_host():
    client = _build_public_client()

    response = client.get("/public/tenant/by-host", headers={"host": "burger.servicedelivery.com.br"})

    assert response.status_code == 200
    assert response.json()["slug"] == "burger"


def test_public_tenant_resolution_by_custom_domain():
    client = _build_public_client()

    response = client.get("/public/tenant/by-host", headers={"host": "burger.test"})

    assert response.status_code == 200
    assert response.json()["slug"] == "burger"


def test_admin_session_cookie_is_host_only_for_custom_domain():
    client = _build_admin_client()

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=True),
        patch("app.routers.admin_auth.clear_login_attempts"),
        patch("app.routers.admin_auth.log_admin_action"),
        patch("app.routers.admin_auth.create_admin_session", return_value="token123"),
        patch("app.services.admin_auth.ADMIN_SESSION_COOKIE_DOMAIN", ".mandarpedido.com"),
        patch("app.services.admin_auth.ADMIN_SESSION_COOKIE_DOMAIN_SOURCE", "auto"),
        patch("app.services.admin_auth.PUBLIC_BASE_DOMAIN", "mandarpedido.com"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "123"},
            headers={"host": "admin.burger.test"},
        )

    assert response.status_code == 200
    assert "Domain=" not in response.headers.get("set-cookie", "")


def test_admin_session_cookie_uses_shared_domain_for_subdomain_hosts():
    client = _build_admin_client()

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=True),
        patch("app.routers.admin_auth.clear_login_attempts"),
        patch("app.routers.admin_auth.log_admin_action"),
        patch("app.routers.admin_auth.create_admin_session", return_value="token123"),
        patch("app.services.admin_auth.ADMIN_SESSION_COOKIE_DOMAIN", ".mandarpedido.com"),
        patch("app.services.admin_auth.ADMIN_SESSION_COOKIE_DOMAIN_SOURCE", "auto"),
        patch("app.services.admin_auth.PUBLIC_BASE_DOMAIN", "mandarpedido.com"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "123"},
            headers={"host": "admin.mandarpedido.com"},
        )

    assert response.status_code == 200
    assert "Domain=.mandarpedido.com" in response.headers.get("set-cookie", "")


def test_public_menu_resolves_tenant_from_host_only():
    client = _build_public_client()

    response = client.get("/public/menu", headers={"host": "pastel-do-joao.servicedelivery.com.br"})

    assert response.status_code == 200
    assert response.json()["slug"] == "pasteldojoao"


def test_public_tenant_resolution_normalizes_subdomain_before_lookup():
    client = _build_public_client()

    response = client.get("/public/tenant/by-host", headers={"host": "pastel-do-joao.servicedelivery.com.br"})

    assert response.status_code == 200
    assert response.json()["slug"] == "pasteldojoao"


def test_cors_allows_platform_subdomains_with_credentials():
    client = _build_admin_client()

    response = client.options(
        "/api/admin/auth/me",
        headers={
            "origin": "https://tenant-a.servicedelivery.com.br",
            "access-control-request-method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://tenant-a.servicedelivery.com.br"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_allows_platform_root_domain_with_credentials():
    client = _build_admin_client()

    response = client.options(
        "/api/admin/auth/me",
        headers={
            "origin": "https://servicedelivery.com.br",
            "access-control-request-method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://servicedelivery.com.br"
    assert response.headers.get("access-control-allow-credentials") == "true"
