import json
import logging

from app.integrations.redis_client import get_redis_client
from app.realtime.delivery_envelope import build_delivery_envelope

logger = logging.getLogger(__name__)


def delivery_status_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery:status"


def delivery_location_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery:location"


def delivery_assignment_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery:assignment"


def _publish(channel: str, payload: dict) -> int:
    client = get_redis_client()
    if client is None:
        logger.debug("Redis unavailable: skipped publish channel=%s", channel)
        return 0

    message = json.dumps(payload)

    try:
        return int(client.publish(channel, message))
    except Exception:
        logger.exception("Failed to publish event channel=%s", channel)
        return 0


def publish_event(tenant_id: int, payload: dict) -> int:
    """Publish a tenant event to Redis Pub/Sub."""
    channel = f"tenant:{tenant_id}:events"
    return _publish(channel, payload)


def publish_delivery_event(tenant_id: int, delivery_user_id: int, payload: dict) -> int:
    """Backward-compatible alias for assignment events."""
    return publish_delivery_assignment_event(
        tenant_id=tenant_id,
        order_id=payload.get("order_id"),
        delivery_user_id=delivery_user_id,
        payload=payload,
    )


def publish_delivery_status_event(tenant_id: int, delivery_user_id: int, status: str) -> int:
    """Publish delivery presence updates to tenant-scoped Redis channel."""
    channel = delivery_status_channel(tenant_id)
    envelope = build_delivery_envelope(
        event_type="delivery.status",
        tenant_id=tenant_id,
        order_id=None,
        delivery_user_id=delivery_user_id,
        payload={"status": str(status)},
    )
    return _publish(channel, envelope)


def publish_delivery_location_event(
    tenant_id: int,
    delivery_user_id: int,
    lat: float,
    lng: float,
    *,
    status: str | None = None,
    order_id: int | None = None,
) -> int:
    """Publish delivery location updates to tenant-scoped Redis channel."""
    channel = delivery_location_channel(tenant_id)
    payload = {"lat": float(lat), "lng": float(lng)}
    if status is not None:
        payload["status"] = str(status)

    envelope = build_delivery_envelope(
        event_type="delivery.location",
        tenant_id=tenant_id,
        order_id=order_id,
        delivery_user_id=delivery_user_id,
        payload=payload,
    )
    return _publish(channel, envelope)


def publish_delivery_assignment_event(
    tenant_id: int,
    order_id: int | None,
    delivery_user_id: int | None,
    payload: dict,
) -> int:
    channel = delivery_assignment_channel(tenant_id)
    envelope = build_delivery_envelope(
        event_type="delivery.assignment",
        tenant_id=tenant_id,
        order_id=order_id,
        delivery_user_id=delivery_user_id,
        payload=payload,
    )
    return _publish(channel, envelope)
