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


async def check_milestones_batch():
    """Batch check milestones for all recent posts."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Get posts with recent reactions (last 24 hours)
        posts = await conn.fetch(
            """
            SELECT id, author_id FROM posts
            WHERE updated_at > NOW() - INTERVAL '24 hours'
            ORDER BY updated_at DESC
            LIMIT 1000
            """
        )

    for post in posts:
        await check_milestones(post["id"], post["author_id"])

    if posts:
        logger.info("Checked milestones for %d posts", len(posts))


async def _send_milestone_push(
    author_id: int, threshold: int, points: int, total_reactions: int, new_points_total: int,
):
    """Send milestone push notification to author."""
    author = await get_user(author_id)
    if not author:
        return

    lang = author.lang
    milestone_text = t(f"milestone_{threshold}", lang)

    if lang == "zh":
        text = (
            f"{milestone_text}\n\n"
            f"📊 总互动: <b>{total_reactions}</b>\n"
            f"💰 积分 +{points}（当前: {new_points_total}）\n\n"
            f"继续创作吧！更多人在等着你的故事 ✨"
        )
    else:
        text = (
            f"{milestone_text}\n\n"
            f"📊 Total interactions: <b>{total_reactions}</b>\n"
            f"💰 +{points} points (Total: {new_points_total})\n\n"
            f"Keep creating! More people await your stories ✨"
        )

    browse_text = "📖 看故事" if lang == "zh" else "📖 Browse"
    post_text = "📝 再写一个" if lang == "zh" else "📝 Write more"
    keyboard = inline_keyboard([
        [inline_button(browse_text, "menu:browse"), inline_button(post_text, "post_also")],
    ])

    try:
        await send_message(author_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.warning("Milestone push to %d failed: %s", author_id, e)


