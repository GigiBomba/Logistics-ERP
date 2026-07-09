from __future__ import annotations

import math

import pytest

from services.route_service import GraphHopperClient

pytestmark = pytest.mark.mutation


class TestKillMutationValidateCoordinates:
    """Kill mutations in GraphHopperClient._validate_coordinates.

    The method returns True for valid lat/lon and False otherwise.
    """

    # ── 1. Boundary values are valid (parametrized) ──
    @pytest.mark.parametrize("lat, lon", [
        (-90.0, -180.0),
        (90.0, 180.0),
        (-90.0, 0.0),
        (90.0, 0.0),
        (0.0, -180.0),
        (0.0, 180.0),
        (0.0, 0.0),
        (51.5074, -0.1278),
        (-33.8688, 151.2093),
    ])
    def test_boundary_values_are_valid(self, lat, lon):
        """Boundary values (-90, -180) through (90, 180) must be valid.
        A mutation that changes <= or >= to < or > will break this."""
        assert GraphHopperClient._validate_coordinates(lat, lon) is True

    # ── 2. Just beyond latitude boundary → invalid ──
    @pytest.mark.parametrize("lat, lon", [
        (-90.1, 0.0),
        (90.1, 0.0),
        (-91.0, 0.0),
        (91.0, 0.0),
    ])
    def test_latitude_beyond_boundary_invalid(self, lat, lon):
        """Latitude just beyond -90 or 90 must be invalid."""
        assert GraphHopperClient._validate_coordinates(lat, lon) is False

    # ── 3. Just beyond longitude boundary → invalid ──
    @pytest.mark.parametrize("lat, lon", [
        (0.0, -180.1),
        (0.0, 180.1),
        (0.0, -181.0),
        (0.0, 181.0),
    ])
    def test_longitude_beyond_boundary_invalid(self, lat, lon):
        """Longitude just beyond -180 or 180 must be invalid."""
        assert GraphHopperClient._validate_coordinates(lat, lon) is False

    # ── 4. NaN coordinates → invalid ──
    @pytest.mark.parametrize("lat, lon", [
        (math.nan, 0.0),
        (0.0, math.nan),
        (math.nan, math.nan),
    ])
    def test_nan_coordinates_invalid(self, lat, lon):
        """NaN values for lat or lon must be caught and return False.
        A mutation that removes the try/except guard will fail here because
        NaN comparisons always return False."""
        assert GraphHopperClient._validate_coordinates(lat, lon) is False

    # ── 5. Inf coordinates → invalid ──
    @pytest.mark.parametrize("lat, lon", [
        (math.inf, 0.0),
        (-math.inf, 0.0),
        (0.0, math.inf),
        (0.0, -math.inf),
        (math.inf, math.inf),
    ])
    def test_inf_coordinates_invalid(self, lat, lon):
        """Infinity values for lat or lon must return False."""
        assert GraphHopperClient._validate_coordinates(lat, lon) is False
