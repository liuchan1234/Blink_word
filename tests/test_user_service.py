"""
Tests for app.services.user_service — user CRUD, points, stats, referral.
Uses FakePool/FakeConnection from conftest for DB mocking.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from app.models import UserProfile, ALL_CHANNEL_IDS, PointsConfig


# ══════════════════════════════════════════════
# get_or_create_user
# ══════════════════════════════════════════════

class TestGetOrCreateUser:

    @pytest.mark.asyncio
    async def test_returns_existing_user(self, fake_pool):
        """Existing user should be returned with is_new=False."""
        row = _make_user_row(id=12345, lang="en", country="USA", points=50)
        pool, conn = fake_pool(rows=[row])

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import get_or_create_user
            user, is_new = await get_or_create_user(12345, "en")

        assert is_new is False
        assert user.id == 12345
        assert user.lang == "en"
        assert user.points == 50

    @pytest.mark.asyncio
    async def test_creates_new_user_when_not_found(self, fake_pool):
        """Non-existing user should be created and returned with is_new=True."""
        new_row = _make_user_row(id=99999, lang="zh")

        # First fetchrow returns None (not found), second returns the new row
        call_count = {"n": 0}
        original_fetchrow = None

        class SmartConn:
            def __init__(self):
                self.executed = []

            async def fetchrow(self, query, *args):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return None  # User not found
                return new_row  # After insert

            async def execute(self, query, *args):
                self.executed.append((query, args))
                return "INSERT 0 1"

        conn = SmartConn()
        pool_obj = type("Pool", (), {"acquire": lambda self: _FakeAcquire(conn)})()

        with patch("app.services.user_service.get_pool", return_value=pool_obj):
            from app.services.user_service import get_or_create_user
            user, is_new = await get_or_create_user(99999, "zh")

        assert is_new is True
        assert user.id == 99999
        assert user.lang == "zh"


# ══════════════════════════════════════════════
# update_user
# ══════════════════════════════════════════════

class TestUpdateUser:

    @pytest.mark.asyncio
    async def test_updates_allowed_fields(self, fake_pool):
        """Should generate correct SQL for allowed fields."""
        pool, conn = fake_pool()

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import update_user
            result = await update_user(123, lang="en", country="Japan")

        assert result is True
        # Verify SQL was executed
        assert len(conn.executed) == 1
        sql = conn.executed[0][1]  # (method, query, args)
        assert "lang" in sql or "lang" in str(conn.executed)

    @pytest.mark.asyncio
    async def test_rejects_unknown_fields(self, fake_pool):
        """Unknown fields should be silently rejected."""
        pool, conn = fake_pool()

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import update_user
            result = await update_user(123, password="hack", admin=True)

        assert result is False  # No valid fields → no update

    @pytest.mark.asyncio
    async def test_empty_fields_returns_false(self, fake_pool):
        """No fields provided should return False."""
        pool, conn = fake_pool()

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import update_user
            result = await update_user(123)

        assert result is False

    @pytest.mark.asyncio
    async def test_serializes_json_fields(self, fake_pool):
        """channel_prefs and stats should be JSON-serialized before saving."""
        pool, conn = fake_pool()

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import update_user
            result = await update_user(123, channel_prefs=[1, 2, 3])

        assert result is True
        # The value passed to execute should be JSON string
        args = conn.executed[0][2]  # (method, query, args)
        assert json.dumps([1, 2, 3]) in [str(a) for a in args]


# ══════════════════════════════════════════════
# add_points
# ══════════════════════════════════════════════

class TestAddPoints:

    @pytest.mark.asyncio
    async def test_returns_new_total(self, fake_pool):
        """Should return the new total points after adding."""
        pool, conn = fake_pool(fetchval_result=150)

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import add_points
            total = await add_points(123, 50, reason="test")

        assert total == 150

    @pytest.mark.asyncio
    async def test_returns_zero_for_missing_user(self, fake_pool):
        """Missing user should return 0."""
        pool, conn = fake_pool(fetchval_result=None)

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import add_points
            total = await add_points(99999, 10, reason="ghost")

        assert total == 0


# ══════════════════════════════════════════════
# process_referral
# ══════════════════════════════════════════════

class TestProcessReferral:

    @pytest.mark.asyncio
    async def test_new_referral_succeeds(self, fake_pool):
        """First referral should succeed and add points."""
        pool, conn = fake_pool(fetchval_result=150)
        # Mock execute to return INSERT 0 1
        conn._fetchval_result = 150

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import process_referral
            result = await process_referral(inviter_id=100, invitee_id=200)

        assert result is True

    @pytest.mark.asyncio
    async def test_duplicate_referral_fails(self, fake_pool):
        """Duplicate referral (ON CONFLICT DO NOTHING) should return False."""
        class DupConn:
            executed = []

            async def execute(self, query, *args):
                return "INSERT 0 0"  # 0 rows → conflict

            async def fetchval(self, query, *args):
                return 100

        conn = DupConn()
        pool_obj = type("Pool", (), {"acquire": lambda self: _FakeAcquire(conn)})()

        with patch("app.services.user_service.get_pool", return_value=pool_obj):
            from app.services.user_service import process_referral
            result = await process_referral(inviter_id=100, invitee_id=200)

        assert result is False


# ══════════════════════════════════════════════
# get_onboard_state
# ══════════════════════════════════════════════

class TestGetOnboardState:

    @pytest.mark.asyncio
    async def test_returns_state(self, fake_pool):
        """Should return the stored onboard_state."""
        pool, conn = fake_pool(fetchval_result="choosing_country")

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import get_onboard_state
            state = await get_onboard_state(123)

        assert state == "choosing_country"

    @pytest.mark.asyncio
    async def test_defaults_to_new(self, fake_pool):
        """Missing user should default to 'new'."""
        pool, conn = fake_pool(fetchval_result=None)

        with patch("app.services.user_service.get_pool", return_value=pool):
            from app.services.user_service import get_onboard_state
            state = await get_onboard_state(99999)

        assert state == "new"


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _make_user_row(
    id=12345,
    lang="zh",
    country="中国",
    points=0,
    show_country=True,
    onboard_state="ready",
):
    """Create a dict that mimics an asyncpg Record for users table."""
    return {
        "id": id,
        "lang": lang,
        "country": country,
        "channel_prefs": json.dumps(ALL_CHANNEL_IDS),
        "points": points,
        "show_country": show_country,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "last_checkin": None,
        "stats": json.dumps({
            "views_total": 0,
            "published_total": 0,
            "likes_received": 0,
            "invited_count": 0,
        }),
        "onboard_state": onboard_state,
    }


class _FakeAcquire:
    """Minimal async context manager for pool.acquire()."""
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass
