from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.deps import get_current_admin_user
from app.routers.admin_auth import router as admin_auth_router


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

    @app.middleware("http")
    async def _inject_tenant(request, call_next):
        host = (request.headers.get("host") or "").lower()
        request.state.tenant = SimpleNamespace(id=1, slug="burger") if host.startswith("burger.") else None
        return await call_next(request)

    app.include_router(admin_auth_router)
    app.dependency_overrides[get_db] = lambda: _FakeDb(user)
    return TestClient(app)


def test_login_sets_http_only_session_cookie():
    user = SimpleNamespace(
        id=7,
        tenant_id=1,
        email="admin@example.com",
        name="Admin",
        role="owner",
        active=True,
        password_hash="hashed",
    )
    client = _build_client(user)

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=True),
        patch("app.routers.admin_auth.clear_login_attempts"),
        patch("app.routers.admin_auth.log_admin_action"),
        patch("app.routers.admin_auth.create_admin_session", return_value="token123"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "123"},
            headers={"host": "burger.mandarpedido.com"},
        )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "admin_session=token123" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Domain=" not in set_cookie




def test_login_sets_cross_site_cookie_policy_for_tenant_domains():
    user = SimpleNamespace(
        id=7,
        tenant_id=1,
        email="admin@example.com",
        name="Admin",
        role="owner",
        active=True,
        password_hash="hashed",
    )
    client = _build_client(user)

    with (
        patch("app.routers.admin_auth.check_login_lock", return_value=(False, 0, None)),
        patch("app.routers.admin_auth.verify_password", return_value=True),
        patch("app.routers.admin_auth.clear_login_attempts"),
        patch("app.routers.admin_auth.log_admin_action"),
        patch("app.routers.admin_auth.create_admin_session", return_value="token123"),
    ):
        response = client.post(
            "/api/admin/auth/login",
            json={"email": "admin@example.com", "password": "123"},
            headers={
                "host": "burger.servicedelivery.com.br",
                "origin": "https://app.servicedelivery.com.br",
            },
        )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "Secure" in set_cookie
    assert "SameSite=none" in set_cookie

def test_logout_clears_session_cookie():
    client = _build_client(user=None)
    response = client.post("/api/admin/auth/logout")

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "admin_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()
    assert "Domain=" not in set_cookie


def test_me_returns_user_when_session_is_valid():
    user = SimpleNamespace(
        id=7,
        tenant_id=1,
        email="admin@example.com",
        name="Admin",
        role="owner",
        active=True,
    )
    client = _build_client(user=None)
    client.app.dependency_overrides[get_current_admin_user] = lambda: user

    response = client.get("/api/admin/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


def test_me_denies_access_without_session_cookie():
    client = _build_client(user=None)

    with patch("app.deps.decode_admin_session", return_value=None):
        response = client.get("/api/admin/auth/me")

    assert response.status_code == 401
