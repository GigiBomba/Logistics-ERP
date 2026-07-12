"""Tests for the client workspace view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QMessageBox


# =========================================================================
#  Fixtures
# =========================================================================


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.get_all_with_revenue.return_value = []
    svc.search_advanced.return_value = []
    svc.get_trip_count.return_value = 0
    svc.get_by_id.return_value = None
    return svc


@pytest.fixture
def client_workspace(qtbot, mock_service):
    """Create QtClientWorkspace with mocked dependencies."""

    view = __import__(
        "ui.views.client_workspace", fromlist=["QtClientWorkspace"],
    ).QtClientWorkspace(
        parent=None, db=MagicMock(), prefs=MagicMock(),
        ops=MagicMock(), client_service=mock_service,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


# =========================================================================
#  Tests — QtClientWorkspace
# =========================================================================


class TestQtClientWorkspace:
    """Suite of tests for the client workspace view."""

    # ── Initialisation ─────────────────────────────────────────────────

    def test_creation(self, client_workspace):
        """Widget constructs without crashing."""
        assert client_workspace.db is not None

    def test_client_table_created(self, client_workspace):
        """Client table widget exists."""
        assert hasattr(client_workspace, "_table")

    def test_search_bar_created(self, client_workspace):
        """Debounced search input exists."""
        assert hasattr(client_workspace, "_search_entry")

    def test_detail_tabs_created(self, client_workspace):
        """Per-client detail tabs exist with at least the expected tabs."""
        assert hasattr(client_workspace, "_client_tabs")
        # Details, Trips, Invoices, Revenue
        assert client_workspace._client_tabs.count() >= 3

    def test_client_table_widget(self, client_workspace):
        """Client table is a StyledTableWidget."""
        from ui.widgets import StyledTableWidget

        assert isinstance(client_workspace._table, StyledTableWidget)

    def test_add_client_button_exists(self, client_workspace):
        """Add/new button exists."""
        assert hasattr(client_workspace, "_new_btn")

    def test_outer_tabs_created(self, client_workspace):
        """Outer Manager/AutoMail tabs exist."""
        assert hasattr(client_workspace, "_tabs")
        assert client_workspace._tabs.count() >= 2

    def test_details_tab_widget(self, client_workspace):
        """_details_tab is an instance of _QtClientDetailsTab."""
        from ui.views.client_workspace.client_details import _QtClientDetailsTab

        assert isinstance(client_workspace._details_tab, _QtClientDetailsTab)

    def test_edit_and_deactivate_buttons(self, client_workspace):
        """Edit and deactivate buttons are present."""
        assert hasattr(client_workspace, "_edit_btn")
        assert hasattr(client_workspace, "_deact_btn")

    def test_detail_tabs_disabled_initially(self, client_workspace):
        """Detail tabs are disabled until a client is selected."""
        assert client_workspace._client_tabs.isEnabled() is False

    def test_title_label_exists(self, client_workspace):
        """Page title label exists."""
        assert hasattr(client_workspace, "_title_label")

    # ── Data loading ───────────────────────────────────────────────────

    def test_load_data_empty(self, client_workspace, mock_service):
        """_load_data handles empty dataset."""
        mock_service.get_all_with_revenue.return_value = []
        client_workspace._load_data()
        assert client_workspace._table.rowCount() == 0

    def test_load_data_with_clients(self, client_workspace, mock_service):
        """_load_data populates table with client data."""
        mock_service.get_all_with_revenue.return_value = [
            {"id": 1, "name": "Client A", "contact_person": "John",
             "phone": "+401234", "email": "a@test.com", "is_active": 1,
             "trip_count": 5},
            {"id": 2, "name": "Client B", "contact_person": "Jane",
             "phone": "+405678", "email": "b@test.com", "is_active": 1,
             "trip_count": 3},
        ]
        client_workspace._load_data()
        assert client_workspace._table.rowCount() == 2

    def test_load_data_no_service(self, client_workspace):
        """_load_data returns early when service is None."""
        client_workspace.service = None
        client_workspace._load_data()  # should not crash

    def test_load_data_with_search(self, client_workspace, mock_service):
        """_load_data uses search_advanced when query is present."""
        mock_service.search_advanced.return_value = [
            {"id": 3, "name": "Found", "contact_person": "", "phone": "",
             "email": "", "is_active": 1, "trip_count": 0},
        ]
        client_workspace._search_entry.setText("Found")
        client_workspace._on_search_changed()
        mock_service.search_advanced.assert_called_with(
            "Found", include_inactive=True, limit=200,
        )

    def test_search_triggers_data_load(self, client_workspace, mock_service):
        """Changing search text reloads data."""
        mock_service.search_advanced.return_value = []
        client_workspace._search_entry.setText("Test")
        client_workspace._on_search_changed()
        assert mock_service.search_advanced.called

    # ── Selection ──────────────────────────────────────────────────────

    def test_on_row_selected_sets_id(self, client_workspace, mock_service):
        """Row selection stores the selected client ID."""
        mock_service.get_client_dashboard = MagicMock(return_value={
            "client": {"id": 42}, "contacts": [], "tags": [],
        })
        mock_service.get_client_trips = MagicMock(return_value=[])
        mock_service.get_client_invoices = MagicMock(return_value=[])
        client_workspace._on_row_selected({"id": 42})
        assert client_workspace._selected_id == 42

    def test_on_row_double_clicked_opens_edit(self, client_workspace):
        """Double-click on a row opens the edit form."""
        client_workspace._selected_id = 42
        with patch.object(client_workspace, "_open_form_edit") as mock_edit:
            client_workspace._on_row_double_clicked({"id": 42})
            mock_edit.assert_called_once()

    # ── Detail display ─────────────────────────────────────────────────

    def test_show_detail_with_none(self, client_workspace):
        """_show_detail with None disables detail tabs."""
        client_workspace._client_tabs.setEnabled(True)
        client_workspace._show_detail(None)
        assert client_workspace._client_tabs.isEnabled() is False

    def test_show_detail_with_id(self, client_workspace, mock_service):
        """_show_detail with valid id enables detail tabs."""
        mock_service.get_client_dashboard = MagicMock(return_value={
            "client": {"id": 1}, "contacts": [], "tags": [],
        })
        mock_service.get_client_trips = MagicMock(return_value=[])
        mock_service.get_client_invoices = MagicMock(return_value=[])
        client_workspace._selected_id = 1
        client_workspace._show_detail(1)
        assert client_workspace._client_tabs.isEnabled() is True

    def test_show_detail_without_service(self, client_workspace):
        """_show_detail returns early when service is None."""
        client_workspace.service = None
        client_workspace._client_tabs.setEnabled(True)
        client_workspace._show_detail(1)
        assert client_workspace._client_tabs.isEnabled() is False

    # ── Tab switching ──────────────────────────────────────────────────

    def test_on_client_tab_changed_details(self, client_workspace, mock_service):
        """Switching to details tab refreshes details."""
        mock_service.get_client_dashboard = MagicMock(return_value={
            "client": {"id": 1}, "contacts": [], "tags": [],
        })
        client_workspace._selected_id = 1
        with patch.object(
            client_workspace._details_tab, "refresh",
        ) as mock_refresh:
            client_workspace._on_client_tab_changed(0)
            mock_refresh.assert_called_with(client_workspace.service, 1)

    def test_on_client_tab_changed_trips(self, client_workspace, mock_service):
        """Switching to trips tab loads trips."""
        mock_service.get_client_trips.return_value = []
        client_workspace._selected_id = 1
        client_workspace._on_client_tab_changed(1)
        mock_service.get_client_trips.assert_called_with(1, limit=100)

    def test_on_client_tab_changed_invoices(self, client_workspace, mock_service):
        """Switching to invoices tab loads invoices."""
        mock_service.get_client_invoices.return_value = []
        client_workspace._selected_id = 1
        client_workspace._on_client_tab_changed(2)
        mock_service.get_client_invoices.assert_called_with(1, limit=100)

    def test_on_client_tab_changed_no_selection(self, client_workspace):
        """Tab change returns early when no client selected."""
        client_workspace._selected_id = None
        client_workspace._on_client_tab_changed(0)  # should not crash

    # ── Data loading helpers (trips, invoices) ─────────────────────────

    def test_load_trips(self, client_workspace, mock_service):
        """_load_trips fetches trips and populates the table."""
        mock_service.get_client_trips.return_value = [
            {"start_date": "2026-01-15", "truck_number": "AB-01",
             "distance_km": 500, "total_price_eur": 2500,
             "net_profit": 500, "status": "completed"},
        ]
        client_workspace._selected_id = 1
        client_workspace._load_trips()
        assert client_workspace._trips_table.rowCount() == 1

    def test_load_trips_no_selection(self, client_workspace):
        """_load_trips returns early without selected id."""
        client_workspace._selected_id = None
        client_workspace._load_trips()  # should not crash

    def test_load_invoices(self, client_workspace, mock_service):
        """_load_invoices fetches invoices and populates the table."""
        mock_service.get_client_invoices.return_value = [
            {"invoice_number": "INV-001", "total_amount": 1500,
             "due_date": "2026-02-15", "status": "Paid"},
        ]
        client_workspace._selected_id = 1
        client_workspace._load_invoices()
        assert client_workspace._invoices_table.rowCount() == 1

    def test_load_invoices_no_selection(self, client_workspace):
        """_load_invoices returns early without selected id."""
        client_workspace._selected_id = None
        client_workspace._load_invoices()  # should not crash

    # ── Revenue chart ──────────────────────────────────────────────────

    def test_load_revenue_chart(self, client_workspace, mock_service):
        """_load_revenue_chart creates a revenue chart widget."""
        from ui.widgets.client_revenue_chart import QtClientRevenueChart

        client_workspace._selected_id = 1
        client_workspace._load_revenue_chart()
        assert client_workspace._revenue_chart is not None
        assert isinstance(client_workspace._revenue_chart, QtClientRevenueChart)

    def test_load_revenue_chart_no_selection(self, client_workspace):
        """_load_revenue_chart returns early without selected id."""
        client_workspace._selected_id = None
        client_workspace._load_revenue_chart()  # should not crash

    def test_load_revenue_chart_replaces_existing(self, client_workspace, mock_service):
        """_load_revenue_chart replaces an existing chart widget."""
        client_workspace._selected_id = 1
        client_workspace._load_revenue_chart()
        first_chart = client_workspace._revenue_chart
        client_workspace._load_revenue_chart()
        assert client_workspace._revenue_chart is not first_chart

    # ── CRUD actions ───────────────────────────────────────────────────

    def test_open_form_new(self, client_workspace):
        """_open_form_new opens client form dialog."""
        from ui.views.client_workspace.client_workspace import _QtClientFormDialog

        with patch.object(_QtClientFormDialog, "exec", return_value=0):
            client_workspace._open_form_new()
            # No crash

    def test_open_form_edit_no_selection(self, client_workspace):
        """_open_form_edit returns early when no client selected."""
        client_workspace._selected_id = None
        client_workspace._open_form_edit()  # should not crash

    def test_open_form_edit_no_service(self, client_workspace):
        """_open_form_edit returns early when service is None."""
        client_workspace._selected_id = 1
        client_workspace.service = None
        client_workspace._open_form_edit()  # should not crash

    def test_open_form_edit_no_client_data(self, client_workspace, mock_service):
        """_open_form_edit returns early when get_by_id returns None."""
        mock_service.get_by_id.return_value = None
        client_workspace._selected_id = 1
        client_workspace._open_form_edit()  # should not crash

    def test_open_form_edit_opens_dialog(self, client_workspace, mock_service):
        """_open_form_edit opens form dialog for existing client."""
        mock_service.get_by_id.return_value = {
            "id": 1, "name": "Test Client",
        }
        client_workspace._selected_id = 1
        with patch(
            "ui.views.client_workspace.client_workspace._QtClientFormDialog.exec",
            return_value=0,
        ):
            client_workspace._open_form_edit()
            # No crash

    def test_on_form_saved(self, client_workspace, mock_service):
        """_on_form_saved reloads data and refreshes detail."""
        mock_service.get_client_dashboard = MagicMock(return_value={
            "client": {"id": 1}, "contacts": [], "tags": [],
        })
        mock_service.get_all_with_revenue.return_value = []
        client_workspace._selected_id = 1
        client_workspace._on_form_saved()
        mock_service.get_all_with_revenue.assert_called()

    # ── Deactivation ───────────────────────────────────────────────────

    def test_deactivate_no_selection(self, client_workspace):
        """_deactivate returns early when no row selected."""
        client_workspace._selected_id = None
        client_workspace._deactivate()  # should not crash

    def test_deactivate_no_service(self, client_workspace):
        """_deactivate returns early when service is None."""
        client_workspace.service = None
        client_workspace._selected_id = 1
        client_workspace._deactivate()  # should not crash

    def test_deactivate_no_client_data(self, client_workspace, mock_service):
        """_deactivate returns early when get_by_id returns None."""
        mock_service.get_by_id.return_value = None
        client_workspace._selected_id = 1
        client_workspace._deactivate()  # should not crash

    def test_deactivate_cancelled(self, client_workspace, mock_service):
        """_deactivate does nothing when user cancels confirmation."""
        mock_service.get_by_id.return_value = {
            "id": 1, "name": "Acme",
        }
        mock_service.get_trip_count.return_value = 0
        client_workspace._selected_id = 1

        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.No):
            client_workspace._deactivate()
            mock_service.deactivate.assert_not_called()

    def test_deactivate_confirmed(self, client_workspace, mock_service):
        """_deactivate calls service.deactivate when confirmed."""
        mock_service.get_by_id.return_value = {
            "id": 1, "name": "Acme",
        }
        mock_service.get_trip_count.return_value = 0
        mock_service.get_all_with_revenue.return_value = []
        client_workspace._selected_id = 1

        with patch.object(QMessageBox, "question",
                          return_value=QMessageBox.StandardButton.Yes):
            client_workspace._deactivate()
            mock_service.deactivate.assert_called_with(1)
            assert client_workspace._selected_id is None
            assert client_workspace._client_tabs.isEnabled() is False

    # ── i18n ───────────────────────────────────────────────────────────

    def test_update_translations_does_not_crash(self, client_workspace):
        """_update_translations refreshes labels without error."""
        client_workspace._update_translations()

    def test_language_callback_registered(self, client_workspace):
        """i18n listener is registered."""
        assert client_workspace._language_callback is not None

    def test_on_language_changed(self, client_workspace, mock_service):
        """Language change triggers translation update and data reload."""
        mock_service.get_all_with_revenue.return_value = []
        client_workspace._on_language_changed("ro")
        mock_service.get_all_with_revenue.assert_called()

    # ── Outer tab management ───────────────────────────────────────────

    def test_on_outer_tab_changed(self, client_workspace):
        """Switching outer tabs does not crash."""
        client_workspace._on_outer_tab_changed(0)
        client_workspace._on_outer_tab_changed(1)

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_shutdown_cleanup(self, client_workspace):
        """shutdown cleans up without error."""
        client_workspace.shutdown()

    def test_wakeup_does_not_crash(self, client_workspace):
        """wakeup refreshes without crash."""
        client_workspace.wakeup()

    def test_cleanup_on_destroy(self, client_workspace):
        """destroyed signal triggers _cleanup."""
        client_workspace._cleanup()  # should not crash

    def test_shutdown_unregisters_listener(self, client_workspace):
        """shutdown sets listener_registered to False."""
        client_workspace.shutdown()
        assert client_workspace._listener_registered is False
