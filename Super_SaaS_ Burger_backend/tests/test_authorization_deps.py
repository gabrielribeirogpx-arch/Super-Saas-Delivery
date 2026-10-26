from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.deps import require_admin_tenant_access, require_role


def _build_request(path: str = "/api/resource", method: str = "GET", query_string: str = "", tenant_id: int | None = None) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string.encode(),
        "headers": [],
        "path_params": {},
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    request.state.tenant = SimpleNamespace(id=tenant_id) if tenant_id is not None else None
    return request


def test_require_admin_tenant_access_denies_tenant_mismatch():
    user = SimpleNamespace(id=10, tenant_id=1, role="admin")
    request = _build_request(tenant_id=2)

    with pytest.raises(HTTPException) as exc:
        require_admin_tenant_access(request=request, tenant_id=None, user=user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Tenant não autorizado"


def test_require_role_denies_tenant_mismatch_before_role_check():
    user = SimpleNamespace(id=11, tenant_id=1, role="cashier")
    request = _build_request(path="/api/admin/reports", tenant_id=77)
    dependency = require_role(["cashier", "admin"])

    with pytest.raises(HTTPException) as exc:
        dependency(request=request, tenant_id=None, user=user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Tenant não autorizado"


def test_require_role_denies_role_when_tenant_matches():
    user = SimpleNamespace(id=12, tenant_id=3, role="operator")
    request = _build_request(path="/api/admin/users")
    dependency = require_role(["admin"])

    with pytest.raises(HTTPException) as exc:
        dependency(request=request, tenant_id=3, user=user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Permissão insuficiente"
