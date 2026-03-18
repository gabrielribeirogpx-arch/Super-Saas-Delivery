from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis as AsyncRedis

TRACKING_TTL_SECONDS = 2 * 60 * 60
THROTTLE_WINDOW_SECONDS = 2
DELIVERY_LOCATION_TTL_SECONDS = 2 * 60 * 60
DELIVERY_DISTANCE_TTL_SECONDS = 6 * 60 * 60

_IN_MEMORY_STORE: dict[str, str] = {}


class TrackingStoreError(Exception):
    pass


def tracking_key(order_id: int) -> str:
    return f"tracking:order:{int(order_id)}"


def tracking_throttle_key(order_id: int, driver_id: int) -> str:
    return f"tracking:throttle:order:{int(order_id)}:driver:{int(driver_id)}"


def delivery_location_key(order_id: int) -> str:
    return f"delivery:{int(order_id)}:location"


def delivery_total_distance_key(order_id: int) -> str:
    return f"delivery:{int(order_id)}:total_distance"


async def _store_set(redis: AsyncRedis | None, key: str, value: str, ex: int | None = None) -> None:
    if redis is None:
        _IN_MEMORY_STORE[key] = value
        return
    await redis.set(key, value, ex=ex)


async def _store_get(redis: AsyncRedis | None, key: str) -> str | None:
    if redis is None:
        return _IN_MEMORY_STORE.get(key)
    raw_value = await redis.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, bytes):
        return raw_value.decode("utf-8")
    return str(raw_value)


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


async def save_delivery_location(redis: AsyncRedis | None, order_id: int, lat: float, lng: float) -> dict[str, Any]:
    payload = {
        "lat": float(lat),
        "lng": float(lng),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await _store_set(redis, delivery_location_key(order_id), json.dumps(payload), ex=DELIVERY_LOCATION_TTL_SECONDS)
    except Exception as exc:
        raise TrackingStoreError("Failed to persist delivery location") from exc
    return payload


async def get_delivery_location(redis: AsyncRedis | None, order_id: int) -> dict[str, Any] | None:
    try:
        raw_payload = await _store_get(redis, delivery_location_key(order_id))
    except Exception as exc:
        raise TrackingStoreError("Failed to load delivery location") from exc
    if raw_payload is None:
        return None
    try:
        parsed = json.loads(raw_payload)
    except Exception as exc:
        raise TrackingStoreError("Delivery location payload is invalid") from exc
    if not isinstance(parsed, dict):
        return None
    return {
        "lat": parsed.get("lat"),
        "lng": parsed.get("lng"),
        "updated_at": parsed.get("updated_at"),
    }


async def save_delivery_total_distance(redis: AsyncRedis | None, order_id: int, total_distance_km: float) -> float:
    normalized_distance = max(0.001, float(total_distance_km))
    try:
        await _store_set(redis, delivery_total_distance_key(order_id), str(normalized_distance), ex=DELIVERY_DISTANCE_TTL_SECONDS)
    except Exception as exc:
        raise TrackingStoreError("Failed to persist total delivery distance") from exc
    return normalized_distance


async def get_delivery_total_distance(redis: AsyncRedis | None, order_id: int) -> float | None:
    try:
        raw_distance = await _store_get(redis, delivery_total_distance_key(order_id))
    except Exception as exc:
        raise TrackingStoreError("Failed to load total delivery distance") from exc
    if raw_distance is None:
        return None
    try:
        return float(raw_distance)
    except (TypeError, ValueError) as exc:
        raise TrackingStoreError("Stored total distance is invalid") from exc
