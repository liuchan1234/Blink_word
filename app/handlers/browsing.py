"""
Blink.World — Private Browsing Handler
Handles card browsing in private chat: fetch next card, like/dislike/fav/report actions.

Extracted from private_chat.py for single-responsibility.
"""

import logging

from app.config import get_settings
from app.services.user_service import get_user, add_points
from app.services.feed_service import get_next_card, get_current_post_id, get_swipe_count
from app.services.post_service import record_swipe, toggle_favorite, report_post
from app.services.translation_service import get_translated_content
from app.i18n import t
from app.models import PointsConfig, Limits, ALL_CHANNEL_IDS
from app.telegram_helpers import send_message, inline_keyboard, inline_button
from app.handlers.card_builder import build_card_inline_keyboard
from app.handlers.card_sender import send_card
from app.handlers.shared import main_menu_keyboard, browse_keyboard
from app.redis_client import check_rate_limit as redis_check_rate_limit

logger = logging.getLogger(__name__)


async def start_browsing(chat_id: int, user_id: int, user, lang: str):
    """Enter browsing mode: switch keyboard and send first card."""
    await send_message(
        chat_id,
        "📖",
        reply_markup=browse_keyboard(lang),
    )
    await send_next_card(chat_id, user_id, user, lang)


async def send_next_card(chat_id: int, user_id: int, user, lang: str):
    """Fetch and send the next story card."""
    # ── Private chat rate limit ──
    allowed = await redis_check_rate_limit(
        f"pm_rate:{user_id}",
        Limits.PRIVATE_SWIPE_PER_MINUTE,
        Limits.PRIVATE_SWIPE_WINDOW,
    )
    if not allowed:
        await send_message(chat_id, t("browse_rate_limited", lang), reply_markup=browse_keyboard(lang))
        return

    channel_ids = user.channel_prefs if user.channel_prefs else ALL_CHANNEL_IDS

    card = await get_next_card(
        user_id=user_id,
        channel_ids=channel_ids,
        viewer_country=user.country,
        viewer_lang=lang,
    )

    if card is None:
        await send_message(
            chat_id,
            t("no_more_content", lang),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    post_id = card["id"]

    # Build keyboard
    card_keyboard = build_card_inline_keyboard(
        post_id,
        channel_id=card.get("channel_id", 0),
        reactions=card.get("reactions", {}),
        include_post_button=True,
        include_swipe_buttons=False,
        lang=lang,
    )

    # Send card via shared sender
    await send_card(chat_id, card, card_keyboard, lang)

    # Check points: every 10 swipes → +5 points
    swipe_count = await get_swipe_count(user_id)
    if swipe_count > 0 and swipe_count % 10 == 0:
        await add_points(user_id, PointsConfig.SWIPE_PER_10, reason="swipe_10")

    # One-time group invite: after 3rd card, only once ever
    if swipe_count == 3:
        settings = get_settings()
        add_link = f"https://t.me/{settings.BOT_USERNAME}?startgroup=true"
        await send_message(
            chat_id,
            t("group_invite_after_cards", lang),
            reply_markup=inline_keyboard([
                [inline_button(t("btn_add_to_group", lang), url=add_link)],
            ]),
        )


# ══════════════════════════════════════════════
# Reply Keyboard Actions (like / dislike / fav / report)
# ══════════════════════════════════════════════

async def handle_like(chat_id: int, user_id: int, lang: str):
    """👍 — record like + send next card."""
    post_id = await get_current_post_id(user_id)
    if post_id:
        await record_swipe(user_id, post_id, "like")

    user = await get_user(user_id)
    if user:
        await send_next_card(chat_id, user_id, user, lang)
    else:
        await send_message(chat_id, t("error_generic", lang))


async def handle_dislike(chat_id: int, user_id: int, lang: str):
    """👎 — record dislike + send next card."""
    post_id = await get_current_post_id(user_id)
    if post_id:
        await record_swipe(user_id, post_id, "dislike")

    user = await get_user(user_id)
    if user:
        await send_next_card(chat_id, user_id, user, lang)
    else:
        await send_message(chat_id, t("error_generic", lang))


async def handle_fav(chat_id: int, user_id: int, lang: str):
    """⭐ — toggle favorite (no page turn)."""
    post_id = await get_current_post_id(user_id)
    if not post_id:
        await send_message(chat_id, t("error_not_found", lang))
        return

    is_fav = await toggle_favorite(user_id, post_id)
    if is_fav:
        await send_message(chat_id, t("favorited", lang), reply_markup=browse_keyboard(lang))
    else:
        unfav_text = t("unfavorited", lang)
        await send_message(chat_id, f"⭐ {unfav_text}", reply_markup=browse_keyboard(lang))


async def handle_report_action(chat_id: int, user_id: int, lang: str):
    """⚠️ — report + send next card."""
    post_id = await get_current_post_id(user_id)
    if post_id:
        await report_post(user_id, post_id)
        await send_message(chat_id, t("reported", lang), reply_markup=browse_keyboard(lang))

    user = await get_user(user_id)
    if user:
        await send_next_card(chat_id, user_id, user, lang)
