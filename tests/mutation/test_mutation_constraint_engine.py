from __future__ import annotations

import pytest

from services.constraint_engine import TruckConstraintEngine

pytestmark = pytest.mark.mutation


class TestKillMutationValidateTruck:
    """Mutation-killing tests for TruckConstraintEngine.validate_truck()."""

    def test_empty_truck_returns_no_truck_provided(self):
        """Kill: not truck -> truck guard mutation (empty dict -> 'No truck provided')."""
        engine = TruckConstraintEngine()
        valid, msg = engine.validate_truck({})
        # not {} is True  -> returns "No truck provided"
        # if truck: with {} is False -> guard skipped, may return "OK" (WRONG)
        assert valid is False
        assert "No truck provided" in msg

    def test_none_truck_returns_no_truck_provided(self):
        """Kill: not truck guard with None input."""
        engine = TruckConstraintEngine()
        valid, msg = engine.validate_truck(None)
        assert valid is False
        assert "No truck provided" in msg

    def test_height_at_min_clearance_no_warning(self):
        """Kill: h > MIN_CLEARANCE_M -> >= mutation (height=4.0 exactly should not warn)."""
        engine = TruckConstraintEngine()
        truck = {
            'height_m': 4.0,
            'max_weight_kg': 10000,
            'width_m': 2.5,
        }
        valid, msg = engine.validate_truck(truck)
        # 4.0 > 4.0 is False  -> passes clearance check
        # 4.0 >= 4.0 is True  -> "requires route clearance" returned early (WRONG)
        assert valid is True
        assert msg == "OK"

    def test_height_at_max_valid(self):
        """Kill: h > MAX_HEIGHT_M -> >= mutation (height=4.0 at max should be valid)."""
        engine = TruckConstraintEngine()
        truck = {
            'height_m': 4.0,
            'max_weight_kg': 10000,
            'width_m': 2.5,
        }
        valid, msg = engine.validate_truck(truck)
        # 4.0 > 4.0 is False -> valid
        # 4.0 >= 4.0 is True -> "exceeds maximum" (WRONG)
        assert valid is True

    def test_weight_at_max_valid(self):
        """Kill: w > MAX_WEIGHT_KG -> >= mutation (40000kg at max should be valid)."""
        engine = TruckConstraintEngine()
        truck = {
            'max_weight_kg': 40000,
            'height_m': 3.5,
            'width_m': 2.5,
        }
        valid, msg = engine.validate_truck(truck)
        # 40000 > 40000 is False -> valid
        # 40000 >= 40000 is True -> "exceeds maximum" (WRONG)
        assert valid is True

    def test_width_at_max_valid(self):
        """Kill: w > MAX_WIDTH_M -> >= mutation (2.55m at max should be valid)."""
        engine = TruckConstraintEngine()
        truck = {
            'width_m': 2.55,
            'height_m': 3.5,
            'max_weight_kg': 10000,
        }
        valid, msg = engine.validate_truck(truck)
        # 2.55 > 2.55 is False -> valid
        # 2.55 >= 2.55 is True -> "exceeds maximum" (WRONG)
        assert valid is True

    def test_excessive_weight_fails_validation(self):
        """Kill: statement deletion — weight guard removed (excessive weight should fail)."""
        engine = TruckConstraintEngine()
        truck = {
            'max_weight_kg': 50000,
            'height_m': 3.5,
            'width_m': 2.5,
        }
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "exceeds maximum" in msg

    def test_excessive_width_fails_validation(self):
        """Kill: statement deletion — width guard removed (excessive width should fail)."""
        engine = TruckConstraintEngine()
        truck = {
            'width_m': 3.0,
            'height_m': 3.5,
            'max_weight_kg': 10000,
        }
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "exceeds maximum" in msg


class TestKillMutationBuildParams:
    """Mutation-killing tests for TruckConstraintEngine.build_params()."""

    def test_zero_weight_excluded_from_params(self):
        """Kill: 0 < w <= -> 0 <= w <= mutation (zero weight should be excluded)."""
        engine = TruckConstraintEngine()
        truck = {
            'max_weight_kg': 0,
            'height_m': 3.5,
            'width_m': 2.5,
        }
        params = engine.build_params(truck)
        # 0 < 0 is False -> weight excluded
        # 0 <= 0 is True  -> weight = "0.0" included (WRONG)
        assert 'weight' not in params

    def test_weight_at_max_included(self):
        """Kill: <= -> < on MAX_WEIGHT_KG (weight exactly at 40000 should be included)."""
        engine = TruckConstraintEngine()
        truck = {
            'max_weight_kg': 40000,
            'height_m': 3.5,
            'width_m': 2.5,
        }
        params = engine.build_params(truck)
        # 0 < 40000 <= 40000 is True -> included
        # 0 < 40000 < 40000 is False -> excluded (WRONG)
        assert 'weight' in params
        assert params['weight'] == '40000.0'

    def test_hazmat_string_no_evaluates_false(self):
        """Kill: hazmat string 'no' evaluates to False in params."""
        engine = TruckConstraintEngine()
        truck = {
            'hazmat': 'no',
            'height_m': 3.5,
            'width_m': 2.5,
            'max_weight_kg': 10000,
        }
        params = engine.build_params(truck)
        assert 'hazmat' in params
        assert params['hazmat'] is False

    def test_hazmat_string_false_evaluates_false(self):
        """Kill: hazmat string 'false' evaluates to False."""
        engine = TruckConstraintEngine()
        truck = {
            'hazmat': 'false',
            'height_m': 3.5,
            'width_m': 2.5,
            'max_weight_kg': 10000,
        }
        params = engine.build_params(truck)
        assert 'hazmat' in params
        assert params['hazmat'] is False

    def test_hazmat_string_yes_evaluates_true(self):
        """Kill: hazmat string 'yes' evaluates to True."""
        engine = TruckConstraintEngine()
        truck = {
            'hazmat': 'yes',
            'height_m': 3.5,
            'width_m': 2.5,
            'max_weight_kg': 10000,
        }
        params = engine.build_params(truck)
        assert 'hazmat' in params
        assert params['hazmat'] is True

    def test_hazmat_string_true_evaluates_true(self):
        """Kill: hazmat string 'true' evaluates to True."""
        engine = TruckConstraintEngine()
        truck = {
            'hazmat': 'true',
            'height_m': 3.5,
            'width_m': 2.5,
            'max_weight_kg': 10000,
        }
        params = engine.build_params(truck)
        assert 'hazmat' in params
        assert params['hazmat'] is True

    def test_hazmat_string_one_evaluates_true(self):
        """Kill: hazmat string '1' evaluates to True."""
        engine = TruckConstraintEngine()
        truck = {
            'hazmat': '1',
            'height_m': 3.5,
            'width_m': 2.5,
            'max_weight_kg': 10000,
        }
        params = engine.build_params(truck)
        assert 'hazmat' in params
        assert params['hazmat'] is True
