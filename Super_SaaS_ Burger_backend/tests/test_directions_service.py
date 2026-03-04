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


def test_get_route_data_returns_none_without_token(monkeypatch):
    monkeypatch.setattr(directions_service, "MAPBOX_TOKEN", None)

    distance, duration = asyncio.run(directions_service.get_route_data(1, 2, 3, 4))

    assert distance is None
    assert duration is None


def test_get_route_data_returns_distance_and_duration(monkeypatch):
    monkeypatch.setattr(directions_service, "MAPBOX_TOKEN", "token")
    response = _Response(200, {"routes": [{"distance": 1520.7, "duration": 312.9}]})
    monkeypatch.setattr(
        directions_service.httpx,
        "AsyncClient",
        lambda timeout: _AsyncClient(response),
    )

    distance, duration = asyncio.run(directions_service.get_route_data(-1, -1, -2, -2))

    assert distance == 1520.7
    assert duration == 312.9
