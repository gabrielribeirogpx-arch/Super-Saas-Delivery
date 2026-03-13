import pytest
from fastapi import HTTPException

from app.routers.public_menu import (
    PublicOrderPayload,
    _validate_delivery_zip,
)


def test_validate_delivery_zip_requires_zip_for_delivery_orders():
    payload = PublicOrderPayload(order_type="delivery", delivery_type="ENTREGA")

    with pytest.raises(HTTPException) as exc:
        _validate_delivery_zip(payload, {})

    assert exc.value.status_code == 400
    assert exc.value.detail == "ZIP code is required for delivery orders"


def test_validate_delivery_zip_accepts_cep_alias():
    payload = PublicOrderPayload(order_type="delivery", delivery_type="ENTREGA")

    resolved = _validate_delivery_zip(payload, {"cep": "01001-000"})

    assert resolved == "01001-000"


def test_validate_delivery_zip_ignores_non_delivery_orders():
    payload = PublicOrderPayload(order_type="pickup", delivery_type="RETIRADA")

    resolved = _validate_delivery_zip(payload, {})

    assert resolved == ""
