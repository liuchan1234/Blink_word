"""
Blink.World — Profile & Misc Private Chat Handlers
Handles: user profile display, group invite prompt, daily check-in, publish entry.

Extracted from private_chat.py for single-responsibility.
"""

import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.services.user_service import add_points, update_user
from app.services.country_service import get_country_display as fmt_country
from app.i18n import t
from app.models import PointsConfig, Limits, CHANNELS, get_channel_display
from app.telegram_helpers import send_message, send_photo, inline_keyboard, inline_button
from app.handlers.shared import main_menu_keyboard

logger = logging.getLogger(__name__)


async def show_profile(chat_id: int, user_id: int, user, lang: str):
    """Show user profile with stats."""
    settings = get_settings()

    stats = user.stats or {}
    invite_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}"

    country_display = fmt_country(user.country, lang) if user.country else t("country_not_set", lang)

    # Group invite deep link
    add_to_group_link = f"https://t.me/{settings.BOT_USERNAME}?startgroup=true"

    text = t("profile_header", lang,
             user_id=user_id,
             country=country_display,
             points=user.points,
             views=stats.get("views_total", 0),
             published=stats.get("published_total", 0),
             likes=stats.get("likes_received", 0),
             invited=stats.get("invited_count", 0),
             invite_link=invite_link,
             invite_points=PointsConfig.INVITE_USER)

    await send_message(chat_id, text, reply_markup=main_menu_keyboard(lang))

    sub_buttons = inline_keyboard([
        [inline_button(t("btn_my_stories", lang), "profile:stories")],
        [inline_button(t("btn_my_favorites", lang), "profile:favorites")],
        [inline_button(t("btn_add_to_group", lang), url=add_to_group_link)],
    ])
    await send_message(chat_id, "👇", reply_markup=sub_buttons)


async def show_group_invite(chat_id: int, user_id: int, lang: str):
    """Show group invite prompt with deep link button."""
    settings = get_settings()
    add_link = f"https://t.me/{settings.BOT_USERNAME}?startgroup=true"

    keyboard = inline_keyboard([
        [inline_button(t("btn_add_to_group", lang), url=add_link)],
    ])

    await send_message(
        chat_id,
        t("group_invite_onboarding", lang),
        reply_markup=keyboard,
    )


async def handle_checkin(chat_id: int, user_id: int, user, lang: str):
    """Handle /checkin — daily sign in for points."""
    now = datetime.now(timezone.utc)

    if user.last_checkin:
        last = user.last_checkin
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last.date() == now.date():
            await send_message(chat_id, t("checkin_already", lang), reply_markup=main_menu_keyboard(lang))
            return

    new_total = await add_points(user_id, PointsConfig.DAILY_CHECKIN, reason="checkin")
    await update_user(user_id, last_checkin=now)

    await send_message(
        chat_id,
        t("checkin_success", lang, points=PointsConfig.DAILY_CHECKIN, total=new_total),
        reply_markup=main_menu_keyboard(lang),
    )


async def start_publish(chat_id: int, user_id: int, user, lang: str):
    """Start the publishing flow: show channel selection."""
    rows = []
    for ch in CHANNELS:
        if not ch.is_user_channel:
            continue
        display = get_channel_display(ch.id, lang)
        rows.append([inline_button(display, f"chan:{ch.id}")])

    await send_message(chat_id, t("choose_channel", lang), reply_markup=inline_keyboard(rows))


async def handle_content_input(
    chat_id: int, user_id: int, user, text: str | None, photo_file_id: str | None, lang: str,
):
    """Handle user's content input during publishing flow."""
    from app.services.publish_service import get_draft, save_draft

    draft = await get_draft(user_id)
    if not draft:
        await send_message(chat_id, t("error_generic", lang), reply_markup=main_menu_keyboard(lang))
        await update_user(user_id, onboard_state="ready")
        return

    content = text or ""

    # Validate length (dynamic by language)
    from app.models import get_min_content_length
    min_len = get_min_content_length(lang)
    if len(content) < min_len:
        await send_message(chat_id, t("content_too_short", lang, min=min_len))
        return
    if len(content) > Limits.CONTENT_MAX_LENGTH:
        await send_message(chat_id, t("content_too_long", lang))
        return

    # Update draft with content
    draft["content"] = content
    if photo_file_id:
        draft["photo_file_id"] = photo_file_id
    draft["state"] = "preview"

    from_group = draft.get("from_group_chat_id")

    await save_draft(user_id, draft)

    # Build preview
    channel_name = get_channel_display(draft.get("channel_id", 0), lang)
    country = draft.get("country", "")
    anonymous = t("anonymous", lang)

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

    if from_group:
        keyboard = inline_keyboard([
            [
                inline_button(t("publish_to_world", lang), "pub:global"),
                inline_button(t("publish_to_group", lang), "pub:group"),
            ],
            [inline_button(t("publish_cancel_btn", lang), "pub:cancel")],
        ])
    else:
        keyboard = inline_keyboard([
            [
                inline_button(t("publish_confirm_btn", lang), "pub:confirm"),
                inline_button(t("publish_cancel_btn", lang), "pub:cancel"),
            ],
        ])

    if photo_file_id:
        await send_photo(chat_id, photo=photo_file_id, caption=preview_text, reply_markup=keyboard)
    else:
        await send_message(chat_id, preview_text, reply_markup=keyboard)
