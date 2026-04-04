"""
Tests for app.handlers.card_builder — card text, inline keyboards, reply keyboards.
"""

import pytest
from unittest.mock import patch
from app.handlers.card_builder import (
    build_card_text,
    build_card_inline_keyboard,
    build_private_browse_keyboard,
    build_group_card_inline_keyboard,
)
from app.models import REACTION_EMOJIS


class TestBuildCardText:

    def _post(self, **overrides):
        base = {
            "channel_id": 4,
            "country": "中国",
            "content": "这是一个测试故事内容",
        }
        base.update(overrides)
        return base

    @patch("app.handlers.card_builder.fmt_country", return_value="🇨🇳 中国")
    def test_includes_channel_and_country(self, mock_fmt):
        text = build_card_text(self._post(), lang="zh")
        assert "🌙" in text  # Channel 4 emoji
        assert "深夜树洞" in text
        assert "🇨🇳 中国" in text

    def test_includes_content(self):
        text = build_card_text(self._post(), lang="zh")
        assert "这是一个测试故事内容" in text

    def test_includes_anonymous_label(self):
        text = build_card_text(self._post(), lang="zh")
        assert "匿名" in text or "anonymous" in text.lower()

    def test_translated_content_used(self):
        text = build_card_text(self._post(), lang="en", translated_content="This is translated")
        assert "This is translated" in text
        assert "这是一个测试故事内容" not in text

    def test_no_country_no_crash(self):
        text = build_card_text(self._post(country=""), lang="zh")
        assert "🌙" in text


class TestBuildCardInlineKeyboard:

    def test_has_reaction_row(self):
        kb = build_card_inline_keyboard("post1", reactions={})
        rows = kb["inline_keyboard"]
        # First row should be reactions
        assert len(rows[0]) == 5  # 5 reaction emojis

    def test_reaction_counts_displayed(self):
        reactions = {"🌸": 10, "🤣": 5, "💔": 0, "🤗": 0, "❓": 0}
        kb = build_card_inline_keyboard("post1", reactions=reactions)
        first_row = kb["inline_keyboard"][0]
        texts = [btn["text"] for btn in first_row]
        assert "🌸 10" in texts
        assert "🤣 5" in texts

    def test_has_post_also_button(self):
        kb = build_card_inline_keyboard("post1", include_post_button=True)
        rows = kb["inline_keyboard"]
        post_row = rows[1]  # Second row
        assert any("📝" in btn["text"] for btn in post_row)

    def test_no_swipe_buttons_by_default(self):
        kb = build_card_inline_keyboard("post1")
        rows = kb["inline_keyboard"]
        # Should only have reaction row + post_also row
        assert len(rows) == 2

    def test_swipe_buttons_when_requested(self):
        kb = build_card_inline_keyboard("post1", include_swipe_buttons=True)
        rows = kb["inline_keyboard"]
        # Should have reaction + post_also + swipe row
        assert len(rows) == 3
        swipe_row = rows[2]
        texts = [btn["text"] for btn in swipe_row]
        assert "👍" in texts
        assert "👎" in texts
        assert "⭐" in texts
        assert "⚠️" in texts

    def test_callback_data_format(self):
        kb = build_card_inline_keyboard("abc123")
        first_btn = kb["inline_keyboard"][0][0]
        assert first_btn["callback_data"].startswith("react:abc123:")


class TestBrowseKeyboard:

    def test_zh_labels(self):
        kb = build_private_browse_keyboard("zh")
        rows = kb["keyboard"]
        assert rows[0] == [{"text": "👍 赞"}, {"text": "👎 下一个"}]
        assert any("收藏" in btn["text"] for btn in rows[1])
        assert any("举报" in btn["text"] for btn in rows[1])
        assert any("返回" in btn["text"] for btn in rows[2])

    def test_en_labels(self):
        kb = build_private_browse_keyboard("en")
        rows = kb["keyboard"]
        assert any("Save" in btn["text"] for btn in rows[1])
        assert any("Report" in btn["text"] for btn in rows[1])
        assert any("Back" in btn["text"] for btn in rows[2])


class TestGroupCardKeyboard:

    def test_has_all_three_layers(self):
        kb = build_group_card_inline_keyboard("post1", reactions={})
        rows = kb["inline_keyboard"]
        assert len(rows) == 2  # Layer 1 + Layer 2 (group swipe uses reply keyboard)
