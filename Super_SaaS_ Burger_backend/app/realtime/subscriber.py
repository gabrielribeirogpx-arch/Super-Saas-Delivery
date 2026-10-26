import asyncio
import json
import logging

from app.integrations.redis_client import get_async_redis_client

logger = logging.getLogger(__name__)

TENANT_EVENTS_PATTERN = "tenant:*:events"


async def run_tenant_events_subscriber(stop_event: asyncio.Event) -> None:
    """Background Redis subscriber for tenant event channels."""
    client = get_async_redis_client()
    if client is None:
        logger.info("REDIS_URL not configured; tenant subscriber disabled")
        return

    pubsub = client.pubsub()

    try:
        await pubsub.psubscribe(TENANT_EVENTS_PATTERN)
        logger.info("Tenant events subscriber started pattern=%s", TENANT_EVENTS_PATTERN)

        while not stop_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue

            raw_channel = message.get("channel")
            raw_payload = message.get("data")

            channel = raw_channel.decode() if isinstance(raw_channel, bytes) else str(raw_channel)
            payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)

            try:
                payload_data = json.loads(payload_text)
            except (TypeError, json.JSONDecodeError):
                payload_data = payload_text

            logger.info("Tenant event received channel=%s payload=%s", channel, payload_data)
    except asyncio.CancelledError:
        logger.info("Tenant events subscriber cancellation requested")
        raise
    except Exception:
        logger.exception("Tenant events subscriber crashed")
    finally:
        await pubsub.aclose()
        await client.aclose()
        logger.info("Tenant events subscriber stopped")
