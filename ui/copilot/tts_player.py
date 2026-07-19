"""TTSPlayer — QObject wrapping QMediaPlayer + QAudioOutput for playback.

Writes incoming audio bytes to a temporary file and plays it via the
system audio output.  Cleans up temp files after playback completes.

Usage:
    player = TTSPlayer()
    player.play_audio(wav_bytes)
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

logger = logging.getLogger(__name__)


class TTSPlayer(QObject):
    """Play TTS audio data through the default system audio output.

    Signals:
        playback_finished: Emitted when the audio playback ends (or is
                           stopped early).
    """

    playback_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)

        self._temp_files: list[str] = []
        self._current_file: Optional[str] = None

        # Forward the native media-status change to our simplified signal.
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    # ── Public API ──────────────────────────────────────────────────────

    def play_audio(self, audio_bytes: bytes, suffix: str = ".wav") -> None:
        """Write *audio_bytes* to a temp file and start playback.

        Args:
            audio_bytes: Raw audio data (WAV, MP3, Ogg, etc.).
            suffix: File extension for the temp file (default ``.wav``).
        """
        # Stop any in-flight playback first.
        self.stop()

        fd, path = tempfile.mkstemp(suffix=suffix, prefix="tts_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(audio_bytes)
        except Exception:
            os.unlink(path)
            raise

        self._current_file = path
        self._temp_files.append(path)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        logger.debug("TTSPlayer: playing %s (%d bytes)", path, len(audio_bytes))

    def stop(self) -> None:
        """Stop playback immediately and reset the player."""
        self._player.stop()
        self._current_file = None

    def cleanup(self) -> None:
        """Remove all temporary files that were created for playback."""
        self.stop()
        for path in self._temp_files:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("TTSPlayer: cleanup failed for %s: %s", path, exc)
        self._temp_files.clear()

    # ── Internal ────────────────────────────────────────────────────────

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Emit ``playback_finished`` when the media reaches its end."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Clean up the file that just finished playing.
            if self._current_file is not None:
                try:
                    Path(self._current_file).unlink(missing_ok=True)
                    self._temp_files = [
                        p for p in self._temp_files if p != self._current_file
                    ]
                except Exception as exc:
                    logger.warning(
                        "TTSPlayer: cleanup of %s failed: %s",
                        self._current_file,
                        exc,
                    )
                self._current_file = None
            self.playback_finished.emit()

    def __del__(self) -> None:
        self.cleanup()
