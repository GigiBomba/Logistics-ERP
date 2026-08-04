"""Tests for the bulk payments view (QtBulkPaymentsView)."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from models.common import ServiceResult


# ---------------------------------------------------------------------------
# Helper: build a mock model instance whose ``model_dump()`` returns *data*.
# ---------------------------------------------------------------------------

def _mock_model(data: dict):
    m = MagicMock()
    m.model_dump.return_value = data
    return m


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bulk_payments_view(qt_widget, qtbot):
    """Construct a QtBulkPaymentsView with mocked services."""
    db = MagicMock()
    prefs = {"default_currency": "EUR"}
    mod = __import__("ui.views.bulk_payments_view", fromlist=["QtBulkPaymentsView"])
    view = mod.QtBulkPaymentsView(qt_widget, db=db, prefs=prefs)
    qtbot.addWidget(view)

    # Replace real services with mocks so no database calls leak through
    view._client_service = MagicMock()
    view._driver_truck_service = MagicMock()
    view._profile_service = MagicMock()
    view._batch_service = MagicMock()

    # Patch blocking QMessageBox dialogs so tests do not hang
    import PySide6.QtWidgets
    info_patch = patch.object(PySide6.QtWidgets.QMessageBox, "information", return_value=None)
    critical_patch = patch.object(PySide6.QtWidgets.QMessageBox, "critical", return_value=None)
    warning_patch = patch.object(PySide6.QtWidgets.QMessageBox, "warning", return_value=None)
    question_patch = patch.object(
        PySide6.QtWidgets.QMessageBox, "question",
        return_value=PySide6.QtWidgets.QMessageBox.StandardButton.Yes,
    )
    info_patch.start()
    critical_patch.start()
    warning_patch.start()
    question_patch.start()

    yield view

    question_patch.stop()
    warning_patch.stop()
    critical_patch.stop()
    info_patch.stop()
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


@pytest.fixture
def sample_client_data():
    return {
        "id": 1,
        "name": "Acme Corp",
        "bank_account": "RO123456",
        "bank_code": "BANKROBU",
        "iban": "RO49AAAA1B31007593840000",
    }


@pytest.fixture
def sample_driver_data():
    return {
        "id": 10,
        "name": "John Doe",
        "type": "driver",
        "bank_account": "RO654321",
        "bank_code": "DRVROBU",
        "iban": "RO49AAAA1B31007593840001",
    }


@pytest.fixture
def sample_profile_data():
    return {
        "id": 20,
        "name": "Custom Supplier",
        "recipient_type": "custom",
        "bank_account": "RO111111",
        "bank_code": "SUPPROBU",
        "iban": "RO49AAAA1B31007593840002",
    }


def _configure_services(view, client_items=None, driver_items=None, profile_items=None):
    """Helper to set up mock service return values."""
    view._client_service.list_all.return_value = ServiceResult(
        success=True,
        data=[_mock_model(c) for c in (client_items or [])],
    )
    view._driver_truck_service.list_drivers.return_value = ServiceResult(
        success=True,
        data=[_mock_model(d) for d in (driver_items or [])],
    )
    view._batch_service.list_profiles.return_value = ServiceResult(
        success=True,
        data=[_mock_model(p) for p in (profile_items or [])],
    )


# ===========================================================================
# Construction & Initialization
# ===========================================================================

class TestConstruction:
    """View constructs and exposes expected attributes."""

    def test_creation(self, bulk_payments_view):
        """View constructs without crashing."""
        assert bulk_payments_view is not None

    def test_title_label(self, bulk_payments_view):
        """Page title label is present."""
        assert hasattr(bulk_payments_view, "_title_label")

    def test_recipient_table_created(self, bulk_payments_view):
        """Recipient table is created."""
        assert hasattr(bulk_payments_view, "_recipient_table")

    def test_batch_table_created(self, bulk_payments_view):
        """Batch table is created."""
        assert hasattr(bulk_payments_view, "_batch_table")

    def test_export_button_created(self, bulk_payments_view):
        """Export CSV button is present."""
        assert hasattr(bulk_payments_view, "_export_btn")

    def test_search_entry_created(self, bulk_payments_view):
        """Search entry is created."""
        assert hasattr(bulk_payments_view, "_search_entry")

    def test_services_initialized(self, bulk_payments_view):
        """Service mocks are in place."""
        assert bulk_payments_view._client_service is not None
        assert bulk_payments_view._driver_truck_service is not None
        assert bulk_payments_view._profile_service is not None
        assert bulk_payments_view._batch_service is not None


# ===========================================================================
# Data Loading
# ===========================================================================

class TestDataLoading:
    """Loading recipients from services."""

    def test_load_data_populates_table(
        self, bulk_payments_view, sample_client_data,
        sample_driver_data, sample_profile_data,
    ):
        """_load_data fills the recipient table."""
        _configure_services(
            bulk_payments_view,
            client_items=[sample_client_data],
            driver_items=[sample_driver_data],
            profile_items=[sample_profile_data],
        )

        bulk_payments_view._load_data()

        assert len(bulk_payments_view._all_recipients) == 3
        # Table should show 3 rows
        assert bulk_payments_view._recipient_table.rowCount() == 3

    def test_load_data_empty_db(self, bulk_payments_view):
        """_load_data handles empty results gracefully."""
        _configure_services(bulk_payments_view)
        bulk_payments_view._load_data()

        assert bulk_payments_view._all_recipients == []
        assert bulk_payments_view._recipient_table.rowCount() == 0

    def test_load_data_service_failure(self, bulk_payments_view):
        """_load_data does not crash on service exception."""
        bulk_payments_view._client_service.list_all.side_effect = RuntimeError("DB down")
        _configure_services(bulk_payments_view, client_items=[])
        # Override the client mock to raise
        bulk_payments_view._client_service.list_all.side_effect = RuntimeError("DB down")
        # Should not crash
        bulk_payments_view._load_data()
        assert bulk_payments_view._all_recipients == []

    def test_load_data_no_db(self, bulk_payments_view):
        """When db is None, _load_data returns immediately."""
        bulk_payments_view.db = None
        bulk_payments_view._load_data()
        assert bulk_payments_view._all_recipients == []


# ===========================================================================
# Search / Filter
# ===========================================================================

class TestSearchFilter:
    """Search-by-name filtering of the recipient table."""

    def test_search_filters_by_name(
        self, bulk_payments_view, sample_client_data, sample_driver_data,
    ):
        _configure_services(
            bulk_payments_view,
            client_items=[sample_client_data],
            driver_items=[sample_driver_data],
        )
        bulk_payments_view._load_data()
        assert bulk_payments_view._recipient_table.rowCount() == 2

        # Search for "Acme" — only client matches
        bulk_payments_view._search_recipients("Acme")
        assert bulk_payments_view._recipient_table.rowCount() == 1

    def test_search_empty_query_shows_all(
        self, bulk_payments_view, sample_client_data, sample_driver_data,
    ):
        _configure_services(
            bulk_payments_view,
            client_items=[sample_client_data],
            driver_items=[sample_driver_data],
        )
        bulk_payments_view._load_data()

        bulk_payments_view._search_recipients("")
        assert bulk_payments_view._recipient_table.rowCount() == 2

    def test_search_no_match(self, bulk_payments_view, sample_client_data):
        _configure_services(
            bulk_payments_view,
            client_items=[sample_client_data],
        )
        bulk_payments_view._load_data()

        bulk_payments_view._search_recipients("zzz_nonexistent")
        assert bulk_payments_view._recipient_table.rowCount() == 0


# ===========================================================================
# Batch Operations
# ===========================================================================

class TestBatchOperations:
    """Adding, removing, and editing items in the payment batch."""

    def test_add_to_batch(self, bulk_payments_view):
        """Adding a recipient to the batch increments batch_items."""
        source = {
            "id": 1, "name": "Acme Corp", "type": "client",
            "bank_account": "RO123456", "bank_code": "BANKROBU",
            "iban": "RO49AAAA1B31007593840000",
            "source_data": {},
        }
        assert len(bulk_payments_view._batch_items) == 0

        with patch("PySide6.QtWidgets.QInputDialog.getDouble",
                   return_value=(1500.00, True)):
            bulk_payments_view._prompt_and_add(source)

        assert len(bulk_payments_view._batch_items) == 1
        assert bulk_payments_view._batch_items[0]["recipient_name"] == "Acme Corp"
        assert bulk_payments_view._batch_items[0]["amount"] == 1500.00

    def test_add_to_batch_cancelled(self, bulk_payments_view):
        """Cancelling the amount dialog does not add anything."""
        source = {"id": 1, "name": "Acme Corp", "type": "client",
                  "bank_account": "RO123456", "bank_code": "BANKROBU",
                  "iban": "RO49AAAA1B31007593840000", "source_data": {}}

        with patch("PySide6.QtWidgets.QInputDialog.getDouble",
                   return_value=(0.0, False)):
            bulk_payments_view._prompt_and_add(source)

        assert len(bulk_payments_view._batch_items) == 0

    def test_remove_from_batch(self, bulk_payments_view):
        """Selected batch item is removed."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client", "recipient_name": "Acme",
             "amount": 1000.0, "currency": "EUR", "payment_reference": "",
             "bank_account": "RO123", "iban": "RO49AAAA", "bank_code": ""},
        ]
        bulk_payments_view._refresh_batch_table()

        # Select the row
        bulk_payments_view._batch_table._data = list(bulk_payments_view._batch_items)
        bulk_payments_view._batch_table.selectRow(0)

        bulk_payments_view._remove_from_batch()
        assert len(bulk_payments_view._batch_items) == 0

    def test_remove_from_batch_no_selection(self, bulk_payments_view):
        """Removing with no selection shows info message (no crash)."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client", "recipient_name": "Acme",
             "amount": 1000.0, "currency": "EUR", "payment_reference": "",
             "bank_account": "RO123", "iban": "RO49AAAA", "bank_code": ""},
        ]
        bulk_payments_view._refresh_batch_table()
        # No row selected
        bulk_payments_view._remove_from_batch()
        assert len(bulk_payments_view._batch_items) == 1

    def test_edit_amount(self, bulk_payments_view):
        """Edit amount updates the batch item."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client", "recipient_name": "Acme",
             "amount": 1000.0, "currency": "EUR", "payment_reference": "",
             "bank_account": "RO123", "iban": "RO49AAAA", "bank_code": ""},
        ]
        bulk_payments_view._refresh_batch_table()
        bulk_payments_view._batch_table._data = list(bulk_payments_view._batch_items)
        bulk_payments_view._batch_table.selectRow(0)

        with patch("PySide6.QtWidgets.QInputDialog.getDouble",
                   return_value=(2500.00, True)):
            bulk_payments_view._edit_amount()

        assert bulk_payments_view._batch_items[0]["amount"] == 2500.0

    def test_add_selected_to_batch_no_selection(self, bulk_payments_view):
        """_add_selected_to_batch with no selection shows info (no crash)."""
        bulk_payments_view._add_selected_to_batch()


# ===========================================================================
# Batch Table Display
# ===========================================================================

class TestBatchDisplay:
    """Batch table rendering and empty state."""

    def test_empty_state_visible(self, bulk_payments_view):
        """Empty state: empty label visible, batch table hidden."""
        # Trigger refresh to set proper visibility state
        bulk_payments_view._refresh_batch_table()
        assert not bulk_payments_view._batch_empty_state.isHidden()
        assert bulk_payments_view._batch_table.isHidden()

    def test_batch_table_shows_items(self, bulk_payments_view):
        """Batch table becomes visible when items are added."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "Acme Corp", "bank_account": "RO123",
             "iban": "RO49AAAA", "amount": 1500.00,
             "currency": "EUR", "payment_reference": "INV-001",
             "bank_code": "BANKROBU"},
        ]
        bulk_payments_view._refresh_batch_table()

        # After adding items the empty state is hidden and the table is not hidden
        assert bulk_payments_view._batch_empty_state.isHidden()
        assert not bulk_payments_view._batch_table.isHidden()
        # 1 data row + 1 total row
        assert bulk_payments_view._batch_table.rowCount() == 2

    def test_total_row_calculated(self, bulk_payments_view):
        """Total row shows correct sum."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "A", "bank_account": "R1",
             "iban": "I1", "amount": 1000.00,
             "currency": "EUR", "payment_reference": "REF1",
             "bank_code": ""},
            {"recipient_id": 2, "recipient_type": "client",
             "recipient_name": "B", "bank_account": "R2",
             "iban": "I2", "amount": 2500.00,
             "currency": "EUR", "payment_reference": "REF2",
             "bank_code": ""},
        ]
        bulk_payments_view._refresh_batch_table()

        total_item = bulk_payments_view._batch_table.item(
            len(bulk_payments_view._batch_items), 4,
        )
        assert total_item is not None
        assert float(total_item.text()) == 3500.00


# ===========================================================================
# CSV Export
# ===========================================================================

class TestCsvExport:
    """CSV export functionality."""

    def test_export_empty_batch(self, bulk_payments_view):
        """Exporting with no items shows info, no crash."""
        bulk_payments_view._export_csv()

    @patch("PySide6.QtWidgets.QFileDialog.getSaveFileName")
    def test_export_cancelled(self, mock_save, bulk_payments_view):
        """Cancelling the save dialog does nothing."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "Acme", "bank_account": "RO123",
             "iban": "I1", "amount": 1000.00,
             "currency": "EUR", "payment_reference": "REF",
             "bank_code": ""},
        ]
        mock_save.return_value = ("", "")
        bulk_payments_view._export_csv()

    @patch("PySide6.QtWidgets.QFileDialog.getSaveFileName")
    @patch("services.csv_service.CsvService.export")
    def test_export_success(self, mock_csv_export, mock_save, bulk_payments_view):
        """Successful export calls CsvService.export."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "Acme", "bank_account": "RO123",
             "iban": "I1", "amount": 1000.00,
             "currency": "EUR", "payment_reference": "REF",
             "bank_code": ""},
        ]
        mock_save.return_value = ("/tmp/batch.csv", "CSV (*.csv)")
        bulk_payments_view._export_csv()
        mock_csv_export.assert_called_once()

    @patch("PySide6.QtWidgets.QFileDialog.getSaveFileName")
    @patch("services.csv_service.CsvService.export")
    def test_export_failure(self, mock_csv_export, mock_save, bulk_payments_view):
        """Export failure shows critical message (no crash)."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "Acme", "bank_account": "RO123",
             "iban": "I1", "amount": 1000.00,
             "currency": "EUR", "payment_reference": "REF",
             "bank_code": ""},
        ]
        mock_save.return_value = ("/tmp/batch.csv", "CSV (*.csv)")
        mock_csv_export.side_effect = PermissionError("Access denied")
        bulk_payments_view._export_csv()
        mock_csv_export.assert_called_once()


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Edge case handling."""

    def test_large_batch(self, bulk_payments_view):
        """A large batch (100 items) renders without error."""
        batch = []
        for i in range(100):
            batch.append({
                "recipient_id": i,
                "recipient_type": "client",
                "recipient_name": f"Client {i}",
                "bank_account": "RO1",
                "iban": "I1",
                "amount": float(i * 100),
                "currency": "EUR",
                "payment_reference": f"R{i}",
                "bank_code": "",
            })
        bulk_payments_view._batch_items = batch
        bulk_payments_view._refresh_batch_table()

        # 100 data rows + 1 total row
        assert bulk_payments_view._batch_table.rowCount() == 101

    def test_large_numbers(self, bulk_payments_view):
        """Very large amounts are displayed correctly."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "Big Corp", "bank_account": "RO1",
             "iban": "I1", "amount": 9_999_999_999.99,
             "currency": "EUR", "payment_reference": "R",
             "bank_code": ""},
        ]
        bulk_payments_view._refresh_batch_table()

        amount_item = bulk_payments_view._batch_table.item(0, 4)
        assert amount_item is not None
        assert "9999999999.99" in amount_item.text()

    def test_missing_data_fields(self, bulk_payments_view):
        """Batch items with missing fields don't crash."""
        minimal_item = {
            "recipient_id": 1,
            "recipient_name": "Minimal",
            "amount": 500.0,
        }
        bulk_payments_view._batch_items = [minimal_item]
        bulk_payments_view._refresh_batch_table()
        assert bulk_payments_view._batch_table.rowCount() == 2

    def test_wakeup_refresh(self, bulk_payments_view, sample_client_data):
        """wakeup() calls _load_data and _refresh_batch_table without error."""
        _configure_services(bulk_payments_view, client_items=[sample_client_data])
        bulk_payments_view.wakeup()

    def test_db_none_construction(self, qt_widget, qtbot):
        """View can be constructed without a database connection."""
        mod = __import__("ui.views.bulk_payments_view", fromlist=["QtBulkPaymentsView"])
        view = mod.QtBulkPaymentsView(qt_widget, db=None)
        qtbot.addWidget(view)

        assert view.db is None
        assert view._client_service is None
        assert view._driver_truck_service is None
        assert view._profile_service is None
        assert view._batch_service is None

        view.wakeup()  # Should not crash
        view.shutdown()


# ===========================================================================
# Context Menus
# ===========================================================================

class TestContextMenus:
    """Context menus render without crashing."""

    def test_recipient_context_menu(self, bulk_payments_view, sample_client_data):
        """Right-click on a recipient shows context menu (smoke test)."""
        _configure_services(bulk_payments_view, client_items=[sample_client_data])
        bulk_payments_view._load_data()
        bulk_payments_view._recipient_table.selectRow(0)

        with patch("PySide6.QtWidgets.QMenu.popup", return_value=None):
            bulk_payments_view._show_recipient_context_menu(
                bulk_payments_view._recipient_table.pos(),
            )

    def test_batch_context_menu(self, bulk_payments_view):
        """Right-click on batch table shows context menu (smoke test)."""
        bulk_payments_view._batch_items = [
            {"recipient_id": 1, "recipient_type": "client",
             "recipient_name": "Acme", "bank_account": "RO123",
             "iban": "I1", "amount": 1000.00,
             "currency": "EUR", "payment_reference": "REF",
             "bank_code": ""},
        ]
        bulk_payments_view._refresh_batch_table()
        bulk_payments_view._batch_table.selectRow(0)

        with patch("PySide6.QtWidgets.QMenu.popup", return_value=None):
            bulk_payments_view._show_batch_context_menu(
                bulk_payments_view._batch_table.pos(),
            )


# ===========================================================================
# Lifecycle
# ===========================================================================

class TestLifecycle:
    """shutdown / cleanup."""

    def test_shutdown_cleanup(self, bulk_payments_view):
        """shutdown() can be called safely."""
        bulk_payments_view.shutdown()

    def test_shutdown_idempotent(self, bulk_payments_view):
        """shutdown() can be called multiple times."""
        bulk_payments_view.shutdown()
        bulk_payments_view.shutdown()
