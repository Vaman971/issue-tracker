import logging
from typing import Awaitable, cast

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

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
            # not the healthcheck timeout: that one can afford to wait, this
            # one is paid on every cache lookup in every turn
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            # Rides out a blip, not an outage. One retry with a tenth-second
            # backoff bounds a failed lookup to about a second; a longer chain
            # costs far more on a dead Redis than the cache saves when it is up.
            retry=Retry(
                ExponentialBackoff(cap=settings.REDIS_RETRY_BACKOFF_CAP_SECONDS),
                retries=settings.REDIS_RETRY_ATTEMPTS,
            ),
            # without this the retry policy applies to connection setup only
            retry_on_timeout=True,
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