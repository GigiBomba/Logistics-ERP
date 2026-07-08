"""Tests for the i18n translation module.

Covers:
  - load_translations() — loading from files, fallback behavior
  - t() / translate() — lookup, missing keys, fallback to English
  - set_language() / get_language() — language switching
  - _translations and _current_lang globals (reset via conftest)
  - Edge cases: empty translations, unknown language, missing key
  - Listener registration and notification
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

import services.i18n as i18n


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_i18n_globals():
    """Ensure module globals are clean before each test.

    The conftest reset_singletons fixture also does this, but having it
    here makes the dependency explicit and guarantees isolation.
    """
    old_translations = i18n._translations
    old_lang = i18n._current_lang
    old_listeners = list(i18n._listeners)
    i18n._translations = {}
    i18n._current_lang = "en"
    i18n._listeners = []
    yield
    i18n._translations = old_translations
    i18n._current_lang = old_lang
    i18n._listeners = old_listeners


@pytest.fixture
def en_translations():
    """Seed the module with a minimal English translation set."""
    i18n._translations["en"] = {
        "greeting": "Hello",
        "farewell": "Goodbye",
        "placeholder": "Value: {value}",
        "nested.key": "Nested value",
    }


@pytest.fixture
def en_ro_translations(en_translations):
    """Seed English + Romanian translations."""
    i18n._translations["ro"] = {
        "greeting": "Salut",
        "farewell": "La revedere",
    }


# ── load_translations() ─────────────────────────────────────────────

class TestLoadTranslations:
    def test_loads_valid_json_files(self, tmp_path):
        """load_translations reads .json files from the translations dir."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text(json.dumps({"key": "value"}), encoding="utf-8")
        (lang_dir / "ro.json").write_text(json.dumps({"salut": "Salut"}), encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.load_translations()

        assert "en" in i18n._translations
        assert "ro" in i18n._translations
        assert i18n._translations["en"]["key"] == "value"

    def test_ensures_en_fallback_when_no_files(self, tmp_path):
        """When no files exist, 'en' gets an empty dict."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.load_translations()

        assert i18n._translations == {"en": {}}

    def test_skips_invalid_json(self, tmp_path):
        """Invalid JSON files are skipped gracefully."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text("not json", encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.load_translations()

        assert i18n._translations == {"en": {}}

    def test_missing_en_uses_any_available(self, tmp_path):
        """If en.json is missing but others exist, use first available as English."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "fr.json").write_text(json.dumps({"hello": "Bonjour"}), encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.load_translations()

        assert "en" in i18n._translations
        assert i18n._translations["en"].get("hello") == "Bonjour"

    def test_flat_nested_keys(self, tmp_path):
        """Nested JSON keys are flattened to dot-separated keys."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text(
            json.dumps({"menu": {"file": "File", "edit": "Edit"}}), encoding="utf-8"
        )

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.load_translations()

        assert i18n._translations["en"]["menu.file"] == "File"
        assert i18n._translations["en"]["menu.edit"] == "Edit"

    def test_non_en_languages_fallback_to_en_keys(self, tmp_path):
        """Non-English translations inherit missing keys from English."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text(json.dumps({"a": "A_en", "b": "B_en"}), encoding="utf-8")
        (lang_dir / "ro.json").write_text(json.dumps({"a": "A_ro"}), encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.load_translations()

        assert i18n._translations["ro"]["a"] == "A_ro"
        assert i18n._translations["ro"]["b"] == "B_en"


# ── t() / translate() ───────────────────────────────────────────────

class TestTranslate:
    def test_basic_translation(self, en_ro_translations):
        i18n._current_lang = "ro"
        assert i18n.t("greeting") == "Salut"

    def test_fallback_to_english_when_key_missing(self, en_ro_translations):
        i18n._current_lang = "ro"
        # 'nested.key' only exists in English
        assert i18n.t("nested.key") == "Nested value"

    def test_returns_key_when_nothing_found(self, en_ro_translations):
        i18n._current_lang = "ro"
        assert i18n.t("nonexistent") == "nonexistent"

    def test_returns_default_when_specified(self, en_ro_translations):
        i18n._current_lang = "ro"
        assert i18n.t("missing", default="Default") == "Default"

    def test_format_placeholders(self, en_translations):
        assert i18n.t("placeholder", value="42") == "Value: 42"

    def test_format_with_positional_args(self, en_translations):
        i18n._translations["en"]["pos"] = "First: {} Second: {}"
        assert i18n.t("pos", "A", "B") == "First: A Second: B"

    def test_format_failure_returns_unformatted(self, en_translations):
        """If format fails (e.g. missing kwarg), return the raw message."""
        result = i18n.t("placeholder")  # no value provided
        assert result == "Value: {value}"  # format fails but returns raw

    def test_translation_in_current_lang_only(self):
        """Only the current language + English are consulted."""
        i18n._translations["en"] = {"greeting": "Hello"}
        i18n._translations["fr"] = {"greeting": "Bonjour"}
        i18n._current_lang = "fr"
        assert i18n.t("greeting") == "Bonjour"

    def test_missing_key_with_empty_translations(self):
        """With empty translations dict, still returns key."""
        i18n._translations = {}
        assert i18n.t("some.key") == "some.key"


# ── set_language() / get_language() ─────────────────────────────────

class TestSetLanguage:
    def test_get_language_default(self):
        assert i18n.get_language() == "en"

    def test_set_language_valid(self, en_ro_translations):
        i18n.set_language("ro")
        assert i18n.get_language() == "ro"

    def test_set_language_unknown_falls_back_to_en(self, en_translations):
        """Setting an unknown language falls back to 'en'."""
        i18n.set_language("xx")
        assert i18n.get_language() == "en"

    def test_set_language_idempotent(self, en_translations):
        """Setting the same language again does not write to file."""
        i18n.set_language("en")
        with patch.object(i18n, "_LANG_FILE", "nope"):
            # Should not raise — early return for no-change
            i18n.set_language("en")

    def test_set_language_triggers_listeners(self, en_ro_translations):
        listener = MagicMock()
        i18n.register_listener(listener)
        i18n.set_language("ro")
        listener.assert_called_once_with("ro")

    def test_set_language_handles_listener_failure(self, en_ro_translations):
        """A failing listener does not prevent other listeners from being called."""
        good = MagicMock()
        bad = MagicMock(side_effect=RuntimeError("boom"))
        i18n.register_listener(bad)
        i18n.register_listener(good)
        i18n.set_language("ro")
        good.assert_called_once_with("ro")

    def test_set_language_unregister_listener(self, en_ro_translations):
        listener = MagicMock()
        i18n.register_listener(listener)
        i18n.unregister_listener(listener)
        i18n.set_language("ro")
        listener.assert_not_called()

    def test_set_language_persists_to_file(self, en_translations):
        """set_language writes to _LANG_FILE."""
        with patch("builtins.open", mock_open()) as m_open:
            i18n.set_language("en")
            m_open.assert_called_once()

    def test_set_language_file_write_failure_does_not_raise(self, en_ro_translations):
        """If writing to _LANG_FILE fails, set_language still switches."""
        with patch.object(i18n, "_LANG_FILE", "/nonexistent/dir/lang.txt"):
            i18n.set_language("ro")
        assert i18n.get_language() == "ro"


# ── get_available_languages() ──────────────────────────────────────

class TestGetAvailableLanguages:
    def test_returns_en_when_dir_empty(self, tmp_path):
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            codes = i18n.get_available_languages()
        assert codes == ["en"]

    def test_lists_json_files(self, tmp_path):
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text("{}")
        (lang_dir / "ro.json").write_text("{}")
        (lang_dir / "fr.json").write_text("{}")
        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            codes = i18n.get_available_languages()
        assert "en" in codes
        assert "ro" in codes
        assert "fr" in codes

    def test_ensures_en_is_first(self, tmp_path):
        """Even if en.json is missing, 'en' is inserted at position 0."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "ro.json").write_text("{}")
        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            codes = i18n.get_available_languages()
        assert codes[0] == "en"


# ── Helper functions ────────────────────────────────────────────────

class TestHelpers:
    def test_get_translations_direct(self, en_ro_translations):
        result = i18n._get_translations("ro")
        assert result["greeting"] == "Salut"

    def test_get_translations_fallback_to_en(self, en_ro_translations):
        result = i18n._get_translations("fr")
        assert result["greeting"] == "Hello"

    def test_get_language_display_name(self):
        assert i18n.get_language_display_name("ro") == "Română"
        assert i18n.get_language_display_name("xx") == "xx"

    def test_register_and_unregister_listener(self):
        listener = MagicMock()
        i18n.register_listener(listener)
        assert listener in i18n._listeners
        i18n.unregister_listener(listener)
        assert listener not in i18n._listeners

    def test_unregister_nonexistent_listener(self):
        """Unregistering a listener that was never added does not raise."""
        listener = MagicMock()
        i18n.unregister_listener(listener)  # should not raise


# ── init_language() ─────────────────────────────────────────────────

class TestInitLanguage:
    def test_loads_persisted_language(self, tmp_path):
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text(json.dumps({"k": "v"}), encoding="utf-8")
        (lang_dir / "ro.json").write_text(json.dumps({"k": "v_ro"}), encoding="utf-8")

        lang_file = tmp_path / "data" / "lang.txt"
        lang_file.parent.mkdir(parents=True, exist_ok=True)
        lang_file.write_text("ro", encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)), \
             patch.object(i18n, "_LANG_FILE", str(lang_file)):
            i18n.init_language()

        assert i18n.get_language() == "ro"

    def test_init_with_missing_lang_file(self, tmp_path):
        """When lang.txt is missing, defaults to English."""
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text(json.dumps({"k": "v"}), encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)):
            i18n.init_language()

        assert i18n.get_language() == "en"

    def test_init_with_broken_lang_file_uses_en(self, tmp_path):
        lang_dir = tmp_path / "data" / "translations"
        lang_dir.mkdir(parents=True)
        (lang_dir / "en.json").write_text(json.dumps({"k": "v"}), encoding="utf-8")

        lang_file = tmp_path / "data" / "lang.txt"
        lang_file.parent.mkdir(parents=True, exist_ok=True)
        lang_file.write_text("unsupported_lang", encoding="utf-8")

        with patch.object(i18n, "_TRANSLATIONS_DIR", str(lang_dir)), \
             patch.object(i18n, "_LANG_FILE", str(lang_file)):
            i18n.init_language()

        assert i18n.get_language() == "en"
