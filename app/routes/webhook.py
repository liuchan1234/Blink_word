"""
Blink.World — Telegram Webhook Route
Thin dispatcher: validates secret, routes update types, returns fast.
All processing happens in background tasks.
"""

import asyncio
import logging

from fastapi import APIRouter, Request, Response, Header

from app.config import get_settings
from app.request_context import set_request_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
):
    """
    Receive Telegram webhook updates.
    Must respond within 10 seconds. Heavy processing is fire-and-forget.
    """
    settings = get_settings()

    # ── Verify secret token ──
    if not settings.WEBHOOK_SECRET:
        logger.warning("Webhook rejected: WEBHOOK_SECRET not configured")
        return Response(status_code=403)
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        logger.warning("Webhook secret mismatch")
        return Response(status_code=403)

    body = await request.json()
    update_id = body.get("update_id", "")

    # ── Route by update type ──
    # Each handler is launched as a background task so we return immediately.
    try:
        if "callback_query" in body:
            asyncio.create_task(_safe_handle(handle_callback_query, body["callback_query"], update_id))

        elif "message" in body:
            message = body["message"]
            asyncio.create_task(_safe_handle(handle_message, message, update_id))

        elif "message_reaction" in body:
            asyncio.create_task(_safe_handle(handle_message_reaction, body["message_reaction"], update_id))

        elif "my_chat_member" in body:
            asyncio.create_task(_safe_handle(handle_chat_member_update, body["my_chat_member"], update_id))

        elif "inline_query" in body:
            asyncio.create_task(_safe_handle(handle_inline_query, body["inline_query"], update_id))

        else:
            logger.info("Unhandled update type: %s", list(body.keys()))

    except Exception as e:
        logger.error("Webhook dispatch error: %s", e, exc_info=True)

    return {"ok": True}


async def _safe_handle(handler, data, update_id=""):
    """Wrap handler in try/except with request_id context."""
    rid = set_request_id(update_id)
    try:
        await handler(data)
    except Exception as e:
        logger.error("Handler %s failed [req:%s]: %s", handler.__name__, rid, e, exc_info=True)


# ══════════════════════════════════════════════
# Message Handler
# ══════════════════════════════════════════════

async def handle_message(message: dict):
    """Route incoming messages by type and content."""
    from app.handlers.private_chat import handle_private_message
    from app.handlers.group_chat import handle_group_message

    chat = message.get("chat", {})
    chat_type = chat.get("type", "")

    if chat_type == "private":
        await handle_private_message(message)
    elif chat_type in ("group", "supergroup"):
        await handle_group_message(message)


# ══════════════════════════════════════════════
# Callback Query Handler
# ══════════════════════════════════════════════

async def handle_callback_query(callback_query: dict):
    """Route callback queries by data prefix."""
    from app.handlers.callbacks import handle_callback

    await handle_callback(callback_query)


# ══════════════════════════════════════════════
# Native Reaction Handler
# ══════════════════════════════════════════════

async def handle_message_reaction(reaction_update: dict):
    """Silently record Telegram native reactions."""
    from app.handlers.reactions import handle_native_reaction

    await handle_native_reaction(reaction_update)


# ══════════════════════════════════════════════
# Chat Member Update (bot added/removed from group)
# ══════════════════════════════════════════════

async def handle_chat_member_update(update: dict):
    """Handle bot being added to or removed from a group."""
    from app.handlers.group_chat import handle_bot_membership_change

    await handle_bot_membership_change(update)


# ══════════════════════════════════════════════
# Inline Query Handler (for native card sharing)
# ══════════════════════════════════════════════

async def handle_inline_query(inline_query: dict):
    """Handle inline queries for sharing cards natively."""
    from app.handlers.card_builder import build_card_text
    from app.services.post_service import get_post
    from app.services.translation_service import get_translated_content
    from app.services.user_service import get_user
    from app.telegram_helpers import api_call
    from app.config import get_settings
    from app.i18n import t

    query_text = inline_query.get("query", "").strip()
    inline_query_id = inline_query.get("id", "")
    user_id = inline_query.get("from", {}).get("id")

    if not query_text.startswith("share:"):
        await api_call("answerInlineQuery", inline_query_id=inline_query_id, results=[], cache_time=1)
        return

    post_id = query_text.replace("share:", "", 1).strip()
    if not post_id:
        await api_call("answerInlineQuery", inline_query_id=inline_query_id, results=[], cache_time=1)
        return

    post = await get_post(post_id)
    if not post:
        await api_call("answerInlineQuery", inline_query_id=inline_query_id, results=[], cache_time=1)
        return

    # Get user lang for translation
    lang = "en"
    if user_id:
        user = await get_user(user_id)
        if user:
            lang = user.lang

    # Translate content if needed
    translated = await get_translated_content(
        post_id=post_id,
        content=post.get("content", ""),
        original_lang=post.get("original_lang", "zh"),
        target_lang=lang,
    )

    # Build card text
    card_text = build_card_text(post, lang=lang, translated_content=translated)

    # Add invite footer with ref link
    settings = get_settings()
    if user_id:
        bot_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}"
    else:
        bot_link = f"https://t.me/{settings.BOT_USERNAME}"
    footer = t("share_card_footer", lang, bot_link=bot_link)
    full_text = card_text + footer

    # Build inline result
    from app.models import get_channel_display
    channel_name = get_channel_display(post.get("channel_id", 0), lang)

    results = [{
        "type": "article",
        "id": post_id,
        "title": channel_name,
        "description": (translated or post.get("content", ""))[:100],
        "input_message_content": {
            "message_text": full_text,
            "parse_mode": "HTML",
        },
    }]

    await api_call("answerInlineQuery", inline_query_id=inline_query_id, results=results, cache_time=300)
