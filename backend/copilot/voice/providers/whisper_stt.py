"""Self-hosted STT provider — faster-whisper/CTranslate2.

Blueprint: §3.2, §22 item 1.
Uses a locally-run Whisper variant (faster-whisper 'small' or 'medium'
multilingual checkpoint) rather than a cloud STT service.

The actual model download and installation of faster-whisper is a one-time
setup step. This provider handles the runtime integration.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

from backend.copilot.voice.schemas import VoiceInputResult

logger = logging.getLogger(__name__)


class WhisperSTTProvider:
    """Self-hosted STT via faster-whisper.

    Usage:
        provider = WhisperSTTProvider(model_size="small")
        result = provider.transcribe(audio_bytes, language="ro")

    Requires: pip install faster-whisper
    Model is downloaded on first use (~500MB for 'small').
    """

    MODEL_SIZES = ("tiny", "small", "medium", "large-v3")

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "default",
    ) -> None:
        self.model_size = model_size if model_size in self.MODEL_SIZES else "small"
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._model_version = f"faster-whisper-{self.model_size}"

    def _load_model(self):
        """Lazy-load the Whisper model (downloaded on first use)."""
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper model loaded: %s (device=%s)", self.model_size, self.device)
            return self._model
        except ImportError:
            logger.warning(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )
            return None
        except Exception as exc:
            logger.error("Failed to load Whisper model: %s", exc)
            return None

    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> Optional[VoiceInputResult]:
        """Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data (WAV, MP3, etc.)
            language: Optional language hint (ISO code, e.g. 'ro', 'en').
                      If None, automatically detected.

        Returns:
            VoiceInputResult with transcript and metadata, or None on failure.
        """
        model = self._load_model()
        if model is None:
            return None

        try:
            # Write audio to a temp file (faster-whisper reads from disk)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                segments, info = model.transcribe(
                    tmp_path,
                    language=language,
                    beam_size=5,
                    vad_filter=True,
                )

                # Collect all segments
                transcript_parts: list[str] = []
                for seg in segments:
                    transcript_parts.append(seg.text)

                transcript = " ".join(transcript_parts).strip()
                detected_lang = info.language if info else (language or "en")
                detection_conf = info.language_probability if info else 0.0
                duration_ms = int((info.duration if info else 0) * 1000)

                return VoiceInputResult(
                    transcript=transcript or "",
                    detected_language=detected_lang,
                    detection_confidence=float(detection_conf or 0.0),
                    audio_duration_ms=duration_ms,
                    stt_model_version=self._model_version,
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        except Exception as exc:
            logger.error("STT transcription failed: %s", exc)
            return None

    @property
    def available(self) -> bool:
        """Check if the model is loadable."""
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False
