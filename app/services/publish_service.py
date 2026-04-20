"""
Blink.World — Publish Service
Manages the publishing workflow state and draft storage via Redis.

Flow: choose channel → (daily topic hint) → enter content → preview → confirm
From group: extra step → [🌍 全世界] [🔒 只发到群里]
"""

import json
import logging

from app.redis_client import get_redis
from app.services.post_service import create_post
from app.services.user_service import add_points, increment_stat
from app.models import PointsConfig

logger = logging.getLogger(__name__)

# Redis keys for publish drafts (TTL 30 min — drafts expire if user doesn't finish)
DRAFT_KEY = "draft:{user_id}"
DRAFT_TTL = 1800  # 30 minutes

# Daily post limit
DAILY_POST_KEY = "daily_pub:{user_id}:{date}"
DAILY_POST_LIMIT = 10


async def save_draft(user_id: int, draft: dict):
    """Save a publishing draft to Redis."""
    try:
        r = get_redis()
        await r.set(DRAFT_KEY.format(user_id=user_id), json.dumps(draft), ex=DRAFT_TTL)
    except Exception as e:
        logger.warning("Failed to save draft for user %d: %s", user_id, e)


async def get_draft(user_id: int) -> dict | None:
    """Get the current publishing draft."""
    try:
        r = get_redis()
        raw = await r.get(DRAFT_KEY.format(user_id=user_id))
        if raw:
            return json.loads(raw)
        return None
    except Exception as e:
        logger.warning("Failed to get draft for user %d: %s", user_id, e)
        return None


async def clear_draft(user_id: int):
    """Clear the publishing draft."""
    try:
        r = get_redis()
        await r.delete(DRAFT_KEY.format(user_id=user_id))
    except Exception:
        pass


async def get_daily_post_count(user_id: int) -> int:
    """Return how many posts this user has published today."""
    try:
        from datetime import date
        r = get_redis()
        key = DAILY_POST_KEY.format(user_id=user_id, date=date.today().isoformat())
        val = await r.get(key)
        return int(val) if val else 0
    except Exception:
        return 0


async def _increment_daily_post_count(user_id: int):
    """Increment today's post counter; expires at end of day (UTC)."""
    try:
        from datetime import date, datetime, timezone
        r = get_redis()
        key = DAILY_POST_KEY.format(user_id=user_id, date=date.today().isoformat())
        await r.incr(key)
        # Set TTL to seconds remaining until midnight UTC
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        ttl = int((midnight - now).total_seconds()) + 60  # +60s buffer
        await r.expire(key, ttl)
    except Exception as e:
        logger.warning("Failed to increment daily post count for user %d: %s", user_id, e)


async def publish_draft(user_id: int, draft: dict) -> str | None:
    """
    Publish a draft to the posts table.
    Returns post_id on success, 'daily_limit' if limit reached, None on failure.
    """
    # ── Daily limit check ──
    count = await get_daily_post_count(user_id)
    if count >= DAILY_POST_LIMIT:
        logger.info("User %d hit daily post limit (%d/%d)", user_id, count, DAILY_POST_LIMIT)
        return "daily_limit"

    try:
        post_id = await create_post(
            channel_id=draft["channel_id"],
            content=draft["content"],
            original_lang=draft.get("lang", "zh"),
            source="ugc",
            author_id=user_id,
            country=draft.get("country", ""),
            photo_file_id=draft.get("photo_file_id"),
            group_only=draft.get("group_only"),
        )

        # Increment daily counter
        await _increment_daily_post_count(user_id)

        # Award points
        await add_points(user_id, PointsConfig.PUBLISH_STORY, reason="publish")
        await increment_stat(user_id, "published_total")

        # Check if answering daily topic → bonus points
        if draft.get("is_daily_topic"):
            await add_points(user_id, PointsConfig.DAILY_TOPIC_BONUS, reason="daily_topic")

        # Clear draft
        await clear_draft(user_id)

        logger.info("User %d published post %s to channel %d", user_id, post_id, draft["channel_id"])
        return post_id

    except Exception as e:
        logger.error("Publish failed for user %d: %s", user_id, e, exc_info=True)
        return None
