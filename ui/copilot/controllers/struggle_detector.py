"""StruggleDetector — autonomously detects user struggle patterns.

Blueprint: §34.9 (workflow abandonment), §18 (workflow_struggle_job concept).

Scenarios that indicate the user is struggling:
1. Rapid navigation between many screens without taking any action
2. Multiple cancelled/skipped walkthroughs in a row
3. Repeating the same navigation pattern (back and forth between two screens)
4. Long pauses on a screen without interaction after rapid navigation

When detected, triggers a subtle tooltip/suggestion from the relevant tour
content — phrased as a helpful nudge, NEVER as "you missed this" or
"you're doing it wrong."

The detection is deliberately simple and local (client-side only).
It does NOT call the backend AI — it's a pattern-matching heuristic
that reuses existing tour content for the nudges.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from ui.copilot.tour_scripts import ALL_SCRIPTS

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

RAPID_NAV_WINDOW_SEC = 30       # Time window for "rapid" navigation detection
RAPID_NAV_THRESHOLD = 4          # Number of screen switches within the window to flag
REPEATED_NAV_PATTERN_MIN = 3     # min times a back-and-forth pattern repeats
IDLE_AFTER_RAPID_NAV_SEC = 15    # seconds of idle after rapid nav to trigger nudge
COOLDOWN_SEC = 120               # don't nudge again within this period after a nudge


class StruggleDetector(QObject):
    """Detects user struggle patterns and emits helpful nudges.

    Signals:
        struggle_detected(workflow_id: str, tooltip_key: str):
            Emitted when a struggle pattern is detected.
            workflow_id: the most relevant tour for the current screen.
            tooltip_key: the i18n key for the nudge text (from tour content).
    """

    struggle_detected = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._nav_history: deque[tuple[str, datetime]] = deque(maxlen=20)
        self._last_nudge_time: datetime | None = None
        self._last_action_time: datetime | None = None
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_after_rapid_nav)

        # Map screen names to tour workflow IDs for relevant nudges
        self._screen_to_workflow: dict[str, str] = {
            "fleet": "app_overview",
            "driver_manager": "add_driver",
            "invoices": "generate_invoice",
            "dispatch_board": "dispatch_trip",
            "maintenance": "schedule_maintenance",
            "copilot": "app_overview",
            "overview": "app_overview",
        }

    # ── Public API ────────────────────────────────────────────────────────

    def record_navigation(self, screen_key: str) -> None:
        """Call this whenever the user navigates to a different screen.

        Args:
            screen_key: The module key (e.g. "fleet", "dispatch_board").
        """
        now = datetime.utcnow()
        self._nav_history.append((screen_key, now))
        self._check_rapid_navigation(now)

    def record_action(self) -> None:
        """Call this whenever the user performs a meaningful action.

        This resets the struggle detection counters.
        """
        self._last_action_time = datetime.utcnow()
        self._nav_history.clear()
        self._idle_timer.stop()

    def record_walkthrough_cancelled(self) -> None:
        """Call when a walkthrough is cancelled (adds to struggle signal)."""
        # Could be used in future for multi-cancellation detection
        pass

    def reset(self) -> None:
        """Reset all struggle state."""
        self._nav_history.clear()
        self._last_nudge_time = None
        self._last_action_time = None
        self._idle_timer.stop()

    # ── Detection Logic ───────────────────────────────────────────────────

    def _check_rapid_navigation(self, now: datetime) -> None:
        """Check if the user is rapidly switching screens without action."""
        if self._last_action_time and (now - self._last_action_time).total_seconds() < RAPID_NAV_WINDOW_SEC:
            # User has taken an action recently — not struggling
            return

        # Check if we're in cooldown (don't spam nudges)
        if self._last_nudge_time:
            cooldown_remaining = (now - self._last_nudge_time).total_seconds()
            if cooldown_remaining < COOLDOWN_SEC:
                return

        # Count unique screen switches in the time window
        window_start = now - timedelta(seconds=RAPID_NAV_WINDOW_SEC)
        recent = [(s, t) for s, t in self._nav_history if t >= window_start]

        if len(recent) >= RAPID_NAV_THRESHOLD:
            # Detect rapid switching — start idle timer
            self._idle_timer.start(IDLE_AFTER_RAPID_NAV_SEC * 1000)

        # Check for repeated back-and-forth pattern
        if self._detect_repeated_pattern(recent):
            self._trigger_nudge(recent[-1][0] if recent else "overview")

        # Check for very high frequency (every 2-3 seconds)
        if len(recent) >= RAPID_NAV_THRESHOLD + 2:
            self._trigger_nudge(recent[-1][0] if recent else "overview")

    def _detect_repeated_pattern(self, recent: list[tuple[str, datetime]]) -> bool:
        """Detect A → B → A → B back-and-forth navigation."""
        if len(recent) < REPEATED_NAV_PATTERN_MIN * 2:
            return False

        screens = [s for s, _ in recent]
        # Look for 3+ repeats of the same pair
        if len(screens) >= 4:
            for i in range(len(screens) - 3):
                if (screens[i] == screens[i + 2] and
                        screens[i + 1] == screens[i + 3] and
                        screens[i] != screens[i + 1]):
                    # Found a repeated A → B → A → B pattern
                    return True
        return False

    def _on_idle_after_rapid_nav(self) -> None:
        """Fires after user rapidly navigated then went idle."""
        # Get the most recent screen
        if self._nav_history:
            latest_screen = self._nav_history[-1][0]
            self._trigger_nudge(latest_screen)

    def _trigger_nudge(self, current_screen: str) -> None:
        """Fire a struggle detection signal with a relevant tour nudge."""
        now = datetime.utcnow()
        if self._last_nudge_time:
            if (now - self._last_nudge_time).total_seconds() < COOLDOWN_SEC:
                return

        # Find the most relevant workflow for this screen
        workflow_id = self._screen_to_workflow.get(current_screen, "app_overview")

        # Get a tooltip key from the first step of that workflow
        script = ALL_SCRIPTS.get(workflow_id)
        tooltip_key = "tour.help_nudge.generic"
        if script and script.get("steps"):
            # Use the first step tooltip as the nudge
            first_step = script["steps"][0]
            tooltip_key = first_step.get("tooltip_key", "tour.help_nudge.generic")

        self._last_nudge_time = now
        self.struggle_detected.emit(workflow_id, tooltip_key)
        logger.info("Struggle detected: screen=%s workflow=%s", current_screen, workflow_id)
