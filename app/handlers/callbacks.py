"""
Blink.World — Callback Query Dispatcher
Routes all inline keyboard button presses to appropriate sub-handlers.

Sub-modules:
  cb_settings.py    — language, country, channel toggle, location toggle
  cb_publishing.py  — channel select, content preview, publish confirm/cancel
  cb_profile.py     — creator panel (my stories), favorites list
"""

import logging

from app.config import get_settings
from app.telegram_helpers import (
    answer_callback_query, send_message,
    edit_message_reply_markup,
    inline_keyboard, inline_button,
)
from app.services.user_service import get_or_create_user, get_user
from app.services.post_service import (
    add_reaction, remove_reaction, get_user_reactions, get_post,
    record_swipe, toggle_favorite, report_post,
)
from app.i18n import t
from app.models import REACTION_EMOJIS, Limits

logger = logging.getLogger(__name__)


async def handle_callback(callback_query: dict):
    """Main callback dispatcher."""
    cb_id = callback_query.get("id", "")
    data = callback_query.get("data", "")
    user_tg = callback_query.get("from", {})
    user_id = user_tg.get("id")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type", "private")
    message_id = message.get("message_id")

    if not user_id or not chat_id or not data:
        await answer_callback_query(cb_id)
        return

    is_group = chat_type in ("group", "supergroup")

    # ── Group activation gate ──
    if is_group:
        existing_user = await get_user(user_id)
        if existing_user is None:
            settings = get_settings()
            bot_link = f"https://t.me/{settings.BOT_USERNAME}?start=from_group_{chat_id}"
            await answer_callback_query(
                cb_id,
                text="👆 Open the Bot to see more stories / 打开 Bot 看更多故事",
                show_alert=True,
            )
            await send_message(
                chat_id,
                f"👆 <a href=\"{bot_link}\">Open Blink.World</a> to browse more stories 🌍",
                reply_markup=inline_keyboard([[
                    inline_button("🚀 Open Blink.World", url=bot_link),
                ]]),
            )
            return

    user, _ = await get_or_create_user(user_id, user_tg.get("language_code"))
    lang = user.lang

    try:
        # ── Onboarding ──
        if data.startswith("set_country:"):
            from app.handlers.cb_settings import handle_set_country
            await handle_set_country(cb_id, chat_id, user_id, data, lang)
        elif data.startswith("set_lang:"):
            from app.handlers.cb_settings import handle_set_lang
            await handle_set_lang(cb_id, chat_id, user_id, data)

        # ── Reactions (Layer 1) ──
        elif data.startswith("react:"):
            await _handle_reaction(cb_id, chat_id, message_id, user_id, data, lang)

        # ── Swipe (Layer 3) ──
        elif data.startswith("swipe:"):
            await _handle_swipe(cb_id, chat_id, message_id, user_id, data, lang, is_group)

        # ── Favorite ──
        elif data.startswith("fav:"):
            if is_group:
                post_id = data.split(":", 1)[1] if ":" in data else ""
                from app.handlers.group_chat import handle_group_favorite
                await handle_group_favorite(cb_id, user_id, post_id, lang)
            else:
                await _handle_favorite(cb_id, user_id, data, lang)

        # ── Report ──
        elif data.startswith("report:"):
            await _handle_report(cb_id, chat_id, message_id, user_id, data, lang, is_group)

        # ── "我也说一个" → start publishing (private only; group uses URL button now) ──
        elif data.startswith("post_also"):
            await answer_callback_query(cb_id)
            # Extract channel_id if present: "post_also:3" → channel_id=3
            parts = data.split(":", 1)
            pre_channel_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            from app.handlers.cb_publishing import start_publish_flow
            await start_publish_flow(chat_id, user_id, user, lang, pre_channel_id=pre_channel_id)

        # ── Publishing flow ──
        elif data.startswith("chan:"):
            from app.handlers.cb_publishing import handle_channel_select
            await handle_channel_select(cb_id, chat_id, user_id, user, data, lang)
        elif data.startswith("pub:"):
            from app.handlers.cb_publishing import handle_publish_action
            await handle_publish_action(cb_id, chat_id, user_id, user, data, lang)

        # ── Admin review ──
        elif data.startswith("adm:"):
            from app.handlers.admin_review import handle_admin_callback
            await handle_admin_callback(cb_id, chat_id, user_id, data)

        # ── Profile sub-pages ──
        elif data.startswith("profile:"):
            from app.handlers.cb_profile import handle_profile
            await handle_profile(cb_id, chat_id, user_id, data, lang)

        # ── Settings ──
        elif data.startswith("settings:"):
            from app.handlers.cb_settings import handle_settings
            await handle_settings(cb_id, chat_id, message_id, user_id, user, data, lang)
        elif data.startswith("toggle_ch:"):
            from app.handlers.cb_settings import handle_toggle_channel
            await handle_toggle_channel(cb_id, chat_id, message_id, user_id, user, data, lang)

        # ── Group Topics (channel selector) ──
        elif data.startswith("gtopic:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                target_chat_id = int(parts[1])
                if parts[2] == "start":
                    await answer_callback_query(cb_id)
                    from app.handlers.group_chat import send_group_card
                    await send_message(
                        target_chat_id, "📖",
                        reply_markup=None,  # keyboard already set
                    )
                    await send_group_card(target_chat_id, lang)
                else:
                    ch_id = int(parts[2])
                    from app.handlers.group_chat import handle_group_topic_toggle
                    await handle_group_topic_toggle(cb_id, target_chat_id, message_id, ch_id, lang)
            else:
                await answer_callback_query(cb_id)

        else:
            logger.debug("Unknown callback_data: %s", data)
            await answer_callback_query(cb_id)

    except Exception as e:
        logger.error("Callback error data=%s: %s", data, e, exc_info=True)
        await answer_callback_query(cb_id)


# ══════════════════════════════════════════════
# Emoji Reactions (Layer 1) — core interaction, stays here
# ══════════════════════════════════════════════

async def _handle_reaction(cb_id: str, chat_id: int, message_id: int, user_id: int, data: str, lang: str):
    from app.models import LEGACY_REACTION_EMOJIS
    parts = data.split(":", 2)
    if len(parts) < 3:
        await answer_callback_query(cb_id)
        return

    post_id, emoji = parts[1], parts[2]

    # Accept both current and legacy emojis (old cached cards may send 🤗/❓)
    valid_emojis = set(REACTION_EMOJIS) | LEGACY_REACTION_EMOJIS
    if emoji not in valid_emojis:
        await answer_callback_query(cb_id)
        return

    existing = await get_user_reactions(user_id, post_id)
    if emoji in existing:
        await remove_reaction(user_id, post_id, emoji)
        await answer_callback_query(cb_id)
    else:
        added = await add_reaction(user_id, post_id, emoji)
        if not added:
            max_r = Limits.REACTIONS_PER_POST
            max_text = t("reaction_limit", lang, max=max_r)
            await answer_callback_query(cb_id, text=max_text, show_alert=False)
            return
        await answer_callback_query(cb_id)

    # Refresh keyboard with updated counts
    post = await get_post(post_id)
    if post and message_id:
        from app.handlers.card_builder import build_card_inline_keyboard, build_group_card_inline_keyboard
        ch_id = post.get("channel_id", 0)
        is_group_chat = chat_id < 0
        if is_group_chat:
            new_markup = build_group_card_inline_keyboard(post_id, channel_id=ch_id, reactions=post.get("reactions", {}), lang=lang)
        else:
            new_markup = build_card_inline_keyboard(post_id, channel_id=ch_id, reactions=post.get("reactions", {}), lang=lang)
        await edit_message_reply_markup(chat_id, message_id, reply_markup=new_markup)


# ══════════════════════════════════════════════
# Swipe (Layer 3) — thin delegation
# ══════════════════════════════════════════════

async def _handle_swipe(cb_id: str, chat_id: int, message_id: int, user_id: int, data: str, lang: str, is_group: bool):
    parts = data.split(":", 2)
    if len(parts) < 3:
        await answer_callback_query(cb_id)
        return

    post_id, action = parts[1], parts[2]

    if is_group:
        from app.handlers.group_chat import handle_group_swipe
        await handle_group_swipe(cb_id, chat_id, message_id, user_id, post_id, action, lang)
    else:
        await record_swipe(user_id, post_id, action)
        await answer_callback_query(cb_id)


# ══════════════════════════════════════════════
# Favorite
# ══════════════════════════════════════════════

async def _handle_favorite(cb_id: str, user_id: int, data: str, lang: str):
    post_id = data.split(":", 1)[1] if ":" in data else ""
    if not post_id:
        await answer_callback_query(cb_id)
        return

    is_fav = await toggle_favorite(user_id, post_id)
    text = t("favorited", lang) if is_fav else t("unfavorited", lang)
    await answer_callback_query(cb_id, text=text)


# ══════════════════════════════════════════════
# Report
# ══════════════════════════════════════════════

async def _handle_report(cb_id: str, chat_id: int, message_id: int, user_id: int, data: str, lang: str, is_group: bool):
    post_id = data.split(":", 1)[1] if ":" in data else ""
    if not post_id:
        await answer_callback_query(cb_id)
        return

    if is_group:
        from app.handlers.group_chat import handle_group_swipe
        await handle_group_swipe(cb_id, chat_id, message_id, user_id, post_id, "report", lang)
    else:
        await report_post(user_id, post_id)
        await answer_callback_query(cb_id, text=t("reported", lang))
