"""Tests for copilot signal emissions — AudioRecorder, TTSPlayer,
GuidedOverlayWidget, and TourController.

Verifies that each QObject-derived class emits its signals at the
correct lifecycle points.  Uses ``qtbot.waitSignal`` for async signals
and ``MagicMock`` handlers for synchronous assertions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtMultimedia import QAudioSource, QMediaDevices, QMediaPlayer
from PySide6.QtTest import QSignalSpy, QTest

# ── SP workaround (if needed) ──────────────────────────────────────────────
# import ui.widgets as _ui_widgets
# if not hasattr(_ui_widgets, "SP"):
#     _ui_widgets.SP = _ui_widgets.S

# ── Test data ──────────────────────────────────────────────────────────────

SAMPLE_TOUR_SCRIPTS: dict[str, dict] = {
    "test_tour": {
        "workflow_id": "test_tour",
        "title_key": "Test Tour",
        "steps": [
            {"title": "Step 1", "description": "First step", "target_element_id": None},
            {"title": "Step 2", "description": "Second step", "target_element_id": None},
            {"title": "Step 3", "description": "Third step", "target_element_id": None},
        ],
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# AudioRecorder signal tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAudioRecorderSignals:
    """Signal emissions from AudioRecorder.

    All three tests mock ``QMediaDevices`` / ``QAudioSource`` to avoid
    depending on real audio hardware.
    """

    # ── Fixtures ──────────────────────────────────────────────────────

    @pytest.fixture
    def mock_device(self):
        """Return a MagicMock that advertises format support."""
        dev = MagicMock()
        dev.isFormatSupported.return_value = True
        return dev

    @pytest.fixture
    def mock_audio_source(self):
        """Return a MagicMock QAudioSource replacement."""
        source = MagicMock(spec=QAudioSource)
        io = MagicMock()
        source.start.return_value = io
        return source

    # ── Test 1 ────────────────────────────────────────────────────────

    def test_error_emitted_when_no_audio_device(self, qapp, qtbot):
        """start_recording emits error_occurred when no default input found."""
        from ui.copilot.audio_recorder import AudioRecorder

        with patch.object(QMediaDevices, "defaultAudioInput", return_value=None):
            recorder = AudioRecorder()
            handler = MagicMock()
            recorder.error_occurred.connect(handler)
            recorder.start_recording()
            handler.assert_called_once_with("No default audio input device found")

    # ── Test 2 ────────────────────────────────────────────────────────

    def test_start_recording_emits_recording_started(
        self, qapp, qtbot, mock_device, mock_audio_source,
    ):
        """start_recording emits recording_started after acquiring the source."""
        from ui.copilot.audio_recorder import AudioRecorder

        with patch.object(QMediaDevices, "defaultAudioInput", return_value=mock_device):
            with patch("ui.copilot.audio_recorder.QAudioSource", return_value=mock_audio_source):
                recorder = AudioRecorder()
                handler = MagicMock()
                recorder.recording_started.connect(handler)
                recorder.start_recording()
                handler.assert_called_once()

    # ── Test 3 ────────────────────────────────────────────────────────

    def test_stop_recording_emits_recording_stopped(
        self, qapp, qtbot, mock_device, mock_audio_source,
    ):
        """stop_recording emits recording_stopped after stopping the source."""
        from ui.copilot.audio_recorder import AudioRecorder

        with patch.object(QMediaDevices, "defaultAudioInput", return_value=mock_device):
            with patch("ui.copilot.audio_recorder.QAudioSource", return_value=mock_audio_source):
                recorder = AudioRecorder()
                handler = MagicMock()
                recorder.recording_stopped.connect(handler)
                recorder.start_recording()
                recorder.stop_recording()
                handler.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# TTSPlayer signal tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTTSPlayerSignals:
    """Signal emissions from TTSPlayer.

    The internal ``QMediaPlayer`` is swapped for a MagicMock so the
    test can control ``mediaStatusChanged`` without real media I/O.
    """

    # ── Test 4 ────────────────────────────────────────────────────────

    def test_playback_finished_emitted_on_end(self, qapp, qtbot):
        """_on_media_status_changed(EndOfMedia) emits playback_finished."""
        from ui.copilot.tts_player import TTSPlayer

        player = TTSPlayer()
        mock_player = MagicMock()
        player._player = mock_player

        handler = MagicMock()
        player.playback_finished.connect(handler)

        player._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)
        handler.assert_called_once()

    # ── Test 5 ────────────────────────────────────────────────────────

    def test_playback_finished_not_emitted_on_other_status(self, qapp, qtbot):
        """Non-EndOfMedia statuses do NOT trigger playback_finished."""
        from ui.copilot.tts_player import TTSPlayer

        player = TTSPlayer()
        mock_player = MagicMock()
        player._player = mock_player

        handler = MagicMock()
        player.playback_finished.connect(handler)

        player._on_media_status_changed(QMediaPlayer.MediaStatus.LoadedMedia)
        player._on_media_status_changed(QMediaPlayer.MediaStatus.BufferedMedia)

        handler.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# GuidedOverlayWidget signal tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGuidedOverlayWidgetSignals:
    """Signal emissions from GuidedOverlayWidget.

    Creates a real overlay attached to a QMainWindow parent.
    Animations are processed via ``qtbot.wait`` between steps.
    """

    # ── Fixtures ──────────────────────────────────────────────────────

    @pytest.fixture
    def overlay(self, qapp, qtbot, qt_main_window):
        """Create a GuidedOverlayWidget parented to the test main window."""
        from ui.copilot.widgets.guided_overlay_widget import GuidedOverlayWidget

        ov = GuidedOverlayWidget(qt_main_window)
        qtbot.addWidget(ov)
        qt_main_window.show()
        ov.show()
        QTest.qWait(50)  # let initial layout settle
        return ov

    # ── Test 6 ────────────────────────────────────────────────────────

    def test_cancelled_emits_on_cancel(self, overlay):
        """cancel() emits the cancelled signal synchronously."""
        handler = MagicMock()
        overlay.cancelled.connect(handler)
        overlay.cancel()
        handler.assert_called_once()

    # ── Test 7 ────────────────────────────────────────────────────────

    @pytest.mark.xfail(
        reason="Source code defines `skipped` signal but `skip_step()` never emits it"
    )
    def test_skipped_emits_on_skip_step(self, overlay):
        """skip_step() emits the skipped signal."""
        steps = [
            {"title": "Step 1", "target_element_id": None},
            {"title": "Step 2", "target_element_id": None},
        ]
        overlay.start_tour(steps)

        handler = MagicMock()
        overlay.skipped.connect(handler)
        overlay.skip_step()
        handler.assert_called_once()

    # ── Test 8 ────────────────────────────────────────────────────────

    def test_completed_emits_on_finish(self, overlay, qtbot):
        """Advancing past the last step emits completed."""
        steps = [{"title": "Only step", "target_element_id": None}]
        overlay.start_tour(steps)

        with qtbot.waitSignal(overlay.completed, timeout=1000):
            overlay.next_step()

    # ── Test 9 ────────────────────────────────────────────────────────

    def test_step_changed_emits_on_each_step(self, overlay, qtbot):
        """step_changed is emitted with the correct index on every transition."""
        steps = [
            {"title": "Step 1", "target_element_id": None},
            {"title": "Step 2", "target_element_id": None},
            {"title": "Step 3", "target_element_id": None},
        ]

        spy = QSignalSpy(overlay.step_changed)

        overlay.start_tour(steps)
        assert spy.wait(3000), "step_changed(0) not emitted after start_tour"
        assert spy.count() >= 1, f"Expected >= 1 emission, got {spy.count()}"

        overlay.next_step()
        assert spy.wait(3000), "step_changed(1) not emitted after next_step"
        assert spy.count() >= 2, f"Expected >= 2 emissions, got {spy.count()}"

        overlay.next_step()
        assert spy.wait(3000), "step_changed(2) not emitted after next_step"
        assert spy.count() == 3, f"Expected 3 emissions, got {spy.count()}"

        indices = [spy.at(i)[0] for i in range(spy.count())]
        assert indices == [0, 1, 2], (
            f"Expected step_changed indices [0, 1, 2], got {indices}"
        )

    # ── Test 10 ───────────────────────────────────────────────────────

    def test_replayed_emits_on_replay(self, overlay):
        """replay() emits the replayed signal synchronously."""
        steps = [
            {"title": "Step 1", "target_element_id": None},
            {"title": "Step 2", "target_element_id": None},
        ]
        overlay.start_tour(steps)
        overlay.next_step()  # advance to step 1

        handler = MagicMock()
        overlay.replayed.connect(handler)
        overlay.replay()
        handler.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# TourController signal tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTourControllerSignals:
    """Signal emissions from TourController.

    Uses a MagicMock overlay (same pattern as ``test_tour_controller.py``)
    so signals are tested without creating a real overlay widget.
    Tour-tracker is also mocked to avoid filesystem side-effects.
    """

    # ── Fixtures ──────────────────────────────────────────────────────

    @pytest.fixture
    def mock_overlay(self):
        """MagicMock overlay — attributes auto-created on access."""
        overlay = MagicMock()
        overlay.is_active.return_value = True
        overlay.current_step_index.return_value = 0
        return overlay

    @pytest.fixture
    def mock_tracker(self):
        """Patch tour_tracker in tour_controller's module scope."""
        with patch("ui.copilot.controllers.tour_controller.tour_tracker") as m:
            m.is_tour_completed.return_value = False
            m.get_completed_tours.return_value = []
            m.get_completion_count.return_value = 0
            yield m

    @pytest.fixture
    def controller(self, qapp, mock_overlay, mock_tracker):
        """TourController with mocked overlay and tracker."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        tc.set_overlay(mock_overlay)
        return tc

    # ── Test 11 ───────────────────────────────────────────────────────

    def test_tour_started_emits_workflow_id(self, controller):
        """start_tour emits tour_started(workflow_id)."""
        handler = MagicMock()
        controller.tour_started.connect(handler)

        with patch.dict(
            "ui.copilot.controllers.tour_controller.ALL_SCRIPTS",
            SAMPLE_TOUR_SCRIPTS,
            clear=True,
        ):
            result = controller.start_tour("test_tour")

        assert result is True
        handler.assert_called_once_with("test_tour")

    # ── Test 12 ───────────────────────────────────────────────────────

    def test_tour_completed_emits_workflow_id(self, controller, mock_tracker):
        """_on_overlay_completed emits tour_completed(workflow_id)."""
        controller.start_tour("app_overview")

        handler = MagicMock()
        controller.tour_completed.connect(handler)

        controller._on_overlay_completed()
        handler.assert_called_once_with("app_overview")

    # ── Test 13 ───────────────────────────────────────────────────────

    def test_tour_cancelled_emits_workflow_id(self, controller):
        """_on_overlay_cancelled emits tour_cancelled(workflow_id)."""
        controller.start_tour("app_overview")

        handler = MagicMock()
        controller.tour_cancelled.connect(handler)

        controller._on_overlay_cancelled()
        handler.assert_called_once_with("app_overview")

    # ── Test 14 ───────────────────────────────────────────────────────

    def test_tour_step_changed_emits_workflow_and_index(self, controller):
        """_on_overlay_step emits tour_step_changed(workflow_id, index)."""
        controller.start_tour("app_overview")

        handler = MagicMock()
        controller.tour_step_changed.connect(handler)

        controller._on_overlay_step(2)
        handler.assert_called_once_with("app_overview", 2)

    # ── Test 15 ───────────────────────────────────────────────────────

    def test_start_tour_fails_without_overlay(self, qapp, mock_tracker):
        """Starting a tour with no overlay returns False and emits nothing."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        handler = MagicMock()
        tc.tour_started.connect(handler)

        with patch.dict(
            "ui.copilot.controllers.tour_controller.ALL_SCRIPTS",
            SAMPLE_TOUR_SCRIPTS,
            clear=True,
        ):
            result = tc.start_tour("test_tour")

        assert result is False
        handler.assert_not_called()
