"""InsightQueueWidget — review queue for proactive Co-Pilot insights.

Blueprint: §30 — Enterprise proactive insight review.
Renders a scrollable list of insight cards fetched from
``GET /copilot/insights``, with severity badges, action buttons,
and a status filter dropdown.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.copilot.models import Insight
from ui.design_tokens import (
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_TEXT,
    COLOR_INFO_DEFAULT,
    COLOR_NEUTRAL_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_PILL,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)
from ui.widgets import StyledComboBox

logger = logging.getLogger(__name__)

# Colour map for severity badges
_SEVERITY_STYLES: Dict[str, Dict[str, str]] = {
    "critical": {"bg": COLOR_ERROR_DEFAULT, "fg": "#FFFFFF"},
    "high":     {"bg": COLOR_WARNING_DEFAULT, "fg": "#000000"},
    "medium":   {"bg": COLOR_INFO_DEFAULT,    "fg": "#FFFFFF"},
    "low":      {"bg": COLOR_NEUTRAL_DEFAULT, "fg": "#FFFFFF"},
}

_TYPE_ICONS: Dict[str, str] = {
    "cost_anomaly":     "\U0001F4B0",
    "driver_alert":     "\U0001F6CD",
    "maintenance_due":  "\U0001F527",
    "overdue_invoice":  "\U0001F4C5",
    "fuel_trend":       "\u26FD",
    "return_load":      "\U0001F504",
    "fleet_availability": "\U0001F697",
}


def _format_timestamp(iso_str: Optional[str]) -> str:
    """Return a human-readable relative timestamp."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return iso_str[:16] if iso_str else ""

    now = datetime.now(timezone.utc)
    delta = now - dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return t("insight.time.just_now", default="just now")
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return t("insight.time.minutes_ago", default=f"{minutes}m ago", n=minutes)
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return t("insight.time.hours_ago", default=f"{hours}h ago", n=hours)
    days = total_seconds // 86400
    return t("insight.time.days_ago", default=f"{days}d ago", n=days)


def _summary_from_payload(payload: Dict[str, Any]) -> str:
    """Build a short summary string from the insight payload.

    Falls back to ``payload.get("message", "")`` or a joined list
    of values for known keys.
    """
    msg = payload.get("message", "") or payload.get("summary", "")
    if msg:
        return str(msg)
    # Fallback: join non-empty string values
    parts = [str(v) for v in payload.values() if isinstance(v, str) and v]
    return parts[0] if parts else ""


# ── Severity badge ──────────────────────────────────────────────────────────


class _SeverityBadge(QLabel):
    """Coloured pill badge showing the insight severity level."""

    def __init__(self, parent: QWidget, severity: str) -> None:
        super().__init__(parent)
        style = _SEVERITY_STYLES.get(severity, _SEVERITY_STYLES["low"])
        i18n_key = f"insight.severity.{severity}"
        display = t(i18n_key, default=severity.capitalize())
        self.setText(display)
        self.setFixedHeight(20)
        self.setStyleSheet(f"""
            background-color: {style['bg']};
            color: {style['fg']};
            border-radius: {RADIUS_PILL}px;
            padding: 0 {SPACE_2}px;
            font-size: {FONT_SIZE_XS}px;
            font-weight: {FONT_WEIGHT_MEDIUM};
        """)


# ── Insight card ────────────────────────────────────────────────────────────


class _InsightCard(QFrame):
    """Single insight row — badge, type, summary, timestamp, action buttons."""

    review_requested = Signal(object)   # Insight
    dismissed = Signal(object)          # Insight
    remind_later = Signal(object)       # Insight

    def __init__(self, parent: QWidget, insight: Insight) -> None:
        super().__init__(parent)
        self._insight = insight
        self.setProperty("role", "insight-card")
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        layout.setSpacing(SPACE_2)

        # ── Type icon ──────────────────────────────────────────────────
        icon_char = _TYPE_ICONS.get(insight.insight_type, "\U0001F4AC")
        icon_lbl = QLabel(icon_char, self)
        icon_lbl.setFixedWidth(24)
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        # ── Info column ────────────────────────────────────────────────
        info_col = QWidget(self)
        info_col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info_layout = QVBoxLayout(info_col)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Top row: severity badge + type label + timestamp
        top_row = QWidget(info_col)
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(SPACE_2)

        severity_badge = _SeverityBadge(top_row, insight.severity)
        top_row_layout.addWidget(severity_badge)

        type_key = f"insight.type.{insight.insight_type}"
        type_lbl = QLabel(t(type_key, default=insight.insight_type.replace("_", " ").title()), top_row)
        type_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px;")
        top_row_layout.addWidget(type_lbl)

        top_row_layout.addStretch()

        ts_lbl = QLabel(_format_timestamp(insight.created_at), top_row)
        ts_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px;")
        top_row_layout.addWidget(ts_lbl)

        info_layout.addWidget(top_row)

        # Summary line
        summary = _summary_from_payload(insight.payload)
        if summary:
            summary_lbl = QLabel(summary[:120], info_col)
            summary_lbl.setWordWrap(True)
            summary_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;")
            info_layout.addWidget(summary_lbl)

        layout.addWidget(info_col, 1)

        # ── Action buttons ─────────────────────────────────────────────
        actions = QWidget(self)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACE_1)

        review_btn = QPushButton(t("insight.action.review", default="Review"), actions)
        review_btn.setProperty("variant", "primary")
        review_btn.setFixedHeight(24)
        review_btn.clicked.connect(self._on_review)
        actions_layout.addWidget(review_btn)

        dismiss_btn = QPushButton(t("insight.action.dismiss", default="Dismiss"), actions)
        dismiss_btn.setProperty("variant", "ghost")
        dismiss_btn.setFixedHeight(24)
        dismiss_btn.clicked.connect(self._on_dismiss)
        actions_layout.addWidget(dismiss_btn)

        remind_btn = QPushButton("\u23F0", actions)
        remind_btn.setFixedWidth(28)
        remind_btn.setFixedHeight(24)
        remind_btn.setToolTip(t("insight.action.remind", default="Remind later"))
        remind_btn.clicked.connect(self._on_remind)
        actions_layout.addWidget(remind_btn)

        layout.addWidget(actions)

    # ── Signal emitters ─────────────────────────────────────────────────

    def _on_review(self) -> None:
        self.review_requested.emit(self._insight)

    def _on_dismiss(self) -> None:
        self.dismissed.emit(self._insight)

    def _on_remind(self) -> None:
        self.remind_later.emit(self._insight)


# ── Insight queue widget ────────────────────────────────────────────────────


class InsightQueueWidget(QFrame):
    """Review queue for proactive Co-Pilot insights.

    Displays a filterable, scrollable list of insight cards.
    Each card offers Review / Dismiss / Remind Later actions.

    Signals:
        review_requested(Insight): emitted when the user clicks Review.
    """

    review_requested = Signal(object)  # Insight

    FILTER_ALL = "all"
    FILTER_NEW = "new"
    FILTER_REVIEWED = "reviewed"

    def __init__(
        self,
        parent: QWidget | None = None,
        api_client: Any = None,
        controller: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("insight-queue")
        self._api_client = api_client
        self._controller = controller
        self._insights: List[Insight] = []
        self._active_filter: str = self.FILTER_ALL

        self.setStyleSheet(f"""
            #insight-queue {{
                background-color: {COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_LG}px;
            }}
        """)

        self._build_ui()

    # ── Public API ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Fetch insights from the backend and rebuild the list."""
        if self._api_client is None:
            logger.debug("InsightQueueWidget: no api_client, skipping refresh")
            return
        try:
            if not hasattr(self._api_client, '_get') and not hasattr(self._api_client, 'get'):
                logger.error("InsightQueueWidget: API client has no GET method")
                resp = {"items": [], "limit": 50}
            else:
                get_method = getattr(self._api_client, '_get', None) or getattr(self._api_client, 'get')
                resp = get_method(
                    "/api/v1/copilot/insights",
                    params={"limit": 50} if self._active_filter == self.FILTER_ALL
                    else {"limit": 50, "status_filter": self._active_filter},
                ) or {"items": [], "limit": 50}
        except Exception as exc:
            logger.warning("InsightQueueWidget: failed to fetch insights: %s", exc)
            resp = {"items": [], "limit": 50}

        raw_items: List[Dict[str, Any]] = resp.get("items", [])
        self._insights = [Insight(**item) for item in raw_items]
        self._rebuild_list()

    def set_filter(self, filter_value: str) -> None:
        """Change the active status filter and refresh."""
        self._active_filter = filter_value
        self.refresh()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_3, SPACE_3, SPACE_3, SPACE_3)
        layout.setSpacing(SPACE_3)

        # ── Header row: title + filter ─────────────────────────────────
        header_row = QWidget(self)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACE_2)

        title_lbl = QLabel(t("insight.title", default="Insights"), header_row)
        title_lbl.setStyleSheet(f"""
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: {FONT_WEIGHT_SEMIBOLD};
        """)
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self._filter_combo = StyledComboBox(
            header_row,
            values=[
                t("insight.filter_all",   default="All"),
                t("insight.filter_new",   default="New"),
                t("insight.filter_reviewed", default="Reviewed"),
            ],
        )
        self._filter_combo.setCurrentIndex(0)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        header_layout.addWidget(self._filter_combo)

        layout.addWidget(header_row)

        # ── Scrollable card list ───────────────────────────────────────
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; border: none; }}
        """)

        self._list_content = QWidget(self._scroll_area)
        self._list_layout = QVBoxLayout(self._list_content)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(SPACE_2)
        self._list_layout.setAlignment(Qt.AlignTop)

        self._scroll_area.setWidget(self._list_content)
        layout.addWidget(self._scroll_area, 1)

        # ── Empty state label (hidden by default) ──────────────────────
        self._empty_lbl = QLabel(
            t("insight.empty", default="No insights to review"), self
        )
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        self._empty_lbl.setVisible(False)
        layout.addWidget(self._empty_lbl)

    # ── List management ────────────────────────────────────────────────

    def _rebuild_list(self) -> None:
        """Clear and rebuild the card list from ``self._insights``."""
        # Clear existing cards
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._insights:
            self._scroll_area.setVisible(False)
            self._empty_lbl.setVisible(True)
            self.setVisible(False)
            return

        self._scroll_area.setVisible(True)
        self._empty_lbl.setVisible(False)
        self.setVisible(True)

        for insight in self._insights:
            card = _InsightCard(self._list_content, insight)
            card.review_requested.connect(self._on_card_review)
            card.dismissed.connect(self._on_card_dismiss)
            card.remind_later.connect(self._on_card_remind)
            self._list_layout.addWidget(card)

        self._list_layout.addStretch(1)

    # ── Filter handler ─────────────────────────────────────────────────

    def _on_filter_changed(self, text: str) -> None:
        all_label = t("insight.filter_all", default="All")
        new_label = t("insight.filter_new", default="New")
        reviewed_label = t("insight.filter_reviewed", default="Reviewed")

        if text == new_label:
            self._active_filter = self.FILTER_NEW
        elif text == reviewed_label:
            self._active_filter = self.FILTER_REVIEWED
        else:
            self._active_filter = self.FILTER_ALL
        self.refresh()

    # ── Card action handlers ───────────────────────────────────────────

    def _on_card_review(self, insight: Insight) -> None:
        self.review_requested.emit(insight)

    def _on_card_dismiss(self, insight: Insight) -> None:
        """Remove the insight from the list (client-side only)."""
        self._insights = [i for i in self._insights if i.id != insight.id]
        self._rebuild_list()

    def _on_card_remind(self, insight: Insight) -> None:
        """Placeholder: could reschedule or snooze the insight."""
        logger.info("Insight %s marked for remind-later", insight.id)
