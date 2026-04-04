"""
Blink.World — Onboarding Handler
Handles /start flow: language detection, country selection, referral processing.

Extracted from private_chat.py to keep each handler module focused on one concern.
"""

import logging

from app.config import get_settings
from app.services.user_service import get_or_create_user, update_user, get_user, add_points
from app.services.country_service import detect_country, get_country_display as fmt_country
from app.i18n import t, guess_country
from app.models import PointsConfig
from app.telegram_helpers import send_message, inline_keyboard, inline_button
from app.handlers.shared import main_menu_keyboard, country_quick_picks, show_settings

logger = logging.getLogger(__name__)


async def handle_start(chat_id: int, user_id: int, text: str, user, is_new: bool, language_code: str | None):
    """Handle /start with optional referral payload."""
    lang = user.lang

    # Parse payload
    payload = text.split(" ", 1)[1].strip() if " " in text else ""

    if payload.startswith("ref_"):
        try:
            inviter_id = int(payload[4:])
            if inviter_id != user_id and inviter_id > 0:
                await process_referral(inviter_id, user_id)
        except (ValueError, TypeError):
            pass

    # Share link: show the shared post first, then continue normally
    if payload.startswith("share_"):
        share_payload = payload.replace("share_", "", 1)
        # Parse optional ref: share_{post_id}_ref_{user_id}
        if "_ref_" in share_payload:
            shared_post_id, ref_part = share_payload.rsplit("_ref_", 1)
            try:
                inviter_id = int(ref_part)
                if inviter_id != user_id and inviter_id > 0:
                    await process_referral(inviter_id, user_id)
            except (ValueError, TypeError):
                pass
        else:
            shared_post_id = share_payload
        await _send_shared_post(chat_id, user_id, shared_post_id, lang)
        if not is_new:
            return  # Existing user: just show the post, done
        # New user: fall through to onboarding below

    # Write link: jumped from group "我也说一个" → start publishing with pre-selected channel
    if payload.startswith("write_") and not is_new:
        try:
            write_channel_id = int(payload.replace("write_", "", 1))
            from app.handlers.cb_publishing import start_publish_flow
            await start_publish_flow(chat_id, user_id, user, lang, pre_channel_id=write_channel_id)
            return
        except (ValueError, TypeError):
            pass

    # Settings deep link: jumped from group "设置" button
    if payload == "open_settings" and not is_new:
        await show_settings(chat_id, user_id, user, lang)
        return

    from_group = None
    if payload.startswith("from_group_"):
        try:
            from_group = int(payload.replace("from_group_", ""))
        except (ValueError, TypeError):
            pass

    from app.services.user_service import get_onboard_state
    onboard_state = await get_onboard_state(user_id)

    if is_new or onboard_state == "new":
        guessed = guess_country(language_code)
        await update_user(user_id, onboard_state="choosing_country")

        await send_message(chat_id, t("welcome", lang))

        await send_message(
            chat_id,
            t("onboard_country_hint", lang),
            reply_markup={"inline_keyboard": country_quick_picks(lang, guessed)},
        )
    else:
        await send_message(chat_id, t("welcome", lang), reply_markup=main_menu_keyboard(lang))

        if from_group:
            await send_message(chat_id, t("activated_back_to_group", lang))


async def finish_country_input(chat_id: int, user_id: int, country_text: str, lang: str):
    """Handle free-text country input — detect, normalize, confirm."""
    info = await detect_country(country_text)

    await update_user(user_id, country=info.name_zh, onboard_state="ready")

    display = f"{info.flag} {info.name_zh if lang == 'zh' else info.name_en}"
    await send_message(chat_id, t("country_set", lang, country=display))

    # Product intro + auto-send first card for new users
    await send_onboard_intro_and_first_card(chat_id, user_id, lang)


async def process_referral(inviter_id: int, invitee_id: int):
    """Process referral reward via service layer."""
    from app.services.user_service import process_referral as svc_process_referral
    success = await svc_process_referral(inviter_id, invitee_id)
    if success:
        inviter = await get_user(inviter_id)
        if inviter:
            try:
                await send_message(
                    inviter_id,
                    t("invite_success", inviter.lang, points=PointsConfig.INVITE_USER),
                )
            except Exception:
                pass


async def _send_shared_post(chat_id: int, user_id: int, post_id: str, lang: str):
    """Send a specific post that was shared via deep link."""
    from app.services.post_service import get_post
    from app.handlers.card_builder import build_card_inline_keyboard
    from app.handlers.card_sender import send_card

    post = await get_post(post_id)
    if not post:
        await send_message(chat_id, t("error_not_found", lang))
        return

    card_keyboard = build_card_inline_keyboard(
        post_id,
        channel_id=post.get("channel_id", 0),
        reactions=post.get("reactions", {}),
        include_post_button=True,
        include_swipe_buttons=False,
        lang=lang,
    )

    await send_card(chat_id, post, card_keyboard, lang)


async def send_onboard_intro_and_first_card(chat_id: int, user_id: int, lang: str):
    """Send product intro message + automatically push the first story card."""
    from app.handlers.card_builder import build_card_inline_keyboard
    from app.handlers.card_sender import send_card
    from app.handlers.browsing import send_next_card
    from app.services.user_service import get_user

    # Send the intro message with main menu keyboard
    await send_message(
        chat_id,
        t("onboard_intro", lang),
        reply_markup=main_menu_keyboard(lang),
    )

    # Auto-send the first card so the user immediately experiences the product
    user = await get_user(user_id)
    if user:
        await send_next_card(chat_id, user_id, user, lang)
