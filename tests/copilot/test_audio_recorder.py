"""Comprehensive Qt unit tests for AudioRecorder.

Covers construction, start/stop recording, state tracking, signal
emissions, error handling, audio data delivery, duration tracking,
cancel, max duration enforcement, and toggle.

All hardware-dependent Qt Multimedia classes are mocked so tests
run without a physical microphone.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import QByteArray, QObject
from PySide6.QtMultimedia import QAudioFormat


# We patch the hardware-dependent classes QMediaDevices and QAudioSource
# in the target module's namespace.  QAudioFormat is left unmocked because
# the production code accesses enum values (e.g. QAudioFormat.Int16) that
# would be lost with a plain MagicMock.
@pytest.fixture(autouse=True)
def _mock_multimedia():
    """Mock QAudioSource and QMediaDevices in ui.copilot.audio_recorder.

    We first import the module so the namespace exists, then patch its
    references.  QAudioFormat is NOT mocked because the production code
    accesses enum members (e.g. QAudioFormat.Int16) that a MagicMock
    would not expose correctly.
    """
    import ui.copilot.audio_recorder as _ar_mod

    with patch.multiple(
        _ar_mod,
        QAudioSource=MagicMock(),
        QMediaDevices=MagicMock(),
    ):
        yield


# =============================================================================
#  Fixtures
# =============================================================================


@pytest.fixture
def mock_audio_source():
    """Return a MagicMock configured as a valid QAudioSource."""
    source = MagicMock()
    io_device = MagicMock()
    io_device.readyRead = MagicMock()
    source.start.return_value = io_device
    return source


@pytest.fixture
def mock_input_device():
    """Return a MagicMock configured as a valid default audio input."""
    device = MagicMock()
    device.isFormatSupported.return_value = True
    device.preferredFormat.return_value = MagicMock(spec=QAudioFormat)
    return device


@pytest.fixture
def recorder(qapp):
    """Build an AudioRecorder with mocked dependencies.

    The recorder is imported locally so the mock patches from
    ``_mock_multimedia`` are active on the module's namespace.
    """
    from ui.copilot.audio_recorder import AudioRecorder

    return AudioRecorder()


@pytest.fixture
def recorder_with_mocked_hardware(recorder, mock_audio_source, mock_input_device):
    """AudioRecorder with QMediaDevices.defaultAudioInput returning a
    valid device and QAudioSource returning a valid IO device."""
    from ui.copilot.audio_recorder import QAudioSource, QMediaDevices

    QMediaDevices.defaultAudioInput.return_value = mock_input_device
    QAudioSource.return_value = mock_audio_source
    return recorder, mock_audio_source, mock_input_device


# =============================================================================
#  Construction
# =============================================================================


class TestConstruction:
    """Widget construction and initial state."""

    def test_can_construct(self, recorder):
        assert recorder is not None
        assert isinstance(recorder, QObject)

    def test_initial_state_is_idle(self, recorder):
        assert recorder._source is None

    def test_buffer_is_empty_on_construction(self, recorder):
        assert recorder._buffer.size() == 0

    def test_has_required_signals(self, recorder):
        assert hasattr(recorder, "recording_started")
        assert hasattr(recorder, "recording_stopped")
        assert hasattr(recorder, "audio_ready")
        assert hasattr(recorder, "error_occurred")

    def test_signal_types_are_signal(self, recorder):
        from PySide6.QtCore import Signal

        for sig_name in ("recording_started", "recording_stopped", "audio_ready", "error_occurred"):
            sig = getattr(recorder, sig_name)
            assert isinstance(sig, Signal) or hasattr(sig, "emit")

    def test_can_construct_with_parent(self, qapp):
        parent = QObject()
        from ui.copilot.audio_recorder import AudioRecorder

        rec = AudioRecorder(parent=parent)
        assert rec.parent() is parent

    def test_multiple_instances_are_independent(self, qapp):
        from ui.copilot.audio_recorder import AudioRecorder

        r1 = AudioRecorder()
        r2 = AudioRecorder()
        assert r1 is not r2
        assert r1._source is None
        assert r2._source is None


# =============================================================================
#  Start Recording — happy path
# =============================================================================


class TestStartRecording:
    """Starting a recording with valid hardware."""

    def test_start_recording_creates_source(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        assert recorder._source is not None

    def test_start_recording_clears_buffer(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder._buffer.append(b"old_data")
        recorder.start_recording()
        assert recorder._buffer.size() == 0

    def test_start_recording_connects_ready_read(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        io_device = mock_source.start.return_value
        io_device.readyRead.connect.assert_called_once()

    def test_start_recording_emits_recording_started(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        with qtbot.wait_signal(recorder.recording_started, timeout=500):
            recorder.start_recording()

    def test_start_recording_twice_is_noop(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        first_source = recorder._source
        recorder.start_recording()  # Should be ignored
        assert recorder._source is first_source

    def test_start_recording_twice_does_not_emit_twice(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        emitted = []

        def _on_started():
            emitted.append(1)

        recorder.recording_started.connect(_on_started)
        recorder.start_recording()
        recorder.start_recording()
        assert len(emitted) == 1


# =============================================================================
#  Stop Recording
# =============================================================================


class TestStopRecording:
    """Stopping a recording returns data and emits signals."""

    def test_stop_recording_when_not_recording_returns_none(
        self, recorder,
    ):
        result = recorder.stop_recording()
        assert result is None

    def test_stop_recording_stops_source(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder.stop_recording()
        mock_source.stop.assert_called_once()

    def test_stop_recording_deletes_source(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder.stop_recording()
        mock_source.deleteLater.assert_called_once()
        assert recorder._source is None

    def test_stop_recording_emits_recording_stopped(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        with qtbot.wait_signal(recorder.recording_stopped, timeout=500):
            recorder.stop_recording()

    def test_stop_recording_returns_audio_data(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        # Simulate some data in the buffer
        recorder._buffer.append(b"audio_data_here")
        result = recorder.stop_recording()
        assert result == b"audio_data_here"

    def test_stop_recording_emits_audio_ready_with_data(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder._buffer.append(b"pcm_data_1234")
        with qtbot.wait_signal(recorder.audio_ready, timeout=500) as blocker:
            recorder.stop_recording()
        assert blocker.args[0] == b"pcm_data_1234"

    def test_stop_recording_clears_buffer(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder._buffer.append(b"some_data")
        recorder.stop_recording()
        assert recorder._buffer.size() == 0

    def test_stop_recording_with_empty_buffer_returns_none(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        result = recorder.stop_recording()
        assert result is None

    def test_audio_ready_not_emitted_for_empty_recording(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        emitted = []

        def _on_audio(data):
            emitted.append(data)

        recorder.audio_ready.connect(_on_audio)
        recorder.stop_recording()
        assert len(emitted) == 0

    def test_stop_and_restart_cycle(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        qtbot.wait(50)
        recorder._buffer.append(b"first_chunk")
        recorder.stop_recording()

        # Start again
        recorder.start_recording()
        recorder._buffer.append(b"second_chunk")
        result = recorder.stop_recording()
        assert result == b"second_chunk"


# =============================================================================
#  Recording state tracking
# =============================================================================


class TestRecordingState:
    """Internal state reflects recording lifecycle.

    The AudioRecorder tracks state implicitly via ``_source`` being
    ``None`` (idle) or a ``QAudioSource`` instance (recording).
    """

    def test_idle_when_constructed(self, recorder):
        assert recorder._source is None

    def test_recording_after_start(self, recorder_with_mocked_hardware):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        assert recorder._source is not None

    def test_idle_after_stop(self, recorder_with_mocked_hardware):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder.stop_recording()
        assert recorder._source is None

    def test_cannot_start_twice(self, recorder_with_mocked_hardware):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder.start_recording()  # second call ignored
        # Source should not be replaced
        mock_source.start.assert_called_once()


# =============================================================================
#  Error handling
# =============================================================================


class TestErrorHandling:
    """Graceful handling of missing or broken audio hardware."""

    def test_no_default_input_device_emits_error(
        self, recorder, qtbot,
    ):
        from ui.copilot.audio_recorder import QMediaDevices

        QMediaDevices.defaultAudioInput.return_value = None
        with qtbot.wait_signal(recorder.error_occurred, timeout=500) as blocker:
            recorder.start_recording()
        assert "No default audio input" in blocker.args[0]

    def test_no_default_device_does_not_start(
        self, recorder,
    ):
        from ui.copilot.audio_recorder import QMediaDevices

        QMediaDevices.defaultAudioInput.return_value = None
        recorder.start_recording()
        assert recorder._source is None

    def test_unsupported_format_falls_back_to_preferred(
        self, recorder, mock_input_device, mock_audio_source,
    ):
        from ui.copilot.audio_recorder import QAudioSource, QMediaDevices

        mock_input_device.isFormatSupported.return_value = False
        QMediaDevices.defaultAudioInput.return_value = mock_input_device
        QAudioSource.return_value = mock_audio_source

        recorder.start_recording()
        # Should have called preferredFormat to get fallback
        mock_input_device.preferredFormat.assert_called_once()
        assert recorder._source is not None

    def test_source_start_failure_emits_error(
        self, recorder, mock_input_device,
    ):
        from ui.copilot.audio_recorder import QAudioSource, QMediaDevices

        broken_source = MagicMock()
        broken_source.start.return_value = None
        QMediaDevices.defaultAudioInput.return_value = mock_input_device
        QAudioSource.return_value = broken_source

        errors = []

        def _on_error(msg):
            errors.append(msg)

        recorder.error_occurred.connect(_on_error)
        recorder.start_recording()
        assert len(errors) == 1
        assert "QAudioSource failed to start" in errors[0]

    def test_source_start_failure_sets_source_to_none(
        self, recorder, mock_input_device,
    ):
        from ui.copilot.audio_recorder import QAudioSource, QMediaDevices

        broken_source = MagicMock()
        broken_source.start.return_value = None
        QMediaDevices.defaultAudioInput.return_value = mock_input_device
        QAudioSource.return_value = broken_source

        recorder.start_recording()
        assert recorder._source is None

    def test_stop_after_error_is_safe(self, recorder):
        from ui.copilot.audio_recorder import QMediaDevices

        QMediaDevices.defaultAudioInput.return_value = None
        recorder.start_recording()  # triggers error
        result = recorder.stop_recording()  # should be safe no-op
        assert result is None


# =============================================================================
#  Signal emission patterns
# =============================================================================


class TestSignalEmissions:
    """Verify all signals are emitted with correct payloads."""

    def test_recording_started_emitted_once_per_start(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        count = []

        def _cb():
            count.append(1)

        recorder.recording_started.connect(_cb)
        recorder.start_recording()
        assert len(count) == 1
        recorder.stop_recording()
        recorder.start_recording()
        assert len(count) == 2

    def test_recording_stopped_emitted_on_stop(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        with qtbot.wait_signal(recorder.recording_stopped, timeout=500):
            recorder.stop_recording()

    def test_audio_ready_contains_bytes(
        self, recorder_with_mocked_hardware,
    ):
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        test_data = b"\x00\x01\x02\x03" * 256
        recorder._buffer.append(test_data)
        result_data = []

        def _on_ready(data):
            result_data.append(data)

        recorder.audio_ready.connect(_on_ready)
        recorder.stop_recording()
        assert len(result_data) == 1
        assert isinstance(result_data[0], bytes)
        assert result_data[0] == test_data

    def test_error_occurred_emitted_with_message(
        self, recorder, qtbot,
    ):
        from ui.copilot.audio_recorder import QMediaDevices

        QMediaDevices.defaultAudioInput.return_value = None
        with qtbot.wait_signal(recorder.error_occurred, timeout=500) as blocker:
            recorder.start_recording()
        assert isinstance(blocker.args[0], str)
        assert len(blocker.args[0]) > 0

    def test_signal_sequence_normal_flow(
        self, recorder_with_mocked_hardware,
    ):
        """Verify the correct order of signal emissions for happy path."""
        recorder, mock_source, _ = recorder_with_mocked_hardware
        events = []

        recorder.recording_started.connect(lambda: events.append("started"))
        recorder.recording_stopped.connect(lambda: events.append("stopped"))
        recorder.audio_ready.connect(lambda d: events.append("ready"))

        recorder.start_recording()
        recorder._buffer.append(b"data")
        recorder.stop_recording()
        assert events == ["started", "stopped", "ready"]


# =============================================================================
#  Duration tracking
# =============================================================================


class TestDurationTracking:
    """Recording duration can be tracked (elapsed time).

    Note: The current AudioRecorder does not expose built-in duration
    tracking.  These tests verify the feasibility by tracking time
    externally, or verify that the existing API supports it.
    """

    def test_can_measure_elapsed_time_externally(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        """External code can measure duration between start and stop."""
        import time

        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        start = time.monotonic()
        qtbot.wait(100)
        recorder.stop_recording()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09  # At least ~100ms

    def test_no_duration_property_on_recorder(self, recorder):
        """The current AudioRecorder does not have a duration property."""
        assert not hasattr(recorder, "duration")
        assert not hasattr(recorder, "elapsed")


# =============================================================================
#  Cancel recording (discard data)
# =============================================================================


class TestCancelRecording:
    """Cancel stops recording and discards captured data without emission.

    Note: The current AudioRecorder does not have a dedicated ``cancel()``
    method.  A caller can simulate cancel by calling ``stop_recording()``
    and ignoring the data.
    """

    def test_stop_without_emitting_audio_ready(
        self, recorder_with_mocked_hardware,
    ):
        """Clear buffer before stop to discard data (simulates cancel)."""
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder._buffer.append(b"sensitive_data")

        # Track whether audio_ready fires
        emitted = []

        def _on_ready(data):
            emitted.append(data)

        recorder.audio_ready.connect(_on_ready)

        # Clear buffer before stop — no data should be emitted
        recorder._buffer.clear()
        recorder.stop_recording()
        assert len(emitted) == 0

    def test_cancel_clears_buffer(
        self, recorder_with_mocked_hardware,
    ):
        """Simulate cancel by discarding buffer content."""
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        recorder._buffer.append(b"discard_this")
        # Clear buffer before stop to discard data
        recorder._buffer.clear()
        result = recorder.stop_recording()
        assert result is None  # No data emitted


# =============================================================================
#  Maximum recording duration enforcement
# =============================================================================


class TestMaxDuration:
    """Recording should stop when a maximum duration is reached.

    Note: The current AudioRecorder does not enforce a maximum
    recording duration.  Clients can implement this externally using
    a QTimer.
    """

    def test_no_max_duration_property(self, recorder):
        assert not hasattr(recorder, "max_duration")

    def test_external_timer_can_stop_recording(
        self, recorder_with_mocked_hardware, qtbot,
    ):
        """External code can use a QTimer to enforce max duration."""
        from PySide6.QtCore import QTimer

        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(recorder.stop_recording)
        timer.start(50)

        with qtbot.wait_signal(recorder.recording_stopped, timeout=500):
            pass

        assert recorder._source is None


# =============================================================================
#  Toggle recording start/stop
# =============================================================================


class TestToggle:
    """Toggle between start and stop states.

    Note: The current AudioRecorder does not have a toggle method.
    These tests verify that external toggle logic works correctly.
    """

    def test_no_toggle_method(self, recorder):
        assert not hasattr(recorder, "toggle")

    def test_external_toggle_logic(
        self, recorder_with_mocked_hardware,
    ):
        """External toggle: call start if idle, stop if recording."""
        recorder, mock_source, _ = recorder_with_mocked_hardware

        # Toggle to start
        if recorder._source is None:
            recorder.start_recording()
        assert recorder._source is not None

        # Toggle to stop
        if recorder._source is not None:
            recorder.stop_recording()
        assert recorder._source is None

    def test_toggle_twice_returns_to_idle(
        self, recorder_with_mocked_hardware,
    ):
        """Two toggles should return to idle state."""
        recorder, mock_source, _ = recorder_with_mocked_hardware

        def toggle():
            if recorder._source is None:
                recorder.start_recording()
            else:
                recorder.stop_recording()

        toggle()  # start
        assert recorder._source is not None
        toggle()  # stop
        assert recorder._source is None
        toggle()  # start again
        assert recorder._source is not None


# =============================================================================
#  Microphone level / volume indicator
# =============================================================================


class TestVolumeIndicator:
    """Volume/microphone level monitoring.

    Note: The current AudioRecorder does not expose real-time volume
    levels.  These tests verify the buffer accumulation which can be
    used to compute levels externally.
    """

    def test_no_volume_level_property(self, recorder):
        assert not hasattr(recorder, "volume_level")
        assert not hasattr(recorder, "mic_level")

    def test_buffer_size_increases_with_data(
        self, recorder_with_mocked_hardware,
    ):
        """The internal buffer grows as data arrives via _on_ready_read.

        Note: _on_ready_read uses self.sender() to get the IO device.
        In the mocked environment sender() returns None, so we simulate
        the call by passing the IO device directly.
        """
        recorder, mock_source, _ = recorder_with_mocked_hardware
        recorder.start_recording()
        io_device = mock_source.start.return_value
        io_device.readAll.return_value = QByteArray(b"\x00\x01" * 100)

        # _on_ready_read checks self.sender(); since the mock signal
        # doesn't set sender(), we patch sender() to return the IO device.
        with patch.object(recorder, "sender", return_value=io_device):
            recorder._on_ready_read()
        assert recorder._buffer.size() == 200


# =============================================================================
#  Edge cases
# =============================================================================


class TestEdgeCases:
    """Edge and corner cases around recording lifecycle."""

    def test_format_name_helper(self):
        """The _format_name helper works correctly."""
        from ui.copilot.audio_recorder import _format_name

        fmt = MagicMock(spec=QAudioFormat)
        fmt.sampleRate.return_value = 16000
        fmt.channelCount.return_value = 1
        fmt.sampleFormat.return_value = "Int16"
        name = _format_name(fmt)
        assert "16000" in name
        assert "1ch" in name
        assert "Int16" in name

    def test_format_name_handles_exception(self):
        from ui.copilot.audio_recorder import _format_name

        fmt = MagicMock(spec=QAudioFormat)
        fmt.sampleRate.return_value = 16000
        fmt.channelCount.return_value = 1
        fmt.sampleFormat.side_effect = Exception("boom")
        name = _format_name(fmt)
        assert "?" in name

    def test_ready_read_with_no_sender(self):
        """_on_ready_read handles missing sender gracefully."""
        from ui.copilot.audio_recorder import AudioRecorder

        rec = AudioRecorder()
        rec._on_ready_read()  # Should not raise or crash

    def test_multiple_error_conditions_in_sequence(self, recorder):
        from ui.copilot.audio_recorder import QMediaDevices

        errors = []
        recorder.error_occurred.connect(errors.append)

        QMediaDevices.defaultAudioInput.return_value = None
        recorder.start_recording()
        assert len(errors) == 1

        # Second attempt still fails
        recorder.start_recording()
        assert len(errors) == 2

    def test_recording_lifecycle_multiple_times(
        self, recorder_with_mocked_hardware,
    ):
        """Full start/stop cycle can be repeated many times."""
        recorder, mock_source, _ = recorder_with_mocked_hardware
        for i in range(5):
            recorder.start_recording()
            recorder._buffer.append(f"chunk_{i}".encode())
            result = recorder.stop_recording()
            assert result == f"chunk_{i}".encode()
