"""Redis cache helper for leaderboards."""
import json
from typing import Any

from app.core.config import settings


def get_redis():
    """Get Redis client if available, else None."""
    try:
        import redis.asyncio as redis
        
        if not settings.redis_url:
            return None
        return redis.from_url(settings.redis_url, decode_responses=True)
    except ImportError:
        return None
    except Exception:
        return None


async def get_cached(key: str) -> Any | None:
    """Get cached JSON value or None."""
    r = get_redis()
    if not r:
        return None
    try:
        val = await r.get(key)
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None


async def set_cached(key: str, value: Any, ttl: int = 60) -> None:
    """Set cached JSON value with TTL."""
    r = get_redis()
    if not r:
        return
    try:
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass
