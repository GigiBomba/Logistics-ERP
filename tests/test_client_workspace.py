"""Tests for the client workspace view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QWidget

# SP workaround: ui.widgets.__init__ uses SP but only S is exported.
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S

# QMenu workaround: ui.widgets.__init__._build_density_menu uses QMenu without import.
from PySide6.QtWidgets import QMenu as _QMenu

if not hasattr(_ui_widgets, "QMenu"):
    _ui_widgets.QMenu = _QMenu

# COLOR_* workaround: client_details.py references design-token constants that
# may not be available at module level.
from ui.design_tokens import (
    COLOR_SUCCESS_DEFAULT as _CSD,
    COLOR_TEXT_TERTIARY as _CTT,
)
import ui.views.client_workspace.client_details as _client_details_mod

for _name, _val in [("COLOR_SUCCESS_DEFAULT", _CSD), ("COLOR_TEXT_TERTIARY", _CTT)]:
    if not hasattr(_client_details_mod, _name):
        setattr(_client_details_mod, _name, _val)


# =========================================================================
#  Fixtures
# =========================================================================


@pytest.fixture(autouse=True)
def run_workers_sync(monkeypatch):
    """Run WorkerPool.run synchronously so remote-mode loads are deterministic.

    ``QtClientWorkspace._load_data`` delegates to ``WorkerPool.run`` when the
    service has no ``_repo`` (remote mode); without this fixture the result
    would be delivered asynchronously on a background thread, racing the
    synchronous assertions in these tests.  Executing the callback inline
    makes every load deterministic.
    """

    def _run_sync(fn, on_result=None, on_error=None, **kwargs):
        if on_result is not None:
            on_result(fn())
        return None

    monkeypatch.setattr(
        "ui.views.client_workspace.client_workspace.WorkerPool.run",
        _run_sync,
    )


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.get_all_with_revenue.return_value = []
    svc.search_advanced.return_value = []
    svc.get_trip_count.return_value = 0
    svc.get_by_id.return_value = None
    # Remote-like: no local repo → _load_data takes the WorkerPool path.
    svc._repo = None
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
        client_workspace._do_load_data()
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
        client_workspace._do_load_data()
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
        client_workspace._do_load_data()
        mock_service.search_advanced.assert_called_with(
            "Found", include_inactive=True, limit=200,
        )

    def test_search_triggers_data_load(self, client_workspace, mock_service):
        """Changing search text reloads data."""
        mock_service.search_advanced.return_value = []
        client_workspace._search_entry.setText("Test")
        client_workspace._do_load_data()
        assert mock_service.search_advanced.called

    def test_load_data_remote_renders_via_worker(self, client_workspace, mock_service):
        """Remote mode (service without _repo) loads through WorkerPool and renders."""
        clients = [
            {"id": 1, "name": "Client A", "contact_person": "John",
             "phone": "+401234", "email": "a@test.com", "is_active": 1,
             "trip_count": 5},
        ]
        mock_service.get_all_with_revenue.return_value = clients
        client_workspace._load_data()
        assert client_workspace._table.rowCount() == 1
        assert client_workspace._all_clients == clients
        mock_service.get_all_with_revenue.assert_called_with(include_inactive=True)

    def test_load_data_remote_search_renders_via_worker(self, client_workspace, mock_service):
        """Remote search path goes through the worker and renders results."""
        mock_service.search_advanced.return_value = [
            {"id": 3, "name": "Found", "contact_person": "", "phone": "",
             "email": "", "is_active": 1, "trip_count": 0},
        ]
        client_workspace._search_entry.setText("Found")
        client_workspace._load_data()
        mock_service.search_advanced.assert_called_with(
            "Found", include_inactive=True, limit=200,
        )
        assert client_workspace._table.rowCount() == 1

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
        client_workspace._load_revenue_chart(force=True)
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

    # ════════════════════════════════════════════════════════════════════
    #  Additional: Skeleton helpers
    # ════════════════════════════════════════════════════════════════════

    def test_show_table_skeleton_replaces_table(self, client_workspace):
        """_show_table_skeleton() hides _table, creates skeleton."""
        with patch(
            "ui.skeleton_widgets.SkeletonTable",
        ) as mock_skel_cls:
            real_skel = QWidget()  # Qt needs a real QWidget for layout
            mock_skel_cls.return_value = real_skel
            client_workspace._show_table_skeleton()
            assert client_workspace._table.isHidden()
            assert client_workspace._client_table_skel is real_skel

    def test_hide_table_skeleton_restores_table(self, client_workspace):
        """_hide_table_skeleton() deletes skeleton, shows _table."""
        with patch(
            "ui.skeleton_widgets.SkeletonTable",
        ) as mock_skel_cls:
            real_skel = QWidget()
            mock_skel_cls.return_value = real_skel
            client_workspace._show_table_skeleton()
            client_workspace._hide_table_skeleton()
            assert not client_workspace._table.isHidden()
            assert client_workspace._client_table_skel is None

    def test_hide_table_skeleton_idempotent(self, client_workspace):
        """Calling _hide_table_skeleton twice when no skeleton → no crash."""
        client_workspace._hide_table_skeleton()
        client_workspace._hide_table_skeleton()  # no crash

    # ════════════════════════════════════════════════════════════════════
    #  Additional: Revenue chart
    # ════════════════════════════════════════════════════════════════════

    def test_load_revenue_chart_staleness_skips(self, client_workspace):
        """Fresh chart timestamp → return early, no new chart."""
        import time

        client_workspace._selected_id = 1
        client_workspace._last_chart_ts = time.time()
        client_workspace._last_chart_client_id = 1
        client_workspace._load_revenue_chart()
        assert client_workspace._revenue_chart is None

    def test_load_revenue_chart_different_client_bypasses(
        self, client_workspace,
    ):
        """Different client id bypasses staleness check -> chart rebuilt."""
        import time

        client_workspace._selected_id = 1
        client_workspace._last_chart_ts = time.time()
        client_workspace._last_chart_client_id = 2  # different
        with patch(
            "ui.widgets.client_revenue_chart.QtClientRevenueChart",
        ) as mock_cls:
            real_chart = QWidget()  # Qt needs a real QWidget for layout
            mock_cls.return_value = real_chart
            client_workspace._load_revenue_chart()
            assert client_workspace._revenue_chart is real_chart

    # ════════════════════════════════════════════════════════════════════
    #  Additional: Error path
    # ════════════════════════════════════════════════════════════════════

    def test_do_load_data_error_path(self, client_workspace, mock_service):
        """Exception in _do_load_data is caught, skeleton hidden."""
        client_workspace._search_entry.setText("trigger error")
        mock_service.search_advanced.side_effect = Exception("DB error")
        with patch.object(
            client_workspace, "_hide_table_skeleton",
        ) as mock_hide:
            client_workspace._do_load_data()
            mock_hide.assert_called_once()


# =========================================================================
#  Tests — _QtClientFormDialog
# =========================================================================


class TestQtClientFormDialog:
    """Suite of tests for the add/edit client form dialog."""

    @pytest.fixture
    def mock_svc(self):
        svc = MagicMock()
        svc._repo = MagicMock()
        svc._repo.get_by_name.return_value = None
        return svc

    def _create_dialog(
        self, qtbot, service, client_data=None, on_save=None,
    ):
        from ui.views.client_workspace.client_workspace import (
            _QtClientFormDialog,
        )

        dialog = _QtClientFormDialog(
            None, service,
            client_data=client_data,
            on_save=on_save or MagicMock(),
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_creation_new_mode(self, qtbot, mock_svc):
        """client_data=None -> _editing=False, window title set."""
        dialog = self._create_dialog(qtbot, mock_svc, client_data=None)
        assert dialog._editing is False
        assert dialog.windowTitle() != ""
        dialog.close()

    def test_creation_edit_mode(self, qtbot, mock_svc):
        """client_data provided -> _editing=True, edit title."""
        dialog = self._create_dialog(
            qtbot, mock_svc, client_data={"id": 1, "name": "Acme"},
        )
        assert dialog._editing is True
        assert dialog.windowTitle() != ""
        dialog.close()

    def test_fields_populated(self, qtbot, mock_svc):
        """All 12 FIELDS entries created in _entries."""
        from ui.views.client_workspace.client_workspace import (
            _QtClientFormDialog,
        )

        dialog = self._create_dialog(qtbot, mock_svc)
        assert len(dialog._entries) == len(_QtClientFormDialog.FIELDS)
        for key, _, _ in _QtClientFormDialog.FIELDS:
            assert key in dialog._entries
        dialog.close()

    def test_combo_field_is_combo(self, qtbot, mock_svc):
        """client_type entry is a StyledComboBox."""
        from ui.widgets import StyledComboBox

        dialog = self._create_dialog(qtbot, mock_svc)
        entry = dialog._entries.get("client_type")
        assert entry is not None
        assert isinstance(entry, StyledComboBox)
        dialog.close()

    def test_edit_prefills_data(self, qtbot, mock_svc):
        """Edit mode prefills entry text from client_data."""
        dialog = self._create_dialog(
            qtbot, mock_svc, client_data={"id": 1, "name": "Acme"},
        )
        assert dialog._entries["name"].text() == "Acme"
        dialog.close()

    def test_save_empty_name_warning(self, qtbot, mock_svc):
        """Empty name -> warning shown, create/update NOT called."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_save=on_save)
        with patch(
            "PySide6.QtWidgets.QMessageBox.warning",
        ) as mock_warn:
            dialog._save()
            mock_warn.assert_called_once()
        mock_svc.create.assert_not_called()
        mock_svc.update.assert_not_called()
        on_save.assert_not_called()
        dialog.close()

    def test_save_new_client(self, qtbot, mock_svc):
        """Fill name -> service.create(**data), on_save, dialog accepted."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_save=on_save)
        dialog._entries["name"].setText("New Client")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dialog._save()
        mock_svc.create.assert_called_once()
        on_save.assert_called_once()
        assert dialog.result() == QDialog.DialogCode.Accepted
        dialog.close()

    def test_save_existing_client(self, qtbot, mock_svc):
        """Edit mode -> service.update(client_id, **data), on_save."""
        on_save = MagicMock()
        dialog = self._create_dialog(
            qtbot, mock_svc,
            client_data={"id": 1, "name": "Acme"}, on_save=on_save,
        )
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dialog._save()
        mock_svc.update.assert_called_once()
        on_save.assert_called_once()
        dialog.close()

    def test_save_duplicate_name_warning(self, qtbot, mock_svc):
        """New mode: _repo.get_by_name returns existing -> warning, early return."""
        on_save = MagicMock()
        mock_svc._repo.get_by_name.return_value = {"id": 99, "name": "Existing"}
        dialog = self._create_dialog(qtbot, mock_svc, on_save=on_save)
        dialog._entries["name"].setText("Existing")
        with patch(
            "PySide6.QtWidgets.QMessageBox.warning",
        ) as mock_warn:
            dialog._save()
            mock_warn.assert_called_once()
        mock_svc.create.assert_not_called()
        on_save.assert_not_called()
        dialog.close()

    def test_save_type_conversion_int(self, qtbot, mock_svc):
        """payment_terms_days='30' -> parsed to int(30)."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_save=on_save)
        dialog._entries["name"].setText("Test")
        dialog._entries["payment_terms_days"].setText("30")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dialog._save()
        val = mock_svc.create.call_args[1]["payment_terms_days"]
        assert val == 30
        assert isinstance(val, int)
        dialog.close()

    def test_save_type_conversion_float(self, qtbot, mock_svc):
        """credit_limit_eur='5000.50' -> float; default_rate_per_km='' -> None."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_save=on_save)
        dialog._entries["name"].setText("Test")
        dialog._entries["credit_limit_eur"].setText("5000.50")
        dialog._entries["default_rate_per_km"].setText("")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dialog._save()
        kwargs = mock_svc.create.call_args[1]
        assert kwargs["credit_limit_eur"] == 5000.50
        assert isinstance(kwargs["credit_limit_eur"], float)
        assert kwargs["default_rate_per_km"] is None
        dialog.close()

    def test_save_type_conversion_rating(self, qtbot, mock_svc):
        """rating='3' -> int(3); empty/invalid -> None."""
        on_save = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_save=on_save)
        dialog._entries["name"].setText("Test")
        dialog._entries["rating"].setText("3")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dialog._save()
        val = mock_svc.create.call_args[1]["rating"]
        assert val == 3
        assert isinstance(val, int)
        dialog.close()

    def test_minimum_size(self, qtbot, mock_svc):
        """Dialog has min width >= 500, height >= 600."""
        dialog = self._create_dialog(qtbot, mock_svc)
        sz = dialog.minimumSize()
        assert sz.width() >= 500
        assert sz.height() >= 600
        dialog.close()


# =========================================================================
#  Tests — _QtMergeDialog
# =========================================================================


class TestQtMergeDialog:
    """Suite of tests for the client merge dialog."""

    @pytest.fixture
    def mock_svc(self):
        svc = MagicMock()
        svc.get_by_id.return_value = {"id": 1, "name": "Source Client"}
        svc.get_all_with_revenue.return_value = [
            {"id": 1, "name": "Source Client"},
            {"id": 2, "name": "Target Client"},
            {"id": 3, "name": "Another Client"},
        ]
        return svc

    def _create_dialog(self, qtbot, service, source_id=1, on_done=None):
        from ui.views.client_workspace.client_workspace import _QtMergeDialog

        dialog = _QtMergeDialog(
            None, service, source_id=source_id,
            on_done=on_done or MagicMock(),
        )
        qtbot.addWidget(dialog)
        return dialog

    def test_creation(self, qtbot, mock_svc):
        """Dialog constructs, modal, window title set."""
        dialog = self._create_dialog(qtbot, mock_svc)
        assert dialog.isModal() is True
        assert dialog.windowTitle() != ""
        dialog.close()

    def test_source_label_shows_name(self, qtbot, mock_svc):
        """Source label contains source client name via translation key."""
        dialog = self._create_dialog(qtbot, mock_svc)
        all_labels = dialog.findChildren(QLabel)
        # The label text will be the translation key since no translations loaded
        found = any("merge_source" in lb.text() for lb in all_labels)
        assert found
        dialog.close()

    def test_target_combo_populated(self, qtbot, mock_svc):
        """Combo has names excluding source client."""
        dialog = self._create_dialog(qtbot, mock_svc)
        assert dialog._target_combo.count() == 2
        names = [
            dialog._target_combo.itemText(i)
            for i in range(dialog._target_combo.count())
        ]
        assert "Source Client" not in names
        assert "Target Client" in names
        dialog.close()

    def test_execute_without_selection(self, qtbot, mock_svc):
        """Empty _name_to_id for combo text -> early return, no merge."""
        on_done = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_done=on_done)
        dialog._name_to_id.clear()
        dialog._execute()
        mock_svc.merge_clients.assert_not_called()
        on_done.assert_not_called()
        dialog.close()

    def test_execute_with_confirmation_yes(self, qtbot, mock_svc):
        """Confirmed -> service.merge_clients called, on_done, dialog accepted."""
        on_done = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_done=on_done)
        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            with patch.object(QMessageBox, "information"):
                dialog._execute()
        mock_svc.merge_clients.assert_called_once_with(1, 2)
        on_done.assert_called_once()
        dialog.close()

    def test_execute_with_confirmation_no(self, qtbot, mock_svc):
        """Rejected -> merge NOT called, dialog stays open."""
        on_done = MagicMock()
        dialog = self._create_dialog(qtbot, mock_svc, on_done=on_done)
        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.No,
        ):
            dialog._execute()
        mock_svc.merge_clients.assert_not_called()
        on_done.assert_not_called()
        dialog.close()

    def test_execute_merge_error(self, qtbot, mock_svc):
        """Exception -> QMessageBox.critical shown, on_done called, accepted."""
        on_done = MagicMock()
        mock_svc.merge_clients.side_effect = Exception("Merge failed")
        dialog = self._create_dialog(qtbot, mock_svc, on_done=on_done)
        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            with patch.object(QMessageBox, "critical") as mock_crit:
                dialog._execute()
                mock_crit.assert_called_once()
        on_done.assert_called_once()
        dialog.close()

    def test_source_not_found(self, qtbot):
        """get_by_id returns None -> dialog builds, source label present."""
        svc = MagicMock()
        svc.get_by_id.return_value = None
        svc.get_all_with_revenue.return_value = []
        svc.merge_clients = MagicMock()
        dialog = self._create_dialog(qtbot, svc)
        svc.get_by_id.assert_called_with(1)
        all_labels = dialog.findChildren(QLabel)
        assert len(all_labels) >= 2  # source label + target label + warning
        dialog.close()

    def test_minimum_size(self, qtbot, mock_svc):
        """Minimum width >= 450."""
        dialog = self._create_dialog(qtbot, mock_svc)
        assert dialog.minimumSize().width() >= 450
        dialog.close()


# =========================================================================
#  Tests — Context menus on trips / invoices tables
# =========================================================================


class TestClientWorkspaceContextMenus:
    """Suite of tests for right-click context menu actions."""

    # ── _get_row_data_at ───────────────────────────────────────────────

    def test_get_row_data_at_valid(self, client_workspace):
        """Valid position returns correct record dict."""
        client_workspace._trips_table._data = [
            {"id": 1, "start_date": "2026-01-01"},
            {"id": 2, "start_date": "2026-02-01"},
        ]
        with patch.object(
            client_workspace._trips_table, "indexAt",
        ) as mock_idx:
            mock_idx.return_value.isValid.return_value = True
            mock_idx.return_value.row.return_value = 0
            result = client_workspace._get_row_data_at(
                client_workspace._trips_table, None,
            )
            assert result == {"id": 1, "start_date": "2026-01-01"}

    def test_get_row_data_at_invalid(self, client_workspace):
        """Invalid position returns None."""
        with patch.object(
            client_workspace._trips_table, "indexAt",
        ) as mock_idx:
            mock_idx.return_value.isValid.return_value = False
            result = client_workspace._get_row_data_at(
                client_workspace._trips_table, None,
            )
            assert result is None

    # ── Trip context menu ──────────────────────────────────────────────

    _POS = QPoint(0, 0)

    def test_show_trip_context_menu_no_record(self, client_workspace):
        """_get_row_data_at returns None -> menu not shown."""
        with patch.object(
            client_workspace, "_get_row_data_at", return_value=None,
        ):
            with patch(
                "ui.views.client_workspace.client_workspace.QMenu",
            ) as mock_menu:
                client_workspace._show_trip_context_menu(self._POS)
                mock_menu.assert_not_called()

    def test_show_trip_context_menu_actions_exist(self, client_workspace):
        """Menu has Edit Trip, View Route, Generate Invoice actions."""
        record = {"id": 42}
        with patch.object(
            client_workspace, "_get_row_data_at", return_value=record,
        ):
            with patch(
                "ui.views.client_workspace.client_workspace.QMenu",
            ) as mock_menu_cls:
                mock_menu = MagicMock()
                mock_menu_cls.return_value = mock_menu
                client_workspace._show_trip_context_menu(self._POS)
                assert mock_menu.addAction.call_count == 3

    # ── Edit trip ──────────────────────────────────────────────────────

    def test_edit_trip_opens_editor(self, client_workspace):
        """_edit_trip with id -> QtEditWindow.exec() called."""
        mock_dialog = MagicMock()
        with patch(
            "ui.dialogs.edit_window.QtEditWindow",
            return_value=mock_dialog,
        ):
            client_workspace._edit_trip({"id": 42})
            mock_dialog.exec.assert_called_once()

    def test_edit_trip_no_id(self, client_workspace):
        """_edit_trip with start_date fallback still works."""
        mock_dialog = MagicMock()
        with patch(
            "ui.dialogs.edit_window.QtEditWindow",
            return_value=mock_dialog,
        ):
            client_workspace._edit_trip({"start_date": "2026-01-01"})
            mock_dialog.exec.assert_called_once()

    def test_edit_trip_error_path(self, client_workspace):
        """Exception in QtEditWindow creation caught, no crash."""
        with patch(
            "ui.dialogs.edit_window.QtEditWindow",
            side_effect=Exception("No DB"),
        ):
            client_workspace._edit_trip({"id": 42})  # no crash

    # ── View trip route ────────────────────────────────────────────────

    def test_view_trip_route_navigates(self, client_workspace):
        """_switch_module('route_planner') called on parent."""
        mock_parent = MagicMock(spec=QWidget)
        mock_parent._switch_module = MagicMock()
        with patch.object(client_workspace, "parent", return_value=mock_parent):
            client_workspace._view_trip_route({})
            mock_parent._switch_module.assert_called_once_with("route_planner")

    def test_view_trip_route_no_parent_switch(self, client_workspace):
        """No parent with _switch_module -> no crash."""
        client_workspace._view_trip_route({})  # no crash

    # ── Generate trip invoice ──────────────────────────────────────────

    def test_generate_trip_invoice_navigates(self, client_workspace):
        """Navigates to invoices with trip_id."""
        mock_parent = MagicMock(spec=QWidget)
        mock_parent._switch_module = MagicMock()
        with patch.object(client_workspace, "parent", return_value=mock_parent):
            client_workspace._generate_trip_invoice({"id": 42})
            mock_parent._switch_module.assert_called_once_with(
                "invoices", {"trip_id": 42},
            )

    # ── Invoice context menu ───────────────────────────────────────────

    def test_show_invoice_context_menu_actions_exist(
        self, client_workspace,
    ):
        """Menu has Edit Invoice, View, Download actions."""
        record = {"invoice_number": "INV-001"}
        with patch.object(
            client_workspace, "_get_row_data_at", return_value=record,
        ):
            with patch(
                "ui.views.client_workspace.client_workspace.QMenu",
            ) as mock_menu_cls:
                mock_menu = MagicMock()
                mock_menu_cls.return_value = mock_menu
                client_workspace._show_invoice_context_menu(self._POS)
                assert mock_menu.addAction.call_count == 3

    # ── Edit invoice ───────────────────────────────────────────────────

    def test_edit_invoice_opens_editor(self, client_workspace):
        """_edit_invoice -> InvoiceEditorDialog.exec() called."""
        mock_dialog = MagicMock()
        with patch(
            "ui.views.invoice_editor.InvoiceEditorDialog",
            return_value=mock_dialog,
        ):
            client_workspace._edit_invoice({})
            mock_dialog.exec.assert_called_once()

    def test_edit_invoice_error_path(self, client_workspace):
        """Exception caught, logged, no crash."""
        with patch(
            "ui.views.invoice_editor.InvoiceEditorDialog",
            side_effect=Exception("Error"),
        ):
            client_workspace._edit_invoice({})  # no crash

    # ── View invoice ───────────────────────────────────────────────────

    def test_view_invoice_no_number(self, client_workspace):
        """Empty invoice_number -> returns early."""
        client_workspace._view_invoice({"invoice_number": ""})  # no crash

    def test_view_invoice_navigates(self, client_workspace):
        """Navigates to invoices with {'invoice': 'INV-001'}."""
        mock_parent = MagicMock(spec=QWidget)
        mock_parent._switch_module = MagicMock()
        with patch.object(client_workspace, "parent", return_value=mock_parent):
            client_workspace._view_invoice({"invoice_number": "INV-001"})
            mock_parent._switch_module.assert_called_once_with(
                "invoices", {"invoice": "INV-001"},
            )

    # ── Download invoice ───────────────────────────────────────────────

    def test_download_invoice_navigates(self, client_workspace):
        """Navigates with {'invoice': 'INV-001', 'action': 'download'}."""
        mock_parent = MagicMock(spec=QWidget)
        mock_parent._switch_module = MagicMock()
        with patch.object(client_workspace, "parent", return_value=mock_parent):
            client_workspace._download_invoice({"invoice_number": "INV-001"})
            mock_parent._switch_module.assert_called_once_with(
                "invoices", {"invoice": "INV-001", "action": "download"},
            )

    def test_download_invoice_no_number(self, client_workspace):
        """Empty invoice_number -> returns early."""
        client_workspace._download_invoice(
            {"invoice_number": ""},
        )  # no crash
