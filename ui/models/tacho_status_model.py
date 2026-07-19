"""TachoStatusModel — QAbstractTableModel for tachograph calibration status.

Replaces the inline per-truck row construction in QtMaintenanceControlPanel
with a proper Model/View table. Uses a single efficient SQL query instead
of N+1 queries per truck.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from repositories.tacho_vehicle_data_repository import TachoVehicleDataRepository
from services.i18n import t


class TachoStatusModel(QAbstractTableModel):
    """Table model for tachograph calibration status across all active trucks.

    Columns: Plate, Last Import, Calibration Date, Expiry, Status.
    Single query eliminates N+1 in the original ControlPanel.
    """

    COL_PLATE = 0
    COL_LAST_IMPORT = 1
    COL_CALIBRATION_DATE = 2
    COL_EXPIRY = 3
    COL_STATUS = 4

    _HEADERS = [
        ("fleet.table_plate", 120),
        ("tacho.last_import", 120),
        ("tacho.calibration_date", 120),
        ("tacho.expiry", 120),
        ("common.status", 80),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._HEADERS)

    def headerData(self, section: int, orientation: int, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._HEADERS):
                return t(self._HEADERS[section][0])
        return None

    def header_width(self, section: int) -> int:
        if 0 <= section < len(self._HEADERS):
            return self._HEADERS[section][1]
        return 80

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            return self._format_cell(row, col)
        if role == Qt.UserRole:
            return row
        return None

    @staticmethod
    def _format_cell(row: dict[str, Any], col: int) -> str:
        if col == TachoStatusModel.COL_PLATE:
            return row.get("plate_number") or "\u2014"
        if col == TachoStatusModel.COL_LAST_IMPORT:
            imp = row.get("imported_at")
            return str(imp)[:10] if imp else "\u2014"
        if col == TachoStatusModel.COL_CALIBRATION_DATE:
            cd = row.get("calibration_date")
            return str(cd)[:10] if cd else "\u2014"
        if col == TachoStatusModel.COL_EXPIRY:
            ex = row.get("calibration_expiry")
            return str(ex)[:10] if ex else "\u2014"
        if col == TachoStatusModel.COL_STATUS:
            return TachoStatusModel._status_label(row)
        return ""

    @staticmethod
    def _days_remaining(row: dict[str, Any]) -> int | None:
        expiry_str = row.get("calibration_expiry")
        if not expiry_str:
            return None
        try:
            expiry = datetime.strptime(str(expiry_str)[:10], "%Y-%m-%d")
            return (expiry - datetime.now()).days
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _status_label(row: dict[str, Any]) -> str:
        days = TachoStatusModel._days_remaining(row)
        if days is None:
            return t("tacho.status_no_data", default="No data")
        if days < 0:
            return t("tacho.status_expired", default="Expired")
        if days <= 7:
            return f"{days}d"
        if days <= 30:
            return f"{days}d"
        return t("tacho.status_valid", default="Valid")

    def refresh(self, db) -> None:
        """Fetch all tacho status data through the repository."""
        if db is None:
            raise RuntimeError("Tacho status model requires local database access - not available in remote mode")
        self.beginResetModel()
        try:
            repo = TachoVehicleDataRepository(db)
            rows = repo.get_tacho_status_data()
            self._rows = list(rows) if rows else []
        except Exception:
            self._rows = []
        self.endResetModel()

    def truck_id_at(self, row: int) -> int | None:
        if 0 <= row < len(self._rows):
            return self._rows[row].get("truck_id")
        return None
