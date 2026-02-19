from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers.admin_auth import router as admin_auth_router
from tests.fixtures_data import HAPPY_PATH_ADMIN


class _FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.user


class _FakeDb:
    def __init__(self, user):
        self.user = user

    def query(self, model):
        return _FakeQuery(self.user)

    def commit(self):
        return None


def _build_client(user):
    app = FastAPI()
    app.include_router(admin_auth_router)
    app.dependency_overrides[get_db] = lambda: _FakeDb(user)
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


def test_admin_login_rejects_platform_root_domain_without_slug():
    user = SimpleNamespace(**HAPPY_PATH_ADMIN)
    client = _build_client(user)

    with patch(
        "app.routers.admin_auth.resolve_tenant_from_host",
        side_effect=HTTPException(status_code=404, detail="Tenant não encontrado"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "123"},
            headers={"host": "mandarpedido.com"},
        )

    assert response.status_code == 400
    assert "subdomínio" in response.json()["detail"].lower()


def test_admin_login_accepts_x_tenant_slug_without_subdomain():
    user = SimpleNamespace(**HAPPY_PATH_ADMIN)
    client = _build_client(user)

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=True),
        patch("app.routers.admin_auth.clear_login_attempts"),
        patch("app.routers.admin_auth.log_admin_action"),
        patch("app.routers.admin_auth.create_admin_session", return_value="token123"),
        patch("app.routers.admin_auth.set_admin_session_cookie"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "123"},
            headers={"host": "service-delivery-backend-production.up.railway.app", "x-tenant-slug": "burger"},
        )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == user.tenant_id
