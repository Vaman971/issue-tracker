import hashlib
import logging

from fastapi import HTTPException, status

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


def _safe_key_part(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def build_rate_limit_key(*parts: str) -> str:
    safe_parts = [_safe_key_part(part) for part in parts if part]
    return "rate_limit:" + ":".join(safe_parts)


async def enforce_rate_limit(
    key: str,
    max_attempts: int,
    window_seconds: int,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    try:
        client = get_redis_client()
        attempts = await client.incr(key)

        if attempts == 1:
            await client.expire(key, window_seconds)

        if attempts > max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
            )
    except HTTPException:
        raise
    except Exception:
        # If Redis is temporarily down, auth should keep working rather than fail closed.
        logger.exception("Rate limit check failed for key=%s", key)


async def reset_rate_limit(key: str) -> None:
    try:
        await get_redis_client().delete(key)
    except Exception:
        logger.exception("Rate limit reset failed for key=%s", key)
