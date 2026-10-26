import asyncio

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
