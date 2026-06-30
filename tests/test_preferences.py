"""Tests for PreferencesManager — load, save, currency, formatting."""
import unittest
from unittest.mock import MagicMock, patch

from services.preferences import PreferencesManager, safe_float, safe_number


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
        self.db.get_setting.return_value = None

    def test_load_with_no_settings_uses_defaults(self):
        prefs = PreferencesManager(self.db)
        prefs.load()
        self.assertEqual(prefs.get_currency(), "EUR")

    def test_load_with_currency_setting(self):
        self.db.get_settings.return_value = {"pref_currency": "RON"}
        prefs = PreferencesManager(self.db)
        prefs.load()
        self.assertEqual(prefs.get_currency(), "RON")

    def test_load_with_unsupported_currency_falls_back(self):
        self.db.get_settings.return_value = {"pref_currency": "XYZ"}
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
        self.db.save_setting.assert_called_with("pref_currency", "RON")
        self.assertIn("RON", notifications)

    def test_set_unsupported_currency_ignored(self):
        prefs = PreferencesManager(self.db)
        prefs.load()
        prefs.set_currency("XYZ")
        self.assertEqual(prefs.get_currency(), "EUR")

    def test_get_setting_returns_none_when_missing(self):
        self.db.get_settings.return_value = {"pref_language": None, "pref_currency": None}
        self.db.get_setting.return_value = None
        prefs = PreferencesManager(self.db)
        self.assertIsNone(prefs.get_setting("nonexistent_key"))

    def test_get_setting_returns_value_when_set(self):
        self.db.get_settings.return_value = {"pref_language": "en", "pref_currency": "EUR"}
        self.db.get_setting.return_value = "some_value"
        prefs = PreferencesManager(self.db)
        self.assertEqual(prefs.get_setting("some_key"), "some_value")

    def test_get_setting_distinguishes_empty_from_none(self):
        self.db.get_settings.return_value = {"pref_language": "", "pref_currency": ""}
        self.db.get_setting.return_value = ""
        prefs = PreferencesManager(self.db)
        self.assertEqual(prefs.get_setting("empty_key"), "")

    def test_save_setting_writes_to_db(self):
        prefs = PreferencesManager(self.db)
        prefs.save_setting("test_key", "test_value")
        self.db.save_setting.assert_called_with("test_key", "test_value")

    def test_get_smtp_config_returns_configured_values(self):
        self.db.get_settings.return_value = {
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "alert_email_recipients": "admin@example.com",
        }

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


if __name__ == "__main__":
    unittest.main()
