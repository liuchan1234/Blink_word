"""
Blink.World — Private Chat Router

Thin dispatcher: routes private messages to the appropriate sub-handler.
All business logic lives in dedicated modules:
  - onboarding.py  — /start, country selection, referral
  - browsing.py    — card browsing, like/dislike/fav/report
  - profile.py     — user profile, group invite, check-in, publishing

This file should stay under ~150 lines — if it grows, extract more.
"""

import logging

from app.services.user_service import get_or_create_user, update_user
from app.services.feed_service import get_current_post_id
from app.i18n import t
from app.telegram_helpers import send_message
from app.handlers.shared import main_menu_keyboard, browse_keyboard, show_settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Main Router
# ══════════════════════════════════════════════

async def handle_private_message(message: dict):
    """Route private messages by type and content."""
    user_tg = message.get("from", {})
    user_id = user_tg.get("id")
    chat_id = message.get("chat", {}).get("id")

    if not user_id or not chat_id:
        return

    text = message.get("text", "").strip()
    language_code = user_tg.get("language_code")

    # Get or create user
    user, is_new = await get_or_create_user(user_id, language_code)
    lang = user.lang

    # Fetch onboard_state from DB
    from app.services.user_service import get_onboard_state
    onboard_state = await get_onboard_state(user_id)

    # ── Handle onboarding states ──
    if onboard_state in ("typing_country", "choosing_country") and text and not text.startswith("/"):
        from app.handlers.onboarding import finish_country_input
        await finish_country_input(chat_id, user_id, text, lang)
        return

    # ── Handle publishing: waiting for content input ──
    if onboard_state == "writing_post":
        if _should_exit_writing(text, lang):
            await update_user(user_id, onboard_state="ready")
            from app.services.publish_service import clear_draft
            await clear_draft(user_id)
            # Fall through to normal button handling below
        else:
            photo = message.get("photo")
            if text and not text.startswith("/"):
                from app.handlers.profile import handle_content_input
                await handle_content_input(chat_id, user_id, user, text, None, lang)
                return
            elif photo:
                largest = photo[-1] if photo else None
                file_id = largest.get("file_id") if largest else None
                caption = message.get("caption", "").strip()
                from app.handlers.profile import handle_content_input
                await handle_content_input(chat_id, user_id, user, caption, file_id, lang)
                return

    # ── Commands ──
    if text.startswith("/start"):
        from app.handlers.onboarding import handle_start
        await handle_start(chat_id, user_id, text, user, is_new, language_code)
        return

    if text == "/help":
        await send_message(chat_id, t("welcome", lang), reply_markup=main_menu_keyboard(lang))
        return

    if text in ("/world", "/blink"):
        from app.handlers.browsing import start_browsing
        await start_browsing(chat_id, user_id, user, lang)
        return

    if text == "/checkin":
        from app.handlers.profile import handle_checkin
        await handle_checkin(chat_id, user_id, user, lang)
        return

    if text == "/settings":
        await show_settings(chat_id, user_id, user, lang)
        return

    if text.startswith("/admin"):
        from app.handlers.admin_review import handle_admin_command
        await handle_admin_command(chat_id, user_id, text)
        return

    # ── Reply keyboard: browsing actions ──
    if text in {"👍", t("browse_like_btn", lang)}:
        from app.handlers.browsing import handle_like
        await handle_like(chat_id, user_id, lang)
        return

    if text in {"👎", t("browse_next_btn", lang)}:
        from app.handlers.browsing import handle_dislike
        await handle_dislike(chat_id, user_id, lang)
        return

    if text in {t("browse_favorite_btn", lang)} or text.startswith("⭐"):
        from app.handlers.browsing import handle_fav
        await handle_fav(chat_id, user_id, lang)
        return

    if text in {t("browse_report_btn", lang)} or text.startswith("⚠️"):
        from app.handlers.browsing import handle_report_action
        await handle_report_action(chat_id, user_id, lang)
        return

    if text in {t("browse_back_btn", lang)}:
        await send_message(chat_id, t("welcome", lang), reply_markup=main_menu_keyboard(lang))
        return

    # ── Menu buttons ──
    menu_browse = t("menu_browse", lang)
    menu_post = t("menu_post", lang)
    menu_me = t("menu_me", lang)
    menu_settings = t("menu_settings", lang)
    menu_group = t("menu_group", lang)

    if text == menu_browse:
        from app.handlers.browsing import start_browsing
        await start_browsing(chat_id, user_id, user, lang)
        return

    if text == menu_post:
        from app.handlers.profile import start_publish
        await start_publish(chat_id, user_id, user, lang)
        return

    if text == menu_me:
        from app.handlers.profile import show_profile
        await show_profile(chat_id, user_id, user, lang)
        return

    if text == menu_settings:
        await show_settings(chat_id, user_id, user, lang)
        return

    if text == menu_group:
        from app.handlers.profile import show_group_invite
        await show_group_invite(chat_id, user_id, lang)
        return

    # ── Fallback ──
    current = await get_current_post_id(user_id)
    if current:
        await send_message(chat_id, "👆", reply_markup=browse_keyboard(lang))
    else:
        await send_message(chat_id, t("welcome", lang), reply_markup=main_menu_keyboard(lang))


def _should_exit_writing(text: str, lang: str) -> bool:
    """Check if the text is a menu/browse button that should cancel writing mode."""
    exit_texts = {
        t("menu_browse", lang), t("menu_post", lang),
        t("menu_me", lang), t("menu_settings", lang),
        t("menu_group", lang),
        t("browse_like_btn", lang), t("browse_next_btn", lang),
        t("browse_favorite_btn", lang), t("browse_report_btn", lang),
        t("browse_back_btn", lang),
    }
    return text in exit_texts
