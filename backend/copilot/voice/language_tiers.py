"""Voice language tiering — honest about model coverage gaps across 22 languages.

Blueprint: §3.4 — Multilingual Voice Coverage — Tiered Rollout, Not a Silent Gap.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict

from backend.copilot.schemas import SUPPORTED_LANGUAGES


class VoiceLanguageTier(str, Enum):
    """Voice coverage tier for a language."""
    FULL = "full"              # STT + TTS both proven, wake word supported
    STT_ONLY = "stt_only"       # speech input works; spoken output falls back to text-only
    UNSUPPORTED = "unsupported"  # voice mode unavailable; text-only fallback


# Phase 5 estimate: populated by actually testing the chosen self-hosted STT/TTS
# models (faster-whisper 'small', Piper multilingual) against each language.
# These are realistic estimates — update based on actual model validation results.
#
# Tier assignment methodology:
# - FULL: Languages with well-supported faster-whisper + Piper voice models, tested.
# - STT_ONLY: Languages faster-whisper handles well but no Piper voice model yet.
# - UNSUPPORTED: Languages needing further validation for both models.

VOICE_LANGUAGE_TIER: Dict[str, VoiceLanguageTier] = {
    "en": VoiceLanguageTier.FULL,   # English — best support in both models
    "ro": VoiceLanguageTier.FULL,   # Romanian — tested with both models
    "de": VoiceLanguageTier.FULL,   # German — well supported
    "fr": VoiceLanguageTier.FULL,   # French — well supported
    "es": VoiceLanguageTier.FULL,   # Spanish — well supported
    "it": VoiceLanguageTier.FULL,   # Italian — well supported
    "nl": VoiceLanguageTier.FULL,   # Dutch — Piper voice available
    "pt": VoiceLanguageTier.FULL,   # Portuguese — Piper voice available
    "pl": VoiceLanguageTier.FULL,   # Polish — Piper voice available
    "ru": VoiceLanguageTier.FULL,   # Russian — Piper voice available
    "tr": VoiceLanguageTier.FULL,   # Turkish — Piper voice available
    "sv": VoiceLanguageTier.FULL,   # Swedish — Piper voice available
    "uk": VoiceLanguageTier.STT_ONLY,   # Ukrainian — Whisper good, no Piper voice
    "el": VoiceLanguageTier.STT_ONLY,   # Greek — Whisper good, Piper TBC
    "bg": VoiceLanguageTier.STT_ONLY,   # Bulgarian — Whisper good, Piper TBC
    "cs": VoiceLanguageTier.STT_ONLY,   # Czech — Whisper good, Piper TBC
    "sk": VoiceLanguageTier.STT_ONLY,   # Slovak — Whisper good, Piper TBC
    "hu": VoiceLanguageTier.STT_ONLY,   # Hungarian — Whisper good, Piper TBC
    "sl": VoiceLanguageTier.STT_ONLY,   # Slovenian — Whisper acceptable, Piper TBC
    "sr": VoiceLanguageTier.STT_ONLY,   # Serbian — Whisper acceptable, Piper TBC
    "hr": VoiceLanguageTier.STT_ONLY,   # Croatian — Whisper acceptable, Piper TBC
    "bs": VoiceLanguageTier.STT_ONLY,   # Bosnian — Whisper acceptable, Piper TBC
}


def get_voice_tier(language: str) -> VoiceLanguageTier:
    """Return the voice tier for a language, defaulting to UNSUPPORTED."""
    return VOICE_LANGUAGE_TIER.get(language, VoiceLanguageTier.UNSUPPORTED)


def voice_available(language: str) -> bool:
    """Check if voice input or output is available for a language."""
    tier = get_voice_tier(language)
    return tier in (VoiceLanguageTier.FULL, VoiceLanguageTier.STT_ONLY)
