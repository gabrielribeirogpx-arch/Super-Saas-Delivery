import json
import logging

from app.integrations.redis_client import get_redis_client
from app.realtime.delivery_envelope import build_delivery_envelope

logger = logging.getLogger(__name__)


def delivery_status_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery:status"


def delivery_location_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery:location"


def delivery_driver_location_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery_driver_location"


def standard_delivery_status_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery-status"


def delivery_assignment_channel(tenant_id: int) -> str:
    return f"tenant:{int(tenant_id)}:delivery:assignment"


def order_tracking_channel(tenant_id: int, order_id: int) -> str:
    return f"tenant:{int(tenant_id)}:order:{int(order_id)}:tracking"


def delivery_order_channel(order_id: int) -> str:
    return f"delivery:{int(order_id)}"


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




def publish_standard_delivery_status_event(tenant_id: int, delivery_user_id: int, status: str) -> int:
    channel = standard_delivery_status_channel(tenant_id)
    envelope = build_delivery_envelope(
        event_type="delivery.status",
        tenant_id=tenant_id,
        order_id=None,
        delivery_user_id=delivery_user_id,
        payload={"status": str(status)},
    )
    return _publish(channel, envelope)

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
    receivers = _publish(channel, envelope)

    if order_id is not None:
        order_payload = {
            "type": "delivery.location",
            "tenant_id": int(tenant_id),
            "order_id": int(order_id),
            "delivery_user_id": int(delivery_user_id),
            "lat": float(lat),
            "lng": float(lng),
        }
        if status is not None:
            order_payload["status"] = str(status)
        receivers += _publish(delivery_order_channel(order_id), order_payload)

    return receivers


def publish_delivery_driver_location_event(
    tenant_id: int,
    driver_id: int,
    order_id: int,
    lat: float,
    lng: float,
) -> int:
    channel = delivery_driver_location_channel(tenant_id)
    payload = {
        "type": "driver_location",
        "tenant_id": int(tenant_id),
        "driver_id": int(driver_id),
        "order_id": int(order_id),
        "lat": float(lat),
        "lng": float(lng),
    }
    return _publish(channel, payload)


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


def publish_public_tracking_event(
    tenant_id: int,
    order_id: int,
    *,
    status: str,
    delivery_user_name: str | None,
    lat: float,
    lng: float,
) -> int:
    channel = order_tracking_channel(tenant_id, order_id)
    envelope = build_delivery_envelope(
        event_type="delivery.public_tracking",
        tenant_id=tenant_id,
        order_id=None,
        delivery_user_id=None,
        payload={
            "status": str(status),
            "delivery_user": {"name": delivery_user_name} if delivery_user_name else None,
            "last_location": {"lat": float(lat), "lng": float(lng)},
        },
    )
    return _publish(channel, envelope)



def publish_order_tracking_eta_event(
    tenant_id: int,
    order_id: int,
    *,
    lat: float,
    lng: float,
    remaining_seconds: int,
    status: str,
    schema_version: int = 1,
) -> int:
    channel = order_tracking_channel(tenant_id, order_id)
    payload = {
        "order_id": int(order_id),
        "lat": float(lat),
        "lng": float(lng),
        "remaining_seconds": max(0, int(remaining_seconds)),
        "status": str(status),
        "schema_version": int(schema_version),
    }
    return _publish(channel, payload)


def publish_order_tracking_location_event(
    tenant_id: int,
    order_id: int,
    *,
    lat: float,
    lng: float,
    remaining_seconds: int,
    distance_meters: int,
) -> int:
    channel = order_tracking_channel(tenant_id, order_id)
    payload = {
        "order_id": int(order_id),
        "lat": float(lat),
        "lng": float(lng),
        "remaining_seconds": max(0, int(remaining_seconds)),
        "distance_meters": max(0, int(distance_meters)),
    }
    return _publish(channel, payload)
