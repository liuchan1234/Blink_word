"""
Blink.World — Profile Callbacks
Extracted from callbacks.py: creator panel (my stories) and favorites list.
"""

import json
import logging

from app.database import get_pool
from app.telegram_helpers import answer_callback_query, send_message
from app.services.country_service import get_country_display as fmt_country
from app.i18n import t
from app.models import get_channel_display, Limits

logger = logging.getLogger(__name__)


async def handle_profile(cb_id: str, chat_id: int, user_id: int, data: str, lang: str):
    """Handle profile:stories and profile:favorites."""
    action = data.split(":", 1)[1] if ":" in data else ""
    await answer_callback_query(cb_id)

    if action == "stories":
        await _show_creator_panel(chat_id, user_id, lang)
    elif action == "favorites":
        await _show_favorites(chat_id, user_id, lang)


async def _show_creator_panel(chat_id: int, user_id: int, lang: str):
    """Show creator's published stories with stats."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, channel_id, content, like_count, view_count, reactions,
                   created_at
            FROM posts
            WHERE author_id = $1 AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            Limits.PROFILE_STORIES_LIMIT,
        )

    if not rows:
        await send_message(chat_id, f"📊 {t('no_stories_yet', lang)}")
        return

    lines = [t("my_stories_title", lang)]

    for i, row in enumerate(rows, 1):
        reactions = row["reactions"]
        if isinstance(reactions, str):
            reactions = json.loads(reactions)

        channel_name = get_channel_display(row["channel_id"], lang)
        content_preview = row["content"][:40] + ("..." if len(row["content"]) > 40 else "")

        # Line 1: views, likes
        stats_line = f"👁 {row['view_count']} · 👍 {row['like_count']}"

        # Line 2: emoji reactions (separate line for readability)
        emoji_line = ""
        if reactions and isinstance(reactions, dict):
            emoji_parts = [f"{e} {c}" for e, c in reactions.items() if c > 0]
            if emoji_parts:
                emoji_line = " ".join(emoji_parts[:5])

        lines.append(f"\n<b>{i}.</b> {channel_name}")
        lines.append(f"   {content_preview}")
        lines.append(f"   {stats_line}")
        if emoji_line:
            lines.append(f"   {emoji_line}")

    await send_message(chat_id, "\n".join(lines))


async def _show_favorites(chat_id: int, user_id: int, lang: str):
    """Show user's saved/favorited stories."""
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.channel_id, p.content, p.country
            FROM post_favorites pf
            JOIN posts p ON p.id = pf.post_id
            WHERE pf.user_id = $1 AND p.is_active = TRUE
            ORDER BY pf.created_at DESC
            LIMIT $2
            """,
            user_id,
            Limits.PROFILE_FAVORITES_LIMIT,
        )

    if not rows:
        await send_message(chat_id, f"⭐ {t('no_favorites_yet', lang)}")
        return

    lines = [t("my_favorites_title", lang)]

    for i, row in enumerate(rows, 1):
        channel_name = get_channel_display(row["channel_id"], lang)
        content_preview = row["content"][:50] + ("..." if len(row["content"]) > 50 else "")
        country = row["country"]

        lines.append(f"\n<b>{i}.</b> {channel_name}")
        if country:
            lines[-1] += f" · {fmt_country(country, lang)}"
        lines.append(f"   {content_preview}")

    await send_message(chat_id, "\n".join(lines))
