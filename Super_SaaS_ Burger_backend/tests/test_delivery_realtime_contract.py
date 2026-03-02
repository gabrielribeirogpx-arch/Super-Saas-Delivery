from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_openapi_contains_delivery_post_endpoints(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "post" in paths["/api/delivery/{order_id}/start"]
    assert "post" in paths["/api/delivery/{order_id}/complete"]


def test_delivery_start_emits_order_status_changed_event():
    from app.routers.delivery_api import start_delivery_order

    order = SimpleNamespace(
        id=10,
        tenant_id=5,
        status="READY",
        assigned_delivery_user_id=None,
        start_delivery_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _Db:
        committed = False

        def query(self, _model):
            return _Query()

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed") as emit_mock:
        result = start_delivery_order(order_id=10, db=db, current_user=current_user)

    assert result["status"] == "OUT_FOR_DELIVERY"
    assert db.committed is True
    emit_mock.assert_called_once_with(order, "READY")


def test_delivery_status_change_handler_publishes_to_delivery_channel():
    from app.services.event_handlers import handle_order_status_changed_delivery_stream

    payload = {"tenant_id": 3, "order_id": 10, "status": "OUT_FOR_DELIVERY"}

    with patch("app.services.event_handlers.publish_delivery_event") as publish_mock:
        handle_order_status_changed_delivery_stream(payload)

    publish_mock.assert_called_once_with(3, payload)
