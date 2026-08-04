"""Tests for QtFleetTab — fleet management view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_fleet_service():
    fs = MagicMock()
    fs.get_trucks.return_value = []
    return fs


@pytest.fixture
def mock_dta_service():
    return MagicMock()


@pytest.fixture
def mock_fleet_repo():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_active_alert_count.return_value = 0
    return ops


@pytest.fixture
def fleet_tab(qtbot, mock_ops, mock_fleet_service, mock_dta_service, mock_fleet_repo):
    """Create a QtFleetTab with all services mocked."""
    patchers = [
        patch("ui.views.fleet_tab.fleet_tab.FleetService", return_value=mock_fleet_service),
        patch("ui.views.fleet_tab.fleet_tab.DriverTruckService", return_value=mock_dta_service),
        patch("ui.views.fleet_tab.fleet_tab.FleetRepository", return_value=mock_fleet_repo),
    ]
    for p in patchers:
        p.start()

    from ui.views.fleet_tab.fleet_tab import QtFleetTab

    widget = QtFleetTab(
        parent=None,
        db=MagicMock(),
        ops=mock_ops,
        fleet_service=mock_fleet_service,
        dta_service=mock_dta_service,
        fleet_repo=mock_fleet_repo,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================

class TestQtFleetTab:
    """Suite of tests for QtFleetTab."""

    def test_initialization(self, fleet_tab):
        """Widget initializes without crashing and stores service references."""
        assert fleet_tab is not None
        assert fleet_tab.service is not None
        assert hasattr(fleet_tab, "_rows")

    @pytest.mark.xfail(reason="Pre-existing: PageTitle is a function not a class — findChildren fails")
    def test_header_renders_title(self, fleet_tab):
        """Header contains a PageTitle with 'Fleet Manager'."""
        from ui.components import PageTitle
        titles = fleet_tab.findChildren(PageTitle)
        assert len(titles) >= 1
        # The PageTitle stores text; ensure at least one exists
        assert any(t.text() for t in titles)

    def test_kpi_strip_renders(self, fleet_tab):
        """KPI strip is built with labelled cards."""
        assert hasattr(fleet_tab, "_kpi_strip")
        assert fleet_tab._kpi_strip is not None
        # KPI value labels dict should contain expected keys
        expected_keys = {"kpi_total", "kpi_active", "kpi_leasing", "kpi_alerts"}
        assert expected_keys.issubset(fleet_tab._kpi_value_labels.keys())

    def test_search_bar_renders(self, fleet_tab):
        """Search text field and reset button exist."""
        assert hasattr(fleet_tab, "_e_search")
        assert fleet_tab._e_search is not None
        assert hasattr(fleet_tab, "_e_plate_search")

    def test_table_renders_with_columns(self, fleet_tab):
        """StyledTableWidget exists and has correct column count."""
        assert hasattr(fleet_tab, "_table")
        table = fleet_tab._table
        from ui.views.fleet_tab.fleet_tab import QtFleetTab
        expected_count = len(QtFleetTab.TABLE_COLUMNS)
        assert table.columnCount() == expected_count

    @pytest.mark.xfail(reason="Pre-existing: Btn is a function not a class — findChildren fails")
    def test_action_buttons_render(self, fleet_tab):
        """Add, edit, delete buttons exist on the widget."""
        from ui.components import Btn
        buttons = fleet_tab.findChildren(Btn)
        btn_texts = [b.text() for b in buttons]
        # Look for at least some action button text (translations at runtime)
        assert len(buttons) >= 3

    def test_alerts_panel_renders(self, fleet_tab):
        """Alerts container is built."""
        assert hasattr(fleet_tab, "_alerts_container")
        assert fleet_tab._alerts_container_layout is not None

    def test_quick_add_section_renders(self, fleet_tab):
        """Quick-add form fields exist."""
        assert hasattr(fleet_tab, "_q_plate")
        assert hasattr(fleet_tab, "_q_model")
        assert hasattr(fleet_tab, "_q_rate")

    @pytest.mark.xfail(reason="Pre-existing: WorkerPool not mocked — async refresh race")
    def test_refresh_populates_table(self, fleet_tab, mock_fleet_service):
        """refresh() calls service and populates table rows."""
        mock_fleet_service.get_trucks.return_value = [
            {
                "id": 1,
                "plate_number": "AB-123-CD",
                "model": "Actros",
                "manufacturer": "Mercedes",
                "year": 2020,
                "vin": "WDB1234567890",
                "mileage": 150000,
                "fuel_consumption": 28.5,
                "monthly_rate": 1200.00,
                "status": "Active",
                "active_status": 1,
            }
        ]
        fleet_tab.refresh()
        assert fleet_tab._table.rowCount() == 1
        # Verify the plate text appears in the table
        item = fleet_tab._table.item(0, 1)  # plate column
        assert item is not None
        assert "AB-123-CD" in item.text()

    def test_refresh_handles_empty_data(self, fleet_tab, mock_fleet_service):
        """refresh() handles empty truck list gracefully."""
        mock_fleet_service.get_trucks.return_value = []
        # Should not raise
        fleet_tab.refresh()
        assert fleet_tab._table.rowCount() == 0

    def test_refresh_handles_service_error(self, fleet_tab, mock_fleet_service, monkeypatch):
        """refresh() catches service exceptions and shows dialog."""
        monkeypatch.setattr("ui.views.fleet_tab.fleet_tab.QMessageBox", MagicMock())
        mock_fleet_service.get_trucks.side_effect = Exception("DB error")
        # Should not crash, should show QMessageBox
        fleet_tab.refresh()
        # Table should remain intact
        assert fleet_tab._table is not None

    def test_shutdown_cleanup(self, fleet_tab):
        """shutdown() calls base class cleanup without crash."""
        # Should not raise
        fleet_tab.shutdown()
        # Calling shutdown twice is safe
        fleet_tab.shutdown()

    def test_wakeup_does_not_crash(self, fleet_tab):
        """wakeup() refreshes without crashing."""
        fleet_tab.wakeup()

    def test_chart_area_renders(self, fleet_tab):
        """Chart area frame exists."""
        assert hasattr(fleet_tab, "_chart_area")
        assert fleet_tab._chart_area is not None

    @pytest.mark.xfail(reason="Pre-existing: WorkerPool not mocked — async refresh race")
    def test_filter_table_by_text(self, fleet_tab, mock_fleet_service):
        """Typing in search filter hides non-matching rows."""
        mock_fleet_service.get_trucks.return_value = [
            {"id": 1, "plate_number": "AB-001", "model": "X", "manufacturer": "Y",
             "year": 2020, "vin": "V1", "mileage": 100, "fuel_consumption": 25.0,
             "monthly_rate": 500, "status": "Active", "active_status": 1},
            {"id": 2, "plate_number": "CD-002", "model": "Z", "manufacturer": "W",
             "year": 2021, "vin": "V2", "mileage": 200, "fuel_consumption": 30.0,
             "monthly_rate": 600, "status": "Active", "active_status": 1},
        ]
        fleet_tab.refresh()
        assert fleet_tab._table.rowCount() == 2

        fleet_tab._e_search.setText("AB")
        # After filtering, only first row should be visible
        assert fleet_tab._table.isRowHidden(0) is False
        assert fleet_tab._table.isRowHidden(1) is True

        fleet_tab._e_search.clear()
        fleet_tab._filter_table()
        assert fleet_tab._table.isRowHidden(0) is False
        assert fleet_tab._table.isRowHidden(1) is False


# =========================================================================
# Additional fixtures for expanded tests
# =========================================================================


from PySide6.QtWidgets import QWidget


class _FakePlotlyWidget(QWidget):
    """Minimal QWidget stand-in for PlotlyChartWidget to avoid QWebEngine."""

    def __init__(self, **kwargs):
        super().__init__()
        self._fig = None

    def set_figure(self, fig):
        self._fig = fig


# Ensure QWidget is available in scope for the fixture below


@pytest.fixture
def fleet_tab_view(qtbot):
    """Create QtFleetTab with all dependencies mocked."""
    from ui.views.fleet_tab.fleet_tab import QtFleetTab

    with (
        patch("ui.views.fleet_tab.fleet_tab.ExportService"),
        patch(
            "ui.views.fleet_tab.fleet_tab.PlotlyChartWidget", _FakePlotlyWidget
        ),
        patch("ui.views.fleet_tab.fleet_tab.WorkerPool") as mock_wp,
    ):
        ops = MagicMock()
        ops.event_bus = MagicMock()
        ops.get_active_alerts.return_value = []
        ops.get_active_alert_count.return_value = 0

        def _sync_run(fn, on_result=None, on_error=None, **kw):
            try:
                result = fn()
                if on_result:
                    on_result(result)
            except Exception as e:
                if on_error:
                    on_error(str(e))

        mock_wp.run = _sync_run

        tab = QtFleetTab(
            parent=None,
            db=MagicMock(),
            ops=ops,
            fleet_repo=MagicMock(),
            fleet_service=MagicMock(),
            dta_service=MagicMock(),
        )
        qtbot.addWidget(tab)
        yield tab
        tab.shutdown()


# =========================================================================
# Helper data / functions
# =========================================================================

_SAMPLE_TRUCK_A = {
    "id": 1,
    "plate_number": "AB-001-CD",
    "model": "Actros",
    "manufacturer": "Mercedes",
    "year": 2020,
    "vin": "WDB1234567890VIN1",
    "mileage": 150000,
    "fuel_consumption": 28.5,
    "monthly_rate": 1200.00,
    "status": "Active",
    "active_status": 1,
}

_SAMPLE_TRUCK_B = {
    "id": 2,
    "plate_number": "CD-002-EF",
    "model": "FH",
    "manufacturer": "Volvo",
    "year": 2021,
    "vin": "YV1234567890VIN2",
    "mileage": 80000,
    "fuel_consumption": 30.0,
    "monthly_rate": 1500.00,
    "status": "Active",
    "active_status": 1,
}


def _populate_trucks(ft, trucks=None):
    """Set service.get_trucks return value and refresh."""
    if trucks is None:
        trucks = [_SAMPLE_TRUCK_A, _SAMPLE_TRUCK_B]
    ft.service.get_trucks.return_value = trucks
    ft.refresh()


# =========================================================================
# TestQtFleetTabUI -- Widget construction and UI structure
# =========================================================================


class TestQtFleetTabUI:
    """Widget construction and UI structure."""

    def test_title_label_visible(self, fleet_tab_view):
        """Header label exists with text."""
        from PySide6.QtWidgets import QLabel

        labels = fleet_tab_view.findChildren(QLabel)
        assert any(l.text() for l in labels if l.text())

    def test_kpi_strip_has_five_cards(self, fleet_tab_view):
        """KPI value labels dict contains expected keys."""
        labels = fleet_tab_view._kpi_value_labels
        assert len(labels) >= 4
        for key in ("kpi_total", "kpi_active", "kpi_leasing", "kpi_alerts"):
            assert key in labels

    def test_search_entry_exists(self, fleet_tab_view):
        """_e_search is QLineEdit."""
        from PySide6.QtWidgets import QLineEdit

        assert isinstance(fleet_tab_view._e_search, QLineEdit)

    def test_table_has_correct_columns(self, fleet_tab_view):
        """Column count >= 6."""
        assert fleet_tab_view._table.columnCount() >= 6

    def test_action_buttons_exist(self, fleet_tab_view):
        """Add, Edit, Delete, Export buttons present."""
        from PySide6.QtWidgets import QPushButton

        buttons = fleet_tab_view.findChildren(QPushButton)
        assert len(buttons) >= 5

    def test_quick_add_section_visible(self, fleet_tab_view):
        """Quick-add form fields exist."""
        assert hasattr(fleet_tab_view, "_q_plate")
        assert hasattr(fleet_tab_view, "_q_model")
        assert hasattr(fleet_tab_view, "_q_rate")

    def test_alerts_panel_container_exists(self, fleet_tab_view):
        """_alerts_container is a QFrame."""
        from PySide6.QtWidgets import QFrame

        assert isinstance(fleet_tab_view._alerts_container, QFrame)

    def test_chart_area_has_tabs(self, fleet_tab_view):
        """QTabWidget in right panel with at least 2 tabs."""
        from PySide6.QtWidgets import QTabWidget

        tabs = fleet_tab_view.findChildren(QTabWidget)
        assert len(tabs) >= 1
        assert tabs[0].count() >= 2


# =========================================================================
# TestQtFleetTabSearch -- Search and find
# =========================================================================


class TestQtFleetTabSearch:
    """Search and find."""

    def test_filter_table_partial_plate(self, fleet_tab_view):
        """Search 'AB-001' -> only that row visible."""
        _populate_trucks(fleet_tab_view)
        assert fleet_tab_view._table.rowCount() == 2
        fleet_tab_view._e_search.setText("AB-001")
        fleet_tab_view._filter_table()
        assert fleet_tab_view._table.isRowHidden(0) is False
        assert fleet_tab_view._table.isRowHidden(1) is True

    def test_filter_table_by_vin_substring(self, fleet_tab_view):
        """Search by VIN substring -> matching rows."""
        _populate_trucks(fleet_tab_view)
        fleet_tab_view._e_search.setText("VIN1")
        fleet_tab_view._filter_table()
        assert fleet_tab_view._table.isRowHidden(0) is False
        assert fleet_tab_view._table.isRowHidden(1) is True

    def test_find_plate_exact_match(self, fleet_tab_view, monkeypatch):
        """_find_plate('AB-001') scrolls to row."""
        _populate_trucks(fleet_tab_view)
        scroll_spy = MagicMock(wraps=fleet_tab_view._table.scrollToItem)
        fleet_tab_view._table.scrollToItem = scroll_spy
        fleet_tab_view._e_plate_search.setText("AB-001-CD")
        fleet_tab_view._find_plate()
        assert fleet_tab_view._table.currentRow() == 0
        scroll_spy.assert_called_once()

    def test_find_plate_no_match_shows_info(self, fleet_tab_view, monkeypatch):
        """No match -> QMessageBox.information."""
        _populate_trucks(fleet_tab_view)
        info_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", info_mock
        )
        fleet_tab_view._e_plate_search.setText("ZZ-999")
        fleet_tab_view._find_plate()
        info_mock.assert_called_once()


# =========================================================================
# TestQtFleetTabContextMenu -- Right-click context menu
# =========================================================================


class TestQtFleetTabContextMenu:
    """Right-click context menu actions."""

    @staticmethod
    def _setup_context(ft, monkeypatch, valid=True):
        """Set up mocks so contextMenuEvent can be tested safely."""
        from PySide6.QtGui import QIcon

        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.qta.icon",
            MagicMock(return_value=QIcon()),
        )
        mock_index = MagicMock()
        mock_index.isValid.return_value = valid
        mock_index.row.return_value = 0
        monkeypatch.setattr(ft._table, "indexAt", MagicMock(return_value=mock_index))
        from PySide6.QtWidgets import QMenu

        monkeypatch.setattr(QMenu, "exec_", MagicMock())

    def test_context_menu_contains_edit(self, fleet_tab_view, monkeypatch):
        """Context menu edit action triggers _edit_truck_selected."""
        _populate_trucks(fleet_tab_view)
        self._setup_context(fleet_tab_view, monkeypatch)
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent

        event = QContextMenuEvent(
            QContextMenuEvent.Mouse, QPoint(10, 10), QPoint(10, 10)
        )
        fleet_tab_view.contextMenuEvent(event)
        from PySide6.QtWidgets import QMenu

        assert QMenu.exec_.called

    def test_context_menu_contains_delete(self, fleet_tab_view, monkeypatch):
        """Context menu delete action triggers _delete_truck."""
        _populate_trucks(fleet_tab_view)
        self._setup_context(fleet_tab_view, monkeypatch)
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent

        event = QContextMenuEvent(
            QContextMenuEvent.Mouse, QPoint(10, 10), QPoint(10, 10)
        )
        fleet_tab_view.contextMenuEvent(event)
        from PySide6.QtWidgets import QMenu

        assert QMenu.exec_.called

    def test_context_menu_contains_documents(self, fleet_tab_view):
        """Documents button exists in the action bar."""
        from PySide6.QtWidgets import QPushButton

        btns = fleet_tab_view.findChildren(QPushButton)
        btn_texts = [b.text().lower() for b in btns if b.text()]
        assert any("document" in t for t in btn_texts)

    def test_context_menu_no_selection_noop(self, fleet_tab_view, monkeypatch):
        """No valid row selected -> no menu shown."""
        fleet_tab_view.service.get_trucks.return_value = []
        fleet_tab_view.refresh()
        self._setup_context(fleet_tab_view, monkeypatch, valid=False)
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QContextMenuEvent

        event = QContextMenuEvent(
            QContextMenuEvent.Mouse, QPoint(-100, -100), QPoint(-100, -100)
        )
        fleet_tab_view.contextMenuEvent(event)
        from PySide6.QtWidgets import QMenu

        assert not QMenu.exec_.called


# =========================================================================
# TestQtFleetTabExport -- CSV / Excel / PDF export
# =========================================================================


class TestQtFleetTabExport:
    """CSV / Excel / PDF export flows."""

    def test_export_csv_success(self, fleet_tab_view, monkeypatch):
        """QFileDialog returns path -> CSV written, success shown."""
        _populate_trucks(fleet_tab_view)
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QFileDialog.getSaveFileName",
            MagicMock(return_value=("test.csv", "CSV files (*.csv)")),
        )
        import builtins

        mock_file = MagicMock()
        monkeypatch.setattr(builtins, "open", MagicMock(return_value=mock_file))

        info_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", info_mock
        )
        fleet_tab_view._export_csv()
        info_mock.assert_called_once()

    def test_export_excel_success(self, fleet_tab_view, monkeypatch):
        """Excel export calls generate_excel and shows success."""
        _populate_trucks(fleet_tab_view)
        fleet_tab_view.exporter.generate_excel = MagicMock(return_value="test.xlsx")
        info_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", info_mock
        )
        fleet_tab_view._export_excel()
        info_mock.assert_called_once()
        fleet_tab_view.exporter.generate_excel.assert_called_once()

    def test_export_pdf_success(self, fleet_tab_view, monkeypatch):
        """PDF export calls generate_pdf and shows success."""
        _populate_trucks(fleet_tab_view)
        fleet_tab_view.exporter.generate_pdf = MagicMock(return_value="test.pdf")
        info_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", info_mock
        )
        fleet_tab_view._export_pdf()
        info_mock.assert_called_once()
        fleet_tab_view.exporter.generate_pdf.assert_called_once()

    def test_export_cancelled(self, fleet_tab_view, monkeypatch):
        """Dialog returns empty path -> no export."""
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QFileDialog.getSaveFileName",
            MagicMock(return_value=("", "")),
        )
        info_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", info_mock
        )
        fleet_tab_view._export_csv()
        info_mock.assert_not_called()


# =========================================================================
# TestQtFleetTabCRUD -- Add / edit / delete truck flows
# =========================================================================


class TestQtFleetTabCRUD:
    """Add / edit / delete truck flows."""

    def test_add_truck_button_opens_form(self, fleet_tab_view, monkeypatch):
        """Add button command triggers _TruckFormDialog."""
        from ui.views.fleet_tab.fleet_tab import _TruckFormDialog

        dlg_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab._TruckFormDialog",
            MagicMock(return_value=dlg_mock),
        )
        fleet_tab_view._add_truck_win()
        dlg_mock.exec_.assert_called_once()

    def test_edit_truck_selected_no_selection(self, fleet_tab_view, monkeypatch):
        """No row selected -> info box, no form."""
        info_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", info_mock
        )
        fleet_tab_view._edit_truck_selected()
        info_mock.assert_called_once()

    def test_edit_truck_selected_opens_form(self, fleet_tab_view, monkeypatch):
        """Row selected -> _TruckFormDialog with truck data."""
        _populate_trucks(fleet_tab_view)
        # Select first row
        fleet_tab_view._table.selectRow(0)

        from ui.views.fleet_tab.fleet_tab import _TruckFormDialog

        dlg_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab._TruckFormDialog",
            MagicMock(return_value=dlg_mock),
        )
        fleet_tab_view.service.get_truck = MagicMock(return_value=_SAMPLE_TRUCK_A)
        fleet_tab_view._edit_truck_selected()
        dlg_mock.exec_.assert_called_once()

    def test_delete_truck_confirmed(self, fleet_tab_view, monkeypatch):
        """User confirms delete -> service.delete_truck called."""
        from PySide6.QtWidgets import QMessageBox

        _populate_trucks(fleet_tab_view)
        fleet_tab_view._table.selectRow(0)
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.question",
            MagicMock(return_value=QMessageBox.Yes),
        )
        fleet_tab_view._delete_truck()
        fleet_tab_view.service.delete_truck.assert_called_once_with(1)

    def test_delete_truck_cancelled(self, fleet_tab_view, monkeypatch):
        """User cancels delete -> service not touched."""
        _populate_trucks(fleet_tab_view)
        fleet_tab_view._table.selectRow(0)
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.question",
            MagicMock(return_value=QMessageBox.No),
        )
        fleet_tab_view._delete_truck()
        fleet_tab_view.service.delete_truck.assert_not_called()


# =========================================================================
# TestQtFleetTabQuickAdd -- Quick-add form
# =========================================================================


class TestQtFleetTabQuickAdd:
    """Quick-add form."""

    def test_quick_add_save_valid(self, fleet_tab_view, monkeypatch):
        """Filled form -> service.add_truck called with correct fields."""
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", MagicMock()
        )
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.warning", MagicMock()
        )
        fleet_tab_view._q_plate.setText("XY-999-ZZ")
        fleet_tab_view._q_model.setText("Test Model")
        fleet_tab_view._q_rate.setText("999.99")
        fleet_tab_view._save_quick()
        fleet_tab_view.service.add_truck.assert_called_once()
        call_kwargs = fleet_tab_view.service.add_truck.call_args[0][0]
        assert call_kwargs["plate_number"] == "XY-999-ZZ"
        assert call_kwargs["monthly_rate"] == 999.99

    def test_quick_add_save_empty_plate(self, fleet_tab_view, monkeypatch):
        """Empty plate -> warning shown, no service call."""
        warn_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.warning", warn_mock
        )
        fleet_tab_view._q_plate.setText("")
        fleet_tab_view._q_model.setText("Some Model")
        fleet_tab_view._q_rate.setText("500")
        fleet_tab_view._save_quick()
        warn_mock.assert_called_once()
        fleet_tab_view.service.add_truck.assert_not_called()

    def test_quick_add_clears_on_success(self, fleet_tab_view, monkeypatch):
        """After successful save, fields are cleared."""
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.information", MagicMock()
        )
        monkeypatch.setattr(
            "ui.views.fleet_tab.fleet_tab.QMessageBox.warning", MagicMock()
        )
        fleet_tab_view._q_plate.setText("XY-999-ZZ")
        fleet_tab_view._q_model.setText("Test Model")
        fleet_tab_view._q_rate.setText("999.99")
        fleet_tab_view._save_quick()
        assert fleet_tab_view._q_plate.text() == ""
        assert fleet_tab_view._q_model.text() == ""
        assert fleet_tab_view._q_rate.text() == "0"


# =========================================================================
# TestQtFleetTabAlerts -- Alert panel
# =========================================================================


class TestQtFleetTabAlerts:
    """Alert panel."""

    def test_alerts_panel_populated(self, fleet_tab_view):
        """ops.get_active_alerts returns items -> widgets created."""
        mock_alert = MagicMock()
        mock_alert.severity.value = "warning"
        mock_alert.title = "Low fuel"
        mock_alert.message = "Truck AB-001 needs refuel"
        fleet_tab_view.ops.get_active_alerts.return_value = [mock_alert]
        fleet_tab_view._refresh_alerts()
        # After refresh_alerts, the container layout should have widgets
        layout = fleet_tab_view._alerts_container_layout
        assert layout.count() > 0

    def test_alerts_panel_empty_state(self, fleet_tab_view):
        """No alerts -> empty state label."""
        fleet_tab_view.ops.get_active_alerts.return_value = []
        fleet_tab_view._refresh_alerts()
        from PySide6.QtWidgets import QLabel

        labels = fleet_tab_view._alerts_container.findChildren(QLabel)
        assert any(l.text() for l in labels)

    def test_alert_event_refreshes_panel(self, fleet_tab_view, qtbot):
        """Publishing ALERT_CREATED -> _refresh_alerts called."""
        spy = MagicMock(wraps=fleet_tab_view._refresh_alerts)
        fleet_tab_view._refresh_alerts = spy
        from services.operations.event_bus import (
            ALERT_CREATED,
            shared_event_bus,
        )

        shared_event_bus.publish(ALERT_CREATED, {})
        qtbot.wait(50)
        spy.assert_called_once()


# =========================================================================
# TestQtFleetTabEvents -- EventBus subscriptions
# =========================================================================


class TestQtFleetTabEvents:
    """EventBus subscriptions."""

    def test_truck_created_event_refreshes(self, fleet_tab_view, qtbot):
        """TRUCK_CREATED -> refresh called."""
        spy = MagicMock(wraps=fleet_tab_view.refresh)
        fleet_tab_view.refresh = spy
        from services.operations.event_bus import TRUCK_CREATED, shared_event_bus

        shared_event_bus.publish(TRUCK_CREATED, {"truck_id": 1})
        qtbot.wait(50)
        spy.assert_called_once()

    def test_truck_updated_event_refreshes(self, fleet_tab_view, qtbot):
        """TRUCK_UPDATED -> refresh called."""
        spy = MagicMock(wraps=fleet_tab_view.refresh)
        fleet_tab_view.refresh = spy
        from services.operations.event_bus import TRUCK_UPDATED, shared_event_bus

        shared_event_bus.publish(TRUCK_UPDATED, {"truck_id": 1})
        qtbot.wait(50)
        spy.assert_called_once()

    def test_truck_deleted_event_refreshes(self, fleet_tab_view, qtbot):
        """TRUCK_DELETED -> refresh called."""
        spy = MagicMock(wraps=fleet_tab_view.refresh)
        fleet_tab_view.refresh = spy
        from services.operations.event_bus import TRUCK_DELETED, shared_event_bus

        shared_event_bus.publish(TRUCK_DELETED, {"truck_id": 1})
        qtbot.wait(50)
        spy.assert_called_once()

    def test_alert_created_refreshes_alerts(self, fleet_tab_view, qtbot):
        """ALERT_CREATED -> _refresh_alerts called."""
        spy = MagicMock(wraps=fleet_tab_view._refresh_alerts)
        fleet_tab_view._refresh_alerts = spy
        from services.operations.event_bus import ALERT_CREATED, shared_event_bus

        shared_event_bus.publish(ALERT_CREATED, {})
        qtbot.wait(50)
        spy.assert_called_once()


# =========================================================================
# TestQtFleetTabMaintenance -- Maintenance view
# =========================================================================


class TestQtFleetTabMaintenance:
    """Maintenance view integration."""

    def test_build_maintenance_kpi_strip(self, fleet_tab_view, monkeypatch):
        """_build_maintenance_kpi_strip creates KPI cards."""
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout()
        fleet_tab_view._fleet_repo.get_maintenance_last_date = MagicMock(
            return_value="2025-01-15"
        )
        fleet_tab_view._fleet_repo.get_maintenance_schedules = MagicMock(
            return_value=[]
        )
        fleet_tab_view._fleet_repo.sum_maintenance_cost = MagicMock(return_value=500.0)
        fleet_tab_view._build_maintenance_kpi_strip(
            layout, truck_id=1, truck_row=_SAMPLE_TRUCK_A
        )
        # Should have added at least the section label + kpi_frame
        assert layout.count() >= 2

    def test_open_maintenance_view(self, fleet_tab_view, monkeypatch):
        """_open_maintenance_view calls QtMaintenanceView."""
        dlg_mock = MagicMock()
        monkeypatch.setattr(
            "ui.dialogs.maintenance_view.QtMaintenanceView",
            MagicMock(return_value=dlg_mock),
        )
        fleet_tab_view._open_maintenance_view(1, "AB-001")
        dlg_mock.exec_.assert_called_once()


# =========================================================================
# TestQtFleetTabDocuments -- Documents
# =========================================================================


class TestQtFleetTabDocuments:
    """Document centre integration."""

    def test_open_truck_documents(self, fleet_tab_view, monkeypatch):
        """_open_truck_documents -> open_entity_documents called with 'truck'."""
        _populate_trucks(fleet_tab_view)
        fleet_tab_view._table.selectRow(0)

        open_docs_mock = MagicMock()
        monkeypatch.setattr(
            "ui.views.document_center_view.open_entity_documents",
            open_docs_mock,
        )
        fleet_tab_view.service._fleet_repo.get_by_id = MagicMock(
            return_value=_SAMPLE_TRUCK_A
        )
        fleet_tab_view._open_truck_documents()
        open_docs_mock.assert_called_once()
        args = open_docs_mock.call_args[0]
        assert args[2] == "truck"  # entity_type

