"""
Blink.World — Configuration
All secrets injected via environment variables. Defaults are empty strings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Telegram ──
    BOT_TOKEN: str = ""
    BOT_USERNAME: str = "BlinkWorldBot"
    WEBHOOK_HOST: str = ""  # e.g. https://blink-world.fly.dev
    WEBHOOK_SECRET: str = ""  # secret_token for webhook verification

    # ── Database ──
    DATABASE_URL: str = ""  # postgresql://user:pass@host:port/db
    DB_POOL_MIN: int = 5
    DB_POOL_MAX: int = 50

    # ── Redis ──
    REDIS_URL: str = ""  # redis://host:port/0

    # ── AI (OpenRouter) ──
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://openrouter.ai/api/v1"
    AI_MODEL: str = "openai/gpt-4o"
    AI_FALLBACK_MODEL: str = "openai/gpt-4o-mini"
    AI_DAILY_LIMIT: int = 10000
    AI_CONCURRENCY: int = 10
    AI_TIMEOUT_TRANSLATE: float = 25.0
    AI_TIMEOUT_GENERATE: float = 45.0
    AI_TIMEOUT_MODERATE: float = 15.0

    # ── Admin ──
    ADMIN_SECRET: str = ""  # empty = reject all admin requests
    ADMIN_USER_IDS: str = ""  # comma-separated Telegram user IDs, e.g. "123456,789012"

    # ── Image Generation ──
    IMAGE_GEN_PROVIDER: str = "openai"  # openai (DALL-E) or stability
    OPENAI_API_KEY: str = ""  # For DALL-E — can be same as AI_API_KEY if using OpenRouter
    STABILITY_API_KEY: str = ""  # For Stability AI
    IMAGE_GEN_ENABLED: bool = True

    # ── App ──
    APP_ENV: str = "production"  # development | staging | production
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def webhook_url(self) -> str:
        return f"{self.WEBHOOK_HOST}/webhook/telegram"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
