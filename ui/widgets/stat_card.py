"""StatCard widget — compact KPI metric card with label, value, and optional status dot."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QWidget

from ui.design_tokens import (
    COLOR_TEXT_PRIMARY,
    FONT_SIZE_SM,
    FONT_SIZE_3XL,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    SPACE_4,
    SPACE_5,
)


class StatCard(QFrame):
    """Compact 88px KPI card with label, value, and optional status dot."""

    STATUS_COLORS = {
        "good": "#22C55E",
        "warning": "#F59E0B",
        "critical": "#EF4444",
        "neutral": "#6366F1",
        "grey": "#6B7280",
        "blue": "#3B82F6",
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "",
        value: str = "",
        status_dot_color: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("stat-card")
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        self._dot: QLabel | None = None
        self._build_ui(label, value, status_dot_color)

    def _build_ui(self, label: str, value: str, dot_color: str | None) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_5, SPACE_4)
        layout.setVerticalSpacing(4)
        layout.setHorizontalSpacing(0)

        self._label_lbl = QLabel(label, self)
        self._label_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
            f"color: rgba(255,255,255,0.55); letter-spacing: 0.5px; "
            f"background: transparent;"
        )
        self._label_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._label_lbl, 0, 0, Qt.AlignLeft | Qt.AlignTop)

        self._value_lbl = QLabel(value, self)
        self._value_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_3XL}px; font-weight: {FONT_WEIGHT_BOLD}; "
            f"color: {COLOR_TEXT_PRIMARY}; background: transparent;"
        )
        self._value_lbl.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        layout.addWidget(self._value_lbl, 1, 0, 1, 2, Qt.AlignLeft | Qt.AlignBottom)

        if dot_color:
            dot = QLabel(self)
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f"background: {dot_color}; border-radius: 4px;")
            layout.addWidget(dot, 0, 1, Qt.AlignRight | Qt.AlignTop)
            self._dot = dot

        layout.setColumnStretch(0, 1)
        layout.setRowStretch(1, 1)

    @property
    def value_label(self) -> QLabel:
        return self._value_lbl

    def set_value(self, text: str) -> None:
        self._value_lbl.setText(text)

    def set_value_color(self, color: str) -> None:
        self._value_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_3XL}px; font-weight: {FONT_WEIGHT_BOLD}; "
            f"color: {color}; background: transparent;"
        )

    def set_label(self, text: str) -> None:
        self._label_lbl.setText(text)

    def set_status_dot(self, color: str | None) -> None:
        dot = self._dot
        if color:
            if dot is None:
                dot = QLabel(self)
                dot.setFixedSize(8, 8)
                self.layout().addWidget(dot, 0, 1, Qt.AlignRight | Qt.AlignTop)
                self._dot = dot
            dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
            dot.show()
        elif dot is not None:
            dot.hide()

    def enterEvent(self, event: QEnterEvent) -> None:
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)
