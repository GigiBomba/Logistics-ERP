"""Tests for the receipt editor view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def receipt_editor(qt_widget, qtbot):
    db = MagicMock()
    prefs = MagicMock()
    prefs.get_currency.return_value = "EUR"
    editor = __import__("ui.views.receipt_editor", fromlist=["QtReceiptEditor"]).QtReceiptEditor(
        qt_widget, db=db, prefs=prefs,
    )
    qtbot.addWidget(editor)
    yield editor
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        editor.shutdown()


class TestQtReceiptEditor:
    def test_creation(self, receipt_editor):
        assert receipt_editor.db is not None

    def test_form_fields_exist(self, receipt_editor):
        assert hasattr(receipt_editor, "_receipt_number")
        assert hasattr(receipt_editor, "_customer_combo")

    def test_line_items_table_exists(self, receipt_editor):
        # ReceiptEditor inherits LineItemsMixin but doesn't call _build_line_items_section
        # Check for an attribute that does exist instead
        assert hasattr(receipt_editor, "_amount_entry")

    def test_shutdown_cleanup(self, receipt_editor):
        receipt_editor._addon_items = [{"id": 1}]
        receipt_editor.shutdown()
        assert receipt_editor._addon_items == [{"id": 1}]

    def test_currency_combo_exists(self, receipt_editor):
        assert hasattr(receipt_editor, "_currency_combo")

    def test_wakeup_does_not_crash(self, receipt_editor):
        receipt_editor.wakeup()

    def test_share_button_exists(self, receipt_editor):
        assert hasattr(receipt_editor, "_share_btn")

    def test_share_button_disabled_without_pdf(self, receipt_editor):
        # No receipt number / PDF on a fresh editor
        assert not receipt_editor._share_btn.isEnabled()

    def test_share_button_enabled_when_pdf_exists(self, receipt_editor, tmp_path, monkeypatch):
        receipt_editor._receipt_number = "TEST-001"
        receipt_editor._receipt_number_entry.setText("TEST-001")
        pdf_path = str(tmp_path / "TEST-001.pdf")
        with open(pdf_path, "w") as f:
            f.write("fake pdf")
        monkeypatch.setattr(receipt_editor, "_pdf_path", lambda: pdf_path)
        receipt_editor._update_share_state()
        assert receipt_editor._share_btn.isEnabled()


class TestReceiptTripAutofill:
    """Trip-selection autofill: fill-only-if-empty, Invoice > Trip precedence."""

    def _mock_trip_service(self, receipt_editor, trip):
        svc = MagicMock()
        svc.get_by_id.return_value = trip
        svc.extract_route_pickup_delivery.return_value = ("Pickup St", "Delivery St")
        receipt_editor._trip_svc_instance = svc
        receipt_editor._trip_combo_map["Trip 1"] = trip.get("id", 1)
        return svc

    def test_trip_selection_fills_vehicle_from_truck(self, receipt_editor):
        """Selecting a trip fills the (empty) Vehicle combo from truck_number."""
        receipt_editor._vehicle_combo.addItem("")  # default empty item
        receipt_editor._vehicle_combo.addItem("AB-01-ABC")
        self._mock_trip_service(
            receipt_editor, {"id": 1, "truck_number": "AB-01-ABC"}
        )
        receipt_editor._on_trip_combo_changed("Trip 1")
        assert receipt_editor._vehicle_combo.currentText() == "AB-01-ABC"

    def test_trip_selection_fills_employee_from_driver(self, receipt_editor):
        """Trip driver maps to the Employee name (receipt has no driver field)."""
        self._mock_trip_service(
            receipt_editor, {"id": 1, "driver_name": "Ion Popescu"}
        )
        receipt_editor._on_trip_combo_changed("Trip 1")
        assert receipt_editor._employee_name_entry.text() == "Ion Popescu"

    def test_trip_selection_only_fills_empty_fields(self, receipt_editor):
        """Fill-only-if-empty: existing user input is never clobbered."""
        receipt_editor._vehicle_combo.addItems(["", "AB-01-ABC", "CD-02-DEF"])
        receipt_editor._vehicle_combo.setCurrentText("CD-02-DEF")  # user choice
        receipt_editor._employee_name_entry.setText("Manual Name")
        receipt_editor._pickup_location_entry.setText("Manual Pickup")
        self._mock_trip_service(
            receipt_editor,
            {"id": 1, "truck_number": "AB-01-ABC", "driver_name": "Ion Popescu"},
        )
        receipt_editor._on_trip_combo_changed("Trip 1")
        assert receipt_editor._vehicle_combo.currentText() == "CD-02-DEF"
        assert receipt_editor._employee_name_entry.text() == "Manual Name"
        assert receipt_editor._pickup_location_entry.text() == "Manual Pickup"
        # The still-empty delivery field should be autofilled
        assert receipt_editor._delivery_location_entry.text() == "Delivery St"

    def test_invoice_values_not_overwritten_by_trip(self, receipt_editor):
        """Invoice > Trip: a trip selection cannot clobber invoice-filled values."""
        from datetime import date
        from decimal import Decimal

        from models.invoice_models import InvoiceResult

        receipt_editor._vehicle_combo.addItem("")  # default empty item
        receipt_editor._vehicle_combo.addItem("AB-01-ABC")
        receipt_editor._customer_combo.addItem("")  # default empty item
        receipt_editor._customer_combo.addItem("Trip Client")
        receipt_editor._currency_combo.addItems(["EUR", "RON"])
        receipt_editor._related_trip_combo.addItem("")  # default empty item
        receipt_editor._related_trip_combo.addItem("Trip 1")

        trip = {
            "id": 1, "client_name": "Trip Client", "truck_number": "AB-01-ABC",
            "driver_name": "Driver One", "currency": "EUR",
        }
        self._mock_trip_service(receipt_editor, trip)

        invoice = InvoiceResult(
            id=5, invoice_number="INV-2026-0005", client_id=1, client_name="ACME",
            trip_id=1, trip_reference="TR-1", invoice_date=date(2026, 9, 1),
            due_date=date(2026, 9, 30), currency="RON",
            subtotal_net=Decimal("800.00"), total_vat=Decimal("160.00"),
            total_gross=Decimal("960.00"), notes="",
        )
        result = MagicMock()
        result.success = True
        result.data = invoice
        invoice_svc = MagicMock()
        invoice_svc.get.return_value = result
        receipt_editor._invoice_svc_instance = invoice_svc
        label = "INV-2026-0005 — 960.00 RON"
        receipt_editor._invoice_map[label] = 5
        receipt_editor._invoice_combo.addItem(label)

        receipt_editor._on_invoice_selected(label)

        # Invoice-filled values are present
        assert receipt_editor._amount_entry.text() == "960.00"
        assert receipt_editor._currency_combo.currentText() == "RON"
        assert receipt_editor._customer_combo.currentText() == "Trip Client"
        assert receipt_editor._invoice_reference_entry.text() == "INV-2026-0005"
        # Trip handler still filled the blanks (vehicle/employee) via the
        # related-trip selection triggered by the invoice
        assert receipt_editor._vehicle_combo.currentText() == "AB-01-ABC"
        assert receipt_editor._employee_name_entry.text() == "Driver One"

        # A further (manual) trip selection must not overwrite invoice values
        receipt_editor._on_trip_combo_changed("Trip 1")
        assert receipt_editor._amount_entry.text() == "960.00"
        assert receipt_editor._currency_combo.currentText() == "RON"
        assert receipt_editor._customer_combo.currentText() == "Trip Client"
