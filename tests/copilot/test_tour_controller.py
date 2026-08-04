"""Tests for TourController — guided walkthrough lifecycle management.

TourController extends QObject and coordinates between:
- tour_tracker.py (completion file on disk)
- tour_scripts.py (authored walkthrough scripts)
- guided_overlay_widget.py (visual overlay component)
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from ui.copilot.tour_scripts import ALL_SCRIPTS


@pytest.fixture
def mock_overlay():
    """MagicMock overlay for test controllers.

    Non-signal methods are tracked via MagicMock.
    Overlay signals are not real (connect succeeds as MagicMock auto-creates attrs).
    Tests that need overlay signal emission call controller handler methods directly.
    """
    overlay = MagicMock()
    overlay.is_active.return_value = True
    overlay.current_step_index.return_value = 0
    return overlay


@pytest.fixture
def mock_tracker():
    """Patch tour_tracker module in tour_controller."""
    with patch("ui.copilot.controllers.tour_controller.tour_tracker") as mock:
        mock.is_tour_completed.return_value = False
        mock.get_completed_tours.return_value = []
        mock.get_completion_count.return_value = 0
        yield mock


@pytest.fixture
def controller(qapp, mock_overlay, mock_tracker):
    """TourController with mocked overlay and tracker."""
    from ui.copilot.controllers.tour_controller import TourController

    tc = TourController()
    tc.set_overlay(mock_overlay)
    return tc


class TestStartTour:
    """Tour initiation — verifying start conditions and side effects."""

    def test_start_tour_valid_id(self, controller, mock_overlay):
        """start_tour with known workflow_id starts the overlay and emits signal."""
        handler = MagicMock()
        controller.tour_started.connect(handler)
        result = controller.start_tour("add_driver")
        assert result is True
        mock_overlay.start_tour.assert_called_once()
        handler.assert_called_once_with("add_driver")

    def test_start_tour_unknown_id(self, controller, mock_overlay):
        """start_tour with unknown workflow_id returns False, no signal."""
        handler = MagicMock()
        controller.tour_started.connect(handler)
        result = controller.start_tour("nonexistent")
        assert result is False
        mock_overlay.start_tour.assert_not_called()
        handler.assert_not_called()

    def test_start_tour_no_overlay(self, qapp, mock_tracker):
        """start_tour returns False when no overlay is set."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        result = tc.start_tour("add_driver")
        assert result is False

    def test_start_tour_no_steps(self, controller, mock_overlay):
        """start_tour returns False when the script has no steps."""
        with patch.dict(
            "ui.copilot.controllers.tour_controller.ALL_SCRIPTS",
            {"empty_tour": {"steps": [], "title_key": "some.key"}},
        ):
            result = controller.start_tour("empty_tour")
            assert result is False
            mock_overlay.start_tour.assert_not_called()

    def test_start_tour_emits_correct_workflow_id(self, controller, mock_overlay):
        """tour_started signal carries the correct workflow_id."""
        handler = MagicMock()
        controller.tour_started.connect(handler)
        controller.start_tour("generate_invoice")
        handler.assert_called_once_with("generate_invoice")


class TestTourLifecycle:
    """Start → step → complete/cancel lifecycle."""

    def test_tour_completed_signal(self, controller, mock_tracker):
        """_on_overlay_completed emits tour_completed and marks completed."""
        controller.start_tour("add_driver")
        handler = MagicMock()
        controller.tour_completed.connect(handler)
        controller._on_overlay_completed()
        handler.assert_called_once_with("add_driver")
        mock_tracker.mark_tour_completed.assert_called_once_with("add_driver")

    def test_tour_cancelled_signal(self, controller):
        """_on_overlay_cancelled emits tour_cancelled."""
        controller.start_tour("add_driver")
        handler = MagicMock()
        controller.tour_cancelled.connect(handler)
        controller._on_overlay_cancelled()
        handler.assert_called_once_with("add_driver")

    def test_tour_step_changed_signal(self, controller):
        """_on_overlay_step emits tour_step_changed with workflow_id and step."""
        controller.start_tour("add_driver")
        handler = MagicMock()
        controller.tour_step_changed.connect(handler)
        controller._on_overlay_step(2)
        handler.assert_called_once_with("add_driver", 2)


class TestOnboarding:
    """First-launch onboarding tour logic."""

    def test_start_onboarding_not_completed(self, controller, mock_tracker, mock_overlay):
        """start_onboarding returns True when app_overview not completed."""
        mock_tracker.is_tour_completed.return_value = False
        result = controller.start_onboarding()
        assert result is True
        mock_overlay.start_tour.assert_called_once()

    def test_start_onboarding_already_completed(self, controller, mock_tracker, mock_overlay):
        """start_onboarding returns False when app_overview already completed."""
        mock_tracker.is_tour_completed.return_value = True
        result = controller.start_onboarding()
        assert result is False
        mock_overlay.start_tour.assert_not_called()

    def test_can_show_onboarding_true(self, controller, mock_tracker):
        """can_show_onboarding returns True when app_overview not completed."""
        mock_tracker.is_tour_completed.return_value = False
        assert controller.can_show_onboarding() is True

    def test_can_show_onboarding_false(self, controller, mock_tracker):
        """can_show_onboarding returns False when app_overview completed."""
        mock_tracker.is_tour_completed.return_value = True
        assert controller.can_show_onboarding() is False


class TestCancelAndSkip:
    """User cancel/skip actions."""

    def test_cancel_current_delegates(self, controller, mock_overlay):
        """cancel_current calls overlay.cancel."""
        controller.start_tour("add_driver")
        controller.cancel_current()
        mock_overlay.cancel.assert_called_once()

    def test_cancel_current_no_overlay(self, qapp, mock_tracker):
        """cancel_current does not crash when no overlay is set."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        tc.cancel_current()  # Should not raise

    def test_cancel_current_no_active_tour(self, controller, mock_overlay):
        """cancel_current does not call overlay.cancel when no tour active."""
        controller.cancel_current()
        mock_overlay.cancel.assert_not_called()

    def test_skip_step_delegates(self, controller, mock_overlay):
        """skip_step calls overlay.skip_step."""
        controller.skip_step()
        mock_overlay.skip_step.assert_called_once()


class TestPauseResume:
    """Pause/resume lifecycle — state preservation and restoration."""

    def test_pause_tour_returns_state(self, controller, mock_overlay):
        """pause_tour returns dict with workflow_id and current_step_index."""
        controller.start_tour("add_driver")
        state = controller.pause_tour()
        assert state == {"workflow_id": "add_driver", "current_step_index": 0}

    def test_pause_tour_no_overlay(self, qapp, mock_tracker):
        """pause_tour returns None when no overlay is set."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        assert tc.pause_tour() is None

    def test_pause_tour_not_active(self, controller, mock_overlay):
        """pause_tour returns None when overlay is not active."""
        controller.start_tour("add_driver")
        mock_overlay.is_active.return_value = False
        result = controller.pause_tour()
        assert result is None

    def test_pause_tour_hides_overlay(self, controller, mock_overlay):
        """pause_tour calls overlay.hide."""
        controller.start_tour("add_driver")
        controller.pause_tour()
        mock_overlay.hide.assert_called_once()

    def test_resume_tour_from_state(self, controller, mock_overlay):
        """resume_tour calls overlay.start_tour with start_from parameter."""
        result = controller.resume_tour(
            {"workflow_id": "add_driver", "current_step_index": 1}
        )
        assert result is True
        mock_overlay.start_tour.assert_called_once()
        _args, kwargs = mock_overlay.start_tour.call_args
        assert kwargs.get("start_from") == 1

    def test_resume_tour_no_overlay(self, qapp, mock_tracker):
        """resume_tour returns False when no overlay is set."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        result = tc.resume_tour(
            {"workflow_id": "add_driver", "current_step_index": 0}
        )
        assert result is False

    def test_resume_tour_unknown_workflow(self, controller, mock_overlay):
        """resume_tour returns False for unknown workflow_id."""
        result = controller.resume_tour(
            {"workflow_id": "nonexistent", "current_step_index": 0}
        )
        assert result is False
        mock_overlay.start_tour.assert_not_called()

    def test_resume_tour_emits_started_signal(self, controller, mock_overlay):
        """resume_tour emits tour_started signal."""
        handler = MagicMock()
        controller.tour_started.connect(handler)
        controller.resume_tour(
            {"workflow_id": "add_driver", "current_step_index": 1}
        )
        handler.assert_called_once_with("add_driver")


class TestReplay:
    """Replay tour — clear completion flag and restart."""

    def test_replay_clears_then_starts(self, controller, mock_tracker, mock_overlay):
        """replay_tour clears completion then starts the tour."""
        controller.replay_tour("add_driver")
        mock_tracker.clear_tour_completed.assert_called_once_with("add_driver")
        mock_overlay.start_tour.assert_called_once()


class TestGetAvailableTours:
    """Tour listings with completion status."""

    def test_get_available_tours_structure(self, controller):
        """Each tour entry has the expected keys."""
        tours = controller.get_available_tours()
        assert len(tours) > 0
        for entry in tours:
            assert "workflow_id" in entry
            assert "title_key" in entry
            assert "completed" in entry
            assert "step_count" in entry
            assert "completion_count" in entry

    def test_get_available_tours_includes_all_scripts(self, controller):
        """One entry per key in ALL_SCRIPTS."""
        tours = controller.get_available_tours()
        workflow_ids = {t["workflow_id"] for t in tours}
        assert workflow_ids == set(ALL_SCRIPTS.keys())


class TestGetCompletedTours:
    """Delegation to tour_tracker."""

    def test_get_completed_tours_delegates(self, controller, mock_tracker):
        """Result matches tour_tracker.get_completed_tours()."""
        mock_tracker.get_completed_tours.return_value = ["add_driver", "app_overview"]
        result = controller.get_completed_tours()
        assert result == ["add_driver", "app_overview"]
        mock_tracker.get_completed_tours.assert_called_once()


class TestIsTourActive:
    """Active tour state queries."""

    def test_is_tour_active_true(self, controller, mock_overlay):
        """is_tour_active returns True when overlay is set and active."""
        assert controller.is_tour_active() is True

    def test_is_tour_active_false_no_overlay(self, qapp, mock_tracker):
        """is_tour_active returns False when no overlay is set."""
        from ui.copilot.controllers.tour_controller import TourController

        tc = TourController()
        assert tc.is_tour_active() is False

    def test_current_workflow_id(self, controller):
        """current_workflow_id returns the correct workflow_id after start."""
        assert controller.current_workflow_id() is None
        controller.start_tour("add_driver")
        assert controller.current_workflow_id() == "add_driver"


class TestMarkAllCompletedAndReset:
    """Bulk completion and reset operations."""

    def test_mark_all_completed(self, controller, mock_tracker):
        """mark_all_completed calls mark_tour_completed for every script key."""
        controller.mark_all_completed()
        expected_calls = [call(wid) for wid in ALL_SCRIPTS]
        mock_tracker.mark_tour_completed.assert_has_calls(
            expected_calls, any_order=True
        )
        assert mock_tracker.mark_tour_completed.call_count == len(ALL_SCRIPTS)

    def test_reset_all(self, controller, mock_tracker):
        """reset_all calls clear_all_tours."""
        controller.reset_all()
        mock_tracker.clear_all_tours.assert_called_once()


class TestOverlaySignalHandlers:
    """Delegation from overlay signals to tour_tracker and controller signals."""

    def test_overlay_completed_marks_and_counts(self, controller, mock_tracker):
        """_on_overlay_completed calls mark_tour_completed AND increment_completion_count."""
        controller.start_tour("add_driver")
        controller._on_overlay_completed()
        mock_tracker.mark_tour_completed.assert_called_once_with("add_driver")
        mock_tracker.increment_completion_count.assert_called_once_with("add_driver")

    def test_overlay_completed_clears_current(self, controller):
        """_on_overlay_completed resets _current_workflow_id to None."""
        controller.start_tour("add_driver")
        controller._on_overlay_completed()
        assert controller.current_workflow_id() is None

    def test_overlay_cancelled_clears_current(self, controller):
        """_on_overlay_cancelled resets _current_workflow_id to None."""
        controller.start_tour("add_driver")
        controller._on_overlay_cancelled()
        assert controller.current_workflow_id() is None

    def test_overlay_completed_no_current(self, controller, mock_tracker):
        """_on_overlay_completed with no current tour does not crash or emit signals."""
        handler = MagicMock()
        controller.tour_completed.connect(handler)
        controller._on_overlay_completed()
        mock_tracker.mark_tour_completed.assert_not_called()
        mock_tracker.increment_completion_count.assert_not_called()
        handler.assert_not_called()
        assert controller.current_workflow_id() is None

    def test_overlay_cancelled_no_current(self, controller):
        """_on_overlay_cancelled with no current tour does not crash or emit signals."""
        handler = MagicMock()
        controller.tour_cancelled.connect(handler)
        controller._on_overlay_cancelled()
        handler.assert_not_called()
        assert controller.current_workflow_id() is None
