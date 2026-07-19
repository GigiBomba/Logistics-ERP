"""TourController — manages onboarding and workflow walkthrough lifecycle.

Blueprint: §34 — Guided UI Mentor System.
§34.7 — Onboarding Tour (first launch).
§34.5 — Context Awareness (pause/resume).

Coordinates between:
- tour_tracker.py (completion file on disk)
- tour_scripts.py (authored walkthrough scripts)
- guided_overlay_widget.py (visual overlay component)
- element_registry.py (widget ID resolution)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from ui.copilot import tour_tracker
from ui.copilot.tour_scripts import ALL_SCRIPTS

logger = logging.getLogger(__name__)


class TourController(QObject):
    """Controls guided walkthrough lifecycle.

    Signals:
        tour_started(workflow_id): emitted when a tour begins
        tour_completed(workflow_id): emitted when a tour finishes (all steps done)
        tour_cancelled(workflow_id): emitted when user cancels
        tour_step_changed(workflow_id, step_index): emitted on each step transition
        tour_available(workflow_ids): emitted when first-launch detection finds available tours
    """

    tour_started = Signal(str)
    tour_completed = Signal(str)
    tour_cancelled = Signal(str)
    tour_step_changed = Signal(str, int)
    tour_available = Signal(list)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlay = None  # Set externally after creation: tour_controller.set_overlay(widget)
        self._current_workflow_id: str | None = None

    # ── Public API ────────────────────────────────────────────────────────

    def set_overlay(self, overlay) -> None:
        """Connect the overlay widget to this controller."""
        self._overlay = overlay
        if overlay:
            overlay.completed.connect(self._on_overlay_completed)
            overlay.cancelled.connect(self._on_overlay_cancelled)
            overlay.step_changed.connect(self._on_overlay_step)

    def start_tour(self, workflow_id: str) -> bool:
        """Start a guided walkthrough by workflow_id.

        Args:
            workflow_id: e.g. "app_overview", "add_driver", "generate_invoice"

        Returns:
            True if the tour started, False if the workflow_id is unknown or overlay not set.
        """
        if not self._overlay:
            logger.warning("Cannot start tour %s: no overlay set", workflow_id)
            return False

        script = ALL_SCRIPTS.get(workflow_id)
        if not script:
            logger.warning("Unknown tour workflow: %s", workflow_id)
            return False

        self._current_workflow_id = workflow_id
        title_key = script.get("title_key", "")
        title_params = script.get("title_params", {})
        steps = script.get("steps", [])

        if not steps:
            logger.warning("Tour %s has no steps", workflow_id)
            return False

        self._overlay.start_tour(steps, title_key=title_key, title_params=title_params)
        self.tour_started.emit(workflow_id)
        logger.info("Tour started: %s (%d steps)", workflow_id, len(steps))
        return True

    def start_onboarding(self) -> bool:
        """Start the onboarding tour (app_overview) if it hasn't been completed.

        Returns:
            True if the tour started, False if already completed or overlay not set.
        """
        if tour_tracker.is_tour_completed("app_overview"):
            logger.info("Onboarding tour already completed, skipping")
            return False

        return self.start_tour("app_overview")

    def can_show_onboarding(self) -> bool:
        """Check if the onboarding tour should be shown (first launch)."""
        return not tour_tracker.is_tour_completed("app_overview")

    def cancel_current(self) -> None:
        """Cancel the currently running tour."""
        if self._overlay and self._current_workflow_id:
            self._overlay.cancel()

    def skip_step(self) -> None:
        """Skip the current step."""
        if self._overlay:
            self._overlay.skip_step()

    def replay_tour(self, workflow_id: str) -> bool:
        """Reset and restart a tour (from settings or user request).

        Args:
            workflow_id: The tour to replay.

        Returns:
            True if the tour started.
        """
        # Clear the completion flag so the tour will show
        tour_tracker.clear_tour_completed(workflow_id)
        return self.start_tour(workflow_id)

    def pause_tour(self) -> dict | None:
        """Pause the current walkthrough and return saved state for resume.

        Returns a dict with {workflow_id, current_step_index} or None if no tour is active.
        The overlay is hidden but not destroyed — state is preserved.
        """
        if not self._overlay or not self._current_workflow_id:
            return None
        if not self._overlay.is_active():
            return None

        state = {
            "workflow_id": self._current_workflow_id,
            "current_step_index": self._overlay.current_step_index(),
        }
        self._overlay.hide()  # Hide the overlay but keep state
        logger.info("Tour paused: %s at step %d", state["workflow_id"], state["current_step_index"])
        return state

    def resume_tour(self, state: dict) -> bool:
        """Resume a paused walkthrough from saved state.

        Args:
            state: dict with {workflow_id, current_step_index} from pause_tour().

        Returns:
            True if the tour resumed, False if the workflow is unknown.
        """
        if not self._overlay:
            return False

        workflow_id = state.get("workflow_id", "")
        step_index = state.get("current_step_index", 0)

        script = ALL_SCRIPTS.get(workflow_id)
        if not script:
            logger.warning("Cannot resume unknown workflow: %s", workflow_id)
            return False

        self._current_workflow_id = workflow_id
        title_key = script.get("title_key", "")
        title_params = script.get("title_params", {})
        steps = script.get("steps", [])

        if not steps:
            logger.warning("Tour %s has no steps, cannot resume", workflow_id)
            return False

        # Clamp step index to valid range
        if step_index >= len(steps):
            step_index = 0

        self._overlay.start_tour(steps, title_key=title_key, title_params=title_params, start_from=step_index)
        self.tour_started.emit(workflow_id)
        logger.info("Tour resumed: %s at step %d", workflow_id, step_index)
        return True

    def get_available_tours(self) -> list[dict[str, Any]]:
        """Return list of all available tours with completion status."""
        result = []
        for wid, script in ALL_SCRIPTS.items():
            result.append({
                "workflow_id": wid,
                "title_key": script.get("title_key", ""),
                "completed": tour_tracker.is_tour_completed(wid),
                "step_count": len(script.get("steps", [])),
                "completion_count": tour_tracker.get_completion_count(wid),
            })
        return result

    def get_completed_tours(self) -> list[str]:
        """Return list of completed workflow IDs."""
        return tour_tracker.get_completed_tours()

    def is_tour_active(self) -> bool:
        """Check if a tour is currently in progress."""
        return self._overlay is not None and self._overlay.is_active()

    def current_workflow_id(self) -> str | None:
        return self._current_workflow_id

    def mark_all_completed(self) -> None:
        """Mark all tours as completed (for testing or bulk ops)."""
        for wid in ALL_SCRIPTS:
            tour_tracker.mark_tour_completed(wid)

    def reset_all(self) -> None:
        """Reset all tour completions."""
        tour_tracker.clear_all_tours()

    # ── Internal signal handlers ──────────────────────────────────────────

    def _on_overlay_completed(self) -> None:
        """Handle overlay completion signal."""
        wid = self._current_workflow_id
        if wid:
            tour_tracker.mark_tour_completed(wid)
            tour_tracker.increment_completion_count(wid)
            self.tour_completed.emit(wid)
            logger.info("Tour completed: %s", wid)
        self._current_workflow_id = None

    def _on_overlay_cancelled(self) -> None:
        """Handle overlay cancellation signal."""
        wid = self._current_workflow_id
        if wid:
            self.tour_cancelled.emit(wid)
            logger.info("Tour cancelled: %s", wid)
        self._current_workflow_id = None

    def _on_overlay_step(self, step_index: int) -> None:
        """Handle overlay step change signal."""
        if self._current_workflow_id:
            self.tour_step_changed.emit(self._current_workflow_id, step_index)
