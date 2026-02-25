from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.routers.admin_auth import router as admin_auth_router
from tests.fixtures_data import HAPPY_PATH_ADMIN


class _FakeQuery:
    def __init__(self, first_result=None, all_results=None):
        self.first_result = first_result
        self.all_results = all_results or []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_result

    def all(self):
        return self.all_results


class _FakeDb:
    def __init__(self, user, tenant=None, users_by_email=None):
        self.user = user
        self.tenant = tenant or SimpleNamespace(id=user.tenant_id, slug="burger")
        self.users_by_email = users_by_email or []

    def query(self, model):
        if model == Tenant:
            return _FakeQuery(first_result=self.tenant)
        if model == AdminUser:
            return _FakeQuery(first_result=self.user, all_results=self.users_by_email)
        return _FakeQuery(first_result=self.user)

    def commit(self):
        return None


def _build_client(user, tenant=None, users_by_email=None):
    app = FastAPI()

    @app.middleware("http")
    async def _inject_tenant(request, call_next):
        fake_db = _FakeDb(user, tenant=tenant, users_by_email=users_by_email)
        host = (request.headers.get("host") or "").lower()
        request.state.tenant = fake_db.tenant if host.startswith(f"{fake_db.tenant.slug}.") else None
        return await call_next(request)

    app.include_router(admin_auth_router)
    app.dependency_overrides[get_db] = lambda: _FakeDb(user, tenant=tenant, users_by_email=users_by_email)
    return TestClient(app)


def test_admin_login_rejects_invalid_credentials():
    user = SimpleNamespace(**HAPPY_PATH_ADMIN)
    client = _build_client(user)

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=False),
        patch("app.routers.admin_auth.register_failed_login", return_value=(1, False)),
        patch("app.routers.admin_auth.log_admin_action"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "wrong"},
            headers={"host": "burger.mandarpedido.com"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciais inválidas"


def test_admin_login_rejects_root_domain_without_tenant_resolution():
    user = SimpleNamespace(**HAPPY_PATH_ADMIN)
    client = _build_client(user, users_by_email=[])

    response = client.post(
        "/api/admin/auth/login",
        json={"email": "admin@example.com", "password": "123"},
        headers={"host": "mandarpedido.com"},
    )

    assert response.status_code == 400
    assert "tenant" in response.json()["detail"].lower()


def test_admin_login_accepts_tenant_slug_on_railway_host():
    user = SimpleNamespace(**HAPPY_PATH_ADMIN)
    client = _build_client(user, users_by_email=[user])

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=True),
        patch("app.routers.admin_auth.clear_login_attempts"),
        patch("app.routers.admin_auth.log_admin_action"),
        patch("app.routers.admin_auth.create_admin_session", return_value="token"),
        patch("app.routers.admin_auth.set_admin_session_cookie"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": user.email, "password": "123", "tenant_slug": "burger"},
            headers={"host": "service-delivery-backand-production.up.railway.app"},
        )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == user.tenant_id
