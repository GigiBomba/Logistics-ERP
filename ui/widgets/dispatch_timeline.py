"""Gantt-like timeline for truck scheduling (PySide6).

Replaces ``ui/widgets/dispatch_timeline.py``. Displays a scrollable timeline
view showing each truck's trips as colour-coded bars grouped by plate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
from ui.components import EmptyState
from ui.theme import COLORS, S
from ui.widgets import ActionButton
from utils.dates import parse_date

# Status values that are considered terminal/finalised and should be hidden.
_DONE_STATUSES = frozenset({
    "Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced",
})

# Map trip status to chip colour token.
_STATUS_COLORS: dict[str, str] = {
    "Planned":   COLORS["chip_planned"],
    "Loading":   COLORS["chip_loading"],
    "In Transit": COLORS["chip_transit"],
}


class QtDispatchTimeline(QWidget):
    """Scrollable Gantt-like timeline of truck trips.

    Parameters
    ----------
    parent : QWidget or None
        Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("qtDispatchTimeline")

        # ── Scroll area ──────────────────────────────────────────────────
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── Content widget ───────────────────────────────────────────────
        self._content = QWidget()
        self._content.setObjectName("timelineContent")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        self._layout.setSpacing(S["1"])
        self._layout.setAlignment(Qt.AlignTop)

        self._scroll.setWidget(self._content)

        # Outer layout — scroll area fills the whole widget.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._scroll)

    # ── Public API ─────────────────────────────────────────────────────────

    def refresh(self, cards_data: list[dict[str, Any]] | None = None) -> None:
        """Rebuild the timeline from *cards_data*.

        Each dict in the list should contain (at minimum): ``truck_plate``,
        ``status``, ``trip_id``, ``departure_date``, and ``eta``.
        Trips whose status is in the done/cancelled set are filtered out.
        """
        self._clear()

        # ── Empty / no-data guard ────────────────────────────────────────
        active = list(self._filter_active(cards_data or []))

        if not active:
            self._show_empty_state()
            return

        # ── Now header ───────────────────────────────────────────────────
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        header_label = QLabel(
            f"{t('dispatch_board.timeline_now')}: {now_str}"
        )
        header_label.setProperty("fontRole", "accent")
        header_label.setContentsMargins(S["2"], 0, 0, 0)
        self._layout.addWidget(header_label)

        # ── Divider ──────────────────────────────────────────────────────
        divider = QFrame()
        divider.setProperty("role", "divider")
        divider.setFixedHeight(1)
        divider.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(divider)

        # ── Column headers ───────────────────────────────────────────────
        header_row = QFrame()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])
        header_layout.setSpacing(0)

        truck_header = QLabel(t("common.truck_label", default="Truck"))
        truck_header.setProperty("fontRole", "label")
        truck_header.setFixedWidth(120)
        header_layout.addWidget(truck_header)

        sched_header = QLabel(t("common.schedule_label", default="Schedule"))
        sched_header.setProperty("fontRole", "label")
        sched_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header_layout.addWidget(sched_header)

        self._layout.addWidget(header_row)

        # ── Group trips by truck plate ───────────────────────────────────
        trucks: dict[str, list[dict]] = {}
        for trip in active:
            plate = trip.get("truck_plate", "")
            if not plate:
                continue
            trucks.setdefault(plate, []).append(trip)

        # ── Per-truck rows ───────────────────────────────────────────────
        for plate in sorted(trucks.keys()):
            trips = trucks[plate]
            self._add_truck_row(plate, trips)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _clear(self) -> None:
        """Remove all widgets from the content layout."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _show_empty_state(self) -> None:
        cta = ActionButton(
            None,
            text=t("dispatch_board.timeline_plan_trip"),
            variant="primary",
        )
        empty = EmptyState(
            parent=self._content,
            icon_name="mdi6.calendar-month-outline",
            title=t("dispatch_board.timeline_no_data"),
            subtitle=t("dispatch_board.timeline_no_data_hint",
                      default="No trips scheduled for the selected period"),
            cta_button=cta,
        )
        self._layout.addWidget(empty)

    @staticmethod
    def _filter_active(cards_data: list[dict]) -> list[dict]:
        """Yield only non-terminal trips that have a truck plate."""
        return [
            cd for cd in cards_data
            if cd.get("status", "") not in _DONE_STATUSES
            and cd.get("truck_plate")
        ]

    def _add_truck_row(self, plate: str, trips: list[dict]) -> None:
        """Build a single truck row: plate label + trip bars."""
        row = QFrame()
        row.setProperty("role", "card")
        row.setContentsMargins(0, 0, 0, 0)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])
        row_layout.setSpacing(S["1"])

        # ── Truck plate label ────────────────────────────────────────────
        plate_label = QLabel(plate)
        plate_label.setProperty("fontRole", "mono")
        plate_label.setFixedWidth(120)
        plate_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row_layout.addWidget(plate_label)

        # ── Trip bars container ──────────────────────────────────────────
        bar_frame = QWidget()
        bar_frame.setContentsMargins(0, 0, 0, 0)
        bar_layout = QVBoxLayout(bar_frame)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(2)  # px gap between bars

        for trip in trips:
            self._add_trip_bar(bar_layout, trip)

        row_layout.addWidget(bar_frame, 1)

        self._layout.addWidget(row)

    def destroy(self) -> None:
        """Clear all widgets and schedule deletion."""
        self._clear()
        super().deleteLater()

    def _add_trip_bar(self, parent_layout: QVBoxLayout, trip: dict) -> None:
        """Append a single coloured trip bar to *parent_layout*."""
        trip_id = trip.get("trip_id", "")
        dep_raw = trip.get("departure_date", "")
        eta_raw = trip.get("eta", "")
        status = trip.get("status", "Planned")

        # Resolve colour.
        bar_color = _STATUS_COLORS.get(status, COLORS["chip_planned"])

        # Format the date range label.
        dep_dt = parse_date(dep_raw, "%d/%m/%Y")
        eta_dt = parse_date(eta_raw, "%d/%m/%Y")
        if dep_dt and eta_dt:
            dep_str = dep_dt.strftime("%d/%m %H:%M")
            eta_str = eta_dt.strftime("%d/%m %H:%M")
            label = f"{trip_id} ({dep_str} - {eta_str})"
        else:
            label = f"{trip_id} ({dep_raw} - {eta_raw})"

        # ── Bar frame ────────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(24)
        bar.setStyleSheet(
            f"background-color: {bar_color}; border-radius: 4px;"
        )

        bar_bar_layout = QHBoxLayout(bar)
        bar_bar_layout.setContentsMargins(S["2"], 0, S["2"], 0)
        bar_bar_layout.setSpacing(0)

        bar_label = QLabel(label)
        bar_label.setProperty("fontRole", "small")
        bar_label.setStyleSheet(
            f"background-color: transparent; color: {COLORS['text_primary']};"
        )
        bar_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        bar_bar_layout.addWidget(bar_label)

        parent_layout.addWidget(bar)
