"""Tests for _TruckFormDialog — truck add/edit dialog."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog


@pytest.fixture
def truck_form(qt_widget, qtbot):
    """Create a _TruckFormDialog in 'add' mode."""
    service = MagicMock()
    service.db = MagicMock()
    dlg = __import__(
        "ui.views.fleet_tab.truck_form", fromlist=["_TruckFormDialog"]
    )._TruckFormDialog(
        parent=qt_widget,
        service=service,
    )
    qtbot.addWidget(dlg)
    yield dlg
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        dlg.close()


@pytest.fixture
def truck_form_edit(qt_widget, qtbot):
    """Create a _TruckFormDialog in 'edit' mode with existing data."""
    service = MagicMock()
    service.db = MagicMock()
    truck_data = {
        "id": 1,
        "plate_number": "AB123CD",
        "model": "Actros",
        "manufacturer": "Mercedes",
        "year": 2020,
        "vin": "WDB123456789",
        "fuel_consumption": 25.5,
        "mileage": 150000,
        "monthly_rate": 2500.0,
        "status": "active",
        "tracking_device_id": "GPS-001",
        "active_status": 1,
    }
    dlg = __import__(
        "ui.views.fleet_tab.truck_form", fromlist=["_TruckFormDialog"]
    )._TruckFormDialog(
        parent=qt_widget,
        service=service,
        truck=truck_data,
    )
    qtbot.addWidget(dlg)
    yield dlg
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        dlg.close()


class TestTruckFormDialog:
    """Suite of tests for _TruckFormDialog."""

    def test_creation_add(self, truck_form):
        """Dialog constructs in add mode without crashing."""
        assert truck_form._truck is None
        assert truck_form._on_save is None

    def test_creation_edit(self, truck_form_edit):
        """Dialog constructs in edit mode with existing data."""
        assert truck_form_edit._truck is not None
        assert truck_form_edit._truck["id"] == 1

    def test_edit_window_title(self, truck_form_edit):
        """Edit dialog has edit button title."""
        assert truck_form_edit.windowTitle() != ""

    def test_add_window_title(self, truck_form):
        """Add dialog has form title."""
        assert truck_form.windowTitle() != ""

    def test_dialog_is_modal(self, truck_form):
        """Dialog is modal."""
        assert truck_form.isModal()

    def test_minimum_width(self, truck_form):
        """Dialog has minimum width set."""
        assert truck_form.minimumWidth() >= 400

    def test_fields_created(self, truck_form):
        """All form fields are created."""
        expected_fields = [
            "plate", "model", "manufacturer", "year", "vin",
            "fuel", "mileage", "monthly_rate", "status", "tracking_device_id",
        ]
        for name in expected_fields:
            assert name in truck_form._fields, f"Missing field: {name}"

    def test_active_checkbox_exists(self, truck_form):
        """Active checkbox is created."""
        assert hasattr(truck_form, "_active_cb")

    def test_plate_required_validation(self, truck_form):
        """Saving with empty plate shows warning and does not accept."""
        truck_form._fields["plate"].setText("")
        with patch(
            "ui.views.fleet_tab.truck_form.QMessageBox.warning"
        ) as mock_warn:
            truck_form._save()
            mock_warn.assert_called_once()

    def test_save_add_calls_service(self, truck_form):
        """Saving in add mode calls add_truck on the service."""
        truck_form._fields["plate"].setText("XY999ZZ")
        truck_form._fields["model"].setText("Test")
        truck_form._fields["manufacturer"].setText("TestMfg")
        truck_form._fields["year"].setText("2022")
        truck_form._fields["vin"].setText("VIN123")
        truck_form._fields["fuel"].setText("30.0")
        truck_form._fields["mileage"].setText("10000")
        truck_form._fields["monthly_rate"].setText("3000")
        truck_form._fields["status"].setText("active")
        truck_form._fields["tracking_device_id"].setText("GPS-X")
        truck_form._service.add_truck = MagicMock(return_value=99)
        truck_form._service.update_truck = MagicMock()
        truck_form._save()
        truck_form._service.add_truck.assert_called_once()

    def test_save_edit_calls_update(self, truck_form_edit):
        """Saving in edit mode calls update_truck on the service."""
        truck_form_edit._service.update_truck = MagicMock()
        truck_form_edit._save()
        truck_form_edit._service.update_truck.assert_called_once()

    def test_year_validation_rejects_non_int(self, truck_form):
        """Non-numeric year shows warning."""
        truck_form._fields["plate"].setText("PLATE1")
        truck_form._fields["year"].setText("not-a-year")
        with patch(
            "ui.views.fleet_tab.truck_form.QMessageBox.warning"
        ) as mock_warn:
            truck_form._save()
            mock_warn.assert_called_once()

    def test_fuel_validation_rejects_non_float(self, truck_form):
        """Non-numeric fuel consumption shows warning."""
        truck_form._fields["plate"].setText("PLATE1")
        truck_form._fields["year"].setText("2022")
        truck_form._fields["fuel"].setText("not-a-number")
        with patch(
            "ui.views.fleet_tab.truck_form.QMessageBox.warning"
        ) as mock_warn:
            truck_form._save()
            mock_warn.assert_called_once()

    def test_edit_prefills_data(self, truck_form_edit):
        """Edit mode pre-fills fields with truck data."""
        assert truck_form_edit._fields["plate"].text() == "AB123CD"
        assert truck_form_edit._fields["model"].text() == "Actros"
        assert truck_form_edit._fields["manufacturer"].text() == "Mercedes"

    def test_driver_combo_not_created_without_dta(self, truck_form):
        """Without dta_service, driver combo is not created."""
        assert not hasattr(truck_form, "_driver_combo")

    def test_cancel_closes_dialog(self, qtbot, truck_form):
        """Cancel button rejects the dialog."""
        truck_form.reject()
        assert truck_form.result() == QDialog.DialogCode.Rejected
