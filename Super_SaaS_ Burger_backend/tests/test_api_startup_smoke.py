from fastapi.testclient import TestClient


REQUIRED_ROUTES = {
    "/api/orders/{order_id}/ticket",
    "/api/admin/bootstrap",
    "/api/onboarding/tenant",
}


def test_api_startup_and_router_registration(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    paths = {route.path for route in main.app.routes}
    assert REQUIRED_ROUTES.issubset(paths)
