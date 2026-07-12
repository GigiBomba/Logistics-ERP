"""Remote preferences backed by a local JSON file.

Mirrors :class:`services.preferences.PreferencesManager` API so that
the remote-only entry point (``main_remote.py``) can read and write
user settings without requiring a ``DatabaseManager``.

Usage::

    from client.remote_preferences import RemotePreferences
    prefs = RemotePreferences()
    prefs.load()
    lang = prefs.get_setting("pref_language", "en")
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Callable, Dict, List, Optional

from services.encryption_service import decrypt_value, encrypt_value
from services.i18n import set_language as i18n_set_language

logger = logging.getLogger("remote_prefs")

_DEFAULT_DATA_DIR = "data"
_PREFS_FILENAME = "prefs.json"
_PREF_LANG_KEY = "pref_language"
_PREF_CURRENCY_KEY = "pref_currency"
_DEFAULT_CURRENCY = "EUR"
_SUPPORTED_CURRENCIES = ["EUR", "RON", "USD", "GBP"]


class RemotePreferences:
    """Local JSON-file preferences manager.

    Provides the same public API as ``PreferencesManager`` so that
    ``MainWindow`` and all UI views can call ``get_setting`` and
    ``save_setting`` identically in local and remote modes.
    """

    _SMTP_KEYS = ["smtp_server", "smtp_port", "smtp_user", "smtp_password"]

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._dir = data_dir or _DEFAULT_DATA_DIR
        self._file = os.path.join(self._dir, _PREFS_FILENAME)
        self._data: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._currency: str = _DEFAULT_CURRENCY
        self._currency_listeners: List[Callable[[str], None]] = []

    def load(self) -> None:
        """Load persisted preferences from the JSON file."""
        os.makedirs(self._dir, exist_ok=True)
        try:
            with open(self._file, encoding="utf-8") as fh:
                self._data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

        lang = self._data.get(_PREF_LANG_KEY)
        if lang:
            i18n_set_language(lang)
        currency = self._data.get(_PREF_CURRENCY_KEY)
        if currency and currency in _SUPPORTED_CURRENCIES:
            self._currency = currency

    def save(self) -> None:
        """Persist current settings to disk."""
        with self._lock:
            try:
                os.makedirs(self._dir, exist_ok=True)
                with open(self._file, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2)
            except OSError as exc:
                logger.warning("Failed to save preferences: %s", exc)

    _SENSITIVE_KEYS: set[str] = {"smtp_password"}

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        value = self._data.get(key, default)
        if value is not None and key in self._SENSITIVE_KEYS:
            value = decrypt_value(value)
        return value

    def get_settings(self, keys: List[str]) -> Dict[str, str]:
        return {k: (self.get_setting(k) or "") for k in keys}

    def save_setting(self, key: str, value: str) -> None:
        if key in self._SENSITIVE_KEYS:
            value = encrypt_value(value)
        self._data[key] = value
        self.save()

    def save_settings(self, data: Dict[str, str]) -> None:
        for k, v in data.items():
            if k in self._SENSITIVE_KEYS:
                data[k] = encrypt_value(v)
        self._data.update(data)
        self.save()

    def clear_cache(self) -> None:
        pass

    def get_smtp_config(self) -> Dict[str, str]:
        cfg = self.get_settings(self._SMTP_KEYS)
        cfg["alert_email_recipients"] = self.get_setting("alert_email_recipients") or ""
        return cfg

    def save_smtp_config(self, config: Dict[str, str]) -> None:
        for key in self._SMTP_KEYS:
            if key in config:
                self.save_setting(key, config[key])
        if "alert_email_recipients" in config:
            self.save_setting("alert_email_recipients", config["alert_email_recipients"])

    def get_available_languages(self) -> List[str]:
        try:
            from services.i18n import LANGUAGE_NAMES
            return list(LANGUAGE_NAMES.keys())
        except Exception:
            return ["en"]

    def get_language_display_name(self, code: str) -> str:
        from services.i18n import LANGUAGE_NAMES
        return LANGUAGE_NAMES.get(code, code)

    def get_language(self) -> str:
        """Return the currently active language code."""
        from services.i18n import get_language
        return get_language()

    def get_language_display(self) -> str:
        """Return the display name of the current language."""
        return self.get_language_display_name(self.get_language())

    def set_language(self, code: str) -> None:
        """Persist and activate a new language."""
        from services.i18n import set_language
        set_language(code)
        self.save_setting(_PREF_LANG_KEY, code)

    def get_supported_currencies(self) -> list[str]:
        """Return the list of supported currency codes."""
        from services.currency_service import SUPPORTED_CURRENCIES
        return list(SUPPORTED_CURRENCIES)

    def set_currency(self, code: str) -> None:
        """Persist a new default currency."""
        self.save_setting(_PREF_CURRENCY_KEY, code)

    def get_currency(self) -> str:
        return self._data.get(_PREF_CURRENCY_KEY, _DEFAULT_CURRENCY)

    def get_currency_symbol(self, code: Optional[str] = None) -> str:
        from services.currency_service import CURRENCY_SYMBOLS
        key = code or self.get_currency()
        return CURRENCY_SYMBOLS.get(key, key)
