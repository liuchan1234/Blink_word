"""
Blink.World — Publishing Flow Callbacks
Extracted from callbacks.py: channel selection, content preview, publish confirm/cancel.
"""

import logging

from app.telegram_helpers import (
    answer_callback_query, send_message, send_photo,
    inline_keyboard, inline_button,
)
from app.services.user_service import update_user
from app.services.publish_service import save_draft, get_draft, clear_draft, publish_draft
from app.i18n import t
from app.models import (
    CHANNELS, USER_CHANNEL_IDS,
    get_channel, get_channel_display,
)
from app.database import get_pool
from app.handlers.shared import main_menu_keyboard

logger = logging.getLogger(__name__)


async def start_publish_flow(chat_id: int, user_id: int, user, lang: str, pre_channel_id: int | None = None):
    """Show channel selection for publishing. If pre_channel_id is set, skip selection."""
    if pre_channel_id:
        ch = get_channel(pre_channel_id)
        if ch and ch.is_user_channel:
            # Auto-select this channel, go straight to content input
            draft = {
                "channel_id": pre_channel_id,
                "country": user.country if user.show_country else "",
                "lang": lang,
                "state": "waiting_content",
            }
            daily_topic = await _get_daily_topic(lang)
            if daily_topic:
                draft["daily_topic"] = daily_topic
            await save_draft(user_id, draft)

            channel_name = get_channel_display(pre_channel_id, lang)
            prompt = t("enter_content", lang)
            if daily_topic:
                prompt = t("daily_topic_hint", lang, topic=daily_topic) + "\n\n" + prompt
            await send_message(chat_id, f"{channel_name}\n\n{prompt}")
            await update_user(user_id, onboard_state="writing_post")
            return

    # No pre-selection or invalid channel → show channel picker
    rows = []
    for ch in CHANNELS:
        if not ch.is_user_channel:
            continue
        display = get_channel_display(ch.id, lang)
        rows.append([inline_button(display, f"chan:{ch.id}")])

    title = t("choose_channel", lang)
    await send_message(chat_id, title, reply_markup=inline_keyboard(rows))


async def handle_channel_select(cb_id: str, chat_id: int, user_id: int, user, data: str, lang: str):
    """User selected a channel → save to draft, ask for content."""
    try:
        channel_id = int(data.split(":", 1)[1])
    except (ValueError, IndexError):
        await answer_callback_query(cb_id)
        return

    ch = get_channel(channel_id)
    if not ch or not ch.is_user_channel:
        await answer_callback_query(cb_id, text="Invalid channel", show_alert=True)
        return

    # Save draft with channel selection
    draft = {
        "channel_id": channel_id,
        "country": user.country if user.show_country else "",
        "lang": lang,
        "state": "waiting_content",
    }

    # Check for daily topic
    daily_topic = await _get_daily_topic(lang)
    if daily_topic:
        draft["daily_topic"] = daily_topic

    await save_draft(user_id, draft)
    await answer_callback_query(cb_id)

    # Show content input prompt
    channel_name = get_channel_display(channel_id, lang)
    prompt = t("enter_content", lang)

    # If there's a daily topic, show it as hint
    if daily_topic:
        prompt = t("daily_topic_hint", lang, topic=daily_topic) + "\n\n" + prompt

    await send_message(chat_id, f"{channel_name}\n\n{prompt}")
    await update_user(user_id, onboard_state="writing_post")


async def handle_publish_action(cb_id: str, chat_id: int, user_id: int, user, data: str, lang: str):
    """Handle publish confirm / cancel / scope selection."""
    action = data.split(":", 1)[1] if ":" in data else ""

    if action == "confirm":
        draft = await get_draft(user_id)
        if not draft:
            await answer_callback_query(cb_id, text=t("error_generic", lang), show_alert=True)
            return

        post_id = await publish_draft(user_id, draft)
        await answer_callback_query(cb_id)

        if post_id == "daily_limit":
            await send_message(chat_id, t("daily_post_limit", lang))
            await update_user(user_id, onboard_state="ready")
            await send_message(chat_id, "👆", reply_markup=main_menu_keyboard(lang))
            return
        elif post_id:
            await send_message(chat_id, t("published_success", lang))
        else:
            await send_message(chat_id, t("error_generic", lang))

        await update_user(user_id, onboard_state="ready")
        await send_message(chat_id, "👆", reply_markup=main_menu_keyboard(lang))

    elif action == "cancel":
        await clear_draft(user_id)
        await answer_callback_query(cb_id, text=t("publish_cancelled", lang))
        await update_user(user_id, onboard_state="ready")
        await send_message(chat_id, t("publish_cancelled", lang), reply_markup=main_menu_keyboard(lang))

    elif action == "global":
        # Publish to global feed
        draft = await get_draft(user_id)
        if draft:
            draft["group_only"] = None
            await save_draft(user_id, draft)
        await _show_publish_preview(cb_id, chat_id, user_id, user, lang)

    elif action == "group":
        # Publish to group only (🔒)
        draft = await get_draft(user_id)
        if draft and draft.get("from_group_chat_id"):
            draft["group_only"] = draft["from_group_chat_id"]
            await save_draft(user_id, draft)
        await _show_publish_preview(cb_id, chat_id, user_id, user, lang)

    else:
        await answer_callback_query(cb_id)


async def _show_publish_preview(cb_id: str, chat_id: int, user_id: int, user, lang: str):
    """Show preview of the post before confirming."""
    await answer_callback_query(cb_id)
    draft = await get_draft(user_id)
    if not draft:
        await send_message(chat_id, t("error_generic", lang))
        return

    channel_name = get_channel_display(draft.get("channel_id", 0), lang)
    country = draft.get("country", "")
    content = draft.get("content", "")
    anonymous = t("anonymous", lang)

    # Build preview
    lines = [channel_name]
    if country:
        lines[0] += f" · 🌍 {country}"
    lines.append("")
    lines.append(content)
    lines.append("")
    lines.append(f"— {anonymous}")
    lines.append("")
    lines.append(t("preview_confirm", lang))

    preview_text = "\n".join(lines)

    keyboard = inline_keyboard([
        [
            inline_button(t("publish_confirm_btn", lang), "pub:confirm"),
            inline_button(t("publish_cancel_btn", lang), "pub:cancel"),
        ],
    ])

    photo = draft.get("photo_file_id")
    if photo:
        await send_photo(chat_id, photo=photo, caption=preview_text, reply_markup=keyboard)
    else:
        await send_message(chat_id, preview_text, reply_markup=keyboard)


async def _get_daily_topic(lang: str) -> str | None:
    """Get today's daily topic if available."""
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT question_zh, question_en FROM daily_topics WHERE topic_date = CURRENT_DATE"
            )
            if row:
                return row["question_zh"] if lang == "zh" else row["question_en"]
    except Exception:
        pass
    return None
