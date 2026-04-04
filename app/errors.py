"""
Blink.World — Custom Error Classes

Structured errors with status codes, context, and user-facing messages.
All business-logic and infrastructure errors should use these classes
instead of bare Exception or generic raise.

Usage:
    raise AppError("GPT service unavailable", status_code=503, context={"user_id": uid})
    raise NotFoundError("Post not found", context={"post_id": pid})
    raise RateLimitError("Too many requests", context={"user_id": uid, "limit": 20})
"""


class AppError(Exception):
    """Base application error with status code and structured context."""

    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 500,
        context: dict | None = None,
        user_message: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.context = context or {}
        # user_message: safe to show to end users (no internals leaked)
        # Falls back to a generic message if not provided.
        self.user_message = user_message

    def __repr__(self):
        return f"{self.__class__.__name__}({self.message!r}, status={self.status_code}, ctx={self.context})"

    @property
    def message(self) -> str:
        return str(self.args[0]) if self.args else "An error occurred"


# ── Specific Error Types ──


class NotFoundError(AppError):
    """Resource not found (404)."""

    def __init__(self, message: str = "Not found", **kwargs):
        super().__init__(message, status_code=404, **kwargs)


class ValidationError(AppError):
    """Input validation failed (400)."""

    def __init__(self, message: str = "Invalid input", **kwargs):
        super().__init__(message, status_code=400, **kwargs)


class RateLimitError(AppError):
    """Rate limit exceeded (429)."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, status_code=429, **kwargs)


class QuotaExceededError(AppError):
    """User or system quota exceeded (429)."""

    def __init__(self, message: str = "Quota exceeded", **kwargs):
        super().__init__(message, status_code=429, **kwargs)


class ExternalServiceError(AppError):
    """External service (AI, Telegram API, etc.) failed (502/503)."""

    def __init__(self, message: str = "External service error", **kwargs):
        kwargs.setdefault("status_code", 503)
        super().__init__(message, **kwargs)


class DatabaseError(AppError):
    """Database operation failed (500)."""

    def __init__(self, message: str = "Database error", **kwargs):
        super().__init__(message, status_code=500, **kwargs)
