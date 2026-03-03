from __future__ import annotations

import asyncio
import json
import logging
import re

from app.integrations.redis_client import get_async_redis_client
from app.realtime.delivery_connections import delivery_connections

logger = logging.getLogger(__name__)

DELIVERY_CHANNEL_PATTERN = "tenant:*:delivery:*"
_CHANNEL_RE = re.compile(r"^tenant:(?P<tenant_id>\d+):delivery:(?P<delivery_user_id>\d+)$")


async def run_delivery_subscriber(stop_event: asyncio.Event) -> None:
    client = get_async_redis_client()
    if client is None:
        logger.info("REDIS_URL not configured; delivery subscriber disabled")
        return

    pubsub = client.pubsub()

    try:
        await pubsub.psubscribe(DELIVERY_CHANNEL_PATTERN)
        logger.info("Delivery subscriber started pattern=%s", DELIVERY_CHANNEL_PATTERN)

        while not stop_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue

            raw_channel = message.get("channel")
            raw_payload = message.get("data")

            channel = raw_channel.decode() if isinstance(raw_channel, bytes) else str(raw_channel)
            payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)

            channel_match = _CHANNEL_RE.match(channel)
            if not channel_match:
                continue

            tenant_id = int(channel_match.group("tenant_id"))
            delivery_user_id = int(channel_match.group("delivery_user_id"))
            websocket = await delivery_connections.get(tenant_id, delivery_user_id)
            if websocket is None:
                continue

            try:
                payload_data = json.loads(payload_text)
            except (TypeError, json.JSONDecodeError):
                payload_data = {"raw": payload_text}

            try:
                await websocket.send_json(payload_data)
            except Exception:
                logger.debug(
                    "Failed to deliver websocket message tenant_id=%s delivery_user_id=%s",
                    tenant_id,
                    delivery_user_id,
                )
                await delivery_connections.remove(tenant_id, delivery_user_id, websocket)
    except asyncio.CancelledError:
        logger.info("Delivery subscriber cancellation requested")
        raise
    except Exception:
        logger.exception("Delivery subscriber crashed")
    finally:
        await pubsub.aclose()
        await client.aclose()
        logger.info("Delivery subscriber stopped")
