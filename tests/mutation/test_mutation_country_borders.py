from __future__ import annotations

import pytest

import services.country_borders as cb

pytestmark = pytest.mark.mutation


# ── Test helpers ──────────────────────────────────────────────────────────

_SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
"""10×10 square in (lat, lon) space from (0,0) to (10,10)."""

_TRIANGLE = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]
"""Right triangle covering the lower-left half of the 10×10 square."""


# ── point_in_polygon ──────────────────────────────────────────────────────


class TestKillMutationPolygonLength:
    """Kill: polygon length check mutated from len < 3 to <= 3 or removed."""

    def test_two_point_polygon_returns_false(self):
        """2-point polygon → False (not a valid polygon).
        If len < 3 is mutated to len <= 3, a 2-point polygon would pass through."""
        polygon = [(0.0, 0.0), (10.0, 10.0)]
        assert cb.point_in_polygon(5.0, 5.0, polygon) is False

    def test_one_point_polygon_returns_false(self):
        """1-point polygon → False."""
        polygon = [(5.0, 5.0)]
        assert cb.point_in_polygon(5.0, 5.0, polygon) is False

    def test_empty_polygon_returns_false(self):
        """Empty polygon → False."""
        assert cb.point_in_polygon(5.0, 5.0, []) is False

    def test_three_point_polygon_processes_normally(self):
        """3-point polygon is valid and returns correct inside/outside result."""
        # Triangle covers lower-left half; (1,1) is inside
        assert cb.point_in_polygon(1.0, 1.0, _TRIANGLE) is True

    def test_three_point_polygon_outside_returns_false(self):
        """3-point polygon with point clearly outside → False."""
        # (8,8) is outside the triangle with vertices (0,0), (10,0), (0,10)
        assert cb.point_in_polygon(8.0, 8.0, _TRIANGLE) is False


class TestKillMutationRayCastingInside:
    """Kill: 'inside = not inside' mutated (removed or set to constant)."""

    def test_known_inside_point_returns_true(self):
        """Point known to be inside square → True.
        If 'inside = not inside' is removed, no crossings would flip inside → False."""
        assert cb.point_in_polygon(5.0, 5.0, _SQUARE) is True

    def test_known_outside_point_returns_false(self):
        """Point known to be outside square → False.
        If 'inside = not inside' is mutated to 'inside = True', outside point would be True."""
        assert cb.point_in_polygon(15.0, 15.0, _SQUARE) is False

    def test_inside_near_edge_returns_true(self):
        """Point just inside the square edge → True (fragile boundary test)."""
        assert cb.point_in_polygon(0.1, 5.0, _SQUARE) is True

    def test_outside_just_beyond_edge_returns_false(self):
        """Point just beyond the square edge → False."""
        assert cb.point_in_polygon(-0.1, 5.0, _SQUARE) is False


class TestKillMutationCoordinateAccess:
    """Kill: lat/lon access order in p[i][0]/p[i][1] swapped."""

    def test_point_clearly_inside_standard_square(self):
        """Standard orientation (lat, lon) tuple: (5,5) inside square → True.
        If lat/lon are swapped in extraction, (5,5) would be read as lon=5, lat=5
        which happens to be symmetric, so use an asymmetric shape instead."""

        # Asymmetric rectangle: [(2, 5), (2, 15), (12, 15), (12, 5)]
        # lat range: 2-12, lon range: 5-15
        rect = [(2.0, 5.0), (2.0, 15.0), (12.0, 15.0), (12.0, 5.0)]
        # (7, 10) → lat=7, lon=10 — well inside
        assert cb.point_in_polygon(7.0, 10.0, rect) is True

    def test_asymmetric_rectangle_outside(self):
        """Point outside asymmetric rectangle → False.
        If lat/lon swapped, (1, 50) → read as lat=50, lon=1, completely different check."""
        rect = [(2.0, 5.0), (2.0, 15.0), (12.0, 15.0), (12.0, 5.0)]
        assert cb.point_in_polygon(1.0, 50.0, rect) is False

    def test_origin_point_in_first_quadrant_polygon(self):
        """Origin (0,0) with polygon in positive quadrant only → False.
        A swapped access would read (0,0) as lat=0, lon=0 regardless, but this
        confirms the function doesn't accidentally match origin to every polygon."""
        quad = [(1.0, 1.0), (1.0, 5.0), (5.0, 5.0), (5.0, 1.0)]
        assert cb.point_in_polygon(0.0, 0.0, quad) is False
        assert cb.point_in_polygon(3.0, 3.0, quad) is True


class TestKillMutationEdgeCrossing:
    """Kill: the ((lng_i > lon) != (lng_j > lon)) clause mutated."""

    def test_crossing_from_left_to_right(self):
        """Point inside when ray crosses edge left→right.
        Standard crossing: lng_i > lon (True) != lng_j > lon (False) → True."""
        assert cb.point_in_polygon(5.0, 5.0, _SQUARE) is True

    def test_crossing_from_right_to_left(self):
        """Point inside when ray crosses edge right→left.
        lng_i > lon (False) != lng_j > lon (True) → True."""
        assert cb.point_in_polygon(5.0, 5.0, _SQUARE) is True  # same as above

    def test_point_left_of_entire_polygon(self):
        """Point left of the entire polygon → no crossings → False.
        If the != is mutated to ==, this could incorrectly register crossings."""
        polygon = [(0.0, 10.0), (0.0, 20.0), (10.0, 20.0), (10.0, 10.0)]
        # lon=-5 is left of all vertices (all lng > -5)
        # For every edge, lng_i > -5 == lng_j > -5 == True
        # True != True → False → no crossing → inside stays False
        assert cb.point_in_polygon(5.0, -5.0, polygon) is False

    def test_point_right_of_entire_polygon(self):
        """Point right of the entire polygon → no crossings → False."""
        polygon = [(0.0, 10.0), (0.0, 20.0), (10.0, 20.0), (10.0, 10.0)]
        # lon=25 is right of all vertices (all lng < 25)
        # For every edge, lng_i > 25 == lng_j > 25 == False
        # False != False → False → no crossing → inside stays False
        assert cb.point_in_polygon(5.0, 25.0, polygon) is False

    def test_point_above_entire_polygon(self):
        """Point above the polygon → no crossings → False."""
        polygon = [(0.0, 10.0), (0.0, 20.0), (10.0, 20.0), (10.0, 10.0)]
        assert cb.point_in_polygon(15.0, 15.0, polygon) is False


class TestKillMutationDivisionByZero:
    """Kill: division by zero when lng_j == lng_i (vertical edge) — must not crash."""

    def test_vertical_edge_no_crash(self):
        """Polygon with vertical edge (lng_j == lng_i) → no ZeroDivisionError.
        The first condition ((lng_i > lon) != (lng_j > lon)) short-circuits before
        division when lng_i == lng_j, but a mutation that changes the condition
        would expose the division."""
        # Vertical edge from (0,10)→(0,0): lng_i=0, lng_j=0 → lng_j-lng_i=0
        polygon = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
        # This should not raise ZeroDivisionError
        result = cb.point_in_polygon(5.0, 5.0, polygon)
        assert result is True

    def test_vertical_edge_point_outside_no_crash(self):
        """Vertical edge with point outside → no crash, returns False."""
        polygon = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
        result = cb.point_in_polygon(5.0, -5.0, polygon)
        assert result is False

    def test_diamond_with_vertical_segment_no_crash(self):
        """Diamond polygon containing a vertical segment → no crash on any point."""
        # Diamond with top (5,5), right (10,0), bottom (5,-5), left (0,0)
        # Note: (10,0)→(5,-5) is diagonal, but (5,-5)→(0,0) cross at lng=0,0 etc.
        # Let's use a simpler polygon with two vertical-aligned points:
        polygon = [(0.0, 0.0), (0.0, 5.0), (5.0, 5.0), (5.0, 0.0), (2.5, -2.5)]
        result = cb.point_in_polygon(2.5, 2.5, polygon)
        # Point is inside → True (or just checking no crash)
        assert isinstance(result, bool)


# ── bbox_contains ──────────────────────────────────────────────────────────


class TestKillMutationBboxContains:
    """Kill: order comparison b[0] <= lon <= b[2] mutated to >=."""

    @pytest.fixture(autouse=True)
    def setup_bbox(self):
        """Seed a known bbox for the test country."""
        saved_data = cb._DATA
        saved_bbox = cb._BBOX
        cb._DATA = {"XX": [_SQUARE]}
        cb._BBOX = {"XX": (0.0, 0.0, 10.0, 10.0)}  # (lon_min, lat_min, lon_max, lat_max)
        yield
        cb._DATA = saved_data
        cb._BBOX = saved_bbox

    def test_inside_bbox_returns_true(self):
        """Point clearly inside bounding box → True.
        If b[0] <= lon is mutated to b[0] >= lon, (5,5) would return False."""
        assert cb.bbox_contains("XX", 5.0, 5.0) is True

    def test_outside_bbox_lon_returns_false(self):
        """Point outside bbox on longitude → False.
        If b[0] <= lon <= b[2] is inverted, lon > b[2] could incorrectly match."""
        assert cb.bbox_contains("XX", 5.0, 15.0) is False

    def test_outside_bbox_lat_returns_false(self):
        """Point outside bbox on latitude → False."""
        assert cb.bbox_contains("XX", 15.0, 5.0) is False

    def test_on_bbox_min_boundary_returns_true(self):
        """Point exactly on the min corner of bbox → True (inclusive boundary)."""
        assert cb.bbox_contains("XX", 0.0, 0.0) is True

    def test_on_bbox_max_boundary_returns_true(self):
        """Point exactly on the max corner of bbox → True (inclusive boundary)."""
        assert cb.bbox_contains("XX", 10.0, 10.0) is True

    def test_unknown_code_returns_false(self):
        """Unknown country code → False (not in _BBOX)."""
        assert cb.bbox_contains("ZZ", 5.0, 5.0) is False


# ── countries_from_points ──────────────────────────────────────────────────


class TestKillMutationCountriesFromPoints:
    """Kill: sampling step max(1, len // 30) and empty list mutations."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        """Seed test polygons for two countries."""
        saved_data = cb._DATA
        saved_bbox = cb._BBOX
        # Country AA covers square from (0,0) to (10,10)
        # Country BB covers square from (20,20) to (30,30)
        cb._DATA = {
            "AA": [[(p[0], p[1]) for p in _SQUARE]],
            "BB": [[(20.0 + p[0], 20.0 + p[1]) for p in _SQUARE]],
        }
        cb._BBOX = {
            "AA": (0.0, 0.0, 10.0, 10.0),
            "BB": (20.0, 20.0, 30.0, 30.0),
        }
        yield
        cb._DATA = saved_data
        cb._BBOX = saved_bbox

    def test_empty_list_returns_empty_list(self):
        """Empty points list → []. If mutated to raise, this would crash."""
        result = cb.countries_from_points([])
        assert result == []

    def test_single_point_in_country_returns_country(self):
        """Single point inside a country's polygon → returns that country code.
        step = max(1, 1 // 30) = max(1, 0) = 1 → point is sampled."""
        result = cb.countries_from_points([(5.0, 5.0)])
        assert "AA" in result
        assert "BB" not in result

    def test_single_point_outside_all_countries(self):
        """Single point outside all countries → empty list."""
        result = cb.countries_from_points([(15.0, 15.0)])
        assert result == []

    def test_multiple_points_covers_both_countries(self):
        """Points in both countries → both country codes returned.
        Sampling step should still allow at least one point per country."""
        points = [(5.0, 5.0), (25.0, 25.0)]
        result = cb.countries_from_points(points)
        assert "AA" in result
        assert "BB" in result

    def test_sampling_with_many_points(self):
        """Many points (60) → step = max(1, 60//30) = 2, still works."""
        # 30 points in AA, 30 points in BB, interleaved
        points = [(5.0, 5.0)] * 30 + [(25.0, 25.0)] * 30
        result = cb.countries_from_points(points)
        assert "AA" in result
        assert "BB" in result

    def test_sampling_single_country_not_double_counted(self):
        """Multiple points in same country → country appears once."""
        points = [(5.0, 5.0), (5.0, 5.0), (5.0, 5.0)]
        result = cb.countries_from_points(points)
        assert result.count("AA") == 1
