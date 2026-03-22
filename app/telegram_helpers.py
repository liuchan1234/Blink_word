"""
Blink.World — Telegram Bot API helpers
All Telegram API calls are centralized here.
Webhook mode: we receive updates, and send responses via HTTP.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_http: httpx.AsyncClient | None = None


def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=30)
    return _http


async def close_http():
    global _http
    if _http and not _http.is_closed:
        await _http.aclose()
        _http = None


def _api_url(method: str) -> str:
    settings = get_settings()
    return f"https://api.telegram.org/bot{settings.BOT_TOKEN}/{method}"


async def api_call(method: str, **params) -> dict | None:
    """Generic Telegram Bot API call with error handling."""
    try:
        http = _get_http()
        # Separate files from JSON params
        files = params.pop("_files", None)
        # Remove None values
        cleaned = {k: v for k, v in params.items() if v is not None}

        if files:
            response = await http.post(_api_url(method), data=cleaned, files=files)
        else:
            response = await http.post(_api_url(method), json=cleaned)

        data = response.json()
        if not data.get("ok"):
            logger.error("Telegram API %s failed: %s", method, data.get("description"))
            return None
        return data.get("result")
    except Exception as e:
        logger.error("Telegram API %s exception: %s", method, e, exc_info=True)
        return None


# ── Message Sending ──

async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
    disable_notification: bool = False,
) -> dict | None:
    """Send a text message."""
    return await api_call(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
        disable_notification=disable_notification,
    )


async def send_photo(
    chat_id: int,
    photo: str,
    caption: str | None = None,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> dict | None:
    """Send a photo (file_id or URL)."""
    return await api_call(
        "sendPhoto",
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> dict | None:
    """Edit message text."""
    return await api_call(
        "editMessageText",
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def edit_message_reply_markup(
    chat_id: int,
    message_id: int,
    reply_markup: dict | None = None,
) -> dict | None:
    """Edit inline keyboard of a message."""
    return await api_call(
        "editMessageReplyMarkup",
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
    )


async def answer_callback_query(
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> dict | None:
    """Answer a callback query (dismiss loading spinner)."""
    return await api_call(
        "answerCallbackQuery",
        callback_query_id=callback_query_id,
        text=text,
        show_alert=show_alert,
    )


async def delete_message(chat_id: int, message_id: int) -> bool:
    """Delete a message. Returns True on success."""
    result = await api_call("deleteMessage", chat_id=chat_id, message_id=message_id)
    return result is not None


async def set_my_commands(commands: list[dict]) -> bool:
    """Set bot commands menu."""
    result = await api_call("setMyCommands", commands=commands)
    return result is not None


# ── Webhook Management ──

async def set_webhook(url: str, secret_token: str | None = None) -> bool:
    """Register webhook URL with Telegram."""
    result = await api_call(
        "setWebhook",
        url=url,
        secret_token=secret_token,
        allowed_updates=["message", "callback_query", "message_reaction", "my_chat_member"],
        drop_pending_updates=True,
    )
    if result is not None:
        logger.info("Webhook set: %s", url)
        return True
    return False


async def delete_webhook() -> bool:
    """Remove webhook."""
    result = await api_call("deleteWebhook", drop_pending_updates=True)
    return result is not None


# ── Keyboard Builders ──

def inline_keyboard(rows: list[list[dict]]) -> dict:
    """Build inline keyboard markup."""
    return {"inline_keyboard": rows}


def inline_button(text: str, callback_data: str | None = None, url: str | None = None) -> dict:
    """Build a single inline button. Either callback_data or url, not both."""
    btn = {"text": text}
    if url:
        btn["url"] = url
    elif callback_data:
        btn["callback_data"] = callback_data
    return btn


def reply_keyboard(rows: list[list[str]], resize: bool = True, persistent: bool = True) -> dict:
    """Build reply keyboard markup."""
    return {
        "keyboard": [[{"text": t} for t in row] for row in rows],
        "resize_keyboard": resize,
        "is_persistent": persistent,
        "one_time_keyboard": False,
    }


def remove_keyboard() -> dict:
    """Remove reply keyboard."""
    return {"remove_keyboard": True}
