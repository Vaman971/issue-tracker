import logging
from typing import Awaitable, cast

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: Redis | None = None

def get_redis_client() -> Redis:
    global redis_client

    if redis_client is None:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_HEALTHCHECK_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_HEALTHCHECK_TIMEOUT_SECONDS
        )
    
    return redis_client

async def ping_redis() -> bool:
    try:
        is_connected = await cast(Awaitable[bool], get_redis_client().ping())
        return is_connected
    except Exception:
        logger.exception("Redis ping failed")
        return False

async def close_redis_client() -> None:
    global redis_client

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None