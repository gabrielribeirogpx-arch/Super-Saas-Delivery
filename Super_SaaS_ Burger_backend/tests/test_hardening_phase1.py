from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core import startup_checks
from app.deps import get_current_admin_user, require_admin_tenant_access


def _build_request(
    path: str = "/api/resource",
    method: str = "GET",
    query_string: str = "",
    headers: list[tuple[bytes, bytes]] | None = None,
    tenant_id: int | None = None,
) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string.encode(),
        "headers": headers or [],
        "path_params": {},
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    request.state.tenant = SimpleNamespace(id=tenant_id) if tenant_id is not None else None
    return request


def test_request_id_is_returned_in_response_header(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID")
    assert request_id
    UUID(request_id)


def test_cors_allows_known_origin_and_blocks_unknown_origin(monkeypatch):
    from app import main
    from app.core.config import CORS_ORIGINS

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    allowed_origin = CORS_ORIGINS[0]
    blocked_origin = "https://blocked-origin.example"

    with TestClient(main.app) as client:
        allowed_response = client.options(
            "/health",
            headers={
                "origin": allowed_origin,
                "access-control-request-method": "GET",
            },
        )
        blocked_response = client.options(
            "/health",
            headers={
                "origin": blocked_origin,
                "access-control-request-method": "GET",
            },
        )

    assert allowed_response.status_code == 200
    assert allowed_response.headers.get("access-control-allow-origin") == allowed_origin

    assert blocked_response.status_code == 400
    assert blocked_response.headers.get("access-control-allow-origin") is None


def test_production_environment_rejects_sqlite(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(startup_checks, "DATABASE_URL", "sqlite:///./forbidden.db")

    with pytest.raises(RuntimeError, match="SQLite is forbidden"):
        startup_checks.validate_database_environment()


def test_migration_check_fails_when_pending_migration(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "pending.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version (version_num) VALUES ('000000000000')")
    conn.commit()
    conn.close()

    from sqlalchemy import create_engine

    monkeypatch.setenv("ENVIRONMENT", "development")
    engine = create_engine(f"sqlite:///{db_path}")

    with pytest.raises(RuntimeError, match="Pending migrations"):
        startup_checks.ensure_migrations_applied(
            engine=engine,
            alembic_config_path=Path(__file__).resolve().parents[1] / "alembic.ini",
        )


def test_401_and_403_errors_are_standardized_messages():
    request = _build_request(headers=[])

    with pytest.raises(HTTPException) as exc401:
        get_current_admin_user(request=request, db=SimpleNamespace(query=lambda *_: None))

    assert exc401.value.status_code == 401
    assert isinstance(exc401.value.detail, str)

    user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    request_tenant_mismatch = _build_request(tenant_id=2)

    with pytest.raises(HTTPException) as exc403:
        require_admin_tenant_access(request=request_tenant_mismatch, tenant_id=None, user=user)

    assert exc403.value.status_code == 403
    assert isinstance(exc403.value.detail, str)
