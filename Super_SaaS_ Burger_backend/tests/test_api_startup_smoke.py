from fastapi.testclient import TestClient


REQUIRED_ROUTES = {
    "/api/orders/{order_id}/ticket",
    "/api/admin/bootstrap",
    "/api/onboarding/tenant",
    "/api/dashboard/overview",
    "/api/dashboard/timeseries",
    "/api/dashboard/top-items",
    "/api/dashboard/recent-orders",
    "/api/inventory/items",
    "/api/reports/financial/summary",
}


def test_api_startup_and_router_registration(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.get("/")
        docs_response = client.get("/docs")
        openapi_response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200

    paths = {route.path for route in main.app.routes}
    assert REQUIRED_ROUTES.issubset(paths)


def test_cors_allows_tenant_subdomain_origin(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.options(
            "/health",
            headers={
                "origin": "https://tempero.servicedelivery.com.br",
                "access-control-request-method": "GET",
                "access-control-request-headers": "content-type,authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://tempero.servicedelivery.com.br"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-methods")
    assert response.headers.get("access-control-allow-headers") is not None



def test_delivery_login_preflight_allows_tempero_origin(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.options(
            "/api/delivery/auth/login",
            headers={
                "origin": "https://tempero.servicedelivery.com.br",
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type,authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://tempero.servicedelivery.com.br"
    assert response.headers.get("access-control-allow-methods") is not None
    assert response.headers.get("access-control-allow-headers") is not None

def test_cors_preflight_rejects_disallowed_origin(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.options(
            "/api/delivery/auth/login",
            headers={
                "origin": "https://malicious.example",
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type,authorization",
            },
        )

    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None


def test_store_orders_preflight_accepts_origin_when_env_has_quotes_and_trailing_slash(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv('CORS_ORIGINS', '"https://tempero.servicedelivery.com.br/", https://servicedelivery.com.br/')

    for module_name in ('app.core.config', 'app.main'):
        if module_name in sys.modules:
            del sys.modules[module_name]

    from app import main  # type: ignore

    monkeypatch.setattr(main, '_startup_tasks', lambda: None)

    with TestClient(main.app) as client:
        response = client.options(
            '/api/store/orders',
            headers={
                'origin': 'https://tempero.servicedelivery.com.br',
                'access-control-request-method': 'POST',
                'access-control-request-headers': 'content-type,authorization',
            },
        )

    assert response.status_code == 200
    assert response.headers.get('access-control-allow-origin') == 'https://tempero.servicedelivery.com.br'
    assert response.headers.get('access-control-allow-methods') is not None
    assert response.headers.get('access-control-allow-headers') is not None
    assert response.headers.get('access-control-allow-credentials') == 'true'

    importlib.invalidate_caches()
