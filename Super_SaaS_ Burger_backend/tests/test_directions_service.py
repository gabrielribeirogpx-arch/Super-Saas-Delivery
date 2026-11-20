import asyncio
from unittest.mock import patch

import httpx

from app.services.directions_service import get_route_metrics_with_fallback, normalize_coord


def test_normalize_coord_swaps_lat_lng_when_needed():
    assert normalize_coord(-123.56321, -46.65425) == (-46.65425, -123.56321)


def test_route_metrics_with_fallback_rejects_unrealistic_distance():
    distance_meters, duration_seconds, geometry, provider = asyncio.run(
        get_route_metrics_with_fallback(
            -23.56321,
            -46.65425,
            -22.9068,
            -43.1729,
        )
    )

    assert distance_meters is None
    assert duration_seconds is None
    assert geometry is None
    assert provider is None


def test_route_metrics_use_mapbox_road_distance():
    from app.services import directions_service

    def respond(request):
        assert request.url.params["geometries"] == "polyline"
        assert request.url.params["overview"] == "full"
        return httpx.Response(200, json={
            "code": "Ok",
            "routes": [{
                "distance": 2400.6,
                "duration": 362.9,
                "geometry": "encoded-road",
                "legs": [{"steps": []}],
            }],
        })

    transport = httpx.MockTransport(respond)
    real_client = httpx.AsyncClient
    with (
        patch.object(directions_service, "MAPBOX_ACCESS_TOKEN", "test-token"),
        patch.object(directions_service.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=transport, **kwargs)),
    ):
        result = asyncio.run(get_route_metrics_with_fallback(-23.5, -46.6, -23.6, -46.7))

    assert result == (2400, 362, "encoded-road", "mapbox_directions")
