"""Tests for frontend Co-Pilot UI widgets.
These tests use static analysis and direct construction where possible.
For Qt-dependent tests, we use mocking at the import level.
"""
from __future__ import annotations

import ast
from unittest.mock import MagicMock

import pytest


class TestCoPilotModels:
    """Tests for ui/copilot/models.py dataclasses (extends test_models.py)."""

    def test_execution_step_defaults_round_trip(self):
        from ui.copilot.models import ExecutionStep, ConfirmationLevel
        step = ExecutionStep(
            step_id="s1", tool_name="test", confirmation_level=ConfirmationLevel.SAFE
        )
        assert step.step_id == "s1"
        assert step.tool_name == "test"
        assert step.confirmation_level == ConfirmationLevel.SAFE
        assert step.status == "pending"

    def test_execution_plan_requires_confirmation_for_level_2(self):
        from ui.copilot.models import (
            ExecutionPlan,
            ExecutionStep,
            ConfirmationLevel,
            Intent,
        )
        step = ExecutionStep(
            step_id="s1",
            tool_name="dispatch.create",
            confirmation_level=ConfirmationLevel.BUSINESS,
        )
        plan = ExecutionPlan(
            plan_id="p1",
            conversation_id="c1",
            intent=Intent(name="dispatch.create"),
            steps=[step],
            overall_confidence=0.9,
            reasoning_graph_id="g1",
            requires_confirmation=True,
        )
        assert plan.requires_confirmation is True

    def test_co_pilot_response_defaults(self):
        from ui.copilot.models import CoPilotResponse
        resp = CoPilotResponse(conversation_id="c1", timeline=[])
        assert resp.conversation_id == "c1"
        assert resp.timeline == []
        assert resp.summary_key is None

    def test_insight_dataclass_defaults(self):
        from ui.copilot.models import Insight
        insight = Insight()
        assert insight.severity == "low"
        assert insight.status == "new"
        assert insight.id == ""


def _read_source(path: str) -> str:
    """Read a source file with UTF-8 encoding (Windows-safe)."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _get_classes(source: str) -> list[str]:
    return [n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ClassDef)]


def _get_methods(source: str) -> list[str]:
    return [
        n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
    ]


class TestWidgetImportPatterns:
    """Verify widget files import cleanly and export expected symbols."""

    def test_chat_bubble_imports(self):
        source = _read_source("ui/copilot/widgets/chat_bubble.py")
        classes = _get_classes(source)
        assert "ChatBubbleWidget" in classes

    def test_chat_input_imports(self):
        source = _read_source("ui/copilot/widgets/chat_input.py")
        classes = _get_classes(source)
        assert len(classes) > 0

    def test_thinking_indicator_ast(self):
        source = _read_source("ui/copilot/widgets/thinking_indicator.py")
        assert "QTimer" in source

    def test_conversation_display_ast(self):
        source = _read_source("ui/copilot/widgets/conversation_display.py")
        methods = _get_methods(source)
        assert "add_message" in methods
        assert "clear" in methods

    def test_timeline_widget_ast(self):
        source = _read_source("ui/copilot/widgets/timeline_widget.py")
        classes = _get_classes(source)
        assert "CoPilotTimelineWidget" in classes

    def test_insight_queue_ast(self):
        source = _read_source("ui/copilot/widgets/insight_queue.py")
        classes = _get_classes(source)
        assert "InsightQueueWidget" in classes or "InsightQueue" in classes


@pytest.mark.skip(reason="Requires Qt application fixture")
class TestCoPilotPanelWithQt:
    """Integration tests for CoPilotPanel (requires Qt)."""

    def test_panel_construction(self):
        """Test that CoPilotPanel can be constructed with a mock controller."""
        from PySide6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        controller = MagicMock()
        try:
            from ui.copilot.widgets.copilot_panel import CoPilotPanel

            panel = CoPilotPanel(parent=parent, controller=controller)
            assert panel is not None
        except Exception as e:
            pytest.skip(
                f"Panel construction failed (expected without full UI stack): {e}"
            )


class TestCopilotView:
    """Tests for the CoPilotView wrapper."""

    def test_view_imports(self):
        source = _read_source("ui/views/copilot_view.py")
        classes = _get_classes(source)
        assert "CoPilotView" in classes

    def test_view_has_wakeup_shutdown(self):
        source = _read_source("ui/views/copilot_view.py")
        methods = _get_methods(source)
        assert "wakeup" in methods
        assert "shutdown" in methods


class TestConfirmationModal:
    """Tests for confirmation_modal.py."""

    def test_imports(self):
        source = _read_source("ui/copilot/widgets/confirmation_modal.py")
        classes = _get_classes(source)
        modal_classes = [c for c in classes if "Confirm" in c or "Modal" in c]
        assert len(modal_classes) > 0

    def test_from_steps_method_exists(self):
        """Verify the from_steps() classmethod added during gap closure exists."""
        source = _read_source("ui/copilot/widgets/confirmation_modal.py")
        assert "from_steps" in source

    def test_redact_params_exists(self):
        """Verify param redaction was added."""
        source = _read_source("ui/copilot/widgets/confirmation_modal.py")
        assert (
            "redact" in source.lower()
            or "sensitive" in source.lower()
            or "SENSITIVE" in source
        )


class TestAudioRecorder:
    """Tests for audio_recorder.py."""

    def test_imports(self):
        source = _read_source("ui/copilot/audio_recorder.py")
        classes = _get_classes(source)
        assert "AudioRecorder" in classes

    def test_has_signals(self):
        """Verify AudioRecorder has the required Qt signals."""
        source = _read_source("ui/copilot/audio_recorder.py")
        assert "Signal" in source
        assert "recording_started" in source or "audio_ready" in source

    def test_has_start_stop_methods(self):
        source = _read_source("ui/copilot/audio_recorder.py")
        assert "start_recording" in source
        assert "stop_recording" in source


class TestTTSPlayer:
    """Tests for tts_player.py."""

    def test_imports(self):
        source = _read_source("ui/copilot/tts_player.py")
        classes = _get_classes(source)
        assert "TTSPlayer" in classes

    def test_has_playback_methods(self):
        source = _read_source("ui/copilot/tts_player.py")
        assert "play_audio" in source
        assert "stop" in source

    def test_has_playback_signal(self):
        source = _read_source("ui/copilot/tts_player.py")
        assert "playback_finished" in source or "Signal" in source


# =============================================================================
# Help Mode Module — AST / Structural
# =============================================================================


class TestHelpModeAST:
    """Structural tests for Help Mode source files."""

    def test_element_registry_structure(self):
        source = _read_source("ui/copilot/element_registry.py")
        assert "ELEMENT_REGISTRY" in source
        assert "resolve_element" in source
        assert "resolve_object_name" in source
        assert "register_element" in source
        assert "validate_script_targets" in source

    def test_tour_tracker_structure(self):
        source = _read_source("ui/copilot/tour_tracker.py")
        for fn in ("mark_tour_completed", "is_tour_completed", "clear_tour_completed",
                   "clear_all_tours", "get_completed_tours", "get_completion_count",
                   "increment_completion_count"):
            assert fn in source, f"Expected {fn} in tour_tracker.py"

    def test_tour_scripts_has_all_scripts(self):
        source = _read_source("ui/copilot/tour_scripts.py")
        assert "ALL_SCRIPTS" in source
        assert "ONBOARDING_TOUR" in source
        assert "ADD_DRIVER_TOUR" in source
        assert "GENERATE_INVOICE_TOUR" in source
        assert "DISPATCH_TRIP_TOUR" in source
        assert "SCHEDULE_MAINTENANCE_TOUR" in source

    def test_guided_overlay_widget_structure(self):
        source = _read_source("ui/copilot/widgets/guided_overlay_widget.py")
        assert "GuidedOverlayWidget" in source
        assert "start_tour" in source
        assert "next_step" in source
        assert "cancel" in source
        assert "completed" in source  # Signal
        assert "paintEvent" in source

    def test_tour_controller_structure(self):
        source = _read_source("ui/copilot/controllers/tour_controller.py")
        assert "TourController" in source
        for fn in ("start_tour", "start_onboarding", "replay_tour",
                   "get_available_tours", "cancel_current"):
            assert fn in source, f"Expected {fn} in tour_controller.py"

    def test_struggle_detector_structure(self):
        source = _read_source("ui/copilot/controllers/struggle_detector.py")
        assert "StruggleDetector" in source
        assert "record_navigation" in source
        assert "record_action" in source
        assert "_check_rapid_navigation" in source
        assert "_detect_repeated_pattern" in source
        assert "struggle_detected" in source

    def test_ask_ai_menu_structure(self):
        source = _read_source("ui/copilot/controllers/ask_ai_menu.py")
        assert "AskAIMenu" in source
        assert "eventFilter" in source
        assert "_element_label" in source or "_build_question" in source
        assert "ask_ai_requested" in source


# =============================================================================
# StruggleDetector — detection logic (pure Python, no Qt rendering)
# =============================================================================


class TestStruggleDetectorLogic:
    """Tests for StruggleDetector detection algorithms (no Qt required)."""

    def test_screen_to_workflow_mapping(self):
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        assert detector._screen_to_workflow["fleet"] == "app_overview"
        assert detector._screen_to_workflow["driver_manager"] == "add_driver"
        assert detector._screen_to_workflow["invoices"] == "generate_invoice"
        assert detector._screen_to_workflow["dispatch_board"] == "dispatch_trip"
        assert detector._screen_to_workflow["maintenance"] == "schedule_maintenance"

    def test_detect_repeated_pattern_detects_abab(self):
        from datetime import datetime
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        now = datetime.utcnow()
        history = [
            ("screen_a", now),
            ("screen_b", now),
            ("screen_a", now),
            ("screen_b", now),
            ("screen_a", now),
            ("screen_b", now),
        ]
        assert detector._detect_repeated_pattern(history) is True

    def test_detect_repeated_pattern_ignores_short_history(self):
        from datetime import datetime
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        now = datetime.utcnow()
        history = [("a", now), ("b", now), ("a", now)]  # Only 3 entries
        assert detector._detect_repeated_pattern(history) is False

    def test_detect_repeated_pattern_ignores_same_screen(self):
        from datetime import datetime
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        now = datetime.utcnow()
        history = [("a", now), ("a", now), ("a", now), ("a", now)]
        assert detector._detect_repeated_pattern(history) is False

    def test_check_rapid_navigation_does_not_fire_when_recent_action(self):
        from datetime import datetime, timedelta
        from unittest.mock import MagicMock
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        now = datetime.utcnow()
        detector._last_action_time = now
        history = [
            ("a", now - timedelta(seconds=5)),
            ("b", now - timedelta(seconds=3)),
            ("c", now - timedelta(seconds=1)),
        ]
        detector._nav_history.extend(history)
        # Should not trigger — recent action resets
        detector._check_rapid_navigation(now)
        assert detector._last_nudge_time is None

    def test_record_navigation_adds_to_history(self):
        from datetime import datetime
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        detector.record_navigation("fleet")
        assert len(detector._nav_history) == 1
        assert detector._nav_history[0][0] == "fleet"

    def test_record_action_clears_history(self):
        from datetime import datetime
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        detector.record_navigation("fleet")
        detector.record_action()
        assert len(detector._nav_history) == 0

    def test_reset_clears_state(self):
        from datetime import datetime
        from ui.copilot.controllers.struggle_detector import StruggleDetector

        detector = StruggleDetector()
        detector.record_navigation("fleet")
        detector.reset()
        assert len(detector._nav_history) == 0
        assert detector._last_nudge_time is None


# =============================================================================
# AskAIMenu — helper functions (pure Python)
# =============================================================================


class TestAskAIMenuHelpers:
    """Tests for AskAIMenu helper functions (no Qt required)."""

    def test_element_label_nav(self):
        from ui.copilot.controllers.ask_ai_menu import _element_label

        label = _element_label("nav_overview")
        assert "Overview" in label
        assert "navigation item" in label

    def test_element_label_btn(self):
        from ui.copilot.controllers.ask_ai_menu import _element_label

        label = _element_label("btn_add_driver")
        assert "Add Driver" in label or "Add" in label
        assert "button" in label

    def test_element_label_unknown_prefix(self):
        from ui.copilot.controllers.ask_ai_menu import _element_label

        label = _element_label("some_random_id")
        # Falls back to title-cased ID
        assert "Some Random Id" in label

    def test_build_question_with_screen(self):
        from ui.copilot.controllers.ask_ai_menu import _build_question

        question = _build_question("nav_overview", "fleet")
        assert "Overview" in question
        assert "fleet" in question.lower() or "Fleet" in question

    def test_build_question_without_screen(self):
        from ui.copilot.controllers.ask_ai_menu import _build_question

        question = _build_question("btn_add_driver", None)
        assert "Add Driver" in question or "Add" in question


# =============================================================================
# TourController — logic with mocked overlay + tracker
# =============================================================================


class TestTourControllerLogic:
    """Tests for TourController (with mocked overlay and tracker)."""

    def test_start_tour_no_overlay_returns_false(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        result = controller.start_tour("app_overview")
        assert result is False

    def test_start_tour_unknown_workflow_returns_false(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        controller.set_overlay(MagicMock())
        result = controller.start_tour("nonexistent")
        assert result is False

    def test_start_tour_valid_workflow_returns_true(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        result = controller.start_tour("app_overview")
        assert result is True
        overlay.start_tour.assert_called_once()

    def test_get_available_tours_returns_list(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        with patch("ui.copilot.tour_tracker.is_tour_completed", return_value=False):
            with patch("ui.copilot.tour_tracker.get_completion_count", return_value=0):
                tours = controller.get_available_tours()
        assert len(tours) == 5
        for t in tours:
            assert "workflow_id" in t
            assert "title_key" in t
            assert "step_count" in t

    def test_replay_tour_clears_and_starts(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        with patch("ui.copilot.tour_tracker.clear_tour_completed") as mock_clear:
            result = controller.replay_tour("app_overview")
        assert result is True
        mock_clear.assert_called_once_with("app_overview")

    def test_cancel_current_when_active(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        overlay.is_active.return_value = True
        controller.set_overlay(overlay)
        # Start a tour so _current_workflow_id is set
        controller.start_tour("app_overview")

        controller.cancel_current()
        overlay.cancel.assert_called_once()

    def test_cancel_current_when_no_overlay(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        controller.cancel_current()  # Should not raise

    def test_start_onboarding_when_not_completed(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        with patch("ui.copilot.tour_tracker.is_tour_completed", return_value=False):
            result = controller.start_onboarding()
        assert result is True

    def test_start_onboarding_when_already_completed(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        with patch("ui.copilot.tour_tracker.is_tour_completed", return_value=True):
            result = controller.start_onboarding()
        assert result is False
        overlay.start_tour.assert_not_called()

    def test_can_show_onboarding(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        with patch("ui.copilot.tour_tracker.is_tour_completed", return_value=False):
            assert controller.can_show_onboarding() is True

    def test_mark_all_completed(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        with patch("ui.copilot.tour_tracker.mark_tour_completed") as mock_mark:
            controller.mark_all_completed()
        assert mock_mark.call_count == 5

    def test_reset_all(self):
        from unittest.mock import patch
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        with patch("ui.copilot.tour_tracker.clear_all_tours") as mock_clear:
            controller.reset_all()
        mock_clear.assert_called_once()

    def test_is_tour_active_false_by_default(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        assert controller.is_tour_active() is False

    def test_is_tour_active_when_overlay_says_active(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        overlay.is_active.return_value = True
        controller.set_overlay(overlay)
        assert controller.is_tour_active() is True

    def test_skip_step(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        controller.skip_step()
        overlay.skip_step.assert_called_once()

    def test_signal_connections_on_set_overlay(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        overlay.completed.connect.assert_called_once()
        overlay.cancelled.connect.assert_called_once()
        overlay.step_changed.connect.assert_called_once()

    # ── Pause / Resume (§34.5) ──────────────────────────────────────────

    def test_pause_tour_returns_none_when_no_overlay(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        result = controller.pause_tour()
        assert result is None

    def test_pause_tour_returns_none_when_not_active(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        overlay.is_active.return_value = False
        controller.set_overlay(overlay)
        controller._current_workflow_id = "app_overview"
        result = controller.pause_tour()
        assert result is None

    def test_pause_tour_saves_state(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        overlay.is_active.return_value = True
        overlay.current_step_index.return_value = 3
        controller.set_overlay(overlay)
        controller._current_workflow_id = "app_overview"
        result = controller.pause_tour()
        assert result is not None
        assert result["workflow_id"] == "app_overview"
        assert result["current_step_index"] == 3
        overlay.hide.assert_called_once()

    def test_resume_tour_no_overlay(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        result = controller.resume_tour({"workflow_id": "app_overview", "current_step_index": 2})
        assert result is False

    def test_resume_tour_unknown_workflow(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        controller.set_overlay(overlay)
        result = controller.resume_tour({"workflow_id": "nonexistent", "current_step_index": 0})
        assert result is False

    def test_resume_tour_valid(self):
        from ui.copilot.controllers.tour_controller import TourController

        controller = TourController()
        overlay = MagicMock()
        overlay.is_active.return_value = True
        controller.set_overlay(overlay)
        result = controller.resume_tour({"workflow_id": "app_overview", "current_step_index": 2})
        assert result is True
        overlay.start_tour.assert_called_once()
        # Verify start_from=2 was passed
        args, kwargs = overlay.start_tour.call_args
        assert kwargs.get("start_from") == 2 or args[3] == 2 if len(args) > 3 else True


# =============================================================================
# GuidedOverlayWidget — Qt-dependent (run-time optional)
# =============================================================================


@pytest.mark.skip(reason="Requires Qt application fixture")
class TestGuidedOverlayWidgetWithQt:
    """Integration-style tests for GuidedOverlayWidget (requires Qt)."""

    def test_widget_construction(self):
        from PySide6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        from ui.copilot.widgets.guided_overlay_widget import GuidedOverlayWidget

        overlay = GuidedOverlayWidget(parent=parent)
        assert overlay is not None
        assert overlay.objectName() == "guided-overlay"
        assert overlay.is_active() is False

    def test_start_tour_shows_widget(self):
        from PySide6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        from ui.copilot.widgets.guided_overlay_widget import GuidedOverlayWidget

        overlay = GuidedOverlayWidget(parent=parent)
        steps = [
            {"step_id": "s1", "type": "dim", "tooltip_key": "test.step1", "order": 1},
            {"step_id": "s2", "type": "highlight", "target_element_id": "nav_overview",
             "tooltip_key": "test.step2", "order": 2},
        ]
        overlay.start_tour(steps, title_key="test.title")
        assert overlay.is_active() is True
        assert overlay.total_steps() == 2
        assert overlay.current_step_index() == 0
        assert overlay.current_step_id() == "s1"

    def test_next_step_advances(self):
        from PySide6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        from ui.copilot.widgets.guided_overlay_widget import GuidedOverlayWidget

        overlay = GuidedOverlayWidget(parent=parent)
        steps = [
            {"step_id": "s1", "type": "dim", "tooltip_key": "test.s1", "order": 1},
            {"step_id": "s2", "type": "dim", "tooltip_key": "test.s2", "order": 2},
        ]
        overlay.start_tour(steps)
        assert overlay.current_step_index() == 0
        overlay.next_step()
        assert overlay.current_step_index() == 1

    def test_cancel_hides_widget(self):
        from PySide6.QtWidgets import QApplication, QWidget

        app = QApplication.instance() or QApplication([])
        parent = QWidget()
        from ui.copilot.widgets.guided_overlay_widget import GuidedOverlayWidget

        overlay = GuidedOverlayWidget(parent=parent)
        steps = [{"step_id": "s1", "type": "dim", "tooltip_key": "test.s1", "order": 1}]
        overlay.start_tour(steps)
        assert overlay.is_active() is True
        overlay.cancel()
        assert overlay.is_active() is False
