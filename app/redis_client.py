"""
Blink.World — Redis client wrapper
Encapsulates common patterns: cache get/set, atomic locks, sets, rate limiting.
"""

import logging
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def init_redis(redis_url: str) -> aioredis.Redis:
    global _redis
    _redis = aioredis.from_url(
        redis_url,
        decode_responses=True,
        max_connections=50,
    )
    # Verify connectivity
    await _redis.ping()
    logger.info("Redis connected: %s", redis_url.split("@")[-1] if "@" in redis_url else redis_url)
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


# ── Common Patterns ──

async def cache_get(key: str) -> str | None:
    """Get cached value. Returns None on miss or Redis failure."""
    try:
        return await get_redis().get(key)
    except Exception as e:
        logger.warning("Redis cache_get failed for %s: %s", key, e)
        return None


async def cache_set(key: str, value: str, ttl: int = 3600) -> bool:
    """Set cached value with TTL. Returns False on failure."""
    try:
        await get_redis().set(key, value, ex=ttl)
        return True
    except Exception as e:
        logger.warning("Redis cache_set failed for %s: %s", key, e)
        return False


async def set_add(key: str, member: str, ttl: int = 604800) -> bool:
    """Add member to a set with TTL refresh. Returns True if new member."""
    try:
        r = get_redis()
        added = await r.sadd(key, member)
        await r.expire(key, ttl)
        return bool(added)
    except Exception as e:
        logger.warning("Redis set_add failed for %s: %s", key, e)
        return True  # Assume new on failure to avoid blocking


async def set_is_member(key: str, member: str) -> bool:
    """Check if member exists in set."""
    try:
        return bool(await get_redis().sismember(key, member))
    except Exception as e:
        logger.warning("Redis set_is_member failed for %s: %s", key, e)
        return False


async def acquire_lock(key: str, ttl: int = 10) -> bool:
    """Acquire a simple distributed lock using SET NX. Returns True if acquired."""
    try:
        result = await get_redis().set(key, "1", nx=True, ex=ttl)
        return result is not None
    except Exception as e:
        logger.warning("Redis acquire_lock failed for %s: %s", key, e)
        return False


async def release_lock(key: str):
    """Release a distributed lock."""
    try:
        await get_redis().delete(key)
    except Exception as e:
        logger.warning("Redis release_lock failed for %s: %s", key, e)


async def incr_with_ttl(key: str, ttl: int = 86400) -> int:
    """Increment counter with TTL. Returns new count."""
    try:
        r = get_redis()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        results = await pipe.execute()
        return results[0]
    except Exception as e:
        logger.warning("Redis incr_with_ttl failed for %s: %s", key, e)
        return 0


# ── Rate Limiting (Lua script for atomicity) ──

_RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or '0')
if current >= limit then
    return 0
end
redis.call('INCR', key)
if current == 0 then
    redis.call('EXPIRE', key, window)
end
return 1
"""


async def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Check and consume rate limit. Returns True if allowed."""
    try:
        result = await get_redis().eval(_RATE_LIMIT_LUA, 1, key, str(limit), str(window_seconds))
        return bool(result)
    except Exception as e:
        logger.warning("Redis rate_limit failed for %s: %s", key, e)
        return True  # Allow on failure to avoid blocking users
