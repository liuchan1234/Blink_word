"""
Tests for app.models — channel definitions, Limits, PointsConfig.
"""

import pytest
from app.models import (
    CHANNELS, USER_CHANNEL_IDS, ALL_CHANNEL_IDS,
    get_channel, get_channel_name, get_channel_display,
    REACTION_EMOJIS, MILESTONE_LEVELS,
    PointsConfig, Limits, UserProfile,
)


class TestChannels:

    def test_eleven_channels_defined(self):
        assert len(CHANNELS) == 11

    def test_channel_ids_sequential(self):
        ids = [c.id for c in CHANNELS]
        assert ids == list(range(1, 12))

    def test_user_channels_are_3_to_11(self):
        assert USER_CHANNEL_IDS == [3, 4, 5, 6, 7, 8, 9, 10, 11]

    def test_all_channel_ids(self):
        assert ALL_CHANNEL_IDS == list(range(1, 12))

    def test_get_channel_valid(self):
        ch = get_channel(3)
        assert ch is not None
        assert ch.names["zh"] == "深夜树洞"
        assert ch.emoji == "🌙"
        assert ch.is_user_channel is True

    def test_get_channel_invalid(self):
        assert get_channel(99) is None

    def test_get_channel_name_zh(self):
        assert get_channel_name(1, "zh") == "环球旅行"

    def test_get_channel_name_en(self):
        assert get_channel_name(1, "en") == "World Travel"

    def test_get_channel_display(self):
        display = get_channel_display(4, "zh")
        assert "🤪" in display
        assert "沙雕日常" in display

    def test_platform_channels_not_user_postable(self):
        """Channels 1-2 are platform-operated and should not allow user posts."""
        for c in CHANNELS:
            if c.id <= 2:
                assert c.is_user_channel is False
            else:
                assert c.is_user_channel is True


class TestReactions:

    def test_five_reaction_emojis(self):
        assert len(REACTION_EMOJIS) == 5
        assert "🌸" in REACTION_EMOJIS
        assert "🤣" in REACTION_EMOJIS
        assert "💔" in REACTION_EMOJIS
        assert "😭" in REACTION_EMOJIS
        assert "💀" in REACTION_EMOJIS


class TestMilestones:

    def test_five_milestone_levels(self):
        assert len(MILESTONE_LEVELS) == 5

    def test_thresholds_ascending(self):
        thresholds = [m["threshold"] for m in MILESTONE_LEVELS]
        assert thresholds == sorted(thresholds)
        assert thresholds == [10, 30, 100, 300, 1000]

    def test_points_match_thresholds(self):
        """PRD: milestone points equal the threshold value."""
        for m in MILESTONE_LEVELS:
            assert m["points"] == m["threshold"]


class TestPointsConfig:

    def test_values_defined(self):
        assert PointsConfig.DAILY_CHECKIN == 10
        assert PointsConfig.SWIPE_PER_10 == 5
        assert PointsConfig.PUBLISH_STORY == 20
        assert PointsConfig.DAILY_TOPIC_BONUS == 10
        assert PointsConfig.INVITE_USER == 50
        assert PointsConfig.ADD_BOT_TO_GROUP == 100
        assert PointsConfig.GROUP_PARTICIPATE == 2


class TestLimits:

    def test_content_length_bounds(self):
        assert Limits.CONTENT_MIN_LENGTH == 6
        assert Limits.CONTENT_MAX_LENGTH == 500

    def test_reactions_per_post(self):
        assert Limits.REACTIONS_PER_POST == 3

    def test_report_thresholds(self):
        assert Limits.REPORT_MIN_VIEWS == 10
        assert Limits.REPORT_DEMOTE_RATE == 0.05
        assert Limits.REPORT_REMOVE_RATE == 0.10

    def test_private_rate_limit_defined(self):
        """Private chat rate limiting should be configured."""
        assert Limits.PRIVATE_SWIPE_PER_MINUTE > 0
        assert Limits.PRIVATE_SWIPE_WINDOW > 0

    def test_group_rate_tiers_ordered(self):
        assert Limits.GROUP_RATE_TIER1_COUNT < Limits.GROUP_RATE_TIER2_COUNT
        assert Limits.GROUP_RATE_TIER1_SECONDS < Limits.GROUP_RATE_TIER2_SECONDS

    def test_profile_limits(self):
        assert Limits.PROFILE_STORIES_LIMIT == 10
        assert Limits.PROFILE_FAVORITES_LIMIT == 10

    def test_ttls_positive(self):
        """All TTL values should be positive integers."""
        ttl_attrs = [
            "VIEWED_TTL", "CURRENT_POST_TTL", "SWIPE_COUNT_TTL",
            "TRANSLATE_TTL", "DRAFT_TTL", "GROUP_STATE_TTL",
            "GROUP_SEEN_TTL", "FLIP_LOCK_TTL", "PENDING_IMAGE_TTL",
        ]
        for attr in ttl_attrs:
            val = getattr(Limits, attr)
            assert isinstance(val, int) and val > 0, f"{attr} = {val}"


class TestUserProfile:

    def test_default_values(self):
        u = UserProfile(id=1)
        assert u.lang == "zh"
        assert u.country == ""
        assert u.points == 0
        assert u.show_country is True
        assert len(u.channel_prefs) == 11  # All channels
        assert u.stats["views_total"] == 0
