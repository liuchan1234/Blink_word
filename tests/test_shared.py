"""
Tests for app.handlers.shared — shared keyboards and utilities.
"""

import pytest
from app.handlers.shared import (
    main_menu_keyboard,
    country_quick_picks,
)


class TestMainMenuKeyboard:

    def test_zh_has_five_buttons(self):
        kb = main_menu_keyboard("zh")
        rows = kb["keyboard"]
        all_texts = [btn["text"] for row in rows for btn in row]
        assert len(all_texts) == 5

    def test_en_has_five_buttons(self):
        kb = main_menu_keyboard("en")
        rows = kb["keyboard"]
        all_texts = [btn["text"] for row in rows for btn in row]
        assert len(all_texts) == 5

    def test_persistent_keyboard(self):
        kb = main_menu_keyboard("zh")
        assert kb.get("is_persistent") is True
        assert kb.get("resize_keyboard") is True


class TestCountryQuickPicks:

    def test_returns_grid(self):
        rows = country_quick_picks("zh")
        assert len(rows) > 0
        # Each row should have 1-3 buttons
        for row in rows:
            assert 1 <= len(row) <= 3

    def test_has_18_countries(self):
        rows = country_quick_picks("zh")
        total = sum(len(row) for row in rows)
        assert total == 18

    def test_callback_data_format(self):
        rows = country_quick_picks("zh")
        first_btn = rows[0][0]
        assert first_btn["callback_data"].startswith("set_country:")

    def test_highlighted_country(self):
        rows = country_quick_picks("zh", highlighted="中国")
        all_btns = [btn for row in rows for btn in row]
        china_btn = [b for b in all_btns if "中国" in b["text"]]
        assert len(china_btn) == 1
        assert "✓" in china_btn[0]["text"]

    def test_en_labels(self):
        rows = country_quick_picks("en")
        all_texts = [btn["text"] for row in rows for btn in row]
        # Should have English names
        assert any("China" in t for t in all_texts)
        assert any("United States" in t for t in all_texts)
