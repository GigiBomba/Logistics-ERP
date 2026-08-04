"""QtAlertPanel — PySide6 popup notification panel for the alert bell icon.

Replaces ``ui/widgets/alert_panel.py`` (CTkToplevel).

Usage::

    panel = QtAlertPanel(self, alerts, on_navigate=self._navigate)
    panel.show_anchored(self._bell)
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import TEXT_WHITE
from ui.design_tokens import (
    COLOR_ERROR_DEFAULT,
    COLOR_INFO_DEFAULT,
    COLOR_WARNING_DEFAULT,
    SP,
)

_SEVERITY_COLORS: dict[str, str] = {
    "CRITICAL": COLOR_ERROR_DEFAULT,
    "WARNING": COLOR_WARNING_DEFAULT,
}

_NAV_DESTINATIONS: dict[str, str] = {
    "trip_delay": "dispatch_board",
    "maintenance": "maintenance_control",
    "inspection": "maintenance_control",
    "insurance": "fleet",
    "overdue_invoice": "invoices",
    "inactive_truck": "fleet",
    "route_issue": "route_planner",
    "compliance_warning": "maintenance",
}

_ALERT_TYPES_WITH_TRIP = {
    "overdue_invoice", "trip_delay", "compliance_warning",
}


class QtAlertPanel(QFrame):
    """Popup alert panel anchored below the bell icon.

    Positioned via :meth:`show_anchored`. Displays up to 20 alerts sorted
    by ``created_at``, each with a severity chip, title, relative timestamp,
    navigation chevron, and a trash/clear-all button in the header.
    """

    MAX_WIDTH = 340
    MAX_HEIGHT = 420

    def __init__(
        self,
        parent: QWidget,
        alerts: list,
        on_navigate: Callable[[str, dict[str, Any] | None], None] | None = None,
        on_clear_all: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup)
        self.setProperty("role", "alert-panel")
        self.setFixedWidth(self.MAX_WIDTH)

        self._on_navigate = on_navigate
        self._on_clear_all = on_clear_all
        self._has_alerts = bool(alerts)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout)
        self._build_list(layout, alerts)

        # Size the panel to content height, capped at MAX_HEIGHT.
        self._apply_max_height()

    # ── Public API ──────────────────────────────────────────────────────────

    def show_anchored(self, anchor: QWidget) -> None:
        """Position the panel below ``anchor`` and show it."""
        if anchor is None:
            return
        global_pos = anchor.mapToGlobal(QPoint(0, 0))
        x = global_pos.x()
        y = global_pos.y() + anchor.height()
        # Prevent offscreen to the right
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            panel_width = self.width()
            if x + panel_width > screen_rect.right():
                x = screen_rect.right() - panel_width - 8
        self.move(x, y)
        self.show()
        self.raise_()
        self.setFocus()

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QWidget()
        header.setProperty("role", "alert-panel-header")
        header.setFixedHeight(42)

        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(SP["4"], 0, SP["2"], 0)
        hdr_layout.setSpacing(0)

        title = QLabel(t("alerts.panel_title"))
        title.setProperty("fontRole", "alert-panel-title")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch(1)

        # Clear-all (trash) button — only show when alerts exist
        if self._has_alerts and self._on_clear_all is not None:
            clear_btn = QLabel("\U0001F5D1")
            clear_btn.setToolTip(t("alerts.clear_all", default="Clear all alerts"))
            clear_btn.setProperty("role", "alert-panel-clear")
            clear_btn.setCursor(Qt.PointingHandCursor)
            clear_btn.setStyleSheet("font-size: 14px; padding: 0 4px;")
            clear_btn.mousePressEvent = lambda _: self._on_clear_all()  # type: ignore[assignment]
            hdr_layout.addWidget(clear_btn)

        close_btn = QLabel("\u2715")
        close_btn.setProperty("role", "alert-panel-close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.mousePressEvent = lambda _: self._close()  # type: ignore[assignment]
        hdr_layout.addWidget(close_btn)

        layout.addWidget(header)

    # ── List ────────────────────────────────────────────────────────────────

    def _build_list(self, layout: QVBoxLayout, alerts: list) -> None:
        scroll = QScrollArea()
        scroll.setProperty("role", "alert-panel-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setProperty("role", "alert-panel-list")
        list_layout = QVBoxLayout(content)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(2)
        list_layout.setAlignment(Qt.AlignTop)

        if not alerts:
            empty = QLabel(t("alerts.none_active"))
            empty.setProperty("fontRole", "alert-panel-empty")
            empty.setAlignment(Qt.AlignCenter)
            empty.setFixedHeight(120)
            list_layout.addWidget(empty)
        else:
            sorted_alerts = sorted(
                alerts,
                key=lambda a: getattr(a, "created_at", "") or "",
                reverse=True,
            )[:20]
            for alert in sorted_alerts:
                self._build_row(list_layout, alert)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    # ── Row ─────────────────────────────────────────────────────────────────

    def _build_row(self, layout: QVBoxLayout, alert) -> None:
        row = QFrame()
        row.setProperty("role", "alert-row")
        row.setCursor(Qt.PointingHandCursor)
        row.setFixedHeight(48)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SP["2"], 0, SP["3"], 0)
        row_layout.setSpacing(SP["2"])

        # -- Severity chip ---------------------------------------------------
        sev = str(getattr(alert.severity, "value", alert.severity)).upper()
        sev_color = _SEVERITY_COLORS.get(sev, COLOR_INFO_DEFAULT)
        sev_key = f"alerts.severity_{sev.lower()}"
        chip = QLabel(t(sev_key))
        chip.setProperty("role", "alert-chip")
        chip.setFixedSize(60, 22)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background-color: {sev_color}; color: {TEXT_WHITE};"
            f"border-radius: 4px; font-size: 11px; font-weight: bold;"
        )
        row_layout.addWidget(chip)

        # -- Text area -------------------------------------------------------
        text_widget = QWidget()
        text_widget.setProperty("role", "alert-row-text")
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        title_text = getattr(alert, "title", None) or getattr(alert, "message", "")
        title_label = QLabel(title_text)
        title_label.setProperty("fontRole", "alert-title")
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)

        time_label = QLabel(self._time_ago(getattr(alert, "created_at", None)))
        time_label.setProperty("fontRole", "alert-time")
        text_layout.addWidget(time_label)

        row_layout.addWidget(text_widget, 1)

        # -- Chevron ---------------------------------------------------------
        chevron = QLabel("\u203a")
        chevron.setProperty("role", "alert-chevron")
        row_layout.addWidget(chevron)

        # -- Click handling --------------------------------------------------
        row.mousePressEvent = lambda e, a=alert: self._go(a)  # type: ignore[assignment]
        chip.mousePressEvent = lambda e, a=alert: self._go(a)  # type: ignore[assignment]
        text_widget.mousePressEvent = lambda e, a=alert: self._go(a)  # type: ignore[assignment]

        layout.addWidget(row)

    # ── Navigation ──────────────────────────────────────────────────────────

    def _go(self, alert) -> None:
        self._close()
        alert_type = str(getattr(alert.type, "value", alert.type))
        destination = _NAV_DESTINATIONS.get(alert_type, "overview")
        nav_data: dict[str, Any] = {}
        if alert_type in _ALERT_TYPES_WITH_TRIP:
            trip_id = getattr(alert, "trip_id", None)
            if trip_id:
                nav_data["trip_id"] = int(trip_id) if str(trip_id).isdigit() else trip_id
        if self._on_navigate:
            self._on_navigate(destination, nav_data if nav_data else None)

    # ── Focus-out close ─────────────────────────────────────────────────────

    def focusOutEvent(self, event) -> None:
        """Close when focus moves outside this panel."""
        super().focusOutEvent(event)
        # Defer so any child click event propagates first.
        QTimer.singleShot(0, self._close)

    # ── Close ───────────────────────────────────────────────────────────────

    def _close(self) -> None:
        with contextlib.suppress(Exception):
            self.close()

    # ── Sizing helper ──────────────────────────────────────────────────────

    def _apply_max_height(self) -> None:
        """Cap panel height at MAX_HEIGHT based on actual content."""
        self.adjustSize()
        if self.height() > self.MAX_HEIGHT:
            self.setFixedHeight(self.MAX_HEIGHT)

    # ── Time helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _time_ago(dt_str: str | None) -> str:
        if not dt_str:
            return ""
        try:
            dt = datetime.fromisoformat(dt_str)
        except Exception:
            return ""
        now = datetime.now()
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return t("time.just_now")
        if secs < 3600:
            return t("time.minutes_ago", n=secs // 60)
        if secs < 86400:
            return t("time.hours_ago", n=secs // 3600)
        return t("time.days_ago", n=delta.days)
