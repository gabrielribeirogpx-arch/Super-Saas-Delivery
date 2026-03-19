from types import SimpleNamespace

from app.routers import public_tracking


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
