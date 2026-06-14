"""Top bar widget for the PySide6 main window.

Replaces ``ui/widgets/top_bar.py``. Provides a breadcrumb label, a clock that
updates every 30 seconds, and an alert bell with a count badge.
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


class TopBar(QFrame):
    """48px top bar with breadcrumb, clock, and alert bell."""

    HEIGHT = 48

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("role", "top-bar")
        self.setFixedHeight(self.HEIGHT)

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
        row_layout.setContentsMargins(16, 0, 16, 0)
        row_layout.setSpacing(12)

        self._breadcrumb = QLabel("")
        self._breadcrumb.setProperty("role", "breadcrumb")
        row_layout.addWidget(self._breadcrumb)

        row_layout.addStretch(1)

        # Fuel status
        self._fuel_label = QLabel("")
        self._fuel_label.setProperty("role", "fuel-status")
        row_layout.addWidget(self._fuel_label)

        # Alert bell + badge
        alert_widget = QWidget()
        alert_layout = QHBoxLayout(alert_widget)
        alert_layout.setContentsMargins(0, 0, 0, 0)
        alert_layout.setSpacing(4)

        self._bell = QLabel("\U0001f514")  # 🔔
        self._bell.setProperty("role", "bell")
        self._bell.setCursor(Qt.PointingHandCursor)
        self._bell.setToolTip("Show alerts")
        self._bell.mousePressEvent = self._on_bell_clicked
        alert_layout.addWidget(self._bell)

        self._badge = QLabel("")
        self._badge.setProperty("role", "badge")
        self._badge.hide()
        alert_layout.addWidget(self._badge)

        row_layout.addWidget(alert_widget)

        self._clock = QLabel("")
        self._clock.setProperty("role", "clock")
        row_layout.addWidget(self._clock)

        layout.addWidget(row)

        # Bottom divider
        divider = QFrame()
        divider.setProperty("role", "top-bar-divider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        layout.addWidget(divider)

    def set_breadcrumb(self, text: str) -> None:
        self._breadcrumb.setText(text)

    def set_fuel_status(self, text: str) -> None:
        """Update the fuel status label in the top bar."""
        self._fuel_label.setText(text)

    def set_alert_count(self, count: int) -> None:
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.show()
            self._bell.setProperty("alert", "true")
        else:
            self._badge.hide()
            self._bell.setProperty("alert", "false")
        self._bell.style().unpolish(self._bell)
        self._bell.style().polish(self._bell)

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
