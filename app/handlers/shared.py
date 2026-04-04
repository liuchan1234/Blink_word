"""
Blink.World — Shared Handler Utilities
Functions used across multiple handlers, extracted to break circular imports.

Previously these lived in private_chat.py or callbacks.py and were imported
via delayed `from app.handlers.private_chat import ...` calls. Centralizing
them here eliminates all 18 lazy imports.
"""

from app.i18n import t, LANGUAGE_NAMES
from app.telegram_helpers import reply_keyboard, inline_keyboard, inline_button, send_message
from app.models import CHANNELS, get_channel_display, ALL_CHANNEL_IDS
from app.services.user_service import get_user, update_user


# ══════════════════════════════════════════════
# Reply Keyboards (used by private_chat + callbacks)
# ══════════════════════════════════════════════

def main_menu_keyboard(lang: str) -> dict:
    """Build the main menu reply keyboard (3 rows)."""
    return reply_keyboard([
        [t("menu_browse", lang), t("menu_post", lang)],
        [t("menu_me", lang), t("menu_settings", lang)],
        [t("menu_group", lang)],
    ])


def browse_keyboard(lang: str) -> dict:
    """Reply keyboard during private chat browsing mode (Layer 3)."""
    from app.handlers.card_builder import build_private_browse_keyboard
    return build_private_browse_keyboard(lang)


def group_browse_keyboard(lang: str) -> dict:
    """Reply keyboard during group browsing mode (Layer 3, with Topics button)."""
    from app.handlers.card_builder import build_group_browse_keyboard
    return build_group_browse_keyboard(lang)


# ══════════════════════════════════════════════
# Country Quick Picks (used by private_chat + cb_settings)
# ══════════════════════════════════════════════

def country_quick_picks(lang: str, highlighted: str = "") -> list[list[dict]]:
    """Build popular country quick-pick inline keyboard. User can also type freely."""
    picks = [
        ("🇨🇳", "中国", "China"),
        ("🇺🇸", "美国", "United States"),
        ("🇯🇵", "日本", "Japan"),
        ("🇰🇷", "韩国", "South Korea"),
        ("🇬🇧", "英国", "UK"),
        ("🇷🇺", "俄罗斯", "Russia"),
        ("🇩🇪", "德国", "Germany"),
        ("🇫🇷", "法国", "France"),
        ("🇧🇷", "巴西", "Brazil"),
        ("🇮🇳", "印度", "India"),
        ("🇸🇬", "新加坡", "Singapore"),
        ("🇲🇾", "马来西亚", "Malaysia"),
        ("🇹🇭", "泰国", "Thailand"),
        ("🇻🇳", "越南", "Vietnam"),
        ("🇮🇩", "印尼", "Indonesia"),
        ("🇨🇦", "加拿大", "Canada"),
        ("🇦🇺", "澳大利亚", "Australia"),
        ("🇪🇸", "西班牙", "Spain"),
    ]

    rows = []
    row = []
    for flag, name_zh, name_en in picks:
        name = name_zh if lang == "zh" else name_en
        marker = " ✓" if name_zh == highlighted or name_en == highlighted else ""
        btn = {"text": f"{flag} {name}{marker}", "callback_data": f"set_country:{name_zh}"}
        row.append(btn)
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return rows


# ══════════════════════════════════════════════
# Settings Page (used by private_chat + cb_settings)
# ══════════════════════════════════════════════

async def show_settings(chat_id: int, user_id: int, user, lang: str):
    """Show settings menu with inline buttons."""
    from app.services.country_service import get_country_display as fmt_country

    country_display = fmt_country(user.country, lang) if user.country else t("country_not_set", lang)
    lang_display = LANGUAGE_NAMES.get(user.lang, user.lang)
    location_display = "✅" if user.show_country else "❌"

    text = t("settings_header", lang,
             lang_name=lang_display, country=country_display,
             location=location_display)

    # Language selector: show all available languages
    lang_buttons = []
    for lcode, lname in LANGUAGE_NAMES.items():
        if lcode == lang:
            lang_buttons.append(inline_button(f"✅ {lname}", f"set_lang:{lcode}"))
        else:
            lang_buttons.append(inline_button(lname, f"set_lang:{lcode}"))

    # Split into rows of 3
    lang_rows = [lang_buttons[i:i+3] for i in range(0, len(lang_buttons), 3)]

    keyboard = inline_keyboard([
        *lang_rows,
        [inline_button(t("settings_country", lang) + " ✏️", "settings:country")],
        [inline_button(t("settings_show_country", lang) + f" {location_display}", "settings:toggle_location")],
        [inline_button(t("settings_channels", lang), "settings:channels")],
    ])

    await send_message(chat_id, text, reply_markup=keyboard)


# ══════════════════════════════════════════════
# Pending Image Upload (used by private_chat + group_chat)
# ══════════════════════════════════════════════

async def send_pending_image(
    chat_id: int,
    pending_key: str,
    caption: str,
    reply_markup: dict,
    post_id: str,
) -> dict | None:
    """
    Upload a pending image from Redis and send it.
    On success, update the post's photo_file_id with the real Telegram file_id.
    """
    import logging
    logger = logging.getLogger(__name__)

    redis_key = pending_key.replace("pending:", "", 1)
    try:
        from app.redis_client import get_redis_binary
        r = get_redis_binary()
        img_bytes = await r.get(redis_key)

        if not img_bytes:
            return await send_message(chat_id, caption, reply_markup=reply_markup)

        from app.services.image_service import send_photo_bytes
        result = await send_photo_bytes(chat_id, img_bytes, caption=caption, reply_markup=reply_markup)

        if result and result.get("photo_file_id"):
            from app.services.post_service import update_post_photo
            await update_post_photo(post_id, result["photo_file_id"])
            await r.delete(redis_key)

        return result
    except Exception as e:
        logger.warning("Pending image send failed for %s: %s", pending_key, e)
        return await send_message(chat_id, caption, reply_markup=reply_markup)
