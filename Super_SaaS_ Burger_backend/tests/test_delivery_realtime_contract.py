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
    assert "/api/delivery/login" not in paths
    assert "/api/delivery/location" not in paths
    assert "/ws/delivery" not in paths
    assert "/ws/admin/delivery-status" not in paths


def test_delivery_login_generates_delivery_jwt_scoped_to_request_tenant():
    from app.routers.delivery_api import DeliveryLoginPayload, delivery_login

    delivery_user = SimpleNamespace(
        id=12,
        tenant_id=5,
        email="delivery@tenant.com",
        password_hash="hashed-password",
        role="DELIVERY",
        is_active=True,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return delivery_user

    class _Db:
        def query(self, _model):
            return _Query()

    request = SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=5)))

    with (
        patch("app.routers.delivery_api.verify_password", return_value=True),
        patch("app.routers.delivery_api.create_access_token", return_value="delivery-token") as token_mock,
    ):
        response = delivery_login(
            payload=DeliveryLoginPayload(email="delivery@tenant.com", password="secret"),
            request=request,
            db=_Db(),
        )

    assert response["token_type"] == "bearer"
    assert response["access_token"] == "delivery-token"
    token_mock.assert_called_once_with(
        "12",
        extra={
            "tenant_id": 5,
            "role": "DELIVERY",
        },
    )


def test_delivery_login_rejects_non_delivery_user_even_with_valid_credentials():
    from fastapi import HTTPException

    from app.routers.delivery_api import DeliveryLoginPayload, delivery_login

    owner_user = SimpleNamespace(
        id=9,
        tenant_id=5,
        email="owner@tenant.com",
        password_hash="hashed-password",
        role="OWNER",
        is_active=True,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return owner_user

    class _Db:
        def query(self, _model):
            return _Query()

    request = SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=5)))

    with patch("app.routers.delivery_api.verify_password", return_value=True):
        try:
            delivery_login(
                payload=DeliveryLoginPayload(email="owner@tenant.com", password="secret"),
                request=request,
                db=_Db(),
            )
            assert False, "expected HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 403


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

        def add(self, _obj):
            return None

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

    payload = {
        "tenant_id": 3,
        "order_id": 10,
        "status": "OUT_FOR_DELIVERY",
        "assigned_delivery_user_id": 21,
    }

    with patch("app.services.event_handlers.publish_delivery_event") as publish_mock:
        handle_order_status_changed_delivery_stream(payload)

    publish_mock.assert_called_once_with(3, 21, payload)


def test_delivery_start_creates_started_log():
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

        def __init__(self):
            self.added = []

        def query(self, _model):
            return _Query()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed"):
        start_delivery_order(order_id=10, db=db, current_user=current_user)

    assert db.committed is True
    assert len(db.added) == 1
    assert db.added[0].event_type == "started"
    assert db.added[0].tenant_id == 5
    assert db.added[0].order_id == 10
    assert db.added[0].delivery_user_id == 99


def test_delivery_complete_creates_completed_log():
    from app.routers.delivery_api import complete_delivery_order

    order = SimpleNamespace(
        id=10,
        tenant_id=5,
        status="OUT_FOR_DELIVERY",
        assigned_delivery_user_id=99,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _Db:
        committed = False

        def __init__(self):
            self.added = []

        def query(self, _model):
            return _Query()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed"):
        complete_delivery_order(order_id=10, db=db, current_user=current_user)

    assert db.committed is True
    assert len(db.added) == 1
    assert db.added[0].event_type == "completed"
    assert db.added[0].tenant_id == 5
    assert db.added[0].order_id == 10
    assert db.added[0].delivery_user_id == 99


def test_delivery_location_creates_location_update_log():
    from app.routers.delivery_api import DeliveryLocationPayload, create_delivery_location_log

    order = SimpleNamespace(
        id=10,
        tenant_id=5,
        status="OUT_FOR_DELIVERY",
        assigned_delivery_user_id=99,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _Db:
        committed = False

        def __init__(self):
            self.added = []

        def query(self, _model):
            return _Query()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    payload = DeliveryLocationPayload(order_id=10, latitude=-23.55, longitude=-46.63)
    with patch("app.routers.delivery_api.publish_delivery_location_event") as publish_mock:
        response = create_delivery_location_log(payload=payload, db=db, current_user=current_user)

    publish_mock.assert_called_once_with(
        tenant_id=5,
        delivery_user_id=99,
        lat=-23.55,
        lng=-46.63,
    )
    assert response["ok"] is True
    assert db.committed is True
    assert len(db.added) == 1
    assert db.added[0].event_type == "location_update"
    assert db.added[0].tenant_id == 5
    assert db.added[0].order_id == 10
    assert db.added[0].delivery_user_id == 99
    assert db.added[0].latitude == -23.55
    assert db.added[0].longitude == -46.63


def test_delivery_complete_expires_tracking_token():
    from app.routers.delivery_api import complete_delivery_order

    order = SimpleNamespace(
        id=10,
        tenant_id=5,
        status="OUT_FOR_DELIVERY",
        assigned_delivery_user_id=99,
        tracking_expires_at=None,
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _Db:
        committed = False

        def __init__(self):
            self.added = []

        def query(self, _model):
            return _Query()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed"), patch(
        "app.routers.delivery_api.publish_tracking_snapshot"
    ):
        complete_delivery_order(order_id=10, db=db, current_user=current_user)

    assert order.tracking_expires_at is not None
