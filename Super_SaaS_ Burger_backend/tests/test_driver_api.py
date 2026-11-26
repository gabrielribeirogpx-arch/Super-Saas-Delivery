import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

from fastapi import Response


def test_driver_login_returns_driver_contract():
    from app.routers.driver_api import DriverLoginPayload, driver_login

    driver_user = SimpleNamespace(
        id=10,
        tenant_id=3,
        email='driver@example.com',
        password_hash='hash',
        credential_version=2,
        name='Driver One',
    )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return driver_user

    class _Db:
        def query(self, _model):
            return _Query()

    request = SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=3)))

    with (
        patch('app.routers.driver_api.verify_password', return_value=True),
        patch('app.routers.driver_api.create_access_token', return_value='driver-token') as token_mock,
    ):
        result = driver_login(DriverLoginPayload(email='driver@example.com', password='secret', remember_device=True), request, Response(), _Db())

    assert result['token'] == 'driver-token'
    assert result['driver']['role'] == 'driver'
    assert result['refresh_token'] == 'driver-token'
    assert token_mock.call_args_list == [call(
        '10',
        extra={
            'credential_version': 2,
            'driver_id': 10,
            'delivery_user_id': 10,
            'restaurant_id': 3,
            'tenant_id': 3,
            'role': 'driver',
        },
    ), call(
        '10',
        extra={'type': 'driver_refresh', 'tenant_id': 3, 'credential_version': 2},
        expires_minutes=30 * 24 * 60,
    )]



def test_build_order_address_prefers_structured_delivery_fields():
    from app.routers.driver_api import _build_order_address

    order = SimpleNamespace(
        street='Rua Rio de Janeiro',
        number='67',
        complement='casa',
        neighborhood='Jardim Brasil',
        city='Gavião Peixoto',
        delivery_address_json={'state': 'SP', 'zip': '14813-132', 'country': 'Brasil'},
        endereco='SP, 14813-132, Brasil',
    )

    assert _build_order_address(order) == 'Rua Rio de Janeiro, 67, casa, Jardim Brasil, Gavião Peixoto, SP, 14813-132, Brasil'


def test_build_order_address_falls_back_to_endereco_when_missing_structured_fields():
    from app.routers.driver_api import _build_order_address

    order = SimpleNamespace(
        street=None,
        number=None,
        complement=None,
        neighborhood=None,
        city=None,
        delivery_address_json=None,
        endereco='SP, 14813-132, Brasil',
    )

    assert _build_order_address(order) == 'SP, 14813-132, Brasil'


def test_driver_location_payload_preserves_public_schema_and_accepts_aliases():
    from app.routers.driver_api import DriverLocationPayload

    legacy = DriverLocationPayload.model_validate({'order_id': 12, 'lat': -23.5, 'lng': -46.6})
    modern = DriverLocationPayload.model_validate({'delivery_id': 12, 'latitude': -23.5, 'longitude': -46.6})

    assert legacy.model_dump() == {'order_id': 12, 'lat': -23.5, 'lng': -46.6}
    assert modern.model_dump() == {'order_id': 12, 'lat': -23.5, 'lng': -46.6}

    schema = DriverLocationPayload.model_json_schema(mode='serialization')
    assert set(schema['properties']) == {'order_id', 'lat', 'lng'}
    assert schema['required'] == ['order_id', 'lat', 'lng']


def test_route_metrics_cache_reuses_nearby_position_and_reroutes_after_movement():
    from app.routers.driver_api import _recalculate_tracking_metrics

    class FakeRedis:
        def __init__(self):
            self.values = {}

        async def get(self, key):
            return self.values.get(key)

        async def set(self, key, value, ex=None):
            assert ex == 30
            self.values[key] = value

    order = SimpleNamespace(
        id=42, tenant_id=7, destination_lat=-23.5, destination_lng=-46.6,
    )
    tracking = SimpleNamespace(
        current_lat=-23.51, current_lng=-46.61, initial_distance_meters=None,
        route_distance_meters=None, route_duration_seconds=None,
    )
    redis = FakeRedis()

    async def fake_route(*_args):
        return 1500, 240, None, 'google_directions'

    with patch('app.routers.driver_api.get_route_metrics_with_fallback', side_effect=fake_route) as route:
        first = asyncio.run(_recalculate_tracking_metrics(order, tracking, redis=redis))
        tracking.current_lat += 0.0001
        second = asyncio.run(_recalculate_tracking_metrics(order, tracking, redis=redis))
        assert first == second
        assert route.call_count == 1

        tracking.current_lat += 0.002
        asyncio.run(_recalculate_tracking_metrics(order, tracking, redis=redis))
        assert route.call_count == 2


def test_storing_known_route_distance_does_not_request_it_again():
    from app.routers.driver_api import _store_total_delivery_distance

    order = SimpleNamespace(id=42, destination_lat=-23.5, destination_lng=-46.6)

    async def fake_save(_redis, _order_id, distance):
        return distance

    with (
        patch('app.routers.driver_api.get_route_metrics_with_fallback') as route,
        patch('app.routers.driver_api.save_delivery_total_distance', side_effect=fake_save),
    ):
        result = asyncio.run(_store_total_delivery_distance(order, -23.51, -46.61, route_distance_meters=1500))

    assert result == 1.5
    route.assert_not_called()


def test_location_update_passes_coordinates_without_logging_them(caplog):
    from app.routers import driver_api

    driver = SimpleNamespace(id=10, tenant_id=3)
    db = Mock()
    data = {"delivery_id": 12, "latitude": -23.512345, "longitude": -46.654321}
    request = SimpleNamespace(headers={"content-type": "application/json"}, json=AsyncMock(return_value=data))
    caplog.set_level(logging.INFO, logger=driver_api.__name__)

    with patch.object(driver_api, "process_driver_location_update", new_callable=AsyncMock) as process:
        process.return_value = {"success": True}
        payload = driver_api.DriverLocationPayload.model_validate(data)
        result = asyncio.run(driver_api.update_driver_location(request, payload=payload, db=db, current_driver=driver))

    assert result == {"success": True}
    process.assert_awaited_once_with(
        authenticated_driver=driver,
        db=db,
        delivery_id=12,
        latitude=-23.512345,
        longitude=-46.654321,
        accuracy=None,
        speed=None,
        heading=None,
        recorded_at=None,
        enforce_rate_limit=False,
    )
    assert "-23.512345" not in caplog.text
    assert "-46.654321" not in caplog.text


def test_location_update_does_not_log_coordinates_from_exceptions(caplog):
    from app.routers import driver_api

    driver = SimpleNamespace(id=10, tenant_id=3)
    db = Mock()
    data = {"order_id": 12, "lat": -23.512345, "lng": -46.654321}
    request = SimpleNamespace(headers={"content-type": "application/json"}, json=AsyncMock(return_value=data))
    caplog.set_level(logging.INFO, logger=driver_api.__name__)

    with patch.object(driver_api, "process_driver_location_update", new_callable=AsyncMock) as process:
        process.side_effect = RuntimeError("GPS database parameters: (-23.512345, -46.654321)")
        payload = driver_api.DriverLocationPayload.model_validate(data)
        result = asyncio.run(driver_api.update_driver_location(request, payload=payload, db=db, current_driver=driver))

    db.rollback.assert_called_once_with()
    assert result.status_code == 200
    assert json.loads(result.body) == {"success": False, "error": "LOCATION_UPDATE_FAILED"}
    records = [record for record in caplog.records if record.name == driver_api.__name__]
    assert [record.getMessage() for record in records] == ["driver location update failed error_type=RuntimeError"]
    assert records[0].exc_info is None
    assert "-23.512345" not in caplog.text
    assert "-46.654321" not in caplog.text


def test_location_is_published_without_waiting_for_route_provider(monkeypatch):
    from unittest.mock import MagicMock
    from app.routers import driver_api

    async def exercise():
        db = MagicMock()
        order = SimpleNamespace(id=12, tenant_id=3, assigned_delivery_user_id=10, status="SAIU")
        tracking = SimpleNamespace(route_distance_meters=600, route_duration_seconds=75, initial_distance_meters=1000)
        db.query.return_value.filter.return_value.first.side_effect = [order, tracking]
        driver = SimpleNamespace(id=10, tenant_id=3, role="driver", name="Driver")
        events = []
        route_open = asyncio.Event()
        route_started = asyncio.Event()

        async def refresh(*args):
            assert events[0]["lat"] == -23.5
            route_started.set()
            await route_open.wait()

        monkeypatch.setattr(driver_api, "feature_allowed", lambda *_: True)
        monkeypatch.setattr(driver_api, "get_async_redis_client", lambda: None)
        monkeypatch.setattr(driver_api, "publish_delivery_driver_location_event", lambda **_: None)
        monkeypatch.setattr(driver_api, "publish_public_tracking_event", lambda **data: events.append(data))
        monkeypatch.setattr(driver_api, "_refresh_route_metrics", refresh)
        monkeypatch.setattr(driver_api, "_route_refresh_tasks", {})
        monkeypatch.setattr(driver_api, "_route_refresh_times", {})

        result = await asyncio.wait_for(driver_api.process_driver_location_update(
            authenticated_driver=driver, db=db, delivery_id=12, latitude=-23.5, longitude=-46.6,
        ), timeout=1)
        assert result["duration_seconds"] == 75
        await asyncio.wait_for(route_started.wait(), timeout=1)
        original_task = driver_api._route_refresh_tasks[(3, 12)]
        driver_api._schedule_route_refresh(db.get_bind(), 3, 12, 10)
        assert driver_api._route_refresh_tasks[(3, 12)] is original_task
        route_open.set()
        await original_task
        await asyncio.sleep(0)
        driver_api._schedule_route_refresh(db.get_bind(), 3, 12, 10)
        assert not driver_api._route_refresh_tasks

    asyncio.run(exercise())
