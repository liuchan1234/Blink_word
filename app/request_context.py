"""
Blink.World — Request Context

Uses Python contextvars to propagate request_id through the async call chain
without changing any function signatures. All loggers automatically include
the request_id via the custom log filter.

Usage:
    # At webhook entry point:
    set_request_id(update_id)

    # In any log call (automatic via filter):
    logger.info("something happened")  # → "something happened [req:abc123]"

    # To read current request_id:
    rid = get_request_id()
"""

import uuid
import logging
from contextvars import ContextVar

# ── Context Variable ──

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(update_id: int | str | None = None) -> str:
    """
    Set a new request_id for the current async context.
    If update_id is provided, uses it as prefix for traceability to Telegram.
    Returns the generated request_id.
    """
    short = uuid.uuid4().hex[:8]
    rid = f"{update_id}-{short}" if update_id else short
    _request_id_var.set(rid)
    return rid


def get_request_id() -> str:
    """Get the current request_id (empty string if not set)."""
    return _request_id_var.get()


# ── Log Filter ──

class RequestIdFilter(logging.Filter):
    """Injects request_id into every log record for structured output."""

    def filter(self, record):
        record.request_id = _request_id_var.get()
        return True
