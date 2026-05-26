"""Internationalization system with JSON translation files and live reload."""
from __future__ import annotations

import json
import os
import time
import threading
from typing import Any, Callable, Dict, List, Optional

_LOCK = threading.Lock()
_translations: Dict[str, Dict[str, str]] = {}
_current_lang: str = "en"
_listeners: List[Callable[[str], None]] = []
_TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "translations")
_LANG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lang.txt")


def _load_file(lang: str) -> Dict[str, str]:
    path = os.path.join(_TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    flat: Dict[str, str] = {}
    _flatten(raw, "", flat)
    return flat


def _flatten(d: Dict, prefix: str, out: Dict[str, str]) -> None:
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
    for code in available:
        _translations[code] = _load_file(code)
    en = _translations.get("en", {})
    for code in available:
        if code == "en":
            continue
        base = _translations.get(code, {})
        for k, v in en.items():
            base.setdefault(k, v)
        _translations[code] = base


def t(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
    """Translate a key to the current language.
    
    Falls back to English, then to the key itself, then to default.
    Supports format placeholders: t("hello", name="World")
    """
    lang_dict = _translations.get(_current_lang, {})
    msg = lang_dict.get(key)
    if msg is None:
        en_dict = _translations.get("en", {})
        msg = en_dict.get(key)
    if msg is None:
        msg = default if default is not None else key
    if kwargs:
        try:
            msg = msg.format(**kwargs)
        except KeyError:
            pass
    return msg


def set_language(lang: str) -> None:
    """Change the active language and notify listeners.

    Logs switch duration, listener count, and reload status.
    """
    global _current_lang
    start = time.perf_counter()
    if lang not in _translations and lang != "en":
        lang = "en"
    with _LOCK:
        old = _current_lang
        _current_lang = lang
    if old == lang:
        return
    try:
        with open(_LANG_FILE, "w", encoding="utf-8") as f:
            f.write(lang)
    except Exception:
        pass
    notified = 0
    for cb in list(_listeners):
        try:
            cb(lang)
            notified += 1
        except Exception:
            pass
    elapsed = time.perf_counter() - start
    print(f"[i18n] language {old}->{lang} | {notified} listener(s) notified in {elapsed*1000:.1f}ms")


def get_language() -> str:
    return _current_lang


def get_available_languages() -> List[str]:
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


def _get_translations(lang: str) -> Dict[str, str]:
    """Return the full flat translation dict for a given language code.
    
    Falls back to English if the language is not loaded.
    This is used by invoice generation (client invoices always use English).
    """
    return _translations.get(lang, _translations.get("en", {}))


def get_language_display_name(lang: str) -> str:
    names = {
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
    return names.get(lang, lang)


def register_listener(cb: Callable[[str], None]) -> None:
    _listeners.append(cb)


def unregister_listener(cb: Callable[[str], None]) -> None:
    try:
        _listeners.remove(cb)
    except ValueError:
        pass


def init_language() -> None:
    """Load persisted language preference and all translations."""
    load_translations()
    lang = "en"
    try:
        if os.path.isfile(_LANG_FILE):
            with open(_LANG_FILE, "r", encoding="utf-8") as f:
                persisted = f.read().strip()
                if persisted in _translations or persisted == "en":
                    lang = persisted
    except Exception:
        pass
    set_language(lang)
