"""
Blink.World — Database layer (asyncpg)
Connection pool + idempotent migration runner.
"""

import os
import logging
import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db(database_url: str, min_size: int = 5, max_size: int = 50) -> asyncpg.Pool:
    """Create connection pool and run migrations."""
    global _pool
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
    )
    await _run_migrations(_pool)
    logger.info("Database initialized, pool size %d-%d", min_size, max_size)
    return _pool


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


async def _run_migrations(pool: asyncpg.Pool):
    """Run all SQL migration files in order. Each file must be idempotent."""
    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
    migrations_dir = os.path.abspath(migrations_dir)

    if not os.path.isdir(migrations_dir):
        logger.warning("Migrations directory not found: %s", migrations_dir)
        return

    files = sorted(
        f for f in os.listdir(migrations_dir)
        if f.endswith(".sql")
    )

    if not files:
        logger.info("No migration files found")
        return

    async with pool.acquire() as conn:
        for filename in files:
            filepath = os.path.join(migrations_dir, filename)
            sql = open(filepath, "r", encoding="utf-8").read()
            try:
                await conn.execute(sql)
                logger.info("Migration applied: %s", filename)
            except Exception as e:
                logger.error("Migration failed: %s — %s", filename, e)
                raise
