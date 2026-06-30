"""Centralized PreferencesManager — language, currency, and formatting."""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("preferences")

# ── Safe numeric helpers ──────────────────────────────────────────────

def safe_float(value: Any, default: float = 0.0, label: str = "") -> float:
    """Convert a value to float, logging warnings on failure.

    Args:
        value:       Input value (str, int, float, None, etc.).
        default:     Fallback if conversion fails.
        label:       Optional field name for logging.

    Returns:
        A float guaranteed to be a valid number.
    """
    if value is None:
        if label:
            logger.warning("safe_float: None value for '%s', using %s", label, default)
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            if label:
                logger.warning("safe_float: empty string for '%s', using %s", label, default)
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning("safe_float: cannot parse '%s' for '%s', using %s", value, label, default)
            return default
    if label:
        logger.warning("safe_float: unexpected type %s for '%s', using %s", type(value).__name__, label, default)
    return default


def safe_number(value: Any, decimals: int = 2, default: float = 0.0, label: str = "") -> str:
    """Format a numeric value as a locale-safe string with *decimals* places.

    Returns a string like ``"1,234.56"`` (dot decimal, comma grouping).
    Never raises ``ValueError`` or ``TypeError``.
    """
    num = safe_float(value, default, label)
    return f"{num:,.{decimals}f}"


# ── Constants ──────────────────────────────────────────────────────────

import contextlib

from services.app_state import AppState
from services.currency_service import CURRENCY_SYMBOLS
from services.i18n import LANGUAGE_NAMES, get_language, t
from services.i18n import register_listener as i18n_register_listener
from services.i18n import set_language as i18n_set_language

_PREF_LANG_KEY = "pref_language"
_PREF_CURRENCY_KEY = "pref_currency"
_DEFAULT_CURRENCY = "EUR"
_SUPPORTED_CURRENCIES = ["EUR", "RON", "USD", "GBP"]

_CURRENCY_FORMAT_LOCALES: dict[str, str] = {
    "EUR": "de_DE",
    "RON": "ro_RO",
    "USD": "en_US",
    "GBP": "en_GB",
}

class PreferencesManager:
    """Centralized app preferences backed by the DB settings table.

    Singleton-like — instantiate once at startup and pass via dependency injection.
    """

    def __init__(self, db) -> None:
        self._db = db
        self._currency: str = _DEFAULT_CURRENCY
        self._currency_listeners: list[Callable[[str], None]] = []
        self._settings_cache: dict[str, str | None] = {}
        self._cache_dirty = True

    # --- Load / persist -------------------------------------------------

    def load(self) -> None:
        """Load persisted preferences from the settings table and apply them."""
        lang = self._get_setting(_PREF_LANG_KEY)
        if lang:
            i18n_set_language(lang)
        currency = self._get_setting(_PREF_CURRENCY_KEY)
        if currency and currency in _SUPPORTED_CURRENCIES:
            self._currency = currency

    def clear_cache(self):
        self._cache_dirty = True
        self._settings_cache.clear()

    def _read_settings_batch(self) -> dict[str, str | None]:
        """Batch-read all known settings into cache."""
        if not self._db:
            return {}
        known_keys = [_PREF_LANG_KEY, _PREF_CURRENCY_KEY, *self._SMTP_KEYS, "alert_email_recipients"]
        try:
            result = self._db.get_settings(known_keys)
            return {k: result.get(k) for k in known_keys}
        except Exception:
            return {}

    def _get_setting(self, key: str) -> str | None:
        """Read a single setting from the DB (batched into cache)."""
        if self._db is None:
            return None
        if self._cache_dirty:
            self._settings_cache = self._read_settings_batch()
            self._cache_dirty = False
        if key not in self._settings_cache:
            self._settings_cache[key] = self._db.get_setting(key)
        return self._settings_cache.get(key)

    def _set_setting(self, key: str, value: str) -> None:
        """Write a single setting to the DB and invalidate cache."""
        if self._db is None:
            logger.warning("Cannot save setting %s: no database", key)
            return
        self._db.save_setting(key, value)
        self._settings_cache[key] = value

    # --- Public settings API (canonical access layer) --------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        value = self._get_setting(key)
        return value if value is not None else default

    def get_settings(self, keys: list[str]) -> dict[str, str]:
        return {k: (self._get_setting(k) or "") for k in keys}

    def save_setting(self, key: str, value: str) -> None:
        self._set_setting(key, value)

    def save_settings(self, data: dict[str, str]) -> None:
        for k, v in data.items():
            self._set_setting(k, v)

    # --- SMTP settings ---------------------------------------------------

    _SMTP_KEYS = ["smtp_server", "smtp_port", "smtp_user", "smtp_password"]

    def get_smtp_config(self) -> dict[str, str]:
        cfg = self.get_settings(self._SMTP_KEYS)
        cfg["alert_email_recipients"] = self.get_setting("alert_email_recipients") or ""
        return cfg

    def save_smtp_config(self, config: dict[str, str]) -> None:
        for k in self._SMTP_KEYS:
            if k in config:
                self._set_setting(k, config[k])
        if "alert_email_recipients" in config:
            self._set_setting("alert_email_recipients", config["alert_email_recipients"])

    # --- Language -------------------------------------------------------

    def get_language(self) -> str:
        return get_language()

    def get_language_display(self) -> str:
        return LANGUAGE_NAMES.get(self.get_language(), self.get_language())

    def get_available_languages(self) -> list[str]:
        from services.i18n import get_available_languages
        return get_available_languages()

    def get_language_display_name(self, code: str) -> str:
        return LANGUAGE_NAMES.get(code, code)

    def set_language(self, code: str) -> None:
        i18n_set_language(code)
        self._set_setting(_PREF_LANG_KEY, code)
        AppState().set("language", code)

    def register_language_listener(self, cb: Callable[[str], None]) -> None:
        i18n_register_listener(cb)

    # --- Currency -------------------------------------------------------

    def get_currency(self) -> str:
        return self._currency

    def get_currency_symbol(self, code: str | None = None) -> str:
        return CURRENCY_SYMBOLS.get(code or self._currency, code or self._currency)

    def get_supported_currencies(self) -> list[str]:
        return list(_SUPPORTED_CURRENCIES)

    def set_currency(self, code: str) -> None:
        if code not in _SUPPORTED_CURRENCIES:
            return
        self._currency = code
        self._set_setting(_PREF_CURRENCY_KEY, code)
        AppState().set("currency", code)
        for cb in self._currency_listeners:
            with contextlib.suppress(Exception):
                cb(code)

    def register_currency_listener(self, cb: Callable[[str], None]) -> None:
        self._currency_listeners.append(cb)

    def unregister_currency_listener(self, cb: Callable[[str], None]) -> None:
        if cb in self._currency_listeners:
            self._currency_listeners.remove(cb)

    # --- Formatting helpers ---------------------------------------------

    def format_currency(self, value: float, decimals: int = 2, currency: str | None = None) -> str:
        """Return a locale-aware formatted currency string.

        Example outputs based on currency:
          EUR -> "1.234,56 €"
          RON -> "1.234,56 lei"
          USD -> "$1,234.56"
          GBP -> "£1,234.56"
        """
        cur = currency if currency is not None else self._currency
        symbol = CURRENCY_SYMBOLS.get(cur, cur)
        if cur in ("USD", "GBP"):
            formatted = f"{value:,.{decimals}f}"
            return f"{symbol}{formatted}"
        formatted = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} {symbol}"

    def format_currency_for(self, value: float, code: str, decimals: int = 2) -> str:
        """Format a value in a specific currency (independent of current pref)."""
        return self.format_currency(value, decimals, currency=code)

    # --- Translation helper ---------------------------------------------

    @staticmethod
    def tr(key: str, default: str | None = None, **kwargs: Any) -> str:
        """Translate a key — delegates to i18n.t()."""
        return t(key, default, **kwargs)
