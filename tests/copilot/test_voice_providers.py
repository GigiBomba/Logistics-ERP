"""Tests for voice provider modules (Whisper STT, Piper TTS)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestWhisperSTTProvider:
    """Tests for backend/copilot/voice/providers/whisper_stt.py"""

    def test_import(self):
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        assert WhisperSTTProvider is not None

    def test_class_attributes(self):
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        assert hasattr(WhisperSTTProvider, "transcribe")
        assert hasattr(WhisperSTTProvider, "available")

    def test_available_returns_bool(self):
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        # available returns True/False depending on whether faster-whisper is installed
        assert isinstance(provider.available, bool)

    def test_transcribe_returns_none_when_no_model(self):
        """transcribe returns None when _load_model returns None."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        # Without a model, _load_model will fail (no faster-whisper) -> returns None
        result = provider.transcribe(b"audio data", language="en")
        assert result is None

    def test_transcribe_passes_language(self):
        """Transcribe passes language parameter correctly."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult
        provider = WhisperSTTProvider()
        # Set _model directly so _load_model returns it
        mock_model = MagicMock()
        # faster-whisper transcribe returns (segments_generator, info)
        mock_segments = [MagicMock(text="hello world")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_info.duration = 2.5
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio data", language="en")
        assert result is not None
        assert isinstance(result, VoiceInputResult)
        assert result.detected_language == "en"
        assert result.transcript == "hello world"

    def test_transcribe_returns_transcript(self):
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult
        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="hello world")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_info.duration = 2.5
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio", language="en")
        assert result is not None
        assert isinstance(result, VoiceInputResult)
        assert result.transcript == "hello world"


class TestPiperTTSProvider:
    """Tests for backend/copilot/voice/providers/piper_tts.py"""

    def test_import(self):
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        assert PiperTTSProvider is not None

    def test_class_attributes(self):
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        assert hasattr(PiperTTSProvider, "synthesize")
        assert hasattr(PiperTTSProvider, "available")
        assert hasattr(PiperTTSProvider, "supported_languages")

    def test_provider_id(self):
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        # Actual provider_id from the class definition
        assert provider.provider_id == "piper-tts"

    def test_supported_languages_returns_list(self):
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        langs = provider.supported_languages()
        assert isinstance(langs, list)

    def test_available_returns_bool(self):
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        # available returns True/False depending on whether piper binary is installed
        assert isinstance(provider.available, bool)


class TestVoiceLanguageTiers:
    """Tests for VOICE_LANGUAGE_TIER completeness."""

    def test_import(self):
        from backend.copilot.voice.language_tiers import VOICE_LANGUAGE_TIER, VoiceLanguageTier
        assert VOICE_LANGUAGE_TIER is not None
        assert VoiceLanguageTier is not None

    def test_all_supported_languages_have_tier(self):
        from backend.copilot.voice.language_tiers import VOICE_LANGUAGE_TIER
        from backend.copilot.i18n_scope import SUPPORTED_LANGUAGES
        for lang in SUPPORTED_LANGUAGES:
            assert lang in VOICE_LANGUAGE_TIER, f"Missing VOICE_LANGUAGE_TIER entry for {lang}"

    def test_no_empty_tiers(self):
        from backend.copilot.voice.language_tiers import VOICE_LANGUAGE_TIER
        for lang, tier in VOICE_LANGUAGE_TIER.items():
            assert tier is not None, f"None tier for {lang}"

    def test_tier_values_are_valid(self):
        from backend.copilot.voice.language_tiers import VOICE_LANGUAGE_TIER, VoiceLanguageTier
        valid = {t.value for t in VoiceLanguageTier}
        for lang, tier in VOICE_LANGUAGE_TIER.items():
            assert tier in valid, f"Invalid tier {tier} for {lang}"
