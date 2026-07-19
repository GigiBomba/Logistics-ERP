"""Comprehensive tests for the Piper TTS provider.

Covers: backend/copilot/voice/providers/piper_tts.py
- Provider interface compliance (TTSProvider ABC)
- available check returns correct status
- synthesize() with text input
- Language-specific voice selection
- Error handling (model not found, piper binary not found, timeout)
- Fallback behavior
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest


class TestPiperTTSProviderInterface:
    """PiperTTSProvider conforms to the TTSProvider interface."""

    def test_is_subclass_of_tts_provider(self):
        """PiperTTSProvider is a concrete TTSProvider."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSProvider
        assert issubclass(PiperTTSProvider, TTSProvider)

    def test_has_synthesize_method(self):
        """PiperTTSProvider implements synthesize."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        assert hasattr(PiperTTSProvider, "synthesize")

    def test_has_supported_languages_method(self):
        """PiperTTSProvider implements supported_languages."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        assert hasattr(PiperTTSProvider, "supported_languages")

    def test_provider_id_and_model_id(self):
        """Provider metadata is set correctly."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        assert PiperTTSProvider.provider_id == "piper-tts"
        assert PiperTTSProvider.model_id == "piper-multilingual"


class TestPiperTTSProviderInit:
    """PiperTTSProvider initialisation."""

    def test_default_voice_dir(self):
        """Default voice directory is set."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        # On Windows, paths use backslashes; use os-agnostic check
        default_path = Path("/usr/share/piper/voices")
        assert provider.voice_dir.parts == default_path.parts

    def test_custom_voice_dir(self):
        """Custom voice directory is accepted."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider(voice_dir="/custom/voices")
        expected = Path("/custom/voices")
        assert provider.voice_dir.parts == expected.parts

    def test_custom_voice_map(self):
        """Custom voice map overrides defaults."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        custom_map = {"en": "custom-en-voice", "fr": "custom-fr-voice"}
        provider = PiperTTSProvider(default_voice_map=custom_map)
        assert provider._voice_map == custom_map

    def test_default_voice_map_size(self):
        """Default voice map covers multiple languages."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        assert len(provider._voice_map) >= 12  # At least 12 default entries

    def test_voice_dir_is_path(self):
        """voice_dir is stored as a Path."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        assert isinstance(provider.voice_dir, Path)

    def test_available_starts_none(self):
        """_available starts as None (lazy)."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        assert provider._available is None


class TestPiperTTSProviderAvailable:
    """available property."""

    @patch("backend.copilot.voice.providers.piper_tts.subprocess.run")
    def test_available_true(self, mock_run):
        """available returns True when piper binary responds."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider

        mock_run.return_value = MagicMock(returncode=0)
        provider = PiperTTSProvider()
        assert provider.available is True
        assert provider._available is True
        mock_run.assert_called_once_with(
            ["piper", "--help"], capture_output=True, timeout=5
        )

    @patch("backend.copilot.voice.providers.piper_tts.subprocess.run")
    def test_available_false_nonzero_returncode(self, mock_run):
        """available returns False when piper binary returns non-zero."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider

        mock_run.return_value = MagicMock(returncode=1)
        provider = PiperTTSProvider()
        assert provider.available is False

    @patch("backend.copilot.voice.providers.piper_tts.subprocess.run")
    def test_available_false_on_exception(self, mock_run):
        """available returns False when piper binary cannot be run."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider

        mock_run.side_effect = FileNotFoundError("piper not found")
        provider = PiperTTSProvider()
        assert provider.available is False

    @patch("backend.copilot.voice.providers.piper_tts.subprocess.run")
    def test_available_caches_result(self, mock_run):
        """available caches its result after first check."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider

        mock_run.return_value = MagicMock(returncode=0)
        provider = PiperTTSProvider()
        _ = provider.available
        _ = provider.available
        _ = provider.available
        # subprocess.run should only be called once
        mock_run.assert_called_once()

    @patch("backend.copilot.voice.providers.piper_tts.subprocess.run")
    def test_available_caches_false(self, mock_run):
        """available caches False result."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider

        mock_run.side_effect = FileNotFoundError("piper not found")
        provider = PiperTTSProvider()
        first = provider.available
        second = provider.available
        assert first is False
        assert second is False
        mock_run.assert_called_once()


class TestPiperTTSProviderSupportedLanguages:
    """supported_languages method."""

    def test_returns_list(self):
        """supported_languages returns a list of strings."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        langs = provider.supported_languages()
        assert isinstance(langs, list)
        assert all(isinstance(l, str) for l in langs)

    def test_contains_expected_languages(self):
        """supported_languages contains expected language codes."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        langs = provider.supported_languages()
        assert "en" in langs
        assert "ro" in langs
        assert "de" in langs
        assert "fr" in langs

    def test_reflects_voice_map(self):
        """supported_languages returns keys from the voice map."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        custom_map = {"en": "en-voice", "ro": "ro-voice"}
        provider = PiperTTSProvider(default_voice_map=custom_map)
        assert provider.supported_languages() == ["en", "ro"]

    def test_unsupported_language_not_in_list(self):
        """Languages not in the voice map are not in supported_languages."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        provider = PiperTTSProvider()
        langs = provider.supported_languages()
        assert "xx" not in langs


class PiperVoiceDir:
    """Helper: creates a temporary voice directory with model files for testing."""

    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "piper_voices"
        self.dir.mkdir()
        # Create placeholder model files
        for lang, voice in [
            ("en", "en_US-less-medium"),
            ("ro", "ro_RO-mihai-medium"),
            ("de", "de_DE-thorsten-medium"),
        ]:
            (self.dir / f"{voice}.onnx").write_text("model")
            (self.dir / f"{voice}.json").write_text("{}")


class TestPiperTTSProviderSynthesize:
    """synthesize() method."""

    @pytest.mark.asyncio
    async def test_synthesize_success(self, tmp_path):
        """synthesize returns audio bytes on success."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))
        request = TTSRequest(text="Hello world", language="en")

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")

            # Mock read_bytes on the temp output file
            with patch.object(Path, "read_bytes", return_value=b"RIFF....WAV audio data...."):
                audio = await provider.synthesize(request)

        assert audio == b"RIFF....WAV audio data...."
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_voice_selection(self, tmp_path):
        """synthesize selects the correct voice model per language."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch.object(Path, "read_bytes", return_value=b"audio"):
                # Romanian
                request_ro = TTSRequest(text="Bună ziua", language="ro")
                await provider.synthesize(request_ro)

                ro_call = mock_run.call_args
                ro_args = ro_call[0][0]
                assert any("ro_RO-mihai-medium" in str(arg) for arg in ro_args)

                # German
                request_de = TTSRequest(text="Guten Tag", language="de")
                await provider.synthesize(request_de)

                de_call = mock_run.call_args
                de_args = de_call[0][0]
                assert any("de_DE-thorsten-medium" in str(arg) for arg in de_args)

    @pytest.mark.asyncio
    async def test_synthesize_unknown_language_falls_back_to_en(self, tmp_path):
        """Unknown languages fall back to English voice model."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch.object(Path, "read_bytes", return_value=b"audio"):
                request = TTSRequest(text="Hello", language="xx")
                await provider.synthesize(request)

                call_args = mock_run.call_args[0][0]
                assert any("en_US-less-medium" in str(arg) for arg in call_args)

    @pytest.mark.asyncio
    async def test_synthesize_model_not_found(self, tmp_path):
        """synthesize returns empty bytes when voice model file is missing."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        # Use an empty directory — no model files present
        provider = PiperTTSProvider(voice_dir=str(tmp_path / "empty_voices"))
        request = TTSRequest(text="Hello", language="en")
        audio = await provider.synthesize(request)

        assert audio == b""

    @pytest.mark.asyncio
    async def test_synthesize_nonzero_returncode(self, tmp_path):
        """synthesize returns empty bytes when piper returns non-zero."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))
        request = TTSRequest(text="Hello", language="en")

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error occurred")
            audio = await provider.synthesize(request)

        assert audio == b""

    @pytest.mark.asyncio
    async def test_synthesize_timeout(self, tmp_path):
        """synthesize returns empty bytes on timeout."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))
        request = TTSRequest(text="Hello", language="en")

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="piper", timeout=30)
            audio = await provider.synthesize(request)

        assert audio == b""

    @pytest.mark.asyncio
    async def test_synthesize_file_not_found(self, tmp_path):
        """synthesize returns empty bytes when piper binary is missing."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))
        request = TTSRequest(text="Hello", language="en")

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("piper not found")
            audio = await provider.synthesize(request)

        assert audio == b""

    @pytest.mark.asyncio
    async def test_synthesize_generic_exception(self, tmp_path):
        """synthesize returns empty bytes on any unexpected error."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))
        request = TTSRequest(text="Hello", language="en")

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")
            audio = await provider.synthesize(request)

        assert audio == b""

    @pytest.mark.asyncio
    async def test_synthesize_text_encoded(self, tmp_path):
        """Text is UTF-8 encoded and passed to piper stdin."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch.object(Path, "read_bytes", return_value=b"audio"):
                request = TTSRequest(text="Bună ziua", language="ro")
                await provider.synthesize(request)

                assert mock_run.call_args[1]["input"] == "Bună ziua".encode("utf-8")

    @pytest.mark.asyncio
    async def test_synthesize_uses_temp_output_file(self, tmp_path):
        """Piper writes to a temp file which is then read."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch.object(Path, "read_bytes", return_value=b"audio data"):
                request = TTSRequest(text="Hello", language="en")
                audio = await provider.synthesize(request)

        assert audio == b"audio data"

        # Check --output_file was passed
        call_args = mock_run.call_args[0][0]
        assert "--output_file" in call_args

    @pytest.mark.asyncio
    async def test_synthesize_output_file_cleaned_up(self, tmp_path):
        """Temp output file is cleaned up after synthesis."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        unlink_called = False
        original_unlink = Path.unlink

        def tracking_unlink(self_path, missing_ok=True):
            nonlocal unlink_called
            unlink_called = True
            return original_unlink(self_path, missing_ok=missing_ok)

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch.object(Path, "unlink", tracking_unlink):
                with patch.object(Path, "read_bytes", return_value=b"audio"):
                    request = TTSRequest(text="Hello", language="en")
                    await provider.synthesize(request)

        assert unlink_called, "Temp file was not cleaned up"

    @pytest.mark.asyncio
    async def test_synthesize_command_structure(self, tmp_path):
        """The piper command is constructed correctly."""
        from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
        from backend.copilot.voice.tts import TTSRequest

        voice_dir = PiperVoiceDir(tmp_path)
        provider = PiperTTSProvider(voice_dir=str(voice_dir.dir))

        with patch("backend.copilot.voice.providers.piper_tts.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            with patch.object(Path, "read_bytes", return_value=b"audio"):
                request = TTSRequest(text="Hello", language="en")
                await provider.synthesize(request)

        args, kwargs = mock_run.call_args
        cmd = args[0]

        assert cmd[0] == "piper"
        assert "--model" in cmd
        assert "--config" in cmd
        assert "--output_file" in cmd
        assert any("en_US-less-medium.onnx" in str(a) for a in cmd)
        assert any("en_US-less-medium.json" in str(a) for a in cmd)
        assert kwargs["input"] == b"Hello"
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] == 30
