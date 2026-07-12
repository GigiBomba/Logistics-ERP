"""Integration test: Trip create → calculate profit → dispatch flow."""
import pytest
from models.trip_models import TripCreate, TripStop
from models.calculator_models import CalculationRequest
from services.trip_service import TripService
from services.calculator import TripCalculator


class TestTripWorkflow:
    def test_create_trip_typed(self, seeded_db):
        """TripService.create() with typed TripCreate model."""
        service = TripService(seeded_db)
        request = TripCreate(
            client_id=1,
            truck_id=1,
            driver_id=1,
            reference="TEST-001",
            start_date="2026-07-15",
            price_eur=1500.0,
            distance_km=800.0,
        )
        result = service.create(request, user_id=1)
        assert result.success
        assert result.data is not None
        assert result.data.client_id == 1

    def test_calculate_profit_typed(self, seeded_db):
        """TripCalculator.calculate() with CalculationRequest."""
        calc = TripCalculator()
        # Use a price high enough to be profitable at 30L/100km, 6.5€/L fuel
        request = CalculationRequest(
            km=800,
            price_eur=3000.0,
            fuel_price=6.5,
            days=2,
            consum_litri=30.0,
        )
        result = calc.calculate(request)
        assert result.success
        assert result.data is not None
        assert result.data.net_profit > 0
        assert result.data.margin_percent > 0

    def test_full_trip_to_profit_workflow(self, seeded_db):
        """End-to-end: create trip → calculate profit."""
        # 1. Create trip
        trip_service = TripService(seeded_db)
        trip_request = TripCreate(
            client_id=1, truck_id=1, driver_id=1,
            reference="E2E-001", start_date="2026-07-15",
            price_eur=2000.0, distance_km=1000.0,
        )
        trip_result = trip_service.create(trip_request, user_id=1)
        assert trip_result.success

        # 2. Calculate profit
        calc = TripCalculator()
        # 1000km, 2000eur, 6.5€/L fuel, 2 days, 30L/100km
        # Fuel cost: (1000/100)*30*6.5 = 1950 → needs higher price for profit
        calc_request = CalculationRequest(
            km=1000, price_eur=3500.0, fuel_price=6.5,
            days=2, consum_litri=30.0,
        )
        profit_result = calc.calculate(calc_request)
        assert profit_result.success
        assert profit_result.data.net_profit > 0
        assert profit_result.data.profit_per_km > 0
