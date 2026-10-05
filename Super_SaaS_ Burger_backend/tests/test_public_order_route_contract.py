from fastapi.testclient import TestClient
from types import SimpleNamespace


def test_canonical_public_order_route_is_registered_and_creates_order(monkeypatch):
    from app import main
    from app.routers import public_menu
    from app.services.tenant_resolver import TenantResolver

    captured = {}

    async def fake_create(request, payload, db, raw_payload=None):
        captured["tenant"] = request.query_params.get("tenant")
        captured["phone"] = payload.customer_phone
        return {
            "order_number": 42,
            "daily_order_number": 42,
            "tracking_token": "tracking-token",
            "status": "pending",
            "estimated_time": 30,
            "subtotal": 25,
            "delivery_fee": 0,
            "total": 25,
            "order_type": "pickup",
            "payment_method": "pix",
            "items": [],
        }

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(public_menu, "_create_public_order_payload", fake_create)
    monkeypatch.setattr(
        TenantResolver,
        "resolve_tenant_from_request",
        classmethod(lambda cls, db, request: SimpleNamespace(id=21, slug="tempero")),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/public/orders?tenant=tempero",
            json={
                "customer_phone": "11999999999",
                "delivery_type": "RETIRADA",
                "order_type": "pickup",
                "payment_method": "pix",
                "items": [{"item_id": 1, "name": "Lanche", "quantity": 1, "unit_price": 25}],
            },
        )

    assert "/public/orders" in main._registered_route_paths()
    assert "/api/public/orders" not in main._registered_route_paths()
    assert response.status_code == 200
    assert response.json()["order_number"] == 42
    assert captured == {"tenant": "tempero", "phone": "11999999999"}
