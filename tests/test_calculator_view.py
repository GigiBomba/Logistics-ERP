"""Tests for QtCalculatorView — profit calculator view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_fleet_service():
    fs = MagicMock()
    fs.get_trucks.return_value = [
        {"id": 1, "plate_number": "AB-123", "model": "Actros",
         "fuel_consumption": 28.5, "monthly_rate": 1200},
    ]
    return fs


@pytest.fixture
def mock_trip_service():
    return MagicMock()


@pytest.fixture
def mock_client_service():
    cs = MagicMock()
    cs.get_all.return_value = [{"id": 1, "name": "Acme Corp"}]
    return cs


@pytest.fixture
def mock_calculator():
    calc = MagicMock()
    calc.calculate.return_value = MagicMock(
        success=True,
        data=MagicMock(
            net_profit=500.0,
            total_income=2000.0,
            profit_per_km=2.5,
            margin_percent=25.0,
            gross_per_km=10.0,
            fuel_cost=300.0,
            toll_cost=100.0,
            salary_cost=400.0,
            extra_costs=50.0,
        ),
        errors=[],
    )
    return calc


@pytest.fixture
def mock_prefs():
    prefs = MagicMock()
    prefs.get_currency.return_value = "EUR"
    return prefs


@pytest.fixture
def calculator_view(qtbot, mock_fleet_service, mock_trip_service,
                    mock_client_service, mock_calculator, mock_prefs):
    """Create QtCalculatorView with all services mocked."""
    patchers = [
        patch("ui.views.calculator_view.TripCalculator", return_value=mock_calculator),
        patch("ui.views.calculator_view.TripConflictService"),
        patch("ui.views.calculator_view.EventBus"),
        patch(
            "ui.views.calculator_view.TripContextService",
            spec=True,
        ),
        patch("ui.views.calculator_view.QMessageBox"),
    ]
    for p in patchers:
        p.start()
    # Make TripConflictService.check_conflicts return empty list to avoid
    # blocking QMessageBox.question dialog
    from ui.views.calculator_view import QMessageBox as _patched_qmb
    _patched_qmb.question.return_value = _patched_qmb.Yes

    from ui.views.calculator_view import QtCalculatorView

    widget = QtCalculatorView(
        parent=None,
        db=MagicMock(),
        fleet_service=mock_fleet_service,
        trip_service=mock_trip_service,
        client_service=mock_client_service,
        prefs=mock_prefs,
        ops=MagicMock(),
        fuel_service=MagicMock(),
        api=MagicMock(),
        api_client=MagicMock(),
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================

class TestQtCalculatorView:
    """Suite of tests for QtCalculatorView."""

    def test_initialization(self, calculator_view):
        """Widget initializes without crashing."""
        assert calculator_view is not None
        assert hasattr(calculator_view, "calculate_btn")

    def test_form_renders_all_input_fields(self, calculator_view):
        """All form input fields exist."""
        assert hasattr(calculator_view, "truck_combo")
        assert hasattr(calculator_view, "e_client")
        assert hasattr(calculator_view, "e_price")
        assert hasattr(calculator_view, "e_sal")
        assert hasattr(calculator_view, "e_extra")
        assert hasattr(calculator_view, "e_start")
        assert hasattr(calculator_view, "e_days")
        assert hasattr(calculator_view, "e_term")
        assert hasattr(calculator_view, "_vat_check")

    def test_calculate_button_exists(self, calculator_view):
        """Calculate button is present on the widget."""
        from ui.components import Btn
        buttons = calculator_view.findChildren(Btn)
        # Find the calculate button specifically
        assert calculator_view.calculate_btn is not None
        assert calculator_view.calculate_btn.isVisible()

    def test_result_panel_renders_after_calculation(self, calculator_view, mock_calculator):
        """After calculation, result labels are updated."""
        # Set up input fields
        calculator_view._route_distance = 500.0
        calculator_view.e_price.setText("2000")
        calculator_view.e_sal.setText("500")
        calculator_view.e_extra.setText("50")
        calculator_view.e_days.setText("2")
        calculator_view.e_term.setText("30")
        calculator_view.e_start.setText("01/01/2025")

        # Trigger calculation
        calculator_view._handle_calculate()

        # Result container should be visible
        assert calculator_view._results_container.isVisible()
        assert calculator_view._empty_state.isHidden()

    def test_validation_prevents_empty_inputs(self, calculator_view, qtbot, monkeypatch):
        """Calculation with empty/zero values shows warning, no crash."""
        monkeypatch.setattr("ui.views.calculator_view.QMessageBox", MagicMock())
        calculator_view.e_price.setText("0")
        calculator_view._route_distance = 0.0
        # Should not crash, should show warning dialog
        calculator_view._handle_calculate()
        # Results should remain hidden
        assert calculator_view._results_container.isHidden()

    def test_validation_prevents_negative_inputs(self, calculator_view, qtbot, monkeypatch):
        """Calculation with negative values shows warning."""
        monkeypatch.setattr("ui.views.calculator_view.QMessageBox", MagicMock())
        calculator_view.e_price.setText("-100")
        calculator_view._route_distance = 500.0
        calculator_view._handle_calculate()
        assert calculator_view._results_container.isHidden()

    def test_identification_section_has_truck_combo(self, calculator_view):
        """Truck combo is populated with mock data."""
        assert calculator_view.truck_combo.count() >= 1

    def test_identification_section_has_client_combo(self, calculator_view):
        """Client combo is populated with mock data."""
        assert calculator_view.e_client.count() >= 1

    def test_vat_toggle_shows_fields(self, calculator_view):
        """Enabling VAT reveals pre/post VAT fields."""
        assert calculator_view._vat_fields_frame.isHidden()
        calculator_view._vat_check.setChecked(True)
        assert calculator_view._vat_fields_frame.isVisible()

    def test_vat_toggle_hides_fields(self, calculator_view):
        """Disabling VAT hides pre/post VAT fields."""
        calculator_view._vat_check.setChecked(True)
        assert calculator_view._vat_fields_frame.isVisible()
        calculator_view._vat_check.setChecked(False)
        assert calculator_view._vat_fields_frame.isHidden()

    def test_vat_percent_input_enabled_with_checkbox(self, calculator_view):
        """VAT percent field enabled only when checkbox is checked."""
        calculator_view._vat_check.setChecked(True)
        assert calculator_view._vat_percent.isEnabled()
        calculator_view._vat_check.setChecked(False)
        assert not calculator_view._vat_percent.isEnabled()

    def test_shutdown_cleanup(self, calculator_view):
        """shutdown() unregisters listeners without crash."""
        calculator_view.shutdown()
        # events should be unsubscribed
        assert not getattr(calculator_view, "_events_subscribed", True)

    def test_wakeup_loads_trucks(self, calculator_view, mock_fleet_service):
        """wakeup() calls _load_trucks."""
        calculator_view.wakeup()
        # load_trucks was already called in __init__, wakeup calls it again
        assert mock_fleet_service.get_trucks.call_count >= 2

    def test_truck_selection_sets_fuel(self, calculator_view, mock_fleet_service):
        """Selecting a truck updates the fuel consumption value."""
        calculator_view._on_truck_selected(0)
        assert calculator_view._selected_truck_fuel == 28.5
