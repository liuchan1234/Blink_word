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


async def publish_draft(user_id: int, draft: dict) -> str | None:
    """
    Publish a draft to the posts table.
    Returns post_id on success, None on failure.
    """
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
