"""Tests for PreferencesManager — load, save, currency, formatting."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from services.preferences import (
    _SENSITIVE_KEYS,
    PreferencesManager,
    safe_float,
    safe_number,
)


class TestSafeFloat(unittest.TestCase):
    def test_none_returns_default(self):
        self.assertEqual(safe_float(None), 0.0)

    def test_none_with_label_logs_warning(self):
        with self.assertLogs("preferences", level="WARNING") as cm:
            result = safe_float(None, label="test_field")
            self.assertEqual(result, 0.0)
            self.assertTrue(any("test_field" in msg for msg in cm.output))

    def test_empty_string_returns_default(self):
        self.assertEqual(safe_float(""), 0.0)

    def test_valid_string_returns_float(self):
        self.assertEqual(safe_float("123.45"), 123.45)

    def test_invalid_string_returns_default(self):
        self.assertEqual(safe_float("not-a-number"), 0.0)

    def test_int_converts_to_float(self):
        self.assertEqual(safe_float(42), 42.0)

    def test_float_passthrough(self):
        self.assertEqual(safe_float(3.14), 3.14)

    def test_custom_default(self):
        self.assertEqual(safe_float(None, default=100.0), 100.0)


class TestSafeNumber(unittest.TestCase):
    def test_formats_with_commas(self):
        result = safe_number(1234.5678, decimals=2)
        self.assertIn("1,234.57", result)

    def test_none_returns_zero_format(self):
        result = safe_number(None)
        self.assertEqual(result, "0.00")

    def test_zero_returns_zero(self):
        result = safe_number(0)
        self.assertEqual(result, "0.00")


class TestPreferencesManager(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.settings_repo_patcher = patch(
            "services.preferences.SettingsRepository", autospec=True
        )
        self.mock_settings_repo_cls = self.settings_repo_patcher.start()
        self.mock_settings_repo = MagicMock()
        self.mock_settings_repo_cls.return_value = self.mock_settings_repo
        # Default: no settings cached
        self.mock_settings_repo.get_settings_by_keys.return_value = {}
        self.mock_settings_repo.get_setting_value.return_value = None

    def tearDown(self):
        self.settings_repo_patcher.stop()

    def test_load_with_no_settings_uses_defaults(self):
        prefs = PreferencesManager(self.db)
        prefs.load()
        self.assertEqual(prefs.get_currency(), "EUR")

    def test_load_with_currency_setting(self):
        self.mock_settings_repo.get_settings_by_keys.return_value = {"pref_currency": "RON"}
        prefs = PreferencesManager(self.db)
        prefs.load()
        self.assertEqual(prefs.get_currency(), "RON")

    def test_load_with_unsupported_currency_falls_back(self):
        self.mock_settings_repo.get_settings_by_keys.return_value = {"pref_currency": "XYZ"}
        prefs = PreferencesManager(self.db)
        prefs.load()
        self.assertEqual(prefs.get_currency(), "EUR")

    def test_set_currency_persists_and_notifies(self):
        prefs = PreferencesManager(self.db)
        prefs.load()

        notifications = []
        prefs.register_currency_listener(lambda c: notifications.append(c))

        prefs.set_currency("RON")
        self.assertEqual(prefs.get_currency(), "RON")
        self.mock_settings_repo.upsert_setting.assert_called_with("pref_currency", "RON")
        self.assertIn("RON", notifications)

    def test_set_unsupported_currency_ignored(self):
        prefs = PreferencesManager(self.db)
        prefs.load()
        prefs.set_currency("XYZ")
        self.assertEqual(prefs.get_currency(), "EUR")

    def test_get_setting_returns_none_when_missing(self):
        self.mock_settings_repo.get_setting_value.return_value = None
        prefs = PreferencesManager(self.db)
        self.assertIsNone(prefs.get_setting("nonexistent_key"))

    def test_get_setting_returns_value_when_set(self):
        self.mock_settings_repo.get_setting_value.return_value = "some_value"
        prefs = PreferencesManager(self.db)
        self.assertEqual(prefs.get_setting("some_key"), "some_value")

    def test_get_setting_distinguishes_empty_from_none(self):
        self.mock_settings_repo.get_setting_value.return_value = ""
        prefs = PreferencesManager(self.db)
        self.assertEqual(prefs.get_setting("empty_key"), "")

    def test_save_setting_writes_to_db(self):
        prefs = PreferencesManager(self.db)
        prefs.save_setting("test_key", "test_value")
        self.mock_settings_repo.upsert_setting.assert_called_with("test_key", "test_value")

    def test_get_smtp_config_returns_configured_values(self):
        def get_settings_by_keys_side_effect(keys):
            mapping = {
                "smtp_server": "smtp.example.com",
                "smtp_port": "587",
                "smtp_user": "user@example.com",
                "smtp_password": "secret",
                "alert_email_recipients": "admin@example.com",
            }
            return {k: mapping.get(k) for k in keys}

        self.mock_settings_repo.get_settings_by_keys.side_effect = get_settings_by_keys_side_effect

        prefs = PreferencesManager(self.db)
        cfg = prefs.get_smtp_config()
        self.assertEqual(cfg["smtp_server"], "smtp.example.com")
        self.assertEqual(cfg["smtp_port"], "587")
        self.assertEqual(cfg["alert_email_recipients"], "admin@example.com")

    def test_format_currency_eur(self):
        prefs = PreferencesManager(self.db)
        prefs.load()
        result = prefs.format_currency(1234.56, currency="EUR")
        self.assertIn("1.234,56", result)
        self.assertIn("€", result)

    def test_format_currency_usd(self):
        prefs = PreferencesManager(self.db)
        result = prefs.format_currency(1234.56, currency="USD")
        self.assertIn("$", result)
        self.assertIn("1,234.56", result)

    def test_format_currency_gbp(self):
        prefs = PreferencesManager(self.db)
        result = prefs.format_currency(1234.56, currency="GBP")
        self.assertIn("£", result)
        self.assertIn("1,234.56", result)

    def test_format_currency_ron(self):
        prefs = PreferencesManager(self.db)
        result = prefs.format_currency(1234.56, currency="RON")
        self.assertIn("1.234,56", result)
        self.assertIn("lei", result)

    def test_get_supported_currencies(self):
        prefs = PreferencesManager(self.db)
        currencies = prefs.get_supported_currencies()
        self.assertIn("EUR", currencies)
        self.assertIn("RON", currencies)
        self.assertIn("USD", currencies)
        self.assertIn("GBP", currencies)

    def test_unregister_currency_listener(self):
        prefs = PreferencesManager(self.db)
        calls = []

        def listener(c):
            calls.append(c)

        prefs.register_currency_listener(listener)
        prefs.set_currency("RON")
        self.assertEqual(len(calls), 1)

        prefs.unregister_currency_listener(listener)
        prefs.set_currency("USD")
        self.assertEqual(len(calls), 1)


class TestPreferencesManagerSensitiveKeys(unittest.TestCase):
    """Tracking-provider credentials are encrypted at rest (Phase 3 blocker fix)."""

    def setUp(self):
        self.db = MagicMock()
        self.settings_repo_patcher = patch(
            "services.preferences.SettingsRepository", autospec=True
        )
        self.mock_settings_repo_cls = self.settings_repo_patcher.start()
        self.mock_settings_repo = MagicMock()
        self.mock_settings_repo_cls.return_value = self.mock_settings_repo
        # Default: no settings cached
        self.mock_settings_repo.get_settings_by_keys.return_value = {}
        self.mock_settings_repo.get_setting_value.return_value = None
        self.addCleanup(self.settings_repo_patcher.stop)

    def test_sensitive_keys_include_tracking_credentials(self):
        """_SENSITIVE_KEYS now covers all four tracking-provider credentials."""
        for key in (
            "tracking.token",
            "tracking.username",
            "tracking.password",
            "tracking.account",
        ):
            self.assertIn(key, _SENSITIVE_KEYS)

    def test_tracking_credential_encrypted_on_write(self):
        """save_setting encrypts a tracking credential before persisting."""
        with patch(
            "services.preferences.encrypt_value", side_effect=lambda v: f"enc:{v}"
        ):
            prefs = PreferencesManager(self.db)
            prefs.save_setting("tracking.password", "sekret")
        self.mock_settings_repo.upsert_setting.assert_called_with(
            "tracking.password", "enc:sekret"
        )

    def test_tracking_credentials_decrypted_on_read(self):
        """get_setting decrypts a stored ciphertext tracking credential."""
        self.mock_settings_repo.get_setting_value.return_value = "enc:sekret"
        with patch(
            "services.preferences.decrypt_value",
            side_effect=lambda v: v.replace("enc:", ""),
        ):
            prefs = PreferencesManager(self.db)
            self.assertEqual(prefs.get_setting("tracking.password"), "sekret")

    def test_tracking_credentials_round_trip(self):
        """Write encrypts to the settings table; read decrypts back to plaintext."""
        with patch(
            "services.preferences.encrypt_value", side_effect=lambda v: f"enc:{v}"
        ):
            prefs = PreferencesManager(self.db)
            prefs.save_setting("tracking.token", "tok-123")
        self.mock_settings_repo.upsert_setting.assert_called_with(
            "tracking.token", "enc:tok-123"
        )
        # Simulate the ciphertext now stored in the settings table.
        self.mock_settings_repo.get_setting_value.return_value = "enc:tok-123"
        with patch(
            "services.preferences.decrypt_value",
            side_effect=lambda v: v.replace("enc:", ""),
        ):
            self.assertEqual(prefs.get_setting("tracking.token"), "tok-123")

    def test_tracking_legacy_plaintext_reads_back_unchanged(self):
        """Legacy plaintext (stored before encryption) reads back unchanged."""
        self.mock_settings_repo.get_setting_value.return_value = "legacy-token-abc"
        with patch(
            "services.preferences.decrypt_value", side_effect=lambda v: v
        ):
            prefs = PreferencesManager(self.db)
            self.assertEqual(prefs.get_setting("tracking.token"), "legacy-token-abc")

    def test_tracking_host_not_encrypted(self):
        """Non-credential tracking settings (e.g. host URL) stay plaintext."""
        with patch(
            "services.preferences.encrypt_value", side_effect=lambda v: f"enc:{v}"
        ):
            prefs = PreferencesManager(self.db)
            prefs.save_setting("tracking.host", "https://example.com")
        self.mock_settings_repo.upsert_setting.assert_called_with(
            "tracking.host", "https://example.com"
        )


if __name__ == "__main__":
    unittest.main()
