"""i18n Scope — canonical list of shipped languages.

Blueprint: §3.1 — Language Scope.

This is a re-export for convenience. The canonical definition lives in
backend.copilot.schemas.SUPPORTED_LANGUAGES to avoid circular imports.
Every module that needs the language list imports from here.
"""
from __future__ import annotations


from backend.copilot.schemas import SUPPORTED_LANGUAGES  # noqa: F401 — re-export

# ISO code → English language name. Used when instructing an LLM which
# language to answer in — models follow a full name ("Romanian") far more
# reliably than a bare ISO code ("ro").
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ro": "Romanian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pl": "Polish",
    "it": "Italian",
    "nl": "Dutch",
    "pt": "Portuguese",
    "ru": "Russian",
    "uk": "Ukrainian",
    "tr": "Turkish",
    "hu": "Hungarian",
    "cs": "Czech",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "hr": "Croatian",
    "bs": "Bosnian",
    "sv": "Swedish",
    "el": "Greek",
    "bg": "Bulgarian",
}

__all__ = ["SUPPORTED_LANGUAGES", "LANGUAGE_NAMES"]
