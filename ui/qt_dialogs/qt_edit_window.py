"""PySide6 edit-trip dialog.

Replaces ``ui.edit_window.EditWindow`` (CTkToplevel) with a modal QDialog
that uses the Qt widget toolkit from ``ui.qt_widgets``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from services.trip_service import TripService
from ui.theme import COLORS, S
from ui.qt_widgets import ActionButton, ScrollableFormContainer, StyledLineEdit, field


class QtEditWindow(QDialog):
    """Modal dialog for editing an existing trip record.

    Args:
        parent: Parent widget (must be a QWidget or None).
        db: Database connection / session object.
        trip_id: Identifier of the trip to edit.
        callback: Zero-arg callable invoked after a successful save.
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        db: Any,
        trip_id: int,
        callback: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("edit_trip.title").format(trip_id))
        self.setMinimumSize(500, 600)
        self.setWindowModality(Qt.ApplicationModal)

        self._trip_service = TripService(db)
        self._trip_id = trip_id
        self._callback = callback
        self._entries: Dict[str, StyledLineEdit] = {}

        trip_data = self._trip_service.get_by_id(trip_id)
        assert trip_data is not None, f"Trip {trip_id} not found"
        self._data: Dict[str, Any] = trip_data
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self)
        layout.addWidget(scroll)

        self._build_form(scroll.content)
        self._build_actions(scroll.content)

    def _build_form(self, parent: QWidget) -> None:
        fields = [
            ("truck_number", t("edit_trip.field_truck")),
            ("driver_name", t("edit_trip.field_driver")),
            ("client_name", t("edit_trip.field_client")),
            ("distance_km", t("edit_trip.field_distance")),
            ("net_profit", t("edit_trip.field_profit")),
        ]

        for key, label_text in fields:
            entry = StyledLineEdit(parent, text=str(self._data.get(key, "")))
            container = field(parent, label_text, entry)
            parent.layout().addWidget(container)
            self._entries[key] = entry

    def _build_actions(self, parent: QWidget) -> None:
        btn = ActionButton(
            parent,
            text=f"\U0001f4be {t('edit_trip.save_button')}",
            command=self._save,
            color=COLORS["success"],
        )
        parent.layout().addSpacing(S["6"])
        parent.layout().addWidget(btn)

    # ── Save logic ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        new_data: Dict[str, Any] = {
            key: self._entries[key].text() for key in self._entries
        }

        # Resolve truck_id from truck_number if the field was changed.
        raw_truck = new_data.get("truck_number", "").strip()
        if raw_truck:
            from repositories.fleet_repository import FleetRepository

            fleet_repo = FleetRepository(
                self._trip_service._trip_repo._db  # type: ignore[union-attr]
            )
            truck = fleet_repo.get_by_plate(raw_truck)
            new_data["truck_id"] = truck["id"] if truck else None
        else:
            new_data["truck_id"] = None

        try:
            self._trip_service.update(self._trip_id, new_data)
            self._callback()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(
                self,
                t("edit_trip.error_title"),
                str(exc),
            )
