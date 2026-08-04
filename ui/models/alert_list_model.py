"""AlertListModel — QAbstractListModel that wraps AlertManager for efficient filtering.

Replaces inline alert widget construction in QtMaintenanceControlPanel with
a proper Qt Model/View architecture. The model is backed by the OperationsEngine
alert manager and can be filtered via QSortFilterProxyModel without losing
scroll position or rebuilding widgets.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt

from services.operations.alert_manager import Alert, Severity

class AlertListModel(QAbstractListModel):
    """A read-only list model presenting active alerts.

    Roles exposed:
        - AlertRole: the full Alert dataclass instance
        - IdRole: alert.id (str)
        - TypeRole: alert.type (AlertType)
        - SeverityRole: alert.severity (Severity)
        - TitleRole: alert.title (str)
        - MessageRole: alert.message (str)
        - CreatedAtRole: alert.created_at (str)
        - TruckIdRole: alert.truck_id (Optional[str])
        - TripIdRole: alert.trip_id (Optional[str])
    """

    # Custom roles
    AlertRole = Qt.UserRole + 1
    IdRole = Qt.UserRole + 2
    TypeRole = Qt.UserRole + 3
    SeverityRole = Qt.UserRole + 4
    TitleRole = Qt.UserRole + 5
    MessageRole = Qt.UserRole + 6
    CreatedAtRole = Qt.UserRole + 7
    TruckIdRole = Qt.UserRole + 8
    TripIdRole = Qt.UserRole + 9

    _ROLE_NAMES = {
        AlertRole: b"alert",
        IdRole: b"id",
        TypeRole: b"type",
        SeverityRole: b"severity",
        TitleRole: b"title",
        MessageRole: b"message",
        CreatedAtRole: b"created_at",
        TruckIdRole: b"truck_id",
        TripIdRole: b"trip_id",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alerts: list[Alert] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._alerts)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._alerts):
            return None
        a = self._alerts[index.row()]
        if role == Qt.DisplayRole:
            return a.title
        if role == self.AlertRole:
            return a
        if role == self.IdRole:
            return a.id
        if role == self.TypeRole:
            return a.type
        if role == self.SeverityRole:
            return a.severity
        if role == self.TitleRole:
            return a.title
        if role == self.MessageRole:
            return a.message
        if role == self.CreatedAtRole:
            return a.created_at
        if role == self.TruckIdRole:
            return a.truck_id
        if role == self.TripIdRole:
            return a.trip_id
        return None

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_NAMES

    def set_alerts(self, alerts: list[Alert]) -> None:
        self.beginResetModel()
        self._alerts = list(alerts)
        self.endResetModel()

    def refresh_from(self, ops) -> None:
        """Fetch active alerts from OperationsEngine and replace model data."""
        alerts = ops.get_active_alerts(limit=200)
        self.set_alerts(alerts)

    def clear(self) -> None:
        """Remove all alerts from the model."""
        self.beginResetModel()
        self._alerts.clear()
        self.endResetModel()

    def get_alerts(self) -> list[Alert]:
        """Return the full list of alerts."""
        return list(self._alerts)

    def get(self, row: int) -> Alert | None:
        if 0 <= row < len(self._alerts):
            return self._alerts[row]
        return None


class AlertFilterProxy(QSortFilterProxyModel):
    """Filter/sort proxy for AlertListModel.

    Filters by severity (checkbox), type (exact match), truck_id/trip_id
    (substring match). Delegates to QSortFilterProxyModel for efficient
    filtering without losing scroll position or rebuilding widgets.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._severity_filter: list[Severity] | None = None
        self._type_filter: str | None = None
        self._truck_filter: str = ""
        self._trip_filter: str = ""

    def set_severity_filter(self, severities: list[Severity] | None) -> None:
        self._severity_filter = severities
        self.invalidateFilter()

    def set_type_filter(self, type_str: str | None) -> None:
        self._type_filter = type_str
        self.invalidateFilter()

    def set_truck_filter(self, text: str) -> None:
        self._truck_filter = text.strip().lower()
        self.invalidateFilter()

    def set_trip_filter(self, text: str) -> None:
        self._trip_filter = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        src = self.sourceModel()
        if src is None:
            return False
        a = src.get(source_row)
        if a is None:
            return False
        if self._severity_filter is not None and a.severity not in self._severity_filter:
            return False
        if self._type_filter is not None and a.type.value != self._type_filter:
            return False
        if self._truck_filter and not (a.truck_id and self._truck_filter in a.truck_id.lower()):
            return False
        return not (self._trip_filter and not (a.trip_id and self._trip_filter in a.trip_id.lower()))

    def source_row(self, proxy_row: int) -> int:
        idx = self.mapToSource(self.index(proxy_row, 0))
        if idx.isValid():
            return idx.row()
        return -1

    def source_alert(self, proxy_row: int) -> Alert | None:
        row = self.source_row(proxy_row)
        if row >= 0:
            src = self.sourceModel()
            if src is not None:
                return src.get(row)
        return None
