from types import SimpleNamespace

from app.routers.delivery_api import _build_order_geocoding_address, _expand_statuses


def test_expand_statuses_defaults_ready_and_out_for_delivery_variants():
    statuses = _expand_statuses(None)
    assert "READY" in statuses
    assert "PRONTO" in statuses
    assert "OUT_FOR_DELIVERY" in statuses
    assert "SAIU" in statuses


def test_expand_statuses_resolves_delivered_alias():
    statuses = _expand_statuses("DELIVERED")
    assert statuses == ["DELIVERED", "ENTREGUE"]


def test_build_order_geocoding_address_includes_all_available_parts():
    order = SimpleNamespace(
        street="Rua Augusta",
        number="1200",
        complement="Apto 31",
        neighborhood="Consolação",
        city="São Paulo",
        delivery_address_json={"state": "SP", "zip": "01305-100"},
    )

    query = _build_order_geocoding_address(order)

    assert query == "Rua Augusta 1200 Apto 31 Consolação São Paulo SP 01305-100 Brasil"
