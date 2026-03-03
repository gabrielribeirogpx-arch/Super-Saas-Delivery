from app.routers.delivery_ws import _extract_connection_claims


def test_extract_connection_claims_requires_delivery_role(monkeypatch):
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "OWNER", "tenant_id": 1, "delivery_user_id": 2},
    )

    try:
        _extract_connection_claims("token")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "DELIVERY" in str(exc)


def test_extract_connection_claims_reads_tenant_and_delivery_user(monkeypatch):
    monkeypatch.setattr(
        "app.routers.delivery_ws.decode_access_token",
        lambda _token: {"role": "DELIVERY", "tenant_id": "7", "delivery_user_id": "12"},
    )

    tenant_id, delivery_user_id = _extract_connection_claims("token")

    assert tenant_id == 7
    assert delivery_user_id == 12
