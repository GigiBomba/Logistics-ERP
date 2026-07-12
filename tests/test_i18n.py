"""Comprehensive unit tests for ``services/i18n.py``.

Covers all public functions, edge cases (empty translations, invalid JSON,
missing files), and error handling paths.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, mock_open, patch

import services.i18n as i18n


# ─── Helpers ──────────────────────────────────────────────────────────

def _make_i18n_module_patch(translations_dir: str = "mock/data/translations",
                             lang_file: str = "mock/data/lang.txt"):
    """Return a dict of overrides to patch ``i18n`` module constants."""
    return {
        "_TRANSLATIONS_DIR": translations_dir,
        "_LANG_FILE": lang_file,
    }


def _reset_globals():
    """Reset i18n module globals before each test."""
    i18n._translations = {}
    i18n._current_lang = "en"
    i18n._listeners.clear()


# ─── _flatten ─────────────────────────────────────────────────────────

class TestFlatten:
    """Unit tests for the private ``_flatten`` helper."""

    def setup_method(self):
        _reset_globals()

    def test_empty_dict(self):
        out: dict[str, str] = {}
        i18n._flatten({}, "", out)
        assert out == {}

    def test_single_key(self):
        out: dict[str, str] = {}
        i18n._flatten({"a": "1"}, "", out)
        assert out == {"a": "1"}

    def test_nested_dict(self):
        out: dict[str, str] = {}
        i18n._flatten({"a": {"b": "1", "c": "2"}}, "", out)
        assert out == {"a.b": "1", "a.c": "2"}

    def test_deeply_nested(self):
        out: dict[str, str] = {}
        i18n._flatten({"a": {"b": {"c": "deep"}}}, "", out)
        assert out == {"a.b.c": "deep"}

    def test_non_dict_values_converted_to_str(self):
        out: dict[str, str] = {}
        i18n._flatten({"int": 42, "float": 3.14, "none": None, "flag": True}, "", out)
        assert out == {"int": "42", "float": "3.14", "none": "None", "flag": "True"}

    def test_mixed_structure(self):
        out: dict[str, str] = {}
        i18n._flatten({
            "title": "Hello",
            "menu": {
                "file": "File",
                "edit": {"cut": "Cut", "paste": "Paste"},
            },
            "version": 1,
        }, "", out)
        assert out == {
            "title": "Hello",
            "menu.file": "File",
            "menu.edit.cut": "Cut",
            "menu.edit.paste": "Paste",
            "version": "1",
        }

    def test_prefix_respected(self):
        out: dict[str, str] = {}
        i18n._flatten({"a": "1"}, "root", out)
        assert out == {"root.a": "1"}

    def test_multiple_calls_accumulate(self):
        out: dict[str, str] = {}
        i18n._flatten({"a": "1"}, "", out)
        i18n._flatten({"b": "2"}, "", out)
        assert out == {"a": "1", "b": "2"}


# ─── _load_file ───────────────────────────────────────────────────────

class TestLoadFile:
    """Unit tests for the private ``_load_file`` helper."""

    def setup_method(self):
        _reset_globals()

    def test_load_valid_file(self):
        """Valid JSON file returns flattened translations."""
        m = mock_open(read_data='{"greeting": "Hello", "nested": {"key": "val"}}')
        with patch("builtins.open", m), \
             patch("os.path.isfile", return_value=True):
            result = i18n._load_file("en")
        assert result == {"greeting": "Hello", "nested.key": "val"}

    def test_load_valid_file_non_string_values(self):
        """Non-string values like integers are converted to str."""
        m = mock_open(read_data='{"count": 5, "ratio": 0.5}')
        with patch("builtins.open", m), \
             patch("os.path.isfile", return_value=True):
            result = i18n._load_file("en")
        assert result == {"count": "5", "ratio": "0.5"}

    def test_file_not_found_returns_empty(self):
        """Missing file returns {}."""
        with patch("os.path.isfile", return_value=False):
            result = i18n._load_file("nonexistent")
        assert result == {}

    def test_invalid_json_returns_empty(self):
        """Invalid JSON content returns {} and logs a warning."""
        m = mock_open(read_data="{invalid json}")
        with patch("builtins.open", m), \
             patch("os.path.isfile", return_value=True), \
             patch.object(i18n.logger, "warning") as mock_warn:
            result = i18n._load_file("fr")
        assert result == {}
        mock_warn.assert_called_once()
        # The logger receives a format string as first arg, then value args
        call_args = mock_warn.call_args[0]
        assert "Skipping" in call_args[0]
        assert call_args[1] == "fr"

    def test_json_decode_error_logs_line_number(self):
        """JSONDecodeError logs the error message and line number."""
        m = mock_open(read_data='{"a": 1\n"b": 2}')
        with patch("builtins.open", m), \
             patch("os.path.isfile", return_value=True), \
             patch.object(i18n.logger, "warning") as mock_warn:
            result = i18n._load_file("de")
        assert result == {}
        mock_warn.assert_called_once()
        call_args = mock_warn.call_args[0]
        assert "Skipping" in call_args[0]
        assert call_args[1] == "de"
        # Third arg is e.msg, fourth is e.lineno (both non-None for JSONDecodeError)
        assert call_args[2] is not None
        assert call_args[3] is not None

    def test_generic_exception_returns_empty(self):
        """An OSError (e.g. permission denied) returns {}."""
        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", side_effect=PermissionError("denied")), \
             patch.object(i18n.logger, "warning") as mock_warn:
            result = i18n._load_file("es")
        assert result == {}
        mock_warn.assert_called_once()
        call_args = mock_warn.call_args[0]
        assert "Skipping" in call_args[0]
        assert call_args[1] == "es"

    def test_utf8_bom_is_stripped(self):
        """File is opened with utf-8-sig encoding to handle BOM."""
        m = mock_open(read_data='{"key": "value"}')
        with patch("builtins.open", m) as mock_file, \
             patch("os.path.isfile", return_value=True):
            i18n._load_file("en")
        # Verify utf-8-sig encoding is used
        call_args = mock_file.call_args
        filepath = call_args[0][0] if call_args[0] else ""
        assert filepath.endswith("en.json")
        kwargs = call_args[1]
        assert kwargs.get("encoding") == "utf-8-sig"

    def test_empty_json_object(self):
        """Empty JSON object {} returns empty dict."""
        m = mock_open(read_data="{}")
        with patch("builtins.open", m), \
             patch("os.path.isfile", return_value=True):
            result = i18n._load_file("en")
        assert result == {}


# ─── load_translations ────────────────────────────────────────────────

class TestLoadTranslations:
    """Tests for the main ``load_translations()`` function."""

    def setup_method(self):
        _reset_globals()

    def test_no_translation_dir_populates_empty_en(self):
        """If no translations exist, _translations gets empty 'en' dict."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch.object(i18n.logger, "warning") as mock_warn:
            i18n.load_translations()
        assert i18n._translations == {"en": {}}
        mock_warn.assert_called_once_with(
            "No translations loaded — using empty fallback"
        )

    def test_empty_directory_populates_empty_en(self):
        """Empty translations dir yields {'en': {}}."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=False), \
             patch("os.listdir", return_value=[]), \
             patch.object(i18n.logger, "warning") as mock_warn:
            i18n.load_translations()
        assert i18n._translations == {"en": {}}
        mock_warn.assert_called_once_with(
            "No translations loaded — using empty fallback"
        )

    def test_single_language_loaded(self):
        """Single language file is loaded successfully."""
        m = mock_open(read_data='{"greeting": "Hello"}')
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json"]), \
             patch("builtins.open", m):
            i18n.load_translations()
        assert "en" in i18n._translations
        assert i18n._translations["en"]["greeting"] == "Hello"

    def test_multiple_languages_loaded(self):
        """Multiple language files are loaded and merged with English fallback."""
        def _mock_open_side_effect(*args, **kwargs):
            filepath = args[0]
            if "en.json" in filepath:
                return mock_open(read_data='{"greeting": "Hello", "farewell": "Goodbye"}').return_value
            elif "fr.json" in filepath:
                return mock_open(read_data='{"greeting": "Bonjour"}').return_value
            return mock_open(read_data="{}").return_value

        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json", "fr.json"]), \
             patch("builtins.open", side_effect=_mock_open_side_effect):
            i18n.load_translations()

        assert "en" in i18n._translations
        assert "fr" in i18n._translations
        assert i18n._translations["en"]["greeting"] == "Hello"
        assert i18n._translations["en"]["farewell"] == "Goodbye"
        # French gets English fallback for missing keys
        assert i18n._translations["fr"]["greeting"] == "Bonjour"
        assert i18n._translations["fr"]["farewell"] == "Goodbye"

    def test_non_en_fallback_when_en_missing(self):
        """If en.json is absent but other langs exist, the first lang becomes 'en'."""
        def _mock_open_side_effect(*args, **kwargs):
            filepath = args[0]
            if "fr.json" in filepath:
                return mock_open(read_data='{"greeting": "Bonjour"}').return_value
            return mock_open(read_data="{}").return_value

        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["fr.json"]), \
             patch("builtins.open", side_effect=_mock_open_side_effect):
            i18n.load_translations()

        assert "en" in i18n._translations
        # en gets a copy of fr's translations as fallback
        assert i18n._translations["en"]["greeting"] == "Bonjour"

    def test_failed_files_excluded(self):
        """Files that fail to load (invalid JSON) are listed as failed."""
        def _mock_open_side_effect(*args, **kwargs):
            filepath = args[0]
            if "en.json" in filepath:
                return mock_open(read_data='{"a": "1"}').return_value
            elif "bad.json" in filepath:
                return mock_open(read_data="not json").return_value
            return mock_open(read_data="{}").return_value

        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json", "bad.json"]), \
             patch("builtins.open", side_effect=_mock_open_side_effect), \
             patch.object(i18n.logger, "info") as mock_info:
            i18n.load_translations()

        assert "en" in i18n._translations
        assert "bad" not in i18n._translations
        mock_info.assert_called_once()
        log_msg = mock_info.call_args[0][0]
        assert "Failed: ['bad']" in log_msg or "bad" in str(mock_info.call_args)

    def test_english_always_has_keys(self):
        """English translations are never merged with fallback (they are the base)."""
        m = mock_open(read_data='{"a": "1"}')
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json", "fr.json"]), \
             patch("builtins.open", m):
            i18n.load_translations()

        # en should only have its own key "a"
        # (m returns the same file for all because side_effect not used)
        assert i18n._translations["en"] == {"a": "1"}

    def test_makedirs_called(self):
        """os.makedirs is called for _TRANSLATIONS_DIR (called once by
        load_translations and once by get_available_languages)."""
        with patch("os.makedirs") as mock_makedirs, \
             patch("os.path.isdir", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch("os.listdir", return_value=[]):
            i18n.load_translations()
        # Called by both load_translations and get_available_languages
        assert mock_makedirs.call_count >= 1
        mock_makedirs.assert_any_call(
            i18n._TRANSLATIONS_DIR, exist_ok=True
        )


# ─── t() ──────────────────────────────────────────────────────────────

class TestT:
    """Tests for the ``t()`` translation function."""

    def setup_method(self):
        _reset_globals()
        # Pre-populate translations for lookup tests
        i18n._translations = {
            "en": {"greeting": "Hello", "farewell": "Goodbye",
                   "placeholder": "Hello {name}", "pos": "Items: {0} and {1}",
                   "percent": "{}% complete"},
            "fr": {"greeting": "Bonjour"},
        }

    def test_basic_lookup_current_lang(self):
        """Key found in current language returns its value."""
        assert i18n.t("greeting") == "Hello"

    def test_fallback_to_english(self):
        """Key missing in current lang but present in English uses English."""
        i18n._current_lang = "fr"
        assert i18n.t("farewell") == "Goodbye"

    def test_fallback_to_key_when_no_default(self):
        """Key missing everywhere returns the key itself when no default."""
        i18n._current_lang = "fr"
        assert i18n.t("nonexistent") == "nonexistent"

    def test_fallback_to_default(self):
        """Key missing everywhere returns the provided default."""
        i18n._current_lang = "fr"
        assert i18n.t("nonexistent", default="DefaultVal") == "DefaultVal"

    def test_format_keyword_args(self):
        """Keyword format placeholders are substituted."""
        assert i18n.t("placeholder", name="World") == "Hello World"

    def test_format_positional_args(self):
        """Positional format placeholders are substituted."""
        assert i18n.t("pos", None, "A", "B") == "Items: A and B"

    def test_format_automatic_positional(self):
        """Automatic {} placeholders with positional args."""
        assert i18n.t("percent", None, 75) == "75% complete"

    def test_format_error_falls_back_to_raw(self):
        """Format errors (missing key/index) return unformatted string."""
        with patch.object(i18n.logger, "warning") as mock_warn:
            result = i18n.t("placeholder", wrong_arg="val")
        assert result == "Hello {name}"  # Unformatted fallback
        mock_warn.assert_called_once()

    def test_format_index_error_falls_back(self):
        """IndexError in format returns raw string."""
        with patch.object(i18n.logger, "warning"):
            result = i18n.t("pos")
        # No args provided for {0} and {1}
        assert result == "Items: {0} and {1}"

    def test_default_with_format(self):
        """Default value can also have format placeholders."""
        result = i18n.t("missing.key", default="Default {name}", name="Value")
        assert result == "Default Value"

    def test_empty_translations_returns_key(self):
        """When no translations loaded, returns key."""
        i18n._translations = {}
        assert i18n.t("anything") == "anything"

    def test_empty_translations_with_default(self):
        """When no translations loaded, returns default."""
        i18n._translations = {}
        assert i18n.t("anything", default="fallback") == "fallback"

    def test_current_lang_is_nonexistent(self):
        """When _current_lang points to a lang not in _translations."""
        i18n._current_lang = "de"
        # Falls back to en which has "greeting"
        assert i18n.t("greeting") == "Hello"
        # Falls back to key
        assert i18n.t("nobody") == "nobody"

    def test_none_default_is_treated_as_none(self):
        """Explicit None default should fall through to key."""
        result = i18n.t("missing.key", default=None)
        assert result == "missing.key"

    def test_logger_warning_on_format_failure(self):
        """Format failure logs a warning with the key and error details."""
        with patch.object(i18n.logger, "warning") as mock_warn:
            i18n.t("placeholder", unknown="x")
        mock_warn.assert_called_once()
        call_args = mock_warn.call_args[0]
        assert "i18n format failed for" in call_args[0]
        assert call_args[1] == "placeholder"

    def test_empty_string_value(self):
        """Empty string translation value is returned as-is."""
        i18n._translations["en"]["empty_key"] = ""
        assert i18n.t("empty_key") == ""

    def test_value_is_str_even_if_file_had_nonstring(self):
        """_flatten converts to str, so t() always returns str."""
        i18n._translations["en"]["num"] = "42"
        assert isinstance(i18n.t("num"), str)

    def test_current_lang_found_does_not_access_en(self):
        """When key is found in current lang, English dict is not accessed
        (no fallback merge needed)."""
        # This is an internal behavior test: t() first checks _current_lang
        # then falls back to "en". We verify by removing "en" after setting
        # current lang.
        i18n._current_lang = "fr"
        i18n._translations.pop("en", None)
        assert i18n.t("greeting") == "Bonjour"


# ─── set_language ─────────────────────────────────────────────────────

class TestSetLanguage:
    """Tests for ``set_language()``."""

    def setup_method(self):
        _reset_globals()

    def test_set_language_updates_current(self):
        """Setting a valid language changes _current_lang."""
        i18n._translations = {"en": {}, "de": {}}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert i18n._current_lang == "de"

    def test_unknown_language_falls_back_to_en(self):
        """Setting a language not in _translations falls back to 'en'."""
        i18n._translations = {"en": {}}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug") as mock_debug, \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert i18n._current_lang == "en"
        # debug is called for: falling back, then again for already 'en' — skipping
        falling_back = any(
            "falling back to 'en'" in c[0][0]
            for c in mock_debug.call_args_list
        )
        assert falling_back

    def test_set_en_always_works(self):
        """Setting 'en' always works even if 'en' not in _translations."""
        i18n._translations = {}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("en")
        assert i18n._current_lang == "en"

    def test_listeners_notified(self):
        """Registered listeners are called with the new language."""
        i18n._translations = {"en": {}, "de": {}}
        listener = MagicMock()
        i18n.register_listener(listener)
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        listener.assert_called_once_with("de")

    def test_listeners_not_notified_on_same_lang(self):
        """Setting the same language twice does not notify listeners."""
        i18n._translations = {"en": {}, "de": {}}
        listener = MagicMock()
        i18n.register_listener(listener)
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug") as mock_debug, \
             patch.object(i18n.logger, "info"):
            # First set to de
            i18n.set_language("de")
            listener.reset_mock()
            # Set to de again
            i18n.set_language("de")
        listener.assert_not_called()
        # Should log "already 'de' — skipping"
        found_skip = any("skipping" in c[0][0].lower()
                         for c in mock_debug.call_args_list)
        assert found_skip

    def test_lang_file_written(self):
        """Language preference is persisted to _LANG_FILE."""
        i18n._translations = {"en": {}, "fr": {}}
        m = mock_open()
        with patch("builtins.open", m) as mock_file, \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("fr")
        # open should have been called for writing
        write_calls = [c for c in mock_file.call_args_list
                       if c[0][0] == i18n._LANG_FILE and "w" in c[1].get("mode", "w")]
        assert len(write_calls) >= 1
        handle = m()
        handle.write.assert_called_once_with("fr")

    def test_lang_file_write_error_does_not_raise(self):
        """If writing to lang file fails, set_language still succeeds."""
        i18n._translations = {"en": {}, "de": {}}
        listener = MagicMock()
        i18n.register_listener(listener)
        with patch("builtins.open", side_effect=OSError("disk full")), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert i18n._current_lang == "de"
        listener.assert_called_once_with("de")

    def test_listener_exception_does_not_block_others(self):
        """A failing listener does not prevent other listeners from being called."""
        i18n._translations = {"en": {}, "es": {}}
        good_listener = MagicMock()
        bad_listener = MagicMock(side_effect=ValueError("oops"))
        i18n.register_listener(good_listener)
        i18n.register_listener(bad_listener)
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"), \
             patch.object(i18n.logger, "warning") as mock_warn:
            i18n.set_language("es")
        good_listener.assert_called_once_with("es")
        bad_listener.assert_called_once_with("es")
        mock_warn.assert_called_once()
        assert "listener" in mock_warn.call_args[0][0]

    def test_logs_language_switch_with_duration(self):
        """set_language logs the language switch and timing info."""
        i18n._translations = {"en": {}, "de": {}}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info") as mock_info:
            i18n.set_language("de")
        mock_info.assert_called_once()
        call_args = mock_info.call_args[0]
        # Format string with %s placeholders for old/new lang
        assert "%s->%s" in call_args[0]
        assert call_args[1] == "en"
        assert call_args[2] == "de"
        assert "listener" in call_args[0]

    def test_skip_logs_debug_when_already_set(self):
        """Setting the current language again logs a debug skip message."""
        i18n._translations = {"en": {}}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug") as mock_debug, \
             patch.object(i18n.logger, "info"):
            i18n.set_language("en")
        assert any("skipping" in c[0][0].lower()
                   for c in mock_debug.call_args_list)


# ─── get_language ─────────────────────────────────────────────────────

class TestGetLanguage:
    """Tests for ``get_language()``."""

    def setup_method(self):
        _reset_globals()

    def test_default_is_en(self):
        """Default language is 'en'."""
        assert i18n.get_language() == "en"

    def test_after_set_returns_new_lang(self):
        """After set_language, get_language returns the new value."""
        i18n._translations = {"en": {}, "de": {}}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert i18n.get_language() == "de"


# ─── get_available_languages ──────────────────────────────────────────

class TestGetAvailableLanguages:
    """Tests for ``get_available_languages()``."""

    def setup_method(self):
        _reset_globals()

    def test_returns_en_when_dir_missing(self):
        """If translations dir does not exist, returns ['en']."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=False):
            result = i18n.get_available_languages()
        assert result == ["en"]

    def test_returns_en_when_dir_empty(self):
        """If translation dir is empty, returns ['en']."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=[]):
            result = i18n.get_available_languages()
        assert result == ["en"]

    def test_returns_codes_from_json_files(self):
        """Only .json files are listed, extension is stripped."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["en.json", "fr.json", "de.json", "notes.txt"]):
            result = i18n.get_available_languages()
        assert result == ["de", "en", "fr"]  # sorted

    def test_en_prepended_if_not_in_list(self):
        """'en' is always first, even if en.json is missing."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["fr.json", "de.json"]):
            result = i18n.get_available_languages()
        assert result == ["en", "de", "fr"]

    def test_en_deduped_when_present(self):
        """If en.json is present, 'en' appears only once."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["en.json", "fr.json"]):
            result = i18n.get_available_languages()
        assert result == ["en", "fr"]
        assert result.count("en") == 1

    def test_makedirs_called_before_listing(self):
        """os.makedirs is called before checking for the directory."""
        with patch("os.makedirs") as mock_makedirs, \
             patch("os.path.isdir") as mock_isdir:
            mock_isdir.return_value = False
            i18n.get_available_languages()
        mock_makedirs.assert_called_once_with(
            i18n._TRANSLATIONS_DIR, exist_ok=True
        )


# ─── _get_translations ────────────────────────────────────────────────

class TestGetTranslations:
    """Tests for the private ``_get_translations()`` helper."""

    def setup_method(self):
        _reset_globals()
        i18n._translations = {
            "en": {"a": "1", "b": "2"},
            "fr": {"a": "un"},
        }

    def test_returns_exact_lang(self):
        """Returns the full dict for the requested language."""
        result = i18n._get_translations("fr")
        assert result == {"a": "un"}

    def test_falls_back_to_english(self):
        """Falls back to English dict when language not loaded."""
        result = i18n._get_translations("de")
        assert result == {"a": "1", "b": "2"}

    def test_falls_back_to_empty_when_no_en(self):
        """Returns {} when neither lang nor en is loaded."""
        i18n._translations = {}
        result = i18n._get_translations("de")
        assert result == {}

    def test_returns_en_for_en(self):
        """Requesting 'en' returns the English dict."""
        result = i18n._get_translations("en")
        assert result == {"a": "1", "b": "2"}


# ─── get_language_display_name ────────────────────────────────────────

class TestGetLanguageDisplayName:
    """Tests for ``get_language_display_name()``."""

    def setup_method(self):
        _reset_globals()

    def test_known_code_returns_name(self):
        """Known language code returns its display name."""
        assert i18n.get_language_display_name("en") == "English"
        assert i18n.get_language_display_name("fr") == "Français"
        assert i18n.get_language_display_name("de") == "Deutsch"

    def test_unknown_code_returns_code(self):
        """Unknown language code returns the code itself."""
        assert i18n.get_language_display_name("xx") == "xx"
        assert i18n.get_language_display_name("") == ""

    def test_all_language_names_defined(self):
        """Every key in LANGUAGE_NAMES has a non-empty display name."""
        for code, name in i18n.LANGUAGE_NAMES.items():
            assert isinstance(code, str) and code
            assert isinstance(name, str) and name

    def test_language_names_count(self):
        """LANGUAGE_NAMES has expected number of entries."""
        assert len(i18n.LANGUAGE_NAMES) >= 20


# ─── register_listener / unregister_listener ──────────────────────────

class TestListeners:
    """Tests for listener registration and removal."""

    def setup_method(self):
        _reset_globals()

    def test_register_listener_adds_to_list(self):
        """register_listener appends the callback to _listeners."""
        cb = lambda x: None
        result = i18n.register_listener(cb)
        assert cb in i18n._listeners
        assert result is cb  # Returns the callback

    def test_listener_called_on_language_change(self):
        """Registered listener is called when language changes."""
        i18n._translations = {"en": {}, "de": {}}
        calls = []
        def listener(lang):
            calls.append(lang)
        i18n.register_listener(listener)
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert calls == ["de"]

    def test_multiple_listeners_all_called(self):
        """Multiple listeners are all called on language change."""
        i18n._translations = {"en": {}, "fr": {}}
        calls = []
        def make_listener():
            def listener(lang):
                calls.append(lang)
            return listener
        i18n.register_listener(make_listener())
        i18n.register_listener(make_listener())
        i18n.register_listener(make_listener())
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("fr")
        assert len(calls) == 3
        assert all(c == "fr" for c in calls)

    def test_unregister_listener_removes(self):
        """unregister_listener removes the callback."""
        cb = lambda x: None
        i18n.register_listener(cb)
        i18n.unregister_listener(cb)
        assert cb not in i18n._listeners

    def test_unregister_nonexistent_does_not_raise(self):
        """Unregistering a callback not in the list is a no-op."""
        i18n.unregister_listener(lambda x: None)  # should not raise

    def test_unregister_multiple_identical(self):
        """If same callback registered twice, unregister removes only one."""
        calls = []
        def cb(lang):
            calls.append(lang)
        i18n.register_listener(cb)
        i18n.register_listener(cb)
        assert len(i18n._listeners) == 2
        i18n.unregister_listener(cb)
        # Should have removed one instance
        assert len(i18n._listeners) == 1
        # The remaining one still fires
        i18n._translations = {"en": {}, "de": {}}
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert calls == ["de"]

    def test_listeners_are_copied_before_iteration(self):
        """Listeners list is copied before iteration to avoid modification during notify."""
        i18n._translations = {"en": {}, "de": {}}
        def self_removing_listener(lang):
            i18n.unregister_listener(self_removing_listener)
        i18n.register_listener(self_removing_listener)
        other = MagicMock()
        i18n.register_listener(other)
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        # Both should still have been called because the list was copied
        other.assert_called_once_with("de")


# ─── init_language ────────────────────────────────────────────────────

class TestInitLanguage:
    """Tests for ``init_language()``."""

    def setup_method(self):
        _reset_globals()

    def test_loads_translations_and_sets_default_en(self):
        """init_language calls load_translations and sets default 'en'."""
        with patch.object(i18n, "load_translations") as mock_load, \
             patch("os.path.isfile", return_value=False), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        mock_load.assert_called_once()
        mock_set.assert_called_once_with("en")

    def test_reads_persisted_lang_from_file(self):
        """If lang file exists with a valid language, that language is used."""
        m = mock_open(read_data="fr")
        # init_language calls load_translations then reads the lang file.
        # set_language checks _translations for the lang, so pre-populate.
        with patch.object(i18n, "load_translations",
                          side_effect=lambda: i18n._translations.update(
                              {"en": {}, "fr": {}})), \
             patch("os.path.isfile", return_value=True), \
             patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        mock_set.assert_called_once_with("fr")

    def test_ignores_invalid_persisted_lang(self):
        """If lang file contains an unknown language, falls back to 'en'."""
        m = mock_open(read_data="xx")
        with patch.object(i18n, "load_translations"), \
             patch("os.path.isfile", return_value=True), \
             patch("builtins.open", m), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        mock_set.assert_called_once_with("en")

    def test_ignores_stripped_empty_lang(self):
        """If lang file is whitespace-only, falls back to 'en'."""
        m = mock_open(read_data="  \n  ")
        with patch.object(i18n, "load_translations"), \
             patch("os.path.isfile", return_value=True), \
             patch("builtins.open", m), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        # strip() gives "" which is not in _translations and not "en"
        mock_set.assert_called_once_with("en")

    def test_ignores_missing_file(self):
        """If lang file does not exist, falls back to 'en'."""
        with patch.object(i18n, "load_translations"), \
             patch("os.path.isfile", return_value=False), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        mock_set.assert_called_once_with("en")

    def test_file_read_error_fallback(self):
        """If reading lang file raises an exception, falls back to 'en'."""
        with patch.object(i18n, "load_translations"), \
             patch("os.path.isfile", return_value=True), \
             patch("builtins.open", side_effect=OSError("locked")), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        mock_set.assert_called_once_with("en")

    def test_persisted_en_from_file(self):
        """When lang file contains 'en', 'en' is used."""
        m = mock_open(read_data="en")
        with patch.object(i18n, "load_translations"), \
             patch("os.path.isfile", return_value=True), \
             patch("builtins.open", m), \
             patch.object(i18n, "set_language") as mock_set:
            i18n.init_language()
        mock_set.assert_called_once_with("en")


# ─── Integration-style / concurrency ─────────────────────────────────

class TestI18nConcurrency:
    """Basic concurrency smoke tests for the i18n module."""

    def setup_method(self):
        _reset_globals()

    def test_t_is_thread_safe(self):
        """Calling t() from multiple threads does not crash."""
        import threading
        i18n._translations = {"en": {"k": "v"}}
        errors = []

        def worker():
            try:
                for _ in range(50):
                    i18n.t("k")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"Thread safety errors: {errors}"

    def test_set_language_is_thread_safe(self):
        """Calling set_language from multiple threads does not crash."""
        import threading
        i18n._translations = {"en": {}, "de": {}, "fr": {}}
        errors = []
        lock = threading.Lock()
        lang_file = mock_open()
        with patch("builtins.open", lang_file), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):

            def worker(lang):
                try:
                    for _ in range(20):
                        i18n.set_language(lang)
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=worker, args=("de",)),
                threading.Thread(target=worker, args=("fr",)),
                threading.Thread(target=worker, args=("en",)),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        assert not errors, f"Thread safety errors: {errors}"


# ─── Edge cases and error handling ────────────────────────────────────

class TestI18nEdgeCases:
    """Edge cases and error-handling paths."""

    def setup_method(self):
        _reset_globals()

    def test_load_translations_with_bom_files(self):
        """Files with BOM are handled (utf-8-sig encoding).
        mock_open cannot simulate encoding stripping, so this validates
        the code path by confirming the en.json file is opened with
        the correct encoding parameter."""
        m = mock_open(read_data='{"key": "value"}')
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json"]), \
             patch("builtins.open", m) as mock_file:
            i18n.load_translations()
        # Verify utf-8-sig encoding was used
        call_kwargs = mock_file.call_args[1]
        assert call_kwargs.get("encoding") == "utf-8-sig"
        assert i18n._translations["en"]["key"] == "value"

    def test_t_with_none_translations(self):
        """t() handles the case where _translations is None or missing."""
        i18n._translations = {}
        result = i18n.t("any.key", default="fallback")
        assert result == "fallback"

    def test_t_respects_thread_lock(self):
        """t() acquires _LOCK for dict access (smoke test)."""
        i18n._translations = {"en": {"a": "1"}}
        # Just verify it doesn't deadlock
        result = i18n.t("a")
        assert result == "1"

    def test_set_language_preserves_listeners_order(self):
        """Listeners are called in registration order."""
        i18n._translations = {"en": {}, "de": {}}
        order = []
        i18n.register_listener(lambda lang: order.append("first"))
        i18n.register_listener(lambda lang: order.append("second"))
        i18n.register_listener(lambda lang: order.append("third"))
        m = mock_open()
        with patch("builtins.open", m), \
             patch.object(i18n.logger, "debug"), \
             patch.object(i18n.logger, "info"):
            i18n.set_language("de")
        assert order == ["first", "second", "third"]

    def test_get_available_languages_filters_non_json(self):
        """Non-.json files are filtered out."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=[
                 "en.json", "fr.json", "notes.txt", "data.dat"
             ]):
            result = i18n.get_available_languages()
        assert result == ["en", "fr"]

    def test_load_translations_empty_file(self):
        """An empty file raises JSONDecodeError and is skipped."""
        m = mock_open(read_data="")
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json"]), \
             patch("builtins.open", m), \
             patch.object(i18n.logger, "warning"):
            i18n.load_translations()
        assert "en" not in i18n._translations or i18n._translations["en"] == {}

    def test_format_error_with_default_returns_formatted_default(self):
        """If key is missing, default is used and format applies to default."""
        result = i18n.t("missing", default="Value: {x}", x=42)
        assert result == "Value: 42"

    def test_register_listener_return_value(self):
        """register_listener returns the callback (for decorator use)."""
        def cb(lang):
            pass
        result = i18n.register_listener(cb)
        assert result is cb

    def test_load_translations_with_only_failed_files(self):
        """If all files fail to load, falls back to empty en."""
        with patch("os.makedirs"), \
             patch("os.path.isdir", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.listdir", return_value=["en.json"]), \
             patch("builtins.open", side_effect=json.JSONDecodeError("bad", "", 0)), \
             patch.object(i18n.logger, "warning"):
            i18n.load_translations()
        assert i18n._translations == {"en": {}}


# ─── LANGUAGE_NAMES integrity ─────────────────────────────────────────

class TestLanguageNames:
    """Tests for the LANGUAGE_NAMES constant."""

    def setup_method(self):
        _reset_globals()

    def test_en_is_english(self):
        assert i18n.LANGUAGE_NAMES["en"] == "English"

    def test_all_values_are_strings(self):
        for code, name in i18n.LANGUAGE_NAMES.items():
            assert isinstance(code, str), f"Code {code!r} is not str"
            assert isinstance(name, str), f"Name for {code!r} is not str"
            assert name, f"Name for {code!r} is empty"

    def test_no_duplicate_names(self):
        names = list(i18n.LANGUAGE_NAMES.values())
        assert len(names) == len(set(names)), "Duplicate display names found"

    def test_no_duplicate_codes(self):
        codes = list(i18n.LANGUAGE_NAMES.keys())
        assert len(codes) == len(set(codes)), "Duplicate language codes found"
