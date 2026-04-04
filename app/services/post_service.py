"""
Blink.World — Post Service
Database operations for post management, reactions, swipes, favorites, reports.
"""

import json
import uuid
import logging
from datetime import datetime, timezone

from app.database import get_pool
from app.redis_client import set_is_member, set_add, cache_get, cache_set
from app.models import Limits

logger = logging.getLogger(__name__)


# ── Post CRUD ──

async def create_post(
    channel_id: int,
    content: str,
    original_lang: str = "zh",
    source: str = "ugc",
    author_id: int | None = None,
    country: str = "",
    photo_file_id: str | None = None,
    group_only: int | None = None,
) -> str:
    """Create a new post. Returns post_id."""
    post_id = str(uuid.uuid4())[:12]  # Short UUID for callback_data (64 byte limit)
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO posts (id, channel_id, country, content, photo_file_id,
                               original_lang, source, author_id, group_only)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            post_id, channel_id, country, content, photo_file_id,
            original_lang, source, author_id, group_only,
        )

    logger.info("Post created: %s (channel=%d, source=%s, author=%s)",
                post_id, channel_id, source, author_id)
    return post_id


async def get_post(post_id: str) -> dict | None:
    """Get a single post by ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM posts WHERE id = $1", post_id)
        if row is None:
            return None
        return _row_to_dict(row)


async def get_feed_posts(
    channel_ids: list[int],
    exclude_post_ids: set[str],
    viewer_country: str = "",
    viewer_lang: str = "zh",
    pool_type: str = "global",
    limit: int = 20,
    group_only_chat_id: int | None = None,
) -> list[dict]:
    """
    Fetch candidate posts for recommendation.
    pool_type: "local" (same country/lang) or "global" (all)
    """
    pool = get_pool()

    conditions = ["p.is_active = TRUE"]
    params = []
    idx = 1

    # Channel filter
    conditions.append(f"p.channel_id = ANY(${idx})")
    params.append(channel_ids)
    idx += 1

    # Global vs group-only
    if group_only_chat_id:
        conditions.append(f"p.group_only = ${idx}")
        params.append(group_only_chat_id)
        idx += 1
    else:
        conditions.append("p.group_only IS NULL")

    # Local pool: filter by country or language
    if pool_type == "local" and viewer_country:
        conditions.append(f"(p.country = ${idx} OR p.original_lang = ${idx + 1})")
        params.append(viewer_country)
        params.append(viewer_lang)
        idx += 2

    # Report rate filter: skip heavily reported posts
    from app.models import Limits
    conditions.append(
        f"(p.view_count < ${idx} "
        f"OR p.report_count::float / GREATEST(p.view_count, 1) <= ${idx + 1})"
    )
    params.append(Limits.REPORT_MIN_VIEWS)
    params.append(Limits.REPORT_DEMOTE_RATE)
    idx += 2

    # Exclude already-viewed posts in SQL to avoid fixed-window blind spots
    if exclude_post_ids:
        conditions.append(f"p.id != ALL(${idx})")
        params.append(list(exclude_post_ids))
        idx += 1

    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT * FROM posts p
            WHERE {where}
            ORDER BY RANDOM()
            LIMIT ${idx}
            """,
            *params, limit,
        )

    return [_row_to_dict(row) for row in rows]


# ── Reactions ──

async def add_reaction(user_id: int, post_id: str, emoji: str) -> bool:
    """
    Add an emoji reaction. Users can have up to 3 per post.
    Returns True if added, False if already at limit or duplicate.
    Uses atomic CTE to prevent race condition on the 3-reaction limit.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            # Atomic: only INSERT if user has < N reactions on this post
            inserted = await conn.fetchval(
                """
                WITH current_count AS (
                    SELECT COUNT(*) as cnt
                    FROM post_reactions
                    WHERE user_id = $1 AND post_id = $2
                ),
                inserted AS (
                    INSERT INTO post_reactions (user_id, post_id, emoji)
                    SELECT $1, $2, $3
                    WHERE (SELECT cnt FROM current_count) < $4
                    ON CONFLICT (user_id, post_id, emoji) DO NOTHING
                    RETURNING 1
                )
                SELECT COUNT(*) FROM inserted
                """,
                user_id, post_id, emoji, Limits.REACTIONS_PER_POST,
            )

            if not inserted or inserted == 0:
                return False  # At limit or duplicate

            # Update post reactions JSONB
            await conn.execute(
                """
                UPDATE posts
                SET reactions = jsonb_set(
                    reactions,
                    $2,
                    (COALESCE((reactions->>$3)::int, 0) + 1)::text::jsonb
                )
                WHERE id = $1
                """,
                post_id, [emoji], emoji,
            )

            # Fire-and-forget: milestone check + hot pre-translate
            author_id = await conn.fetchval(
                "SELECT author_id FROM posts WHERE id = $1", post_id,
            )
            if author_id:
                import asyncio
                from app.services.milestone_service import check_milestones
                from app.services.translation_service import check_hot_post_for_pretranslate
                asyncio.create_task(_safe_task(check_milestones(post_id, author_id)))
                asyncio.create_task(_safe_task(check_hot_post_for_pretranslate(post_id)))

            return True
        except Exception as e:
            logger.warning("add_reaction failed: %s", e)
            return False


async def remove_reaction(user_id: int, post_id: str, emoji: str) -> bool:
    """Remove an emoji reaction."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM post_reactions WHERE user_id = $1 AND post_id = $2 AND emoji = $3",
            user_id, post_id, emoji,
        )
        if "DELETE 1" in result:
            await conn.execute(
                """
                UPDATE posts
                SET reactions = jsonb_set(
                    reactions,
                    $2,
                    (GREATEST(COALESCE((reactions->>$3)::int, 0) - 1, 0))::text::jsonb
                )
                WHERE id = $1
                """,
                post_id, [emoji], emoji,
            )
            return True
        return False


async def get_user_reactions(user_id: int, post_id: str) -> list[str]:
    """Get list of emojis this user has reacted with on this post."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT emoji FROM post_reactions WHERE user_id = $1 AND post_id = $2",
            user_id, post_id,
        )
        return [row["emoji"] for row in rows]


# ── Swipes (Like / Dislike) ──

async def record_swipe(user_id: int, post_id: str, action: str) -> bool:
    """Record a like or dislike. Returns True if newly recorded."""
    if action not in ("like", "dislike"):
        return False

    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            # Atomic: INSERT + increment in one statement using CTE
            # Only increments counter if the INSERT actually inserted a row
            result = await conn.fetchval(
                """
                WITH inserted AS (
                    INSERT INTO post_swipes (user_id, post_id, action)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, post_id) DO NOTHING
                    RETURNING 1
                )
                SELECT COUNT(*) FROM inserted
                """,
                user_id, post_id, action,
            )

            if not result or result == 0:
                return False  # Duplicate swipe, don't increment

            # Now safe to increment — we know the INSERT succeeded
            if action == "like":
                await conn.execute(
                    "UPDATE posts SET like_count = like_count + 1 WHERE id = $1",
                    post_id,
                )
            else:
                await conn.execute(
                    "UPDATE posts SET dislike_count = dislike_count + 1 WHERE id = $1",
                    post_id,
                )

            # Fire-and-forget: milestone check + author stat
            if action == "like":
                author_id = await conn.fetchval(
                    "SELECT author_id FROM posts WHERE id = $1", post_id,
                )
                if author_id:
                    import asyncio
                    from app.services.milestone_service import check_milestones
                    asyncio.create_task(_safe_task(check_milestones(post_id, author_id)))

                    from app.services.user_service import increment_stat
                    asyncio.create_task(_safe_task(increment_stat(author_id, "likes_received")))

            return True
        except Exception as e:
            logger.warning("record_swipe failed: %s", e)
            return False


# ── Favorites ──

async def toggle_favorite(user_id: int, post_id: str) -> bool:
    """Toggle favorite. Returns True if favorited, False if unfavorited.
    Uses transaction for atomicity to prevent counter drift on concurrent clicks."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Try to delete first. If deleted, it was a toggle-off.
            deleted = await conn.fetchval(
                """
                WITH removed AS (
                    DELETE FROM post_favorites
                    WHERE user_id = $1 AND post_id = $2
                    RETURNING 1
                )
                SELECT COUNT(*) FROM removed
                """,
                user_id, post_id,
            )
            if deleted and deleted > 0:
                await conn.execute(
                    "UPDATE posts SET favorite_count = GREATEST(favorite_count - 1, 0) WHERE id = $1",
                    post_id,
                )
                return False
            else:
                # Not currently favorited → insert, check it actually inserted
                inserted = await conn.fetchval(
                    """
                    WITH new_fav AS (
                        INSERT INTO post_favorites (user_id, post_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                        RETURNING 1
                    )
                    SELECT COUNT(*) FROM new_fav
                    """,
                    user_id, post_id,
                )
                if inserted and inserted > 0:
                    await conn.execute(
                        "UPDATE posts SET favorite_count = favorite_count + 1 WHERE id = $1",
                        post_id,
                    )
                return True


# ── Reports ──

async def report_post(user_id: int, post_id: str) -> bool:
    """Report a post. Returns True if newly reported."""
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            # Atomic: only increment if INSERT actually inserted a row
            inserted = await conn.fetchval(
                """
                WITH new_report AS (
                    INSERT INTO post_reports (user_id, post_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                    RETURNING 1
                )
                SELECT COUNT(*) FROM new_report
                """,
                user_id, post_id,
            )

            if not inserted or inserted == 0:
                return False  # Duplicate report, don't increment

            await conn.execute(
                "UPDATE posts SET report_count = report_count + 1 WHERE id = $1",
                post_id,
            )
            # Check auto-remove thresholds
            row = await conn.fetchrow(
                "SELECT report_count, view_count FROM posts WHERE id = $1",
                post_id,
            )
            if row and row["view_count"] >= Limits.REPORT_MIN_VIEWS:
                rate = row["report_count"] / row["view_count"]
                if rate > Limits.REPORT_REMOVE_RATE:
                    await conn.execute(
                        "UPDATE posts SET is_active = FALSE WHERE id = $1",
                        post_id,
                    )
                    logger.warning("Post %s auto-removed: report rate %.1f%%",
                                   post_id, rate * 100)
            return True
        except Exception as e:
            logger.warning("report_post failed: %s", e)
            return False


# ── View Count ──

async def increment_view(post_id: str):
    """Increment post view count."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET view_count = view_count + 1 WHERE id = $1",
            post_id,
        )


# ── Post-Message Mapping ──

async def save_post_message(chat_id: int, message_id: int, post_id: str):
    """Save mapping of Telegram message to post."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO post_messages (chat_id, message_id, post_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (chat_id, message_id) DO UPDATE SET post_id = $3
            """,
            chat_id, message_id, post_id,
        )


async def get_post_by_message(chat_id: int, message_id: int) -> str | None:
    """Get post_id from a Telegram message."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT post_id FROM post_messages WHERE chat_id = $1 AND message_id = $2",
            chat_id, message_id,
        )


# ── Helpers ──

def _row_to_dict(row) -> dict:
    """Convert asyncpg Record to dict."""
    d = dict(row)
    if isinstance(d.get("reactions"), str):
        d["reactions"] = json.loads(d["reactions"])
    return d


async def _safe_task(coro):
    """Wrap a coroutine in try/except for fire-and-forget tasks."""
    try:
        await coro
    except Exception as e:
        logger.error("Background task failed: %s", e, exc_info=True)


# ── Functions extracted from handlers (keeping SQL in service layer) ──

async def update_post_photo(post_id: str, photo_file_id: str):
    """Update a post's photo_file_id (e.g., after deferred upload)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE posts SET photo_file_id = $1 WHERE id = $2",
            photo_file_id, post_id,
        )


async def save_native_reaction(post_id: str, message_id: int, chat_id: int, emoji: str):
    """Record a Telegram native reaction."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO native_reactions (post_id, message_id, chat_id, emoji, count, updated_at)
            VALUES ($1, $2, $3, $4, 1, NOW())
            ON CONFLICT (post_id, emoji)
            DO UPDATE SET count = native_reactions.count + 1, updated_at = NOW()
            """,
            post_id, message_id, chat_id, emoji,
        )
