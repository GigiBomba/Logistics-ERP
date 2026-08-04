"""Internationalization system with JSON translation files and live reload."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_translations: dict[str, dict[str, str]] = {}
_current_lang: str = "en"
_listeners: list[Callable[[str], None]] = []
import contextlib

from utils.resource_path import data_path, resource_path

_TRANSLATIONS_DIR = resource_path("data/translations")
_LANG_FILE = data_path("data/lang.txt")


LANGUAGE_NAMES = {
    "en": "English",
    "ro": "Română",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "ru": "Русский",
    "it": "Italiano",
    "pl": "Polski",
    "uk": "Українська",
    "nl": "Nederlands",
    "sr": "Српски",
    "hr": "Hrvatski",
    "tr": "Türkçe",
    "pt": "Português",
    "hu": "Magyar",
    "cs": "Čeština",
    "sk": "Slovenčina",
    "bs": "Bosanski",
    "sl": "Slovenščina",
    "sv": "Svenska",
    "el": "Ελληνικά",
    "bg": "Български",
}


def _load_file(lang: str) -> dict[str, str] | None:
    """Load a single translation file.

    Returns the flat translation dict on success, or ``None`` if the file
    does not exist or cannot be parsed.
    """
    path = os.path.join(_TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8-sig") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        logger.warning("Skipping %s: %s (line %s)", lang, e.msg, e.lineno)
        return None
    except Exception as e:
        logger.warning("Skipping %s: %s", lang, e)
        return None
    if not isinstance(raw, dict):
        logger.warning("Skipping %s: expected JSON object, got %s", lang, type(raw).__name__)
        return None
    flat: dict[str, str] = {}
    _flatten(raw, "", flat)
    return flat


def _flatten(d: dict, prefix: str, out: dict[str, str]) -> None:
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _flatten(v, key, out)
        else:
            out[key] = str(v)


def load_translations() -> None:
    """Load all available translation files into memory."""
    global _translations
    os.makedirs(_TRANSLATIONS_DIR, exist_ok=True)
    available = get_available_languages()
    _translations = {}
    loaded = []
    failed = []
    for code in available:
        data = _load_file(code)
        if data is not None:
            _translations[code] = data
            loaded.append(code)
        else:
            failed.append(code)
    if not _translations:
        _translations["en"] = {}
        logger.warning("No translations loaded — using empty fallback")
        return
    en = _translations.get("en", {})
    if not en and _translations:
        # Pick first non-en translation as English fallback
        for code, data in _translations.items():
            if code != "en":
                _translations["en"] = data
                en = data
                break
    for code in loaded:
        if code == "en":
            continue
        base = _translations.get(code, {})
        for k, v in en.items():
            base.setdefault(k, v)
        _translations[code] = base
    if failed:
        logger.info("Translations loaded: %s. Failed: %s", loaded, failed)


def t(key: str, default: str | None = None, *args: Any, **kwargs: Any) -> str:
    """Translate a key to the current language.

    Falls back to English, then to the key itself, then to default.
    Supports format placeholders: t("hello", name="World")
    """
    with _LOCK:
        lang_dict = _translations.get(_current_lang, {})
        msg = lang_dict.get(key)
        if msg is None:
            en_dict = _translations.get("en", {})
            msg = en_dict.get(key)
        if msg is None:
            msg = default
    # Do string formatting OUTSIDE the lock for performance
    if msg is None:
        return key
    if not args and not kwargs:
        return str(msg)
    try:
        return str(msg).format(*args, **kwargs)
    except Exception:
        logger.warning("i18n format failed for %s", key)
        return str(msg)


def set_language(lang: str) -> None:
    """Change the active language and notify listeners.

    Logs switch duration, listener count, and reload status.
    """
    global _current_lang
    start = time.perf_counter()
    if lang not in _translations and lang != "en":
        logger.debug("set_language: '%s' not in loaded translations, falling back to 'en'", lang)
        lang = "en"
    with _LOCK:
        old = _current_lang
        _current_lang = lang
    if old == lang:
        logger.debug("set_language: already '%s' — skipping", lang)
        return
    try:
        with open(_LANG_FILE, "w", encoding="utf-8") as f:
            f.write(lang)
    except Exception:
        pass
    notified = 0
    failed = 0
    with _LOCK:
        listeners = list(_listeners)
    for cb in listeners:
        try:
            cb(lang)
            notified += 1
        except Exception as exc:
            failed += 1
            logger.warning("set_language: listener %s failed: %s",
                           getattr(cb, "__name__", str(cb)[:60]), exc)
    elapsed = time.perf_counter() - start
    logger.info("language %s->%s | %d listener(s) notified in %.1fms (%d failed)",
                old, lang, notified, elapsed * 1000, failed)


def get_language() -> str:
    return _current_lang


def get_available_languages() -> list[str]:
    """Return list of available language codes based on JSON files."""
    os.makedirs(_TRANSLATIONS_DIR, exist_ok=True)
    codes = []
    if not os.path.isdir(_TRANSLATIONS_DIR):
        return ["en"]
    for fname in sorted(os.listdir(_TRANSLATIONS_DIR)):
        if fname.endswith(".json"):
            codes.append(fname[:-5])
    if "en" not in codes:
        codes.insert(0, "en")
    return codes


def _get_translations(lang: str) -> dict[str, str]:
    """Return the full flat translation dict for a given language code.

    Falls back to English if the language is not loaded.
    This is used by invoice generation (client invoices always use English).
    """
    with _LOCK:
        return _translations.get(lang, _translations.get("en", {}))


def get_language_display_name(lang: str) -> str:
    return LANGUAGE_NAMES.get(lang, lang)


def register_listener(cb: Callable[[str], None]) -> Callable[[str], None]:
    with _LOCK:
        _listeners.append(cb)
    return cb


def unregister_listener(cb: Callable[[str], None]) -> None:
    with _LOCK, contextlib.suppress(ValueError):
        _listeners.remove(cb)


def init_language() -> None:
    """Load persisted language preference and all translations."""
    load_translations()
    lang = "en"
    try:
        if os.path.isfile(_LANG_FILE):
            with open(_LANG_FILE, encoding="utf-8") as f:
                persisted = f.read().strip()
                if persisted in _translations or persisted == "en":
                    lang = persisted
    except Exception:
        pass
    set_language(lang)
