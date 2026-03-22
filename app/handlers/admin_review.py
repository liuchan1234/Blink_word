"""
Blink.World — Admin Review Handler
Bot-based content moderation. Admins review flagged content directly in Telegram chat.

Commands:
  /admin           → Show admin menu
  /admin review    → Start reviewing flagged content
  /admin stats     → Show moderation stats

Callback actions:
  adm:keep:{post_id}   → Mark as safe, keep active
  adm:remove:{post_id} → Remove (set is_active=FALSE)
  adm:skip             → Skip to next item
"""

import logging

from app.config import get_settings
from app.database import get_pool
from app.telegram_helpers import (
    send_message, send_photo, answer_callback_query,
    inline_keyboard, inline_button, edit_message_text,
)

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    settings = get_settings()
    if not settings.ADMIN_USER_IDS:
        return False
    try:
        admin_ids = [int(x.strip()) for x in settings.ADMIN_USER_IDS.split(",") if x.strip()]
        return user_id in admin_ids
    except (ValueError, TypeError):
        return False


async def handle_admin_command(chat_id: int, user_id: int, text: str):
    """Route admin commands."""
    if not is_admin(user_id):
        await send_message(chat_id, "You are not an admin.")
        return

    parts = text.strip().split()
    subcommand = parts[1] if len(parts) > 1 else ""

    if subcommand == "review":
        await _send_next_review_item(chat_id)
    elif subcommand == "stats":
        await _send_moderation_stats(chat_id)
    else:
        await _send_admin_menu(chat_id)


async def handle_admin_callback(cb_id: str, chat_id: int, user_id: int, data: str):
    """Handle admin review actions from inline buttons."""
    if not is_admin(user_id):
        await answer_callback_query(cb_id, text="Not authorized", show_alert=True)
        return

    parts = data.split(":")
    if len(parts) < 2:
        await answer_callback_query(cb_id)
        return

    action = parts[1]

    if action == "keep" and len(parts) >= 3:
        post_id = parts[2]
        await _action_keep(cb_id, chat_id, post_id)

    elif action == "remove" and len(parts) >= 3:
        post_id = parts[2]
        await _action_remove(cb_id, chat_id, post_id)

    elif action == "skip":
        await answer_callback_query(cb_id)
        await _send_next_review_item(chat_id)

    elif action == "review":
        await answer_callback_query(cb_id)
        await _send_next_review_item(chat_id)

    elif action == "stats":
        await answer_callback_query(cb_id)
        await _send_moderation_stats(chat_id)

    else:
        await answer_callback_query(cb_id)


# ══════════════════════════════════════════════
# Admin Menu
# ══════════════════════════════════════════════

async def _send_admin_menu(chat_id: int):
    """Show admin control panel."""
    pool = get_pool()
    async with pool.acquire() as conn:
        flagged = await conn.fetchval(
            """
            SELECT COUNT(*) FROM posts
            WHERE is_active = TRUE AND report_count > 0
            ORDER BY report_count DESC
            """
        )
        total_posts = await conn.fetchval("SELECT COUNT(*) FROM posts")
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        removed = await conn.fetchval("SELECT COUNT(*) FROM posts WHERE is_active = FALSE")

    text = (
        "<b>🔧 Admin Panel</b>\n\n"
        f"📊 Total users: <b>{total_users}</b>\n"
        f"📝 Total posts: <b>{total_posts}</b>\n"
        f"🚫 Removed: <b>{removed}</b>\n"
        f"⚠️ Flagged (needs review): <b>{flagged}</b>\n"
    )

    keyboard = inline_keyboard([
        [inline_button(f"⚠️ Review flagged ({flagged})", "adm:review")],
        [inline_button("📊 Detailed stats", "adm:stats")],
    ])

    await send_message(chat_id, text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Review Queue
# ══════════════════════════════════════════════

async def _send_next_review_item(chat_id: int):
    """Send the next flagged post for admin review."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Get the most reported active post that hasn't been admin-reviewed
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

    if not row:
        await send_message(
            chat_id,
            "✅ <b>No flagged content to review!</b>\n\nAll clear.",
            reply_markup=inline_keyboard([
                [inline_button("🔙 Admin menu", "adm:menu")],
            ]),
        )
        return

    post_id = row["id"]
    report_count = row["report_count"]
    view_count = row["view_count"]
    report_rate = (report_count / view_count * 100) if view_count > 0 else 0

    from app.models import get_channel_display
    channel = get_channel_display(row["channel_id"], "en")
    source = row["source"]
    author = f"user:{row['author_id']}" if row["author_id"] else "AI/ops"

    # Build review card
    review_text = (
        f"<b>⚠️ REVIEW — {report_count} reports</b>\n\n"
        f"📺 {channel} · 📍 {row['country']}\n"
        f"👤 Source: {source} · Author: {author}\n"
        f"📊 Views: {view_count} · Reports: {report_count} ({report_rate:.1f}%)\n"
        f"👍 {row['like_count']} · 👎 {row['dislike_count']}\n"
        f"📅 {row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '?'}\n\n"
        f"── Content ──\n\n"
        f"{row['content']}\n\n"
        f"── ID: <code>{post_id}</code> ──"
    )

    keyboard = inline_keyboard([
        [
            inline_button("✅ Keep", f"adm:keep:{post_id}"),
            inline_button("🚫 Remove", f"adm:remove:{post_id}"),
        ],
        [
            inline_button("⏭️ Skip", "adm:skip"),
            inline_button("🔙 Admin menu", "adm:menu"),
        ],
    ])

    # Send photo if exists, otherwise text
    if row["photo_file_id"] and not row["photo_file_id"].startswith("pending:"):
        await send_photo(chat_id, photo=row["photo_file_id"], caption=review_text, reply_markup=keyboard)
    else:
        await send_message(chat_id, review_text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Actions
# ══════════════════════════════════════════════

async def _action_keep(cb_id: str, chat_id: int, post_id: str):
    """Mark post as reviewed and safe — clear report count."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET report_count = 0 WHERE id = $1",
            post_id,
        )
    await answer_callback_query(cb_id, text="✅ Kept")
    logger.info("Admin kept post %s", post_id)
    # Send next item
    await _send_next_review_item(chat_id)


async def _action_remove(cb_id: str, chat_id: int, post_id: str):
    """Remove a post — set is_active = FALSE."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET is_active = FALSE WHERE id = $1",
            post_id,
        )
    await answer_callback_query(cb_id, text="🚫 Removed")
    logger.info("Admin removed post %s", post_id)
    # Send next item
    await _send_next_review_item(chat_id)


# ══════════════════════════════════════════════
# Stats
# ══════════════════════════════════════════════

async def _send_moderation_stats(chat_id: int):
    """Send detailed moderation statistics."""
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
            WHERE is_active = TRUE AND view_count >= 10
            AND report_count::float / GREATEST(view_count, 1) > 0.05
            """
        )

        # Per-channel breakdown
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

        # Recent reports
        recent = await conn.fetch(
            """
            SELECT p.id, p.content, p.report_count, p.view_count
            FROM posts p
            WHERE p.report_count > 0 AND p.is_active = TRUE
            ORDER BY p.report_count DESC
            LIMIT 5
            """
        )

    from app.models import get_channel_display
    channel_lines = []
    for ch in channels:
        name = get_channel_display(ch["channel_id"], "en")
        channel_lines.append(
            f"  {name}: {ch['active_count']}/{ch['total']} active · {ch['total_reports']} reports"
        )

    recent_lines = []
    for r in recent:
        preview = r["content"][:40] + "..." if len(r["content"]) > 40 else r["content"]
        rate = (r["report_count"] / r["view_count"] * 100) if r["view_count"] > 0 else 0
        recent_lines.append(f"  ⚠️ {r['report_count']} reports ({rate:.0f}%) — {preview}")

    text = (
        "<b>📊 Moderation Stats</b>\n\n"
        f"Total posts: {total}\n"
        f"Active: {active}\n"
        f"Removed: {removed}\n"
        f"Flagged: {flagged}\n"
        f"High risk (>5% report rate): {high_risk}\n\n"
        f"<b>Per channel:</b>\n"
        + "\n".join(channel_lines) + "\n\n"
        f"<b>Top reported (active):</b>\n"
        + ("\n".join(recent_lines) if recent_lines else "  None") + "\n"
    )

    keyboard = inline_keyboard([
        [inline_button("⚠️ Start reviewing", "adm:review")],
        [inline_button("🔙 Admin menu", "adm:menu")],
    ])

    await send_message(chat_id, text, reply_markup=keyboard)
