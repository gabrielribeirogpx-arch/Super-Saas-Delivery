from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis as AsyncRedis

TRACKING_TTL_SECONDS = 2 * 60 * 60
THROTTLE_WINDOW_SECONDS = 2


class TrackingStoreError(Exception):
    pass


def tracking_key(order_id: int) -> str:
    return f"tracking:order:{int(order_id)}"


def tracking_throttle_key(order_id: int, driver_id: int) -> str:
    return f"tracking:throttle:order:{int(order_id)}:driver:{int(driver_id)}"


async def can_accept_location_update(redis: AsyncRedis, order_id: int, driver_id: int) -> bool:
    key = tracking_throttle_key(order_id=order_id, driver_id=driver_id)
    try:
        accepted = await redis.set(key, "1", ex=THROTTLE_WINDOW_SECONDS, nx=True)
    except Exception as exc:
        raise TrackingStoreError("Failed to evaluate tracking throttle") from exc
    return bool(accepted)


async def save_driver_location(redis: AsyncRedis, order_id: int, lat: float, lng: float) -> dict[str, Any]:
    payload = {
        "lat": float(lat),
        "lng": float(lng),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await redis.set(tracking_key(order_id), json.dumps(payload), ex=TRACKING_TTL_SECONDS)
    except Exception as exc:
        raise TrackingStoreError("Failed to persist driver location") from exc

    return payload


async def get_driver_location(redis: AsyncRedis, order_id: int) -> dict[str, Any] | None:
    try:
        raw_payload = await redis.get(tracking_key(order_id))
    except Exception as exc:
        raise TrackingStoreError("Failed to load driver location") from exc

    if raw_payload is None:
        return None

    try:
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8")
        parsed = json.loads(raw_payload)
    except Exception as exc:
        raise TrackingStoreError("Tracking payload is invalid") from exc

    if not isinstance(parsed, dict):
        return None

    return {
        "lat": parsed.get("lat"),
        "lng": parsed.get("lng"),
        "updated_at": parsed.get("updated_at"),
    }
