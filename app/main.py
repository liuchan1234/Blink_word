"""
Blink.World — FastAPI Entry Point

Lifespan:
  startup  → DB pool + migrations + Redis + webhook registration + bot commands
  shutdown → close all connections

Routes:
  /webhook/telegram  — Telegram webhook
  /health            — basic health check
  /health/detailed   — detailed health (admin only)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import init_db, close_db
from app.redis_client import init_redis, close_redis
from app.ai_client import close_ai_client
from app.telegram_helpers import set_webhook, set_my_commands, close_http

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()

    # ── Configure logging ──
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting Blink.World (env=%s)", settings.APP_ENV)

    # ── Initialize Database ──
    if settings.DATABASE_URL:
        await init_db(
            settings.DATABASE_URL,
            min_size=settings.DB_POOL_MIN,
            max_size=settings.DB_POOL_MAX,
        )
    else:
        logger.warning("DATABASE_URL not set — running without database")

    # ── Initialize Redis ──
    if settings.REDIS_URL:
        await init_redis(settings.REDIS_URL)
    else:
        logger.warning("REDIS_URL not set — running without Redis")

    # ── Register Webhook ──
    if settings.BOT_TOKEN and settings.WEBHOOK_HOST:
        success = await set_webhook(
            settings.webhook_url,
            secret_token=settings.WEBHOOK_SECRET or None,
        )
        if success:
            logger.info("Telegram webhook registered: %s", settings.webhook_url)
        else:
            logger.error("Failed to register Telegram webhook")

        # Set bot commands menu
        await set_my_commands([
            {"command": "start", "description": "开始 / Start"},
            {"command": "blink", "description": "群内刷故事 / Browse in group"},
            {"command": "checkin", "description": "每日签到 / Daily check-in"},
            {"command": "help", "description": "帮助 / Help"},
        ])
    else:
        logger.warning("BOT_TOKEN or WEBHOOK_HOST not set — webhook not registered")

    # ── Start Background Tasks ──
    from app.tasks import start_background_tasks, stop_background_tasks
    start_background_tasks()

    logger.info("Blink.World started successfully")

    yield  # ── App is running ──

    # ── Shutdown ──
    logger.info("Shutting down Blink.World...")
    stop_background_tasks()
    await close_ai_client()
    await close_http()
    await close_redis()
    await close_db()
    logger.info("Blink.World stopped")


# ── Create App ──

app = FastAPI(
    title="Blink.World",
    description="Anonymous real story platform on Telegram",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().is_dev else None,
    redoc_url=None,
)

# ── Register Routes ──
from app.routes.webhook import router as webhook_router
from app.routes.health import router as health_router

app.include_router(webhook_router)
app.include_router(health_router)
