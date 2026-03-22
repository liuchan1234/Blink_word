"""
Blink.World — Group Service
Manages group registration, rate limiting, swipe counting, and daily summary.
"""

import json
import logging
from datetime import datetime, timezone

from app.database import get_pool
from app.redis_client import get_redis, acquire_lock, release_lock, incr_with_ttl
from app.algorithm import compute_group_rate_limit

logger = logging.getLogger(__name__)

# Redis keys
GROUP_STATE_KEY = "group_state:{chat_id}"       # Today's swipe count (TTL 24h)
GROUP_RATE_KEY = "rate_limit:{chat_id}"          # Rate limit lock (dynamic TTL)
GROUP_LAST_POST_KEY = "group_last:{chat_id}"     # Last post_id shown (TTL 24h)
GROUP_SEEN_KEY = "group_seen:{chat_id}"          # Set of recently shown post_ids (TTL 24h)

STATE_TTL = 86400       # 24h
SEEN_TTL = 86400        # 24h


async def register_group(chat_id: int, title: str = "", added_by: int | None = None):
    """Register or update a group in the database."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO groups (chat_id, title, added_by, last_active)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (chat_id)
            DO UPDATE SET title = $2, last_active = NOW()
            """,
            chat_id, title, added_by,
        )


async def get_today_swipe_count(chat_id: int) -> int:
    """Get today's swipe count for a group."""
    try:
        r = get_redis()
        val = await r.get(GROUP_STATE_KEY.format(chat_id=chat_id))
        return int(val) if val else 0
    except Exception:
        return 0


async def increment_swipe_count(chat_id: int) -> int:
    """Increment and return today's swipe count."""
    return await incr_with_ttl(GROUP_STATE_KEY.format(chat_id=chat_id), ttl=STATE_TTL)


async def check_rate_limit(chat_id: int) -> int:
    """
    Check if group is rate limited.
    Returns 0 if allowed, or seconds to wait if limited.
    """
    count = await get_today_swipe_count(chat_id)
    cooldown = compute_group_rate_limit(count)

    if cooldown <= 0:
        return 0

    # Try to acquire lock (the lock IS the rate limit)
    key = GROUP_RATE_KEY.format(chat_id=chat_id)
    acquired = await acquire_lock(key, ttl=cooldown)
    if acquired:
        return 0  # Lock acquired = allowed to proceed
    else:
        # Already locked = rate limited
        try:
            r = get_redis()
            ttl = await r.ttl(key)
            return max(ttl, 1)
        except Exception:
            return cooldown


async def try_acquire_flip_lock(chat_id: int) -> bool:
    """
    Acquire atomic lock for group card flip.
    Prevents two simultaneous button presses from triggering two flips.
    Short TTL (3s) — just enough to prevent concurrent duplicates.
    """
    key = f"flip_lock:{chat_id}"
    return await acquire_lock(key, ttl=3)


async def set_last_post(chat_id: int, post_id: str):
    """Track the current post shown in a group."""
    try:
        r = get_redis()
        await r.set(GROUP_LAST_POST_KEY.format(chat_id=chat_id), post_id, ex=STATE_TTL)
    except Exception:
        pass


async def get_last_post(chat_id: int) -> str | None:
    """Get the last post_id shown in a group."""
    try:
        r = get_redis()
        return await r.get(GROUP_LAST_POST_KEY.format(chat_id=chat_id))
    except Exception:
        return None


async def add_seen_post(chat_id: int, post_id: str):
    """Add post to group's recently seen set (for dedup)."""
    try:
        r = get_redis()
        key = GROUP_SEEN_KEY.format(chat_id=chat_id)
        await r.sadd(key, post_id)
        await r.expire(key, SEEN_TTL)
    except Exception:
        pass


async def get_seen_posts(chat_id: int) -> set[str]:
    """Get set of recently shown post_ids in a group."""
    try:
        r = get_redis()
        key = GROUP_SEEN_KEY.format(chat_id=chat_id)
        members = await r.smembers(key)
        return set(members) if members else set()
    except Exception:
        return set()


async def get_group_daily_summary(chat_id: int) -> dict:
    """Get today's group statistics for the daily summary."""
    swipe_count = await get_today_swipe_count(chat_id)

    # Count today's group-only posts
    pool = get_pool()
    async with pool.acquire() as conn:
        poster_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM posts
            WHERE group_only = $1
            AND created_at >= CURRENT_DATE
            AND created_at < CURRENT_DATE + INTERVAL '1 day'
            """,
            chat_id,
        )

        # Most popular card shown today (by total reactions)
        top_post = await conn.fetchrow(
            """
            SELECT p.id, p.content, p.like_count,
                   (SELECT COALESCE(SUM((value)::int), 0)
                    FROM jsonb_each_text(p.reactions)) as total_reactions
            FROM post_messages pm
            JOIN posts p ON p.id = pm.post_id
            WHERE pm.chat_id = $1
            AND pm.created_at >= CURRENT_DATE
            ORDER BY total_reactions DESC
            LIMIT 1
            """,
            chat_id,
        )

    return {
        "swipe_count": swipe_count,
        "poster_count": poster_count or 0,
        "top_post": dict(top_post) if top_post else None,
    }
