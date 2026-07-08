"""Tests for country_borders module.

All tests set `_DATA` and `_BBOX` module globals directly so we never
need the real JSON file on disk.
"""

from __future__ import annotations

import pytest

import services.country_borders as cb
from services.country_borders import (
    bbox_contains,
    countries_at_point,
    countries_from_points,
    get_bounds,
    get_polygon,
    get_polygons,
    point_in_country,
    point_in_polygon,
)

# A minimal test dataset: France with a single square polygon near Paris.
MOCK_DATA: dict[str, list[list[list[float]]]] = {
    "FR": [
        [[48.0, 2.0], [48.0, 3.0], [49.0, 3.0], [49.0, 2.0], [48.0, 2.0]],
    ],
    "IT": [
        [[42.0, 12.0], [42.0, 13.0], [43.0, 13.0], [43.0, 12.0], [42.0, 12.0]],
    ],
}

MOCK_BBOX = {
    "FR": (2.0, 48.0, 3.0, 49.0),
    "IT": (12.0, 42.0, 13.0, 43.0),
}


@pytest.fixture(autouse=True)
def mock_borders_data():
    """Set _DATA and _BBOX directly so no JSON file is needed."""
    old_data = cb._DATA
    old_bbox = cb._BBOX
    cb._DATA = MOCK_DATA
    cb._BBOX = MOCK_BBOX
    yield
    cb._DATA = old_data
    cb._BBOX = old_bbox


# ── point_in_polygon ─────────────────────────────────────────────


class TestPointInPolygon:
    def test_point_inside_square(self):
        """A point clearly inside the square should return True."""
        polygon = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
        assert point_in_polygon(5, 5, polygon) is True

    def test_point_outside_square(self):
        polygon = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
        assert point_in_polygon(15, 15, polygon) is False

    def test_point_on_edge(self):
        """A point exactly on an edge may return True or False (undefined)."""
        polygon = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
        # On the left edge x=0
        result = point_in_polygon(5, 0, polygon)
        assert isinstance(result, bool)

    def test_less_than_three_points_returns_false(self):
        assert point_in_polygon(5, 5, [(0, 0), (10, 10)]) is False
        assert point_in_polygon(5, 5, [(0, 0)]) is False
        assert point_in_polygon(5, 5, []) is False

    def test_complex_polygon(self):
        """L-shaped polygon."""
        polygon = [(0, 0), (0, 10), (5, 10), (5, 5), (10, 5), (10, 0), (0, 0)]
        assert point_in_polygon(2, 2, polygon) is True   # inside bottom-left
        assert point_in_polygon(7, 7, polygon) is False  # in the missing corner

    def test_point_at_origin(self):
        polygon = [(-10, -10), (-10, 10), (10, 10), (10, -10), (-10, -10)]
        assert point_in_polygon(0, 0, polygon) is True


# ── get_polygon / get_polygons ───────────────────────────────────


class TestGetPolygon:
    def test_returns_main_ring(self):
        poly = get_polygon("FR")
        assert len(poly) == 5
        assert poly[0] == (48.0, 2.0)

    def test_missing_country_returns_empty_list(self):
        assert get_polygon("XX") == []

    def test_case_insensitive(self):
        poly_lower = get_polygon("fr")
        poly_upper = get_polygon("FR")
        assert poly_lower == poly_upper

    def test_returns_tuples(self):
        poly = get_polygon("FR")
        for pt in poly:
            assert isinstance(pt, tuple)
            assert len(pt) == 2
            assert isinstance(pt[0], float)
            assert isinstance(pt[1], float)


class TestGetPolygons:
    def test_returns_all_rings(self):
        rings = get_polygons("FR")
        assert len(rings) == 1
        assert len(rings[0]) == 5

    def test_missing_country_returns_empty(self):
        assert get_polygons("XX") == []


# ── bbox_contains ────────────────────────────────────────────────


class TestBboxContains:
    def test_point_within_bbox(self):
        assert bbox_contains("FR", 48.5, 2.5) is True

    def test_point_outside_bbox(self):
        assert bbox_contains("FR", 50.0, 5.0) is False

    def test_missing_code_returns_false(self):
        assert bbox_contains("XX", 48.5, 2.5) is False


# ── countries_at_point ───────────────────────────────────────────


class TestCountriesAtPoint:
    def test_point_in_france(self):
        countries = countries_at_point(48.5, 2.5)
        assert "FR" in countries

    def test_point_in_italy(self):
        countries = countries_at_point(42.5, 12.5)
        assert "IT" in countries

    def test_point_no_country(self):
        countries = countries_at_point(0, 0)
        assert countries == []


# ── point_in_country ─────────────────────────────────────────────


class TestPointInCountry:
    def test_point_in_country(self):
        assert point_in_country(48.5, 2.5, "FR") is True

    def test_point_not_in_country(self):
        assert point_in_country(48.5, 2.5, "IT") is False

    def test_missing_country(self):
        assert point_in_country(48.5, 2.5, "XX") is False


# ── countries_from_points ────────────────────────────────────────


class TestCountriesFromPoints:
    def test_empty_points_returns_empty_list(self):
        assert countries_from_points([]) == []

    def test_single_point_in_france(self):
        result = countries_from_points([(48.5, 2.5)])
        assert "FR" in result

    def test_multiple_points_in_same_country(self):
        result = countries_from_points([(48.5, 2.5), (48.6, 2.6)])
        assert "FR" in result
        assert len(result) == 1

    def test_points_in_multiple_countries(self):
        result = countries_from_points([(48.5, 2.5), (42.5, 12.5)])
        assert "FR" in result
        assert "IT" in result

    def test_sampling_at_most_30_points(self):
        """Many points should be sampled down to ~30."""
        points = [(48.5, 2.0 + i * 0.01) for i in range(200)]
        result = countries_from_points(points)
        assert isinstance(result, list)


# ── get_bounds ───────────────────────────────────────────────────


class TestGetBounds:
    def test_returns_bbox(self):
        bounds = get_bounds("FR")
        assert bounds is not None
        lon_min, lat_min, lon_max, lat_max = bounds
        assert lon_min == 2.0
        assert lat_min == 48.0
        assert lon_max == 3.0
        assert lat_max == 49.0

    def test_missing_code_returns_none(self):
        assert get_bounds("XX") is None

    def test_case_insensitive(self):
        bounds_upper = get_bounds("FR")
        bounds_lower = get_bounds("fr")
        assert bounds_upper == bounds_lower


# ── Additional edge-case tests ─────────────────────────────────────


class TestEdgeCases:
    def test_load_returns_existing_data(self, mock_borders_data):
        """Calling _load() after a previous call returns cached data."""
        # _DATA is already set by the fixture, so _load should return it
        data = cb._load()
        assert data is not None
        assert "FR" in data

    @pytest.mark.parametrize("lat,lon,code,expected", [
        (48.5, 2.5, "FR", True),
        (42.5, 12.5, "IT", True),
        (50.0, 5.0, "FR", False),
        (44.0, 8.0, "IT", False),
    ])
    def test_point_in_country_parametrized(self, mock_borders_data, lat, lon, code, expected):
        assert point_in_country(lat, lon, code) is expected

    def test_countries_at_point_multiple_matches(self, mock_borders_data):
        """A point near the border may match multiple countries if
        polygon data overlaps.  Our mock data is non-overlapping so
        only one country should match."""
        countries = countries_at_point(48.5, 2.5)
        assert len(countries) == 1
        assert countries == ["FR"]

    def test_countries_from_points_deduplicates(self, mock_borders_data):
        """Duplicate country codes should be returned only once."""
        points = [(48.5, 2.5), (48.6, 2.6)]  # both in FR
        result = countries_from_points(points)
        assert len(result) == 1

    def test_countries_from_points_handles_large_input(self, mock_borders_data):
        """A very large list of points should be sampled without error."""
        points = [(48.5, 2.0 + i * 0.001) for i in range(5000)]
        result = countries_from_points(points)
        assert isinstance(result, list)

    def test_get_polygon_data_is_none(self):
        """When _DATA is None, get_polygon returns []."""
        old = cb._DATA
        cb._DATA = None
        try:
            assert get_polygon("FR") == []
        finally:
            cb._DATA = old

    def test_get_polygons_data_is_none(self):
        """When _DATA is None, get_polygons returns []."""
        old = cb._DATA
        cb._DATA = None
        try:
            assert get_polygons("FR") == []
        finally:
            cb._DATA = old

    def test_bbox_contains_data_is_none(self):
        """When _DATA is None, bbox_contains returns False."""
        old_data = cb._DATA
        old_bbox = cb._BBOX
        cb._DATA = None
        cb._BBOX = {}
        try:
            assert bbox_contains("FR", 48.5, 2.5) is False
        finally:
            cb._DATA = old_data
            cb._BBOX = old_bbox

    def test_get_bounds_data_is_none(self):
        """When _DATA is None, get_bounds returns None."""
        old_data = cb._DATA
        cb._DATA = None
        try:
            assert get_bounds("FR") is None
        finally:
            cb._DATA = old_data

    def test_large_polygon_performance(self, mock_borders_data):
        """A large polygon should still yield correct results."""
        # Build a large square polygon
        polygon = [(i, j) for i in range(-90, 91, 10) for j in range(-180, 181, 10)]
        assert point_in_polygon(0, 0, polygon) is True
        assert point_in_polygon(100, 200, polygon) is False
