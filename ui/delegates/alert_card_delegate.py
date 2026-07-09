"""AlertCardDelegate — QStyledItemDelegate that renders alert cards.

Each alert is rendered as a styled card with:
- Left accent border (color = severity)
- Icon + title + timestamp row
- Message body
- Reference badges (truck / trip)
- Action buttons (resolve, view trip, view truck, schedule maintenance)

Uses QStyleOptionViewItem and custom painting for efficient rendering
without creating 10+ child widgets per alert.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QStyledItemDelegate

from services.operations.alert_manager import Alert, AlertType, Severity
from ui.design_tokens import (
    BG_ELEVATED,
    BG_OVERLAY,
    BORDER_DEFAULT,
    DANGER,
    INFO,
    TEXT_MUTED,
    TEXT_WHITE,
    WARNING,
)
from ui.models.alert_list_model import AlertListModel

# ── Color palette ────────────────────────────────────────────────
_COLORS = {
    "critical": DANGER,
    "warning": WARNING,
    "info": INFO,
    "muted": TEXT_MUTED,
    "primary": TEXT_WHITE,
    "bg_card": BG_ELEVATED,
    "bg_section": BG_OVERLAY,
    "border": BORDER_DEFAULT,
}

# Per-severity accent colors
_SEV_COLORS = {
    Severity.CRITICAL: QColor("#ef4444"),
    Severity.WARNING: QColor("#f59e0b"),
    Severity.INFO: QColor("#3b82f6"),
}

# Alert type → icon character
_TYPE_ICONS = {
    AlertType.MAINTENANCE: "\u2699",
    AlertType.INSPECTION: "\u2611",
    AlertType.INSURANCE: "\u26E8",
    AlertType.OVERDUE_INVOICE: "\u20AC",
    AlertType.TRIP_DELAY: "\u23F1",
    AlertType.INACTIVE_TRUCK: "\u25CB",
    AlertType.ROUTE_ISSUE: "\u26A0",
    AlertType.COMPLIANCE_WARNING: "\u2696",
    AlertType.COMPLIANCE_RISK: "\u26A0",
    AlertType.TACHOGRAPH_EXPIRY: "\U0001F4BE",
    AlertType.DRIVER_HOURS_WEEKLY: "\u23F1",
    AlertType.DRIVER_HOURS_DAILY: "\u23F1",
    AlertType.DOCUMENT_EXPIRY: "\U0001F4C4",
    AlertType.CONTRACT_EXPIRY: "\U0001F4C4",
    AlertType.POLICY_VIOLATION: "\u26A0",
}

_CARD_HEIGHT = 140
_ACCENT_WIDTH = 3
_MARGIN = 8
_ROW_HEIGHT = 18


class AlertCardDelegate(QStyledItemDelegate):
    """Renders an Alert as a styled card with accent border, text, and refs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font_title = QFont("Segoe UI", 10, QFont.Bold)
        self._font_body = QFont("Segoe UI", 9)
        self._font_small = QFont("Segoe UI", 8)
        self._font_mono = QFont("Consolas", 9)

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), _CARD_HEIGHT)

    def paint(self, painter: QPainter, option, index):
        alert: Alert | None = index.data(AlertListModel.AlertRole)
        if alert is None:
            return

        rect = option.rect
        sev_color = _SEV_COLORS.get(alert.severity, QColor(_COLORS["muted"]))

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # ── Background ──────────────────────────────────────────
        painter.fillRect(rect, QColor(_COLORS["bg_card"]))

        # ── Left accent strip ───────────────────────────────────
        accent_rect = QRect(rect.left(), rect.top(), _ACCENT_WIDTH, rect.height())
        painter.fillRect(accent_rect, sev_color)

        # ── Content area ────────────────────────────────────────
        x = rect.left() + _ACCENT_WIDTH + _MARGIN
        y = rect.top() + _MARGIN
        w = rect.width() - _ACCENT_WIDTH - 2 * _MARGIN

        # Row 1: icon + title + timestamp
        icon = _TYPE_ICONS.get(alert.type, "\u2753")
        painter.setFont(self._font_title)
        painter.setPen(QColor(_COLORS["primary"]))
        painter.drawText(x, y, w - 100, _ROW_HEIGHT, Qt.AlignLeft | Qt.AlignVCenter,
                         f"{icon}  {alert.title}")

        ts = (alert.created_at or "")[:16].replace("T", " ")
        painter.setFont(self._font_small)
        painter.setPen(QColor(_COLORS["muted"]))
        painter.drawText(x + w - 100, y, 100, _ROW_HEIGHT,
                         Qt.AlignRight | Qt.AlignVCenter, ts)

        y += _ROW_HEIGHT + 4

        # Row 2: message (truncated to 2 lines)
        painter.setFont(self._font_body)
        painter.setPen(QColor(_COLORS["muted"]))
        msg = alert.message or ""
        # Simple truncation at ~120 chars
        if len(msg) > 120:
            msg = msg[:117] + "..."
        painter.drawText(x, y, w, _ROW_HEIGHT * 2, Qt.AlignLeft | Qt.TextWordWrap, msg)

        y += _ROW_HEIGHT * 2 + 4

        # Row 3: references
        refs = []
        if alert.truck_id:
            refs.append(f"\U0001F69A  Truck {alert.truck_id}")
        if alert.trip_id:
            refs.append(f"\U0001F4CB  Trip {alert.trip_id}")
        if refs:
            painter.setFont(self._font_small)
            painter.setPen(QColor(_COLORS["info"]))
            painter.drawText(x, y, w, _ROW_HEIGHT, Qt.AlignLeft, "  \u2022  ".join(refs))

        painter.restore()
