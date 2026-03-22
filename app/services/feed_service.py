"""
Blink.World — Feed Service
Core browsing engine: picks the next card for a user.
Handles viewed-set tracking (Redis), pool selection (50/50), weighted random.
"""

import logging
from datetime import datetime, timezone

from app.redis_client import set_add, get_redis
from app.algorithm import select_post_pool_strategy, weighted_random_select
from app.services.post_service import get_feed_posts, increment_view

logger = logging.getLogger(__name__)

# Redis key patterns
VIEWED_KEY = "viewed:{user_id}"          # Set of post_ids user has seen (TTL 7d)
CURRENT_POST_KEY = "cur_post:{user_id}"  # Current post being viewed (TTL 1h)
SWIPE_COUNT_KEY = "swipes:{user_id}"     # Today's swipe count for points (TTL 24h)

VIEWED_TTL = 7 * 86400   # 7 days
CURRENT_TTL = 3600        # 1 hour
SWIPE_COUNT_TTL = 86400   # 24 hours


async def get_next_card(
    user_id: int,
    channel_ids: list[int],
    viewer_country: str,
    viewer_lang: str,
) -> dict | None:
    """
    Get the next card for a user's private feed.

    Strategy:
    1. 50% chance → draw from local pool (same country/language)
    2. 50% chance → draw from global pool
    3. Weight by quality × emotion × freshness × affinity
    4. Filter out already-viewed posts
    5. Increment view count + mark as viewed

    Returns post dict or None if no content available.
    """
    if not channel_ids:
        return None

    # Get viewed post IDs from Redis
    viewed_ids = await _get_viewed_set(user_id)

    # 50/50 strategy
    pool_type = select_post_pool_strategy()

    # Fetch candidates
    candidates = await get_feed_posts(
        channel_ids=channel_ids,
        exclude_post_ids=viewed_ids,
        viewer_country=viewer_country,
        viewer_lang=viewer_lang,
        pool_type=pool_type,
        limit=30,
    )

    # If local pool is empty, try global
    if not candidates and pool_type == "local":
        candidates = await get_feed_posts(
            channel_ids=channel_ids,
            exclude_post_ids=viewed_ids,
            viewer_country=viewer_country,
            viewer_lang=viewer_lang,
            pool_type="global",
            limit=30,
        )

    if not candidates:
        return None

    # Weighted random selection
    now = datetime.now(timezone.utc)
    selected = weighted_random_select(candidates, viewer_country, viewer_lang, now)

    if selected is None:
        return None

    post_id = selected["id"]

    # Mark as viewed
    await _mark_viewed(user_id, post_id)

    # Set as current post (for reply keyboard actions)
    await _set_current_post(user_id, post_id)

    # Increment view count
    await increment_view(post_id)

    # Increment user swipe count (for points)
    await _increment_swipe_count(user_id)

    return selected


async def get_current_post_id(user_id: int) -> str | None:
    """Get the post_id the user is currently viewing."""
    try:
        r = get_redis()
        return await r.get(CURRENT_POST_KEY.format(user_id=user_id))
    except Exception:
        return None


async def set_current_post(user_id: int, post_id: str):
    """Explicitly set current post (used when sending a card)."""
    await _set_current_post(user_id, post_id)


async def get_swipe_count(user_id: int) -> int:
    """Get today's swipe count for points calculation."""
    try:
        r = get_redis()
        val = await r.get(SWIPE_COUNT_KEY.format(user_id=user_id))
        return int(val) if val else 0
    except Exception:
        return 0


# ── Internal helpers ──

async def _get_viewed_set(user_id: int) -> set[str]:
    """Get set of post IDs user has already viewed."""
    try:
        r = get_redis()
        key = VIEWED_KEY.format(user_id=user_id)
        members = await r.smembers(key)
        return set(members) if members else set()
    except Exception as e:
        logger.warning("Failed to get viewed set for user %d: %s", user_id, e)
        return set()


async def _mark_viewed(user_id: int, post_id: str):
    """Mark a post as viewed by user."""
    await set_add(VIEWED_KEY.format(user_id=user_id), post_id, ttl=VIEWED_TTL)


async def _set_current_post(user_id: int, post_id: str):
    """Set the current post being viewed."""
    try:
        r = get_redis()
        await r.set(CURRENT_POST_KEY.format(user_id=user_id), post_id, ex=CURRENT_TTL)
    except Exception as e:
        logger.warning("Failed to set current post for user %d: %s", user_id, e)


async def _increment_swipe_count(user_id: int) -> int:
    """Increment daily swipe counter. Returns new count."""
    try:
        r = get_redis()
        key = SWIPE_COUNT_KEY.format(user_id=user_id)
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, SWIPE_COUNT_TTL)
        results = await pipe.execute()
        return results[0]
    except Exception:
        return 0
