from types import SimpleNamespace

from app.services.loyalty import calculate_order_points, resolve_reais_por_ponto


def test_resolve_reais_por_ponto_uses_new_field_when_present():
    tenant = SimpleNamespace(reais_por_ponto=10, points_per_real=5)

    assert resolve_reais_por_ponto(tenant) == 10


def test_resolve_reais_por_ponto_falls_back_to_legacy_points_per_real():
    tenant = SimpleNamespace(reais_por_ponto=None, points_per_real=0.5)

    assert resolve_reais_por_ponto(tenant) == 2


def test_calculate_order_points_uses_spent_value_per_point_rule():
    assert calculate_order_points(total_cents=2599, reais_por_ponto=10) == 2
