from __future__ import annotations

import math

import pytest

from services.route_service import GraphHopperClient

pytestmark = pytest.mark.mutation


class TestKillMutationHaversine:
    """Kill mutations in GraphHopperClient._haversine_distance.

    _haversine_distance(lat1, lon1, lat2, lon2) -> float (km)
    """

    # ── 1. Known distance: Paris → London ≈ 343 km ──
    def test_known_distance_paris_to_london(self):
        """Paris (48.8566, 2.3522) to London (51.5074, -0.1278) ≈ 343 km.
        A mutation that changes R=6371 will shift this."""
        dist = GraphHopperClient._haversine_distance(
            48.8566, 2.3522, 51.5074, -0.1278
        )
        assert 300 < dist < 400, (
            f"Paris→London should be ~343 km, got {dist}"
        )

    # ── 2. Same point → 0.0 ──
    def test_same_point_returns_zero(self):
        """Identical coordinates must return exactly 0.0."""
        dist = GraphHopperClient._haversine_distance(
            48.8566, 2.3522, 48.8566, 2.3522
        )
        assert dist == 0.0, f"Same point should be 0, got {dist}"

    # ── 3. Antipodal points ≈ 20000 km ──
    def test_antipodal_points(self):
        """Antipodal points (opposite sides of Earth) should be ~πR ≈ 20015 km.
        A formula mutation (e.g. removing the cos factor) will break this."""
        # Equatorial antipodes: (0, 0) and (0, 180)
        dist = GraphHopperClient._haversine_distance(0.0, 0.0, 0.0, 180.0)
        # π * 6371 ≈ 20015 km
        assert 19000 < dist < 21000, (
            f"Antipodal distance should be ~20015 km, got {dist}"
        )

    # ── 4. Negative coordinates work correctly ──
    def test_negative_coordinates(self):
        """Southern and western hemisphere coordinates must work correctly.
        Sydney (-33.8688, 151.2093) to Tokyo (35.6762, 139.6503) ≈ 7820 km."""
        dist = GraphHopperClient._haversine_distance(
            -33.8688, 151.2093, 35.6762, 139.6503
        )
        assert 7500 < dist < 8100, (
            f"Sydney→Tokyo should be ~7820 km, got {dist}"
        )

    # ── 5. Always returns non-negative float (not NaN) ──
    def test_returns_non_negative_non_nan(self):
        """The function must always return a non-negative finite float.
        A mutation that produces NaN or negative values will be killed."""
        cases = [
            (48.8566, 2.3522, 51.5074, -0.1278),
            (0.0, 0.0, 0.0, 0.0),
            (-90.0, -180.0, 90.0, 180.0),
            (45.0, 0.0, -45.0, 0.0),
            (0.0, -90.0, 0.0, 90.0),
        ]
        for lat1, lon1, lat2, lon2 in cases:
            dist = GraphHopperClient._haversine_distance(lat1, lon1, lat2, lon2)
            assert isinstance(dist, float), f"Distance must be float, got {type(dist)}"
            assert not math.isnan(dist), f"Distance must not be NaN: {dist}"
            assert not math.isinf(dist), f"Distance must not be Inf: {dist}"
            assert dist >= 0.0, f"Distance must be >= 0, got {dist}"
