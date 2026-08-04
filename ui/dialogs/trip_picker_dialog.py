"""PySide6 trip picker dialog used by the Document Center.

When a user clicks "Link to trip…" on a document, this dialog
shows a list of recent trips so they can wire the document to
one.  It is intentionally minimal — there is no fuzzy
auto-match, no auto-attach, and no default selection: the user
must press "Link" to confirm.

The dialog is a thin wrapper around :class:`TripRepository`:
the caller passes the ``db`` and we fetch a recent slice of
trips on ``__init__`` and on every search keystroke.  For very
large fleets this is bounded by the ``limit`` argument.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from ui.components import EmptyState

from services.i18n import t
from ui.design_tokens import SP

logger = logging.getLogger(__name__)


class QtTripPickerDialog(QDialog):
    """Modal dialog that lets the user pick a single trip.

    Public API:
        ``exec()`` returns ``QDialog.Accepted`` if the user
        confirmed a selection, otherwise ``QDialog.Rejected``.
        ``selected_trip_id()`` returns the chosen trip_id, or
        ``None`` if the user closed without confirming.
    """

    def __init__(self, db: Any, parent: QWidget | None = None,
                 *, limit: int = 200) -> None:
        super().__init__(parent)
        self._db = db
        self._limit = limit
        self._selected: int | None = None

        self.setWindowTitle(t("docs.pick_trip_title", default="Pick a trip"))
        self.setAccessibleName("Select trip")
        self.setAccessibleDescription("Dialog for selecting a trip from a list")
        self.setMinimumSize(520, 420)
        self.setWindowModality(Qt.ApplicationModal)

        self._build_ui()
        self._load_trips("")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["2"])

        # Search row
        search_row = QHBoxLayout()
        search_lbl = QLabel(
            t("docs.pick_trip_search", default="Filter (origin, destination, plate):"),
            self,
        )
        search_row.addWidget(search_lbl)

        self._search_edit = QLineEdit(self)
        self._search_edit.setAccessibleName("Search trips")
        self._search_edit.setPlaceholderText(
            t("docs.pick_trip_placeholder", default="Type to filter…")
        )
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_edit, 1)
        layout.addLayout(search_row)

        # Trip list
        self._list = QListWidget(self)
        self._list.setAccessibleName("Trip list")
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        # Empty-state
        self._trip_picker_empty = EmptyState(
            parent=self,
            icon_name="fa5s.search",
            title=t("trip_picker.empty_title", "No trips available"),
            subtitle=t("trip_picker.empty_desc", "Create a trip first."),
        )
        self._trip_picker_empty.setVisible(False)
        layout.addWidget(self._trip_picker_empty)

        # Action row
        button_row = QHBoxLayout()
        button_row.addStretch()

        self._cancel_btn = QPushButton(
            t("common.cancel", default="Cancel"), self
        )
        self._cancel_btn.setAccessibleName("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self._cancel_btn)

        self._link_btn = QPushButton(
            t("docs.link_to_trip", default="Link to trip…"), self
        )
        self._link_btn.setAccessibleName("Link to trip")
        self._link_btn.setDefault(True)
        self._link_btn.setEnabled(False)
        self._link_btn.clicked.connect(self._on_link_clicked)
        button_row.addWidget(self._link_btn)

        layout.addLayout(button_row)

        # Set tab order: search → list → Cancel → Link
        self.setTabOrder(self._search_edit, self._list)
        self.setTabOrder(self._list, self._cancel_btn)
        self.setTabOrder(self._cancel_btn, self._link_btn)

        # Escape key dismisses (default QDialog behavior)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_trips(self, query: str) -> None:
        if self._db is None:
            logger.warning("Trip picker requires local database access - not available in remote mode")
            trips = []
            self._list.clear()
            self._list.setVisible(False)
            self._trip_picker_empty.setVisible(True)
            self._link_btn.setEnabled(False)
            self._selected = None
            return
        try:
            from repositories.trip_repository import TripRepository
            repo = TripRepository(self._db)
            trips: list[dict[str, Any]] = repo.get_all(limit=self._limit)
        except Exception:
            logger.exception("Failed to load trips for picker")
            trips = []

        q = (query or "").strip().lower()
        if q:
            trips = [
                t for t in trips
                if q in _trip_search_blob(t).lower()
            ]

        self._list.clear()
        for trow in trips:
            label, sub = _format_trip(trow)
            item = QListWidgetItem(f"{label}\n  {sub}")
            item.setData(Qt.UserRole, int(str(trow.get("id", 0) or 0)))
            self._list.addItem(item)

        has_items = self._list.count() > 0
        self._list.setVisible(has_items)
        self._trip_picker_empty.setVisible(not has_items)
        self._link_btn.setEnabled(False)
        self._selected = None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self._load_trips(text)

    def _on_selection_changed(self) -> None:
        items = self._list.selectedItems()
        self._link_btn.setEnabled(bool(items))
        if items:
            self._selected = int(items[0].data(Qt.UserRole) or 0)
        else:
            self._selected = None

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._selected = int(item.data(Qt.UserRole) or 0)
        self.accept()

    def _on_link_clicked(self) -> None:
        if self._selected is not None:
            self.accept()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def selected_trip_id(self) -> int | None:
        return self._selected


# ── Helpers ──────────────────────────────────────────────────────────


def _trip_search_blob(t: dict[str, Any]) -> str:
    """Return a single searchable string for a trip row."""
    parts: list[str] = []
    for key in (
        "id", "origin", "destination", "origin_city", "destination_city",
        "truck_plate", "driver_name", "client_name", "trip_number",
        "cmr_number", "status",
    ):
        v = t.get(key)
        if v is not None and v != "":
            parts.append(str(v))
    return " ".join(parts)


def _format_trip(t: dict[str, Any]) -> tuple:
    """Return ``(primary_label, sublabel)`` for a trip row."""
    tid = t.get("id", "?")
    origin = t.get("origin") or t.get("origin_city") or ""
    destination = t.get("destination") or t.get("destination_city") or ""
    primary = f"#{tid}  {origin} → {destination}" if origin and destination else f"#{tid}"
    sub_bits: list[str] = []
    if t.get("truck_plate"):
        sub_bits.append(str(t["truck_plate"]))
    if t.get("driver_name"):
        sub_bits.append(str(t["driver_name"]))
    if t.get("client_name"):
        sub_bits.append(str(t["client_name"]))
    if t.get("status"):
        sub_bits.append(str(t["status"]))
    if t.get("departure_date"):
        sub_bits.append(str(t["departure_date"]))
    return primary, "  •  ".join(sub_bits)
