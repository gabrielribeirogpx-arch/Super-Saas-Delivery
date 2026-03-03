from fastapi.testclient import TestClient

from app.routers.delivery_ws import _extract_admin_connection_claims, _extract_connection_claims


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


def test_extract_admin_connection_claims_requires_admin_role(monkeypatch):
    class _WebSocket:
        cookies = {"admin_session": "session-token"}

    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_admin_session",
        lambda _token: {"tenant_id": 3, "role": "owner"},
    )

    try:
        _extract_admin_connection_claims(_WebSocket())
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "ADMIN" in str(exc)


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
