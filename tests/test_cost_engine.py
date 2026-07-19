"""Tests for services.cost_engine — CostEngineService.

Covers both the typed interface (CostEstimateRequest →
CostEstimateOperationResult) and the legacy dict-based path.

All external dependencies (FuelPriceService, FleetRepository, Config) are
mocked so that tests are deterministic and fast.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from models.cost_models import CostBreakdown, CostEstimateRequest, CostEstimateResult
from services.cost_engine import CostEngineService


class TestCostEngineService:
    """Unit tests for CostEngineService (all collaborators mocked)."""

    # ------------------------------------------------------------------
    # Per-test setup — engine with a fixed fuel price (no live service)
    # ------------------------------------------------------------------

    def setup_method(self):
        """Create a fresh engine with a deterministic fuel price."""
        self.engine = CostEngineService(fuel_price_eur_per_liter=1.5)

    # ==================================================================
    # COUNTRY_FACTORS — static mapping
    # ==================================================================

    def test_country_factors_ro_is_baseline(self):
        """COUNTRY_FACTORS['RO'] is 1.0 (baseline)."""
        assert CostEngineService.COUNTRY_FACTORS["RO"] == 1.0

    def test_country_factors_de_multiplier(self):
        """COUNTRY_FACTORS['DE'] is 1.2."""
        assert CostEngineService.COUNTRY_FACTORS["DE"] == 1.2

    def test_country_factors_fr_multiplier(self):
        """COUNTRY_FACTORS['FR'] is 1.3."""
        assert CostEngineService.COUNTRY_FACTORS["FR"] == 1.3

    def test_country_factors_it_multiplier(self):
        """COUNTRY_FACTORS['IT'] is 1.25."""
        assert CostEngineService.COUNTRY_FACTORS["IT"] == 1.25

    def test_country_factors_default_is_1_0(self):
        """COUNTRY_FACTORS['DEFAULT'] is 1.0."""
        assert CostEngineService.COUNTRY_FACTORS["DEFAULT"] == 1.0

    def test_country_factors_immutable_across_instances(self):
        """COUNTRY_FACTORS is a class-level dict, shared across instances."""
        e1 = CostEngineService()
        e2 = CostEngineService()
        assert e1.COUNTRY_FACTORS is e2.COUNTRY_FACTORS
        assert e1.COUNTRY_FACTORS["RO"] == 1.0

    # ==================================================================
    # ROAD_CLASS_FACTOR — static mapping
    # ==================================================================

    def test_road_class_motorway_factor(self):
        """ROAD_CLASS_FACTOR['motorway'] is 1.0."""
        assert CostEngineService.ROAD_CLASS_FACTOR["motorway"] == 1.0

    def test_road_class_trunk_factor(self):
        """ROAD_CLASS_FACTOR['trunk'] is 1.0."""
        assert CostEngineService.ROAD_CLASS_FACTOR["trunk"] == 1.0

    def test_road_class_primary_factor(self):
        """ROAD_CLASS_FACTOR['primary'] is 0.8."""
        assert CostEngineService.ROAD_CLASS_FACTOR["primary"] == 0.8

    def test_road_class_secondary_factor(self):
        """ROAD_CLASS_FACTOR['secondary'] is 0.5."""
        assert CostEngineService.ROAD_CLASS_FACTOR["secondary"] == 0.5

    def test_road_class_tertiary_factor(self):
        """ROAD_CLASS_FACTOR['tertiary'] is 0.2."""
        assert CostEngineService.ROAD_CLASS_FACTOR["tertiary"] == 0.2

    def test_road_class_default_factor(self):
        """ROAD_CLASS_FACTOR['default'] is 0.3."""
        assert CostEngineService.ROAD_CLASS_FACTOR["default"] == 0.3

    # ==================================================================
    # Fuel price property
    # ==================================================================

    def test_fuel_price_returns_fixed_when_set(self):
        """fuel_price returns the explicitly passed value."""
        engine = CostEngineService(fuel_price_eur_per_liter=2.0)
        assert engine.fuel_price == 2.0

    def test_fuel_price_caches_fixed_value(self):
        """fuel_price returns same fixed value every call, no service lookup."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.5)
        assert engine.fuel_price == 1.5
        assert engine.fuel_price == 1.5

    @patch("services.cost_engine.FuelPriceService")
    def test_fuel_price_fallback_to_service(self, mock_fps_cls):
        """fuel_price falls back to FuelPriceService when no fixed price given."""
        mock_instance = MagicMock()
        mock_instance.get_price.return_value = 1.8
        mock_fps_cls.return_value = mock_instance

        engine = CostEngineService(country_code="DE")
        assert engine.fuel_price == 1.8
        mock_instance.get_price.assert_called_once_with("DE")

    @patch("services.cost_engine.FuelPriceService")
    def test_fuel_price_uses_default_country(self, mock_fps_cls):
        """fuel_price queries FuelPriceService with the engine's default country."""
        mock_instance = MagicMock()
        mock_instance.get_price.return_value = 1.7
        mock_fps_cls.return_value = mock_instance

        engine = CostEngineService(country_code="FR")
        _ = engine.fuel_price
        mock_instance.get_price.assert_called_once_with("FR")

    @patch("services.cost_engine.FuelPriceService")
    def test_fuel_price_fallback_country_not_in_service(self, mock_fps_cls):
        """When the service returns a price for a non-standard country, it's used."""
        mock_instance = MagicMock()
        mock_instance.get_price.return_value = 1.99
        mock_fps_cls.return_value = mock_instance

        engine = CostEngineService(country_code="XX")
        assert engine.fuel_price == 1.99

    # ==================================================================
    # Typed estimate() — CostEstimateRequest interface
    # ==================================================================

    def test_estimate_typed_returns_operation_result(self):
        """estimate(CostEstimateRequest) returns CostEstimateOperationResult."""
        request = CostEstimateRequest(distance_km=1000, consumption_l_per_100km=30)
        result = self.engine.estimate(request)
        assert result.success is True
        assert isinstance(result.data, CostEstimateResult)
        assert isinstance(result.data.breakdown, CostBreakdown)

    def test_estimate_typed_correct_breakdown(self):
        """Typed estimate computes fuel, toll, driver, extras and total correctly."""
        request = CostEstimateRequest(
            distance_km=1000,
            consumption_l_per_100km=30,
            toll_cost_eur=150.0,
            driver_daily_rate=200.0,
            days=2,
            extra_costs={"parking": 50, "tolls_extra": 30},
        )
        result = self.engine.estimate(request)
        bd = result.data.breakdown

        # fuel = 1000 * 30 / 100 * 1.5 = 450
        assert bd.fuel_cost == 450.0
        assert bd.toll_cost == 150.0
        # driver = 200 * 2 = 400
        assert bd.driver_cost == 400.0
        assert bd.extra_costs == {"parking": 50, "tolls_extra": 30}
        # total = 450 + 150 + 400 + 80 = 1080
        assert bd.total_cost == 1080.0
        # cost_per_km = 1080 / 1000 = 1.08
        assert bd.cost_per_km == 1.08
        assert bd.currency == "EUR"

    def test_estimate_typed_request_defaults(self):
        """Typed estimate uses default values for optional request fields."""
        request = CostEstimateRequest(distance_km=500, consumption_l_per_100km=30)
        result = self.engine.estimate(request)
        bd = result.data.breakdown

        # fuel = 500 * 30 / 100 * 1.5 = 225
        assert bd.fuel_cost == 225.0
        # defaults: toll=0, driver=0, days=1, extras={}
        assert bd.toll_cost == 0.0
        assert bd.driver_cost == 0.0
        assert bd.extra_costs == {}
        assert bd.total_cost == 225.0
        assert bd.cost_per_km == 0.45  # 225 / 500

    def test_estimate_typed_extra_costs_included_in_total(self):
        """Extra costs are summed and added to total."""
        request = CostEstimateRequest(
            distance_km=100,
            consumption_l_per_100km=30,
            extra_costs={"toll": 20, "ferry": 15, "parking": 10},
        )
        result = self.engine.estimate(request)
        bd = result.data.breakdown
        assert bd.total_cost == pytest.approx(bd.fuel_cost + 45.0)

    def test_estimate_typed_cost_per_km_precision(self):
        """cost_per_km is rounded to 4 decimal places."""
        request = CostEstimateRequest(distance_km=3, consumption_l_per_100km=30)
        result = self.engine.estimate(request)
        # fuel = 3 * 30 / 100 * 1.5 = 1.35
        # total = 1.35, cost_per_km = 1.35 / 3 = 0.45
        assert result.data.breakdown.cost_per_km == 0.45

    def test_estimate_typed_result_metadata(self):
        """Result contains distance_km, days, and truck_info from request."""
        request = CostEstimateRequest(
            distance_km=750, consumption_l_per_100km=30, days=3
        )
        result = self.engine.estimate(request)
        assert result.data.distance_km == 750
        assert result.data.days == 3

    def test_estimate_typed_with_currency(self):
        """Currency is propagated from request to breakdown."""
        request = CostEstimateRequest(
            distance_km=100, consumption_l_per_100km=30, currency="USD"
        )
        result = self.engine.estimate(request)
        assert result.data.breakdown.currency == "USD"

    def test_estimate_typed_empty_truck_info(self):
        """truck_info is empty when no truck_id is provided."""
        request = CostEstimateRequest(distance_km=100, consumption_l_per_100km=30)
        result = self.engine.estimate(request)
        assert result.data.truck_info == ""

    # ==================================================================
    # Typed estimate — truck resolution via fleet_repo
    # ==================================================================

    def test_estimate_typed_resolves_truck_info(self):
        """truck_info is populated from fleet_repo when truck_id is given."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "manufacturer": "Volvo",
            "model": "FH",
            "plate_number": "B-123-ABC",
        }
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        request = CostEstimateRequest(
            distance_km=100, truck_id=1, consumption_l_per_100km=30
        )
        result = engine.estimate(request)
        assert result.data.truck_info == "Volvo FH (B-123-ABC)"
        mock_repo.get_by_id.assert_called_once_with(1)

    def test_estimate_typed_truck_info_no_plate(self):
        """truck_info omits plate when plate_number is missing."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "manufacturer": "MAN",
            "model": "TGX",
        }
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        request = CostEstimateRequest(
            distance_km=100, truck_id=1, consumption_l_per_100km=30
        )
        result = engine.estimate(request)
        assert result.data.truck_info == "MAN TGX"

    def test_estimate_typed_truck_info_empty_when_not_found(self):
        """truck_info is empty when truck_id not found in fleet_repo."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        request = CostEstimateRequest(
            distance_km=100, truck_id=99, consumption_l_per_100km=30
        )
        result = engine.estimate(request)
        assert result.data.truck_info == ""

    def test_estimate_typed_consumption_from_request_takes_priority(self):
        """consumption_l_per_100km from request is used over truck lookup."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"fuel_consumption": 40}  # truck says 40
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        request = CostEstimateRequest(
            distance_km=100,
            consumption_l_per_100km=30,  # request says 30 → wins
            truck_id=1,
        )
        result = engine.estimate(request)
        # fuel = 100 * 30 / 100 * 1.5 = 45
        assert result.data.breakdown.fuel_cost == 45.0

    def test_estimate_typed_consumption_from_truck_fallback(self):
        """When request has no consumption, falls back to truck's value."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"fuel_consumption": 35}
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        request = CostEstimateRequest(distance_km=100, truck_id=1)
        result = engine.estimate(request)
        # fuel = 100 * 35 / 100 * 1.5 = 52.5
        assert result.data.breakdown.fuel_cost == 52.5

    def test_estimate_typed_consumption_default_when_no_truck(self):
        """When neither request nor truck has consumption, default is 34.0."""
        request = CostEstimateRequest(distance_km=100)
        result = self.engine.estimate(request)
        # fuel = 100 * 34.0 / 100 * 1.5 = 51.0
        assert result.data.breakdown.fuel_cost == 51.0

    def test_estimate_typed_fuel_price_from_request(self):
        """fuel_price_per_liter from request overrides engine default."""
        request = CostEstimateRequest(
            distance_km=100,
            consumption_l_per_100km=30,
            fuel_price_per_liter=2.0,
        )
        result = self.engine.estimate(request)
        # fuel = 100 * 30 / 100 * 2.0 = 60.0
        assert result.data.breakdown.fuel_cost == 60.0

    # ==================================================================
    # Typed estimate — error handling
    # ==================================================================

    def test_estimate_typed_handles_consumption_resolution_error(self):
        """When _resolve_consumption raises, result is an error ServiceResult."""
        request = CostEstimateRequest(distance_km=100, consumption_l_per_100km=30)
        with patch.object(
            self.engine, "_resolve_consumption", side_effect=ValueError("bad fuel data")
        ):
            result = self.engine.estimate(request)
            assert result.success is False
            assert result.errors[0].code == "ESTIMATION_ERROR"

    def test_estimate_typed_handles_zero_division_gracefully(self):
        """Zero distance in typed path is rejected by Pydantic before reaching engine."""
        with pytest.raises(ValueError, match="Distance must be positive"):
            CostEstimateRequest(distance_km=0)

    def test_estimate_typed_negative_distance_rejected(self):
        """Negative distance in typed path is rejected by Pydantic."""
        with pytest.raises(ValueError, match="Distance must be positive"):
            CostEstimateRequest(distance_km=-100)

    # ==================================================================
    # Legacy estimate() — dict-based interface (deprecated path)
    # ==================================================================

    def test_estimate_legacy_basic(self):
        """Legacy estimate returns expected fuel calculations."""
        result = self.engine.estimate(
            1000.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        # fuel_liters = (1000 / 100) * 30 = 300
        assert result["fuel_liters"] == 300.0
        # fuel_cost = 300 * 1.5 = 450
        assert result["fuel_cost"] == 450.0
        assert result["toll_cost"] > 0
        assert result["total_cost"] == pytest.approx(
            result["fuel_cost"] + result["toll_cost"]
        )

    def test_estimate_legacy_none_distance_returns_zeros(self):
        """None distance returns all-zero dict."""
        result = self.engine.estimate(None, {}, country_code="RO")
        assert result == {
            "fuel_liters": 0.0,
            "fuel_cost": 0.0,
            "toll_cost": 0.0,
            "total_cost": 0.0,
        }

    # ==================================================================
    # COUNTRY_FACTORS applied in legacy toll calculation
    # ==================================================================

    def test_legacy_country_factor_de_higher_than_ro(self):
        """DE (1.2) produces higher toll than RO (1.0), all else equal."""
        truck = {"fuel_consumption_l_per_100km": 30}
        result_ro = self.engine.estimate(100.0, truck, country_code="RO")
        result_de = self.engine.estimate(100.0, truck, country_code="DE")
        assert result_de["toll_cost"] == pytest.approx(result_ro["toll_cost"] * 1.2)

    def test_legacy_country_factor_france(self):
        """FR (1.3) toll is 1.3× RO toll."""
        truck = {"fuel_consumption_l_per_100km": 30}
        result_ro = self.engine.estimate(100.0, truck, country_code="RO")
        result_fr = self.engine.estimate(100.0, truck, country_code="FR")
        assert result_fr["toll_cost"] == pytest.approx(result_ro["toll_cost"] * 1.3)

    def test_legacy_country_factor_italy(self):
        """IT (1.25) toll is 1.25× RO toll."""
        truck = {"fuel_consumption_l_per_100km": 30}
        result_ro = self.engine.estimate(100.0, truck, country_code="RO")
        result_it = self.engine.estimate(100.0, truck, country_code="IT")
        assert result_it["toll_cost"] == pytest.approx(result_ro["toll_cost"] * 1.25)

    def test_legacy_unknown_country_uses_default_factor(self):
        """Unknown country code falls back to DEFAULT factor (1.0)."""
        truck = {"fuel_consumption_l_per_100km": 30}
        result_ro = self.engine.estimate(100.0, truck, country_code="RO")
        result_xx = self.engine.estimate(100.0, truck, country_code="XX")
        assert result_xx["toll_cost"] == result_ro["toll_cost"]

    def test_legacy_country_factor_case_sensitive(self):
        """Country code lookup is case-sensitive — 'ro' not in dict, uses DEFAULT."""
        truck = {"fuel_consumption_l_per_100km": 30}
        result_ro = self.engine.estimate(100.0, truck, country_code="ro")  # lowercase
        result_default = self.engine.estimate(100.0, truck, country_code="RO")
        # Lowercase 'ro' is not found → DEFAULT (1.0) which equals RO (1.0)
        assert result_ro["toll_cost"] == result_default["toll_cost"]

    # ==================================================================
    # ROAD_CLASS_FACTOR applied in legacy toll calculation
    # ==================================================================

    def test_legacy_road_class_motorway_highest_toll(self):
        """Motorway (1.0) toll is 2× secondary (0.5)."""
        truck = {"fuel_consumption_l_per_100km": 30}
        route_mw = {"road_class": "motorway"}
        route_sec = {"road_class": "secondary"}
        result_mw = self.engine.estimate(100.0, truck, route_mw, country_code="RO")
        result_sec = self.engine.estimate(100.0, truck, route_sec, country_code="RO")
        assert result_mw["toll_cost"] == pytest.approx(result_sec["toll_cost"] * 2.0)

    def test_legacy_road_class_primary(self):
        """Primary road factor 0.8 reduces toll by 20% vs motorway."""
        truck = {"fuel_consumption_l_per_100km": 30}
        route_mw = {"road_class": "motorway"}
        route_pri = {"road_class": "primary"}
        result_mw = self.engine.estimate(100.0, truck, route_mw, country_code="RO")
        result_pri = self.engine.estimate(100.0, truck, route_pri, country_code="RO")
        assert result_pri["toll_cost"] == pytest.approx(result_mw["toll_cost"] * 0.8)

    def test_legacy_road_class_tertiary_lowest_toll(self):
        """Tertiary road factor 0.2 gives lowest toll among defined classes."""
        truck = {"fuel_consumption_l_per_100km": 30}
        route_ter = {"road_class": "tertiary"}
        route_pri = {"road_class": "primary"}
        result_ter = self.engine.estimate(100.0, truck, route_ter, country_code="RO")
        result_pri = self.engine.estimate(100.0, truck, route_pri, country_code="RO")
        assert result_ter["toll_cost"] < result_pri["toll_cost"]

    def test_legacy_unknown_road_class_defaults_to_0_5(self):
        """Unknown road_class string falls back to factor 0.5."""
        from config import Config

        truck = {"fuel_consumption_l_per_100km": 30}
        route = {"road_class": "unclassified"}
        result = self.engine.estimate(100.0, truck, route, country_code="RO")
        expected_toll = 100.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        assert result["toll_cost"] == pytest.approx(expected_toll)

    def test_legacy_no_road_class_uses_default_0_5(self):
        """When route_details has no road_class key, default factor 0.5 is used."""
        from config import Config

        truck = {"fuel_consumption_l_per_100km": 30}
        route = {"some_other_key": True}
        result = self.engine.estimate(100.0, truck, route, country_code="RO")
        expected_toll = 100.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        assert result["toll_cost"] == pytest.approx(expected_toll)

    def test_legacy_no_route_details_uses_default_factor(self):
        """When route_details is None, default road factor 0.5."""
        from config import Config

        truck = {"fuel_consumption_l_per_100km": 30}
        result = self.engine.estimate(100.0, truck, route_details=None, country_code="RO")
        expected_toll = 100.0 * Config.DEFAULT_TOLL_RATE * 1.0 * 0.5
        assert result["toll_cost"] == pytest.approx(expected_toll)

    # ==================================================================
    # Country factor + road class factor stacking
    # ==================================================================

    def test_country_and_road_class_stack_multiplicatively(self):
        """Country factor × road class factor applied to toll_rate."""
        from config import Config

        truck = {"fuel_consumption_l_per_100km": 30}
        route = {"road_class": "primary"}  # 0.8
        result = self.engine.estimate(100.0, truck, route, country_code="DE")  # 1.2
        expected_toll = 100.0 * Config.DEFAULT_TOLL_RATE * 1.2 * 0.8
        assert result["toll_cost"] == pytest.approx(expected_toll)

    def test_country_and_road_class_stacked_multiple_combos(self):
        """Different (country, road_class) combos produce distinct tolls."""
        from config import Config

        truck = {"fuel_consumption_l_per_100km": 30}

        # Combo 1: FR (1.3) × secondary (0.5)
        r1 = self.engine.estimate(
            100.0, truck, {"road_class": "secondary"}, country_code="FR"
        )
        expected_1 = 100.0 * Config.DEFAULT_TOLL_RATE * 1.3 * 0.5
        assert r1["toll_cost"] == pytest.approx(expected_1)

        # Combo 2: IT (1.25) × motorway (1.0)
        r2 = self.engine.estimate(
            100.0, truck, {"road_class": "motorway"}, country_code="IT"
        )
        expected_2 = 100.0 * Config.DEFAULT_TOLL_RATE * 1.25 * 1.0
        assert r2["toll_cost"] == pytest.approx(expected_2)

        # Verify they differ
        assert r1["toll_cost"] != r2["toll_cost"]

    # ==================================================================
    # Fuel consumption resolution (legacy path)
    # ==================================================================

    def test_legacy_consumption_primary_key(self):
        """fuel_consumption_l_per_100km is the primary consumption key."""
        result = self.engine.estimate(
            100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        assert result["fuel_liters"] == 30.0  # (100/100)*30

    def test_legacy_consumption_fallback_key(self):
        """fuel_consumption (legacy key) is used when primary key missing."""
        result = self.engine.estimate(
            100.0, {"fuel_consumption": 35}, country_code="RO"
        )
        assert result["fuel_liters"] == 35.0

    def test_legacy_consumption_primary_overrides_fallback(self):
        """When both keys present, fuel_consumption_l_per_100km wins."""
        result = self.engine.estimate(
            100.0,
            {"fuel_consumption_l_per_100km": 30, "fuel_consumption": 40},
            country_code="RO",
        )
        assert result["fuel_liters"] == 30.0

    def test_legacy_consumption_default_when_no_keys(self):
        """Default consumption of 34.0 L/100km when no key present."""
        result = self.engine.estimate(100.0, {}, country_code="RO")
        expected_liters = (100.0 / 100.0) * 34.0
        assert result["fuel_liters"] == expected_liters

    # ==================================================================
    # Edge cases
    # ==================================================================

    def test_legacy_zero_distance(self):
        """Zero distance produces zero fuel and toll costs."""
        result = self.engine.estimate(0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
        assert result["fuel_liters"] == 0.0
        assert result["fuel_cost"] == 0.0
        assert result["toll_cost"] == 0.0
        # total = fuel + toll = 0
        assert result["total_cost"] == 0.0

    def test_legacy_very_large_distance(self):
        """Very large distance (1M km) produces sensible results."""
        result = self.engine.estimate(
            1_000_000.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        assert result["fuel_liters"] == 300_000.0
        assert result["fuel_cost"] == 450_000.0
        assert result["toll_cost"] > 0
        assert result["total_cost"] == pytest.approx(
            result["fuel_cost"] + result["toll_cost"]
        )

    def test_legacy_very_small_distance(self):
        """Very small distance (0.001 km) produces proportional results."""
        result = self.engine.estimate(
            0.001, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        # fuel_liters = (0.001 / 100) * 30 = 0.0003 → rounded to 0.0
        assert result["fuel_liters"] == 0.0
        assert isinstance(result["total_cost"], float)

    def test_legacy_negative_distance(self):
        """Negative distance produces negative fuel values (code does not guard)."""
        result = self.engine.estimate(
            -100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        assert result["fuel_liters"] == -30.0
        assert result["fuel_cost"] == -45.0

    def test_legacy_zero_fuel_price(self):
        """Zero fuel price results in zero fuel cost."""
        engine = CostEngineService(fuel_price_eur_per_liter=0.0)
        result = engine.estimate(
            100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        assert result["fuel_cost"] == 0.0
        assert result["total_cost"] == pytest.approx(result["toll_cost"])

    def test_legacy_very_high_fuel_price(self):
        """Very high fuel price (10.0 EUR/L) produces proportionally higher costs."""
        engine = CostEngineService(fuel_price_eur_per_liter=10.0)
        result = engine.estimate(
            100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO"
        )
        assert result["fuel_cost"] == 300.0  # (100/100)*30*10

    # ==================================================================
    # Toll rate from Config
    # ==================================================================

    @patch("services.cost_engine.Config")
    def test_toll_rate_from_config(self, mock_config):
        """Toll cost uses Config.DEFAULT_TOLL_RATE."""
        mock_config.DEFAULT_TOLL_RATE = 0.12
        engine = CostEngineService(fuel_price_eur_per_liter=1.5)
        result = engine.estimate(100.0, {"fuel_consumption_l_per_100km": 30}, country_code="RO")
        expected_toll = 100.0 * 0.12 * 1.0 * 0.5
        assert result["toll_cost"] == pytest.approx(expected_toll)

    # ==================================================================
    # estimate_for_truck — convenience method
    # ==================================================================

    def test_estimate_for_truck_no_fleet_repo_returns_error(self):
        """estimate_for_truck returns error when fleet_repo is None."""
        engine = CostEngineService(fuel_price_eur_per_liter=1.5)
        result = engine.estimate_for_truck(100.0, 1)
        assert result.success is False
        assert result.errors[0].code == "FLEET_REPO_MISSING"

    def test_estimate_for_truck_not_found_returns_error(self):
        """estimate_for_truck returns TRUCK_NOT_FOUND error when truck missing."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        result = engine.estimate_for_truck(100.0, 999)
        assert result.success is False
        assert result.errors[0].code == "TRUCK_NOT_FOUND"
        mock_repo.get_by_id.assert_called_once_with(999)

    def test_estimate_for_truck_success(self):
        """estimate_for_truck delegates to typed estimate with truck consumption."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"fuel_consumption": 30}
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        result = engine.estimate_for_truck(100.0, 42)
        assert result.success is True
        assert result.data.breakdown.fuel_cost == 45.0  # (100*30/100)*1.5
        # get_by_id is called by estimate_for_truck + _resolve_truck_info
        mock_repo.get_by_id.assert_any_call(42)
        assert mock_repo.get_by_id.call_count == 2

    def test_estimate_for_truck_includes_truck_info(self):
        """estimate_for_truck populates truck_info in the result."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "manufacturer": "Scania",
            "model": "R500",
            "plate_number": "SB-123-XYZ",
            "fuel_consumption": 32,
        }
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        result = engine.estimate_for_truck(100.0, 7)
        assert result.data.truck_info == "Scania R500 (SB-123-XYZ)"

    def test_estimate_for_truck_error_on_repo_failure(self):
        """estimate_for_truck catches repo exceptions and returns error."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.side_effect = RuntimeError("DB timeout")
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo
        )
        result = engine.estimate_for_truck(100.0, 1)
        assert result.success is False
        assert result.errors[0].code == "ESTIMATE_TRUCK_ERROR"

    # ==================================================================
    # Typed estimate() — dispatch routing
    # ==================================================================

    def test_estimate_typed_dispatched_correctly(self):
        """estimate(CostEstimateRequest) dispatches to typed path, not legacy."""
        request = CostEstimateRequest(distance_km=100, consumption_l_per_100km=30)
        with patch.object(
            self.engine, "_estimate_typed", wraps=self.engine._estimate_typed
        ) as mock_typed:
            with patch.object(
                self.engine,
                "_estimate_legacy",
                wraps=self.engine._estimate_legacy,
            ) as mock_legacy:
                self.engine.estimate(request)
                mock_typed.assert_called_once()
                mock_legacy.assert_not_called()

    def test_estimate_legacy_dispatched_correctly(self):
        """estimate(positional args) dispatches to legacy path."""
        with patch.object(
            self.engine, "_estimate_legacy", wraps=self.engine._estimate_legacy
        ) as mock_legacy:
            with patch.object(
                self.engine,
                "_estimate_typed",
                wraps=self.engine._estimate_typed,
            ) as mock_typed:
                self.engine.estimate(100.0, {}, country_code="RO")
                mock_legacy.assert_called_once()
                mock_typed.assert_not_called()

    def test_estimate_legacy_kwargs_dispatched_correctly(self):
        """estimate(distance_km=..., truck=...) dispatches to legacy path."""
        with patch.object(
            self.engine, "_estimate_legacy", wraps=self.engine._estimate_legacy
        ) as mock_legacy:
            self.engine.estimate(
                distance_km=100.0, truck={}, country_code="RO"
            )
            mock_legacy.assert_called_once()

    def test_estimate_typed_emits_info_log(self):
        """Typed estimate logs request and result."""
        request = CostEstimateRequest(distance_km=100, consumption_l_per_100km=30)
        with patch("services.cost_engine.logger") as mock_logger:
            self.engine.estimate(request)
            assert mock_logger.info.call_count >= 2  # request + result

    # ==================================================================
    # Typed estimate — rounding
    # ==================================================================

    def test_estimate_typed_rounding_precision(self):
        """Breakdown values are rounded to 2 decimal places."""
        request = CostEstimateRequest(
            distance_km=1, consumption_l_per_100km=30
        )
        result = self.engine.estimate(request)
        bd = result.data.breakdown
        # fuel = 1 * 30 / 100 * 1.5 = 0.45
        assert bd.fuel_cost == 0.45
        assert bd.total_cost == 0.45
