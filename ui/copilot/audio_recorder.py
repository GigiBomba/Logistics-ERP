"""AudioRecorder — QObject wrapping QAudioSource for PCM recording.

Records 16 kHz mono Int16 audio from the default input device.
Emits signals for recording lifecycle and delivers raw PCM bytes.

Usage:
    recorder = AudioRecorder()
    recorder.audio_ready.connect(on_audio)
    recorder.start_recording()
    # ... speak ...
    recorder.stop_recording()
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QByteArray, QObject, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices

logger = logging.getLogger(__name__)


class AudioRecorder(QObject):
    """Record PCM audio from the default microphone input.

    Signals:
        recording_started: Emitted when capture begins.
        recording_stopped: Emitted when capture ends.
        audio_ready: Delivers the recorded raw PCM ``bytes`` after stop.
        error_occurred: Emitted on device or format errors with a message.
    """

    recording_started = Signal()
    recording_stopped = Signal()
    audio_ready = Signal(bytes)
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._source: Optional[QAudioSource] = None
        self._buffer = QByteArray()

    # ── Public API ──────────────────────────────────────────────────────

    def start_recording(self) -> None:
        """Open the default microphone and begin capturing PCM data."""
        if self._source is not None:
            logger.debug("AudioRecorder: already recording, ignoring start")
            return

        fmt = QAudioFormat()
        fmt.setSampleRate(16_000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)

        input_device = QMediaDevices.defaultAudioInput()
        if input_device is None:
            self.error_occurred.emit("No default audio input device found")
            return

        if not input_device.isFormatSupported(fmt):
            fallback = input_device.preferredFormat()
            logger.warning(
                "Requested format not supported; using preferred %s",
                _format_name(fallback),
            )
            fmt = fallback

        self._source = QAudioSource(input_device, fmt)
        self._buffer.clear()

        io_device = self._source.start()
        if io_device is None:
            self.error_occurred.emit("QAudioSource failed to start")
            self._source = None
            return

        io_device.readyRead.connect(self._on_ready_read)
        logger.info(
            "AudioRecorder started (%s Hz, %s ch, %s)",
            fmt.sampleRate(),
            fmt.channelCount(),
            _format_name(fmt),
        )
        self.recording_started.emit()

    def stop_recording(self) -> Optional[bytes]:
        """Stop capture and emit ``audio_ready`` with recorded PCM data.

        Returns the recorded ``bytes`` (or ``None`` if nothing was captured).
        """
        if self._source is None:
            return None

        self._source.stop()
        self._source.deleteLater()
        self._source = None

        self.recording_stopped.emit()

        if self._buffer.size() == 0:
            logger.debug("AudioRecorder: stopped with empty buffer")
            return None

        result: bytes = self._buffer.data()
        self._buffer.clear()
        logger.info("AudioRecorder stopped — captured %d bytes", len(result))
        self.audio_ready.emit(result)
        return result

    # ── Internal ────────────────────────────────────────────────────────

    def _on_ready_read(self) -> None:
        """Accumulate incoming PCM chunks into the internal buffer."""
        io = self.sender()
        if io is None:
            return
        chunk = io.readAll()
        self._buffer.append(chunk)


def _format_name(fmt: QAudioFormat) -> str:
    """Return a human-readable label for an audio format."""
    try:
        sf = fmt.sampleFormat()
    except Exception:
        sf = "?"
    return f"{fmt.sampleRate()}/{fmt.channelCount()}ch/{sf}"
