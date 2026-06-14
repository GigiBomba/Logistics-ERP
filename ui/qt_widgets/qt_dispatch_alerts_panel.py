"""PySide6 dispatch alerts panel: KPIs, alerts, unassigned trips, assignment summary.

Replaces ``ui/widgets/dispatch_alerts_panel.py`` (CTkFrame).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from services.operations.alert_manager import Severity
from ui.theme import COLORS, S
from ui.qt_widgets import ActionButton, KpiCard

# Terminal statuses that are excluded from KPI and unassigned counts.
_DONE_STATUSES = frozenset({
    "Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced",
})


class QtDispatchAlertsPanel(QWidget):
    """Combined panel showing: active alerts, unassigned trips, assignment summary.

    Parameters
    ----------
    parent : QWidget or None
        Parent widget.
    db : optional
        Database handle.
    ops : optional
        Operations engine instance providing ``get_alerts``, ``get_active_alerts``,
        and ``resolve_alert``.
    on_assign_truck : callable or None
        Called with the trip dict when "Quick Assign" is triggered for a missing truck.
    on_assign_driver : callable or None
        Called with the trip dict when "Quick Assign" is triggered for a missing driver.
    on_resolve_alert : callable or None
        Called after an alert is resolved (no arguments).
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        ops=None,
        on_assign_truck: Optional[Callable] = None,
        on_assign_driver: Optional[Callable] = None,
        on_resolve_alert: Optional[Callable] = None,
    ):
        super().__init__(parent)
        self._db = db
        self._ops = ops
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._on_resolve_alert = on_resolve_alert

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Scroll area ──────────────────────────────────────────────────
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── Content widget ───────────────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        content_layout.setSpacing(S["3"])
        content_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(content)

        # Outer layout — scroll area fills the whole panel.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

        # ── Four card sections ───────────────────────────────────────────
        self._brief_content = self._build_card_section(
            content_layout, "dispatch_board.brief_title", has_resolve_all=False,
        )
        self._alerts_content = self._build_card_section(
            content_layout, "dispatch_board.alerts_panel_title", has_resolve_all=True,
        )
        self._unassigned_content = self._build_card_section(
            content_layout, "dispatch_board.alerts_panel_unassigned_title",
            has_resolve_all=True,
        )
        self._summary_content = self._build_card_section(
            content_layout, "dispatch_board.alerts_panel_summary_title",
            has_resolve_all=False,
        )

    def _build_card_section(
        self,
        parent_layout: QVBoxLayout,
        title_key: str,
        has_resolve_all: bool = False,
    ) -> QVBoxLayout:
        """Build a card section with a header row and return the inner content layout.

        The card is a ``QFrame[role="card"]``.  The header contains the translated
        title and, when *has_resolve_all* is ``True``, a ghost "Resolve All" button
        on the right.  Callers add content widgets to the returned layout.
        """
        card = QFrame()
        card.setProperty("role", "card")
        card.setFrameShape(QFrame.StyledPanel)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(S["4"], S["3"], S["4"], S["3"])
        card_layout.setSpacing(S["2"])

        # Header row
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(S["2"])

        title_lbl = QLabel(t(title_key))
        title_lbl.setProperty("fontRole", "h3")
        header_layout.addWidget(title_lbl)

        if has_resolve_all:
            header_layout.addStretch()
            resolve_btn = ActionButton(
                header,
                text=t("dispatch_board.alerts_panel_resolve_all"),
                command=self._resolve_all_alerts,
                variant="ghost",
            )
            resolve_btn.setFixedHeight(24)
            header_layout.addWidget(resolve_btn)

        card_layout.addWidget(header)

        # Inner content container
        content = QWidget()
        inner_layout = QVBoxLayout(content)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(S["2"])
        card_layout.addWidget(content)

        parent_layout.addWidget(card)
        return inner_layout

    # ── Public API ───────────────────────────────────────────────────────────

    def refresh(self, cards_data: Optional[list[dict[str, Any]]] = None) -> None:
        """Rebuild all four sections from *cards_data*.

        Each dict should contain (at minimum) ``status``, ``departure_date``,
        ``eta``, ``truck_plate``, ``driver_name``, ``trip_id``, ``origin``,
        and ``destination``.
        """
        data = cards_data or []
        self._refresh_brief(data)
        self._refresh_alerts()
        self._refresh_unassigned(data)
        self._refresh_summary(data)

    # ── Brief KPIs ───────────────────────────────────────────────────────────

    def _refresh_brief(self, cards_data: list[dict[str, Any]]) -> None:
        self._clear_layout(self._brief_content)

        today_str = datetime.now().strftime("%d/%m/%Y")
        departing = 0
        arriving = 0
        needs_attention = 0

        for cd in cards_data:
            status = cd.get("status", "")
            if status in _DONE_STATUSES:
                continue
            dep = cd.get("departure_date", "")
            eta = cd.get("eta", "")
            if dep and dep[:10] == today_str:
                departing += 1
            if eta and eta[:10] == today_str:
                arriving += 1
            has_truck = bool(cd.get("truck_plate"))
            has_driver = bool(cd.get("driver_name"))
            if not has_truck or not has_driver:
                needs_attention += 1

        critical_count = 0
        if self._ops:
            try:
                alerts = self._ops.get_alerts(
                    severity=Severity.CRITICAL, resolved=False, limit=50,
                )
                critical_count = len(alerts)
            except Exception:
                pass

        kpis: list[tuple[str, int, str]] = [
            ("dispatch_board.brief_departing_today", departing, COLORS["accent"]),
            ("dispatch_board.brief_arriving_today", arriving, COLORS["success"]),
            (
                "dispatch_board.brief_critical",
                critical_count,
                COLORS["danger"] if critical_count else COLORS["text_muted"],
            ),
            (
                "dispatch_board.brief_needs_attention",
                needs_attention,
                COLORS["warning"] if needs_attention else COLORS["text_muted"],
            ),
        ]

        kpi_row = QWidget()
        kpi_row_layout = QHBoxLayout(kpi_row)
        kpi_row_layout.setContentsMargins(0, 0, 0, 0)
        kpi_row_layout.setSpacing(S["2"])

        for key, val, color in kpis:
            card_widget = KpiCard(kpi_row, t(key), str(val))
            card_widget.value_label.setStyleSheet(f"color: {color};")
            kpi_row_layout.addWidget(card_widget, 1)

        self._brief_content.addWidget(kpi_row)

    # ── Alerts ───────────────────────────────────────────────────────────────

    def _refresh_alerts(self) -> None:
        self._clear_layout(self._alerts_content)

        if not self._ops:
            label = QLabel("Ops not available")
            label.setProperty("fontRole", "muted")
            label.setAlignment(Qt.AlignCenter)
            self._alerts_content.addWidget(label)
            return

        alerts = self._ops.get_active_alerts(limit=20)
        if not alerts:
            label = QLabel(t("dispatch_board.alerts_panel_no_alerts"))
            label.setProperty("fontRole", "muted")
            label.setAlignment(Qt.AlignCenter)
            self._alerts_content.addWidget(label)
            return

        for alert in alerts:
            self._draw_alert_row(alert)

    def _draw_alert_row(self, alert) -> None:
        sev_colors: dict[str, str] = {
            "critical": COLORS["danger"],
            "warning": COLORS["warning"],
            "info": COLORS["info"],
        }
        sev = str(getattr(alert.severity, "value", alert.severity)).lower()
        chip_color = sev_colors.get(sev, COLORS["info"])

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

        # Severity chip
        chip = QLabel(sev.upper()[:3])
        chip.setFixedWidth(36)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background-color: {chip_color}; color: #ffffff; "
            f"border-radius: 3px; padding: 2px 0; font-size: 11px; font-weight: bold;"
        )
        row_layout.addWidget(chip)

        # Message text
        text = getattr(alert, "title", "") or getattr(alert, "message", "")
        msg_lbl = QLabel(text[:60])
        msg_lbl.setProperty("fontRole", "secondary")
        msg_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(msg_lbl, 1)

        # Resolve button
        resolve_btn = ActionButton(
            row,
            text="\u2713",
            command=lambda a=alert: self._resolve_alert_row(a),
            variant="ghost",
        )
        resolve_btn.setFixedSize(22, 22)
        row_layout.addWidget(resolve_btn)

        self._alerts_content.addWidget(row)

    def _resolve_alert_row(self, alert) -> None:
        if self._ops:
            self._ops.resolve_alert(alert.id)
        if self._on_resolve_alert:
            self._on_resolve_alert()

    def _resolve_all_alerts(self) -> None:
        if not self._ops:
            return
        alerts = self._ops.get_active_alerts(limit=100)
        for alert in alerts:
            self._ops.resolve_alert(alert.id)
        if self._on_resolve_alert:
            self._on_resolve_alert()

    # ── Unassigned trips ─────────────────────────────────────────────────────

    def _refresh_unassigned(self, cards_data: list[dict[str, Any]]) -> None:
        self._clear_layout(self._unassigned_content)

        no_truck: list[dict[str, Any]] = []
        no_driver: list[dict[str, Any]] = []
        no_both: list[dict[str, Any]] = []

        for cd in cards_data:
            has_truck = bool(cd.get("truck_plate"))
            has_driver = bool(cd.get("driver_name"))
            status = cd.get("status", "")
            if status in _DONE_STATUSES:
                continue
            if not has_truck and not has_driver:
                no_both.append(cd)
            elif not has_truck:
                no_truck.append(cd)
            elif not has_driver:
                no_driver.append(cd)

        all_unassigned = no_truck + no_driver + no_both
        if not all_unassigned:
            label = QLabel(t("dispatch_board.alerts_panel_no_unassigned"))
            label.setProperty("fontRole", "success")
            label.setAlignment(Qt.AlignCenter)
            self._unassigned_content.addWidget(label)
            return

        if no_truck:
            self._draw_unassigned_group("dispatch_board.alerts_panel_no_truck", no_truck)
        if no_driver:
            self._draw_unassigned_group("dispatch_board.alerts_panel_no_driver", no_driver)
        if no_both:
            self._draw_unassigned_group("dispatch_board.alerts_panel_neither", no_both)

    def _draw_unassigned_group(
        self,
        title_key: str,
        items: list[dict[str, Any]],
    ) -> None:
        grp = QWidget()
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(0, 0, 0, 0)
        grp_layout.setSpacing(S["1"])

        # Group title
        title_lbl = QLabel(t(title_key))
        title_lbl.setProperty("fontRole", "warning")
        grp_layout.addWidget(title_lbl)

        for item in items[:5]:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(S["2"])

            trip_id = item.get("trip_id", "")
            origin = item.get("origin", "?")
            dest = item.get("destination", "?")
            route = f"{trip_id}: {origin}\u2192{dest}"

            route_lbl = QLabel(route[:50])
            route_lbl.setProperty("fontRole", "secondary")
            route_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            row_layout.addWidget(route_lbl, 1)

            assign_btn = ActionButton(
                row,
                text=t("dispatch_board.alerts_panel_quick_assign"),
                command=lambda i=item: self._quick_assign(i),
                variant="primary",
            )
            assign_btn.setFixedHeight(20)
            assign_btn.setFixedWidth(70)
            row_layout.addWidget(assign_btn)

            grp_layout.addWidget(row)

        if len(items) > 5:
            more_lbl = QLabel(f"... +{len(items) - 5} more")
            more_lbl.setProperty("fontRole", "muted")
            grp_layout.addWidget(more_lbl)

        self._unassigned_content.addWidget(grp)

    def _quick_assign(self, item: dict[str, Any]) -> None:
        if self._on_assign_truck and not item.get("truck_plate"):
            self._on_assign_truck(item)
        if self._on_assign_driver and not item.get("driver_name"):
            self._on_assign_driver(item)

    # ── Summary KPIs ─────────────────────────────────────────────────────────

    def _refresh_summary(self, cards_data: list[dict[str, Any]]) -> None:
        self._clear_layout(self._summary_content)

        total_active = 0
        fully_assigned = 0
        partial = 0
        unassigned = 0

        for cd in cards_data:
            status = cd.get("status", "")
            if status in _DONE_STATUSES:
                continue
            total_active += 1
            has_truck = bool(cd.get("truck_plate"))
            has_driver = bool(cd.get("driver_name"))
            if has_truck and has_driver:
                fully_assigned += 1
            elif has_truck or has_driver:
                partial += 1
            else:
                unassigned += 1

        kpis: list[tuple[str, int, str]] = [
            ("dispatch_board.alerts_panel_total_trips", total_active, COLORS["text_primary"]),
            ("dispatch_board.alerts_panel_fully_assigned", fully_assigned, COLORS["success"]),
            ("dispatch_board.alerts_panel_partial", partial, COLORS["warning"]),
            (
                "dispatch_board.alerts_panel_unassigned",
                unassigned,
                COLORS["danger"] if unassigned else COLORS["text_muted"],
            ),
        ]

        kpi_row = QWidget()
        kpi_row_layout = QHBoxLayout(kpi_row)
        kpi_row_layout.setContentsMargins(0, 0, 0, 0)
        kpi_row_layout.setSpacing(S["2"])

        for key, val, color in kpis:
            card_widget = KpiCard(kpi_row, t(key), str(val))
            card_widget.value_label.setStyleSheet(f"color: {color};")
            kpi_row_layout.addWidget(card_widget, 1)

        self._summary_content.addWidget(kpi_row)

    # ── Layout helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        """Remove and delete all items from *layout*."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                QtDispatchAlertsPanel._clear_layout(item.layout())
