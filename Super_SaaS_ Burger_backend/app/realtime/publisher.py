import json
import logging

from app.integrations.redis_client import get_redis_client

logger = logging.getLogger(__name__)


def publish_event(tenant_id: int, payload: dict) -> int:
    """Publish a tenant event to Redis Pub/Sub."""
    client = get_redis_client()
    if client is None:
        logger.debug("Redis unavailable: skipped publish tenant_id=%s", tenant_id)
        return 0

    channel = f"tenant:{tenant_id}:events"
    message = json.dumps(payload)

    try:
        return int(client.publish(channel, message))
    except Exception:
        logger.exception("Failed to publish tenant event tenant_id=%s", tenant_id)
        return 0
