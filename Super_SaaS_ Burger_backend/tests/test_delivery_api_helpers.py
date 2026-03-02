from app.routers.delivery_api import _expand_statuses


def test_expand_statuses_defaults_ready_and_out_for_delivery_variants():
    statuses = _expand_statuses(None)
    assert "READY" in statuses
    assert "PRONTO" in statuses
    assert "OUT_FOR_DELIVERY" in statuses
    assert "SAIU" in statuses


def test_expand_statuses_resolves_delivered_alias():
    statuses = _expand_statuses("DELIVERED")
    assert statuses == ["DELIVERED", "ENTREGUE"]
