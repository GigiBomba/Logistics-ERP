"""Modal dialog for creating or editing a truck record."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.driver_truck_service import DriverTruckService
from services.fleet_service import FleetService
from services.i18n import t
from services.operations.event_bus import (
    TRUCK_CREATED,
    TRUCK_UPDATED,
    EventBus,
)
from ui.components import Btn
from ui.design_tokens import SP
from ui.widgets import (
    StyledCheckBox,
    StyledComboBox,
    StyledLineEdit,
)

logger = logging.getLogger(__name__)


class _TruckFormDialog(QDialog):
    """Modal dialog for creating or editing a truck record."""

    def __init__(
        self,
        parent: QWidget | None,
        service: FleetService,
        dta_service: DriverTruckService | None = None,
        truck: dict[str, Any] | None = None,
        on_save=None,
    ):
        super().__init__(parent)
        self._service = service
        self._dta_service = dta_service
        self._truck = truck
        self._on_save = on_save
        self._driver_ids: list[str] = []
        self._driver_names: list[str] = []
        self._fields: dict[str, StyledLineEdit] = {}

        is_edit = truck is not None
        self.setWindowTitle(
            t("fleet.edit_button") if is_edit else t("fleet.truck_form_title")
        )
        self.setMinimumWidth(480)
        self.setModal(True)

        self._build()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        self._form_layout = QVBoxLayout(content)
        self._form_layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])
        self._form_layout.setSpacing(SP["3"])
        self._form_layout.setAlignment(Qt.AlignTop)

        truck = self._truck or {}

        def make_field(label_key: str, default: str = "") -> StyledLineEdit:
            label = QLabel(t(label_key))
            label.setProperty("fontRole", "label")
            self._form_layout.addWidget(label)
            edit = StyledLineEdit()
            edit.setText(default)
            self._form_layout.addWidget(edit)
            return edit

        self._fields = {
            "plate": make_field(
                "fleet.form_plate", truck.get("plate_number", "")
            ),
            "model": make_field(
                "fleet.form_model", truck.get("model", "")
            ),
            "manufacturer": make_field(
                "fleet.form_manufacturer", truck.get("manufacturer", "")
            ),
            "year": make_field(
                "fleet.form_year",
                str(truck["year"]) if truck and truck.get("year") else "",
            ),
            "vin": make_field(
                "fleet.form_vin", truck.get("vin", "")
            ),
            "fuel": make_field(
                "fleet.form_consumption",
                str(truck.get("fuel_consumption", "") or ""),
            ),
            "mileage": make_field(
                "fleet.form_km",
                str(truck.get("mileage", "0") or "0"),
            ),
            "monthly_rate": make_field(
                "fleet.form_rate",
                f"{truck['monthly_rate']:.2f}"
                if truck and truck.get("monthly_rate") is not None
                else "0",
            ),
            "status": make_field(
                "fleet.form_status",
                truck.get("status", t("fleet.status_active")),
            ),
            "tracking_device_id": make_field(
                "fleet.form_tracking_device_id",
                truck.get("tracking_device_id", ""),
            ),
        }

        # -- Driver assignment dropdown --
        if self._dta_service:
            lbl = QLabel(t("fleet.table_driver"))
            lbl.setProperty("fontRole", "label")
            self._form_layout.addWidget(lbl)

            driver_options: list[tuple[str, str]] = [
                ("", t("fleet.table_driver_unassigned"))
            ]
            try:
                if self._service.db is None:
                    logger.warning("DriverRepository requires local database - not available in remote mode")
                else:
                    from repositories.driver_repository import DriverRepository
                    dr_repo = DriverRepository(self._service.db)
                    for dr in dr_repo.get_active_drivers():
                        driver_options.append((str(dr["id"]), dr["name"]))
            except Exception:
                pass

            self._driver_ids = [did for did, _ in driver_options]
            self._driver_names = [name for _, name in driver_options]
            self._driver_combo = StyledComboBox(values=self._driver_names, state="readonly")
            self._form_layout.addWidget(self._driver_combo)

            if truck and self._dta_service:
                assigned = self._dta_service.get_driver_name_for_truck(truck["id"])
                if assigned and assigned in self._driver_names:
                    self._driver_combo.setCurrentText(assigned)

        # -- Active checkbox --
        self._active_cb = StyledCheckBox(
            text=t("fleet.form_active"),
        )
        active_val = truck.get("active_status", 1) if truck else 1
        self._active_cb.setChecked(bool(active_val))
        self._form_layout.addWidget(self._active_cb)

        # -- Spacer --
        self._form_layout.addStretch(1)

        # -- Buttons --
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP["3"])

        save_btn = Btn(
            self, t("fleet.save_button"), variant="primary", command=self._save
        )
        cancel_btn = Btn(
            self, t("fleet.cancel_button"), variant="secondary", command=self.reject
        )
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        self._form_layout.addLayout(btn_row)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        scroll.setWidget(content)

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _save(self) -> None:
        f = self._fields
        plate = f["plate"].text().strip().upper()
        if not plate:
            QMessageBox.warning(
                self,
                t("fleet.validation_plate_required"),
                t("fleet.validation_plate_required"),
            )
            return

        year: int | None = None
        if f["year"].text().strip():
            try:
                year = int(f["year"].text().strip())
            except ValueError:
                QMessageBox.warning(
                    self,
                    t("fleet.validation_year_invalid"),
                    t("fleet.validation_year_invalid"),
                )
                return

        fuel: float | None = None
        if f["fuel"].text().strip():
            try:
                fuel = float(f["fuel"].text().strip())
            except ValueError:
                QMessageBox.warning(
                    self,
                    t("fleet.validation_consumption_invalid"),
                    t("fleet.validation_consumption_invalid"),
                )
                return

        try:
            mileage = float(f["mileage"].text() or "0")
            monthly_rate = float(f["monthly_rate"].text() or "0")
        except ValueError:
            QMessageBox.warning(
                self,
                t("fleet.validation_km_rate_service_invalid"),
                t("fleet.validation_km_rate_service_invalid"),
            )
            return

        data: dict[str, Any] = {
            "plate_number": plate,
            "model": f["model"].text(),
            "manufacturer": f["manufacturer"].text(),
            "year": year,
            "vin": f["vin"].text(),
            "fuel_consumption": fuel,
            "mileage": mileage,
            "monthly_rate": monthly_rate,
            "status": f["status"].text(),
            "active_status": 1 if self._active_cb.isChecked() else 0,
            "tracking_device_id": f["tracking_device_id"].text().strip(),
        }

        try:
            if self._truck:
                truck_id = self._truck["id"]
                self._service.update_truck(truck_id, data)
            else:
                truck_id = self._service.add_truck(data)

            # Driver assignment
            if self._dta_service and hasattr(self, "_driver_combo"):
                try:
                    selected_idx = self._driver_names.index(
                        self._driver_combo.currentText()
                    )
                except ValueError:
                    selected_idx = -1
                if selected_idx >= 0:
                    did_str = self._driver_ids[selected_idx]
                    if did_str:
                        self._dta_service.assign_driver_to_truck(
                            int(did_str), truck_id
                        )
                    else:
                        self._dta_service.unassign_truck(truck_id)

            # Publish the change so dropdowns in other views
            # (route planner, calculator, dispatch assignment) refresh
            # without a restart.
            plate = data.get("plate_number", "")
            try:
                bus = EventBus()
                if self._truck:
                    bus.publish(TRUCK_UPDATED, {
                        "truck_id": int(truck_id),
                        "plate": plate,
                    })
                else:
                    bus.publish(TRUCK_CREATED, {
                        "truck_id": int(truck_id),
                        "plate": plate,
                    })
            except Exception:
                logger.exception(
                    "Failed to publish truck %s event", truck_id
                )

            if self._on_save:
                self._on_save()
            self.accept()
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.error_save", default="Save Error"),
                str(ex),
            )
