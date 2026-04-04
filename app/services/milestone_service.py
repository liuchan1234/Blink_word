"""
Blink.World — Milestone Service

Checks post reaction thresholds and sends push notifications to authors.
Each milestone per post triggers only once (post_milestones table).

Thresholds: 10(+10) / 30(+30) / 100(+100) / 300(+300) / 1000(+1000)
"""

import logging

from app.database import get_pool
from app.models import MILESTONE_LEVELS
from app.services.user_service import add_points, get_user
from app.telegram_helpers import send_message, inline_keyboard, inline_button
from app.i18n import t

logger = logging.getLogger(__name__)


async def check_milestones(post_id: str, author_id: int | None):
    """Check if a post crossed any milestone thresholds. Idempotent."""
    if not author_id:
        return

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE((SELECT SUM((value)::int) FROM jsonb_each_text(reactions)), 0) as total_reactions,
                like_count, content, channel_id
            FROM posts WHERE id = $1
            """,
            post_id,
        )
        if not row:
            return

        total = row["total_reactions"] + row["like_count"]

        triggered = await conn.fetch(
            "SELECT milestone_level FROM post_milestones WHERE post_id = $1", post_id,
        )
        triggered_set = {r["milestone_level"] for r in triggered}

        for milestone in MILESTONE_LEVELS:
            threshold = milestone["threshold"]
            points = milestone["points"]

            if total >= threshold and threshold not in triggered_set:
                result = await conn.execute(
                    """
                    INSERT INTO post_milestones (post_id, milestone_level)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """,
                    post_id, threshold,
                )
                if "INSERT 0 1" in result:
                    new_total = await add_points(author_id, points, reason=f"milestone_{threshold}")
                    await _send_milestone_push(author_id, threshold, points, total, new_total)
                    logger.info("Milestone %d for post %s (author=%d, +%d)", threshold, post_id, author_id, points)


async def _send_milestone_push(
    author_id: int, threshold: int, points: int, total_reactions: int, new_points_total: int,
):
    """Send milestone push notification to author."""
    author = await get_user(author_id)
    if not author:
        return

    lang = author.lang
    milestone_text = t(f"milestone_{threshold}", lang)

    text = t("milestone_push_body", lang,
             milestone=milestone_text, total=total_reactions,
             points=points, current=new_points_total)

    keyboard = inline_keyboard([
        [inline_button(t("milestone_browse_btn", lang), "menu:browse"),
         inline_button(t("milestone_post_btn", lang), "post_also")],
    ])

    try:
        await send_message(author_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.warning("Milestone push to %d failed: %s", author_id, e)


async def check_milestones_batch():
    """
    Periodic batch milestone scan.
    Re-check recent posts so missed real-time triggers can be recovered.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, author_id
            FROM posts
            WHERE author_id IS NOT NULL
              AND created_at > NOW() - INTERVAL '30 days'
            ORDER BY created_at DESC
            LIMIT 500
            """
        )

    if not rows:
        return

    for row in rows:
        try:
            await check_milestones(row["id"], row["author_id"])
        except Exception as e:
            logger.warning("Batch milestone check failed for post %s: %s", row["id"], e)


