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
        email="5511999998888@tenant.com",
        password_hash="hashed-password",
        role="DELIVERY",
        active=True,
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
            payload=DeliveryLoginPayload(email="rider@example.com", password="secret"),
            request=request,
            db=_Db(),
        )

    assert response["token_type"] == "bearer"
    assert response["access_token"] == "delivery-token"
    token_mock.assert_called_once_with(
        "12",
        extra={
            "tenant_id": 5,
            "delivery_user_id": 12,
            "role": "delivery",
        },
    )


def test_delivery_login_rejects_when_no_delivery_user_matches():
    from fastapi import HTTPException

    from app.routers.delivery_api import DeliveryLoginPayload, delivery_login

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _Db:
        def query(self, _model):
            return _Query()

    request = SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=5)))

    with patch("app.routers.delivery_api.verify_password", return_value=True):
        try:
            delivery_login(
                payload=DeliveryLoginPayload(email="rider@example.com", password="secret"),
                request=request,
                db=_Db(),
            )
            assert False, "expected HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 401


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

    with patch("app.services.event_handlers.publish_delivery_assignment_event") as publish_mock:
        handle_order_status_changed_delivery_stream(payload)

    publish_mock.assert_called_once_with(
        tenant_id=3,
        order_id=10,
        delivery_user_id=21,
        payload=payload,
    )


def test_delivery_start_creates_started_log():
    from app.routers.delivery_api import start_delivery_order
    from app.models.delivery_tracking import DeliveryTracking

    order = SimpleNamespace(
        id=10,
        tenant_id=5,
        status="READY",
        assigned_delivery_user_id=None,
        start_delivery_at=None,
    )

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _Db:
        committed = False

        def __init__(self):
            self.added = []

        def query(self, model):
            if model is DeliveryTracking:
                return _TrackingQuery()
            return _OrderQuery()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed"):
        start_delivery_order(order_id=10, db=db, current_user=current_user)

    assert db.committed is True
    assert len(db.added) == 2
    assert db.added[0].order_id == 10
    assert db.added[0].delivery_user_id == 99
    assert db.added[1].event_type == "started"
    assert db.added[1].tenant_id == 5
    assert db.added[1].order_id == 10
    assert db.added[1].delivery_user_id == 99


def test_delivery_start_does_not_create_tracking_when_it_already_exists():
    from app.routers.delivery_api import start_delivery_order
    from app.models.delivery_tracking import DeliveryTracking

    order = SimpleNamespace(
        id=10,
        tenant_id=5,
        status="READY",
        assigned_delivery_user_id=None,
        start_delivery_at=None,
    )

    existing_tracking = SimpleNamespace(order_id=10)

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return existing_tracking

    class _Db:
        def __init__(self):
            self.added = []

        def query(self, model):
            if model is DeliveryTracking:
                return _TrackingQuery()
            return _OrderQuery()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            return None

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed"):
        start_delivery_order(order_id=10, db=db, current_user=current_user)

    assert len(db.added) == 1
    assert db.added[0].event_type == "started"


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
        delivery_address_json={"lat": -23.56, "lng": -46.62},
    )
    tracking = SimpleNamespace(
        order_id=10,
        current_lat=None,
        current_lng=None,
        route_distance_meters=None,
        route_duration_seconds=None,
        expected_delivery_at=None,
    )

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return tracking

    class _Db:
        committed = False

        def __init__(self):
            self.added = []

        def query(self, model):
            from app.models.delivery_tracking import DeliveryTracking
            if model is DeliveryTracking:
                return _TrackingQuery()
            return _OrderQuery()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = _Db()
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    payload = DeliveryLocationPayload(order_id=10, latitude=-23.55, longitude=-46.63)
    with (
        patch("app.routers.delivery_api.publish_delivery_location_event") as publish_mock,
        patch("app.routers.delivery_api.publish_public_tracking_event") as public_mock,
        patch("app.routers.delivery_api.publish_order_tracking_eta_event") as eta_mock,
    ):
        response = create_delivery_location_log(payload=payload, db=db, current_user=current_user)

    publish_mock.assert_called_once_with(
        tenant_id=5,
        delivery_user_id=99,
        lat=-23.55,
        lng=-46.63,
        order_id=10,
    )
    public_mock.assert_called_once()
    eta_mock.assert_called_once()
    assert response["ok"] is True
    assert db.committed is True
    assert len(db.added) == 1
    assert db.added[0].event_type == "location_update"
    assert db.added[0].tenant_id == 5
    assert db.added[0].order_id == 10
    assert db.added[0].delivery_user_id == 99
    assert db.added[0].latitude == -23.55
    assert db.added[0].longitude == -46.63
    assert tracking.current_lat == -23.55
    assert tracking.current_lng == -46.63
    assert isinstance(tracking.route_distance_meters, int)
    assert isinstance(tracking.route_duration_seconds, int)


def test_delivery_location_eta_update_enforces_tenant_isolation():
    from fastapi import HTTPException

    from app.routers.delivery_api import DeliveryLocationPayload, create_delivery_location_log

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _Db:
        def query(self, _model):
            return _OrderQuery()

    payload = DeliveryLocationPayload(order_id=10, latitude=-23.55, longitude=-46.63)
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    try:
        create_delivery_location_log(payload=payload, db=_Db(), current_user=current_user)
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404


def test_delivery_start_is_idempotent_and_does_not_duplicate_tracking():
    from app.models.delivery_tracking import DeliveryTracking
    from app.routers.delivery_api import start_delivery_order

    order = SimpleNamespace(
        id=20,
        tenant_id=5,
        status="READY",
        assigned_delivery_user_id=None,
        start_delivery_at=None,
    )
    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def __init__(self, db):
            self._db = db

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self._db.tracking

    class _Db:
        def __init__(self):
            self.added = []
            self.tracking = None

        def query(self, model):
            if model is DeliveryTracking:
                return _TrackingQuery(self)
            return _OrderQuery()

        def add(self, obj):
            self.added.append(obj)
            if isinstance(obj, DeliveryTracking):
                self.tracking = obj

        def commit(self):
            return None

    db = _Db()

    with (
        patch("app.routers.delivery_api.emit_order_status_changed"),
        patch("app.routers.delivery_api.calculate_eta", return_value=900),
    ):
        first = start_delivery_order(order_id=20, db=db, current_user=current_user)
        second = start_delivery_order(order_id=20, db=db, current_user=current_user)

    trackings = [obj for obj in db.added if isinstance(obj, DeliveryTracking)]
    assert first["status"] == "OUT_FOR_DELIVERY"
    assert second["status"] == "OUT_FOR_DELIVERY"
    assert len(trackings) == 1
    assert trackings[0].estimated_duration_seconds == 900
    assert trackings[0].expected_delivery_at is not None


def test_get_delivery_order_eta_returns_expected_fields_and_statuses():
    from app.models.delivery_tracking import DeliveryTracking
    from app.models.order import Order
    from app.routers.delivery_api import get_delivery_order_eta

    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")
    order = SimpleNamespace(id=10, tenant_id=5)

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def __init__(self, tracking):
            self._tracking = tracking

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self._tracking

    class _Db:
        def __init__(self, tracking):
            self._tracking = tracking

        def query(self, model):
            if model is Order:
                return _OrderQuery()
            if model is DeliveryTracking:
                return _TrackingQuery(self._tracking)
            raise AssertionError("unexpected model")

    scenarios = [
        (1200, "ON_TIME"),
        (120, "ARRIVING"),
        (0, "DELAYED"),
    ]

    for route_duration_seconds, expected_status in scenarios:
        tracking = SimpleNamespace(
            route_duration_seconds=route_duration_seconds,
            route_distance_meters=2300,
        )
        response = get_delivery_order_eta(order_id=10, db=_Db(tracking), current_user=current_user)
        assert set(response.keys()) == {"remaining_seconds", "status", "distance_meters"}
        assert response["status"] == expected_status
        assert response["distance_meters"] == 2300


def test_get_delivery_order_eta_returns_404_when_tracking_not_found():
    from fastapi import HTTPException

    from app.models.delivery_tracking import DeliveryTracking
    from app.models.order import Order
    from app.routers.delivery_api import get_delivery_order_eta

    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")
    order = SimpleNamespace(id=10, tenant_id=5)

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _Db:
        def query(self, model):
            if model is Order:
                return _OrderQuery()
            if model is DeliveryTracking:
                return _TrackingQuery()
            raise AssertionError("unexpected model")

    try:
        get_delivery_order_eta(order_id=10, db=_Db(), current_user=current_user)
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404


def test_delivery_complete_sets_tracking_completed_at():
    from datetime import datetime, timezone

    from app.models.delivery_tracking import DeliveryTracking
    from app.routers.delivery_api import complete_delivery_order

    order = SimpleNamespace(id=10, tenant_id=5, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=99)
    tracking = SimpleNamespace(order_id=10, completed_at=None)

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _TrackingQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return tracking

    class _Db:
        def __init__(self):
            self.added = []

        def query(self, model):
            if model is DeliveryTracking:
                return _TrackingQuery()
            return _OrderQuery()

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            return None

    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    with patch("app.routers.delivery_api.emit_order_status_changed"):
        response = complete_delivery_order(order_id=10, db=_Db(), current_user=current_user)

    assert response == {"ok": True, "status": "DELIVERED", "assigned_delivery_user_id": 99}
    assert tracking.completed_at is not None
    assert isinstance(tracking.completed_at, datetime)
    assert tracking.completed_at.tzinfo == timezone.utc
    assert tracking.route_duration_seconds == 0


def test_delivery_eta_is_blocked_for_order_from_another_tenant():
    from fastapi import HTTPException

    from app.models.order import Order
    from app.routers.delivery_api import get_delivery_order_eta

    current_user = SimpleNamespace(id=99, tenant_id=5, role="DELIVERY")

    class _OrderQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _Db:
        def query(self, model):
            if model is Order:
                return _OrderQuery()
            raise AssertionError("tracking query should not run when tenant is blocked")

    try:
        get_delivery_order_eta(order_id=777, db=_Db(), current_user=current_user)
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
