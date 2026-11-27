import json
from datetime import datetime

import httpx
from redis.exceptions import RedisError

from app.integrations.redis_client import get_redis_client
from app.services.ifood_orders import ORDERS_URL

TRACKING_INTERVAL = 30


def _tracking_summary(payload: dict) -> dict:
    result = {}
    for name, limit in (("latitude", 90), ("longitude", 180)):
        value = payload.get(name)
        if type(value) in (int, float) and -limit <= value <= limit:
            result[name] = value
    for name in ("expectedDelivery", "trackDate"):
        value = payload.get(name)
        if isinstance(value, str):
            try:
                if datetime.fromisoformat(value).utcoffset() is not None:
                    result[name] = value
            except ValueError:
                pass
    return result


def fetch_ifood_tracking(token: str, order_id: str) -> dict | None:
    """Share the per-order iFood request limit across staff and backend replicas."""
    cache = get_redis_client()
    if cache is None:
        return None
    key = f"ifood:tracking:{order_id}"
    try:
        with cache:
            cached = cache.get(key)
            if cached is not None:
                return json.loads(cached)
            if not cache.set(f"{key}:request", "1", ex=TRACKING_INTERVAL, nx=True):
                return None
            result = None
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{ORDERS_URL}/{order_id}/tracking", headers={
                    "Authorization": f"Bearer {token}",
                })
                if response.status_code == 200:
                    payload = response.json()
                    if isinstance(payload, dict):
                        result = _tracking_summary(payload) or None
            cache.set(key, json.dumps(result), ex=TRACKING_INTERVAL)
            return result
    except (httpx.RequestError, RedisError, ValueError):
        return None
