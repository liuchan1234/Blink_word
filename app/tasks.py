"""
Blink.World — Background Tasks
Periodic tasks run by a simple asyncio scheduler in the FastAPI lifespan.

Tasks:
  - Daily topic generation (every 24h at 00:00 UTC)
  - Hot post pre-translation (every 30 min)
  - Milestone batch check (every 15 min)
  - Group daily summary (every 24h at 22:00 UTC)
"""

import asyncio
import logging
from datetime import datetime, timezone, time

from app.database import get_pool
from app.ai_client import get_ai_client
from app.i18n import t
from app.services.translation_service import pre_translate_hot_post
from app.services.milestone_service import check_milestones

logger = logging.getLogger(__name__)

# ── Task registry ──

_tasks: list[asyncio.Task] = []


def start_background_tasks():
    """Start all periodic background tasks. Called during app startup."""
    _tasks.append(asyncio.create_task(_run_periodic(_generate_daily_topic, interval=3600, name="daily_topic")))
    _tasks.append(asyncio.create_task(_run_periodic(pre_translate_hot_post, interval=1800, name="pre_translate")))
    _tasks.append(asyncio.create_task(_run_periodic(check_milestones, interval=900, name="milestone_batch")))
    _tasks.append(asyncio.create_task(_run_periodic(_send_group_summaries, interval=3600, name="group_summary")))
    logger.info("Started %d background tasks", len(_tasks))


def stop_background_tasks():
    """Cancel all background tasks."""
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    logger.info("Stopped all background tasks")


async def _run_periodic(func, interval: int, name: str):
    """Run a function periodically with error handling."""
    while True:
        try:
            await asyncio.sleep(interval)
            logger.debug("Running background task: %s", name)
            await func()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Background task %s failed: %s", name, e, exc_info=True)
            await asyncio.sleep(60)  # Wait a bit before retrying after error


# ══════════════════════════════════════════════
# Daily Topic Generation
# ══════════════════════════════════════════════

async def _generate_daily_topic():
    """Generate today's daily topic if not already set."""
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM daily_topics WHERE topic_date = CURRENT_DATE"
        )
        if existing:
            return  # Already generated today

    # Generate via AI
    ai = get_ai_client()
    system = (
        "你是一个社交平台的话题策划师。生成一个适合匿名分享的每日话题。\n"
        "话题要能引发共鸣，让人想分享自己的真实经历。\n"
        "同时提供中文和英文版本。\n"
        "返回 JSON: {\"zh\": \"中文话题\", \"en\": \"English topic\"}"
    )

    from pydantic import BaseModel

    class TopicResult(BaseModel):
        zh: str
        en: str

    result = await ai.generate_json(
        system=system,
        prompt=f"为 {datetime.now(timezone.utc).strftime('%Y-%m-%d')} 生成一个每日话题",
        schema=TopicResult,
        max_tokens=256,
        timeout_s=15.0,
    )

    if result:
        question_zh = result["zh"]
        question_en = result["en"]
    else:
        # Fallback topics
        question_zh = "你今天最想对谁说一句话？"
        question_en = "Who do you most want to say something to today?"

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO daily_topics (topic_date, question_zh, question_en)
            VALUES (CURRENT_DATE, $1, $2)
            ON CONFLICT (topic_date) DO NOTHING
            """,
            question_zh, question_en,
        )

    logger.info("Daily topic generated: %s / %s", question_zh, question_en)


# ══════════════════════════════════════════════
# Group Daily Summary
# ══════════════════════════════════════════════

async def _send_group_summaries():
    """Send daily summary to active groups. Only at ~22:00 UTC."""
    now = datetime.now(timezone.utc)
    if now.hour != 22:
        return  # Only run at 22:00 UTC

    pool = get_pool()
    async with pool.acquire() as conn:
        # Get groups that were active today
        groups = await conn.fetch(
            """
            SELECT chat_id FROM groups
            WHERE last_active >= CURRENT_DATE
            """
        )

    if not groups:
        return

    from app.services.group_service import get_group_daily_summary
    from app.telegram_helpers import send_message
    from app.i18n import t

    for group in groups:
        chat_id = group["chat_id"]
        try:
            summary = await get_group_daily_summary(chat_id)

            swipe_count = summary["swipe_count"]
            poster_count = summary["poster_count"]
            top_post = summary.get("top_post")

            if swipe_count == 0:
                continue  # No activity, skip

            # TODO: detect group language preference. Default to zh for now.
            lang = "zh"

            lines = [
                t("group_summary_header", lang),
                "",
                t("group_summary_swipes", lang, count=swipe_count),
                t("group_summary_posters", lang, count=poster_count),
            ]

            if top_post:
                preview = top_post["content"][:50] + ("..." if len(top_post["content"]) > 50 else "")
                total_r = top_post.get("total_reactions", 0)
                lines.append("")
                lines.append(t("group_summary_top", lang, count=total_r))
                lines.append(f"   {preview}")

            lines.append("")
            lines.append(t("group_summary_cta", lang))

            await send_message(chat_id, "\n".join(lines))
        except Exception as e:
            logger.warning("Failed to send summary to group %d: %s", chat_id, e)

    logger.info("Sent daily summaries to %d groups", len(groups))
