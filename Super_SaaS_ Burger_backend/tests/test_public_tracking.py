from datetime import datetime, timedelta, timezone
import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.models.order import Order
from app.routers.public_tracking import TrackingNotFound, _resolve_public_tracking_order


class FakeOrderQuery:
    def __init__(self, order, tracking_tokens=None):
        self._order = order
        self._tracking_tokens = tracking_tokens or []
        self._selected_model = Order

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        if self._selected_model is Order.tracking_token:
            return [(token,) for token in self._tracking_tokens]
        return []

    def first(self):
        return self._order


class FakeDb:
    def __init__(self, order, tracking_tokens=None):
        self._order = order
        self._tracking_tokens = tracking_tokens or []

    def expire_all(self):
        return None

    def query(self, model):
        query = FakeOrderQuery(self._order, tracking_tokens=self._tracking_tokens)
        query._selected_model = model
        return query



def _build_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/public/order/secure-public-token",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    request = Request(scope)
    request.state.tenant = None
    return request


def _order_with_token(*, expires_delta_days: int, revoked: bool):
    return SimpleNamespace(
        id=33,
        tenant_id=9,
        tracking_token="secure-public-token",
        tracking_expires_at=datetime.now(timezone.utc) + timedelta(days=expires_delta_days),
        tracking_revoked=revoked,
    )



def test_generate_tracking_token_fits_database_limit():
    from app.services.public_tracking import TRACKING_TOKEN_MAX_LENGTH, generate_tracking_token

    token = generate_tracking_token()

    assert token
    assert len(token) <= TRACKING_TOKEN_MAX_LENGTH



def test_resolve_public_tracking_rejects_blank_token():
    with pytest.raises(TrackingNotFound):
        _resolve_public_tracking_order(FakeDb(order=None), "   ")



def test_resolve_public_tracking_rejects_expired_token():
    order = _order_with_token(expires_delta_days=-1, revoked=False)

    with pytest.raises(TrackingNotFound):
        _resolve_public_tracking_order(FakeDb(order=order), order.tracking_token)



def test_resolve_public_tracking_rejects_revoked_token():
    order = _order_with_token(expires_delta_days=2, revoked=True)

    with pytest.raises(TrackingNotFound):
        _resolve_public_tracking_order(FakeDb(order=order), order.tracking_token)


def test_resolve_public_tracking_restores_missing_expiration_for_legacy_orders():
    order = SimpleNamespace(
        id=33,
        tenant_id=9,
        tracking_token="legacy-public-token",
        tracking_expires_at=None,
        tracking_revoked=False,
    )

    class _LegacyDb(FakeDb):
        def __init__(self, order):
            super().__init__(order=order)
            self.committed = False
            self.refreshed = False
            self.added = None

        def add(self, instance):
            self.added = instance

        def commit(self):
            self.committed = True

        def refresh(self, instance):
            self.refreshed = True

    db = _LegacyDb(order)

    resolved = _resolve_public_tracking_order(db, order.tracking_token)

    assert resolved is order
    assert order.tracking_expires_at is not None
    assert db.added is order
    assert db.committed is True
    assert db.refreshed is True



def test_resolve_public_tracking_prevents_enumeration_of_missing_tokens():
    with pytest.raises(TrackingNotFound):
        _resolve_public_tracking_order(FakeDb(order=None), "missing-secure-public-token")


def test_valid_token_cannot_resolve_a_different_order():
    expected_token = "token-for-order-33"
    order = _order_with_token(expires_delta_days=2, revoked=False)
    order.tracking_token = expected_token

    class _TokenQuery(FakeOrderQuery):
        def filter(self, expression, *_args, **_kwargs):
            compared_token = getattr(getattr(expression, "right", None), "value", None)
            if compared_token != expected_token:
                self._order = None
            return self

    class _TokenDb(FakeDb):
        def query(self, model):
            return _TokenQuery(self._order)

    assert _resolve_public_tracking_order(_TokenDb(order), expected_token) is order
    with pytest.raises(TrackingNotFound):
        _resolve_public_tracking_order(_TokenDb(order), "token-for-another-order")



def test_public_tracking_sse_rejects_invalid_token(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr("app.routers.public_tracking._resolve_public_tracking_order", lambda *_args, **_kwargs: (_ for _ in ()).throw(TrackingNotFound()))

    with TestClient(main.app) as client:
        response = client.get("/api/public/sse/not-a-valid-token")

    assert response.status_code == 404
    assert response.json() == {"detail": "Rastreamento não encontrado"}


def test_public_tracking_sse_skips_empty_initial_tracking_payload(monkeypatch):
    from app.routers.public_tracking import sse_public_tracking

    order = SimpleNamespace(id=44, tenant_id=9, tracking_token="secure-public-token")

    async def _run_test():
        checks = iter([False, True])

        async def is_disconnected():
            return next(checks)

        request = SimpleNamespace(is_disconnected=is_disconnected, state=SimpleNamespace())

        async def _build_snapshot(*_args, **_kwargs):
            return {
                "progress": 0.0,
                "distance_meters": None,
                "duration_seconds": None,
                "driver_lat": None,
                "driver_lng": None,
                "destination_lat": -23.5,
                "destination_lng": -46.6,
                "last_location": None,
                "initial_distance_meters": None,
            }

        monkeypatch.setattr("app.routers.public_tracking.SessionLocal", lambda: SimpleNamespace(close=lambda: None))
        monkeypatch.setattr("app.routers.public_tracking._resolve_public_tracking_order", lambda *_args, **_kwargs: order)
        monkeypatch.setattr("app.routers.public_tracking._build_public_tracking_snapshot_async", _build_snapshot)
        monkeypatch.setattr("app.routers.public_tracking.get_async_redis_client", lambda: None)

        response = await sse_public_tracking("secure-public-token", request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)

        assert chunks == [": keep-alive\n\n"]

    asyncio.run(_run_test())



def test_build_public_tracking_snapshot_reads_delivery_name_from_admin_users():
    from app.models.admin_user import AdminUser
    from app.models.delivery_log import DeliveryLog
    from app.routers.public_tracking import _build_public_tracking_snapshot

    order = SimpleNamespace(id=44, tenant_id=9, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=777)
    admin_user = SimpleNamespace(name="Rider Admin")
    last_location = SimpleNamespace(latitude=-23.0, longitude=-46.0)

    class _Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            if self.model is AdminUser:
                return admin_user
            if self.model is DeliveryLog:
                return last_location
            return None

    class _Db:
        def query(self, model):
            return _Query(model)

    payload = _build_public_tracking_snapshot(_Db(), order)

    assert payload["delivery_user"] == {"name": "Rider Admin"}
    assert payload["last_location"] == {"lat": -23.0, "lng": -46.0}



def test_build_public_order_payload_uses_public_settings_and_fallbacks():
    from app.models.order_item import OrderItem
    from app.models.tenant import Tenant
    from app.models.tenant_public_settings import TenantPublicSettings
    from app.routers.public_tracking import _build_public_order_payload

    order = SimpleNamespace(
        id=44,
        daily_order_number=None,
        tenant_id=9,
        status="RECEBIDO",
        payment_method="pix",
        created_at=None,
        ready_at=None,
        start_delivery_at=None,
        estimated_delivery_minutes=None,
        delivery_type="ENTREGA",
        order_type="delivery",
        total_cents=3590,
        valor_total=0,
    )
    tenant = SimpleNamespace(name="Tempero da Casa", business_name="")
    public_settings = SimpleNamespace(logo_url="https://cdn.example/logo.png", primary_color="#22c55e")
    items = [SimpleNamespace(name="Hambúrguer", quantity=2)]

    class _Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            if self.model is Tenant:
                return tenant
            if self.model is TenantPublicSettings:
                return public_settings
            return None

        def all(self):
            if self.model is OrderItem:
                return items
            return []

    class _Db:
        def query(self, model):
            return _Query(model)

    payload = _build_public_order_payload(_Db(), order)

    assert payload["order_number"] == 44
    assert "order_id" not in payload
    assert payload["total"] == 3590.0
    assert payload["total_cents"] == 3590
    assert payload["store_name"] == "Tempero da Casa"
    assert payload["store_logo_url"] == "https://cdn.example/logo.png"
    assert payload["primary_color"] == "#22c55e"


def test_numeric_location_endpoint_is_an_opaque_deprecated_tombstone(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        existing_shape = client.get("/api/location/1")
        another_shape = client.get("/api/location/999999")

    assert existing_shape.status_code == 404
    assert another_shape.status_code == 404
    assert existing_shape.json() == another_shape.json() == {"detail": "Rastreamento não encontrado"}


def test_public_tracking_logs_only_token_fingerprint(caplog):
    token = "complete-secret-public-tracking-token"
    order = SimpleNamespace(
        id=33,
        tenant_id=9,
        tracking_token=token,
        tracking_expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        tracking_revoked=False,
    )

    with caplog.at_level(logging.INFO, logger="app.routers.public_tracking"):
        resolved = _resolve_public_tracking_order(FakeDb(order=order), token)

    assert resolved is order
    assert token not in caplog.text
    assert "token_fingerprint=" in caplog.text


def test_tracking_token_is_redacted_from_request_log_paths():
    from app.core.log_redaction import redact_public_tracking_tokens, tracking_token_fingerprint

    token = "complete-secret-public-tracking-token"
    logged_path = redact_public_tracking_tokens(f"GET /api/public/order/{token}?tenant_id=9 HTTP/1.1")

    assert token not in logged_path
    assert tracking_token_fingerprint(token) in logged_path



def test_resolve_public_tracking_sets_request_tenant_from_order():
    order = _order_with_token(expires_delta_days=2, revoked=False)
    request = _build_request({"x-tenant-id": "other-tenant"})

    resolved = _resolve_public_tracking_order(FakeDb(order=order, tracking_tokens=[order.tracking_token]), order.tracking_token, request)

    assert resolved == order
    assert request.state.tenant_id == order.tenant_id


def test_async_tracking_snapshot_awaits_live_progress_once_without_sync_bridge(monkeypatch):
    from unittest.mock import AsyncMock
    from app.routers import public_tracking

    order = SimpleNamespace(
        id=44, tenant_id=9, status="PRONTO", assigned_delivery_user_id=None
    )
    fallback_location = SimpleNamespace(latitude=-23.0, longitude=-46.0)

    class Query:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return fallback_location

    db = SimpleNamespace(query=lambda _model: Query())
    live = {
        "progress": 0.75,
        "distance_meters": 250,
        "duration_seconds": 90,
        "driver_lat": -23.1,
        "driver_lng": -46.1,
        "destination_lat": -23.2,
        "destination_lng": -46.2,
        "initial_distance_meters": 1000,
        "last_location": {"lat": -23.1, "lng": -46.1, "updated_at": "now"},
    }
    loader = AsyncMock(return_value=live)

    def forbidden_sync_bridge(*_args, **_kwargs):
        pytest.fail("Async SSE snapshot must not enter the synchronous asyncio.run bridge")

    monkeypatch.setattr(public_tracking, "_load_live_progress_snapshot_async", loader)
    monkeypatch.setattr(public_tracking, "_load_live_progress_snapshot", forbidden_sync_bridge)

    payload = asyncio.run(public_tracking._build_public_tracking_snapshot_async(db, order))

    loader.assert_awaited_once_with(db, order)
    assert payload["status"] == "ready"
    assert payload["status_step"] == 3
    assert payload["status_label"] == "Pronto"
    for key, value in live.items():
        assert payload[key] == value


def test_sync_tracking_snapshot_does_not_hide_runtime_errors(monkeypatch):
    from unittest.mock import AsyncMock
    from app.routers import public_tracking

    loader = AsyncMock(side_effect=RuntimeError("snapshot provider failed"))
    monkeypatch.setattr(public_tracking, "_load_live_progress_snapshot_async", loader)
    db, order = object(), object()

    with pytest.raises(RuntimeError, match="snapshot provider failed"):
        public_tracking._load_live_progress_snapshot(db, order)

    loader.assert_awaited_once_with(db, order)


def _status_snapshot(status):
    from app.routers.public_tracking import _resolve_tracking_metadata
    raw, normalized, step, label = _resolve_tracking_metadata(SimpleNamespace(status=status))
    return dict(status=normalized, status_raw=raw, status_step=step, status_label=label)


def _tracking_events(chunks):
    return [
        json.loads(chunk.split("data: ", 1)[1].strip())
        for chunk in chunks if chunk.startswith("event: tracking_update\n")
    ]


def test_sse_without_redis_streams_all_statuses_and_suppresses_unchanged(monkeypatch):
    from app.routers import public_tracking as tracking

    async def run():
        states = iter(["RECEBIDO", "EM_PREPARO", "EM_PREPARO", "PRONTO", "SAIU", "ENTREGUE"])
        checks = iter([False] * 6 + [True])
        async def disconnected():
            return next(checks)
        async def snapshot(*_args):
            return {**_status_snapshot("RECEBIDO"), "driver_lat": None, "driver_lng": None}
        async def no_sleep(_seconds):
            pass
        order = SimpleNamespace(id=44, tenant_id=9)
        monkeypatch.setattr(tracking, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
        monkeypatch.setattr(tracking, "_resolve_public_tracking_order", lambda *_args: order)
        monkeypatch.setattr(tracking, "_build_public_tracking_snapshot_async", snapshot)
        monkeypatch.setattr(tracking, "get_async_redis_client", lambda: None)
        monkeypatch.setattr(tracking, "TRACKING_STATUS_POLL_SECONDS", 0)
        monkeypatch.setattr(tracking, "_poll_public_tracking_status", lambda *_args: _status_snapshot(next(states)))
        monkeypatch.setattr(tracking.asyncio, "sleep", no_sleep)
        response = await tracking.sse_public_tracking("secure-public-token", SimpleNamespace(is_disconnected=disconnected))
        chunks = [chunk async for chunk in response.body_iterator]
        events = _tracking_events(chunks)
        assert [e["status"] for e in events] == ["pending", "preparing", "ready", "delivering", "delivered"]
        assert [e["status_step"] for e in events] == [1, 2, 3, 4, 5]
        assert not any("event: driver_update" in chunk for chunk in chunks)
    asyncio.run(run())


def test_sse_redis_status_only_event_is_emitted_and_clients_are_closed(monkeypatch):
    from app.routers import public_tracking as tracking
    from app.realtime.delivery_envelope import build_delivery_envelope

    async def run():
        checks = iter([False, True])
        closed = []
        class Pubsub:
            async def subscribe(self, channel):
                assert channel == "tenant:9:order:44:tracking"
            async def get_message(self, **_kwargs):
                envelope = build_delivery_envelope(
                    event_type="order.status", tenant_id=9, order_id=44,
                    payload={"status": "PRONTO", "status_step": 99},
                )
                return {"data": json.dumps(envelope)}
            async def aclose(self):
                closed.append("pubsub")
        class Redis:
            def pubsub(self):
                return Pubsub()
            async def aclose(self):
                closed.append("redis")
        async def disconnected():
            return next(checks)
        async def snapshot(*_args):
            return _status_snapshot("EM_PREPARO")
        async def location(*_args):
            return None
        monkeypatch.setattr(tracking, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
        monkeypatch.setattr(tracking, "_resolve_public_tracking_order", lambda *_args: SimpleNamespace(id=44, tenant_id=9))
        monkeypatch.setattr(tracking, "_build_public_tracking_snapshot_async", snapshot)
        monkeypatch.setattr(tracking, "get_async_redis_client", lambda: Redis())
        monkeypatch.setattr(tracking, "get_delivery_location", location)
        response = await tracking.sse_public_tracking("secure-public-token", SimpleNamespace(is_disconnected=disconnected))
        chunks = [chunk async for chunk in response.body_iterator]
        events = _tracking_events(chunks)
        assert [e["status"] for e in events] == ["preparing", "ready"]
        assert events[-1]["status_step"] == 3
        assert events[-1]["status_label"] == "Pronto"
        assert not any("event: driver_update" in chunk for chunk in chunks)
        assert closed == ["pubsub", "redis"]
    asyncio.run(run())


@pytest.mark.parametrize("tenant_id,order_id", [(8, 44), (9, 45)])
def test_status_poll_rejects_changed_order_identity_and_closes_session(monkeypatch, tenant_id, order_id):
    from app.routers import public_tracking as tracking
    closed = []
    db = FakeDb(_order_with_token(expires_delta_days=2, revoked=False))
    db._order.id = 44
    db.close = lambda: closed.append(True)
    monkeypatch.setattr(tracking, "SessionLocal", lambda: db)
    with pytest.raises(TrackingNotFound):
        tracking._poll_public_tracking_status("secure-public-token", tenant_id, order_id)
    assert closed == [True]


@pytest.mark.parametrize("expired,revoked", [(True, False), (False, True)])
def test_status_poll_revalidates_tracking_access(monkeypatch, expired, revoked):
    from app.routers import public_tracking as tracking
    closed = []
    db = FakeDb(_order_with_token(expires_delta_days=-1 if expired else 2, revoked=revoked))
    db.close = lambda: closed.append(True)
    monkeypatch.setattr(tracking, "SessionLocal", lambda: db)
    with pytest.raises(TrackingNotFound):
        tracking._poll_public_tracking_status("secure-public-token", 9, 33)
    assert closed == [True]


def test_status_poll_uses_new_session_each_time(monkeypatch):
    from app.routers import public_tracking as tracking
    sessions, closed = [], []
    statuses = iter(["EM_PREPARO", "PRONTO"])
    def session():
        order = _order_with_token(expires_delta_days=2, revoked=False)
        order.status = next(statuses)
        db = FakeDb(order)
        db.close = lambda: closed.append(db)
        sessions.append(db)
        return db
    monkeypatch.setattr(tracking, "SessionLocal", session)
    assert tracking._poll_public_tracking_status("secure-public-token", 9, 33)["status"] == "preparing"
    assert tracking._poll_public_tracking_status("secure-public-token", 9, 33)["status"] == "ready"
    assert len(sessions) == 2
    assert closed == sessions


def test_sse_stops_when_token_is_revoked_mid_stream(monkeypatch):
    from app.routers import public_tracking as tracking

    async def run():
        async def snapshot(*_args):
            return _status_snapshot("PRONTO")
        async def disconnected():
            return False
        def revoked(*_args):
            raise TrackingNotFound()
        monkeypatch.setattr(tracking, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
        monkeypatch.setattr(tracking, "_resolve_public_tracking_order", lambda *_args: SimpleNamespace(id=44, tenant_id=9))
        monkeypatch.setattr(tracking, "_build_public_tracking_snapshot_async", snapshot)
        monkeypatch.setattr(tracking, "get_async_redis_client", lambda: None)
        monkeypatch.setattr(tracking, "TRACKING_STATUS_POLL_SECONDS", 0)
        monkeypatch.setattr(tracking, "_poll_public_tracking_status", revoked)
        response = await tracking.sse_public_tracking("secure-public-token", SimpleNamespace(is_disconnected=disconnected))
        events = _tracking_events([chunk async for chunk in response.body_iterator])
        assert [e["status"] for e in events] == ["ready"]
    asyncio.run(run())
