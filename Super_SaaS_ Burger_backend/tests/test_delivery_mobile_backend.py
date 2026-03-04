from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_delivery_auth_login_uses_email_and_returns_delivery_claims():
    from app.routers.delivery_api import DeliveryLoginPayload, delivery_auth_login

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
        patch("app.routers.delivery_api.create_access_token", return_value="delivery-mobile-token") as token_mock,
    ):
        response = delivery_auth_login(
            payload=DeliveryLoginPayload(email="rider@example.com", password="secret"),
            request=request,
            db=_Db(),
        )

    assert response["token_type"] == "bearer"
    assert response["access_token"] == "delivery-mobile-token"
    token_mock.assert_called_once_with(
        "12",
        extra={
            "tenant_id": 5,
            "delivery_user_id": 12,
            "role": "delivery",
        },
    )


def test_delivery_auth_login_filters_only_active_delivery_admin_users():
    from app.routers.delivery_api import DeliveryLoginPayload, delivery_auth_login

    captured_filters = []

    class _Query:
        def filter(self, *args, **_kwargs):
            captured_filters.extend(args)
            return self

        def first(self):
            return None

    class _Db:
        def query(self, _model):
            return _Query()

    request = SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=5)))

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        delivery_auth_login(
            payload=DeliveryLoginPayload(email="rider@example.com", password="secret"),
            request=request,
            db=_Db(),
        )

    assert exc.value.status_code == 401

    serialized_filters = " | ".join(str(item) for item in captured_filters)
    assert "admin_users.active" in serialized_filters
    assert "lower(admin_users.email)" in serialized_filters


def test_delivery_location_ws_accepts_then_validates_and_publishes(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "delivery", "tenant_id": 8, "delivery_user_id": 13},
    )

    published_calls = []
    monkeypatch.setattr(
        "app.routers.delivery_ws.publish_delivery_location_event",
        lambda **kwargs: published_calls.append(kwargs),
    )

    with TestClient(main.app) as client:
        with client.websocket_connect(
            "/ws/delivery/location",
            headers={"authorization": "Bearer delivery-token"},
        ) as websocket:
            websocket.send_json({"lat": -23.5, "lng": -46.6, "status": "online"})

    assert published_calls == [
        {
            "tenant_id": 8,
            "delivery_user_id": 13,
            "lat": -23.5,
            "lng": -46.6,
            "status": "online",
        }
    ]


def test_delivery_location_ws_rejects_invalid_role(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "OWNER", "tenant_id": 8, "delivery_user_id": 13},
    )

    with TestClient(main.app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                "/ws/delivery/location",
                headers={"authorization": "Bearer delivery-token"},
            ):
                pass
    assert exc.value.code == 1008
