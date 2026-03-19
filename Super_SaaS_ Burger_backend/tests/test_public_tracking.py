from datetime import datetime, timedelta, timezone
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



def test_public_tracking_sse_rejects_invalid_token(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr("app.routers.public_tracking._resolve_public_tracking_order", lambda *_args, **_kwargs: (_ for _ in ()).throw(TrackingNotFound()))

    with TestClient(main.app) as client:
        response = client.get("/api/public/sse/not-a-valid-token")

    assert response.status_code == 404
    assert response.json() == {"detail": "Rastreamento não encontrado"}



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
    assert payload["order_id"] == 44
    assert payload["total"] == 3590.0
    assert payload["total_cents"] == 3590
    assert payload["store_name"] == "Tempero da Casa"
    assert payload["store_logo_url"] == "https://cdn.example/logo.png"
    assert payload["primary_color"] == "#22c55e"



def test_resolve_public_tracking_sets_request_tenant_from_order():
    order = _order_with_token(expires_delta_days=2, revoked=False)
    request = _build_request({"x-tenant-id": "other-tenant"})

    resolved = _resolve_public_tracking_order(FakeDb(order=order, tracking_tokens=[order.tracking_token]), order.tracking_token, request)

    assert resolved == order
    assert request.state.tenant_id == order.tenant_id
