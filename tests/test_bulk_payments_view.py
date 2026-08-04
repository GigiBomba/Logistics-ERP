"""Tests for the bulk payments view."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def bulk_payments(qt_widget, qtbot):
    db = MagicMock()
    prefs = {"default_currency": "EUR"}
    api_client = MagicMock()
    view = __import__(
        "ui.views.bulk_payments_view", fromlist=["QtBulkPaymentsView"]
    ).QtBulkPaymentsView(
        qt_widget,
        db=db,
        prefs=prefs,
        api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtBulkPaymentsView:
    """Suite of tests for QtBulkPaymentsView."""

    def test_creation(self, bulk_payments):
        """View constructs without crashing."""
        assert bulk_payments.db is not None
        assert bulk_payments._prefs == {"default_currency": "EUR"}
        assert bulk_payments._batch_items == []

    def test_header_title(self, bulk_payments):
        """Header title label is created."""
        assert hasattr(bulk_payments, "_title_label")

    def test_toolbar_buttons_exist(self, bulk_payments):
        """All toolbar buttons are present."""
        assert hasattr(bulk_payments, "_export_btn")
        assert hasattr(bulk_payments, "_new_profile_btn")
        assert hasattr(bulk_payments, "_remove_selected_btn")

    def test_search_entry_exists(self, bulk_payments):
        """Search input widget exists."""
        assert hasattr(bulk_payments, "_search_entry")

    def test_add_selected_button_exists(self, bulk_payments):
        """Add-selected button exists."""
        assert hasattr(bulk_payments, "_add_selected_btn")

    def test_recipient_table_created(self, bulk_payments):
        """Recipient table widget is created."""
        assert hasattr(bulk_payments, "_recipient_table")

    def test_batch_panel_created(self, bulk_payments):
        """Batch panel title, empty-label, and table exist."""
        assert hasattr(bulk_payments, "_batch_title")
        assert hasattr(bulk_payments, "_batch_empty_state")
        assert hasattr(bulk_payments, "_batch_table")

    def test_batch_empty_state(self, bulk_payments):
        """Batch starts empty: empty label visible, table hidden after refresh."""
        assert bulk_payments._batch_items == []
        bulk_payments._refresh_batch_table()
        assert not bulk_payments._batch_empty_state.isHidden()
        assert bulk_payments._batch_table.isHidden()

    def test_services_initialized(self, bulk_payments):
        """All service-layer attributes are created."""
        assert bulk_payments._client_service is not None
        assert bulk_payments._driver_truck_service is not None
        assert bulk_payments._profile_service is not None
        assert bulk_payments._batch_service is not None

    def test_shutdown_cleanup(self, bulk_payments):
        """shutdown() can be called without error."""
        bulk_payments.shutdown()

    def test_wakeup_loads_data(self, bulk_payments):
        """wakeup() triggers _load_data and _refresh_batch_table."""
        bulk_payments._client_service = MagicMock()
        bulk_payments._client_service.list_all.return_value.data = []
        bulk_payments._driver_truck_service = MagicMock()
        bulk_payments._driver_truck_service.list_drivers.return_value.data = []
        bulk_payments._batch_service = MagicMock()
        bulk_payments._batch_service.list_profiles.return_value.data = []
        bulk_payments.wakeup()
        bulk_payments._client_service.list_all.assert_called_once()

    def test_add_to_batch_updates_state(self, bulk_payments):
        """Adding a recipient to the batch updates the batch table."""
        bulk_payments._all_recipients = [
            {
                "id": 1,
                "name": "Test Client",
                "type": "client",
                "bank_account": "RO123",
                "bank_code": "BANK",
                "iban": "RO12BANK123",
                "source": "client",
                "source_data": {},
            }
        ]
        bulk_payments._recipient_table.set_data(
            [
                {
                    "name": "Test Client",
                    "type": "client",
                    "bank_account": "RO123",
                    "bank_code": "BANK",
                    "iban": "RO12BANK123",
                    "_source": bulk_payments._all_recipients[0],
                }
            ]
        )
        # Simulate adding the recipient by calling the internal method
        item = {
            "recipient_id": 1,
            "recipient_type": "client",
            "recipient_name": "Test Client",
            "bank_account": "RO123",
            "bank_code": "BANK",
            "bank_bic": "",
            "iban": "RO12BANK123",
            "amount": 1500.00,
            "currency": "EUR",
            "payment_reference": "",
        }
        bulk_payments._batch_items.append(item)
        bulk_payments._refresh_batch_table()
        assert len(bulk_payments._batch_items) == 1
        assert bulk_payments._batch_empty_state.isHidden()
        assert not bulk_payments._batch_table.isHidden()
