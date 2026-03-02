import logging
import os

import redis
from redis import Redis

logger = logging.getLogger(__name__)


def get_redis_client() -> Redis | None:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    return redis.from_url(redis_url)


def validate_redis_connection() -> bool:
    client = get_redis_client()
    if client is None:
        logger.info("REDIS_URL not configured; skipping Redis connection validation")
        return False

    try:
        client.ping()
        logger.info("Redis connected successfully")
        return True
    except Exception as exc:
        logger.error("Failed to connect to Redis: %s", exc)
        return False
