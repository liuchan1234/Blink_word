"""
Blink.World — Health Check & Admin Routes
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, Response

from app.config import get_settings
from app.database import get_pool
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health():
    """Basic health check: DB + Redis connectivity."""
    status = {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    errors = []

    # Check DB
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as e:
        errors.append(f"db: {e}")

    # Check Redis
    try:
        r = get_redis()
        await r.ping()
    except Exception as e:
        errors.append(f"redis: {e}")

    if errors:
        status["status"] = "degraded"
        status["errors"] = errors
        # Return 200 even if degraded, as long as app is running
        return status

    return status


@router.get("/health/detailed")
async def health_detailed(x_admin_secret: str | None = Header(None)):
    """Detailed health with pool stats. Requires admin secret."""
    settings = get_settings()

    if not settings.ADMIN_SECRET or x_admin_secret != settings.ADMIN_SECRET:
        return Response(status_code=403)

    result = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        pool = get_pool()
        result["db"] = {
            "pool_size": pool.get_size(),
            "pool_free": pool.get_idle_size(),
            "pool_min": pool.get_min_size(),
            "pool_max": pool.get_max_size(),
        }
        async with pool.acquire() as conn:
            counts = {}
            # Tables are hardcoded whitelist — safe, but use explicit queries
            counts["users"] = await conn.fetchval("SELECT COUNT(*) FROM users")
            counts["posts"] = await conn.fetchval("SELECT COUNT(*) FROM posts")
            counts["post_reactions"] = await conn.fetchval("SELECT COUNT(*) FROM post_reactions")
            counts["groups"] = await conn.fetchval("SELECT COUNT(*) FROM groups")
            result["db"]["counts"] = counts
    except Exception as e:
        result["db"] = {"error": str(e)}

    try:
        r = get_redis()
        info = await r.info("memory")
        result["redis"] = {
            "used_memory_human": info.get("used_memory_human", "?"),
            "connected_clients": info.get("connected_clients", "?"),
        }
    except Exception as e:
        result["redis"] = {"error": str(e)}

    return result
