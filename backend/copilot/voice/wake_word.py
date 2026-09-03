"""Wake-word detection providers — interface + concrete engine (§3.5, §16).

Blueprint: §3.5 (voice input), §16 (Enterprise hands-free voice).

The wake-word engine is an **optional** dependency.  ``OpenWakeWordProvider``
attempts to load ``openwakeword`` (https://github.com/dscripka/openWakeWord)
and degrades to a non-functional state when the package is missing, so the
desktop app keeps push-to-talk fully working:

    pip install openwakeword        # optional — enables wake-word detection

No wake-word library is a declared project dependency today (verified against
``pyproject.toml`` / ``requirements*.txt``), so the engine is guarded exactly
like the Whisper STT provider: an import failure makes ``available`` return
``False`` and callers fall back to push-to-talk silently (logged only).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class WakeWordRequest(BaseModel):
    """A streamed audio chunk for wake-word detection.

    The desktop ``AudioRecorder`` produces 16 kHz mono Int16 PCM — the
    default input format of openwakeword.
    """

    model_config = ConfigDict(extra="forbid")

    audio: bytes
    sample_rate: int = 16000


class WakeWordResult(BaseModel):
    """Outcome of processing one audio chunk."""

    model_config = ConfigDict(extra="forbid")

    detected: bool = False
    confidence: float = 0.0
    keyword: str = ""


class WakeWordProvider(ABC):
    """Every concrete wake-word engine implements this interface.

    Streaming contract:
      - ``process()`` is called repeatedly with successive PCM chunks; the
        engine keeps internal state so a keyword spanning chunk boundaries
        is still detected.
      - ``reset()`` clears that state after a detection (or when monitoring
        stops) so the next phrase starts clean.
    """

    provider_id: str = ""
    model_id: str = ""

    @abstractmethod
    def process(self, request: WakeWordRequest) -> WakeWordResult:
        """Detect the wake word in *request.audio*.  Never raises."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Clear streaming state between monitoring sessions."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether the engine is usable (engine + models loaded)."""
        ...

    @property
    def unavailable_reason(self) -> str:
        """Human-readable reason for ``available is False``."""
        return ""

    def close(self) -> None:
        """Release engine resources (default no-op)."""
        return None


class OpenWakeWordProvider(WakeWordProvider):
    """openwakeword-based engine (optional dependency).

    Uses the ``hey jarvis`` model shipped with ``openwakeword``.  When the
    package is not installed the provider is inert (``available`` is
    ``False``, ``process`` always returns ``detected=False``) — the UI falls
    back to push-to-talk.
    """

    provider_id: str = "openwakeword"
    model_id: str = "openwakeword-hey_jarvis"

    #: Default keyword(s) — openwakeword bundles "hey jarvis".
    DEFAULT_KEYWORDS: List[str] = ["hey jarvis"]
    DEFAULT_THRESHOLD: float = 0.5

    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._keywords = keywords or list(self.DEFAULT_KEYWORDS)
        self._threshold = threshold
        self._model = None
        self._reason = ""
        self._load()

    # ── Engine loading (guarded) ───────────────────────────────────────

    def _load(self) -> None:
        """Attempt to import and instantiate the openwakeword model."""
        if self._model is not None:
            return
        try:
            import numpy as np  # noqa: F401 — required by openwakeword

            from openwakeword.model import Model

            self._model = Model(wakeword_models=self._keywords)
            self._reason = ""
        except ImportError:
            self._model = None
            self._reason = (
                "openwakeword not installed — install with `pip install openwakeword`"
            )
            logger.info("Wake-word engine unavailable: %s", self._reason)
        except Exception as exc:
            self._model = None
            self._reason = f"openwakeword failed to load: {exc}"
            logger.error("Wake-word engine failed to load: %s", exc)

    # ── WakeWordProvider ───────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def unavailable_reason(self) -> str:
        return self._reason or (
            "openwakeword not installed — install with `pip install openwakeword`"
        )

    def process(self, request: WakeWordRequest) -> WakeWordResult:
        if self._model is None:
            return WakeWordResult(detected=False)
        try:
            import numpy as np

            samples = np.frombuffer(request.audio, dtype=np.int16)
            if samples.size == 0:
                return WakeWordResult(detected=False)
            pcm = samples.astype(np.float32) / 32768.0
            prediction = self._model.predict(pcm)
            # prediction: (n_keywords, n_chunks) — use the latest chunk.
            arr = np.asarray(prediction)
            latest = arr[:, -1] if arr.ndim == 2 else arr
            confidence = float(np.max(latest)) if latest.size else 0.0
            if confidence >= self._threshold:
                keyword = self._keywords[0] if self._keywords else ""
                return WakeWordResult(
                    detected=True, confidence=confidence, keyword=keyword
                )
            return WakeWordResult(detected=False, confidence=confidence)
        except Exception as exc:
            logger.error("Wake-word processing failed: %s", exc)
            return WakeWordResult(detected=False)

    def reset(self) -> None:
        if self._model is None:
            return
        try:
            self._model.reset()
        except Exception as exc:
            logger.debug("Wake-word model reset failed: %s", exc)