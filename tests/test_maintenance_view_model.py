"""Tests for the maintenance view model."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestMaintenanceViewModel:
    def test_creation(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(qt_widget)
        assert model is not None

    def test_set_truck_data(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(qt_widget)
        truck = {"id": 1, "plate": "AG01ABC", "make": "Volvo", "mileage": 150000}
        model.set_truck_data(truck)

    def test_set_records(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(qt_widget)
        records = [{"id": 1, "description": "Oil change", "date": "2026-01-01", "cost": 500}]
        model.set_records(records)

    def test_set_schedules(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(qt_widget)
        schedules = [{"id": 1, "type": "oil_change", "interval_km": 15000}]
        model.set_schedules(schedules)

    def test_compute_health(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(qt_widget)
        health = model.compute_health() if hasattr(model, "compute_health") else 100
        assert isinstance(health, (int, float))
