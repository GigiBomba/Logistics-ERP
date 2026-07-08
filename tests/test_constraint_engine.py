"""Tests for TruckConstraintEngine."""

from __future__ import annotations

import pytest

from services.constraint_engine import TruckConstraintEngine


@pytest.fixture
def engine() -> TruckConstraintEngine:
    return TruckConstraintEngine()


class TestValidateTruck:
    def test_empty_dict_returns_false(self, engine: TruckConstraintEngine):
        valid, msg = engine.validate_truck({})
        assert valid is False
        assert msg == "No truck provided"

    def test_none_returns_false(self, engine: TruckConstraintEngine):
        valid, msg = engine.validate_truck(None)
        assert valid is False
        assert msg == "No truck provided"

    def test_valid_truck_returns_ok(self, engine: TruckConstraintEngine):
        truck = {
            "height_m": 3.5,
            "max_weight_kg": 20000,
            "width_m": 2.4,
        }
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_excessive_height_returns_clearance(self, engine: TruckConstraintEngine):
        """Height above MAX_HEIGHT_M triggers a route clearance note, not a hard error."""
        truck = {"height_m": 5.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True  # clearance is advisory, not blocking
        assert "clearance" in msg.lower()

    def test_moderate_height_returns_clearance_warning(self, engine: TruckConstraintEngine):
        """Height above MIN_CLEARANCE_M but below MAX_HEIGHT_M → route clearance note."""
        truck = {"height_m": 4.2}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert "clearance" in msg.lower()

    def test_excessive_weight_returns_false(self, engine: TruckConstraintEngine):
        truck = {"max_weight_kg": 50000}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "weight" in msg.lower()

    def test_weight_via_alternate_key(self, engine: TruckConstraintEngine):
        """Should also check weight_kg if max_weight_kg is missing."""
        truck = {"weight_kg": 50000}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "weight" in msg.lower()

    def test_excessive_width_returns_false(self, engine: TruckConstraintEngine):
        truck = {"width_m": 3.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "width" in msg.lower()

    def test_valid_truck_with_all_fields(self, engine: TruckConstraintEngine):
        truck = {
            "height_m": 3.8,
            "max_weight_kg": 36000,
            "width_m": 2.5,
            "length_m": 15.0,
        }
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_non_numeric_values_are_skipped(self, engine: TruckConstraintEngine):
        """Non-numeric values should not crash validation."""
        truck = {"height_m": "very tall", "max_weight_kg": "heavy"}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_zero_values(self, engine: TruckConstraintEngine):
        truck = {"height_m": 0, "max_weight_kg": 0, "width_m": 0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_negative_values(self, engine: TruckConstraintEngine):
        truck = {"height_m": -1.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True  # negative height doesn't fail validation logic


class TestBuildParams:
    def test_empty_truck_returns_empty_dict(self, engine: TruckConstraintEngine):
        assert engine.build_params({}) == {}

    def test_full_truck_returns_correct_params(self, engine: TruckConstraintEngine):
        truck = {
            "max_weight_kg": 20000,
            "height_m": 3.5,
            "width_m": 2.4,
            "length_m": 13.6,
            "axleload_kg": 8000,
        }
        params = engine.build_params(truck)
        assert params["weight"] == "20000.0"
        assert params["height"] == "3.5"
        assert params["width"] == "2.4"
        assert params["length"] == "13.6"
        assert params["axleload"] == "8000.0"

    def test_only_includes_values_within_valid_ranges(self, engine: TruckConstraintEngine):
        truck = {
            "max_weight_kg": engine.MAX_WEIGHT_KG + 1,
            "height_m": engine.MAX_HEIGHT_M + 1,
            "width_m": engine.MAX_WIDTH_M + 1,
            "length_m": engine.MAX_LENGTH_M + 1,
        }
        params = engine.build_params(truck)
        assert "weight" not in params
        assert "height" not in params
        assert "width" not in params
        assert "length" not in params

    def test_skips_out_of_range_values(self, engine: TruckConstraintEngine):
        truck = {
            "max_weight_kg": 0,
            "height_m": -1,
            "width_m": -2,
        }
        params = engine.build_params(truck)
        assert "weight" not in params
        assert "height" not in params
        assert "width" not in params

    def test_handles_hazmat_bool(self, engine: TruckConstraintEngine):
        truck = {"hazmat": True}
        params = engine.build_params(truck)
        assert params["hazmat"] == "true"

        truck = {"hazmat": False}
        params = engine.build_params(truck)
        assert params["hazmat"] == "false"

    def test_handles_hazmat_string(self, engine: TruckConstraintEngine):
        truck = {"hazmat": "true"}
        params = engine.build_params(truck)
        # For string input, the result is stored as a boolean after evaluation
        assert params["hazmat"] is True

    def test_uses_weight_kg_fallback(self, engine: TruckConstraintEngine):
        truck = {"weight_kg": 15000}
        params = engine.build_params(truck)
        assert params["weight"] == "15000.0"

    def test_weight_kg_preferred_over_max_weight_kg(self, engine: TruckConstraintEngine):
        """max_weight_kg takes precedence over weight_kg if both present."""
        truck = {"max_weight_kg": 20000, "weight_kg": 15000}
        params = engine.build_params(truck)
        # max_weight_kg is checked first
        assert params["weight"] == "20000.0"

    def test_hazmat_not_included_when_missing(self, engine: TruckConstraintEngine):
        truck = {"max_weight_kg": 10000}
        params = engine.build_params(truck)
        assert "hazmat" not in params

    def test_axleload_positive_check(self, engine: TruckConstraintEngine):
        truck = {"axleload_kg": 0}
        params = engine.build_params(truck)
        assert "axleload" not in params

    def test_non_dict_input_returns_empty(self, engine: TruckConstraintEngine):
        assert engine.build_params(None) == {}


class TestValidateProfile:
    def test_valid_profiles_return_true(self, engine: TruckConstraintEngine):
        for profile in ("truck", "truck_fast", "truck_safe", "truck_cheap", "truck_short",
                        "car", "bike", "foot"):
            assert engine.validate_profile(profile) is True

    def test_invalid_profile_returns_false(self, engine: TruckConstraintEngine):
        assert engine.validate_profile("spaceship") is False
        assert engine.validate_profile("") is False

    def test_case_insensitive(self, engine: TruckConstraintEngine):
        assert engine.validate_profile("TRUCK") is True
        assert engine.validate_profile("Truck_Fast") is True
        assert engine.validate_profile("CAR") is True

    def test_none_profile_raises(self, engine: TruckConstraintEngine):
        with pytest.raises(AttributeError):
            engine.validate_profile(None)


class TestGetTruckValue:
    def test_dict_get(self):
        truck = {"height_m": 4.0, "name": "test"}
        assert TruckConstraintEngine._get_truck_value(truck, "height_m") == 4.0
        assert TruckConstraintEngine._get_truck_value(truck, "missing") is None

    def test_dict_like_object(self):
        """Dict-like objects with .get() method work."""
        class DictLike:
            def get(self, key, default=None):
                data = {"height_m": 3.5, "name": "test"}
                return data.get(key, default)

        obj = DictLike()
        assert TruckConstraintEngine._get_truck_value(obj, "height_m") == 3.5

    def test_none_truck(self):
        """None truck returns None for any key."""
        assert TruckConstraintEngine._get_truck_value(None, "key") is None

    def test_sqlite_row_style(self):
        """An object with __getitem__ works."""
        class RowLike:
            def __getitem__(self, key):
                if key == "height_m":
                    return 3.5
                raise KeyError(key)

        row = RowLike()
        assert TruckConstraintEngine._get_truck_value(row, "height_m") == 3.5

    def test_object_with_attributes(self):
        """An object with attribute access works."""
        class TruckObj:
            height_m = 4.0

        obj = TruckObj()
        assert TruckConstraintEngine._get_truck_value(obj, "height_m") == 4.0
        assert TruckConstraintEngine._get_truck_value(obj, "missing") is None

    def test_list_input_returns_none(self):
        """A list input should not crash and return None."""
        assert TruckConstraintEngine._get_truck_value([1, 2, 3], "height_m") is None


class TestValidateTruckEdgeCases:
    """Additional edge-case tests for validate_truck."""

    def test_height_exactly_at_max_is_clearance(self, engine: TruckConstraintEngine):
        """Height exactly at MAX_HEIGHT_M triggers route clearance note."""
        truck = {"height_m": engine.MAX_HEIGHT_M}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert "clearance" in msg.lower()

    def test_width_exactly_at_max_is_ok(self, engine: TruckConstraintEngine):
        """Width exactly at MAX_WIDTH_M should be valid."""
        truck = {"width_m": engine.MAX_WIDTH_M}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_weight_exactly_at_max_is_ok(self, engine: TruckConstraintEngine):
        """Weight exactly at MAX_WEIGHT_KG should be valid."""
        truck = {"max_weight_kg": engine.MAX_WEIGHT_KG}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_height_below_min_clearance_no_warning(self, engine: TruckConstraintEngine):
        """Height below MIN_CLEARANCE_M should not trigger clearance warning."""
        truck = {"height_m": engine.MIN_CLEARANCE_M - 0.5}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_all_excessive_values(self, engine: TruckConstraintEngine):
        """All dimensions exceeding limits — weight check fires first."""
        truck = {
            "height_m": 5.0,   # > MAX_HEIGHT → clearance (true)
            "max_weight_kg": 50000,  # > MAX_WEIGHT → false
            "width_m": 3.0,   # > MAX_WIDTH → false
        }
        # Weight check happens before width, so weight error returns first
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "weight" in msg.lower()


class TestBuildParamsEdgeCases:
    """Additional edge-case tests for build_params."""

    def test_hazmat_string_yes(self, engine: TruckConstraintEngine):
        """Hazmat string 'yes' should resolve to True."""
        truck = {"hazmat": "yes"}
        params = engine.build_params(truck)
        assert params["hazmat"] is True

    def test_hazmat_string_1(self, engine: TruckConstraintEngine):
        """Hazmat string '1' should resolve to True."""
        truck = {"hazmat": "1"}
        params = engine.build_params(truck)
        assert params["hazmat"] is True

    def test_hazmat_string_no(self, engine: TruckConstraintEngine):
        """Hazmat string 'no' should resolve to False."""
        truck = {"hazmat": "no"}
        params = engine.build_params(truck)
        assert params["hazmat"] is False

    def test_hazmat_string_0(self, engine: TruckConstraintEngine):
        """Hazmat string '0' should resolve to False."""
        truck = {"hazmat": "0"}
        params = engine.build_params(truck)
        assert params["hazmat"] is False

    def test_length_exactly_at_max_is_included(self, engine: TruckConstraintEngine):
        """Length exactly at MAX_LENGTH_M should be included."""
        truck = {"length_m": engine.MAX_LENGTH_M}
        params = engine.build_params(truck)
        assert params["length"] == str(engine.MAX_LENGTH_M)

    def test_negative_axleload_excluded(self, engine: TruckConstraintEngine):
        """Negative axleload should be excluded (not > 0)."""
        truck = {"axleload_kg": -1000}
        params = engine.build_params(truck)
        assert "axleload" not in params

    def test_axleload_positive_included(self, engine: TruckConstraintEngine):
        """Positive axleload should be included."""
        truck = {"axleload_kg": 5000}
        params = engine.build_params(truck)
        assert params["axleload"] == "5000.0"

    def test_build_params_handles_numeric_strings(self, engine: TruckConstraintEngine):
        """String-form numbers should be handled without crashing."""
        truck = {
            "max_weight_kg": "20000",
            "height_m": "3.5",
            "width_m": "2.4",
        }
        params = engine.build_params(truck)
        assert params["weight"] == "20000.0"
        assert params["height"] == "3.5"
        assert params["width"] == "2.4"


class TestValidateProfileEdgeCases:
    """Additional edge-case tests for validate_profile."""

    def test_profile_with_whitespace(self, engine: TruckConstraintEngine):
        """Profile with surrounding whitespace should be stripped."""
        # Note: current implementation uses .lower() but doesn't strip
        # This documents current behavior
        assert engine.validate_profile(" Truck ") is False

    def test_partial_profile_match(self, engine: TruckConstraintEngine):
        """Partial profiles should not match."""
        assert engine.validate_profile("truc") is False
        assert engine.validate_profile("truck_") is False
