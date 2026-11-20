import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest


def test_navigation_route_returns_road_geometry_without_exposing_google_key():
    from app.services import directions_service

    def respond(request):
        assert request.method == "POST"
        assert request.headers["x-goog-api-key"] == "server-only-key"
        assert json.loads(request.content)["languageCode"] == "pt-BR"
        return httpx.Response(200, json={
            "routes": [{
                "polyline": {"encodedPolyline": "encoded-route"},
                "distanceMeters": 1800,
                "duration": "360s",
                "legs": [{
                    "steps": [{
                        "navigationInstruction": {
                            "instructions": "Vire à direita na Rua A",
                            "maneuver": "TURN_RIGHT",
                        },
                        "distanceMeters": 120,
                    }],
                }],
            }],
        })

    transport = httpx.MockTransport(respond)
    real_client = httpx.AsyncClient
    with (
        patch.object(directions_service, "GOOGLE_ROUTES_API_KEY", "server-only-key"),
        patch.object(directions_service.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=transport, **kwargs)),
    ):
        result = asyncio.run(directions_service.get_navigation_route(-23.5, -46.6, -23.6, -46.7))

    assert result["distance_meters"] == 1800
    assert result["duration_seconds"] == 360
    assert result["next_instruction"] == "Vire à direita na Rua A"
    assert result["next_maneuver"] == "turn-right"
    assert "server-only-key" not in str(result)


def test_navigation_denies_order_assigned_to_another_driver():
    from app.routers.driver_api import get_driver_navigation

    order = SimpleNamespace(id=41, assigned_delivery_user_id=99, status="OUT_FOR_DELIVERY")

    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return order

    db = SimpleNamespace(query=lambda _model: Query())
    driver = SimpleNamespace(id=7, tenant_id=3)
    with patch("app.routers.driver_api.require_feature"):
        with pytest.raises(Exception) as exc:
            asyncio.run(get_driver_navigation(41, -23.5, -46.6, db, driver))
    assert exc.value.status_code == 403


def test_navigation_returns_route_only_for_the_active_assigned_order():
    from app.routers.driver_api import get_driver_navigation

    order = SimpleNamespace(
        id=41,
        assigned_delivery_user_id=7,
        status="OUT_FOR_DELIVERY",
        destination_lat=-23.6,
        destination_lng=-46.7,
    )

    class Query:
        def filter(self, *_args):
            return self

        def first(self):
            return order

    db = SimpleNamespace(query=lambda _model: Query())
    driver = SimpleNamespace(id=7, tenant_id=3)
    route = {"distance_meters": 1800, "duration_seconds": 360, "encoded_polyline": "encoded-route"}
    with (
        patch("app.routers.driver_api.require_feature"),
        patch("app.routers.driver_api.get_navigation_route", return_value=route) as route_lookup,
    ):
        result = asyncio.run(get_driver_navigation(41, -23.5, -46.6, db, driver))

    assert result["order_id"] == 41
    assert result["destination_lat"] == -23.6
    assert result["encoded_polyline"] == "encoded-route"
    route_lookup.assert_awaited_once_with(-23.5, -46.6, -23.6, -46.7)
