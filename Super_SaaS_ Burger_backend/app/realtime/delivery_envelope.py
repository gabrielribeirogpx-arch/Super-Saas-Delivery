from __future__ import annotations

from datetime import datetime, timezone

DELIVERY_SCHEMA_VERSION = 1


def build_delivery_envelope(
    *,
    event_type: str,
    tenant_id: int,
    payload: dict,
    order_id: int | None = None,
    delivery_user_id: int | None = None,
) -> dict:
    return {
        "type": str(event_type),
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "tenant_id": int(tenant_id),
        "order_id": int(order_id) if order_id is not None else None,
        "delivery_user_id": int(delivery_user_id) if delivery_user_id is not None else None,
        "payload": dict(payload),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def parse_delivery_envelope(raw_payload: str, *, expected_tenant_id: int | None = None) -> dict | None:
    import json

    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    schema_version = payload.get("schema_version")
    tenant_id = payload.get("tenant_id")
    payload_data = payload.get("payload")

    if schema_version != DELIVERY_SCHEMA_VERSION:
        return None

    if not isinstance(tenant_id, int):
        return None

    if expected_tenant_id is not None and tenant_id != int(expected_tenant_id):
        return None

    if not isinstance(payload.get("type"), str):
        return None

    if payload.get("order_id") is not None and not isinstance(payload.get("order_id"), int):
        return None

    if payload.get("delivery_user_id") is not None and not isinstance(payload.get("delivery_user_id"), int):
        return None

    if not isinstance(payload_data, dict):
        return None

    if not isinstance(payload.get("ts"), str):
        return None

    return payload
