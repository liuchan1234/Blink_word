"""
Blink.World — FastAPI Entry Point

Lifespan:
  startup  → DB pool + migrations + Redis + webhook registration + bot commands
  shutdown → close all connections

Routes:
  /webhook/telegram  — Telegram webhook
  /health            — basic health check
  /health/detailed   — detailed health (admin only)
  /admin             — developer HTML console (HTTP Basic, password=ADMIN_SECRET)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import init_db, close_db, get_pool
from app.redis_client import init_redis, close_redis
from app.ai_client import close_ai_client
from app.telegram_helpers import set_webhook, set_my_commands, close_http

logger = logging.getLogger(__name__)
_STARTUP_OWNER_LOCK_KEY = 323323777


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()

    # ── Configure logging ──
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s [req:%(request_id)s]",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Inject request_id into all log records
    from app.request_context import RequestIdFilter
    for handler in logging.root.handlers:
        handler.addFilter(RequestIdFilter())

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

    # Only one worker should perform startup side effects (webhook/tasks).
    startup_owner_conn = None
    is_startup_owner = False
    if settings.DATABASE_URL:
        pool = get_pool()
        startup_owner_conn = await pool.acquire()
        is_startup_owner = await startup_owner_conn.fetchval(
            "SELECT pg_try_advisory_lock($1)", _STARTUP_OWNER_LOCK_KEY
        )
        if not is_startup_owner:
            await pool.release(startup_owner_conn)
            startup_owner_conn = None

    # ── Register Webhook + Start background tasks (owner only) ──
    from app.tasks import start_background_tasks, stop_background_tasks

    if is_startup_owner:
        if settings.BOT_TOKEN and settings.WEBHOOK_HOST:
            success = await set_webhook(
                settings.webhook_url,
                secret_token=settings.WEBHOOK_SECRET or None,
            )
            if success:
                logger.info("Telegram webhook registered: %s", settings.webhook_url)
            else:
                logger.error("Failed to register Telegram webhook")

            # Private chat: full command menu
            await set_my_commands([
                {"command": "start", "description": "开始 / Start"},
                {"command": "world", "description": "刷故事 / Browse stories"},
                {"command": "checkin", "description": "每日签到 / Daily check-in"},
                {"command": "settings", "description": "设置 / Settings"},
                {"command": "help", "description": "帮助 / Help"},
            ], scope={"type": "all_private_chats"})

            # Groups: /world + /bye
            await set_my_commands([
                {"command": "world", "description": "群内刷故事 / Browse in group"},
                {"command": "bye", "description": "收起按键 / Hide buttons"},
            ], scope={"type": "all_group_chats"})
        else:
            logger.warning("BOT_TOKEN or WEBHOOK_HOST not set — webhook not registered")

        start_background_tasks()
    else:
        logger.info("Startup side effects are handled by another worker")

    logger.info("Blink.World started successfully")

    yield  # ── App is running ──

    # ── Shutdown ──
    logger.info("Shutting down Blink.World...")
    if is_startup_owner:
        stop_background_tasks()
    if startup_owner_conn is not None:
        try:
            await startup_owner_conn.execute("SELECT pg_advisory_unlock($1)", _STARTUP_OWNER_LOCK_KEY)
        finally:
            await get_pool().release(startup_owner_conn)
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
from app.routes.admin_ui import router as admin_ui_router

app.include_router(webhook_router)
app.include_router(health_router)
app.include_router(admin_ui_router)


# ── Global Exception Handler ──
from fastapi import Request
from fastapi.responses import JSONResponse
from app.errors import AppError


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Handle structured AppError with context logging."""
    logger.warning(
        "AppError on %s: %s (status=%d, context=%s)",
        request.url.path, exc.message, exc.status_code, exc.context,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "detail": exc.user_message or "Something went wrong",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "Something went wrong"},
    )
