"""Comprehensive tests for voice pipeline data contracts.

Covers: backend/copilot/voice/schemas.py
- VoiceInputResult field validation
- WakeWordConfig validation
- Edge cases and field constraints
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestVoiceInputResult:
    """VoiceInputResult schema validation."""

    def test_create_with_all_fields(self):
        """VoiceInputResult can be created with all required fields."""
        from backend.copilot.voice.schemas import VoiceInputResult
        result = VoiceInputResult(
            transcript="hello world",
            detected_language="en",
            detection_confidence=0.95,
            audio_duration_ms=2500,
            stt_model_version="faster-whisper-small",
        )
        assert result.transcript == "hello world"
        assert result.detected_language == "en"
        assert result.detection_confidence == 0.95
        assert result.audio_duration_ms == 2500
        assert result.stt_model_version == "faster-whisper-small"

    def test_extra_fields_forbidden(self):
        """Extra fields are rejected."""
        from backend.copilot.voice.schemas import VoiceInputResult
        with pytest.raises(ValueError, match="extra"):
            VoiceInputResult(
                transcript="test",
                detected_language="en",
                detection_confidence=0.5,
                audio_duration_ms=1000,
                stt_model_version="v1",
                unknown_field="x",
            )

    def test_confidence_ge_zero(self):
        """detection_confidence must be >= 0.0."""
        from backend.copilot.voice.schemas import VoiceInputResult
        with pytest.raises(ValueError):
            VoiceInputResult(
                transcript="test",
                detected_language="en",
                detection_confidence=-0.1,
                audio_duration_ms=1000,
                stt_model_version="v1",
            )

    def test_confidence_le_one(self):
        """detection_confidence must be <= 1.0."""
        from backend.copilot.voice.schemas import VoiceInputResult
        with pytest.raises(ValueError):
            VoiceInputResult(
                transcript="test",
                detected_language="en",
                detection_confidence=1.5,
                audio_duration_ms=1000,
                stt_model_version="v1",
            )

    def test_confidence_boundary_values(self):
        """detection_confidence accepts boundary values 0.0 and 1.0."""
        from backend.copilot.voice.schemas import VoiceInputResult

        # Lower bound
        low = VoiceInputResult(
            transcript="test",
            detected_language="en",
            detection_confidence=0.0,
            audio_duration_ms=1000,
            stt_model_version="v1",
        )
        assert low.detection_confidence == 0.0

        # Upper bound
        high = VoiceInputResult(
            transcript="test",
            detected_language="en",
            detection_confidence=1.0,
            audio_duration_ms=1000,
            stt_model_version="v1",
        )
        assert high.detection_confidence == 1.0

    def test_detected_language_is_string(self):
        """detected_language must be a string."""
        from backend.copilot.voice.schemas import VoiceInputResult
        with pytest.raises(ValueError):
            VoiceInputResult(
                transcript="test",
                detected_language=123,  # type: ignore[arg-type]
                detection_confidence=0.5,
                audio_duration_ms=1000,
                stt_model_version="v1",
            )

    def test_transcript_is_string(self):
        """transcript must be a string."""
        from backend.copilot.voice.schemas import VoiceInputResult
        with pytest.raises(ValueError):
            VoiceInputResult(
                transcript=42,  # type: ignore[arg-type]
                detected_language="en",
                detection_confidence=0.5,
                audio_duration_ms=1000,
                stt_model_version="v1",
            )

    def test_empty_transcript_allowed(self):
        """Empty transcript string is allowed."""
        from backend.copilot.voice.schemas import VoiceInputResult
        result = VoiceInputResult(
            transcript="",
            detected_language="en",
            detection_confidence=0.0,
            audio_duration_ms=0,
            stt_model_version="v1",
        )
        assert result.transcript == ""
        assert result.audio_duration_ms == 0

    def test_audio_duration_ms_is_int(self):
        """audio_duration_ms must be an integer."""
        from backend.copilot.voice.schemas import VoiceInputResult
        with pytest.raises(ValueError):
            VoiceInputResult(
                transcript="test",
                detected_language="en",
                detection_confidence=0.5,
                audio_duration_ms=1000.5,  # type: ignore[arg-type]
                stt_model_version="v1",
            )

    def test_negative_duration_allowed(self):
        """Pydantic will coerce negative ints but they are technically allowed by the model."""
        from backend.copilot.voice.schemas import VoiceInputResult
        # Pydantic v2 coerces but does not validate ge for int without Field(ge=...)
        result = VoiceInputResult(
            transcript="test",
            detected_language="en",
            detection_confidence=0.5,
            audio_duration_ms=-1,
            stt_model_version="v1",
        )
        # No ge constraint on audio_duration_ms, so this is allowed
        assert result.audio_duration_ms == -1

    def test_stt_model_version_is_string(self):
        """stt_model_version must be a string."""
        from backend.copilot.voice.schemas import VoiceInputResult
        result = VoiceInputResult(
            transcript="test",
            detected_language="en",
            detection_confidence=0.5,
            audio_duration_ms=1000,
            stt_model_version="faster-whisper-small",
        )
        assert isinstance(result.stt_model_version, str)

    def test_model_serialization(self):
        """VoiceInputResult can be serialized to a dict."""
        from backend.copilot.voice.schemas import VoiceInputResult
        result = VoiceInputResult(
            transcript="hello",
            detected_language="en",
            detection_confidence=0.9,
            audio_duration_ms=1500,
            stt_model_version="v1",
        )
        d = result.model_dump()
        assert d["transcript"] == "hello"
        assert d["detected_language"] == "en"
        assert d["detection_confidence"] == 0.9
        assert d["audio_duration_ms"] == 1500
        assert d["stt_model_version"] == "v1"

    def test_model_deserialization(self):
        """VoiceInputResult can be deserialized from a dict."""
        from backend.copilot.voice.schemas import VoiceInputResult
        data = {
            "transcript": "hello world",
            "detected_language": "ro",
            "detection_confidence": 0.85,
            "audio_duration_ms": 3200,
            "stt_model_version": "faster-whisper-medium",
        }
        result = VoiceInputResult.model_validate(data)
        assert result.transcript == "hello world"
        assert result.detected_language == "ro"
        assert result.detection_confidence == 0.85
        assert result.audio_duration_ms == 3200


class TestWakeWordConfig:
    """WakeWordConfig schema validation."""

    def test_create_with_required_fields(self):
        """WakeWordConfig can be created with required fields."""
        from backend.copilot.voice.schemas import WakeWordConfig
        cfg = WakeWordConfig(enabled=True, phrase="hey operion")
        assert cfg.enabled is True
        assert cfg.phrase == "hey operion"
        assert cfg.sensitivity == 0.5  # default

    def test_create_with_all_fields(self):
        """WakeWordConfig can be created with all fields."""
        from backend.copilot.voice.schemas import WakeWordConfig
        cfg = WakeWordConfig(enabled=False, phrase="hello computer", sensitivity=0.8)
        assert cfg.enabled is False
        assert cfg.phrase == "hello computer"
        assert cfg.sensitivity == 0.8

    def test_extra_fields_forbidden(self):
        """Extra fields are rejected."""
        from backend.copilot.voice.schemas import WakeWordConfig
        with pytest.raises(ValueError, match="extra"):
            WakeWordConfig(
                enabled=True,
                phrase="hey",
                sensitivity=0.5,
                unknown_field="x",
            )

    def test_sensitivity_ge_zero(self):
        """sensitivity must be >= 0.0."""
        from backend.copilot.voice.schemas import WakeWordConfig
        with pytest.raises(ValueError):
            WakeWordConfig(enabled=True, phrase="hey", sensitivity=-0.1)

    def test_sensitivity_le_one(self):
        """sensitivity must be <= 1.0."""
        from backend.copilot.voice.schemas import WakeWordConfig
        with pytest.raises(ValueError):
            WakeWordConfig(enabled=True, phrase="hey", sensitivity=1.5)

    def test_sensitivity_boundary_values(self):
        """sensitivity accepts boundary values 0.0 and 1.0."""
        from backend.copilot.voice.schemas import WakeWordConfig

        low = WakeWordConfig(enabled=True, phrase="hey", sensitivity=0.0)
        assert low.sensitivity == 0.0

        high = WakeWordConfig(enabled=True, phrase="hey", sensitivity=1.0)
        assert high.sensitivity == 1.0

    def test_sensitivity_default(self):
        """sensitivity defaults to 0.5."""
        from backend.copilot.voice.schemas import WakeWordConfig
        cfg = WakeWordConfig(enabled=True, phrase="test")
        assert cfg.sensitivity == 0.5

    def test_phrase_is_string(self):
        """phrase must be a string."""
        from backend.copilot.voice.schemas import WakeWordConfig
        with pytest.raises(ValueError):
            WakeWordConfig(enabled=True, phrase=123)  # type: ignore[arg-type]

    def test_empty_phrase_allowed(self):
        """Empty phrase is technically allowed (no min_length)."""
        from backend.copilot.voice.schemas import WakeWordConfig
        cfg = WakeWordConfig(enabled=True, phrase="")
        assert cfg.phrase == ""

    def test_enabled_is_bool(self):
        """enabled must be a boolean; Pydantic v2 coerces 'truthy' strings
        so we use a non-coercible value."""
        from backend.copilot.voice.schemas import WakeWordConfig
        with pytest.raises(ValueError):
            WakeWordConfig(enabled="not_a_boolean_value", phrase="hey")  # type: ignore[arg-type]

    def test_model_serialization(self):
        """WakeWordConfig can be serialized to a dict."""
        from backend.copilot.voice.schemas import WakeWordConfig
        cfg = WakeWordConfig(enabled=True, phrase="hey operion", sensitivity=0.7)
        d = cfg.model_dump()
        assert d["enabled"] is True
        assert d["phrase"] == "hey operion"
        assert d["sensitivity"] == 0.7

    def test_model_deserialization(self):
        """WakeWordConfig can be deserialized from a dict."""
        from backend.copilot.voice.schemas import WakeWordConfig
        data = {"enabled": False, "phrase": "hello computer", "sensitivity": 0.3}
        cfg = WakeWordConfig.model_validate(data)
        assert cfg.enabled is False
        assert cfg.phrase == "hello computer"
        assert cfg.sensitivity == 0.3


class TestVoiceSchemasInterop:
    """Cross-schema interoperability."""

    def test_voice_input_result_in_wake_word_config(self):
        """Schemas are independent and can be used together."""
        from backend.copilot.voice.schemas import VoiceInputResult, WakeWordConfig

        stt_result = VoiceInputResult(
            transcript="wake word detected",
            detected_language="en",
            detection_confidence=0.99,
            audio_duration_ms=500,
            stt_model_version="v1",
        )
        ww_config = WakeWordConfig(
            enabled=True,
            phrase="hey operion",
            sensitivity=0.7,
        )

        assert stt_result.transcript == "wake word detected"
        assert ww_config.phrase == "hey operion"

    def test_both_schemas_have_extra_forbid(self):
        """Both schemas use extra='forbid'."""
        from backend.copilot.voice.schemas import VoiceInputResult, WakeWordConfig
        assert VoiceInputResult.model_config.get("extra") == "forbid"
        assert WakeWordConfig.model_config.get("extra") == "forbid"
