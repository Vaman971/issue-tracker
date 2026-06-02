import json
import logging
from typing import Any

from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


async def cache_get_json(key: str) -> Any | None:
    try:
        value = await get_redis_client().get(key)
    except Exception:
        logger.exception("Cache get failed for key=%s", key)
        return None

    if value is None:
        return None

    return json.loads(value)


async def cache_set_json(
    key: str,
    value: Any,
    ttl_seconds: int = settings.REDIS_DEFAULT_TTL_SECONDS,
) -> None:
    try:
        await get_redis_client().set(
            key,
            json.dumps(value),
            ex=ttl_seconds,
        )
    except Exception:
        logger.exception("Cache set failed for key=%s", key)


async def cache_delete(key: str) -> None:
    try:
        await get_redis_client().delete(key)
    except Exception:
        logger.exception("Cache delete failed for key=%s", key)


async def cache_delete_pattern(pattern: str) -> None:
    client = get_redis_client()

    try:
        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
    except Exception:
        logger.exception("Cache delete pattern failed for pattern=%s", pattern)
