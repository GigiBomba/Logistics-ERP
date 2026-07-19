"""ThinkingIndicatorWidget — animated 3-dot "Thinking..." indicator.

Blueprint: §2.2. Uses QTimer to cycle dot opacity, creating a pulsing effect.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_SM,
    SPACE_1,
    SPACE_2,
)


class ThinkingIndicatorWidget(QWidget):
    """Animated "Thinking..." indicator with three pulsing dots.

    Public API:
        start() — begin animation
        stop()  — stop animation and hide
    """

    DOT_COUNT = 3
    INTERVAL_MS = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setVisible(False)

        self._dots: list[QLabel] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._frame = 0

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_2)

        # Thinking label
        label = QLabel(t("copilot.chat.thinking", default="Thinking…"))
        label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(label)

        # Three dots
        for i in range(self.DOT_COUNT):
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; "
                f"background: transparent; border: none;"
            )
            self._dots.append(dot)
            layout.addWidget(dot)

        layout.addStretch(1)

    def start(self) -> None:
        """Start the pulsing animation and show the widget."""
        self._frame = 0
        self.setVisible(True)
        self._timer.start(self.INTERVAL_MS)
        self._on_tick()

    def stop(self) -> None:
        """Stop the animation and hide the widget."""
        self._timer.stop()
        self.setVisible(False)
        # Reset all dots to full opacity
        for dot in self._dots:
            dot.setStyleSheet(
                f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; "
                f"background: transparent; border: none;"
            )

    def _on_tick(self) -> None:
        """Animate one frame: cycle which dot is at full opacity."""
        for i, dot in enumerate(self._dots):
            opacity = "FF" if i == self._frame % self.DOT_COUNT else "44"
            dot.setStyleSheet(
                f"color: rgba(142, 142, 160, {opacity}); "
                f"font-size: {FONT_SIZE_SM}px; "
                f"background: transparent; border: none;"
            )
        self._frame += 1
