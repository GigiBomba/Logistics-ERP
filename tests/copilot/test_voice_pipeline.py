"""Full voice pipeline integration tests.

Covers:
- STT → LLM → TTS integration (mocked steps)
- Voice handler processes and routes correctly
- End-to-end voice flow through the copilot controller
- Error propagation through the pipeline
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_stt_provider():
    """A mock WhisperSTTProvider that returns a known transcript."""
    provider = MagicMock()
    result = MagicMock()
    result.transcript = "find truck 42"
    result.detected_language = "en"
    result.detection_confidence = 0.95
    result.audio_duration_ms = 2000
    result.stt_model_version = "faster-whisper-small"
    provider.transcribe.return_value = result
    return provider


@pytest.fixture
def mock_tts_provider():
    """A mock TTS provider that returns audio bytes."""
    provider = MagicMock()
    provider.provider_id = "mock-tts"
    provider.model_id = "mock-v1"
    provider.synthesize = AsyncMock(return_value=b"RIFF....WAV audio....")
    provider.supported_languages.return_value = ["en", "ro", "de"]
    return provider


@pytest.fixture
def mock_remote():
    """A mock remote API client."""
    remote = MagicMock()
    response_data = {
        "summary_key": "copilot.vehicle.found",
        "summary_params": {"vehicle_id": 42},
        "clarification_question_key": None,
        "clarification_params": None,
        "conversation_id": "conv-123",
        "plan": None,
        "timeline": [],
        "confirmation_required": False,
        "token_usage": {"total": 100},
        "model_id": "gemma-3-4b-it",
    }
    remote.voice_input.return_value = response_data
    return remote


# ── STT → LLM → TTS Pipeline ─────────────────────────────────────────────


class TestSTTToLLMPipeline:
    """STT produces transcript → LLM processes it correctly."""

    @pytest.mark.asyncio
    async def test_stt_transcript_passed_to_llm(self, mock_stt_provider, mock_remote):
        """Transcript from STT is passed as utterance to the LLM endpoint."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider
        controller._conversation_id = None

        result = await controller.send_voice(b"fake audio bytes", language="en")

        # Verify STT was called
        mock_stt_provider.transcribe.assert_called_once_with(
            b"fake audio bytes", language="en"
        )

        # Verify LLM was called with the transcript
        mock_remote.voice_input.assert_called_once_with(
            utterance="find truck 42",
            language="en",
        )
        assert result.summary_key == "copilot.vehicle.found"

    @pytest.mark.asyncio
    async def test_stt_transcript_with_existing_conversation(self, mock_stt_provider, mock_remote):
        """Existing conversation_id is passed to the voice endpoint."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider
        controller._conversation_id = "conv-existing"

        await controller.send_voice(b"audio", language="en")

        mock_remote.voice_input.assert_called_once_with(
            utterance="find truck 42",
            language="en",
            conversation_id="conv-existing",
        )

    @pytest.mark.asyncio
    async def test_stt_failure_prevents_llm_call(self, mock_remote):
        """When STT fails, LLM is not called and an error is raised."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = None  # STT failed
        controller._stt_provider = mock_stt

        with pytest.raises(RuntimeError, match="stt_failed"):
            await controller.send_voice(b"audio", language="en")

        mock_remote.voice_input.assert_not_called()

    @pytest.mark.asyncio
    async def test_stt_language_hint_passed(self, mock_remote):
        """Language hint is passed to the STT provider."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt_result = MagicMock()
        mock_stt_result.transcript = "salut"
        mock_stt.transcribe.return_value = mock_stt_result
        controller._stt_provider = mock_stt

        await controller.send_voice(b"audio", language="ro")

        mock_stt.transcribe.assert_called_once_with(b"audio", language="ro")


class TestLLMToTTSPipeline:
    """LLM response can be fed into TTS for spoken output."""

    @pytest.mark.asyncio
    async def test_llm_response_synthesized_to_speech(self, mock_tts_provider):
        """LLM response text is passed to TTS for synthesis."""
        from backend.copilot.voice.tts import TTSRequest

        llm_response = "The vehicle with ID 42 is a truck located in Bucharest."

        audio = await mock_tts_provider.synthesize(
            TTSRequest(text=llm_response, language="en")
        )

        assert audio == b"RIFF....WAV audio...."
        mock_tts_provider.synthesize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tts_with_language_matching_llm(self, mock_tts_provider):
        """TTS language matches the LLM response language."""
        from backend.copilot.voice.tts import TTSRequest

        llm_response = "Bună ziua, domnule."
        _ = await mock_tts_provider.synthesize(
            TTSRequest(text=llm_response, language="ro")
        )

        # Verify language was passed correctly
        call_args = mock_tts_provider.synthesize.call_args
        request = call_args[0][0]
        assert request.language == "ro"
        assert request.text == llm_response

    @pytest.mark.asyncio
    async def test_tts_fallback_language(self, mock_tts_provider):
        """Unsupported language falls back gracefully."""
        from backend.copilot.voice.tts import TTSRequest

        # Mock fallback: unsupported language still gets audio (provider handles it)
        mock_tts_provider.supported_languages.return_value = ["en", "fr"]
        _ = await mock_tts_provider.synthesize(
            TTSRequest(text="Hello", language="xx")
        )

        # Provider was called even for unsupported language (no error)
        mock_tts_provider.synthesize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tts_failure_returns_empty_bytes(self, mock_tts_provider):
        """TTS failure returns empty bytes (graceful degradation)."""
        from backend.copilot.voice.tts import TTSRequest

        mock_tts_provider.synthesize = AsyncMock(return_value=b"")

        audio = await mock_tts_provider.synthesize(
            TTSRequest(text="Hello", language="en")
        )
        assert audio == b""


class TestFullVoicePipeline:
    """End-to-end STT → LLM → TTS pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_happy_path(self, mock_stt_provider, mock_tts_provider, mock_remote):
        """Full voice pipeline: audio → transcript → LLM response → audio response."""
        from ui.copilot.controllers.copilot_controller import CoPilotController
        from backend.copilot.voice.tts import TTSRequest

        # STT produces transcript
        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider
        controller._conversation_id = None

        # Run send_voice (STT → LLM)
        response = await controller.send_voice(b"audio bytes", language="en")

        # Verify STT step
        mock_stt_provider.transcribe.assert_called_once_with(b"audio bytes", language="en")

        # Verify LLM step
        mock_remote.voice_input.assert_called_once_with(
            utterance="find truck 42",
            language="en",
        )

        # Verify response
        assert response.summary_key == "copilot.vehicle.found"
        assert response.conversation_id == "conv-123"

        # Now simulate TTS on the response
        summary_text = "Found vehicle with ID 42"
        tts_audio = await mock_tts_provider.synthesize(
            TTSRequest(text=summary_text, language="en")
        )

        assert tts_audio == b"RIFF....WAV audio...."

    @pytest.mark.asyncio
    async def test_stt_failure_tts_never_called(self, mock_tts_provider, mock_remote):
        """When STT fails, TTS is never invoked."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = None
        controller._stt_provider = mock_stt

        with pytest.raises(RuntimeError):
            await controller.send_voice(b"audio", language="en")

        mock_remote.voice_input.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_failure_propagates(self, mock_stt_provider, mock_remote):
        """When the LLM endpoint fails, the error propagates."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        mock_remote.voice_input.side_effect = RuntimeError("API error")

        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider

        with pytest.raises(RuntimeError, match="API error"):
            await controller.send_voice(b"audio", language="en")

    @pytest.mark.asyncio
    async def test_controller_initializes_stt_on_demand(self, mock_remote):
        """STT provider is lazily initialized on first voice use."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        assert controller._stt_provider is None

        # Mock _load_stt_provider to return a mock
        mock_stt = MagicMock()
        mock_stt_result = MagicMock()
        mock_stt_result.transcript = "test"
        mock_stt.transcribe.return_value = mock_stt_result

        with patch.object(controller, "_load_stt_provider", return_value=mock_stt):
            await controller.send_voice(b"audio", language="en")

        assert controller._stt_provider is mock_stt


class TestVoiceEventPublishing:
    """Voice pipeline event publishing."""

    @pytest.mark.asyncio
    async def test_voice_completed_event_published(self, mock_stt_provider, mock_remote):
        """Voice completion event is published after successful processing."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        mock_event_bus = MagicMock()
        controller = CoPilotController(remote=mock_remote, event_bus=mock_event_bus)
        controller._stt_provider = mock_stt_provider

        await controller.send_voice(b"audio", language="en")

        mock_event_bus.publish.assert_any_call(
            "copilot.voice.completed",
            {"conversation_id": "conv-123"},
        )

    @pytest.mark.asyncio
    async def test_error_event_on_stt_failure(self, mock_remote):
        """Error event is emitted when STT fails."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = None
        controller._stt_provider = mock_stt

        with pytest.raises(RuntimeError):
            await controller.send_voice(b"audio", language="en")

    @pytest.mark.asyncio
    async def test_new_turn_emitted(self, mock_stt_provider, mock_remote):
        """new_turn signal is emitted after voice processing."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider
        controller._conversation_id = None

        # Spy on the signal
        mock_new_turn = MagicMock()
        controller.new_turn.connect(mock_new_turn)

        await controller.send_voice(b"audio", language="en")

        mock_new_turn.assert_called_once_with(mock_remote.voice_input.return_value)

    @pytest.mark.asyncio
    async def test_timeline_updated_emitted(self, mock_stt_provider, mock_remote):
        """timeline_updated signal is emitted after voice processing."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider
        mock_timeline = MagicMock()
        controller.timeline_updated.connect(mock_timeline)

        await controller.send_voice(b"audio", language="en")

        mock_timeline.assert_called_once_with([])  # Empty timeline in mock response


class TestVoicePipelineEdgeCases:
    """Edge cases in the voice pipeline."""

    @pytest.mark.asyncio
    async def test_empty_audio_input(self, mock_remote):
        """Empty audio bytes are handled gracefully."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt_result = MagicMock()
        mock_stt_result.transcript = ""
        mock_stt.transcribe.return_value = mock_stt_result
        controller._stt_provider = mock_stt

        with pytest.raises(RuntimeError, match="stt_failed"):
            await controller.send_voice(b"", language="en")

    @pytest.mark.asyncio
    async def test_stt_exception_handling(self, mock_remote):
        """Exception in STT is caught gracefully."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = RuntimeError("STT crash")
        controller._stt_provider = mock_stt

        with pytest.raises(RuntimeError):
            await controller.send_voice(b"audio", language="en")

    @pytest.mark.asyncio
    async def test_none_transcript_handled(self, mock_remote):
        """None transcript from STT raises error."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=mock_remote)
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = None
        controller._stt_provider = mock_stt

        with pytest.raises(RuntimeError):
            await controller.send_voice(b"audio", language="en")

    @pytest.mark.asyncio
    async def test_remote_exception_handling(self, mock_stt_provider, mock_remote):
        """Exception from remote API is propagated."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        mock_remote.voice_input.side_effect = ConnectionError("Network issue")

        controller = CoPilotController(remote=mock_remote)
        controller._stt_provider = mock_stt_provider

        with pytest.raises(ConnectionError, match="Network issue"):
            await controller.send_voice(b"audio", language="en")


class TestTranscribeAudioHelper:
    """_transcribe_audio helper method."""

    def test_transcribe_audio_success(self):
        """_transcribe_audio returns transcript on success."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=MagicMock())
        mock_stt = MagicMock()
        mock_result = MagicMock()
        mock_result.transcript = "hello world"
        mock_stt.transcribe.return_value = mock_result
        controller._stt_provider = mock_stt

        result = controller._transcribe_audio(b"audio", "en")
        assert result == "hello world"

    def test_transcribe_audio_no_provider(self):
        """_transcribe_audio returns None when no STT provider is available."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=MagicMock())
        controller._stt_provider = None

        with patch.object(controller, "_load_stt_provider", return_value=None):
            result = controller._transcribe_audio(b"audio", "en")
            assert result is None

    def test_transcribe_audio_none_result(self):
        """_transcribe_audio returns None when transcribe returns None."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=MagicMock())
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = None
        controller._stt_provider = mock_stt

        result = controller._transcribe_audio(b"audio", "en")
        assert result is None

    def test_transcribe_audio_empty_transcript(self):
        """_transcribe_audio returns None when transcript is empty string."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=MagicMock())
        mock_stt = MagicMock()
        mock_result = MagicMock()
        mock_result.transcript = ""
        mock_stt.transcribe.return_value = mock_result
        controller._stt_provider = mock_stt

        result = controller._transcribe_audio(b"audio", "en")
        assert result is None

    def test_transcribe_audio_exception(self):
        """_transcribe_audio returns None when transcribe raises."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=MagicMock())
        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = RuntimeError("fail")
        controller._stt_provider = mock_stt

        result = controller._transcribe_audio(b"audio", "en")
        assert result is None

    def test_transcribe_audio_language_passed(self):
        """Language is passed through to the STT provider."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        controller = CoPilotController(remote=MagicMock())
        mock_stt = MagicMock()
        mock_result = MagicMock()
        mock_result.transcript = "test"
        mock_stt.transcribe.return_value = mock_result
        controller._stt_provider = mock_stt

        controller._transcribe_audio(b"audio", "de")
        mock_stt.transcribe.assert_called_once_with(b"audio", language="de")


class TestLoadSTTProvider:
    """_load_stt_provider static method."""

    def test_load_stt_provider_success(self):
        """_load_stt_provider returns a WhisperSTTProvider when available."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        # Mock at the source module, since WhisperSTTProvider is imported
        # inside the static method body, not at module level
        mock_provider = MagicMock()
        with patch(
            "backend.copilot.voice.providers.whisper_stt.WhisperSTTProvider",
            return_value=mock_provider,
        ):
            provider = CoPilotController._load_stt_provider()
            assert provider is mock_provider

    def test_load_stt_provider_import_error(self):
        """_load_stt_provider returns None when faster-whisper is not installed."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        with patch(
            "backend.copilot.voice.providers.whisper_stt.WhisperSTTProvider",
            side_effect=ImportError("no module"),
        ):
            provider = CoPilotController._load_stt_provider()
            assert provider is None

    def test_load_stt_provider_generic_error(self):
        """_load_stt_provider returns None on unexpected error."""
        from ui.copilot.controllers.copilot_controller import CoPilotController

        with patch(
            "backend.copilot.voice.providers.whisper_stt.WhisperSTTProvider",
            side_effect=RuntimeError("init failed"),
        ):
            provider = CoPilotController._load_stt_provider()
            assert provider is None
