"""
Blink.World — User Service
Database operations for user management.
"""

import json
import logging
from datetime import datetime, timezone

from app.database import get_pool
from app.models import UserProfile, ALL_CHANNEL_IDS

logger = logging.getLogger(__name__)


async def get_or_create_user(user_id: int, language_code: str | None = None) -> tuple[UserProfile, bool]:
    """
    Get existing user or create a new one.
    Returns (user, is_new).
    """
    pool = get_pool()
    from app.i18n import detect_language

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

        if row:
            user = _row_to_user(row)
            return user, False

        # New user
        lang = detect_language(language_code)
        channel_prefs = json.dumps(ALL_CHANNEL_IDS)
        default_stats = json.dumps({
            "views_total": 0,
            "published_total": 0,
            "likes_received": 0,
            "invited_count": 0,
        })

        await conn.execute(
            """
            INSERT INTO users (id, lang, channel_prefs, stats, onboard_state)
            VALUES ($1, $2, $3, $4, 'new')
            ON CONFLICT (id) DO NOTHING
            """,
            user_id, lang, channel_prefs, default_stats,
        )

        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        user = _row_to_user(row)
        return user, True


async def update_user(user_id: int, **fields) -> bool:
    """Update specific user fields. Only updates provided fields."""
    if not fields:
        return False

    # Whitelist: only these columns can be updated dynamically
    ALLOWED_FIELDS = {
        "lang", "country", "channel_prefs", "points", "show_country",
        "last_checkin", "stats", "onboard_state",
    }

    pool = get_pool()
    set_clauses = []
    values = []
    idx = 1

    for key, value in fields.items():
        if key not in ALLOWED_FIELDS:
            logger.warning("update_user: rejected unknown field '%s'", key)
            continue
        if key in ("channel_prefs", "stats") and isinstance(value, (dict, list)):
            value = json.dumps(value)
        set_clauses.append(f"{key} = ${idx}")
        values.append(value)
        idx += 1

    if not set_clauses:
        return False

    values.append(user_id)
    sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ${idx}"

    async with pool.acquire() as conn:
        await conn.execute(sql, *values)
    return True


async def add_points(user_id: int, points: int, reason: str = "") -> int:
    """Add points to user atomically. Returns new total."""
    pool = get_pool()
    async with pool.acquire() as conn:
        new_total = await conn.fetchval(
            "UPDATE users SET points = points + $1 WHERE id = $2 RETURNING points",
            points, user_id,
        )
        if new_total is None:
            logger.warning("add_points: user %d not found", user_id)
            return 0
        logger.info("Points +%d for user %d (%s), total=%d", points, user_id, reason, new_total)
        return new_total


async def increment_stat(user_id: int, stat_key: str, amount: int = 1):
    """Increment a specific stat in the user's stats JSONB."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET stats = jsonb_set(
                stats,
                $2,
                (COALESCE((stats->>$3)::int, 0) + $4)::text::jsonb
            )
            WHERE id = $1
            """,
            user_id,
            [stat_key],
            stat_key,
            amount,
        )


async def get_user(user_id: int) -> UserProfile | None:
    """Get user by ID. Returns None if not found."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        if row is None:
            return None
        return _row_to_user(row)


async def get_onboard_state(user_id: int) -> str:
    """Read onboard_state directly from DB."""
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT onboard_state FROM users WHERE id = $1", user_id
        )
        return val or "new"


async def process_referral(inviter_id: int, invitee_id: int) -> bool:
    """Process referral reward. Atomic, prevents duplicates. Returns True if newly processed."""
    from app.models import PointsConfig
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO referrals (inviter_id, invitee_id)
                VALUES ($1, $2)
                ON CONFLICT (invitee_id) DO NOTHING
                """,
                inviter_id, invitee_id,
            )
            if "INSERT 0 1" in result:
                await add_points(inviter_id, PointsConfig.INVITE_USER, reason="invite")
                await increment_stat(inviter_id, "invited_count")
                return True
        return False
    except Exception as e:
        logger.error("Referral processing failed: %s", e)
        return False


def _row_to_user(row) -> UserProfile:
    """Convert asyncpg Record to UserProfile."""
    stats = row["stats"]
    if isinstance(stats, str):
        stats = json.loads(stats)

    channel_prefs = row["channel_prefs"]
    if isinstance(channel_prefs, str):
        channel_prefs = json.loads(channel_prefs)

    return UserProfile(
        id=row["id"],
        lang=row["lang"],
        country=row["country"],
        channel_prefs=channel_prefs,
        points=row["points"],
        show_country=row["show_country"],
        is_premium=row.get("is_premium", False) or False,
        created_at=row["created_at"],
        last_checkin=row["last_checkin"],
        stats=stats,
    )


async def get_invitees_activity(inviter_id: int) -> list[dict]:
    """
    Query activity stats for all users invited by inviter_id.
    Returns a list of dicts, one per invitee, sorted by swipe_count desc.
    Each dict contains:
      - invitee_id
      - swipe_count   (total posts swiped, like+dislike)
      - points
      - is_premium
      - joined_at     (when they joined the bot)
      - last_active   (timestamp of their last swipe, or None)
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                r.invitee_id,
                u.points,
                u.is_premium,
                u.created_at            AS joined_at,
                COUNT(s.post_id)        AS swipe_count,
                MAX(s.created_at)       AS last_active
            FROM referrals r
            JOIN users u ON u.id = r.invitee_id
            LEFT JOIN post_swipes s ON s.user_id = r.invitee_id
            WHERE r.inviter_id = $1
            GROUP BY r.invitee_id, u.points, u.is_premium, u.created_at
            ORDER BY swipe_count DESC, u.created_at DESC
            """,
            inviter_id,
        )
    return [dict(row) for row in rows]
