"""
Blink.World — Group Chat Handler (Round 3 Full Implementation)

/world triggers continuous flow.
Any member pressing 👍/👎/⚠️ → record action + flip to next card for everyone.
⭐ → favorite, no flip.
Rate limiting based on daily swipe count.
Group dedup: recently shown cards don't repeat.
"""

import asyncio
import logging

from app.config import get_settings
from app.telegram_helpers import send_message, send_photo, answer_callback_query, inline_keyboard, inline_button, remove_keyboard
from app.services.user_service import get_or_create_user, add_points
from app.services.group_service import (
    register_group,
    check_rate_limit,
    try_acquire_flip_lock,
    increment_swipe_count,
    set_last_post,
    get_last_post,
    add_seen_post,
    get_seen_posts,
    get_group_channel_prefs,
    toggle_group_channel,
)
from app.services.post_service import (
    get_feed_posts,
    increment_view,
    record_swipe,
    toggle_favorite,
    report_post,
)
from app.services.feed_service import set_current_post
from app.algorithm import weighted_random_select, select_post_pool_strategy
from app.handlers.card_builder import build_group_card_inline_keyboard
from app.handlers.shared import group_browse_keyboard, main_menu_keyboard
from app.models import ALL_CHANNEL_IDS, CHANNELS, get_channel_display, PointsConfig, Limits
from app.i18n import t

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Group Message Router
# ══════════════════════════════════════════════

async def handle_group_message(message: dict):
    """Handle messages in group/supergroup chats."""
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()
    user_tg = message.get("from", {})
    user_id = user_tg.get("id")
    lang = "zh"
    if user_id:
        user, _ = await get_or_create_user(user_id, user_tg.get("language_code"))
        lang = user.lang if user else "zh"

    if not chat_id:
        return

    menu_browse = t("menu_browse", lang)
    menu_post = t("menu_post", lang)
    menu_me = t("menu_me", lang)
    menu_settings = t("menu_settings", lang)
    menu_group = t("menu_group", lang)
    menu_back = t("browse_back_btn", lang)

    # Reply keyboard actions in group
    browse_like = t("browse_like_btn", lang)
    browse_next = t("browse_next_btn", lang)
    browse_fav = t("browse_favorite_btn", lang)
    browse_report = t("browse_report_btn", lang)
    browse_topics = t("browse_topics_btn", lang)

    if text in {"👍", browse_like}:
        await _handle_group_text_action(chat_id, user_id, "like")
        return
    if text in {"👎", browse_next}:
        await _handle_group_text_action(chat_id, user_id, "dislike")
        return
    if text in {"⭐", browse_fav} or text.startswith("⭐"):
        await _handle_group_text_action(chat_id, user_id, "favorite")
        return
    if text in {"⚠️", browse_report} or text.startswith("⚠️"):
        await _handle_group_text_action(chat_id, user_id, "report")
        return

    # 🎯 Topics — show group channel selector
    if text == browse_topics or text.startswith("🎯"):
        await _show_group_topics(chat_id, lang)
        return

    if text == menu_back:
        await send_message(chat_id, t("group_welcome", lang), reply_markup=main_menu_keyboard(lang))
        return

    if text == menu_browse:
        await send_message(chat_id, "📖", reply_markup=group_browse_keyboard(lang))
        await send_group_card(chat_id, lang)
        return

    if text == menu_post:
        settings = get_settings()
        await send_message(chat_id, f"{t('share_via_dm', lang)} @{settings.BOT_USERNAME}", reply_markup=main_menu_keyboard(lang))
        return

    if text == menu_me:
        settings = get_settings()
        await send_message(chat_id, f"{t('profile_via_dm', lang)} @{settings.BOT_USERNAME}", reply_markup=main_menu_keyboard(lang))
        return

    if text == menu_settings:
        settings_obj = get_settings()
        settings_link = f"https://t.me/{settings_obj.BOT_USERNAME}?start=open_settings"
        hint = t("settings_open_hint", lang)
        keyboard = inline_keyboard([
            [inline_button("⚙️ " + t("menu_settings", lang), url=settings_link)]
        ])
        await send_message(chat_id, hint, reply_markup=keyboard)
        return

    if text == menu_group:
        await send_message(chat_id, t("already_in_group", lang), reply_markup=main_menu_keyboard(lang))
        return

    # /world command triggers the continuous flow
    # Also handle /start and /blink (legacy) in groups
    if text == "/world" or text.startswith("/world@") \
       or text == "/blink" or text.startswith("/blink@") \
       or text == "/start" or text.startswith("/start@"):
        await send_message(chat_id, "📖", reply_markup=group_browse_keyboard(lang))
        await send_group_card(chat_id, lang)
        return

    # /stop command — hide the reply keyboard
    if text == "/stop" or text.startswith("/stop@"):
        await send_message(chat_id, t("group_stopped", lang), reply_markup=remove_keyboard())
        return


# ══════════════════════════════════════════════
# Group Card — Send Next
# ══════════════════════════════════════════════

async def send_group_card(chat_id: int, lang: str = "zh"):
    """Fetch and send the next card to the group.
    Caller must hold the flip lock. Lock is released when done."""
    from app.services.group_service import release_flip_lock

    try:
        # Check rate limit
        wait_seconds = await check_rate_limit(chat_id)
        if wait_seconds > 0:
            await send_message(chat_id, t("group_rate_limited", lang, seconds=wait_seconds))
            return

        # Get group's seen posts for dedup
        seen = await get_seen_posts(chat_id)

        # Use group's channel preferences (or all channels if not set)
        channel_ids = await get_group_channel_prefs(chat_id) or ALL_CHANNEL_IDS

        # 50/50 pool strategy
        pool_type = select_post_pool_strategy()

        # Fetch candidates (global posts only, not group_only from other groups)
        candidates = await get_feed_posts(
            channel_ids=channel_ids,
            exclude_post_ids=seen,
            viewer_country="",
            viewer_lang=lang,
            pool_type=pool_type,
            limit=30,
        )

        if not candidates and pool_type == "local":
            candidates = await get_feed_posts(
                channel_ids=channel_ids,
                exclude_post_ids=seen,
                viewer_country="",
                viewer_lang=lang,
                pool_type="global",
                limit=30,
            )

        if not candidates:
            await send_message(chat_id, t("no_more_content", lang))
            return

        # Weighted random selection
        from datetime import datetime, timezone
        selected = weighted_random_select(candidates, "", lang, datetime.now(timezone.utc))

        if not selected:
            await send_message(chat_id, t("no_more_content", lang))
            return

        post_id = selected["id"]

        # Build group-style keyboard
        card_keyboard = build_group_card_inline_keyboard(post_id, channel_id=selected.get("channel_id", 0), reactions=selected.get("reactions", {}), lang=lang)

        # Send card via shared sender (handles translate + photo/pending + message tracking)
        from app.handlers.card_sender import send_card
        await send_card(chat_id, selected, card_keyboard, lang)

        await set_last_post(chat_id, post_id)
        await add_seen_post(chat_id, post_id)
        await increment_view(post_id)
        await increment_swipe_count(chat_id)
    finally:
        # Release lock immediately so next click can proceed
        await release_flip_lock(chat_id)


async def _handle_group_text_action(chat_id: int, user_id: int | None, action: str):
    """Handle group actions from reply keyboard text buttons."""
    if not user_id:
        return

    user, _ = await get_or_create_user(user_id, None)
    lang = user.lang if user else "zh"
    post_id = await get_last_post(chat_id)
    if not post_id:
        await send_message(chat_id, t("no_more_content", lang), reply_markup=group_browse_keyboard(lang))
        return

    if action in ("like", "dislike"):
        await record_swipe(user_id, post_id, action)
        await add_points(user_id, PointsConfig.GROUP_PARTICIPATE, reason="group_swipe")
        acquired = await try_acquire_flip_lock(chat_id)
        if acquired:
            await send_group_card(chat_id, lang)
        # If not acquired, another request is already sending the next card — no need to wait
        return

    if action == "favorite":
        is_fav = await toggle_favorite(user_id, post_id)
        text = t("favorited", lang) if is_fav else t("unfavorited", lang)
        await send_message(chat_id, text, reply_markup=group_browse_keyboard(lang))
        return

    if action == "report":
        await report_post(user_id, post_id)
        acquired = await try_acquire_flip_lock(chat_id)
        if acquired:
            await send_group_card(chat_id, lang)


# ══════════════════════════════════════════════
# Group Inline Button Actions
# ══════════════════════════════════════════════

async def handle_group_swipe(
    cb_id: str,
    chat_id: int,
    message_id: int,
    user_id: int,
    post_id: str,
    action: str,
    lang: str,
):
    """
    Handle 👍/👎/⚠️ in group — records action + flips to next card.
    First person to press triggers the flip for the whole group.
    """
    # Record the individual action
    if action in ("like", "dislike"):
        await record_swipe(user_id, post_id, action)
        await add_points(user_id, PointsConfig.GROUP_PARTICIPATE, reason="group_swipe")
    elif action == "report":
        await report_post(user_id, post_id)

    await answer_callback_query(cb_id)

    # Atomic flip lock — prevents duplicate card sends from concurrent clicks
    acquired = await try_acquire_flip_lock(chat_id)
    if acquired:
        # send_group_card releases the lock in its finally block
        await send_group_card(chat_id, lang)


async def handle_group_favorite(cb_id: str, user_id: int, post_id: str, lang: str):
    """Handle ⭐ in group — favorite, no flip."""
    is_fav = await toggle_favorite(user_id, post_id)
    text = t("favorited", lang) if is_fav else t("unfavorited", lang)
    await answer_callback_query(cb_id, text=text)


# ══════════════════════════════════════════════
# Group Topics — Channel Selector
# ══════════════════════════════════════════════

async def _show_group_topics(chat_id: int, lang: str):
    """Show inline channel selector for group channel preferences."""
    current = await get_group_channel_prefs(chat_id) or list(ALL_CHANNEL_IDS)

    rows = []
    for ch in CHANNELS:
        mark = "✅" if ch.id in current else "❌"
        name = get_channel_display(ch.id, lang)
        rows.append([inline_button(f"{mark} {name}", f"gtopic:{chat_id}:{ch.id}")])

    rows.append([inline_button(t("group_topics_start", lang), f"gtopic:{chat_id}:start")])

    await send_message(
        chat_id,
        t("group_topics_header", lang),
        reply_markup=inline_keyboard(rows),
    )


async def handle_group_topic_toggle(
    cb_id: str, chat_id: int, message_id: int, channel_id: int, lang: str,
):
    """Handle inline button toggle for group channel selector."""
    from app.telegram_helpers import edit_message_reply_markup

    new_prefs = await toggle_group_channel(chat_id, channel_id)

    # Rebuild keyboard with updated checkmarks — single column
    rows = []
    for ch in CHANNELS:
        mark = "✅" if ch.id in new_prefs else "❌"
        name = get_channel_display(ch.id, lang)
        rows.append([inline_button(f"{mark} {name}", f"gtopic:{chat_id}:{ch.id}")])

    rows.append([inline_button(t("group_topics_start", lang), f"gtopic:{chat_id}:start")])

    await edit_message_reply_markup(
        chat_id, message_id, reply_markup=inline_keyboard(rows),
    )
    await answer_callback_query(cb_id)


# ══════════════════════════════════════════════
# Bot Membership Changes
# ══════════════════════════════════════════════

async def handle_bot_membership_change(update: dict):
    """Handle bot being added to or removed from a group."""
    chat = update.get("chat", {})
    chat_id = chat.get("id")
    chat_title = chat.get("title", "")
    new_member = update.get("new_chat_member", {})
    status = new_member.get("status", "")
    added_by_user = update.get("from", {})
    added_by_id = added_by_user.get("id")

    if not chat_id:
        return

    if status in ("member", "administrator"):
        # Bot was added to group
        logger.info("Bot added to group %d (%s) by user %s", chat_id, chat_title, added_by_id)

        # Register group in DB
        await register_group(chat_id, title=chat_title, added_by=added_by_id)

        # Detect language from the user who added the bot
        lang = "en"
        if added_by_id:
            user, is_new = await get_or_create_user(added_by_id, added_by_user.get("language_code"))
            await add_points(added_by_id, PointsConfig.ADD_BOT_TO_GROUP, reason="add_bot_to_group")
            lang = user.lang if user else "en"

            # Notify the user privately about their reward
            try:
                text = t("group_add_reward", lang,
                         title=chat_title, points=PointsConfig.ADD_BOT_TO_GROUP)
                await send_message(added_by_id, text)
            except Exception:
                pass

        # Send short welcome + main menu + auto-send a hot card
        await send_message(chat_id, t("group_welcome", lang), reply_markup=main_menu_keyboard(lang))
        await send_group_card(chat_id, lang)

    elif status in ("left", "kicked"):
        logger.info("Bot removed from group %d (%s)", chat_id, chat_title)
