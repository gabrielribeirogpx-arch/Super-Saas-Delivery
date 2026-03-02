import logging
import os

import redis
import redis.asyncio as redis_asyncio
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger(__name__)


def _get_redis_url() -> str:
    return os.getenv("REDIS_URL", "").strip()


def get_redis_client() -> Redis | None:
    redis_url = _get_redis_url()
    if not redis_url:
        return None
    return redis.from_url(redis_url)


def get_async_redis_client() -> AsyncRedis | None:
    redis_url = _get_redis_url()
    if not redis_url:
        return None
    return redis_asyncio.from_url(redis_url)


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
