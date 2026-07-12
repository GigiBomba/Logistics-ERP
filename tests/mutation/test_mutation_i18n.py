"""Mutation tests for i18n system — boundary inputs, corrupt translation files, concurrency.

Tests the robustness of the internationalization system under hostile or
unexpected conditions.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.mutation


# ═════════════════════════════════════════════════════════════════════════════
# Non-existent / invalid language codes
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationI18nLanguageCodes:
    """i18n system handles invalid language codes gracefully."""

    @pytest.fixture(autouse=True)
    def _reset_i18n(self):
        import services.i18n as i18n
        i18n._translations = {"en": {"hello": "Hello", "world": "World"}}
        i18n._current_lang = "en"

    @pytest.mark.parametrize("bad_lang", [
        "xx", "zz", "aa", "qq",
        "ab", "xy", "zz_ZZ",
    ])
    def test_non_existent_language_code(self, bad_lang):
        """set_language with non-existent codes falls back to 'en'."""
        import services.i18n as i18n
        i18n.set_language(bad_lang)
        # Should fall back to 'en'
        assert i18n.get_language() == "en"

    @pytest.mark.parametrize("bad_lang", [
        "", None, "   ", "en-US-extra", "en; DROP TABLE",
    ])
    def test_malformed_language_code(self, bad_lang):
        """set_language with malformed codes."""
        import services.i18n as i18n
        i18n.set_language(bad_lang)
        current = i18n.get_language()
        assert current is not None
        assert isinstance(current, str)

    def test_empty_string_language_code(self):
        """Empty string language code falls back gracefully."""
        import services.i18n as i18n
        i18n._current_lang = "en"
        # Directly set a language that doesn't exist in translations
        i18n.set_language("")
        # Should not crash — may stay at 'en' or empty string
        assert i18n.get_language() in ("en", "")

    def test_none_language_code(self):
        """None language code handled gracefully."""
        import services.i18n as i18n
        i18n._current_lang = "en"
        try:
            i18n.set_language(None)  # type: ignore[arg-type]
        except (TypeError, AttributeError):
            pass
        # Should not crash
        assert i18n.get_language() is not None

    def test_very_long_language_code(self):
        """Extremely long language code."""
        import services.i18n as i18n
        i18n._current_lang = "en"
        long_code = "x" * 1000
        i18n.set_language(long_code)
        # Should fall back to 'en'
        assert i18n.get_language() == "en"

    def test_sql_injection_language_code(self):
        """SQL injection in language code."""
        import services.i18n as i18n
        i18n._current_lang = "en"
        i18n.set_language("'; DROP TABLE users; --")
        assert i18n.get_language() == "en"

    def test_xss_in_language_code(self):
        """XSS in language code."""
        import services.i18n as i18n
        i18n._current_lang = "en"
        i18n.set_language("<script>alert('xss')</script>")
        assert i18n.get_language() == "en"


# ═════════════════════════════════════════════════════════════════════════════
# Corrupt translation files
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationI18nCorruptFiles:
    """i18n system handles corrupt/missing translation files gracefully."""

    @pytest.fixture
    def temp_translations_dir(self):
        """Create a temporary translations directory."""
        import services.i18n as i18n
        with tempfile.TemporaryDirectory() as d:
            original_dir = i18n._TRANSLATIONS_DIR
            i18n._TRANSLATIONS_DIR = d
            yield d
            i18n._TRANSLATIONS_DIR = original_dir

    @pytest.fixture(autouse=True)
    def _reset(self):
        import services.i18n as i18n
        i18n._translations = {}
        i18n._current_lang = "en"
        yield
        i18n._translations = {}
        i18n._current_lang = "en"

    def test_empty_json_file(self, temp_translations_dir):
        """Empty JSON file does not crash load_translations."""
        import services.i18n as i18n
        path = os.path.join(temp_translations_dir, "fr.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
        i18n.load_translations()
        # 'fr' wasn't loaded because the file is empty JSON (not valid)
        # The system should fall back to 'en'
        assert "en" in i18n._translations
        assert "fr" not in i18n._translations or i18n._translations["fr"] == {}

    def test_corrupt_json_file(self, temp_translations_dir):
        """Corrupt JSON file does not crash load_translations."""
        import services.i18n as i18n
        path = os.path.join(temp_translations_dir, "de.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{invalid json content!!!")
        i18n.load_translations()
        # Should not crash — 'de' should be skipped
        assert "en" in i18n._translations or len(i18n._translations) > 0

    def test_json_with_wrong_type(self, temp_translations_dir):
        """JSON file with array instead of object doesn't crash."""
        import services.i18n as i18n
        path = os.path.join(temp_translations_dir, "es.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(["not", "a", "dict"], f)
        i18n.load_translations()
        # Should not crash
        assert "en" in i18n._translations or len(i18n._translations) > 0

    def test_missing_key_in_translation(self, temp_translations_dir):
        """Missing key falls back to key itself or default."""
        import services.i18n as i18n
        # Create en.json with some keys
        path_en = os.path.join(temp_translations_dir, "en.json")
        with open(path_en, "w", encoding="utf-8") as f:
            json.dump({"hello": "Hello"}, f)
        i18n.load_translations()
        i18n.set_language("en")

        # Key that exists
        assert i18n.t("hello") == "Hello"
        # Key that doesn't exist — falls back to key itself
        assert i18n.t("nonexistent_key") == "nonexistent_key"
        # With default
        assert i18n.t("missing", default="Fallback") == "Fallback"

    def test_empty_translation_file(self, temp_translations_dir):
        """Empty JSON object {} does not crash."""
        import services.i18n as i18n
        path = os.path.join(temp_translations_dir, "ro.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}")
        # Create en.json so there's a fallback
        path_en = os.path.join(temp_translations_dir, "en.json")
        with open(path_en, "w", encoding="utf-8") as f:
            json.dump({"hello": "Hello"}, f)
        i18n.load_translations()
        assert "ro" in i18n._translations
        assert i18n._translations["ro"] == {}

    def test_no_translation_files(self, temp_translations_dir):
        """No translation files — system falls back to empty en."""
        import services.i18n as i18n
        i18n.load_translations()
        # Should have 'en' with empty dict
        assert i18n._translations.get("en") is not None


# ═════════════════════════════════════════════════════════════════════════════
# Unicode and format args
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationI18nUnicode:
    """i18n t() function handles Unicode and format edge cases."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import services.i18n as i18n
        i18n._translations = {
            "en": {
                "hello": "Hello {name}",
                "price": "Price: {amount} €",
                "unicode": "Unicode: {text}",
            },
        }
        i18n._current_lang = "en"
        yield
        i18n._translations = {}
        i18n._current_lang = "en"

    def test_unicode_in_format_args(self):
        """t() handles Unicode characters in format arguments."""
        import services.i18n as i18n
        result = i18n.t("hello", name="München Straße 🚚")
        assert "München Straße 🚚" in result

    def test_emoji_in_format_args(self):
        """t() handles emoji in format arguments."""
        import services.i18n as i18n
        result = i18n.t("hello", name="🎉🚛💨")
        assert "🎉🚛💨" in result

    def test_control_characters_in_args(self):
        """t() handles control characters without crashing."""
        import services.i18n as i18n
        result = i18n.t("hello", name="\x00\x01\x02test\x1f")
        assert "\x00" not in result or result is not None

    def test_very_long_format_arg(self):
        """t() handles extremely long format arguments."""
        import services.i18n as i18n
        long_name = "A" * 100000
        result = i18n.t("hello", name=long_name)
        assert len(result) >= 100000

    def test_missing_format_arg(self):
        """t() with missing format argument logs warning but does not crash."""
        import services.i18n as i18n
        # {name} is expected but not provided
        result = i18n.t("hello")
        # Should return the template string unformatted (or handle gracefully)
        assert result is not None
        assert isinstance(result, str)

    def test_extra_format_args(self):
        """t() with unused format arguments."""
        import services.i18n as i18n
        result = i18n.t("hello", name="World", extra="Ignored")
        assert "World" in result

    def test_numeric_format_args(self):
        """t() with numeric format arguments."""
        import services.i18n as i18n
        result = i18n.t("price", amount=1234.56)
        assert "1234.56" in result

    def test_none_format_arg(self):
        """t() with None format argument."""
        import services.i18n as i18n
        result = i18n.t("hello", name=None)
        assert result is not None

    def test_html_in_format_args(self):
        """t() with HTML/script content in format args (no injection)."""
        import services.i18n as i18n
        xss = "<script>alert('xss')</script>"
        result = i18n.t("hello", name=xss)
        assert xss in result

    def test_sql_injection_in_format_args(self):
        """t() with SQL injection in format args."""
        import services.i18n as i18n
        sql = "'; DROP TABLE users; --"
        result = i18n.t("hello", name=sql)
        assert sql in result

    def test_path_traversal_in_format_args(self):
        """t() with path traversal in format args."""
        import services.i18n as i18n
        traversal = "../../../etc/passwd"
        result = i18n.t("hello", name=traversal)
        assert traversal in result


# ═════════════════════════════════════════════════════════════════════════════
# Concurrent language switches
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationI18nConcurrency:
    """Concurrent language switches during t() calls don't crash."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import services.i18n as i18n
        i18n._translations = {
            "en": {"greeting": "Hello"},
            "fr": {"greeting": "Bonjour"},
            "de": {"greeting": "Hallo"},
            "es": {"greeting": "Hola"},
        }
        i18n._current_lang = "en"
        yield
        i18n._translations = {}
        i18n._current_lang = "en"

    def test_concurrent_switches_during_translate(self):
        """Concurrent set_language and t() calls do not crash."""
        import services.i18n as i18n

        results = []
        errors = []

        def translate_worker():
            for _ in range(50):
                try:
                    for lang in ["en", "fr", "de", "es"]:
                        i18n.set_language(lang)
                        result = i18n.t("greeting")
                        results.append((lang, result))
                except Exception as e:
                    errors.append(e)

        def switch_worker():
            for _ in range(50):
                try:
                    for lang in ["de", "es", "fr", "en"]:
                        i18n.set_language(lang)
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=translate_worker),
            threading.Thread(target=switch_worker),
            threading.Thread(target=translate_worker),
            threading.Thread(target=switch_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrency errors: {errors}"
        assert len(results) > 0, "No translation results collected"


# ═════════════════════════════════════════════════════════════════════════════
# Language display name edge cases
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationI18nDisplayNames:
    """get_language_display_name handles edge cases."""

    @pytest.mark.parametrize("code, expected", [
        ("en", "English"),
        ("fr", "Français"),
        ("zz", "zz"),  # unknown code returns itself
        ("", ""),       # empty string returns itself
        (None, None),   # None returns None (or crashes gracefully)
    ])
    def test_display_name_edge_cases(self, code, expected):
        import services.i18n as i18n
        try:
            result = i18n.get_language_display_name(code)
            if code is None:
                assert result is None or result == "None"
            else:
                assert result == expected
        except (TypeError, AttributeError):
            if code is None:
                pass  # None may be acceptable to fail
            else:
                raise


# ═════════════════════════════════════════════════════════════════════════════
# Listeners
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationI18nListeners:
    """i18n listener registration and failure handling."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import services.i18n as i18n
        i18n._translations = {"en": {"hello": "Hello"}}
        i18n._current_lang = "en"
        i18n._listeners = []
        yield
        i18n._listeners = []
        i18n._translations = {}
        i18n._current_lang = "en"

    def test_listener_that_raises(self):
        """A listener that raises an exception does not break the system."""
        import services.i18n as i18n

        def failing_listener(lang):
            raise RuntimeError("Listener failed!")

        i18n.register_listener(failing_listener)
        # Should not crash despite listener failure
        i18n.set_language("en")
        # Language should still be 'en'
        assert i18n.get_language() == "en"

    def test_unregister_nonexistent_listener(self):
        """Unregistering a listener that was never registered."""
        import services.i18n as i18n

        def dummy(lang):
            pass

        # Should not crash or raise
        i18n.unregister_listener(dummy)

    def test_multiple_listeners_some_fail(self):
        """Multiple listeners where some fail — surviving ones still called."""
        import services.i18n as i18n

        calls = []

        def good_listener(lang):
            calls.append(lang)

        def bad_listener(lang):
            raise ValueError("Boom!")

        i18n.register_listener(good_listener)
        i18n.register_listener(bad_listener)
        i18n.set_language("en")

        # The good listener should have been called despite the bad one failing
        assert len(calls) >= 1
