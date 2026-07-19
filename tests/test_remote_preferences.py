"""Tests for client.remote_preferences — RemotePreferences settings management.

Notes
-----
- RemotePreferences is **not** a singleton; each ``RemotePreferences()`` call
  creates an independent instance backed by its own JSON file.
- Sensitive keys (``smtp_password``) are encrypted/decrypted via
  ``services.encryption_service`` which is mocked here.
- File I/O is performed against temporary directories created via ``tmp_path``.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, call, patch

import pytest

from client.remote_preferences import RemotePreferences


@pytest.fixture
def prefs(tmp_path):
    """Return a fresh RemotePreferences backed by a temporary directory."""
    p = RemotePreferences(data_dir=str(tmp_path))
    yield p


# The test environment may not have encryption_service properly configured;
# mock it for all tests in this file.
@pytest.fixture(autouse=True)
def _mock_encryption():
    with patch("client.remote_preferences.encrypt_value", side_effect=lambda v: f"enc:{v}"):
        with patch("client.remote_preferences.decrypt_value", side_effect=lambda v: v.replace("enc:", "")):
            yield


# ── Initialisation ──────────────────────────────────────────────────────


class TestRemotePreferencesInit:
    def test_default_data_dir(self):
        p = RemotePreferences()
        assert p._dir == "data"
        assert p._file == os.path.join("data", "prefs.json")

    def test_custom_data_dir(self, tmp_path):
        custom = str(tmp_path / "custom_dir")
        p = RemotePreferences(data_dir=custom)
        assert p._dir == custom
        assert p._file == os.path.join(custom, "prefs.json")

    def test_empty_data_dict_on_init(self, tmp_path):
        p = RemotePreferences(data_dir=str(tmp_path))
        assert p._data == {}

    def test_default_currency_is_eur(self, tmp_path):
        p = RemotePreferences(data_dir=str(tmp_path))
        assert p._currency == "EUR"

    def test_lock_is_initialised(self, tmp_path):
        p = RemotePreferences(data_dir=str(tmp_path))
        assert p._lock is not None


# ── get_setting / save_setting ─────────────────────────────────────────


class TestRemotePreferencesGetSet:
    def test_set_and_get_string(self, prefs):
        prefs.save_setting("pref_language", "ro")
        assert prefs.get_setting("pref_language") == "ro"

    def test_set_and_get_numeric_string(self, prefs):
        prefs.save_setting("items_per_page", "50")
        assert prefs.get_setting("items_per_page") == "50"

    def test_set_and_get_boolean_string(self, prefs):
        prefs.save_setting("dark_mode", "true")
        assert prefs.get_setting("dark_mode") == "true"

    def test_set_and_get_json_string(self, prefs):
        d = {"nested": "value", "count": 3}
        serialised = json.dumps(d)
        prefs.save_setting("my_dict", serialised)
        assert json.loads(prefs.get_setting("my_dict")) == d

    def test_get_missing_key_returns_none(self, prefs):
        assert prefs.get_setting("nonexistent") is None

    def test_get_missing_key_with_custom_default(self, prefs):
        assert prefs.get_setting("nonexistent", "fallback") == "fallback"

    def test_get_missing_key_with_empty_string_default(self, prefs):
        assert prefs.get_setting("nonexistent", "") == ""

    def test_overwrite_existing_key(self, prefs):
        prefs.save_setting("key1", "value1")
        prefs.save_setting("key1", "value2")
        assert prefs.get_setting("key1") == "value2"

    def test_get_setting_returns_none_for_explicit_none(self, prefs):
        prefs._data["key_none"] = None
        val = prefs.get_setting("key_none")
        assert val is None

    def test_get_settings_batch(self, prefs):
        prefs.save_setting("a", "1")
        prefs.save_setting("b", "2")
        result = prefs.get_settings(["a", "b", "c"])
        assert result == {"a": "1", "b": "2", "c": ""}

    def test_save_settings_batch(self, prefs):
        prefs.save_settings({"key1": "val1", "key2": "val2"})
        assert prefs.get_setting("key1") == "val1"
        assert prefs.get_setting("key2") == "val2"


# ── Persistence round-trip ──────────────────────────────────────────────


class TestRemotePreferencesPersistence:
    def test_save_writes_to_file(self, prefs):
        prefs.save_setting("pref_language", "fr")
        assert os.path.isfile(prefs._file)
        with open(prefs._file, encoding="utf-8") as f:
            data = json.load(f)
        assert data["pref_language"] == "fr"

    def test_load_restores_saved_data(self, prefs):
        prefs.save_setting("pref_language", "de")
        prefs.save_setting("custom_key", "custom_value")

        # New instance, same directory
        p2 = RemotePreferences(data_dir=prefs._dir)
        p2.load()
        assert p2.get_setting("pref_language") == "de"
        assert p2.get_setting("custom_key") == "custom_value"

    def test_load_missing_file_does_not_raise(self, tmp_path):
        p = RemotePreferences(data_dir=str(tmp_path / "nonexistent"))
        p.load()  # should not raise
        assert p._data == {}

    def test_load_invalid_json_does_not_raise(self, prefs):
        with open(prefs._file, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        p2 = RemotePreferences(data_dir=prefs._dir)
        p2.load()  # should not raise
        assert p2._data == {}

    def test_save_creates_directory(self, tmp_path):
        deep_dir = str(tmp_path / "a" / "b" / "c")
        p = RemotePreferences(data_dir=deep_dir)
        p.save_setting("key", "value")
        assert os.path.isfile(p._file)

    def test_save_empty_data(self, prefs):
        prefs.save()
        assert os.path.isfile(prefs._file)
        with open(prefs._file, encoding="utf-8") as f:
            assert json.load(f) == {}

    def test_save_failure_logs_warning(self, prefs, caplog):
        caplog.set_level("WARNING")
        # Make the directory non-writable by pointing to a file path
        p = RemotePreferences(data_dir=prefs._dir)
        # Replace _file with a path that will fail
        p._file = os.path.join(prefs._dir, "nonexistent_dir", "prefs.json")
        p.save_setting("key", "value")  # save inside catches OSError
        assert len(caplog.records) >= 1
        assert "Failed to save preferences" in caplog.text

    def test_save_round_trip_preserves_all_types(self, prefs):
        prefs.save_setting("string", "hello")
        prefs.save_setting("int_str", "42")
        prefs.save_setting("bool_str", "false")
        prefs.save_setting("empty", "")

        p2 = RemotePreferences(data_dir=prefs._dir)
        p2.load()
        assert p2.get_setting("string") == "hello"
        assert p2.get_setting("int_str") == "42"
        assert p2.get_setting("bool_str") == "false"
        assert p2.get_setting("empty") == ""


# ── Sensitive-key encryption ────────────────────────────────────────────


class TestRemotePreferencesSensitiveKeys:
    def test_smtp_password_encrypted_on_save(self, prefs):
        prefs.save_setting("smtp_password", "secret123")
        assert prefs._data["smtp_password"] == "enc:secret123"

    def test_smtp_password_decrypted_on_get(self, prefs):
        prefs.save_setting("smtp_password", "secret123")
        val = prefs.get_setting("smtp_password")
        assert val == "secret123"

    def test_non_sensitive_key_not_encrypted(self, prefs):
        with patch("client.remote_preferences.encrypt_value") as mock_enc:
            prefs.save_setting("normal_key", "value")
            mock_enc.assert_not_called()

    def test_non_sensitive_key_not_decrypted(self, prefs):
        with patch("client.remote_preferences.decrypt_value") as mock_dec:
            prefs.save_setting("normal_key", "value")
            prefs.get_setting("normal_key")
            mock_dec.assert_not_called()

    def test_batch_save_encrypts_sensitive_keys(self, prefs):
        prefs.save_settings({
            "smtp_password": "p4ss",
            "normal_key": "val",
        })
        assert prefs._data["smtp_password"] == "enc:p4ss"
        assert prefs._data["normal_key"] == "val"

    def test_smtp_config_encrypts_password(self, prefs):
        prefs.save_smtp_config({
            "smtp_server": "smtp.test.com",
            "smtp_port": "587",
            "smtp_user": "user",
            "smtp_password": "pass",
            "alert_email_recipients": "admin@test.com",
        })
        assert "enc:pass" in prefs._data["smtp_password"]

    def test_smtp_config_round_trip(self, prefs):
        prefs.save_smtp_config({
            "smtp_server": "smtp.test.com",
            "smtp_port": "587",
            "smtp_user": "user",
            "smtp_password": "pass",
            "alert_email_recipients": "admin@test.com",
        })
        cfg = prefs.get_smtp_config()
        assert cfg["smtp_server"] == "smtp.test.com"
        assert cfg["smtp_port"] == "587"
        assert cfg["smtp_user"] == "user"
        assert cfg["alert_email_recipients"] == "admin@test.com"


# ── Language / Currency ─────────────────────────────────────────────────


class TestRemotePreferencesLanguage:
    def test_get_language_default(self, prefs):
        lang = prefs.get_language()
        assert lang == "en"

    def test_set_language_persists(self, prefs):
        prefs.set_language("ro")
        assert prefs.get_setting("pref_language") == "ro"

    def test_set_language_activates(self, prefs):
        with patch("services.i18n.set_language") as mock_set:
            prefs.set_language("de")
            mock_set.assert_called_once_with("de")

    def test_load_sets_language_from_file(self, prefs):
        prefs.save_setting("pref_language", "fr")
        p2 = RemotePreferences(data_dir=prefs._dir)
        with patch("client.remote_preferences.i18n_set_language") as mock_set:
            p2.load()
            mock_set.assert_called_once_with("fr")

    def test_get_available_languages(self, prefs):
        langs = prefs.get_available_languages()
        assert isinstance(langs, list)
        assert "en" in langs


class TestRemotePreferencesCurrency:
    def test_get_currency_default(self, prefs):
        assert prefs.get_currency() == "EUR"

    def test_set_currency(self, prefs):
        prefs.set_currency("USD")
        assert prefs.get_currency() == "USD"

    def test_set_currency_persists(self, prefs):
        prefs.set_currency("GBP")
        with open(prefs._file, encoding="utf-8") as f:
            data = json.load(f)
        assert data["pref_currency"] == "GBP"

    def test_load_restores_currency(self, prefs):
        prefs.set_currency("RON")
        p2 = RemotePreferences(data_dir=prefs._dir)
        p2.load()
        assert p2.get_currency() == "RON"

    def test_get_currency_symbol(self, prefs):
        sym = prefs.get_currency_symbol("EUR")
        assert isinstance(sym, str)

    def test_get_currency_symbol_default(self, prefs):
        prefs.set_currency("USD")
        sym = prefs.get_currency_symbol()
        assert isinstance(sym, str)

    def test_get_supported_currencies(self, prefs):
        currencies = prefs.get_supported_currencies()
        assert isinstance(currencies, list)
        assert "EUR" in currencies


# ── Edge cases ──────────────────────────────────────────────────────────


class TestRemotePreferencesEdgeCases:
    def test_clear_cache_is_noop(self, prefs):
        prefs.clear_cache()  # should not raise

    def test_empty_value_round_trip(self, prefs):
        prefs.save_setting("empty_key", "")
        assert prefs.get_setting("empty_key") == ""

    def test_none_value_in_data(self, prefs):
        prefs._data["key"] = None
        assert prefs.get_setting("key") is None

    def test_many_keys(self, prefs):
        for i in range(100):
            prefs.save_setting(f"key{i}", f"val{i}")
        assert len(prefs._data) == 100
        assert prefs.get_setting("key99") == "val99"

    def test_language_display_name(self, prefs):
        name = prefs.get_language_display_name("en")
        assert isinstance(name, str)

    def test_get_language_display(self, prefs):
        display = prefs.get_language_display()
        assert isinstance(display, str)

    def test_get_currency_symbol_unknown(self, prefs):
        # Unknown code returns the code itself
        sym = prefs.get_currency_symbol("XYZ")
        assert sym == "XYZ"
