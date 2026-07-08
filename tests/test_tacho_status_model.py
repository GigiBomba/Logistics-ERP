"""Tests for the tacho status model."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestTachoStatusModel:
    def test_creation(self, qt_widget, qtbot):
        from ui.models.tacho_status_model import TachoStatusModel
        model = TachoStatusModel(qt_widget)
        assert model is not None

    def test_set_driver_data(self, qt_widget, qtbot):
        from ui.models.tacho_status_model import TachoStatusModel
        model = TachoStatusModel(qt_widget)
        drivers = [
            {"id": 1, "name": "John Doe", "driving_hours": 8.5, "rest_hours": 11.0},
            {"id": 2, "name": "Jane Smith", "driving_hours": 4.0, "rest_hours": 20.0},
        ]
        model.set_driver_data(drivers)

    def test_get_driver_status(self, qt_widget, qtbot):
        from ui.models.tacho_status_model import TachoStatusModel
        model = TachoStatusModel(qt_widget)
        status = model.get_driver_status(1) if hasattr(model, "get_driver_status") else None

    def test_clear(self, qt_widget, qtbot):
        from ui.models.tacho_status_model import TachoStatusModel
        model = TachoStatusModel(qt_widget)
        model.clear()
