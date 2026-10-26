from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.delivery_api import get_delivery_last_location


class _FakeQuery:
    def __init__(self, tracking):
        self.tracking = tracking

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.tracking


class _FakeDb:
    def __init__(self, tracking):
        self.tracking = tracking

    def query(self, _model):
        return _FakeQuery(self.tracking)


def test_last_location_returns_waiting_when_no_tracking():
    payload = get_delivery_last_location(
        tenant_id=7,
        order_id=10,
        db=_FakeDb(None),
        request_tenant_id=7,
    )

    assert payload == {"status": "waiting"}


def test_last_location_returns_waiting_when_coordinates_missing():
    tracking = SimpleNamespace(current_lat=None, current_lng=-46.0, created_at=None, id=99)

    payload = get_delivery_last_location(
        tenant_id=7,
        order_id=10,
        db=_FakeDb(tracking),
        request_tenant_id=7,
    )

    assert payload == {"status": "waiting"}


def test_last_location_returns_latest_coordinates():
    tracking = SimpleNamespace(
        current_lat=-23.561684,
        current_lng=-46.625378,
        created_at=SimpleNamespace(isoformat=lambda: "2026-03-04T12:00:00+00:00"),
        id=100,
    )

    payload = get_delivery_last_location(
        tenant_id=9,
        order_id=44,
        db=_FakeDb(tracking),
        request_tenant_id=9,
    )

    assert payload == {
        "lat": -23.561684,
        "lng": -46.625378,
        "timestamp": "2026-03-04T12:00:00+00:00",
    }


def test_last_location_rejects_tenant_mismatch():
    with pytest.raises(HTTPException) as exc:
        get_delivery_last_location(
            tenant_id=8,
            order_id=44,
            db=_FakeDb(None),
            request_tenant_id=9,
        )

    assert exc.value.status_code == 403
