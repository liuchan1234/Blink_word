"""
Blink.World — Admin Service
Database operations for content moderation. Extracted from admin_review.py.
"""

import logging

from app.database import get_pool
from app.models import Limits

logger = logging.getLogger(__name__)


async def get_admin_overview() -> dict:
    """Get admin panel overview stats."""
    pool = get_pool()
    async with pool.acquire() as conn:
        flagged = await conn.fetchval(
            "SELECT COUNT(*) FROM posts WHERE is_active = TRUE AND report_count > 0"
        )
        total_posts = await conn.fetchval("SELECT COUNT(*) FROM posts")
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        removed = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_active = FALSE")

    return {
        "flagged": flagged or 0,
        "total_posts": total_posts or 0,
        "total_users": total_users or 0,
        "removed": removed or 0,
    }


async def get_next_flagged_post() -> dict | None:
    """Get the most reported active post for review."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.id, p.channel_id, p.content, p.photo_file_id,
                   p.country, p.source, p.author_id,
                   p.report_count, p.view_count, p.like_count, p.dislike_count,
                   p.reactions, p.created_at
            FROM posts p
            WHERE p.is_active = TRUE
              AND p.report_count > 0
            ORDER BY p.report_count DESC, p.created_at ASC
            LIMIT 1
            """
        )

    if row is None:
        return None
    return dict(row)


async def keep_post(post_id: str):
    """Mark post as reviewed and safe — clear report count."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET report_count = 0 WHERE id = $1",
            post_id,
        )
    logger.info("Admin kept post %s", post_id)


async def remove_post(post_id: str):
    """Remove a post — set is_active = FALSE."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET is_active = FALSE WHERE id = $1",
            post_id,
        )
    logger.info("Admin removed post %s", post_id)


async def get_moderation_stats() -> dict:
    """Get detailed moderation statistics."""
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM posts")
        active = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_active = TRUE")
        removed = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_active = FALSE")
        flagged = await conn.fetchval(
            "SELECT COUNT(*) FROM posts WHERE is_active = TRUE AND report_count > 0"
        )
        high_risk = await conn.fetchval(
            """
            SELECT COUNT(*) FROM posts
            WHERE is_active = TRUE AND view_count >= $1
            AND report_count::float / GREATEST(view_count, 1) > $2
            """,
            Limits.REPORT_MIN_VIEWS,
            Limits.REPORT_DEMOTE_RATE,
        )

        channels = await conn.fetch(
            """
            SELECT channel_id, COUNT(*) as total,
                   SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_count,
                   SUM(report_count) as total_reports
            FROM posts
            GROUP BY channel_id
            ORDER BY channel_id
            """
        )

        recent = await conn.fetch(
            """
            SELECT p.id, p.content, p.report_count, p.view_count
            FROM posts p
            WHERE p.report_count > 0 AND p.is_active = TRUE
            ORDER BY p.report_count DESC
            LIMIT 5
            """
        )

    return {
        "total": total or 0,
        "active": active or 0,
        "removed": removed or 0,
        "flagged": flagged or 0,
        "high_risk": high_risk or 0,
        "channels": [dict(r) for r in channels],
        "recent": [dict(r) for r in recent],
    }

