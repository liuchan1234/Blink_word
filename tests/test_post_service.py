"""
Tests for app.services.post_service — post CRUD, swipes, favorites, reactions, reports.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from app.models import Limits


# ══════════════════════════════════════════════
# create_post
# ══════════════════════════════════════════════

class TestCreatePost:

    @pytest.mark.asyncio
    async def test_creates_post_and_returns_id(self, fake_pool):
        """Should insert a row and return a short UUID post_id."""
        pool, conn = fake_pool()

        with patch("app.services.post_service.get_pool", return_value=pool):
            from app.services.post_service import create_post
            post_id = await create_post(
                channel_id=4,
                content="测试故事内容，超过六个字了。",
                original_lang="zh",
                source="ugc",
                author_id=12345,
                country="中国",
            )

        assert post_id is not None
        assert len(post_id) == 12  # Short UUID
        assert len(conn.executed) == 1
        assert "INSERT INTO posts" in conn.executed[0][1]

    @pytest.mark.asyncio
    async def test_creates_post_with_photo(self, fake_pool):
        """Should pass photo_file_id to the INSERT."""
        pool, conn = fake_pool()

        with patch("app.services.post_service.get_pool", return_value=pool):
            from app.services.post_service import create_post
            post_id = await create_post(
                channel_id=1,
                content="Photo post",
                photo_file_id="AgACAgIAAxkBAAI...",
            )

        assert post_id is not None
        # photo_file_id should be in the args
        args = conn.executed[0][2]
        assert "AgACAgIAAxkBAAI..." in args


# ══════════════════════════════════════════════
# record_swipe
# ══════════════════════════════════════════════

class TestRecordSwipe:

    @pytest.mark.asyncio
    async def test_records_new_like(self, fake_pool):
        """New like should INSERT and increment like_count."""
        call_log = []

        class SwipeConn:
            async def fetchval(self, query, *args):
                call_log.append(("fetchval", query[:30]))
                if "WITH inserted" in query:
                    return 1  # Successfully inserted
                if "SELECT author_id" in query:
                    return None  # No author
                return None

            async def execute(self, query, *args):
                call_log.append(("execute", query[:40]))
                return "UPDATE 1"

        conn = SwipeConn()
        pool_obj = _make_pool(conn)

        with patch("app.services.post_service.get_pool", return_value=pool_obj):
            from app.services.post_service import record_swipe
            result = await record_swipe(user_id=100, post_id="abc123", action="like")

        assert result is True
        # Should have incremented like_count
        executed_queries = [q for _, q in call_log if "execute" == _]
        assert any("like_count" in q for _, q in call_log)

    @pytest.mark.asyncio
    async def test_duplicate_swipe_returns_false(self, fake_pool):
        """Duplicate swipe (ON CONFLICT DO NOTHING) should return False."""
        class DupConn:
            async def fetchval(self, query, *args):
                if "WITH inserted" in query:
                    return 0  # Nothing inserted (conflict)
                return None

            async def execute(self, query, *args):
                return "UPDATE 0"

        conn = DupConn()
        pool_obj = _make_pool(conn)

        with patch("app.services.post_service.get_pool", return_value=pool_obj):
            from app.services.post_service import record_swipe
            result = await record_swipe(user_id=100, post_id="abc123", action="like")

        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_action_returns_false(self, fake_pool):
        """Invalid action (not like/dislike) should return False immediately."""
        pool, conn = fake_pool()

        with patch("app.services.post_service.get_pool", return_value=pool):
            from app.services.post_service import record_swipe
            result = await record_swipe(user_id=100, post_id="abc123", action="love")

        assert result is False
        assert len(conn.executed) == 0  # No DB call made


# ══════════════════════════════════════════════
# toggle_favorite (atomicity test)
# ══════════════════════════════════════════════

class TestToggleFavorite:

    @pytest.mark.asyncio
    async def test_favorite_new_post(self):
        """Toggling unfavorited post should INSERT and return True."""
        class FavConn:
            executed = []

            async def fetchval(self, query, *args):
                if "WITH removed" in query:
                    return 0  # Nothing deleted → was not favorited
                return None

            async def execute(self, query, *args):
                self.executed.append(query[:50])
                return "INSERT 0 1"

        conn = FavConn()
        pool_obj = _make_pool(conn)

        with patch("app.services.post_service.get_pool", return_value=pool_obj):
            from app.services.post_service import toggle_favorite
            is_fav = await toggle_favorite(user_id=100, post_id="abc123")

        assert is_fav is True
        assert any("INSERT INTO post_favorites" in q for q in conn.executed)

    @pytest.mark.asyncio
    async def test_unfavorite_existing(self):
        """Toggling already-favorited post should DELETE and return False."""
        class UnfavConn:
            executed = []

            async def fetchval(self, query, *args):
                if "WITH removed" in query:
                    return 1  # Deleted → was favorited
                return None

            async def execute(self, query, *args):
                self.executed.append(query[:50])
                return "UPDATE 1"

        conn = UnfavConn()
        pool_obj = _make_pool(conn)

        with patch("app.services.post_service.get_pool", return_value=pool_obj):
            from app.services.post_service import toggle_favorite
            is_fav = await toggle_favorite(user_id=100, post_id="abc123")

        assert is_fav is False
        assert any("GREATEST(favorite_count - 1" in q for q in conn.executed)


# ══════════════════════════════════════════════
# report_post
# ══════════════════════════════════════════════

class TestReportPost:

    @pytest.mark.asyncio
    async def test_report_increments_count(self):
        """Reporting should increment report_count."""
        class ReportConn:
            executed = []

            async def execute(self, query, *args):
                self.executed.append(query[:60])
                return "INSERT 0 1"

            async def fetchrow(self, query, *args):
                return {"report_count": 2, "view_count": 100}

        conn = ReportConn()
        pool_obj = _make_pool(conn)

        with patch("app.services.post_service.get_pool", return_value=pool_obj):
            from app.services.post_service import report_post
            result = await report_post(user_id=100, post_id="abc123")

        assert result is True
        assert any("report_count" in q for q in conn.executed)

    @pytest.mark.asyncio
    async def test_high_report_rate_deactivates_post(self):
        """Report rate > 10% should set is_active = FALSE."""
        class HighReportConn:
            executed = []

            async def execute(self, query, *args):
                self.executed.append(query[:60])
                return "INSERT 0 1"

            async def fetchrow(self, query, *args):
                # 15 reports / 100 views = 15% > REPORT_REMOVE_RATE (10%)
                return {"report_count": 15, "view_count": 100}

        conn = HighReportConn()
        pool_obj = _make_pool(conn)

        with patch("app.services.post_service.get_pool", return_value=pool_obj):
            from app.services.post_service import report_post
            result = await report_post(user_id=100, post_id="abc123")

        assert result is True
        assert any("is_active = FALSE" in q for q in conn.executed)


# ══════════════════════════════════════════════
# get_post
# ══════════════════════════════════════════════

class TestGetPost:

    @pytest.mark.asyncio
    async def test_returns_post_dict(self, fake_pool):
        """Should convert DB row to dict."""
        row = {
            "id": "abc123",
            "channel_id": 4,
            "country": "中国",
            "content": "故事内容",
            "photo_file_id": None,
            "original_lang": "zh",
            "source": "ugc",
            "author_id": 12345,
            "group_only": None,
            "created_at": datetime(2026, 3, 20, tzinfo=timezone.utc),
            "reactions": '{"🌸": 5}',
            "like_count": 10,
            "dislike_count": 2,
            "favorite_count": 3,
            "report_count": 0,
            "view_count": 50,
            "is_active": True,
        }
        pool, conn = fake_pool(rows=[row])

        with patch("app.services.post_service.get_pool", return_value=pool):
            from app.services.post_service import get_post
            post = await get_post("abc123")

        assert post is not None
        assert post["id"] == "abc123"
        # reactions should be parsed from JSON string
        assert post["reactions"] == {"🌸": 5}

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self, fake_pool):
        """Missing post should return None."""
        pool, conn = fake_pool(rows=[])

        with patch("app.services.post_service.get_pool", return_value=pool):
            from app.services.post_service import get_post
            post = await get_post("nonexistent")

        assert post is None


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

def _make_pool(conn):
    """Create a minimal pool mock with the given connection."""
    class FakeAcquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            pass

    return type("Pool", (), {"acquire": lambda self: FakeAcquire()})()
