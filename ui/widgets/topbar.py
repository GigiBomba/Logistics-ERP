"""Top bar widget for the PySide6 main window.

Replaces ui/widgets/top_bar.py. Provides clock, alert bell, fuel status, and navigation controls.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any, Callable

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    BORDER_DEFAULT,
    BTN_HEIGHT_SM,
    COLOR_ACCENT_PRIMARY,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_SECONDARY,
    DANGER,
    FONT_MONO,
    FONT_SIZE_LG,
    FONT_SIZE_SM,
    SUCCESS,
    TEXT_MUTED,
    TOPBAR_HEIGHT,
)

class TopBar(QFrame):
    """44px top bar with clock, alert bell, fuel status, and navigation controls."""

    back_clicked = Signal()
    recent_clicked = Signal(str)
    report_issue_clicked = Signal()

    def __init__(self, parent: QWidget | None = None, ops=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(TOPBAR_HEIGHT)
        self._ops = ops

        self._alert_dialog = None
        self._alerts_data: list = []
        self._on_navigate: Callable[[str, dict[str, Any] | None], None] | None = None

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

        # Back button (hidden until nav stack has history)
        self._back_btn = QPushButton()
        self._back_btn.setIcon(qta.icon("fa5s.arrow-left", color=COLOR_TEXT_SECONDARY))
        self._back_btn.setFixedSize(BTN_HEIGHT_SM, BTN_HEIGHT_SM)
        self._back_btn.setStyleSheet(f"min-height: {BTN_HEIGHT_SM}px; max-height: {BTN_HEIGHT_SM}px; padding: 0px;")
        self._back_btn.setAccessibleName("Go back")
        self._back_btn.setToolTip(t("nav.back", default="Back (Alt+Left)"))
        self._back_btn.setProperty("variant", "ghost")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setVisible(False)
        self._back_btn.clicked.connect(self.back_clicked.emit)
        row_layout.addWidget(self._back_btn)

        # Recent button (hidden until nav stack has items)
        self._recent_btn = QPushButton()
        self._recent_btn.setIcon(qta.icon("fa5s.clock", color=COLOR_TEXT_SECONDARY))
        self._recent_btn.setText(t("nav.recent", default="Recent"))
        self._recent_btn.setToolTip(t("nav.recent_tooltip", default="Recently viewed pages"))
        self._recent_btn.setProperty("variant", "ghost")
        self._recent_btn.setCursor(Qt.PointingHandCursor)
        self._recent_btn.setFixedHeight(BTN_HEIGHT_SM)
        self._recent_btn.setStyleSheet(f"min-height: {BTN_HEIGHT_SM}px; max-height: {BTN_HEIGHT_SM}px; padding: 0px;")
        self._recent_btn.setVisible(False)
        row_layout.addWidget(self._recent_btn)

        row_layout.addStretch(1)

        # Subtle vertical separator before the right section
        sep_before = QFrame()
        sep_before.setFrameShape(QFrame.VLine)
        sep_before.setFixedSize(1, 20)
        sep_before.setStyleSheet(f"background: {COLOR_BORDER_SUBTLE}; max-width: 1px; min-width: 1px;")
        row_layout.addWidget(sep_before)

        # Fuel status dot
        self._fuel_dot = QLabel()
        self._fuel_dot.setFixedSize(8, 8)
        self._fuel_dot.setStyleSheet(
            f"background: {DANGER}; border-radius: 4px;"
        )
        self._fuel_dot.setToolTip(t("fuel.updated_tooltip", default="Fuel prices updated ? ago"))
        row_layout.addWidget(self._fuel_dot)

        # Alert bell + badge
        alert_widget = QWidget()
        alert_layout = QHBoxLayout(alert_widget)
        alert_layout.setContentsMargins(0, 0, 0, 0)
        alert_layout.setSpacing(4)

        self._bell = QLabel()
        self._bell.setPixmap(qta.icon("fa5s.bell", color=TEXT_MUTED).pixmap(16, 16))
        self._bell.setAccessibleName("Notifications")
        self._bell.setCursor(Qt.PointingHandCursor)
        self._bell.setToolTip(t("common.show_alerts", default="Show alerts"))
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

        # Report Issue button - placeholder
        self._report_issue_btn = QPushButton()
        self._report_issue_btn.setIcon(
            qta.icon("fa5s.bug", color=TEXT_MUTED),
        )
        self._report_issue_btn.setFixedSize(BTN_HEIGHT_SM, BTN_HEIGHT_SM)
        self._report_issue_btn.setStyleSheet(f"min-height: {BTN_HEIGHT_SM}px; max-height: {BTN_HEIGHT_SM}px; padding: 0px;")
        self._report_issue_btn.setAccessibleName("Report Issue")
        self._report_issue_btn.setToolTip(
            t("report_issue.button_tooltip", default="Report an Issue"),
        )
        self._report_issue_btn.setProperty("variant", "ghost")
        self._report_issue_btn.setCursor(Qt.PointingHandCursor)
        self._report_issue_btn.clicked.connect(self.report_issue_clicked.emit)
        row_layout.addWidget(self._report_issue_btn)

        # Separator
        sep = QFrame()
        sep.setFixedSize(1, 16)
        sep.setStyleSheet(f"background: {BORDER_DEFAULT};")
        row_layout.addWidget(sep)

        # Clock
        self._clock = QLabel("")
        self._clock.setAccessibleName("Current time")
        self._clock.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: '{FONT_MONO}'; font-size: {FONT_SIZE_SM}px; background: transparent;"
        )
        row_layout.addWidget(self._clock)

        layout.addWidget(row)

    def set_fuel_status(self, text: str) -> None:
        """Update the fuel status tooltip and dot color."""
        self._fuel_dot.setToolTip(text)
        # Simple heuristic: if text contains "offline" or "?", show red, else green
        lower = text.lower()
        if "offline" in lower or "?" in lower:
            self._fuel_dot.setStyleSheet(f"background: {DANGER}; border-radius: 4px;")
        else:
            self._fuel_dot.setStyleSheet(f"background: {SUCCESS}; border-radius: 4px;")

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

    def set_alert_navigate_callback(self, callback: Callable[[str, dict[str, Any] | None], None]) -> None:
        self._on_navigate = callback

    def set_back_enabled(self, enabled: bool) -> None:
        """Show or hide the back navigation button."""
        self._back_btn.setVisible(enabled)

    def _update_recent_menu(self, recent_items: list[tuple[str, str]]) -> None:
        """Update recent dropdown. Each tuple: (view_key, display_name)."""
        self._recent_btn.setVisible(len(recent_items) > 0)
        if not recent_items:
            return
        menu = QMenu(self)
        for view_key, name in recent_items[-5:]:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, vk=view_key: self.recent_clicked.emit(vk))
            menu.addAction(action)
        self._recent_btn.setMenu(menu)

    def _update_clock(self) -> None:
        self._clock.setText(datetime.now().strftime("%H:%M"))

    def _on_bell_clicked(self, event) -> None:
        from ui.widgets.alert_panel import QtAlertPanel

        if self._alert_dialog is not None:
            with contextlib.suppress(Exception):
                self._alert_dialog.close()
            self._alert_dialog = None

        alerts = getattr(self, "_alerts_data", [])

        def _clear_all():
            ops = self._ops
            if ops is not None:
                active = ops.get_active_alerts(limit=500)
                for a in active:
                    with contextlib.suppress(Exception):
                        ops.resolve_alert(a.id)
            self._alert_dialog = None

        panel = QtAlertPanel(self, alerts, on_navigate=self._on_navigate, on_clear_all=_clear_all)
        self._alert_dialog = panel
        panel.show_anchored(self._bell)

    def destroy(self) -> None:
        if self._clock_timer is not None:
            self._clock_timer.stop()
        super().deleteLater()
