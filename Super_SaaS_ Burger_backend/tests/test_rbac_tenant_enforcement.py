from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.services.authorization_service import AuthorizationService


def _build_request(path: str = '/api/admin/critical/1') -> Request:
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': path,
        'query_string': b'',
        'headers': [],
        'path_params': {'tenant_id': '1'},
        'client': ('testclient', 50000),
        'server': ('testserver', 80),
        'scheme': 'http',
    }
    return Request(scope)


def test_user_without_required_role_receives_403():
    user = SimpleNamespace(id=1, tenant_id=1, role='cashier')

    with pytest.raises(HTTPException) as exc:
        AuthorizationService.ensure_role(
            request=_build_request(),
            user=user,
            tenant_id=1,
            roles=['admin'],
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == 'Permissão insuficiente'


def test_tenant_isolation_blocks_cross_tenant_access_with_403():
    user = SimpleNamespace(id=2, tenant_id=1, role='admin')

    with pytest.raises(HTTPException) as exc:
        AuthorizationService.ensure_role(
            request=_build_request(path='/api/admin/critical/99'),
            user=user,
            tenant_id=99,
            roles=['admin'],
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == 'Tenant não autorizado'
