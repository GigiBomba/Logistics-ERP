"""GuidedOverlayWidget — interactive step-by-step UI tour overlay.

Blueprint: §34.4 — Frontend Guided UI Overlay.

Renders a full-window dim scrim with highlighted target elements,
tooltip bubbles, optional arrow pointers, and pulse animations.
Supports wait_for_click and wait_for_input step types that block
advancement until the user actually interacts with the target.

States:
    HIDDEN       — invisible, not active
    SHOWING      — dim + tooltip visible, waiting for non-blocking step
    WAITING_CLICK   — dim + highlight + tooltip, listening for click on target
    WAITING_INPUT   — dim + highlight + tooltip, listening for input on target
    ANIMATING    — cross-fade transition between steps

Design tokens (indigo primary #6366F1):
    - Highlight ring: 3px solid indigo with 2s pulse animation
    - Tooltip card: COLOR_BG_ELEVATED background, COLOR_TEXT_PRIMARY text
    - Dim scrim: COLOR_BG_BASE at ~55% opacity
    - Controls bottom-right: Cancel | Skip | Replay buttons
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAccessible,
    QAccessibleEvent,
    QColor,
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.copilot.element_registry import resolve_element
from ui.design_tokens import (
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_BASE,
    COLOR_BG_CARD,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

HIGHLIGHT_RING_WIDTH = 3
HIGHLIGHT_RING_COLOR = COLOR_ACCENT_PRIMARY  # #6366F1
HIGHLIGHT_RING_RADIUS = 8
DIM_OPACITY = 0.55
PULSE_INTERVAL_MS = 2000
PULSE_DURATION_MS = 600
ANIM_DURATION_MS = 300
TOOLTIP_MAX_WIDTH = 400


class GuidedOverlayWidget(QWidget):
    """Full-window overlay for interactive guided walkthroughs.

    Signals:
        cancelled: emitted when user clicks Cancel
        skipped: emitted when user clicks Skip
        replayed: emitted when user clicks Replay
        completed: emitted when the final step is reached
        step_changed(step_index): emitted on every step transition
    """

    cancelled = Signal()
    skipped = Signal()
    replayed = Signal()
    completed = Signal()
    step_changed = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("guided-overlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # ── State ────────────────────────────────────────────────────────
        self._steps: list[dict[str, Any]] = []
        self._current_step_index: int = 0
        self._state: str = "HIDDEN"  # HIDDEN | SHOWING | WAITING_CLICK | WAITING_INPUT | ANIMATING
        self._title_key: str = ""
        self._title_params: dict[str, Any] = {}

        # ── Target tracking ──────────────────────────────────────────────
        self._target_widget: Optional[QWidget] = None
        self._target_rect: QRect = QRect()
        self._pulse_value: float = 0.0  # 0.0–1.0 for pulse animation

        # ── UI elements ──────────────────────────────────────────────────
        self._tooltip_card: Optional[QFrame] = None
        self._tooltip_label: Optional[QLabel] = None
        self._step_counter: Optional[QLabel] = None

        # ── Controls ─────────────────────────────────────────────────────
        self._cancel_btn: Optional[QPushButton] = None
        self._skip_btn: Optional[QPushButton] = None
        self._replay_btn: Optional[QPushButton] = None

        # ── Animations ───────────────────────────────────────────────────
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._start_pulse)
        self._pulse_anim: Optional[QPropertyAnimation] = None
        self._fade_anim: Optional[QPropertyAnimation] = None
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        # ── Install event filter on parent for resize tracking ───────────
        self._parent_event_filter: Optional[_ParentResizeFilter] = None

        self._build_ui()
        self.setAccessibleName("Guided Tour Overlay")
        self.setAccessibleDescription("Step-by-step guided walkthrough overlay")
        self.hide()

    # ── Public API ────────────────────────────────────────────────────────

    def start_tour(
        self,
        steps: list[dict[str, Any]],
        title_key: str = "",
        title_params: dict[str, Any] | None = None,
        start_from: int = 0,
    ) -> None:
        """Begin a guided walkthrough with the given steps.

        Args:
            steps: List of step dicts (must have step_id, type, tooltip_key).
            title_key: i18n key for the walkthrough title.
            title_params: Optional params for title interpolation.
            start_from: Step index to start from (for resume after pause).
        """
        self._steps = steps
        self._title_key = title_key
        self._title_params = title_params or {}
        self._current_step_index = start_from

        if self.parentWidget() and self._parent_event_filter is None:
            self._parent_event_filter = _ParentResizeFilter(self, self.parentWidget())
            self.parentWidget().installEventFilter(self._parent_event_filter)
            self._parent_event_filter.resized.connect(self._on_parent_resized)

        self._show_step(start_from)

        # Announce tour start to screen readers
        QAccessible.updateAccessibility(QAccessibleEvent(self, QAccessible.Event.Alert))

    def next_step(self) -> None:
        """Advance to the next step (if not on the last)."""
        if self._current_step_index < len(self._steps) - 1:
            self._current_step_index += 1
            self._show_step(self._current_step_index)
        else:
            self._finish_tour()

    def prev_step(self) -> None:
        """Go back to the previous step (if not on the first)."""
        if self._current_step_index > 0:
            self._current_step_index -= 1
            self._show_step(self._current_step_index)

    def cancel(self) -> None:
        """Cancel the tour and hide the overlay."""
        self._cleanup()
        self.hide()
        self._state = "HIDDEN"
        self.cancelled.emit()
        logger.info("Tour cancelled at step %d/%d", self._current_step_index + 1, len(self._steps))

    def skip_step(self) -> None:
        """Skip the current step (advance without interaction)."""
        if self._current_step_index < len(self._steps) - 1:
            self._current_step_index += 1
            self._show_step(self._current_step_index)
        else:
            self._finish_tour()

    def replay(self) -> None:
        """Restart the tour from step 0."""
        self._current_step_index = 0
        self._show_step(0)
        self.replayed.emit()

    def is_active(self) -> bool:
        """Return True if the overlay is currently showing a tour."""
        return self._state != "HIDDEN"

    def current_step_id(self) -> Optional[str]:
        """Return the step_id of the current step, or None."""
        if 0 <= self._current_step_index < len(self._steps):
            return self._steps[self._current_step_index].get("step_id")
        return None

    def current_step_index(self) -> int:
        return self._current_step_index

    def total_steps(self) -> int:
        return len(self._steps)

    # ─── UI Build ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Create the overlay child widgets."""
        self.resize(self.parentWidget().size() if self.parentWidget() else QApplication.primaryScreen().size())

        # ── Tooltip card ─────────────────────────────────────────────────
        self._tooltip_card = QFrame(self)
        self._tooltip_card.setObjectName("guided-tooltip")
        self._tooltip_card.setStyleSheet(f"""
            #guided-tooltip {{
                background-color: {COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_LG}px;
            }}
        """)
        card_layout = QVBoxLayout(self._tooltip_card)
        card_layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        card_layout.setSpacing(SPACE_2)

        # Step counter (e.g., "2 / 8")
        self._step_counter = QLabel("", self._tooltip_card)
        self._step_counter.setStyleSheet(f"""
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_XS}px;
            font-weight: {FONT_WEIGHT_MEDIUM};
            background: transparent;
            border: none;
        """)
        card_layout.addWidget(self._step_counter)

        # Tooltip text
        self._tooltip_label = QLabel("", self._tooltip_card)
        self._tooltip_label.setWordWrap(True)
        self._tooltip_label.setMaximumWidth(TOOLTIP_MAX_WIDTH)
        self._tooltip_label.setStyleSheet(f"""
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
            background: transparent;
            border: none;
        """)
        card_layout.addWidget(self._tooltip_label)

        # ── Control buttons ──────────────────────────────────────────────
        controls_frame = QFrame(self._tooltip_card)
        controls_frame.setStyleSheet("background: transparent; border: none;")
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(0, SPACE_2, 0, 0)
        controls_layout.setSpacing(SPACE_2)

        # Cancel
        self._cancel_btn = QPushButton(t("tour.control.cancel"), controls_frame)
        self._cancel_btn.setStyleSheet(self._control_btn_style())
        self._cancel_btn.setAccessibleName("Cancel tour")
        self._cancel_btn.setAccessibleDescription("Exit the guided walkthrough")
        self._cancel_btn.clicked.connect(self.cancel)
        controls_layout.addWidget(self._cancel_btn)

        # Skip
        self._skip_btn = QPushButton(t("tour.control.skip"), controls_frame)
        self._skip_btn.setStyleSheet(self._control_btn_style())
        self._skip_btn.setAccessibleName("Skip step")
        self._skip_btn.setAccessibleDescription("Skip to the next step of the tour")
        self._skip_btn.clicked.connect(self.skip_step)
        controls_layout.addWidget(self._skip_btn)

        # Replay (hidden by default, shown when tour is partially done)
        self._replay_btn = QPushButton(t("tour.control.replay"), controls_frame)
        self._replay_btn.setStyleSheet(self._control_btn_style())
        self._replay_btn.setAccessibleName("Replay tour")
        self._replay_btn.setAccessibleDescription("Restart the tour from the beginning")
        self._replay_btn.clicked.connect(self.replay)
        self._replay_btn.setVisible(False)
        controls_layout.addWidget(self._replay_btn)

        controls_layout.addStretch(1)
        card_layout.addWidget(controls_frame)

        self._tooltip_card.hide()

    def _control_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_XS}px;
                padding: 4px {SPACE_3}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """

    # ── Step Display ─────────────────────────────────────────────────────

    def _show_step(self, index: int) -> None:
        """Display the step at the given index."""
        if not self._steps or index < 0 or index >= len(self._steps):
            return

        step = self._steps[index]
        step_type = step.get("type", "dim")
        tooltip_key = step.get("tooltip_key", "")
        target_id = step.get("target_element_id")
        tooltip_params = step.get("tooltip_params", {})

        # Fade in new step
        self._state = "ANIMATING"
        self._fade_transition(lambda: self._render_step(step_type, target_id, tooltip_key, tooltip_params, index))

    def _render_step(
        self,
        step_type: str,
        target_id: Optional[str],
        tooltip_key: str,
        tooltip_params: dict[str, Any],
        index: int,
    ) -> None:
        """Render the current step's visual state."""
        # Resolve target widget
        self._target_widget = None
        self._target_rect = QRect()
        if target_id:
            object_name = resolve_element(target_id)
            if object_name:
                self._target_widget = self._find_widget_by_object_name(object_name)

        # Update tooltip
        tooltip_text = t(tooltip_key, **tooltip_params) if tooltip_key else ""
        if self._tooltip_label:
            self._tooltip_label.setText(tooltip_text)
        if self._step_counter:
            self._step_counter.setText(f"{index + 1} / {len(self._steps)}")

        # Position tooltip near target
        self._position_tooltip()

        # Update state
        if step_type == "wait_for_click":
            self._state = "WAITING_CLICK"
            self._start_pulse()
        elif step_type == "wait_for_input":
            self._state = "WAITING_INPUT"
            self._start_pulse()
            self._install_input_filter()
        elif step_type == "show_success":
            self._state = "SHOWING"
            self._stop_pulse()
            # Auto-advance after showing success for a moment
            QTimer.singleShot(2000, self._finish_tour)
        elif step_type == "navigate":
            self._state = "SHOWING"
            self._stop_pulse()
            # Advance after a brief pause for the user to read
            QTimer.singleShot(3000, lambda: self.skip_step() if self.is_active() else None)
        else:
            self._state = "SHOWING"
            self._stop_pulse()

        # Show UI
        self._tooltip_card.show()
        self.show()
        self.raise_()

        # Emit step change
        self.step_changed.emit(index)

        # Announce step to screen readers
        if self._tooltip_label and self._tooltip_label.text():
            QAccessible.updateAccessibility(QAccessibleEvent(self, QAccessible.Event.Alert))

    def _position_tooltip(self) -> None:
        """Position the tooltip card near the target element."""
        if not self._tooltip_card:
            return

        target = self._target_widget
        if target and target.isVisible():
            # Get target's global position and map to overlay coordinates
            global_pos = target.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(global_pos)
            target_size = target.size()
            self._target_rect = QRect(local_pos, target_size)

            # Position tooltip below target, or above if near bottom
            card_width = min(TOOLTIP_MAX_WIDTH, self.width() - SPACE_4 * 2)
            half_width = card_width // 2
            cx = local_pos.x() + target_size.width() // 2
            # Clamp to screen edges
            tooltip_x = max(SPACE_2, min(cx - half_width, self.width() - card_width - SPACE_2))
            tooltip_y = local_pos.y() + target_size.height() + SPACE_3

            # Check if below would go off-screen
            card_height_est = 120  # approximate
            if tooltip_y + card_height_est > self.height():
                tooltip_y = local_pos.y() - card_height_est
                if tooltip_y < 0:
                    tooltip_y = SPACE_2

            self._tooltip_card.setGeometry(tooltip_x, tooltip_y, card_width, self._tooltip_card.sizeHint().height())
            self._tooltip_card.adjustSize()
        else:
            # No target — center the tooltip
            card_width = min(TOOLTIP_MAX_WIDTH, self.width() - SPACE_6 * 2)
            cx = (self.width() - card_width) // 2
            cy = self.height() // 3
            self._tooltip_card.setGeometry(cx, cy, card_width, self._tooltip_card.sizeHint().height())
            self._tooltip_card.adjustSize()

        # Ensure tooltip is fully visible
        self._clamp_tooltip_position()

    def _clamp_tooltip_position(self) -> None:
        """Clamp tooltip within screen bounds."""
        if not self._tooltip_card:
            return
        geo = self._tooltip_card.geometry()
        if geo.left() < 0:
            geo.moveLeft(SPACE_2)
        if geo.top() < 0:
            geo.moveTop(SPACE_2)
        if geo.right() > self.width():
            geo.moveRight(self.width() - SPACE_2)
        if geo.bottom() > self.height():
            geo.moveBottom(self.height() - SPACE_2)
        self._tooltip_card.setGeometry(geo)

    # ── Event Handling ────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse clicks — wait_for_click advances on target click."""
        if self._state == "WAITING_CLICK" and self._target_widget:
            global_pos = event.globalPosition().toPoint()
            target_global = self._target_widget.mapToGlobal(QPoint(0, 0))
            target_rect = QRect(target_global, self._target_widget.size())
            if target_rect.contains(global_pos):
                # Let the click pass through and advance to next step
                QTimer.singleShot(100, self.next_step)

        # Cancel on clicking outside the tooltip (if not WAITING_CLICK/INPUT)
        if self._state == "SHOWING" and self._tooltip_card:
            if not self._tooltip_card.geometry().contains(event.position().toPoint()):
                pass  # Don't auto-cancel on outside click — too aggressive

        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Escape:
            self.cancel()
        elif event.key() == Qt.Key_Space or event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
            if self._state != "WAITING_CLICK":
                self.skip_step()
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Reposition tooltip on window resize."""
        super().resizeEvent(event)
        if self.is_active():
            self._position_tooltip()
            self.update()

    # ── Painting (dim overlay + highlight ring + pulse) ───────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the dim overlay, highlight ring, and pulse animation."""
        if self._state == "HIDDEN":
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # ── Dim scrim ────────────────────────────────────────────────────
        dim_color = QColor(COLOR_BG_BASE)
        dim_color.setAlphaF(DIM_OPACITY)
        painter.fillRect(self.rect(), dim_color)

        # ── Highlight ring around target ─────────────────────────────────
        if self._state in ("WAITING_CLICK", "WAITING_INPUT", "SHOWING") and not self._target_rect.isEmpty():
            # Expose the target area (remove dim from target)
            # Draw a "cutout" by filling the area with semi-transparent
            target_color = QColor(COLOR_BG_BASE)
            target_color.setAlphaF(0.0)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.fillRect(self._target_rect, target_color)

            # Draw highlight ring
            pulse_offset = int(self._pulse_value * 6) if self._pulse_value > 0 else 0
            ring_rect = self._target_rect.adjusted(
                -HIGHLIGHT_RING_WIDTH - pulse_offset,
                -HIGHLIGHT_RING_WIDTH - pulse_offset,
                HIGHLIGHT_RING_WIDTH + pulse_offset,
                HIGHLIGHT_RING_WIDTH + pulse_offset,
            )

            pen = QPen(QColor(HIGHLIGHT_RING_COLOR), HIGHLIGHT_RING_WIDTH + pulse_offset // 2)
            painter.setPen(pen)
            painter.drawRoundedRect(ring_rect, HIGHLIGHT_RING_RADIUS, HIGHLIGHT_RING_RADIUS)

        painter.end()

    # ── Pulse Animation ───────────────────────────────────────────────────

    def _start_pulse(self) -> None:
        """Start the 2s pulse animation on the highlight ring."""
        self._pulse_timer.start(PULSE_INTERVAL_MS)
        self._do_pulse()

    def _stop_pulse(self) -> None:
        """Stop the pulse animation."""
        self._pulse_timer.stop()
        if self._pulse_anim:
            self._pulse_anim.stop()
            self._pulse_anim = None
        self._pulse_value = 0.0
        self.update()

    def _do_pulse(self) -> None:
        """Run a single pulse animation cycle."""
        if self._pulse_anim:
            self._pulse_anim.stop()
        self._pulse_anim = QPropertyAnimation(self, b"pulse_value")
        self._pulse_anim.setDuration(PULSE_DURATION_MS)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.OutQuad)
        self._pulse_anim.finished.connect(lambda: setattr(self, "_pulse_value", 0.0))
        self._pulse_anim.start()

    def _get_pulse_value(self) -> float:
        return self._pulse_value

    def _set_pulse_value(self, val: float) -> None:
        self._pulse_value = val
        self.update()

    pulse_value = Property(float, _get_pulse_value, _set_pulse_value)

    # ── Fade Transition ───────────────────────────────────────────────────

    def _fade_transition(self, on_complete: Callable) -> None:
        """Cross-fade to the next step."""
        if self._fade_anim:
            self._fade_anim.stop()

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(ANIM_DURATION_MS // 2)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.InQuad)

        fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade_in.setDuration(ANIM_DURATION_MS // 2)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutQuad)

        self._fade_anim.finished.connect(on_complete)
        self._fade_anim.finished.connect(fade_in.start)
        self._fade_anim.start()

    # ── Finish / Cleanup ──────────────────────────────────────────────────

    def _finish_tour(self) -> None:
        """Mark the tour as complete and close the overlay."""
        self._cleanup()
        self.hide()
        self._state = "HIDDEN"
        self.completed.emit()

        # Announce tour completion to screen readers
        QAccessible.updateAccessibility(QAccessibleEvent(self, QAccessible.Event.Alert))

        logger.info("Tour completed")

    def _cleanup(self) -> None:
        """Clean up timers and animations."""
        self._stop_pulse()
        self._remove_input_filter()
        if self._fade_anim:
            self._fade_anim.stop()
            self._fade_anim = None
        self._tooltip_card.hide()
        self._target_widget = None
        self._target_rect = QRect()

    # ── Input event filter for WAITING_INPUT state ────────────────────────

    def _install_input_filter(self) -> None:
        """Install event filter on target widget to detect text input."""
        if self._target_widget and not hasattr(self, "_input_filter"):
            self._input_filter = _InputEventFilter(self, self._target_widget)
            self._input_filter.input_detected.connect(self._on_input_detected)
            self._target_widget.installEventFilter(self._input_filter)

    def _remove_input_filter(self) -> None:
        """Remove the input event filter."""
        if hasattr(self, "_input_filter") and self._input_filter:
            if self._target_widget:
                self._target_widget.removeEventFilter(self._input_filter)
            self._input_filter = None

    def _on_input_detected(self) -> None:
        """Handle input detected on target widget — advance to next step."""
        if self._state == "WAITING_INPUT":
            self._remove_input_filter()
            QTimer.singleShot(100, self.next_step)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _find_widget_by_object_name(self, object_name: str) -> Optional[QWidget]:
        """Find a widget with the given objectName in the widget tree."""
        if not self.parentWidget():
            return None

        # Search the entire widget tree
        widgets = self.parentWidget().findChildren(QWidget, name=object_name)
        for w in widgets:
            if w.isVisible():
                return w
        # Return first match even if not visible
        return widgets[0] if widgets else None

    def _on_parent_resized(self) -> None:
        """Handle parent widget resize."""
        if self.parentWidget():
            self.resize(self.parentWidget().size())
            if self.is_active():
                self._position_tooltip()
                self.update()


class _ParentResizeFilter(QObject):
    """Event filter that emits resized when the parent widget resizes."""

    resized = Signal()

    def __init__(self, overlay: GuidedOverlayWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self._overlay = overlay

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Resize:
            self.resized.emit()
        return super().eventFilter(obj, event)


class _InputEventFilter(QObject):
    """Event filter that detects text input on a target widget.

    Used by GuidedOverlayWidget for wait_for_input step type — emits
    ``input_detected`` when the user types into the target field.
    """

    input_detected = Signal()

    def __init__(self, overlay: "GuidedOverlayWidget", target: QWidget) -> None:
        super().__init__(target)
        self._overlay = overlay
        self._original_text: str = ""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.KeyPress:
            # Detect any text input key (letters, numbers, backspace, delete)
            self._overlay._on_input_detected()
        elif event.type() == QEvent.FocusIn:
            # Also detect focus gain on the target field as a signal
            pass  # Wait for actual input, not just focus
        return super().eventFilter(obj, event)
