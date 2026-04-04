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
from app.telegram_helpers import (
    send_message, send_photo, answer_callback_query,
    inline_keyboard, inline_button,
)
from app.models import get_channel_display
from app.services.admin_service import (
    get_admin_overview,
    get_next_flagged_post,
    keep_post,
    remove_post,
    get_moderation_stats,
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
        await keep_post(post_id)
        await answer_callback_query(cb_id, text="✅ Kept")
        await _send_next_review_item(chat_id)

    elif action == "remove" and len(parts) >= 3:
        post_id = parts[2]
        await remove_post(post_id)
        await answer_callback_query(cb_id, text="🚫 Removed")
        await _send_next_review_item(chat_id)

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
    overview = await get_admin_overview()

    text = (
        "<b>🔧 Admin Panel</b>\n\n"
        f"📊 Total users: <b>{overview['total_users']}</b>\n"
        f"📝 Total posts: <b>{overview['total_posts']}</b>\n"
        f"🚫 Removed: <b>{overview['removed']}</b>\n"
        f"⚠️ Flagged (needs review): <b>{overview['flagged']}</b>\n"
    )

    keyboard = inline_keyboard([
        [inline_button(f"⚠️ Review flagged ({overview['flagged']})", "adm:review")],
        [inline_button("📊 Detailed stats", "adm:stats")],
    ])

    await send_message(chat_id, text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Review Queue
# ══════════════════════════════════════════════

async def _send_next_review_item(chat_id: int):
    """Send the next flagged post for admin review."""
    row = await get_next_flagged_post()

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

    channel = get_channel_display(row["channel_id"], "en")
    source = row["source"]
    author = f"user:{row['author_id']}" if row["author_id"] else "AI/ops"

    review_text = (
        f"<b>⚠️ REVIEW — {report_count} reports</b>\n\n"
        f"📺 {channel} · 🌍 {row['country']}\n"
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

    if row["photo_file_id"] and not row["photo_file_id"].startswith("pending:"):
        await send_photo(chat_id, photo=row["photo_file_id"], caption=review_text, reply_markup=keyboard)
    else:
        await send_message(chat_id, review_text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Stats
# ══════════════════════════════════════════════

async def _send_moderation_stats(chat_id: int):
    """Send detailed moderation statistics."""
    stats = await get_moderation_stats()

    channel_lines = []
    for ch in stats["channels"]:
        name = get_channel_display(ch["channel_id"], "en")
        channel_lines.append(
            f"  {name}: {ch['active_count']}/{ch['total']} active · {ch['total_reports']} reports"
        )

    recent_lines = []
    for r in stats["recent"]:
        preview = r["content"][:40] + "..." if len(r["content"]) > 40 else r["content"]
        rate = (r["report_count"] / r["view_count"] * 100) if r["view_count"] > 0 else 0
        recent_lines.append(f"  ⚠️ {r['report_count']} reports ({rate:.0f}%) — {preview}")

    text = (
        "<b>📊 Moderation Stats</b>\n\n"
        f"Total posts: {stats['total']}\n"
        f"Active: {stats['active']}\n"
        f"Removed: {stats['removed']}\n"
        f"Flagged: {stats['flagged']}\n"
        f"High risk (>5% report rate): {stats['high_risk']}\n\n"
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
