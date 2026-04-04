"""
Tests for app.algorithm — pure functions, no mocks needed.
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.algorithm import (
    compute_exposure_weight,
    select_post_pool_strategy,
    weighted_random_select,
    should_auto_remove,
    compute_group_rate_limit,
)
from app.models import Limits


# ══════════════════════════════════════════════
# compute_exposure_weight
# ══════════════════════════════════════════════

class TestExposureWeight:

    def _now(self):
        return datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)

    def test_fresh_popular_post_scores_high(self):
        """A fresh post with many likes and reactions should score well."""
        w = compute_exposure_weight(
            like_count=20, dislike_count=2,
            reactions_total=30, view_count=50,
            created_at=self._now() - timedelta(hours=1),
            viewer_country="中国", viewer_lang="zh",
            post_country="中国", post_lang="zh",
            channel_id=4, now=self._now(),
        )
        assert w > 1.0

    def test_old_unpopular_post_scores_low(self):
        """A 3-day-old post with dislikes should score poorly."""
        w = compute_exposure_weight(
            like_count=1, dislike_count=10,
            reactions_total=0, view_count=100,
            created_at=self._now() - timedelta(days=3),
            viewer_country="中国", viewer_lang="zh",
            post_country="美国", post_lang="en",
            channel_id=4, now=self._now(),
        )
        assert w < 0.1

    def test_same_country_affinity_boost(self):
        """Same country should give 2x affinity vs different country."""
        base_args = dict(
            like_count=10, dislike_count=2,
            reactions_total=5, view_count=30,
            created_at=self._now() - timedelta(hours=2),
            viewer_lang="zh", post_lang="zh",
            channel_id=4, now=self._now(),
        )
        w_same = compute_exposure_weight(viewer_country="中国", post_country="中国", **base_args)
        w_diff = compute_exposure_weight(viewer_country="中国", post_country="日本", **base_args)
        assert w_same > w_diff

    def test_channel1_exempt_from_affinity(self):
        """Channel 1 (环球风光) should ignore affinity — always 1.0."""
        base_args = dict(
            like_count=10, dislike_count=0,
            reactions_total=5, view_count=20,
            created_at=self._now() - timedelta(hours=1),
            viewer_lang="zh", post_lang="en",
            now=self._now(),
        )
        w_same = compute_exposure_weight(viewer_country="中国", post_country="中国", channel_id=1, **base_args)
        w_diff = compute_exposure_weight(viewer_country="中国", post_country="日本", channel_id=1, **base_args)
        assert w_same == w_diff

    def test_no_votes_defaults_to_half_quality(self):
        """No likes or dislikes should give quality = 0.5."""
        w = compute_exposure_weight(
            like_count=0, dislike_count=0,
            reactions_total=0, view_count=1,
            created_at=self._now(),
            viewer_country="", viewer_lang="en",
            post_country="", post_lang="en",
            channel_id=4, now=self._now(),
        )
        # quality=0.5, emotion=0, freshness≈1.0, affinity=1.0 → ~0.5
        assert 0.4 < w < 0.6

    def test_weight_never_zero(self):
        """Weight should have a floor > 0 to prevent dead posts."""
        w = compute_exposure_weight(
            like_count=0, dislike_count=100,
            reactions_total=0, view_count=1000,
            created_at=self._now() - timedelta(days=30),
            viewer_country="", viewer_lang="",
            post_country="", post_lang="",
            channel_id=4, now=self._now(),
        )
        assert w >= 0.001


# ══════════════════════════════════════════════
# select_post_pool_strategy
# ══════════════════════════════════════════════

class TestPoolStrategy:

    def test_returns_valid_strategy(self):
        """Should return either 'local' or 'global'."""
        results = {select_post_pool_strategy() for _ in range(100)}
        assert results == {"local", "global"}

    def test_roughly_balanced(self):
        """Should be approximately 50/50 over many trials."""
        results = [select_post_pool_strategy() for _ in range(1000)]
        local_ratio = results.count("local") / len(results)
        assert 0.4 < local_ratio < 0.6


# ══════════════════════════════════════════════
# weighted_random_select
# ══════════════════════════════════════════════

class TestWeightedSelect:

    def _make_post(self, post_id, like_count=10, created_hours_ago=1):
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        return {
            "id": post_id,
            "channel_id": 4,
            "country": "中国",
            "original_lang": "zh",
            "like_count": like_count,
            "dislike_count": 0,
            "reactions": {"🌸": 3},
            "view_count": 20,
            "created_at": now - timedelta(hours=created_hours_ago),
        }

    def test_selects_from_list(self):
        posts = [self._make_post("a"), self._make_post("b"), self._make_post("c")]
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        selected = weighted_random_select(posts, "中国", "zh", now)
        assert selected is not None
        assert selected["id"] in ("a", "b", "c")

    def test_empty_list_returns_none(self):
        assert weighted_random_select([], "中国", "zh") is None

    def test_single_post_returns_it(self):
        posts = [self._make_post("only")]
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        selected = weighted_random_select(posts, "中国", "zh", now)
        assert selected["id"] == "only"

    def test_popular_post_selected_more_often(self):
        """A post with 100 likes should be selected more often than one with 1."""
        popular = self._make_post("pop", like_count=100, created_hours_ago=1)
        unpopular = self._make_post("unpop", like_count=1, created_hours_ago=1)
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)

        selections = {"pop": 0, "unpop": 0}
        for _ in range(500):
            s = weighted_random_select([popular, unpopular], "中国", "zh", now)
            selections[s["id"]] += 1

        assert selections["pop"] > selections["unpop"]


# ══════════════════════════════════════════════
# should_auto_remove
# ══════════════════════════════════════════════

class TestAutoRemove:

    def test_low_views_always_normal(self):
        """Posts with < REPORT_MIN_VIEWS views should never be auto-removed."""
        assert should_auto_remove(5, Limits.REPORT_MIN_VIEWS - 1) == "normal"

    def test_high_report_rate_removed(self):
        """Report rate > 10% should trigger removal."""
        assert should_auto_remove(15, 100) == "removed"

    def test_medium_report_rate_demoted(self):
        """Report rate 5-10% should trigger demotion."""
        assert should_auto_remove(7, 100) == "demoted"

    def test_low_report_rate_normal(self):
        """Report rate < 5% should be normal."""
        assert should_auto_remove(2, 100) == "normal"

    def test_zero_reports_normal(self):
        assert should_auto_remove(0, 500) == "normal"


# ══════════════════════════════════════════════
# compute_group_rate_limit
# ══════════════════════════════════════════════

class TestGroupRateLimit:

    def test_under_tier1_no_limit(self):
        assert compute_group_rate_limit(0) == 0
        assert compute_group_rate_limit(Limits.GROUP_RATE_TIER1_COUNT - 1) == 0

    def test_tier1_cooldown(self):
        assert compute_group_rate_limit(Limits.GROUP_RATE_TIER1_COUNT) == Limits.GROUP_RATE_TIER1_SECONDS
        assert compute_group_rate_limit(Limits.GROUP_RATE_TIER2_COUNT) == Limits.GROUP_RATE_TIER1_SECONDS

    def test_tier2_cooldown(self):
        assert compute_group_rate_limit(Limits.GROUP_RATE_TIER2_COUNT + 1) == Limits.GROUP_RATE_TIER2_SECONDS
