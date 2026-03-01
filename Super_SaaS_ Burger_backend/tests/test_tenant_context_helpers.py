from types import SimpleNamespace

from starlette.requests import Request

from app.services.tenant_context import get_current_tenant_id, tenant_filter


def _build_request(path: str = "/") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [],
    }
    request = Request(scope)
    request.state.tenant = None
    request.state.tenant_id = None
    return request


class _QueryStub:
    def __init__(self):
        self.called_with = None

    def filter(self, expression):
        self.called_with = expression
        return self


class _ModelStub:
    tenant_id = 123


def test_get_current_tenant_id_from_state_tenant_id():
    request = _build_request()
    request.state.tenant_id = "12"

    assert get_current_tenant_id(request) == 12


def test_get_current_tenant_id_falls_back_to_state_tenant_object():
    request = _build_request()
    request.state.tenant = SimpleNamespace(id=33)

    assert get_current_tenant_id(request) == 33


def test_tenant_filter_keeps_query_unchanged_without_tenant_id():
    request = _build_request()
    query = _QueryStub()

    result = tenant_filter(query, _ModelStub, request)

    assert result is query
    assert query.called_with is None


def test_tenant_filter_applies_filter_with_tenant_id():
    request = _build_request()
    request.state.tenant_id = 8
    query = _QueryStub()

    result = tenant_filter(query, _ModelStub, request)

    assert result is query
    assert query.called_with is False
