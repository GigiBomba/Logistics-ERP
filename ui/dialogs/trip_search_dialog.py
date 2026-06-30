"""Trip search dialog for the automation pipeline's human verification stage.

Allows the user to search for a trip when the automation cannot auto-match.
Supports text filtering (client name, plate, driver, CMR number, origin,
destination) and optional date range filtering.

Usage::

    dlg = QtTripSearchDialog(db, parent=self)
    if dlg.exec() == QDialog.Accepted:
        trip_id = dlg.selected_trip_id()
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.theme import S

logger = logging.getLogger(__name__)

SEARCH_LIMIT = 200
DEFAULT_RANGE_DAYS = 90


class QtTripSearchDialog(QDialog):
    """Modal dialog that lets the user search for and pick a single trip.

    Public API:
        ``exec()`` returns ``QDialog.Accepted`` if the user confirmed a
        selection, otherwise ``QDialog.Rejected``.
        ``selected_trip_id()`` returns the chosen trip id, or ``None``.
    """

    def __init__(
        self,
        db: Any,
        parent: QWidget | None = None,
        *,
        limit: int = SEARCH_LIMIT,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._limit = limit
        self._selected: int | None = None

        self.setWindowTitle(t("docs.pick_trip_title", default="Search trips"))
        self.setMinimumSize(600, 480)
        self.setWindowModality(Qt.ApplicationModal)

        self._build_ui()
        self._load_trips()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        layout.setSpacing(S["2"])

        # Search row
        search_row = QHBoxLayout()
        search_lbl = QLabel(
            t("docs.pick_trip_search", default="Search:"),
            self,
        )
        search_row.addWidget(search_lbl)

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText(
            t("docs.pick_trip_placeholder",
              default="Client, plate, driver, CMR, origin, destination…")
        )
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_edit, 1)
        layout.addLayout(search_row)

        # Date range row
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel(t("docs.filter_date_range", default="Date range:"), self))
        self._from_date = QDateEdit(self)
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(
            datetime.now() - timedelta(days=DEFAULT_RANGE_DAYS)
        )
        self._from_date.dateChanged.connect(self._on_search_changed)
        date_row.addWidget(self._from_date)

        date_row.addWidget(QLabel("  →  ", self))
        self._to_date = QDateEdit(self)
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(datetime.now())
        self._to_date.dateChanged.connect(self._on_search_changed)
        date_row.addWidget(self._to_date)

        layout.addLayout(date_row)

        # Trip list
        self._list = QListWidget(self)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        # Empty-state label
        self._empty_lbl = QLabel(
            t("docs.pick_trip_empty", default="No trips match your filter."),
            self,
        )
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.hide()
        layout.addWidget(self._empty_lbl)

        # Action row
        button_row = QHBoxLayout()
        button_row.addStretch()

        self._cancel_btn = QPushButton(
            t("common.cancel", default="Cancel"), self,
        )
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._select_btn = QPushButton(
            t("docs.select_trip", default="Select"), self,
        )
        self._select_btn.setDefault(True)
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._on_select_clicked)
        button_row.addWidget(self._select_btn)

        layout.addLayout(button_row)

    # ── Data ──────────────────────────────────────────────────────────

    def _load_trips(self) -> None:
        from repositories.trip_repository import TripRepository
        repo = TripRepository(self._db)

        query = self._search_edit.text().strip().lower()
        from_date = self._from_date.date().toString("yyyy-MM-dd")
        to_date = self._to_date.date().toString("yyyy-MM-dd")

        try:
            if query:
                trips = repo.get_all(limit=self._limit)
            else:
                trips = repo.get_by_date_range(from_date, to_date) if hasattr(repo, 'get_by_date_range') else repo.get_all(limit=self._limit)
        except Exception:
            logger.exception("Failed to load trips")
            trips = []

        if query:
            trips = [t for t in trips if _trip_search_blob(t).lower().find(query) >= 0]

        # Filter by date range client-side for broader search.
        if query and from_date and to_date:
            with contextlib.suppress(Exception):
                trips = [
                    t for t in trips
                    if _trip_date_in_range(t, from_date, to_date)
                ]

        self._list.clear()
        for trow in trips[:self._limit]:
            label, sub = _format_trip(trow)
            item = QListWidgetItem(f"{label}\n  {sub}")
            item.setData(Qt.UserRole, int(trow.get("id") or 0))
            self._list.addItem(item)

        self._empty_lbl.setVisible(self._list.count() == 0)
        self._select_btn.setEnabled(False)
        self._selected = None

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_search_changed(self, text: str | None = None) -> None:
        self._load_trips()

    def _on_selection_changed(self) -> None:
        items = self._list.selectedItems()
        self._select_btn.setEnabled(bool(items))
        if items:
            self._selected = int(items[0].data(Qt.UserRole) or 0)
        else:
            self._selected = None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._selected = int(item.data(Qt.UserRole) or 0)
        self.accept()

    def _on_select_clicked(self) -> None:
        if self._selected is not None:
            self.accept()

    # ── Public ────────────────────────────────────────────────────────

    def selected_trip_id(self) -> int | None:
        return self._selected


# ── Helpers ──────────────────────────────────────────────────────────

def _trip_search_blob(t: dict[str, Any]) -> str:
    """Return a single searchable string for a trip row."""
    parts: list[str] = []
    for key in (
        "id", "origin", "destination", "origin_city", "destination_city",
        "truck_plate", "truck_number", "driver_name", "client_name",
        "cmr_number", "status",
    ):
        v = t.get(key)
        if v is not None and v != "":
            parts.append(str(v))
    return " ".join(parts)


def _trip_date_in_range(t: dict[str, Any], from_date: str, to_date: str) -> bool:
    """Check if a trip's start_date falls within [from_date, to_date]."""
    sd = t.get("start_date", "")
    if not sd or len(sd) < 10:
        return True  # no date → include
    trip_date = sd[:10]
    return from_date <= trip_date <= to_date


def _format_trip(t: dict[str, Any]) -> tuple:
    """Return ``(primary_label, sublabel)`` for a trip row."""
    tid = t.get("id", "?")
    origin = t.get("origin") or t.get("origin_city") or ""
    destination = t.get("destination") or t.get("destination_city") or ""
    primary = f"#{tid}  {origin} → {destination}" if origin and destination else f"#{tid}"
    sub_bits: list[str] = []
    if t.get("truck_plate") or t.get("truck_number"):
        sub_bits.append(str(t.get("truck_plate") or t.get("truck_number")))
    if t.get("driver_name"):
        sub_bits.append(str(t["driver_name"]))
    if t.get("client_name"):
        sub_bits.append(str(t["client_name"]))
    if t.get("status"):
        sub_bits.append(str(t["status"]))
    if t.get("start_date"):
        sub_bits.append(str(t["start_date"])[:10])
    return primary, "  •  ".join(sub_bits)
