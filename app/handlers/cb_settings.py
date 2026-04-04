"""
Blink.World — Settings Callbacks
Extracted from callbacks.py: language switch, country change, channel toggle, location toggle.
"""

import logging

from app.telegram_helpers import (
    answer_callback_query, send_message,
    edit_message_reply_markup,
    inline_keyboard, inline_button,
)
from app.services.user_service import update_user, get_user
from app.services.country_service import detect_country as detect_country_input
from app.i18n import t, SUPPORTED_LANGUAGES
from app.models import CHANNELS, ALL_CHANNEL_IDS, get_channel_display
from app.handlers.shared import (
    main_menu_keyboard,
    country_quick_picks,
    show_settings,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Country Selection (onboarding + settings)
# ══════════════════════════════════════════════

async def handle_set_country(cb_id: str, chat_id: int, user_id: int, data: str, lang: str):
    country_raw = data.split(":", 1)[1]

    # Use country service to normalize and get flag
    info = await detect_country_input(country_raw)

    # Check if this is first-time onboarding or a settings change
    from app.services.user_service import get_onboard_state
    was_onboarding = (await get_onboard_state(user_id)) in ("new", "choosing_country")

    await update_user(user_id, country=info.name_zh, onboard_state="ready")

    display = f"{info.flag} {info.name_zh if lang == 'zh' else info.name_en}"
    await answer_callback_query(cb_id, text=t("country_set", lang, country=display))

    if was_onboarding:
        # First-time user: show product intro + first card
        from app.handlers.onboarding import send_onboard_intro_and_first_card
        await send_onboard_intro_and_first_card(chat_id, user_id, lang)
    else:
        # Existing user changing country from settings
        await send_message(chat_id, t("setup_complete", lang), reply_markup=main_menu_keyboard(lang))


# ══════════════════════════════════════════════
# Language Switch
# ══════════════════════════════════════════════

async def handle_set_lang(cb_id: str, chat_id: int, user_id: int, data: str):
    new_lang = data.split(":", 1)[1]
    if new_lang not in SUPPORTED_LANGUAGES:
        new_lang = "en"

    await update_user(user_id, lang=new_lang)
    await answer_callback_query(cb_id, text=t("lang_changed", new_lang))

    await send_message(chat_id, t("welcome", new_lang), reply_markup=main_menu_keyboard(new_lang))


# ══════════════════════════════════════════════
# Settings Sub-actions
# ══════════════════════════════════════════════

async def handle_settings(cb_id: str, chat_id: int, message_id: int, user_id: int, user, data: str, lang: str):
    action = data.split(":", 1)[1] if ":" in data else ""

    if action == "country":
        await answer_callback_query(cb_id)
        await update_user(user_id, onboard_state="choosing_country")
        await send_message(
            chat_id, t("settings_choose_country", lang),
            reply_markup={"inline_keyboard": country_quick_picks(lang, user.country)},
        )
    elif action == "toggle_location":
        new_val = not user.show_country
        await update_user(user_id, show_country=new_val)
        status = "✅" if new_val else "❌"
        await answer_callback_query(cb_id, text=f"🌍 → {status}")
        refreshed = await get_user(user_id)
        if refreshed:
            await show_settings(chat_id, user_id, refreshed, lang)
    elif action == "channels":
        await answer_callback_query(cb_id)
        await _show_channel_settings(chat_id, user_id, user, lang)
    elif action == "channels_done":
        await answer_callback_query(cb_id)
        done_text = t("channel_settings_saved", lang)
        await send_message(chat_id, done_text, reply_markup=main_menu_keyboard(lang))
    else:
        await answer_callback_query(cb_id)


async def _show_channel_settings(chat_id: int, user_id: int, user, lang: str):
    prefs = set(user.channel_prefs) if user.channel_prefs else set(ALL_CHANNEL_IDS)
    title = t("channel_select_title", lang)

    rows = []
    for ch in CHANNELS:
        is_on = ch.id in prefs
        mark = "✅" if is_on else "⬜"
        name = get_channel_display(ch.id, lang)
        rows.append([inline_button(f"{mark} {name}", f"toggle_ch:{ch.id}")])

    rows.append([inline_button(t("channel_select_done", lang), "settings:channels_done")])
    await send_message(chat_id, title, reply_markup=inline_keyboard(rows))


async def handle_toggle_channel(cb_id: str, chat_id: int, message_id: int, user_id: int, user, data: str, lang: str):
    try:
        channel_id = int(data.split(":", 1)[1])
    except (ValueError, IndexError):
        await answer_callback_query(cb_id)
        return

    prefs = set(user.channel_prefs) if user.channel_prefs else set(ALL_CHANNEL_IDS)
    if channel_id in prefs:
        prefs.discard(channel_id)
    else:
        prefs.add(channel_id)

    if not prefs:
        await answer_callback_query(cb_id, text=t("channel_select_min", lang))
        return

    await update_user(user_id, channel_prefs=sorted(prefs))
    await answer_callback_query(cb_id)

    # Refresh inline keyboard
    rows = []
    for ch in CHANNELS:
        is_on = ch.id in prefs
        mark = "✅" if is_on else "⬜"
        name = get_channel_display(ch.id, lang)
        rows.append([inline_button(f"{mark} {name}", f"toggle_ch:{ch.id}")])

    rows.append([inline_button(t("channel_select_done", lang), "settings:channels_done")])
    await edit_message_reply_markup(chat_id, message_id, reply_markup=inline_keyboard(rows))
