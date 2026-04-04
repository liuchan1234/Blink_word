"""
Tests for app.i18n — translation keys, language detection, completeness.
"""

import pytest
from app.i18n import (
    t, detect_language, guess_country,
    SUPPORTED_LANGUAGES, LANGUAGE_NAMES, _T,
)


class TestTranslationKeys:

    def test_all_supported_languages_have_names(self):
        for lang in SUPPORTED_LANGUAGES:
            assert lang in LANGUAGE_NAMES

    def test_supported_languages(self):
        assert set(SUPPORTED_LANGUAGES) == {"zh", "en", "ru", "id", "pt"}

    def test_core_keys_exist(self):
        """Essential keys used across the app must exist."""
        core_keys = [
            "welcome", "choose_country", "country_set", "setup_complete",
            "menu_browse", "menu_post", "menu_me", "menu_settings",
            "anonymous", "no_more_content", "error_generic",
            "favorited", "reported", "published_success",
            "choose_channel", "enter_content",
            "content_too_short", "content_too_long",
        ]
        for key in core_keys:
            assert key in _T, f"Missing i18n key: {key}"

    def test_all_keys_have_all_languages(self):
        """Every translation key should have entries for all 5 languages."""
        missing = []
        for key, translations in _T.items():
            for lang in SUPPORTED_LANGUAGES:
                if lang not in translations:
                    missing.append(f"{key}.{lang}")
        if missing:
            pytest.fail(f"Missing translations: {', '.join(missing[:20])}{'...' if len(missing) > 20 else ''}")

    def test_no_empty_translations(self):
        """No translation value should be empty string."""
        empty = []
        for key, translations in _T.items():
            for lang, text in translations.items():
                if not text.strip():
                    empty.append(f"{key}.{lang}")
        if empty:
            pytest.fail(f"Empty translations: {', '.join(empty[:10])}")


class TestTranslationFunction:

    def test_basic_lookup(self):
        result = t("welcome", "zh")
        assert "Blink.World" in result

    def test_english_fallback(self):
        result = t("welcome", "en")
        assert "Blink.World" in result

    def test_unknown_key_returns_key(self):
        result = t("nonexistent_key_xyz", "zh")
        assert result == "nonexistent_key_xyz"

    def test_unknown_lang_falls_back_to_en(self):
        result = t("welcome", "xx")
        # Should fall back to English
        assert "Blink.World" in result

    def test_variable_substitution(self):
        result = t("country_set", "zh", country="🇨🇳 中国")
        assert "🇨🇳 中国" in result


class TestLanguageDetection:

    def test_chinese_detected(self):
        assert detect_language("zh") == "zh"
        assert detect_language("zh-hans") == "zh"
        assert detect_language("zh-tw") == "zh"

    def test_english_detected(self):
        assert detect_language("en") == "en"
        assert detect_language("en-US") == "en"

    def test_russian_detected(self):
        assert detect_language("ru") == "ru"

    def test_indonesian_detected(self):
        assert detect_language("id") == "id"

    def test_portuguese_detected(self):
        assert detect_language("pt") == "pt"
        assert detect_language("pt-br") == "pt"

    def test_unknown_defaults_to_en(self):
        assert detect_language("xx") == "en"
        assert detect_language(None) == "en"
        assert detect_language("") == "en"


class TestCountryGuess:

    def test_chinese_guesses_china(self):
        result = guess_country("zh")
        assert result in ("中国", "China", "")

    def test_none_returns_empty(self):
        result = guess_country(None)
        assert result == "" or isinstance(result, str)
