"""
Blink.World — Card Sender (shared)

Encapsulates the common "translate → build → send → track" pipeline
used by both private chat browsing and group chat browsing.

Callers provide the post dict and a keyboard builder; this module handles
translation, photo/pending-image dispatch, and message-to-post mapping.
"""

import logging

from app.telegram_helpers import send_message, send_photo
from app.services.translation_service import get_translated_content
from app.services.post_service import save_post_message
from app.handlers.card_builder import build_card_text
from app.handlers.shared import send_pending_image

logger = logging.getLogger(__name__)


async def send_card(
    chat_id: int,
    post: dict,
    keyboard: dict,
    lang: str,
) -> dict | None:
    """
    Translate, render, and send a story card to a chat.

    Args:
        chat_id:  Telegram chat to send to.
        post:     Post dict with id, content, original_lang, photo_file_id, etc.
        keyboard: Pre-built inline keyboard markup (caller decides private vs group style).
        lang:     Viewer's language code.

    Returns:
        Telegram API result dict, or None on failure.
    """
    post_id = post["id"]

    # ── Translate ──
    translated = await get_translated_content(
        post_id=post_id,
        content=post.get("content", ""),
        original_lang=post.get("original_lang", "zh"),
        target_lang=lang,
    )

    # ── Build text ──
    card_text = build_card_text(post, lang=lang, translated_content=translated)

    # ── Send (photo / pending-image / text) ──
    photo_file_id = post.get("photo_file_id")
    result = None

    if photo_file_id and photo_file_id.startswith("pending:"):
        result = await send_pending_image(
            chat_id, photo_file_id, card_text, keyboard, post_id,
        )
    elif photo_file_id:
        result = await send_photo(
            chat_id,
            photo=photo_file_id,
            caption=card_text,
            reply_markup=keyboard,
        )
    else:
        result = await send_message(
            chat_id,
            card_text,
            reply_markup=keyboard,
        )

    # ── Track message → post mapping ──
    if result and isinstance(result, dict):
        msg_id = result.get("message_id")
        if msg_id:
            await save_post_message(chat_id, msg_id, post_id)

    return result
