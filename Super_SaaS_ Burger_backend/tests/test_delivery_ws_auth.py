import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.routers.delivery_ws import _extract_connection_claims


def test_extract_connection_claims_requires_delivery_role(monkeypatch):
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "OWNER", "tenant_id": 1, "delivery_user_id": 2},
    )

    try:
        _extract_connection_claims("token")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "DELIVERY" in str(exc)


def test_extract_connection_claims_reads_tenant_and_delivery_user(monkeypatch):
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "DELIVERY", "tenant_id": "7", "delivery_user_id": "12"},
    )

    tenant_id, delivery_user_id = _extract_connection_claims("token")

    assert tenant_id == 7
    assert delivery_user_id == 12


def test_delivery_ws_publishes_online_and_offline_events(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "DELIVERY", "tenant_id": 8, "delivery_user_id": 13},
    )

    published_calls = []
    monkeypatch.setattr(
        "app.routers.delivery_ws.publish_delivery_status_event",
        lambda tenant_id, delivery_user_id, status: published_calls.append((tenant_id, delivery_user_id, status)),
    )

    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/delivery?token=delivery-token"):
            pass

    assert published_calls == [
        (8, 13, "online"),
        (8, 13, "offline"),
    ]


def test_admin_delivery_ws_requires_tenant_query_param(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_admin_session",
        lambda _token: {"tenant_id": 3, "role": "admin"},
    )

    with TestClient(main.app) as client:
        client.cookies.set("admin_session", "session-token")
        with client.websocket_connect("/ws/admin/delivery-status") as websocket:
            try:
                websocket.receive_text()
                assert False, "expected websocket disconnect"
            except WebSocketDisconnect as exc:
                assert exc.code == 1008


def test_admin_delivery_ws_rejects_tenant_mismatch(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_admin_session",
        lambda _token: {"tenant_id": 3, "role": "admin"},
    )

    with TestClient(main.app) as client:
        client.cookies.set("admin_session", "session-token")
        with client.websocket_connect("/ws/admin/delivery-status?tenant_id=4") as websocket:
            try:
                websocket.receive_text()
                assert False, "expected websocket disconnect"
            except WebSocketDisconnect as exc:
                assert exc.code == 1008


def test_admin_delivery_ws_accepts_matching_tenant_and_fails_if_redis_unavailable(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_admin_session",
        lambda _token: {"tenant_id": 3, "role": "admin"},
    )
    monkeypatch.setattr("app.routers.delivery_ws.get_async_redis_client", lambda: None)

    with TestClient(main.app) as client:
        client.cookies.set("admin_session", "session-token")
        with client.websocket_connect("/ws/admin/delivery-status?tenant_id=3") as websocket:
            try:
                websocket.receive_text()
                assert False, "expected websocket disconnect"
            except WebSocketDisconnect as exc:
                assert exc.code == 1011



def test_public_tracking_ws_rejects_invalid_token(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    class _Db:
        def close(self):
            return None

    monkeypatch.setattr("app.routers.delivery_ws.SessionLocal", lambda: _Db())
    monkeypatch.setattr("app.routers.delivery_ws._load_order_by_tracking_token", lambda *_args, **_kwargs: None)

    with TestClient(main.app) as client:
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws/public/tracking/invalid-token"):
                pass
        assert excinfo.value.code == 1008


def test_public_tracking_ws_rejects_expired_token(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    class _Db:
        def close(self):
            return None

    order = type("OrderObj", (), {
        "tenant_id": 1,
        "id": 2,
        "status": "OUT_FOR_DELIVERY",
        "tracking_token": "token",
        "tracking_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    })()

    monkeypatch.setattr("app.routers.delivery_ws.SessionLocal", lambda: _Db())
    monkeypatch.setattr("app.routers.delivery_ws._load_order_by_tracking_token", lambda *_args, **_kwargs: order)

    with TestClient(main.app) as client:
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws/public/tracking/token"):
                pass
        assert excinfo.value.code == 1008
