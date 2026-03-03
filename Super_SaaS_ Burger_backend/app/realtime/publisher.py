import json
import logging

from app.integrations.redis_client import get_redis_client

logger = logging.getLogger(__name__)


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
    """Publish a delivery event to Redis Pub/Sub for a specific delivery user."""
    channel = f"tenant:{tenant_id}:delivery:{delivery_user_id}"
    return _publish(channel, payload)


def publish_delivery_status_event(tenant_id: int, delivery_user_id: int, status: str) -> int:
    """Publish delivery presence updates to tenant-scoped Redis channel."""
    channel = f"tenant:{tenant_id}:delivery-status"
    payload = {
        "delivery_user_id": int(delivery_user_id),
        "status": str(status),
    }
    return _publish(channel, payload)
