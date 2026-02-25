from types import SimpleNamespace

from starlette.requests import Request
import pytest

from app.services.tenant_resolver import TenantResolutionError, TenantResolver


def _build_request(path: str, headers: dict[str, str] | None = None, path_params: dict | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": path.split("?", 1)[1].encode() if "?" in path else b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "path_params": path_params or {},
    }
    request = Request(scope)
    request.state.tenant = None
    return request


def test_resolve_tenant_id_from_query_param():
    request = _build_request("/api/dashboard/overview?tenant_id=21")

    tenant_id = TenantResolver.resolve_tenant_id_from_request(request)

    assert tenant_id == 21


def test_resolve_tenant_id_from_header_when_missing_query():
    request = _build_request("/api/dashboard/overview", headers={"x-tenant-id": "42"})

    tenant_id = TenantResolver.resolve_tenant_id_from_request(request)

    assert tenant_id == 42


def test_resolve_tenant_id_prioritizes_explicit_parameter():
    request = _build_request("/api/dashboard/overview?tenant_id=21", headers={"x-tenant-id": "42"})

    tenant_id = TenantResolver.resolve_tenant_id_from_request(request, tenant_id=7)

    assert tenant_id == 7


def test_resolve_tenant_id_falls_back_to_state_tenant():
    request = _build_request("/api/dashboard/overview")
    request.state.tenant = SimpleNamespace(id=9)

    tenant_id = TenantResolver.resolve_tenant_id_from_request(request)

    assert tenant_id == 9


def test_extract_subdomain_accepts_base_domain_with_scheme(monkeypatch):
    monkeypatch.setattr("app.services.tenant_resolver.PUBLIC_BASE_DOMAIN", "https://servicedelivery.com.br")

    subdomain = TenantResolver.extract_subdomain("tempero.servicedelivery.com.br")

    assert subdomain == "tempero"


def test_extract_subdomain_accepts_base_domain_with_wildcard_and_leading_dot(monkeypatch):
    monkeypatch.setattr("app.services.tenant_resolver.PUBLIC_BASE_DOMAIN", "*.servicedelivery.com.br")

    wildcard_subdomain = TenantResolver.extract_subdomain("tempero.servicedelivery.com.br")

    monkeypatch.setattr("app.services.tenant_resolver.PUBLIC_BASE_DOMAIN", ".servicedelivery.com.br")

    dotted_subdomain = TenantResolver.extract_subdomain("tempero.servicedelivery.com.br")

    assert wildcard_subdomain == "tempero"
    assert dotted_subdomain == "tempero"


def test_extract_subdomain_from_request_prioritizes_forwarded_host(monkeypatch):
    monkeypatch.setenv("BASE_DOMAIN", "servicedelivery.com.br")
    request = _build_request(
        "/api/dashboard/overview",
        headers={
            "host": "servicedelivery.com.br",
            "x-forwarded-host": "tempero.servicedelivery.com.br:443",
        },
    )

    subdomain = TenantResolver.extract_subdomain_from_request(request)

    assert subdomain == "tempero"


def test_extract_subdomain_raises_for_invalid_host(monkeypatch):
    monkeypatch.setenv("BASE_DOMAIN", "servicedelivery.com.br")

    with pytest.raises(TenantResolutionError):
        TenantResolver.extract_subdomain("tempero.outrabase.com")
