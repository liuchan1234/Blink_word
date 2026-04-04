"""
Tests for app.services.feed_service — feed browsing, viewed tracking, swipe count.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta


# ══════════════════════════════════════════════
# get_next_card
# ══════════════════════════════════════════════

class TestGetNextCard:

    def _make_post(self, post_id="abc123", channel_id=4):
        return {
            "id": post_id,
            "channel_id": channel_id,
            "country": "中国",
            "content": "测试故事内容",
            "photo_file_id": None,
            "original_lang": "zh",
            "source": "ugc",
            "author_id": 12345,
            "group_only": None,
            "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "reactions": {"🌸": 3},
            "like_count": 10,
            "dislike_count": 2,
            "favorite_count": 1,
            "report_count": 0,
            "view_count": 20,
            "is_active": True,
        }

    @pytest.mark.asyncio
    async def test_returns_post_when_available(self, mock_redis):
        """Should return a post dict when candidates exist."""
        post = self._make_post()

        with patch("app.services.feed_service.get_feed_posts", new_callable=AsyncMock, return_value=[post]), \
             patch("app.services.feed_service.increment_view", new_callable=AsyncMock), \
             patch("app.services.user_service.get_pool", return_value=MagicMock()):

            # Mock increment_stat to avoid DB call
            with patch("app.services.user_service.increment_stat", new_callable=AsyncMock):
                from app.services.feed_service import get_next_card
                result = await get_next_card(
                    user_id=100,
                    channel_ids=[1, 2, 3, 4],
                    viewer_country="中国",
                    viewer_lang="zh",
                )

        assert result is not None
        assert result["id"] == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self, mock_redis):
        """Should return None when no candidates available."""
        with patch("app.services.feed_service.get_feed_posts", new_callable=AsyncMock, return_value=[]):
            from app.services.feed_service import get_next_card
            result = await get_next_card(
                user_id=100,
                channel_ids=[1, 2, 3, 4],
                viewer_country="中国",
                viewer_lang="zh",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_channels(self, mock_redis):
        """Empty channel_ids should return None immediately."""
        from app.services.feed_service import get_next_card
        result = await get_next_card(
            user_id=100,
            channel_ids=[],
            viewer_country="中国",
            viewer_lang="zh",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_falls_back_to_global_when_local_empty(self, mock_redis):
        """When local pool returns empty, should try global pool."""
        post = self._make_post()
        call_count = {"n": 0}

        async def mock_get_feed_posts(**kwargs):
            call_count["n"] += 1
            if kwargs.get("pool_type") == "local":
                return []  # Local empty
            return [post]  # Global has content

        with patch("app.services.feed_service.get_feed_posts", side_effect=mock_get_feed_posts), \
             patch("app.services.feed_service.select_post_pool_strategy", return_value="local"), \
             patch("app.services.feed_service.increment_view", new_callable=AsyncMock), \
             patch("app.services.user_service.increment_stat", new_callable=AsyncMock), \
             patch("app.services.user_service.get_pool", return_value=MagicMock()):

            from app.services.feed_service import get_next_card
            result = await get_next_card(
                user_id=100,
                channel_ids=[1, 2, 3, 4],
                viewer_country="中国",
                viewer_lang="zh",
            )

        assert result is not None
        assert call_count["n"] == 2  # Called twice: local then global


# ══════════════════════════════════════════════
# get_current_post_id
# ══════════════════════════════════════════════

class TestGetCurrentPostId:

    @pytest.mark.asyncio
    async def test_returns_cached_post_id(self, mock_redis):
        """Should return post_id from Redis."""
        await mock_redis.set("cur_post:100", "abc123")

        from app.services.feed_service import get_current_post_id
        result = await get_current_post_id(100)

        assert result == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_set(self, mock_redis):
        """Should return None when no current post."""
        from app.services.feed_service import get_current_post_id
        result = await get_current_post_id(99999)

        assert result is None


# ══════════════════════════════════════════════
# get_swipe_count
# ══════════════════════════════════════════════

class TestGetSwipeCount:

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_redis):
        """Should return swipe count from Redis."""
        await mock_redis.set("swipes:100", "42")

        from app.services.feed_service import get_swipe_count
        result = await get_swipe_count(100)

        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_zero_when_not_set(self, mock_redis):
        """Should return 0 when no swipe count exists."""
        from app.services.feed_service import get_swipe_count
        result = await get_swipe_count(99999)

        assert result == 0
