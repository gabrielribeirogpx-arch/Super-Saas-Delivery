import asyncio
from types import SimpleNamespace

from app.routers import public_tracking


def test_build_live_progress_payload_prefers_route_metrics(monkeypatch):
    order = SimpleNamespace(destination_lat=-23.1, destination_lng=-46.1, customer_lat=None, customer_lng=None, delivery_lat=None, delivery_lng=None)
    driver_location = {"lat": -23.0, "lng": -46.0, "updated_at": "2026-03-18T00:00:00Z"}

    async def fake_route(*_args, **_kwargs):
        return 2500.0, 600.0, None

    monkeypatch.setattr(public_tracking, "get_route_data", fake_route)

    payload = asyncio.run(public_tracking._build_live_progress_payload(order, driver_location, total_distance_km=5.0))

    assert payload["distance_km"] == 2.5
    assert payload["eta_seconds"] == 600
    assert payload["progress"] == 0.5


def test_build_live_progress_payload_falls_back_to_linear_distance(monkeypatch):
    order = SimpleNamespace(destination_lat=-23.1, destination_lng=-46.1, customer_lat=None, customer_lng=None, delivery_lat=None, delivery_lng=None)
    driver_location = {"lat": -23.0, "lng": -46.0, "updated_at": "2026-03-18T00:00:00Z"}

    async def fake_route(*_args, **_kwargs):
        return None, None, None

    monkeypatch.setattr(public_tracking, "get_route_data", fake_route)
    monkeypatch.setattr(public_tracking, "calculate_distance_km", lambda *_args, **_kwargs: 1.25)
    monkeypatch.setattr(public_tracking, "estimate_eta_seconds", lambda distance_km: 150 if distance_km == 1.25 else 0)

    payload = asyncio.run(public_tracking._build_live_progress_payload(order, driver_location, total_distance_km=5.0))

    assert payload["distance_km"] == 1.25
    assert payload["eta_seconds"] == 150
    assert payload["progress"] == 0.75
