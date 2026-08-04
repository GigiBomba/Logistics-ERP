"""Tests for StruggleDetector — autonomously detects user struggle patterns.

Blueprint: §34.9 (workflow abandonment), §18 (workflow_struggle_job concept).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from freezegun import freeze_time

from ui.copilot.tour_scripts import ALL_SCRIPTS

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def detector(qapp):
    """Create a fresh StruggleDetector instance for each test."""
    from ui.copilot.controllers.struggle_detector import StruggleDetector

    return StruggleDetector()


# ── Tests: RecordNavigation ─────────────────────────────────────────────────


class TestRecordNavigation:
    """Basic navigation recording behaviour."""

    def test_initial_state(self, detector):
        """Fresh detector has empty history, no nudge time, idle timer inactive."""
        assert len(detector._nav_history) == 0
        assert detector._last_nudge_time is None
        assert detector._idle_timer.isActive() is False

    def test_record_navigation_appends(self, detector):
        """record_navigation adds one entry to ``_nav_history``."""
        with freeze_time("2024-06-01 12:00:00"):
            detector.record_navigation("fleet")
            assert len(detector._nav_history) == 1
            screen, ts = detector._nav_history[0]
            assert screen == "fleet"
            assert isinstance(ts, datetime)


# ── Tests: RapidNavigationDetection ─────────────────────────────────────────


class TestRapidNavigationDetection:
    """4+ screen switches within the 30-second window without an action."""

    def test_rapid_nav_starts_idle_timer(self, detector):
        """4 rapid unique switches within 30s → idle timer becomes active."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            for screen in ("fleet", "dispatch_board", "drivers", "invoices"):
                detector.record_navigation(screen)
                frozen.tick(5)
            assert detector._idle_timer.isActive() is True

    def test_rapid_nav_with_recent_action_suppressed(self, detector):
        """record_action() before rapid nav → suppression (no timer start)."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            detector.record_action()  # sets _last_action_time = now
            for screen in ("fleet", "dispatch_board", "drivers", "invoices"):
                detector.record_navigation(screen)
                frozen.tick(5)
            # _last_action_time is within the 30s window → suppression
            assert detector._idle_timer.isActive() is False


# ── Tests: RepeatedPatternDetection ─────────────────────────────────────────


class TestRepeatedPatternDetection:
    """A→B→A→B→A→B back-and-forth pattern detection."""

    def test_repeated_pattern_detected(self, detector, qtbot):
        """fleet→dispatch→fleet→dispatch→fleet→dispatch triggers a nudge."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            pattern = ["fleet", "dispatch_board", "fleet",
                       "dispatch_board", "fleet", "dispatch_board"]
            # The last navigation call should trigger the nudge
            with qtbot.waitSignal(detector.struggle_detected, timeout=500):
                for screen in pattern:
                    detector.record_navigation(screen)
                    frozen.tick(2)

    def test_non_repeated_pattern_no_nudge(self, detector):
        """fleet→dispatch→drivers→overview → no nudge emitted."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            emitted = []
            detector.struggle_detected.connect(lambda *a: emitted.append(a))
            for screen in ("fleet", "dispatch_board", "drivers", "overview"):
                detector.record_navigation(screen)
                frozen.tick(5)
            assert len(emitted) == 0


# ── Tests: CooldownEnforcement ──────────────────────────────────────────────


class TestCooldownEnforcement:
    """Second nudge blocked within the 120-second cooldown window."""

    def test_cooldown_blocks_second_nudge(self, detector):
        """Trigger nudge, wait 30s (<120) → second nudge is blocked."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            detector._trigger_nudge("fleet")
            assert detector._last_nudge_time is not None

            frozen.tick(30)
            emitted = []
            detector.struggle_detected.connect(lambda *a: emitted.append(a))
            detector._trigger_nudge("fleet")
            assert len(emitted) == 0

    def test_cooldown_expired_allows_nudge(self, detector, qtbot):
        """Wait 121s (≥120) → nudge is allowed."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            detector._trigger_nudge("fleet")
            frozen.tick(121)
            with qtbot.waitSignal(detector.struggle_detected, timeout=500):
                detector._trigger_nudge("fleet")


# ── Tests: RecordActionResets ───────────────────────────────────────────────


class TestRecordActionResets:
    """record_action clears navigation history and stops the idle timer."""

    def test_record_action_clears_history(self, detector):
        """Navigate 3x → record_action → _nav_history is empty."""
        with freeze_time("2024-06-01 12:00:00"):
            for screen in ("fleet", "dispatch_board", "drivers"):
                detector.record_navigation(screen)
            assert len(detector._nav_history) == 3
            detector.record_action()
            assert len(detector._nav_history) == 0

    def test_record_action_stops_idle_timer(self, detector):
        """Rapid nav starts timer → record_action stops it."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            for screen in ("fleet", "dispatch_board", "drivers", "invoices"):
                detector.record_navigation(screen)
                frozen.tick(5)
            assert detector._idle_timer.isActive() is True
            detector.record_action()
            assert detector._idle_timer.isActive() is False


# ── Tests: Reset ────────────────────────────────────────────────────────────


class TestReset:
    """Full state clear."""

    def test_reset_clears_everything(self, detector):
        """Set all state → reset() → initial state restored."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            detector.record_navigation("fleet")
            detector.record_navigation("dispatch_board")
            detector.record_navigation("drivers")
            detector._last_action_time = datetime.utcnow()
            detector._trigger_nudge("fleet")

            # Verify non-default state
            assert len(detector._nav_history) == 3
            assert detector._last_nudge_time is not None
            assert detector._last_action_time is not None

            detector.reset()

            assert len(detector._nav_history) == 0
            assert detector._last_nudge_time is None
            assert detector._last_action_time is None
            assert detector._idle_timer.isActive() is False


# ── Tests: TriggerNudge ─────────────────────────────────────────────────────


class TestTriggerNudge:
    """Signal payload correctness."""

    def test_nudge_payload_contains_workflow_id(self, detector, qtbot):
        """Signal carries the correct workflow_id for a mapped screen."""
        with freeze_time("2024-06-01 12:00:00"):
            with qtbot.waitSignal(detector.struggle_detected,
                                  timeout=500) as blocker:
                detector._trigger_nudge("fleet")
            workflow_id, tooltip_key = blocker.args
        assert workflow_id == "app_overview"

    def test_nudge_payload_contains_tooltip_key(self, detector, qtbot):
        """Signal carries the first step's tooltip_key from ALL_SCRIPTS."""
        with freeze_time("2024-06-01 12:00:00"):
            with qtbot.waitSignal(detector.struggle_detected,
                                  timeout=500) as blocker:
                detector._trigger_nudge("fleet")
            _workflow_id, tooltip_key = blocker.args
        expected_key = ALL_SCRIPTS["app_overview"]["steps"][0]["tooltip_key"]
        assert tooltip_key == expected_key

    def test_unknown_screen_defaults_to_app_overview(self, detector, qtbot):
        """Unmapped screen → nudge uses ``app_overview`` as the workflow."""
        with freeze_time("2024-06-01 12:00:00"):
            with qtbot.waitSignal(detector.struggle_detected,
                                  timeout=500) as blocker:
                detector._trigger_nudge("totally_unknown")
            workflow_id, tooltip_key = blocker.args
        assert workflow_id == "app_overview"
        expected_key = ALL_SCRIPTS["app_overview"]["steps"][0]["tooltip_key"]
        assert tooltip_key == expected_key


# ── Tests: IdleAfterRapidNav ────────────────────────────────────────────────


class TestIdleAfterRapidNav:
    """Idle timer fires after rapid navigation and emits the nudge."""

    def test_idle_timer_fires_nudge(self, detector, qtbot):
        """Rapid nav → _on_idle_after_rapid_nav → struggle_detected emitted."""
        with freeze_time("2024-06-01 12:00:00") as frozen:
            for screen in ("fleet", "dispatch_board", "drivers", "invoices"):
                detector.record_navigation(screen)
                frozen.tick(5)
            assert detector._idle_timer.isActive() is True

            with qtbot.waitSignal(detector.struggle_detected,
                                  timeout=500) as blocker:
                detector._on_idle_after_rapid_nav()
            assert blocker.signal_triggered
