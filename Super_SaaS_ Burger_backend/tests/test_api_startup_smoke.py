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
