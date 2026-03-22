"""
Blink.World — Group Chat Handler (Round 3 Full Implementation)

/blink triggers continuous flow.
Any member pressing 👍/👎/⚠️ → record action + flip to next card for everyone.
⭐ → favorite, no flip.
Rate limiting based on daily swipe count.
Group dedup: recently shown cards don't repeat.
"""

import logging

from app.telegram_helpers import send_message, send_photo, answer_callback_query
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
)
from app.services.post_service import (
    get_feed_posts,
    increment_view,
    save_post_message,
    record_swipe,
    toggle_favorite,
    report_post,
)
from app.services.feed_service import set_current_post
from app.algorithm import weighted_random_select, select_post_pool_strategy
from app.handlers.card_builder import build_card_text, build_group_card_inline_keyboard
from app.models import ALL_CHANNEL_IDS, PointsConfig
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

    if not chat_id:
        return

    # /blink command triggers the continuous flow
    if text == "/blink" or text.startswith("/blink@"):
        if user_id:
            user, _ = await get_or_create_user(user_id, user_tg.get("language_code"))
        await _send_group_card(chat_id)
        return


# ══════════════════════════════════════════════
# Group Card — Send Next
# ══════════════════════════════════════════════

async def _send_group_card(chat_id: int, lang: str = "zh"):
    """Fetch and send the next card to the group."""
    # Check rate limit
    wait_seconds = await check_rate_limit(chat_id)
    if wait_seconds > 0:
        await send_message(chat_id, t("group_rate_limited", lang, seconds=wait_seconds))
        return

    # Get group's seen posts for dedup
    seen = await get_seen_posts(chat_id)

    # 50/50 pool strategy
    pool_type = select_post_pool_strategy()

    # Fetch candidates (global posts only, not group_only from other groups)
    candidates = await get_feed_posts(
        channel_ids=ALL_CHANNEL_IDS,
        exclude_post_ids=seen,
        viewer_country="",
        viewer_lang=lang,
        pool_type=pool_type,
        limit=30,
    )

    if not candidates and pool_type == "local":
        candidates = await get_feed_posts(
            channel_ids=ALL_CHANNEL_IDS,
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

    # Translate content if needed
    from app.services.translation_service import get_translated_content
    translated = await get_translated_content(
        post_id=post_id,
        content=selected.get("content", ""),
        original_lang=selected.get("original_lang", "zh"),
        target_lang=lang,
    )

    # Build card
    card_text = build_card_text(selected, lang=lang, translated_content=translated)
    card_keyboard = build_group_card_inline_keyboard(post_id, selected.get("reactions", {}))

    # Send card
    photo_file_id = selected.get("photo_file_id")
    result = None

    if photo_file_id and photo_file_id.startswith("pending:"):
        # Deferred image upload
        from app.handlers.private_chat import _send_pending_image
        result = await _send_pending_image(chat_id, photo_file_id, card_text, card_keyboard, post_id)
    elif photo_file_id:
        result = await send_photo(
            chat_id,
            photo=photo_file_id,
            caption=card_text,
            reply_markup=card_keyboard,
        )
    else:
        result = await send_message(
            chat_id,
            card_text,
            reply_markup=card_keyboard,
        )

    # Track
    if result and isinstance(result, dict):
        msg_id = result.get("message_id")
        if msg_id:
            await save_post_message(chat_id, msg_id, post_id)

    await set_last_post(chat_id, post_id)
    await add_seen_post(chat_id, post_id)
    await increment_view(post_id)
    await increment_swipe_count(chat_id)


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

    # Atomic flip lock — only one flip per button press wave
    acquired = await try_acquire_flip_lock(chat_id)
    if not acquired:
        # Another user already triggered the flip, skip
        return

    # Send next card to the group
    await _send_group_card(chat_id, lang)


async def handle_group_favorite(cb_id: str, user_id: int, post_id: str, lang: str):
    """Handle ⭐ in group — favorite, no flip."""
    is_fav = await toggle_favorite(user_id, post_id)
    text = t("favorited", lang) if is_fav else ("已取消收藏" if lang == "zh" else "Unsaved")
    await answer_callback_query(cb_id, text=text)


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

        # Award points to the user who added the bot
        if added_by_id:
            user, is_new = await get_or_create_user(added_by_id, added_by_user.get("language_code"))
            await add_points(added_by_id, PointsConfig.ADD_BOT_TO_GROUP, reason="add_bot_to_group")

            # Send welcome in the detected language
            lang = user.lang if user else "en"
            await send_message(chat_id, t("group_welcome", lang))

            # Notify the user privately about their reward
            try:
                if lang == "zh":
                    text = f"🎉 你将 Bot 拉入了群组「{chat_title}」，获得 +{PointsConfig.ADD_BOT_TO_GROUP} 积分！"
                else:
                    text = f"🎉 You added the Bot to \"{chat_title}\", earned +{PointsConfig.ADD_BOT_TO_GROUP} points!"
                await send_message(added_by_id, text)
            except Exception:
                pass  # Private notification failure is non-blocking
        else:
            await send_message(chat_id, t("group_welcome", "en"))

    elif status in ("left", "kicked"):
        logger.info("Bot removed from group %d (%s)", chat_id, chat_title)
