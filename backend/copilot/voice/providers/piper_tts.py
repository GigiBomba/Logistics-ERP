"""Self-hosted TTS provider — Piper TTS.

Blueprint: §3.3.
Uses Piper TTS (https://github.com/rhasspy/piper) for local text-to-speech.
Multilingual, supports 22 languages with appropriate voice models.

Requires: piper-tts (pip install piper-tts)
Voice models must be downloaded separately per language.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from backend.copilot.voice.tts import TTSProvider, TTSRequest

logger = logging.getLogger(__name__)


class PiperTTSProvider(TTSProvider):
    """Self-hosted TTS via Piper.

    Piper runs as a subprocess. Voice models are downloaded per-language
    and cached in a configurable directory.

    Usage:
        provider = PiperTTSProvider(voice_dir="/path/to/voices")
        audio = await provider.synthesize(TTSRequest(text="Bună ziua", language="ro"))
    """

    provider_id: str = "piper-tts"
    model_id: str = "piper-multilingual"

    def __init__(
        self,
        voice_dir: Optional[str] = None,
        default_voice_map: Optional[dict[str, str]] = None,
    ) -> None:
        self.voice_dir = Path(voice_dir or "/usr/share/piper/voices")
        # Language -> voice model file mapping
        self._voice_map = default_voice_map or {
            "en": "en_US-less-medium",
            "ro": "ro_RO-mihai-medium",
            "de": "de_DE-thorsten-medium",
            "fr": "fr_FR-siwis-medium",
            "es": "es_ES-davefx-medium",
            "it": "it_IT-paola-medium",
            "nl": "nl_NL-mls-medium",
            "pt": "pt_BR-edresson-medium",
            "pl": "pl_PL-mls-medium",
            "ru": "ru_RU-ruslan-medium",
            "tr": "tr_TR-dfki-medium",
            "sv": "sv_SE-nst-medium",
        }
        self._available = None

    async def synthesize(self, request: TTSRequest) -> bytes:
        """Synthesize text to WAV audio bytes."""
        voice = self._voice_map.get(request.language, self._voice_map.get("en", ""))
        model_path = self.voice_dir / f"{voice}.onnx"
        config_path = self.voice_dir / f"{voice}.json"

        if not model_path.exists():
            logger.warning(
                "Voice model not found: %s (language=%s). "
                "Download from https://huggingface.co/rhasspy/piper-voices",
                model_path, request.language,
            )
            return b""

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

        try:
            result = subprocess.run(
                [
                    "piper",
                    "--model", str(model_path),
                    "--config", str(config_path),
                    "--output_file", output_path,
                ],
                input=request.text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error("Piper failed: %s", result.stderr.decode())
                return b""

            audio_bytes = Path(output_path).read_bytes()
            return audio_bytes

        except subprocess.TimeoutExpired:
            logger.error("Piper timed out for language=%s", request.language)
            return b""
        except FileNotFoundError:
            logger.error("Piper binary not found. Install: pip install piper-tts")
            return b""
        except Exception as exc:
            logger.error("TTS synthesis failed: %s", exc)
            return b""
        finally:
            Path(output_path).unlink(missing_ok=True)

    def supported_languages(self) -> List[str]:
        return list(self._voice_map.keys())

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5)
                self._available = result.returncode == 0
            except Exception:
                self._available = False
        return self._available
