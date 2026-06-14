"""Toast notification widget for PySide6.

Replaces the legacy tk.Toplevel toast with a frameless overlay that fades in,
displays a message, and fades out automatically.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QTimer, QPoint
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout, QGraphicsOpacityEffect


class Toast(QFrame):
    """Non-blocking toast message that auto-dismisses after a delay."""

    DEFAULT_DURATION_MS = 2500
    FADE_DURATION_MS = 250

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        message: str = "",
        icon: str = "✅",
        duration_ms: int = DEFAULT_DURATION_MS,
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setProperty("role", "toast")

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._icon = QLabel(icon)
        self._icon.setProperty("role", "toast-icon")
        layout.addWidget(self._icon)

        self._label = QLabel(message)
        self._label.setProperty("role", "toast-label")
        layout.addWidget(self._label)

        self._duration_ms = duration_ms
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._start_fade_out)

        self._setup_animations()
        self.adjustSize()

    def _setup_animations(self):
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(self.FADE_DURATION_MS)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(self.FADE_DURATION_MS)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.close)

    def show_at(self, anchor: QWidget, offset: QPoint = QPoint(0, 0)) -> None:
        """Position the toast relative to ``anchor`` and show it."""
        if anchor is None:
            return
        self.adjustSize()
        global_pos = anchor.mapToGlobal(QPoint(0, 0))
        x = global_pos.x() + offset.x()
        y = global_pos.y() + offset.y()
        self.move(x, y)
        self.show()
        self.raise_()
        self._fade_in.start()
        self._dismiss_timer.start(self._duration_ms)

    def _start_fade_out(self):
        self._fade_out.start()

    @classmethod
    def show_success(
        cls,
        parent: QWidget,
        message: str,
        anchor: Optional[QWidget] = None,
    ) -> "Toast":
        toast = cls(parent, message, icon="✅")
        toast.show_at(anchor or parent, QPoint(parent.width() - toast.width() - 20, 20))
        return toast

    @classmethod
    def show_error(
        cls,
        parent: QWidget,
        message: str,
        anchor: Optional[QWidget] = None,
    ) -> "Toast":
        toast = cls(parent, message, icon="❌")
        toast.setProperty("state", "error")
        toast.show_at(anchor or parent, QPoint(parent.width() - toast.width() - 20, 20))
        return toast
