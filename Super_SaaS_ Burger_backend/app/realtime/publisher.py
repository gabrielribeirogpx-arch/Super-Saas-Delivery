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


def publish_delivery_event(tenant_id: int, payload: dict) -> int:
    """Publish a delivery event to Redis Pub/Sub."""
    channel = f"tenant:{tenant_id}:delivery"
    return _publish(channel, payload)
