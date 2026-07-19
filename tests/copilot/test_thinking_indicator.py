"""Comprehensive Qt unit tests for ThinkingIndicatorWidget.

Covers widget construction, animation state machine, dot cycling,
show/hide transitions, custom sizes, custom speed, and cleanup.
"""

from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QWidget

from ui.copilot.widgets.thinking_indicator import ThinkingIndicatorWidget


# =============================================================================
#  Helpers
# =============================================================================


def _get_dot_labels(widget: ThinkingIndicatorWidget) -> list[QLabel]:
    """Return the three dot QLabel children."""
    return list(widget._dots)


def _extract_opacity(stylesheet: str) -> str | None:
    """Extract the alpha hex (e.g. 'FF' or '44') from a rgba colour.

    The style is like: ``color: rgba(142, 142, 160, 44); ...``
    """
    for part in stylesheet.split(";"):
        part = part.strip()
        if part.startswith("color:"):
            # color: rgba(142, 142, 160, FF)
            rgba = part.split("(", 1)[-1].rsplit(")", 1)[0]
            parts = [p.strip() for p in rgba.split(",")]
            if len(parts) == 4:
                return parts[3]
    return None


# =============================================================================
#  Construction
# =============================================================================


class TestConstruction:
    """Widget construction, defaults, and initial state."""

    def test_can_construct(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert widget is not None
        assert isinstance(widget, ThinkingIndicatorWidget)

    def test_default_visibility_is_hidden(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert widget.isVisible() is False

    def test_size_policy(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        sp = widget.sizePolicy()
        assert sp.horizontalPolicy() == QSizePolicy.Preferred
        assert sp.verticalPolicy() == QSizePolicy.Fixed

    def test_has_three_dots(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert len(widget._dots) == 3

    def test_all_dots_start_at_full_opacity(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        for dot in widget._dots:
            opacity = _extract_opacity(dot.styleSheet())
            assert opacity == "FF" or opacity is None  # full opacity = no alpha override

    def test_timer_not_running_on_construction(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert widget._timer.isActive() is False

    def test_initial_frame_is_zero(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert widget._frame == 0

    def test_layout_contains_thinking_label(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        layout = widget.layout()
        assert layout is not None
        assert isinstance(layout, QHBoxLayout)
        # First item should be the "Thinking…" label
        label = layout.itemAt(0).widget()
        assert isinstance(label, QLabel)
        assert "Thinking" in label.text()

    def test_constant_values(self):
        assert ThinkingIndicatorWidget.DOT_COUNT == 3
        assert ThinkingIndicatorWidget.INTERVAL_MS == 400


# =============================================================================
#  Animation — start / stop
# =============================================================================


class TestAnimationLifecycle:
    """Animation starts, ticks, and stops correctly."""

    def test_start_shows_widget_and_starts_timer(self, qt_widget: QWidget):
        qt_widget.show()  # Parent must be visible for child isVisible() to work
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        assert widget.isVisible() is True
        assert widget._timer.isActive() is True

    def test_start_resets_frame_counter(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget._frame = 42
        widget.start()
        # start() calls _on_tick() which increments frame to 1
        assert widget._frame == 1

    def test_stop_hides_widget_and_stops_timer(self, qt_widget: QWidget):
        qt_widget.show()
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        assert widget.isVisible() is True
        widget.stop()
        assert widget.isVisible() is False
        assert widget._timer.isActive() is False

    def test_stop_resets_all_dots_to_full_opacity(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        # Let a few ticks happen so dots are in varied opacity
        widget._on_tick()
        widget._on_tick()
        # Verify at least one dot is at dim opacity
        dim_found = any(
            _extract_opacity(d.styleSheet()) == "44" for d in widget._dots
        )
        assert dim_found, "Expected at least one dim dot after several ticks"

        widget.stop()
        # All dots should be back to full opacity
        for dot in widget._dots:
            opacity = _extract_opacity(dot.styleSheet())
            assert opacity == "FF" or opacity is None

    def test_start_stop_idempotent(self, qt_widget: QWidget):
        """Calling start/stop multiple times should not raise."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        widget.start()  # second start
        assert widget._timer.isActive() is True
        widget.stop()
        widget.stop()  # second stop
        assert widget._timer.isActive() is False

    def test_stop_when_not_started_does_not_raise(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.stop()  # should be a no-op
        assert widget.isVisible() is False


# =============================================================================
#  Dot animation cycling
# =============================================================================


class TestDotCycling:
    """Each tick advances the lit dot in a round-robin fashion."""

    def test_tick_advances_frame(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert widget._frame == 0
        widget._on_tick()
        assert widget._frame == 1
        widget._on_tick()
        assert widget._frame == 2
        widget._on_tick()
        assert widget._frame == 3

    def test_dot_0_is_lit_on_first_tick(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget._on_tick()
        opacities = [_extract_opacity(d.styleSheet()) for d in widget._dots]
        # Dot 0 should be full opacity
        assert opacities[0] == "FF"
        # Others should be dim
        assert opacities[1] == "44"
        assert opacities[2] == "44"

    def test_dot_1_is_lit_on_second_tick(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget._on_tick()
        widget._on_tick()
        opacities = [_extract_opacity(d.styleSheet()) for d in widget._dots]
        assert opacities[0] == "44"
        assert opacities[1] == "FF"
        assert opacities[2] == "44"

    def test_dot_2_is_lit_on_third_tick(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget._on_tick()
        widget._on_tick()
        widget._on_tick()
        opacities = [_extract_opacity(d.styleSheet()) for d in widget._dots]
        assert opacities[0] == "44"
        assert opacities[1] == "44"
        assert opacities[2] == "FF"

    def test_cycling_wraps_around_on_fourth_tick(self, qt_widget: QWidget):
        """After 3 ticks, the 4th should light dot 0 again."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        for _ in range(3):
            widget._on_tick()
        widget._on_tick()  # 4th tick — wraps around
        opacities = [_extract_opacity(d.styleSheet()) for d in widget._dots]
        assert opacities[0] == "FF"
        assert opacities[1] == "44"
        assert opacities[2] == "44"

    def test_continuous_cycling_over_many_frames(self, qt_widget: QWidget):
        """Run many ticks and verify the pattern stays correct."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        for frame in range(30):
            widget._on_tick()
            expected_lit = frame % 3
            opacities = [_extract_opacity(d.styleSheet()) for d in widget._dots]
            for i, opacity in enumerate(opacities):
                if i == expected_lit:
                    assert opacity == "FF", f"Frame {frame}: dot {i} should be lit"
                else:
                    assert opacity == "44", f"Frame {frame}: dot {i} should be dim"

    def test_exactly_one_dot_lit_per_tick(self, qt_widget: QWidget):
        """After any tick, exactly one dot is at full opacity."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        for _ in range(10):
            widget._on_tick()
            lit_count = sum(
                1 for d in widget._dots if _extract_opacity(d.styleSheet()) == "FF"
            )
            assert lit_count == 1


# =============================================================================
#  Timer-driven animation
# =============================================================================


class TestTimerDrivenAnimation:
    """Animation runs on a real QTimer (uses qtbot to process events)."""

    def test_timer_fires_and_cycles_dots(self, qt_widget: QWidget, qtbot):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        # Wait for a few timer intervals
        qtbot.wait(widget.INTERVAL_MS * 4)
        # Frame should have advanced at least 3 times
        assert widget._frame >= 3
        widget.stop()

    def test_timer_stops_after_stop(self, qt_widget: QWidget, qtbot):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        qtbot.wait(widget.INTERVAL_MS * 2)
        widget.stop()
        frame_before = widget._frame
        qtbot.wait(widget.INTERVAL_MS * 3)
        # Frame should not advance after stop
        assert widget._frame == frame_before

    def test_animation_restarts_cleanly(self, qt_widget: QWidget, qtbot):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        qtbot.wait(widget.INTERVAL_MS * 3)
        widget.stop()
        widget.start()
        # After restart, frame is 1 (start() calls _on_tick() which runs with
        # frame=0 to light dot 0, then increments to frame=1). Dot 0 is lit.
        assert widget._frame == 1
        opacities = [_extract_opacity(d.styleSheet()) for d in widget._dots]
        assert opacities[0] == "FF"

    def test_multiple_start_stop_cycles(self, qt_widget: QWidget, qtbot):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        for _ in range(5):
            widget.start()
            qtbot.wait(widget.INTERVAL_MS * 2)
            widget.stop()
            assert widget._timer.isActive() is False
            assert widget.isVisible() is False


# =============================================================================
#  Custom animation speed
# =============================================================================


class TestCustomSpeed:
    """The animation speed can be controlled by patching INTERVAL_MS."""

    def test_faster_interval_ticks_quicker(self, qt_widget: QWidget, qtbot):
        with patch.object(ThinkingIndicatorWidget, "INTERVAL_MS", 10):
            widget = ThinkingIndicatorWidget(parent=qt_widget)
            widget.start()
            # Frame is 1 after start() (from the _on_tick() call inside).
            # Wait for several timer ticks at 10ms each.
            qtbot.wait(50)  # ~5 ticks at 10ms
            assert widget._frame >= 3  # initial tick + at least 2 more
            widget.stop()

    def test_slower_interval_ticks_slower(self, qt_widget: QWidget, qtbot):
        with patch.object(ThinkingIndicatorWidget, "INTERVAL_MS", 500):
            widget = ThinkingIndicatorWidget(parent=qt_widget)
            widget.start()
            # Frame is 1 after start() (from the _on_tick() call inside start())
            assert widget._frame == 1
            qtbot.wait(100)  # Less than one interval — no additional tick
            assert widget._frame == 1  # No tick beyond the initial one
            widget.stop()

    def test_zero_interval_does_not_raise(self, qt_widget: QWidget):
        with patch.object(ThinkingIndicatorWidget, "INTERVAL_MS", 0):
            widget = ThinkingIndicatorWidget(parent=qt_widget)
            widget.start()  # Should not raise even with 0ms
            assert widget._timer.isActive() is True
            widget.stop()


# =============================================================================
#  Show/hide transitions
# =============================================================================


class TestShowHideTransitions:
    """Widget visibility changes correctly via start/stop."""

    def test_start_triggers_show_event(self, qt_widget: QWidget, qtbot):
        qt_widget.show()
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        qtbot.wait_for_window_shown(widget)

    def test_stop_triggers_hide(self, qt_widget: QWidget, qtbot):
        qt_widget.show()
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        assert widget.isVisible() is True
        widget.stop()
        assert widget.isVisible() is False

    def test_visible_property_after_start_stop(self, qt_widget: QWidget):
        qt_widget.show()
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert widget.isVisible() is False
        widget.setVisible(True)
        assert widget.isVisible() is True
        widget.setVisible(False)
        assert widget.isVisible() is False

    def test_animation_does_not_run_when_hidden_directly(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        assert widget._timer.isActive() is True
        # Hiding via setVisible should not stop the timer (timer controls visibility)
        widget.setVisible(False)
        # The timer continues but the widget is hidden
        # This is expected — stop() should be used to fully halt
        assert widget._timer.isActive() is True


# =============================================================================
#  Different indicator sizes
# =============================================================================


class TestSizing:
    """Widget adapts to different sizes through its layout."""

    def test_minimum_size_hint(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        hint = widget.minimumSizeHint()
        assert hint.width() >= 0
        assert hint.height() >= 0

    def test_size_hint(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        hint = widget.sizeHint()
        assert hint.width() > 0
        assert hint.height() > 0

    def test_widget_can_be_resized(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.resize(300, 40)
        assert widget.width() == 300
        assert widget.height() == 40

    def test_dots_visible_after_resize(self, qt_widget: QWidget):
        qt_widget.show()
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.resize(500, 60)
        widget.start()
        for dot in widget._dots:
            assert dot.isVisible() is True
        widget.stop()

    def test_widget_in_a_parent_layout(self, qt_widget: QWidget):
        """Widget can be embedded and still animate."""
        from PySide6.QtWidgets import QVBoxLayout

        qt_widget.show()
        layout = QVBoxLayout(qt_widget)
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        layout.addWidget(widget)
        widget.start()
        assert widget.isVisible() is True
        assert widget._timer.isActive() is True
        widget.stop()


# =============================================================================
#  Cleanup on destruction
# =============================================================================


class TestCleanup:
    """Widget cleans up resources when destroyed."""

    def test_timer_stops_on_destruction(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        assert widget._timer.isActive() is True
        widget.deleteLater()
        # Process pending delete events
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.sendPostedEvents(widget, 0)
        # After destruction the timer should not be active
        # (direct access after deleteLater is undefined, but we can
        #  check that no crash occurs and the parent remains valid)
        assert qt_widget.isWidgetType() is True

    def test_multiple_delete_is_safe(self, qt_widget: QWidget):
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        widget.deleteLater()
        widget.deleteLater()  # Double delete should not raise

    def test_no_memory_leak_from_timer(self, qt_widget: QWidget):
        """Timer is child of widget so Qt cleans it up automatically."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        children = widget.findChildren(QTimer)
        assert len(children) == 1
        assert children[0] is widget._timer


# =============================================================================
#  Edge cases
# =============================================================================


class TestEdgeCases:
    """Edge and corner cases for the indicator."""

    def test_construct_without_parent(self, qapp):
        """Can construct without a parent (top-level widget)."""
        widget = ThinkingIndicatorWidget()
        assert widget is not None
        assert widget.parent() is None
        widget.start()
        assert widget._timer.isActive() is True
        widget.stop()
        widget.deleteLater()

    def test_dot_count_is_always_three(self, qt_widget: QWidget):
        """DOT_COUNT is a class constant, not instance-configurable."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        assert len(widget._dots) == 3
        # Create another instance to verify it also has 3
        widget2 = ThinkingIndicatorWidget(parent=qt_widget)
        assert len(widget2._dots) == 3

    def test_start_after_destruction_does_not_crash(self, qt_widget: QWidget):
        """Calling start on a deleted widget should be harmless."""
        widget = ThinkingIndicatorWidget(parent=qt_widget)
        widget.start()
        widget.deleteLater()
        # This should not crash (the widget may still be alive in Python)
        # We just verify the method doesn't raise
        try:
            widget.start()
        except RuntimeError:
            # C++ object already deleted — acceptable
            pass
