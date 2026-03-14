from app.models.order import Order
from app.services.order_events import build_order_payload


def test_build_order_payload_uses_daily_order_number_and_total_fallbacks():
    order = Order(
        id=82,
        daily_order_number=2,
        tenant_id=1,
        status="pending",
        cliente_nome="Cliente",
        cliente_telefone="5511999999999",
        total_cents=None,
        valor_total=3190,
        tipo_entrega="ENTREGA",
    )

    payload = build_order_payload(order)

    assert payload["order_id"] == 82
    assert payload["order_number"] == 2
    assert payload["daily_order_number"] == 2
    assert payload["total_cents"] == 3190


def test_build_order_payload_defaults_total_to_zero_when_missing():
    order = Order(
        id=10,
        daily_order_number=None,
        tenant_id=1,
        status="pending",
        cliente_nome="Cliente",
        cliente_telefone="5511888888888",
        total_cents=None,
        valor_total=None,
        tipo_entrega="ENTREGA",
    )

    payload = build_order_payload(order)

    assert payload["order_number"] == 10
    assert payload["total_cents"] == 0
