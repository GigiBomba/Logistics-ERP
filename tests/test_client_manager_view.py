"""Tests for QtClientManager — client CRUD view.

Form-dialog tests are in ``test_client_form_dialog.py`` to avoid Qt
event-loop interference when both are run in the same session.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client_service():
    svc = MagicMock()
    svc.get_all.return_value = []
    svc.search.return_value = []
    svc.get_trip_count.return_value = 0
    return svc


@pytest.fixture
def client_manager(qtbot, mock_client_service):
    """Create QtClientManager with mocked client_service."""
    from ui.views.client_manager import QtClientManager

    widget = QtClientManager(
        parent=None,
        db=MagicMock(),
        prefs={},
        client_service=mock_client_service,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()


# =========================================================================
# Tests — QtClientManager
# =========================================================================


class TestQtClientManager:
    """Suite of tests for the client management view."""

    # ── Initialisation ─────────────────────────────────────────────────

    def test_initialization(self, client_manager):
        """Widget constructs without crashing."""
        assert client_manager is not None
        assert client_manager.service is not None

    def test_title_label(self, client_manager):
        """Page title label exists."""
        assert hasattr(client_manager, "_title_label")
        assert client_manager._title_label is not None

    def test_search_entry_exists(self, client_manager):
        """Debounced search input exists."""
        assert hasattr(client_manager, "_search_entry")
        assert client_manager._search_entry is not None

    def test_table_widget_exists(self, client_manager):
        """Styled table widget exists."""
        assert hasattr(client_manager, "table")
        assert client_manager.table is not None

    def test_action_buttons_exist(self, client_manager):
        """New, edit, and deactivate buttons are present."""
        assert hasattr(client_manager, "_new_btn")
        assert hasattr(client_manager, "_edit_btn")
        assert hasattr(client_manager, "_deact_btn")

    def test_initial_data_load(self, client_manager, mock_client_service):
        """Data is loaded on construction."""
        mock_client_service.get_all.assert_called_once()

    # ── Table columns ──────────────────────────────────────────────────

    def test_table_has_columns(self, client_manager):
        """Table has the expected number of columns."""
        assert client_manager.table.columnCount() >= 5

    # ── Data loading ───────────────────────────────────────────────────

    def test_load_data_empty(self, client_manager, mock_client_service):
        """_load_data handles empty dataset."""
        mock_client_service.get_all.return_value = []
        client_manager._load_data()
        assert client_manager.table.rowCount() == 0

    def test_load_data_with_clients(self, client_manager, mock_client_service):
        """_load_data populates table with client data."""
        mock_client_service.get_all.return_value = [
            {"id": 1, "name": "Client A", "contact_person": "John",
             "phone": "+401234", "email": "a@test.com", "is_active": 1},
            {"id": 2, "name": "Client B", "contact_person": "Jane",
             "phone": "+405678", "email": "b@test.com", "is_active": 1},
        ]
        mock_client_service.get_trip_count.return_value = 3
        client_manager._load_data()
        assert client_manager.table.rowCount() == 2

    def test_search_triggers_data_load(self, client_manager, mock_client_service):
        """Changing search text reloads data via debounce."""
        mock_client_service.search.return_value = [
            {"id": 3, "name": "Found", "contact_person": "", "phone": "",
             "email": "", "is_active": 1},
        ]
        mock_client_service.get_trip_count.return_value = 0
        client_manager._search_entry.setText("Found")
        # The debounced signal fires eventually; call _load_data directly
        client_manager._on_search_changed()
        # Should have called search instead of get_all
        mock_client_service.search.assert_called_with("Found", limit=200)

    # ── Selection ──────────────────────────────────────────────────────

    def test_on_row_selected_sets_id(self, client_manager):
        """Row selection stores the selected client ID."""
        client_manager._on_row_selected({"id": 42})
        assert client_manager._selected_id == 42

    def test_on_row_double_clicked_opens_edit(self, client_manager):
        """Double-click on a row opens the edit form."""
        client_manager._selected_id = 42
        with patch.object(client_manager, "_open_form_edit") as mock_edit:
            client_manager._on_row_double_clicked({"id": 42})
            mock_edit.assert_called_once()

    # ── i18n ───────────────────────────────────────────────────────────

    def test_language_callback_registered(self, client_manager):
        """i18n listener is registered."""
        assert client_manager._language_callback is not None

    def test_update_translations_does_not_crash(self, client_manager):
        """_update_translations refreshes labels without error."""
        client_manager._update_translations()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_shutdown_does_not_crash(self, client_manager):
        """shutdown unregisters the listener."""
        client_manager.shutdown()
        assert client_manager._listener_registered is False

    def test_wakeup_reloads_data(self, client_manager, mock_client_service):
        """wakeup triggers data reload."""
        mock_client_service.get_all.reset_mock()
        client_manager.wakeup()
        mock_client_service.get_all.assert_called()

    def test_cleanup_on_destroy(self, client_manager):
        """destroyed signal triggers _cleanup."""
        client_manager._cleanup()
        # no crash

    # ── Deactivation ───────────────────────────────────────────────────

    def test_deactivate_no_selection(self, client_manager):
        """_deactivate returns early when no row selected."""
        client_manager._selected_id = None
        client_manager._deactivate()  # should not crash

    def test_deactivate_no_service(self, client_manager):
        """_deactivate returns early when service is None."""
        client_manager.service = None
        client_manager._selected_id = 1
        client_manager._deactivate()  # should not crash
