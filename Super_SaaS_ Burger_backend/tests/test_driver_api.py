import asyncio
from types import SimpleNamespace
from unittest.mock import patch


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
        result = driver_login(DriverLoginPayload(email='driver@example.com', password='secret'), request, _Db())

    assert result['token'] == 'driver-token'
    assert result['driver']['role'] == 'driver'
    token_mock.assert_called_once_with(
        '10',
        extra={
            'credential_version': 2,
            'driver_id': 10,
            'delivery_user_id': 10,
            'restaurant_id': 3,
            'tenant_id': 3,
            'role': 'driver',
        },
    )


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
