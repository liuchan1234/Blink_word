"""
Blink.World — Telegram Webhook Route
Thin dispatcher: validates secret, routes update types, returns fast.
All processing happens in background tasks.
"""

import asyncio
import logging

from fastapi import APIRouter, Request, Response, Header

from app.config import get_settings

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
    if settings.WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
            logger.warning("Webhook secret mismatch")
            return Response(status_code=403)

    body = await request.json()

    # ── Route by update type ──
    # Each handler is launched as a background task so we return immediately.
    try:
        if "callback_query" in body:
            asyncio.create_task(_safe_handle(handle_callback_query, body["callback_query"]))

        elif "message" in body:
            message = body["message"]
            asyncio.create_task(_safe_handle(handle_message, message))

        elif "message_reaction" in body:
            asyncio.create_task(_safe_handle(handle_message_reaction, body["message_reaction"]))

        elif "my_chat_member" in body:
            asyncio.create_task(_safe_handle(handle_chat_member_update, body["my_chat_member"]))

        else:
            logger.debug("Unhandled update type: %s", list(body.keys()))

    except Exception as e:
        logger.error("Webhook dispatch error: %s", e, exc_info=True)

    return {"ok": True}


async def _safe_handle(handler, data):
    """Wrap handler in try/except to prevent unhandled task exceptions."""
    try:
        await handler(data)
    except Exception as e:
        logger.error("Handler %s failed: %s", handler.__name__, e, exc_info=True)


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
