"""
Blink.World — Database layer (asyncpg)
Connection pool + idempotent migration runner.
"""

import os
import asyncio
import logging
import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_MIGRATION_LOCK_KEY = 323323001


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
        # Use non-blocking lock to avoid deadlocks with CONCURRENTLY index build.
        # Followers wait until the runner releases the lock, then skip migrations.
        got_lock = await conn.fetchval("SELECT pg_try_advisory_lock($1)", _MIGRATION_LOCK_KEY)
        if not got_lock:
            logger.info("Another process is running migrations; waiting...")
            while True:
                await asyncio.sleep(0.5)
                can_probe = await conn.fetchval("SELECT pg_try_advisory_lock($1)", _MIGRATION_LOCK_KEY)
                if can_probe:
                    await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK_KEY)
                    logger.info("Migrations already completed by another process")
                    return

        try:
            for filename in files:
                filepath = os.path.join(migrations_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    sql = f.read()
                statements = _split_sql_statements(sql)
                try:
                    for stmt in statements:
                        await conn.execute(stmt)
                    logger.info("Migration applied: %s", filename)
                except Exception as e:
                    logger.error("Migration failed: %s — %s", filename, e)
                    raise
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK_KEY)


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split migration SQL into statements by ';'.
    Keep parser simple: migration files here are plain DDL without function bodies.
    """
    return [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
