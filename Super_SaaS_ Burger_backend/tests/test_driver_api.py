from types import SimpleNamespace
from unittest.mock import patch


def test_driver_login_returns_driver_contract():
    from app.routers.driver_api import DriverLoginPayload, driver_login

    driver_user = SimpleNamespace(
        id=10,
        tenant_id=3,
        email='driver@example.com',
        password_hash='hash',
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
