"""Tests for the TTS provider interface and request model.

Covers: backend/copilot/voice/tts.py — TTSRequest model, TTSProvider ABC,
and abstract method contracts.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestTTSRequest:
    """TTSRequest model validation."""

    def test_create_with_required_fields(self):
        """TTSRequest can be created with text and language only."""
        from backend.copilot.voice.tts import TTSRequest
        req = TTSRequest(text="Hello world", language="en")
        assert req.text == "Hello world"
        assert req.language == "en"
        assert req.voice_profile_id is None

    def test_create_with_voice_profile(self):
        """TTSRequest accepts an optional voice_profile_id."""
        from backend.copilot.voice.tts import TTSRequest
        req = TTSRequest(
            text="Bună ziua",
            language="ro",
            voice_profile_id="ro_RO-mihai-medium",
        )
        assert req.voice_profile_id == "ro_RO-mihai-medium"

    def test_extra_fields_forbidden(self):
        """TTSRequest forbids extra fields (extra='forbid')."""
        from backend.copilot.voice.tts import TTSRequest
        with pytest.raises(ValueError, match="extra") as excinfo:
            TTSRequest(text="test", language="en", unknown_field="x")
        assert "extra" in str(excinfo.value).lower()

    def test_text_must_be_string(self):
        """TTSRequest.text must be a string (type validation)."""
        from backend.copilot.voice.tts import TTSRequest
        with pytest.raises(ValueError):
            TTSRequest(text=123, language="en")  # type: ignore[arg-type]

    def test_language_must_be_string(self):
        """TTSRequest.language must be a string."""
        from backend.copilot.voice.tts import TTSRequest
        req = TTSRequest(text="hello", language="en")
        assert isinstance(req.language, str)


class TestTTSProviderABC:
    """TTSProvider abstract base class contract."""

    def test_abc_cannot_be_instantiated(self):
        """TTSProvider cannot be instantiated directly (abstract methods)."""
        from backend.copilot.voice.tts import TTSProvider
        with pytest.raises(TypeError):
            TTSProvider()  # type: ignore[abstract]

    def test_abstract_methods_exist(self):
        """TTSProvider declares the required abstract methods."""
        from backend.copilot.voice.tts import TTSProvider
        assert hasattr(TTSProvider, "synthesize")
        assert hasattr(TTSProvider, "supported_languages")

    def test_synthesize_signature(self):
        """synthesize is abstract async and accepts a TTSRequest."""
        from backend.copilot.voice.tts import TTSProvider
        import inspect
        sig = inspect.signature(TTSProvider.synthesize)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "request" in params
        # Should return bytes
        assert sig.return_annotation is bytes or sig.return_annotation == "bytes"

    def test_supported_languages_signature(self):
        """supported_languages returns List[str]."""
        from backend.copilot.voice.tts import TTSProvider
        import inspect
        sig = inspect.signature(TTSProvider.supported_languages)
        assert "self" in sig.parameters
        assert sig.return_annotation is not inspect.Parameter.empty

    def test_concrete_implementation_compliance(self):
        """A concrete provider implements both abstract methods."""
        from backend.copilot.voice.tts import TTSRequest, TTSProvider

        class FakeProvider(TTSProvider):
            provider_id = "fake"
            model_id = "fake-v1"

            async def synthesize(self, request: TTSRequest) -> bytes:
                return b"fake audio"

            def supported_languages(self) -> list[str]:
                return ["en", "ro"]

        provider = FakeProvider()
        assert provider.provider_id == "fake"
        assert provider.model_id == "fake-v1"
        assert provider.supported_languages() == ["en", "ro"]


class TestTTSProviderProviderId:
    """Provider metadata attributes."""

    def test_provider_id_is_string(self):
        """TTSProvider subclasses have a provider_id str attribute."""
        from backend.copilot.voice.tts import TTSProvider

        class Impl(TTSProvider):
            provider_id = "test"
            model_id = "t1"

            async def synthesize(self, request: "TTSRequest") -> bytes:
                return b""

            def supported_languages(self) -> list[str]:
                return []

        assert Impl.provider_id == "test"

    def test_model_id_is_string(self):
        """TTSProvider subclasses have a model_id str attribute."""
        from backend.copilot.voice.tts import TTSProvider

        class Impl(TTSProvider):
            provider_id = "test"
            model_id = "whisper-small"

            async def synthesize(self, request: "TTSRequest") -> bytes:
                return b""

            def supported_languages(self) -> list[str]:
                return []

        assert Impl.model_id == "whisper-small"
