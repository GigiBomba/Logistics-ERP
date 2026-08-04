"""Comprehensive tests for the Whisper STT provider.

Covers: backend/copilot/voice/providers/whisper_stt.py
- Model loading (lazy init on first use)
- transcribe() returns correct text for audio input
- Language detection works
- Error handling (model load failure, transcription failure)
- Different audio formats
- available property
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest


class TestWhisperSTTProviderInit:
    """WhisperSTTProvider initialisation."""

    def test_default_init(self):
        """Provider is created with sensible defaults."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        assert provider.model_size == "small"
        assert provider.device == "auto"
        assert provider.compute_type == "default"
        assert provider._model is None
        assert provider._model_version == "faster-whisper-small"

    def test_custom_model_size(self):
        """Provider accepts a valid custom model size."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider(model_size="medium")
        assert provider.model_size == "medium"

    def test_custom_model_size_fallback(self):
        """Invalid model sizes fall back to 'small'."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider(model_size="invalid")
        assert provider.model_size == "small"

    def test_custom_device(self):
        """Provider accepts a custom device."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider(device="cpu")
        assert provider.device == "cpu"

    def test_custom_compute_type(self):
        """Provider accepts a custom compute type."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider(compute_type="int8")
        assert provider.compute_type == "int8"

    def test_model_sizes_constant(self):
        """MODEL_SIZES contains expected values."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        assert WhisperSTTProvider.MODEL_SIZES == ("tiny", "small", "medium", "large-v3")

    def test_model_version_format(self):
        """_model_version matches expected format."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider(model_size="tiny")
        assert provider._model_version == "faster-whisper-tiny"
        provider2 = WhisperSTTProvider(model_size="medium")
        assert provider2._model_version == "faster-whisper-medium"


class TestWhisperSTTProviderAvailable:
    """available property."""

    @patch("backend.copilot.voice.providers.whisper_stt.WhisperSTTProvider.available", new_callable=PropertyMock)
    def test_available_returns_bool(self, mock_available):
        """available returns a boolean."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        mock_available.return_value = True
        assert isinstance(provider.available, bool)

    def test_available_when_faster_whisper_installed(self):
        """available is True when faster_whisper can be imported."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        # In the test env faster-whisper is likely not installed,
        # but we can patch the try/except block internally.
        # Instead we test via the actual import guard.
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = MagicMock()
            assert provider.available is True

    def test_available_when_not_installed(self):
        """available is False when faster_whisper is not installed."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        # Simulate ImportError
        def fake_import(name, *args, **kwargs):
            if name == "faster_whisper":
                raise ImportError("No module named 'faster_whisper'")
            raise ImportError(f"No module named '{name}'")

        with patch("builtins.__import__", side_effect=fake_import):
            provider = WhisperSTTProvider()
            assert provider.available is False


class TestWhisperSTTProviderModelLoading:
    """_load_model lazy-loading behaviour."""

    @staticmethod
    def _inject_faster_whisper():
        """Add a mock faster_whisper module to sys.modules so patch can find it."""
        import sys
        mock_fw = MagicMock()
        mock_fw.WhisperModel = MagicMock()
        sys.modules["faster_whisper"] = mock_fw
        return mock_fw

    def test_model_is_none_before_first_call(self):
        """Model starts as None before any load attempt."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        assert provider._model is None

    def test_lazy_load_returns_model(self):
        """_load_model creates and caches the model on first call."""
        import sys
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        mock_fw = self._inject_faster_whisper()
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model

        provider = WhisperSTTProvider()
        loaded = provider._load_model()

        assert loaded is mock_model
        assert provider._model is mock_model
        mock_fw.WhisperModel.assert_called_once_with(
            "small", device="auto", compute_type="default"
        )
        # Clean up
        del sys.modules["faster_whisper"]

    def test_lazy_load_returns_cached_model(self):
        """Subsequent calls return the cached model without re-initialising."""
        import sys
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        mock_fw = self._inject_faster_whisper()
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model

        provider = WhisperSTTProvider()
        first = provider._load_model()
        second = provider._load_model()

        assert first is second
        assert mock_fw.WhisperModel.call_count == 1
        del sys.modules["faster_whisper"]

    def test_load_model_import_error(self):
        """_load_model returns None and logs warning when faster-whisper not installed."""
        import sys
        import types
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        # Replace faster_whisper in sys.modules with a bare module that
        # does NOT export WhisperModel, so the "from faster_whisper import
        # WhisperModel" inside _load_model() raises ImportError.
        old_fw = sys.modules.get("faster_whisper")
        old_sub = {k: v for k, v in sys.modules.items() if k.startswith("faster_whisper.")}
        for k in list(old_sub):
            del sys.modules[k]
        sys.modules["faster_whisper"] = types.ModuleType("faster_whisper")

        try:
            provider = WhisperSTTProvider()
            result = provider._load_model()
            assert result is None
            assert provider._model is None
        finally:
            if old_fw is not None:
                sys.modules["faster_whisper"] = old_fw
            else:
                del sys.modules["faster_whisper"]
            for key, val in old_sub.items():
                sys.modules[key] = val

    def test_load_model_generic_error(self):
        """_load_model returns None on generic exception."""
        import sys
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        mock_fw = self._inject_faster_whisper()
        mock_fw.WhisperModel.side_effect = RuntimeError("OOM")

        provider = WhisperSTTProvider()
        result = provider._load_model()
        assert result is None
        assert provider._model is None
        del sys.modules["faster_whisper"]

    def test_load_model_passes_parameters(self):
        """_load_model passes model_size, device, and compute_type to WhisperModel."""
        import sys
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        mock_fw = self._inject_faster_whisper()

        provider = WhisperSTTProvider(
            model_size="medium", device="cpu", compute_type="int8"
        )
        provider._load_model()
        mock_fw.WhisperModel.assert_called_once_with(
            "medium", device="cpu", compute_type="int8"
        )
        del sys.modules["faster_whisper"]


class TestWhisperSTTProviderTranscribe:
    """transcribe() method."""

    def test_transcribe_returns_none_when_no_model(self):
        """transcribe returns None when _load_model fails."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        provider = WhisperSTTProvider()
        with patch.object(provider, "_load_model", return_value=None):
            result = provider.transcribe(b"audio data", language="en")
            assert result is None

    def test_transcribe_success(self):
        """transcribe returns VoiceInputResult with correct fields on success."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [
            MagicMock(text="hello world"),
        ]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_info.duration = 2.5
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"fake audio bytes", language="en")

        assert isinstance(result, VoiceInputResult)
        assert result.transcript == "hello world"
        assert result.detected_language == "en"
        assert result.detection_confidence == 0.95
        assert result.audio_duration_ms == 2500
        assert result.stt_model_version == "faster-whisper-small"

    def test_transcribe_multiple_segments(self):
        """Multiple segments are joined into a single transcript."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [
            MagicMock(text="first part"),
            MagicMock(text="second part"),
            MagicMock(text="third part"),
        ]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98
        mock_info.duration = 5.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"long audio")

        assert result.transcript == "first part second part third part"

    def test_transcribe_empty_transcript(self):
        """Empty transcript returns empty string, not None."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.5
        mock_info.duration = 0.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"silence")

        assert result.transcript == ""

    def test_transcribe_auto_language_detection(self):
        """When language is None, the detected language from info is used."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="salut")]
        mock_info = MagicMock()
        mock_info.language = "ro"
        mock_info.language_probability = 0.92
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio", language=None)

        assert result.detected_language == "ro"
        assert result.detection_confidence == 0.92

    def test_transcribe_language_hint_passed(self):
        """transcribe passes the language hint to the model."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_info = MagicMock()
        mock_info.language = "de"
        mock_info.language_probability = 0.9
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        provider.transcribe(b"audio", language="de")

        # Verify language parameter was passed to model.transcribe
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs["language"] == "de"
        assert kwargs["beam_size"] == 5
        assert kwargs["vad_filter"] is True

    def test_transcribe_model_params(self):
        """transcribe calls model.transcribe with correct parameters."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.9
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        provider.transcribe(b"audio", language="en")

        mock_model.transcribe.assert_called_once()
        args, kwargs = mock_model.transcribe.call_args
        # First positional arg is the file path (a temp file)
        assert args[0].endswith(".wav")
        assert kwargs["language"] == "en"
        assert kwargs["beam_size"] == 5
        assert kwargs["vad_filter"] is True

    def test_transcribe_exception_handling(self):
        """transcribe returns None when transcription raises an exception."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("GPU out of memory")
        provider._model = mock_model

        result = provider.transcribe(b"audio", language="en")

        assert result is None

    def test_transcribe_exception_during_segment_iteration(self):
        """transcribe handles exceptions during segment iteration."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        def failing_iter(*args, **kwargs):
            yield from []
            raise RuntimeError("Segment processing failed")

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.9
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = (failing_iter(), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio", language="en")

        assert result is None

    def test_transcribe_temp_file_cleaned_up(self, monkeypatch):
        """Temporary file is cleaned up after transcription."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        import tempfile
        from pathlib import Path

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.9
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        # xdist-safe: the suite runs with ``-n auto``, so OTHER workers may
        # create/delete *.wav files in the shared system temp dir at any
        # moment.  Scope the assertion to a private temp dir instead of
        # globbing the global temp dir — the semantics (the provider leaves
        # no new wav file behind) are unchanged.
        private_tmp = Path(tempfile.mkdtemp(prefix="copilot-stt-test-"))
        monkeypatch.setattr(tempfile, "tempdir", str(private_tmp))

        temp_files_before = set(private_tmp.glob("*.wav"))
        provider.transcribe(b"audio", language="en")
        temp_files_after = set(private_tmp.glob("*.wav"))

        # No new wav files should remain
        assert temp_files_after == temp_files_before

    def test_transcribe_audio_formats(self):
        """transcribe handles different audio input formats (bytes in, VoiceInputResult out)."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.9
        mock_info.duration = 1.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        # WAV bytes
        wav_bytes = b"RIFF....WAVEfmt ....data...."
        result = provider.transcribe(wav_bytes, language="en")
        assert isinstance(result, VoiceInputResult)

        # MP3 bytes (just a different byte sequence)
        mp3_bytes = b"ID3....\xff\xfb...."
        result2 = provider.transcribe(mp3_bytes, language="en")
        assert isinstance(result2, VoiceInputResult)

    def test_transcribe_without_language_hint(self):
        """transcribe works without any language hint (auto-detect)."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        from backend.copilot.voice.schemas import VoiceInputResult

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="hola")]
        mock_info = MagicMock()
        mock_info.language = "es"
        mock_info.language_probability = 0.87
        mock_info.duration = 1.5
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio")

        assert result.detected_language == "es"
        assert result.transcript == "hola"

    def test_transcribe_error_writes_temp_file(self, monkeypatch):
        """Even when model.transcribe raises, the temp file is cleaned up."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
        import tempfile
        from pathlib import Path

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("fail")
        provider._model = mock_model

        # xdist-safe: scope to a private temp dir (see
        # test_transcribe_temp_file_cleaned_up).
        private_tmp = Path(tempfile.mkdtemp(prefix="copilot-stt-test-"))
        monkeypatch.setattr(tempfile, "tempdir", str(private_tmp))

        temp_files_before = set(private_tmp.glob("*.wav"))
        result = provider.transcribe(b"audio", language="en")
        temp_files_after = set(private_tmp.glob("*.wav"))

        assert result is None
        assert temp_files_after == temp_files_before


# Need tempfile for cleanup test
import tempfile


class TestWhisperSTTProviderFallback:
    """Fallback and edge-case behaviour."""

    def test_available_false_then_transcribe_returns_none(self):
        """When the model cannot be loaded, transcribe returns None."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        with patch.object(provider, "_load_model", return_value=None):
            result = provider.transcribe(b"audio")
            assert result is None

    def test_detection_confidence_default(self):
        """When info has None probability, defaults to 0.0."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = None
        mock_info.duration = 0.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio", language="en")
        assert result.detection_confidence == 0.0

    def test_duration_zero(self):
        """When info has zero duration, audio_duration_ms is 0."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.9
        mock_info.duration = 0.0
        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
        provider._model = mock_model

        result = provider.transcribe(b"audio", language="en")
        assert result is not None
        assert result.audio_duration_ms == 0

    def test_language_default_when_info_none(self):
        """When info is None, detected_language falls back to the provided language or 'en'."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_model.transcribe.return_value = (iter(mock_segments), None)
        provider._model = mock_model

        result = provider.transcribe(b"audio", language="fr")
        assert result.detected_language == "fr"

    def test_language_default_when_no_language_hint(self):
        """When info is None and no language hint, defaults to 'en'."""
        from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider

        provider = WhisperSTTProvider()
        mock_model = MagicMock()
        mock_segments = [MagicMock(text="test")]
        mock_model.transcribe.return_value = (iter(mock_segments), None)
        provider._model = mock_model

        result = provider.transcribe(b"audio")
        assert result.detected_language == "en"
