"""Extended tests for the calculator view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def calculator_view(qt_widget, qtbot):
    db = MagicMock()
    fleet_service = MagicMock()
    trip_service = MagicMock()
    client_service = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    fuel_service = MagicMock()
    fuel_service.is_available.return_value = True
    fuel_service.last_updated_str.return_value = "2026-01-01"
    fuel_service.age_seconds.return_value = 3600
    api = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.calculator_view", fromlist=["QtCalculatorView"]).QtCalculatorView(
        qt_widget, db=db, fleet_service=fleet_service, trip_service=trip_service,
        client_service=client_service, prefs=prefs, ops=ops,
        fuel_service=fuel_service, api=api, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtCalculatorView:
    def test_creation(self, calculator_view):
        assert calculator_view.db is not None

    def test_origin_input_exists(self, calculator_view):
        assert hasattr(calculator_view, "_origin_input")

    def test_destination_input_exists(self, calculator_view):
        assert hasattr(calculator_view, "_destination_input")

    def test_distance_input_exists(self, calculator_view):
        assert hasattr(calculator_view, "_distance_input")

    def test_fuel_price_displayed(self, calculator_view):
        assert hasattr(calculator_view, "_fuel_price_label")

    def test_calculate_button_exists(self, calculator_view):
        assert hasattr(calculator_view, "_btn_calculate")

    def test_result_section_exists(self, calculator_view):
        assert hasattr(calculator_view, "_result_label")

    def test_shutdown_cleanup(self, calculator_view):
        calculator_view.shutdown()

    def test_wakeup_does_not_crash(self, calculator_view):
        calculator_view.wakeup()

    def test_waypoints_section(self, calculator_view):
        assert hasattr(calculator_view, "_waypoints_list")
