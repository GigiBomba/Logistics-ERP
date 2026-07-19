"""Comprehensive unit tests for TruckConstraintEngine.

Covers initialization, truck validation (dimensions, clearance, hazmat),
parameter building for GraphHopper, and edge cases.
"""
from unittest.mock import MagicMock, patch

import pytest

from services.constraint_engine import TruckConstraintEngine


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Default TruckConstraintEngine instance (logger mocked)."""
    with patch("utils.logger.get_logger", return_value=MagicMock()):
        yield TruckConstraintEngine()


# ── Initialization ────────────────────────────────────────────────────────

class TestInit:
    def test_engine_created_without_logger_on_failure(self):
        """When get_logger fails the engine still instantiates."""
        with patch("utils.logger.get_logger", side_effect=ImportError("no logger")):
            e = TruckConstraintEngine()
            assert e.logger is None

    def test_default_constants_are_set(self, engine):
        assert engine.MIN_CLEARANCE_M == 4.0
        assert engine.MAX_WEIGHT_KG == 40000
        assert engine.MAX_WIDTH_M == 2.55
        assert engine.MAX_HEIGHT_M == 4.0
        assert engine.MAX_LENGTH_M == 16.5


# ── validate_truck ────────────────────────────────────────────────────────

class TestValidateTruck:
    def test_no_truck_returns_false(self, engine):
        valid, msg = engine.validate_truck(None)
        assert valid is False
        assert "No truck provided" in msg

    def test_empty_truck_returns_false(self, engine):
        valid, msg = engine.validate_truck({})
        assert valid is False
        assert "No truck provided" in msg

    # Height

    def test_height_below_clearance_returns_ok(self, engine):
        truck = {"height_m": 3.5}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_height_at_clearance_returns_ok(self, engine):
        truck = {"height_m": 4.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert msg == "OK"

    def test_height_above_clearance_requires_clearance(self, engine):
        truck = {"height_m": 4.1}
        valid, msg = engine.validate_truck(truck)
        assert valid is True  # clearance route is allowed
        assert "requires route clearance" in msg

    def test_height_exceeds_maximum_clearance_message(self, engine):
        """Height > MIN_CLEARANCE returns clearance message, not failure.
        The code checks MIN_CLEARANCE before MAX_HEIGHT and returns early."""
        truck = {"height_m": 5.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert "requires route clearance" in msg

    # Weight

    def test_weight_within_limit_ok(self, engine):
        truck = {"max_weight_kg": 20000}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_weight_at_limit_ok(self, engine):
        truck = {"max_weight_kg": 40000}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_weight_exceeds_maximum_fails(self, engine):
        truck = {"max_weight_kg": 45000}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "exceeds maximum" in msg
        assert "40000kg" in msg

    def test_weight_falls_back_to_weight_kg_key(self, engine):
        truck = {"weight_kg": 35000}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_weight_both_keys_max_weight_kg_preferred(self, engine):
        truck = {"max_weight_kg": 20000, "weight_kg": 1000}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    # Width

    def test_width_within_limit_ok(self, engine):
        truck = {"width_m": 2.4}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_width_at_limit_ok(self, engine):
        truck = {"width_m": 2.55}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_width_exceeds_maximum_fails(self, engine):
        truck = {"width_m": 3.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "exceeds maximum" in msg
        assert "2.55m" in msg

    # Length — validate_truck does NOT enforce length
    def test_length_any_value_passes_validation(self, engine):
        truck = {"length_m": 30.0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    # Hazmat — validate_truck does NOT validate hazmat
    def test_hazmat_flag_ignored_by_validate(self, engine):
        truck = {"hazmat": True}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    # Axle load — validate_truck does NOT validate axle load
    def test_axle_load_ignored_by_validate(self, engine):
        truck = {"axleload_kg": 20000}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    # Clearance-based route filtering behaviour
    def test_height_above_clearance_below_max_still_clearance_message(self, engine):
        """Between MIN_CLEARANCE and MAX_HEIGHT: clearance message, not failure."""
        truck = {"height_m": 4.3}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert "clearance" in msg

    # Multiple invalid dimensions
    def test_multiple_violations_first_wins(self, engine):
        """Height is checked before weight — so height clearance message is reported first."""
        truck = {"height_m": 5.0, "max_weight_kg": 50000}
        valid, msg = engine.validate_truck(truck)
        # Height > MIN_CLEARANCE returns early with clearance message (not failure)
        assert valid is True
        assert "clearance" in msg

    def test_weight_violation_reported_when_height_valid(self, engine):
        truck = {"height_m": 2.0, "max_weight_kg": 50000}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "weight" in msg

    # None / missing keys
    def test_missing_dimensions_passes(self, engine):
        truck = {"model": "MAN"}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_none_dimensions_passes(self, engine):
        truck = {"height_m": None, "max_weight_kg": None, "width_m": None}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    # Type errors gracefully handled
    def test_invalid_height_type_skips_check(self, engine):
        truck = {"height_m": "really_tall"}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_negative_dimension_passes(self, engine):
        """Negative values pass float conversion and compare as not exceeding max."""
        truck = {"height_m": -1.0, "max_weight_kg": -100}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_zero_height_passes(self, engine):
        truck = {"height_m": 0}
        valid, msg = engine.validate_truck(truck)
        assert valid is True


# ── build_params ──────────────────────────────────────────────────────────

class TestBuildParams:
    def test_empty_truck_returns_empty_dict(self, engine):
        params = engine.build_params({})
        assert params == {}

    def test_none_truck_returns_empty_dict(self, engine):
        params = engine.build_params(None)
        assert params == {}

    # Weight (float values converted to str via float → str, so "20000.0")
    def test_weight_passed_correctly(self, engine):
        params = engine.build_params({"max_weight_kg": 20000})
        assert params["weight"] == "20000.0"

    def test_weight_fallback_to_weight_kg(self, engine):
        params = engine.build_params({"weight_kg": 15000})
        assert params["weight"] == "15000.0"

    def test_weight_prefers_max_weight_kg(self, engine):
        params = engine.build_params({"max_weight_kg": 20000, "weight_kg": 5000})
        assert params["weight"] == "20000.0"

    def test_weight_zero_skipped(self, engine):
        params = engine.build_params({"max_weight_kg": 0})
        assert "weight" not in params

    def test_weight_negative_skipped(self, engine):
        params = engine.build_params({"max_weight_kg": -100})
        assert "weight" not in params

    def test_weight_exceeding_max_skipped(self, engine):
        params = engine.build_params({"max_weight_kg": 50000})
        assert "weight" not in params

    # Height
    def test_height_passed_correctly(self, engine):
        params = engine.build_params({"height_m": 3.5})
        assert params["height"] == "3.5"

    def test_height_zero_skipped(self, engine):
        params = engine.build_params({"height_m": 0})
        assert "height" not in params

    def test_height_negative_skipped(self, engine):
        params = engine.build_params({"height_m": -1})
        assert "height" not in params

    def test_height_exceeding_max_skipped(self, engine):
        params = engine.build_params({"height_m": 10})
        assert "height" not in params

    # Width
    def test_width_passed_correctly(self, engine):
        params = engine.build_params({"width_m": 2.4})
        assert params["width"] == "2.4"

    def test_width_zero_skipped(self, engine):
        params = engine.build_params({"width_m": 0})
        assert "width" not in params

    def test_width_exceeding_max_skipped(self, engine):
        params = engine.build_params({"width_m": 5})
        assert "width" not in params

    # Length
    def test_length_passed_correctly(self, engine):
        params = engine.build_params({"length_m": 13.6})
        assert params["length"] == "13.6"

    def test_length_zero_skipped(self, engine):
        params = engine.build_params({"length_m": 0})
        assert "length" not in params

    def test_length_exceeding_max_skipped(self, engine):
        params = engine.build_params({"length_m": 25})
        assert "length" not in params

    def test_length_omitted_when_not_provided(self, engine):
        params = engine.build_params({"max_weight_kg": 10000})
        assert "length" not in params

    # Axle load (float → str adds ".0")
    def test_axle_load_passed_correctly(self, engine):
        params = engine.build_params({"axleload_kg": 10000})
        assert params["axleload"] == "10000.0"

    def test_axle_load_zero_skipped(self, engine):
        params = engine.build_params({"axleload_kg": 0})
        assert "axleload" not in params

    def test_axle_load_negative_skipped(self, engine):
        params = engine.build_params({"axleload_kg": -1})
        assert "axleload" not in params

    # Hazmat
    def test_hazmat_true_included(self, engine):
        params = engine.build_params({"hazmat": True})
        assert params["hazmat"] == "true"

    def test_hazmat_false_included(self, engine):
        params = engine.build_params({"hazmat": False})
        assert params["hazmat"] == "false"

    def test_hazmat_string_true(self, engine):
        """String hazmat values store the boolean result of the truthy check."""
        params = engine.build_params({"hazmat": "true"})
        assert params["hazmat"] is True

    def test_hazmat_string_yes(self, engine):
        params = engine.build_params({"hazmat": "yes"})
        assert params["hazmat"] is True

    def test_hazmat_string_1(self, engine):
        params = engine.build_params({"hazmat": "1"})
        assert params["hazmat"] is True

    def test_hazmat_string_no(self, engine):
        params = engine.build_params({"hazmat": "no"})
        assert params["hazmat"] is False

    def test_hazmat_none_excluded(self, engine):
        params = engine.build_params({"hazmat": None})
        assert "hazmat" not in params

    def test_hazmat_not_provided_excluded(self, engine):
        params = engine.build_params({"max_weight_kg": 10000})
        assert "hazmat" not in params

    # Combined params
    def test_build_params_all_dimensions(self, engine):
        truck = {
            "max_weight_kg": 25000,
            "height_m": 3.8,
            "width_m": 2.5,
            "length_m": 14.0,
            "axleload_kg": 9000,
            "hazmat": True,
        }
        params = engine.build_params(truck)
        assert params["weight"] == "25000.0"
        assert params["height"] == "3.8"
        assert params["width"] == "2.5"
        assert params["length"] == "14.0"
        assert params["axleload"] == "9000.0"
        assert params["hazmat"] == "true"

    def test_build_params_all_dimensions_as_strings(self, engine):
        """Values may come as strings from the database."""
        truck = {
            "max_weight_kg": "25000",
            "height_m": "3.8",
            "width_m": "2.5",
        }
        params = engine.build_params(truck)
        assert params["weight"] == "25000.0"
        assert params["height"] == "3.8"
        assert params["width"] == "2.5"

    def test_logging_on_params_built(self, engine):
        mock_logger = MagicMock()
        engine.logger = mock_logger
        params = engine.build_params({"max_weight_kg": 10000})
        mock_logger.info.assert_called_once()
        assert "1 truck params" in mock_logger.info.call_args[0][0]

    def test_logging_warning_on_exception(self, engine):
        mock_logger = MagicMock()
        engine.logger = mock_logger
        # Provoke an exception inside the try block
        with patch.object(engine, "_get_truck_value", side_effect=RuntimeError("boom")):
            params = engine.build_params({"max_weight_kg": 10000})
            assert params == {}  # returns empty on exception
            mock_logger.warning.assert_called_once()
            assert "boom" in mock_logger.warning.call_args[0][0]

    def test_profile_logged(self, engine):
        mock_logger = MagicMock()
        engine.logger = mock_logger
        engine.build_params({"max_weight_kg": 10000}, profile="truck_safe")
        assert "truck_safe" in mock_logger.info.call_args[0][0]


# ── _get_truck_value ──────────────────────────────────────────────────────

class TestGetTruckValue:
    def test_dict_with_get_method(self):
        truck = {"plate_number": "AB123CD"}
        result = TruckConstraintEngine._get_truck_value(truck, "plate_number")
        assert result == "AB123CD"

    def test_dict_with_get_returns_none_for_missing(self):
        truck = {"model": "MAN"}
        result = TruckConstraintEngine._get_truck_value(truck, "plate_number")
        assert result is None

    def test_attribute_access_fallback(self):
        class FakeTruck:
            plate_number = "XY999ZZ"
        result = TruckConstraintEngine._get_truck_value(FakeTruck(), "plate_number")
        assert result == "XY999ZZ"

    def test_attribute_access_missing_returns_none(self):
        class FakeTruck:
            pass
        result = TruckConstraintEngine._get_truck_value(FakeTruck(), "plate_number")
        assert result is None

    def test_sqlite_row_style_dict_by_key(self):
        """Simulate sqlite3.Row behaviour: supports __getitem__ by column name."""
        class RowLike:
            def __getitem__(self, key):
                if key == "id":
                    return 42
                raise KeyError(key)
            def get(self, key, default=None):
                try:
                    return self[key]
                except KeyError:
                    return default
        result = TruckConstraintEngine._get_truck_value(RowLike(), "id")
        assert result == 42

    def test_none_truck_returns_none(self):
        result = TruckConstraintEngine._get_truck_value(None, "id")
        assert result is None


# ── validate_profile ──────────────────────────────────────────────────────

class TestValidateProfile:
    def test_valid_profiles(self, engine):
        for profile in ["truck", "truck_fast", "truck_safe", "truck_cheap", "truck_short",
                        "car", "bike", "foot"]:
            assert engine.validate_profile(profile) is True

    def test_valid_profile_case_insensitive(self, engine):
        assert engine.validate_profile("TRUCK") is True
        assert engine.validate_profile("Truck_Fast") is True

    def test_invalid_profile(self, engine):
        assert engine.validate_profile("helicopter") is False

    def test_empty_profile(self, engine):
        assert engine.validate_profile("") is False


# ── Edge cases: extreme values ────────────────────────────────────────────

class TestExtremeValues:
    def test_extremely_large_weight_value_in_validate(self, engine):
        truck = {"max_weight_kg": 1e12}
        valid, msg = engine.validate_truck(truck)
        assert valid is False
        assert "exceeds maximum" in msg

    def test_extremely_tall_height_in_validate(self, engine):
        """Height > MIN_CLEARANCE returns clearance message (not failure)."""
        truck = {"height_m": 1e6}
        valid, msg = engine.validate_truck(truck)
        assert valid is True
        assert "clearance" in msg

    def test_extremely_small_dimensions_pass(self, engine):
        truck = {"height_m": 1e-10, "max_weight_kg": 1e-10, "width_m": 1e-10}
        valid, msg = engine.validate_truck(truck)
        assert valid is True

    def test_very_large_geometry_values_in_params(self, engine):
        """Weight/height/width/length exceeding max are skipped.
        Axleload has no max check (only > 0) so it is included."""
        params = engine.build_params({
            "max_weight_kg": 1e12,
            "height_m": 1e6,
            "width_m": 1e3,
            "length_m": 1e3,
            "axleload_kg": 1e12,
        })
        assert "weight" not in params
        assert "height" not in params
        assert "width" not in params
        assert "length" not in params
        assert "axleload" in params

    def test_none_fields_all_handled_gracefully(self, engine):
        truck = {
            "height_m": None,
            "max_weight_kg": None,
            "width_m": None,
            "length_m": None,
            "axleload_kg": None,
            "hazmat": None,
            "id": None,
        }
        params = engine.build_params(truck)
        assert params == {}


if __name__ == "__main__":
    pytest.main([__file__])
