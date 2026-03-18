import asyncio

from app.services import directions_service


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _AsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *_args, **_kwargs):
        return self._response


def test_get_route_data_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(directions_service, "GOOGLE_MAPS_API_KEY", None)

    distance, duration, geometry = asyncio.run(directions_service.get_route_data(1, 2, 3, 4))

    assert distance is None
    assert duration is None
    assert geometry is None


def test_get_route_data_returns_distance_and_duration(monkeypatch):
    monkeypatch.setattr(directions_service, "GOOGLE_MAPS_API_KEY", "token")
    response = _Response(200, {
        "status": "OK",
        "routes": [{
            "legs": [{
                "distance": {"value": 1521},
                "duration": {"value": 313},
            }]
        }],
    })
    monkeypatch.setattr(
        directions_service.httpx,
        "AsyncClient",
        lambda timeout: _AsyncClient(response),
    )

    distance, duration, geometry = asyncio.run(directions_service.get_route_data(-1, -1, -2, -2))

    assert distance == 1521.0
    assert duration == 313.0
    assert geometry is None
