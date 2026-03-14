import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.public_menu import (
    PublicOrderPayload,
    _validate_delivery_zip,
)


def test_public_order_payload_requires_zip_for_delivery_orders():
    with pytest.raises(ValidationError) as exc:
        PublicOrderPayload(order_type="delivery", delivery_type="ENTREGA")

    assert "ZIP code is required for delivery orders" in str(exc.value)


def test_validate_delivery_zip_accepts_cep_alias():
    payload = PublicOrderPayload(
        order_type="delivery",
        delivery_type="ENTREGA",
        delivery_address={"cep": "01001-000"},
    )

    resolved = _validate_delivery_zip(payload, {"cep": "01001-000"})

    assert resolved == "01001-000"


def test_validate_delivery_zip_raises_for_missing_zip_in_delivery_context():
    payload = PublicOrderPayload(
        order_type="delivery",
        delivery_type="ENTREGA",
        delivery_address={"zip": "01001-000"},
    )

    with pytest.raises(HTTPException) as exc:
        _validate_delivery_zip(payload, {})

    assert exc.value.status_code == 400
    assert exc.value.detail == "ZIP code is required for delivery orders"


def test_validate_delivery_zip_ignores_non_delivery_orders():
    payload = PublicOrderPayload(order_type="pickup", delivery_type="RETIRADA")

    resolved = _validate_delivery_zip(payload, {})

    assert resolved == ""
