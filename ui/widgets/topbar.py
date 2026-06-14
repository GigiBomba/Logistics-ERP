"""Top bar widget for the PySide6 main window.

Replaces ui/widgets/top_bar.py. Provides breadcrumb, clock, alert bell, and fuel status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
)

import qtawesome as qta

from ui.design_tokens import (
    BG_BASE, BORDER_DEFAULT, ACCENT, DANGER, SUCCESS,
    TEXT_PRIMARY, TEXT_MUTED, TEXT_SECONDARY,
    FONT_MONO, TOPBAR_HEIGHT, SP,
)


class TopBar(QFrame):
    """44px top bar with breadcrumb, clock, alert bell, and fuel status."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(TOPBAR_HEIGHT)

        self._alert_dialog = None
        self._alerts_data: list = []
        self._on_navigate: Optional[Callable[[str], None]] = None

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(30_000)

        self._build()
        self._update_clock()
        self.set_alert_count(0)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top row
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 0, 16, 0)
        row_layout.setSpacing(8)

        # Breadcrumb
        self._breadcrumb = QLabel("")
        self._breadcrumb.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 600; background: transparent;"
        )
        row_layout.addWidget(self._breadcrumb)

        row_layout.addStretch(1)

        # Fuel status dot
        self._fuel_dot = QLabel()
        self._fuel_dot.setFixedSize(6, 6)
        self._fuel_dot.setStyleSheet(
            f"background: {DANGER}; border-radius: 3px;"
        )
        self._fuel_dot.setToolTip("Fuel prices updated ? ago")
        row_layout.addWidget(self._fuel_dot)

        # Alert bell + badge
        alert_widget = QWidget()
        alert_layout = QHBoxLayout(alert_widget)
        alert_layout.setContentsMargins(0, 0, 0, 0)
        alert_layout.setSpacing(4)

        self._bell = QLabel()
        self._bell.setPixmap(qta.icon("fa5s.bell", color=TEXT_MUTED).pixmap(16, 16))
        self._bell.setCursor(Qt.PointingHandCursor)
        self._bell.setToolTip("Show alerts")
        self._bell.mousePressEvent = self._on_bell_clicked
        alert_layout.addWidget(self._bell)

        self._badge = QLabel("")
        self._badge.setStyleSheet(
            f"background: {DANGER}; color: white; border-radius: 8px; "
            f"font-size: 10px; font-weight: 600; min-width: 16px; max-width: 16px; "
            f"min-height: 16px; max-height: 16px; qproperty-alignment: AlignCenter;"
        )
        self._badge.hide()
        alert_layout.addWidget(self._badge)

        row_layout.addWidget(alert_widget)

        # Separator
        sep = QFrame()
        sep.setFixedSize(1, 16)
        sep.setStyleSheet(f"background: {BORDER_DEFAULT};")
        row_layout.addWidget(sep)

        # Clock
        self._clock = QLabel("")
        self._clock.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_MONO}'; font-size: 13px; background: transparent;"
        )
        row_layout.addWidget(self._clock)

        layout.addWidget(row)

    def set_breadcrumb(self, text: str) -> None:
        self._breadcrumb.setText(text)

    def set_fuel_status(self, text: str) -> None:
        """Update the fuel status tooltip and dot color."""
        self._fuel_dot.setToolTip(text)
        # Simple heuristic: if text contains "offline" or "?", show red, else green
        lower = text.lower()
        if "offline" in lower or "?" in lower:
            self._fuel_dot.setStyleSheet(f"background: {DANGER}; border-radius: 3px;")
        else:
            self._fuel_dot.setStyleSheet(f"background: {SUCCESS}; border-radius: 3px;")

    def set_alert_count(self, count: int) -> None:
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.show()
            self._bell.setPixmap(qta.icon("fa5s.bell", color=DANGER).pixmap(16, 16))
        else:
            self._badge.hide()
            self._bell.setPixmap(qta.icon("fa5s.bell", color=TEXT_MUTED).pixmap(16, 16))

    def set_alerts(self, alerts: list) -> None:
        """Store alerts data for display when the bell is clicked."""
        self._alerts_data = alerts

    def set_alert_navigate_callback(self, callback: Callable[[str], None]) -> None:
        self._on_navigate = callback

    def _update_clock(self) -> None:
        self._clock.setText(datetime.now().strftime("%H:%M"))

    def _on_bell_clicked(self, event) -> None:
        from ui.widgets.alert_panel import QtAlertPanel

        if self._alert_dialog is not None:
            try:
                self._alert_dialog.close()
            except Exception:
                pass
            self._alert_dialog = None

        alerts = getattr(self, "_alerts_data", [])
        panel = QtAlertPanel(self, alerts, on_navigate=self._on_navigate)
        self._alert_dialog = panel
        panel.show_anchored(self._bell)

    def destroy(self) -> None:
        if self._clock_timer is not None:
            self._clock_timer.stop()
        super().deleteLater()
