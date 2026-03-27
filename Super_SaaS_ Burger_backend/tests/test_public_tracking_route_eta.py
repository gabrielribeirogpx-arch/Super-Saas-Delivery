from types import SimpleNamespace

from app.routers import public_tracking


def test_get_public_order_location_supports_api_prefix_and_tenant_query_param(monkeypatch):
    order = SimpleNamespace(id=42, status="OUT_FOR_DELIVERY", destination_lat=-23.55, destination_lng=-46.63)

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return order

    class _Db:
        def query(self, _model):
            return _Query()

    monkeypatch.setattr(public_tracking, "_resolve_tracking_record", lambda *_args, **_kwargs: None)

    async def _fake_live_state(*_args, **_kwargs):
        return -23.51, -46.61, "2026-03-19T00:00:00+00:00"

    monkeypatch.setattr(public_tracking, "_resolve_live_driver_state", _fake_live_state)

    response = public_tracking.asyncio.run(
        public_tracking.get_public_order_location(order_id=42, tenant="burger", db=_Db())
    )

    payload = response.body.decode("utf-8")
    assert '"driver_lat":-23.51' in payload
    assert '"driver_lng":-46.61' in payload
    assert '"destination_lat":-23.55' in payload
    assert '"destination_lng":-46.63' in payload
    assert '"status":"OUT_FOR_DELIVERY"' in payload


def test_build_live_progress_payload_uses_tracking_route_metrics():
    tracking = SimpleNamespace(
        current_lat=-23.0,
        current_lng=-46.0,
        route_distance_meters=2500,
        route_duration_seconds=600,
        estimated_duration_seconds=None,
        created_at=None,
    )
    order = SimpleNamespace()

    payload = public_tracking.asyncio.run(public_tracking._build_live_progress_payload(order, tracking))

    assert payload["distance_meters"] == 2500
    assert payload["duration_seconds"] == 600
    assert payload["driver_lat"] == -23.0
    assert payload["driver_lng"] == -46.0
    assert payload["progress"] == 0.0


def test_build_live_progress_payload_prefers_redis_driver_location_and_google_directions(monkeypatch):
    tracking = SimpleNamespace(
        current_lat=-23.0,
        current_lng=-46.0,
        route_distance_meters=None,
        route_duration_seconds=None,
        estimated_duration_seconds=None,
        created_at=None,
    )
    order = SimpleNamespace(id=99, customer_lat=-23.55, customer_lng=-46.63)

    class _Redis:
        async def aclose(self):
            return None

    async def _fake_get_delivery_location(_redis, order_id):
        assert order_id == 99
        return {"lat": -23.51, "lng": -46.61, "updated_at": "2026-03-19T00:00:00+00:00"}

    async def _fake_get_route_data(origin_lat, origin_lng, dest_lat, dest_lng):
        assert (origin_lat, origin_lng) == (-23.51, -46.61)
        assert (dest_lat, dest_lng) == (-23.55, -46.63)
        return 850, 240, None

    monkeypatch.setattr(public_tracking, "get_async_redis_client", lambda: _Redis())
    monkeypatch.setattr(public_tracking, "get_delivery_location", _fake_get_delivery_location)
    monkeypatch.setattr(public_tracking, "get_route_data", _fake_get_route_data)

    payload = public_tracking.asyncio.run(public_tracking._build_live_progress_payload(order, tracking))

    assert payload["driver_lat"] == -23.51
    assert payload["driver_lng"] == -46.61
    assert payload["distance_meters"] == 850
    assert payload["duration_seconds"] == 240
    assert payload["last_location"] == {
        "lat": -23.51,
        "lng": -46.61,
        "updated_at": "2026-03-19T00:00:00+00:00",
    }


def test_build_live_progress_payload_returns_empty_when_tracking_missing():
    payload = public_tracking.asyncio.run(public_tracking._build_live_progress_payload(SimpleNamespace(), None))

    assert payload == {
        "progress": 0.0,
        "distance_meters": None,
        "duration_seconds": None,
        "last_location": None,
        "driver_lat": None,
        "driver_lng": None,
        "destination_lat": None,
        "destination_lng": None,
        "initial_distance_meters": None,
    }


def test_build_public_tracking_event_rejects_empty_driver_payload():
    assert public_tracking._build_public_tracking_event({"payload": {"distance_meters": 100}}) == {"distance_meters": 100}

    payload = public_tracking._build_public_tracking_event({"payload": {"lat": -23.5, "lng": -46.6}})

    assert payload == {
        "driver_lat": -23.5,
        "driver_lng": -46.6,
        "last_location": {"lat": -23.5, "lng": -46.6},
    }
