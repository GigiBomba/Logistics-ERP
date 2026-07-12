"""pytest-qt tests for AlertListModel and AlertFilterProxy.

Extends the legacy tests in ``test_alert_list_model.py`` with real Alert
dataclass instances, full role coverage, and proxy filter tests.

Tests
-----
- AlertListModel creation and initial state
- rowCount with zero, one, and many alerts
- data() for each custom role (AlertRole, IdRole, TypeRole, SeverityRole,
  TitleRole, MessageRole, CreatedAtRole, TruckIdRole, TripIdRole)
- data() for invalid index returns None
- set_alerts replaces data with begin/endResetModel
- clear empties the model
- get() returns alert by row
- refresh_from fetches from ops and replaces data
- AlertFilterProxy severity, type, truck, trip filtering
- AlertFilterProxy source_row and source_alert helpers
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QModelIndex, Qt

from services.operations.alert_manager import Alert, AlertType, Severity
from ui.models.alert_list_model import AlertFilterProxy, AlertListModel


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def model(qt_widget, qtbot):
    """Create an AlertListModel with a QWidget parent."""
    m = AlertListModel(qt_widget)
    qtbot.addWidget(qt_widget)
    yield m


@pytest.fixture
def proxy(qt_widget, qtbot):
    """Create an AlertFilterProxy with a QWidget parent."""
    p = AlertFilterProxy(qt_widget)
    qtbot.addWidget(qt_widget)
    yield p


@pytest.fixture
def sample_alerts() -> list[Alert]:
    return [
        Alert(
            id="a001", type=AlertType.TRIP_DELAY, severity=Severity.CRITICAL,
            title="Critical Delay", message="45 min delay",
            truck_id="TRK-001", trip_id="T-100",
            created_at="2026-07-12T10:00:00",
        ),
        Alert(
            id="a002", type=AlertType.MAINTENANCE, severity=Severity.WARNING,
            title="Maintenance Due", message="Oil change needed",
            truck_id="TRK-002", trip_id=None,
            created_at="2026-07-12T11:00:00",
        ),
        Alert(
            id="a003", type=AlertType.INSPECTION, severity=Severity.INFO,
            title="Inspection OK", message="All clear",
            truck_id=None, trip_id="T-300",
            created_at="2026-07-12T12:00:00",
        ),
    ]


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Model initializes correctly."""

    def test_creation(self, model):
        assert model is not None
        assert isinstance(model, AlertListModel)

    def test_initial_alerts_empty(self, model):
        assert model._alerts == []
        assert model.rowCount() == 0

    def test_role_names_defined(self, model):
        roles = model.roleNames()
        assert AlertListModel.AlertRole in roles
        assert roles[AlertListModel.AlertRole] == b"alert"
        assert roles[AlertListModel.IdRole] == b"id"
        assert roles[AlertListModel.TitleRole] == b"title"


# =========================================================================
# rowCount
# =========================================================================


class TestRowCount:
    """rowCount reflects the number of alerts."""

    def test_zero(self, model):
        assert model.rowCount() == 0

    def test_one(self, model):
        model.set_alerts([
            Alert(id="1", type=AlertType.INSPECTION, severity=Severity.INFO, title="A"),
        ])
        assert model.rowCount() == 1

    def test_three(self, model, sample_alerts):
        model.set_alerts(sample_alerts)
        assert model.rowCount() == 3


# =========================================================================
# data()
# =========================================================================


class TestData:
    """data() returns correct values for each role."""

    def _setup(self, model):
        model.set_alerts([
            Alert(id="x01", type=AlertType.TRIP_DELAY, severity=Severity.CRITICAL,
                  title="Test Alert", message="Test message",
                  truck_id="TRK-001", trip_id="T-001",
                  created_at="2026-07-12T10:00:00"),
        ])
        return model.index(0, 0)

    def test_display_role_returns_title(self, model):
        idx = self._setup(model)
        assert idx.data(Qt.DisplayRole) == "Test Alert"

    def test_alert_role_returns_alert_instance(self, model):
        idx = self._setup(model)
        alert = idx.data(AlertListModel.AlertRole)
        assert isinstance(alert, Alert)
        assert alert.id == "x01"

    def test_id_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.IdRole) == "x01"

    def test_type_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.TypeRole) == AlertType.TRIP_DELAY

    def test_severity_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.SeverityRole) == Severity.CRITICAL

    def test_title_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.TitleRole) == "Test Alert"

    def test_message_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.MessageRole) == "Test message"

    def test_created_at_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.CreatedAtRole) == "2026-07-12T10:00:00"

    def test_truck_id_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.TruckIdRole) == "TRK-001"

    def test_trip_id_role(self, model):
        idx = self._setup(model)
        assert idx.data(AlertListModel.TripIdRole) == "T-001"

    def test_data_invalid_index_returns_none(self, model):
        assert model.data(QModelIndex(), Qt.DisplayRole) is None

    def test_data_out_of_range_returns_none(self, model):
        model.set_alerts([Alert(id="1", type=AlertType.COMPLIANCE_WARNING, severity=Severity.INFO, title="A")])
        idx = model.index(99, 0)
        assert idx.data(Qt.DisplayRole) is None

    def test_unknown_role_returns_none(self, model):
        idx = self._setup(model)
        assert idx.data(Qt.UserRole + 999) is None

    def test_none_fields_return_none(self, model):
        model.set_alerts([
            Alert(id="n1", type=AlertType.COMPLIANCE_WARNING, severity=Severity.INFO,
                  title="No Refs", message="", truck_id=None, trip_id=None),
        ])
        idx = model.index(0, 0)
        assert idx.data(AlertListModel.TruckIdRole) is None
        assert idx.data(AlertListModel.TripIdRole) is None


# =========================================================================
# set_alerts / clear
# =========================================================================


class TestSetAlertsAndClear:
    """set_alerts replaces data; clear empties."""

    def test_set_alerts_replaces(self, model, sample_alerts):
        model.set_alerts(sample_alerts)
        assert model.rowCount() == 3
        assert model.get(0).id == "a001"
        assert model.get(2).id == "a003"

    def test_set_alerts_empty_list(self, model):
        model.set_alerts([])
        assert model.rowCount() == 0

    def test_clear_empties(self, model, sample_alerts):
        model.set_alerts(sample_alerts)
        assert model.rowCount() == 3
        model.set_alerts([])
        assert model.rowCount() == 0

    def test_clear_twice_no_error(self, model):
        model.set_alerts([])
        model.set_alerts([])  # must not crash


# =========================================================================
# get()
# =========================================================================


class TestGet:
    """get() returns alert by row number."""

    def test_get_valid_row(self, model, sample_alerts):
        model.set_alerts(sample_alerts)
        assert model.get(0).id == "a001"
        assert model.get(1).id == "a002"

    def test_get_negative_row(self, model):
        assert model.get(-1) is None

    def test_get_out_of_range(self, model, sample_alerts):
        model.set_alerts(sample_alerts)
        assert model.get(999) is None

    def test_get_on_empty_model(self, model):
        assert model.get(0) is None


# =========================================================================
# refresh_from()
# =========================================================================


class TestRefreshFrom:
    """refresh_from fetches alerts from ops and replaces model data."""

    def test_refresh_fetches_and_sets(self, model, sample_alerts):
        ops = MagicMock()
        ops.get_active_alerts.return_value = sample_alerts
        model.refresh_from(ops)
        assert model.rowCount() == 3
        assert model.get(0).id == "a001"
        ops.get_active_alerts.assert_called_once_with(limit=200)

    def test_refresh_replaces_existing(self, model, sample_alerts):
        model.set_alerts(sample_alerts)
        ops = MagicMock()
        ops.get_active_alerts.return_value = []
        model.refresh_from(ops)
        assert model.rowCount() == 0

    def test_refresh_with_empty_ops_result(self, model):
        ops = MagicMock()
        ops.get_active_alerts.return_value = []
        model.refresh_from(ops)
        assert model.rowCount() == 0


# =========================================================================
# AlertFilterProxy
# =========================================================================


class TestAlertFilterProxy:
    """AlertFilterProxy filters correctly by severity, type, truck, trip."""

    def _setup(self, proxy, model, sample_alerts):
        model.set_alerts(sample_alerts)
        proxy.setSourceModel(model)
        return proxy

    def test_no_filter_shows_all(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        assert proxy.rowCount() == 3

    def test_filter_by_severity_critical(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.CRITICAL])
        assert proxy.rowCount() == 1
        alert = proxy.source_alert(0)
        assert alert is not None
        assert alert.id == "a001"

    def test_filter_by_severity_warning(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.WARNING])
        assert proxy.rowCount() == 1
        assert proxy.source_alert(0).id == "a002"

    def test_filter_by_severity_multiple(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.CRITICAL, Severity.WARNING])
        assert proxy.rowCount() == 2

    def test_filter_by_severity_none_returns_none(self, proxy, model, sample_alerts):
        """Filtering for an unused severity returns zero rows."""
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.INFO])  # only one INFO
        assert proxy.rowCount() == 1
        proxy.set_severity_filter([])
        assert proxy.rowCount() == 0

    def test_filter_reset_with_none(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.CRITICAL])
        assert proxy.rowCount() == 1
        proxy.set_severity_filter(None)
        assert proxy.rowCount() == 3

    def test_filter_by_type(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_type_filter("trip_delay")
        assert proxy.rowCount() == 1
        assert proxy.source_alert(0).id == "a001"

    def test_filter_by_type_none(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_type_filter("nonexistent")
        assert proxy.rowCount() == 0

    def test_filter_by_type_reset(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_type_filter("trip_delay")
        assert proxy.rowCount() == 1
        proxy.set_type_filter(None)
        assert proxy.rowCount() == 3

    def test_filter_by_truck_substring(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_truck_filter("TRK-001")
        assert proxy.rowCount() == 1
        assert proxy.source_alert(0).id == "a001"

    def test_filter_by_truck_case_insensitive(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_truck_filter("trk-001")
        assert proxy.rowCount() == 1

    def test_filter_by_truck_no_match(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_truck_filter("TRK-999")
        assert proxy.rowCount() == 0

    def test_filter_by_truck_alert_without_truck(self, proxy, model, sample_alerts):
        """Alert with truck_id=None should not match a non-empty filter."""
        self._setup(proxy, model, sample_alerts)
        proxy.set_truck_filter("TRK")
        # a003 has no truck_id, but a001 and a002 match
        assert proxy.rowCount() == 2

    def test_filter_by_trip_substring(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_trip_filter("T-100")
        assert proxy.rowCount() == 1
        assert proxy.source_alert(0).id == "a001"

    def test_filter_by_trip_case_insensitive(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_trip_filter("t-100")
        assert proxy.rowCount() == 1

    def test_filter_by_trip_no_match(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_trip_filter("T-999")
        assert proxy.rowCount() == 0

    def test_combined_filters(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.CRITICAL])
        proxy.set_truck_filter("TRK-001")
        assert proxy.rowCount() == 1

    def test_combined_filters_no_overlap(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.CRITICAL])
        proxy.set_truck_filter("TRK-002")
        assert proxy.rowCount() == 0

    def test_source_row_valid(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.CRITICAL])
        assert proxy.rowCount() == 1
        src_row = proxy.source_row(0)
        assert src_row == 0  # a001 is at index 0 in source

    def test_source_row_invalid(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        assert proxy.source_row(999) == -1

    def test_source_alert_valid(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        proxy.set_severity_filter([Severity.WARNING])
        alert = proxy.source_alert(0)
        assert alert is not None
        assert alert.id == "a002"

    def test_source_alert_invalid(self, proxy, model, sample_alerts):
        self._setup(proxy, model, sample_alerts)
        assert proxy.source_alert(999) is None

    def test_source_alert_without_source_model(self, proxy):
        assert proxy.source_alert(0) is None

    def test_source_row_without_source_model(self, proxy):
        assert proxy.source_row(0) == -1


# =========================================================================
# Proxy — model lifecycle
# =========================================================================


class TestProxyLifecycle:
    """Proxy handles model changes correctly."""

    def test_set_source_model_updates(self, proxy):
        m = AlertListModel()
        m.set_alerts([Alert(id="1", type=AlertType.COMPLIANCE_WARNING, severity=Severity.INFO, title="A")])
        proxy.setSourceModel(m)
        assert proxy.rowCount() == 1

    def test_model_data_change_reflected(self, proxy, model):
        proxy.setSourceModel(model)
        assert proxy.rowCount() == 0
        model.set_alerts([Alert(id="1", type=AlertType.COMPLIANCE_WARNING, severity=Severity.INFO, title="A")])
        assert proxy.rowCount() == 1

    def test_model_clear_reflected(self, proxy, model):
        model.set_alerts([Alert(id="1", type=AlertType.COMPLIANCE_WARNING, severity=Severity.INFO, title="A")])
        proxy.setSourceModel(model)
        assert proxy.rowCount() == 1
        model.set_alerts([])
        assert proxy.rowCount() == 0
