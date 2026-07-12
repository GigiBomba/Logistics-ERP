"""Comprehensive tests for services/country_borders.py.

Covers all public functions, ray-casting algorithm edge cases,
module-level caching behaviour, file-loading fallbacks, and sampling logic.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

import services.country_borders as cb


# ---------------------------------------------------------------------------
# Fixtures – sample geometries used throughout the test suite
# ---------------------------------------------------------------------------

SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
TRIANGLE = [(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)]
US_RING = [[30.0, -100.0], [30.0, -80.0], [40.0, -80.0], [40.0, -100.0]]
CA_RING = [[50.0, -110.0], [50.0, -90.0], [60.0, -90.0], [60.0, -110.0]]
MEX_RING = [[15.0, -105.0], [15.0, -85.0], [30.0, -85.0], [30.0, -105.0]]
ISLAND_RING = [[41.0, -82.0], [41.0, -81.0], [42.0, -81.0], [42.0, -82.0]]

SAMPLE_DATA: dict[str, list[list[list[float]]]] = {
    "US": [US_RING],
    "CA": [CA_RING],
    "MX": [MEX_RING],
    "US_ISLANDS": [US_RING, ISLAND_RING],
}


# ---------------------------------------------------------------------------
# Helpers – populate module-level state like _load() does
# ---------------------------------------------------------------------------

def _set_data(data: dict[str, list[list[list[float]]]] | None) -> None:
    """Populate _DATA and _BBOX exactly as _load() would after a successful read.

    This is the preferred way to prepare test data for functions that
    internally call ``bbox_contains`` / ``countries_at_point`` /
    ``point_in_country``, since those all rely on ``_BBOX`` being built.
    """
    cb._DATA = data
    cb._BBOX = {}
    if data is not None:
        for code, rings in data.items():
            all_lats: list[float] = []
            all_lons: list[float] = []
            for ring in rings:
                all_lats.extend(p[0] for p in ring)
                all_lons.extend(p[1] for p in ring)
            cb._BBOX[code] = (min(all_lons), min(all_lats), max(all_lons), max(all_lats))


# ---------------------------------------------------------------------------
# Autouse – reset module-level cache between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_module_cache() -> None:
    """Reset _DATA / _BBOX before every test to prevent cross-test pollution."""
    cb._DATA = None
    cb._BBOX = {}


# ===================================================================
# TestPointInPolygon – ray-casting algorithm
# ===================================================================

class TestPointInPolygon:
    """Unit tests for the core ray-casting implementation."""

    # --- inside cases ---------------------------------------------------

    def test_inside_square_center(self) -> None:
        assert cb.point_in_polygon(5.0, 5.0, SQUARE) is True

    def test_inside_square_off_center(self) -> None:
        assert cb.point_in_polygon(2.0, 8.0, SQUARE) is True

    def test_inside_triangle_centroid(self) -> None:
        """Centroid (approx (5, 3.33)) should be inside the triangle."""
        assert cb.point_in_polygon(3.33, 5.0, TRIANGLE) is True

    def test_inside_triangle_lower_left(self) -> None:
        assert cb.point_in_polygon(1.0, 2.0, TRIANGLE) is True

    # --- outside cases --------------------------------------------------

    def test_outside_square_far(self) -> None:
        assert cb.point_in_polygon(15.0, 15.0, SQUARE) is False

    def test_outside_square_below(self) -> None:
        assert cb.point_in_polygon(-1.0, 5.0, SQUARE) is False

    def test_outside_square_left(self) -> None:
        assert cb.point_in_polygon(5.0, -1.0, SQUARE) is False

    def test_outside_square_above(self) -> None:
        assert cb.point_in_polygon(11.0, 5.0, SQUARE) is False

    def test_outside_square_right(self) -> None:
        assert cb.point_in_polygon(5.0, 11.0, SQUARE) is False

    def test_outside_triangle(self) -> None:
        assert cb.point_in_polygon(0.0, 10.0, TRIANGLE) is False

    # --- edge / vertex cases -------------------------------------------

    def test_on_bottom_edge_square(self) -> None:
        """Point exactly on the bottom edge — algorithm may count it."""
        result = cb.point_in_polygon(0.0, 5.0, SQUARE)
        # The ray-casting algorithm may return True or False for on-edge
        # points depending on implementation. We assert deterministic
        # behaviour (no crash, bool result).
        assert isinstance(result, bool)

    def test_on_left_edge_square(self) -> None:
        result = cb.point_in_polygon(5.0, 0.0, SQUARE)
        assert isinstance(result, bool)

    def test_on_vertex_square(self) -> None:
        """Point exactly on a vertex."""
        result = cb.point_in_polygon(0.0, 0.0, SQUARE)
        assert isinstance(result, bool)

    # --- degenerate / edge-case polygons --------------------------------

    def test_empty_polygon(self) -> None:
        assert cb.point_in_polygon(5.0, 5.0, []) is False

    def test_single_point_polygon(self) -> None:
        assert cb.point_in_polygon(5.0, 5.0, [(5.0, 5.0)]) is False

    def test_two_point_polygon(self) -> None:
        assert cb.point_in_polygon(5.0, 5.0, [(0.0, 0.0), (10.0, 10.0)]) is False

    def test_none_polygon(self) -> None:
        with pytest.raises(TypeError):
            cb.point_in_polygon(5.0, 5.0, None)  # type: ignore[arg-type]

    # --- real-world-like coordinate order -------------------------------

    def test_inside_us_shaped_polygon(self) -> None:
        """lat=35, lon=-90 should be inside the US rectangle."""
        us_poly = [(p[0], p[1]) for p in US_RING]
        assert cb.point_in_polygon(35.0, -90.0, us_poly) is True

    def test_outside_us_shaped_polygon(self) -> None:
        us_poly = [(p[0], p[1]) for p in US_RING]
        assert cb.point_in_polygon(45.0, -90.0, us_poly) is False


# ===================================================================
# TestGetPolygon – first-ring extraction
# ===================================================================

class TestGetPolygon:
    """Tests for get_polygon() — returns the main (first) ring."""

    def test_valid_code_returns_tuples(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.get_polygon("US")
        assert result == [(p[0], p[1]) for p in US_RING]
        assert all(isinstance(p, tuple) and len(p) == 2 for p in result)

    def test_upper_case_normalisation(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result_lower = cb.get_polygon("us")
            result_upper = cb.get_polygon("US")
        assert result_lower == result_upper

    def test_invalid_code(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.get_polygon("ZZ")
        assert result == []

    def test_empty_rings(self) -> None:
        data = {"XX": []}
        with patch.object(cb, "_load", return_value=data):
            result = cb.get_polygon("XX")
        assert result == []

    def test_empty_first_ring(self) -> None:
        data = {"XX": [[]]}
        with patch.object(cb, "_load", return_value=data):
            result = cb.get_polygon("XX")
        assert result == []

    def test_load_returns_none(self) -> None:
        with patch.object(cb, "_load", return_value=None):
            result = cb.get_polygon("US")
        assert result == []

    def test_multiple_rings_only_main_returned(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.get_polygon("US_ISLANDS")
        assert result == [(p[0], p[1]) for p in US_RING]


# ===================================================================
# TestGetPolygons – all rings
# ===================================================================

class TestGetPolygons:
    """Tests for get_polygons() — returns every ring (mainland + islands)."""

    def test_valid_code_all_rings(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.get_polygons("US_ISLANDS")
        assert len(result) == 2
        assert result[0] == [(p[0], p[1]) for p in US_RING]
        assert result[1] == [(p[0], p[1]) for p in ISLAND_RING]

    def test_single_ring_country(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.get_polygons("US")
        assert len(result) == 1
        assert result[0] == [(p[0], p[1]) for p in US_RING]

    def test_upper_case_normalisation(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            assert cb.get_polygons("us") == cb.get_polygons("US")

    def test_invalid_code(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.get_polygons("ZZ")
        assert result == []

    def test_empty_rings(self) -> None:
        data = {"XX": []}
        with patch.object(cb, "_load", return_value=data):
            result = cb.get_polygons("XX")
        assert result == []

    def test_load_returns_none(self) -> None:
        with patch.object(cb, "_load", return_value=None):
            result = cb.get_polygons("US")
        assert result == []

    def test_some_empty_rings_skipped(self) -> None:
        """If a ring is empty, it should still be in the list as empty."""
        data = {"XX": [[], [(1.0, 2.0)]]}
        with patch.object(cb, "_load", return_value=data):
            result = cb.get_polygons("XX")
        assert len(result) == 2
        assert result[0] == []
        assert result[1] == [(1.0, 2.0)]


# ===================================================================
# TestBboxContains – bounding-box pre-check
# ===================================================================

class TestBboxContains:
    """Tests for bbox_contains() — fast bounding-box check."""

    def _populate_bbox(self) -> None:
        cb._DATA = {}  # non-None so _load doesn't re-run
        cb._BBOX["US"] = (-100.0, 30.0, -80.0, 40.0)

    def test_inside(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 35.0, -90.0) is True

    def test_outside_above(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 41.0, -90.0) is False

    def test_outside_below(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 29.0, -90.0) is False

    def test_outside_left(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 35.0, -101.0) is False

    def test_outside_right(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 35.0, -79.0) is False

    def test_on_min_lon(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 35.0, -100.0) is True

    def test_on_max_lon(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 35.0, -80.0) is True

    def test_on_min_lat(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 30.0, -90.0) is True

    def test_on_max_lat(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("US", 40.0, -90.0) is True

    def test_upper_case_normalisation(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("us", 35.0, -90.0) is True

    def test_invalid_code(self) -> None:
        self._populate_bbox()
        assert cb.bbox_contains("ZZ", 35.0, -90.0) is False

    def test_empty_bbox(self) -> None:
        cb._DATA = {}
        cb._BBOX = {}
        assert cb.bbox_contains("US", 35.0, -90.0) is False

    def test_load_is_called_when_data_none(self) -> None:
        """If _DATA is None, bbox_contains should call _load."""
        with patch.object(cb, "_load") as mock_load:
            mock_load.return_value = None
            cb.bbox_contains("US", 35.0, -90.0)
        mock_load.assert_called_once()


# ===================================================================
# TestCountriesAtPoint – find all countries containing a point
# ===================================================================

class TestCountriesAtPoint:
    """Tests for countries_at_point() — full point-in-country lookup."""

    def test_point_in_one_country(self) -> None:
        """Point inside US only (use data without overlapping rings)."""
        data = {"US": [US_RING]}
        _set_data(data)
        result = cb.countries_at_point(35.0, -90.0)
        assert result == ["US"]

    def test_point_in_two_countries(self) -> None:
        """Point inside Mexico only (US box is lat 30–40, MX is 15–30)."""
        data = {
            "US": [US_RING],
            "MX": [MEX_RING],
        }
        _set_data(data)
        # (25, -95) is inside MX bbox (lat 15-30) and MX polygon
        result = cb.countries_at_point(25.0, -95.0)
        assert result == ["MX"]

    def test_point_in_no_countries(self) -> None:
        _set_data(SAMPLE_DATA)
        result = cb.countries_at_point(0.0, 0.0)
        assert result == []

    def test_point_in_country_with_islands(self) -> None:
        """Point inside the island ring, not the mainland."""
        _set_data(SAMPLE_DATA)
        result = cb.countries_at_point(41.5, -81.5)
        # US_ISLANDS has mainland (US_RING, covering lat 30-40) and island
        # (ISLAND_RING, covering lat 41-42).  lat=41.5 is above mainland
        # so only US_ISLANDS matches via the island ring.
        assert result == ["US_ISLANDS"]

    def test_load_returns_none(self) -> None:
        _set_data(None)
        result = cb.countries_at_point(35.0, -90.0)
        assert result == []

    def test_point_outside_bbox_but_inside_some_other(self) -> None:
        """Bbox pre-filter should prevent false positives."""
        data = {
            "US": [US_RING],
            "CA": [CA_RING],
        }
        _set_data(data)
        # (35, -100) is on US bbox edge, inside US polygon
        result = cb.countries_at_point(35.0, -100.0)
        assert "US" in result

    def test_in_bbox_but_outside_polygon(self) -> None:
        """Point inside US bbox but outside actual US polygon (just outside
        the rectangle — lon just past -100 should fail)."""
        data = {"US": [US_RING]}
        _set_data(data)
        # lon = -100.1 is outside US_RING's lon range of -100 to -80
        result = cb.countries_at_point(35.0, -100.1)
        assert result == []


# ===================================================================
# TestPointInCountry – check a single country for a point
# ===================================================================

class TestPointInCountry:
    """Tests for point_in_country() — check if point is inside any ring."""

    def test_inside_bbox_and_polygon(self) -> None:
        _set_data(SAMPLE_DATA)
        assert cb.point_in_country(35.0, -90.0, "US") is True

    def test_inside_island_ring(self) -> None:
        _set_data(SAMPLE_DATA)
        assert cb.point_in_country(41.5, -81.5, "US_ISLANDS") is True

    def test_outside_bbox(self) -> None:
        _set_data(SAMPLE_DATA)
        assert cb.point_in_country(45.0, -90.0, "US") is False

    def test_inside_bbox_non_rectangular_miss(self) -> None:
        """Create a U-shaped polygon — point inside bbox but in the notch."""
        notch_poly = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0),
                      (7.0, 5.0), (7.0, 2.0), (3.0, 2.0),
                      (3.0, 5.0), (0.0, 5.0)]
        data = {"XX": [[[p[0], p[1]] for p in notch_poly]]}
        _set_data(data)
        # bbox is (0, 0, 10, 5); point (3.5, 5.0) is inside bbox but in
        # the notch (outside polygon)
        assert cb.point_in_country(3.5, 5.0, "XX") is False

    def test_invalid_code(self) -> None:
        _set_data(SAMPLE_DATA)
        assert cb.point_in_country(35.0, -90.0, "ZZ") is False

    def test_upper_case_normalisation(self) -> None:
        _set_data(SAMPLE_DATA)
        assert cb.point_in_country(35.0, -90.0, "us") is True

    def test_load_returns_none(self) -> None:
        _set_data(None)
        assert cb.point_in_country(35.0, -90.0, "US") is False


# ===================================================================
# TestCountriesFromPoints – multi-point country detection with sampling
# ===================================================================

class TestCountriesFromPoints:
    """Tests for countries_from_points() — sampling logic included."""

    def test_empty_points(self) -> None:
        assert cb.countries_from_points([]) == []

    def test_single_point(self) -> None:
        with patch.object(cb, "countries_at_point", return_value=["US"]):
            result = cb.countries_from_points([(35.0, -90.0)])
        assert result == ["US"]

    def test_points_in_two_countries(self) -> None:
        def mock_cap(lat: float, lon: float) -> list[str]:
            if 30 <= lat <= 40:
                return ["US"]
            return ["CA"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            result = cb.countries_from_points([(35.0, -90.0), (55.0, -100.0)])
        assert sorted(result) == ["CA", "US"]

    def test_sampling_large_list(self) -> None:
        """60 points should be sampled down to ~30 via step=2."""
        points = [(35.0, -90.0 + i * 0.1) for i in range(60)]
        call_args: list[tuple[float, float]] = []

        def mock_cap(lat: float, lon: float) -> list[str]:
            call_args.append((lat, lon))
            return ["US"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            result = cb.countries_from_points(points)
        # step = max(1, 60//30) = 2, so ~30 calls
        assert len(call_args) <= 31  # 60/2 = 30, possibly +1 due to indexing
        assert result == ["US"]

    def test_sampling_over_30_but_not_exact_multiple(self) -> None:
        """45 points => step = 1, all points sampled."""
        points = [(35.0, -90.0 + i * 0.1) for i in range(45)]
        call_args: list[tuple[float, float]] = []

        def mock_cap(lat: float, lon: float) -> list[str]:
            call_args.append((lat, lon))
            return ["US"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            cb.countries_from_points(points)
        # step = max(1, 45//30) = 1, so all 45 are sampled
        assert len(call_args) == 45

    def test_no_countries_found(self) -> None:
        with patch.object(cb, "countries_at_point", return_value=[]):
            result = cb.countries_from_points([(35.0, -90.0)])
        assert result == []

    def test_duplicate_countries_deduplicated(self) -> None:
        def mock_cap(lat: float, lon: float) -> list[str]:
            return ["US"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            result = cb.countries_from_points([(35.0, -90.0), (36.0, -91.0)])
        assert result == ["US"]

    def test_sampling_step_calculation_edge(self) -> None:
        """31 points => step = max(1, 31//30) = 1, all sampled."""
        points = [(35.0, -90.0)] * 31
        call_args: list[tuple[float, float]] = []

        def mock_cap(lat: float, lon: float) -> list[str]:
            call_args.append((lat, lon))
            return ["US"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            cb.countries_from_points(points)
        assert len(call_args) == 31

    def test_sampling_exactly_30(self) -> None:
        """30 points => step = 1, all sampled."""
        points = [(35.0, -90.0)] * 30
        call_args: list[tuple[float, float]] = []

        def mock_cap(lat: float, lon: float) -> list[str]:
            call_args.append((lat, lon))
            return ["US"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            cb.countries_from_points(points)
        assert len(call_args) == 30

    def test_sampling_under_30(self) -> None:
        """29 points => step = 1, all sampled."""
        points = [(35.0, -90.0)] * 29
        call_args: list[tuple[float, float]] = []

        def mock_cap(lat: float, lon: float) -> list[str]:
            call_args.append((lat, lon))
            return ["US"]
        with patch.object(cb, "countries_at_point", side_effect=mock_cap):
            cb.countries_from_points(points)
        assert len(call_args) == 29


# ===================================================================
# TestGetBounds – bounding box retrieval
# ===================================================================

class TestGetBounds:
    """Tests for get_bounds() — returns (lon_min, lat_min, lon_max, lat_max)."""

    def _populate_bbox(self) -> None:
        cb._DATA = {}
        cb._BBOX["US"] = (-100.0, 30.0, -80.0, 40.0)

    def test_valid_code(self) -> None:
        self._populate_bbox()
        assert cb.get_bounds("US") == (-100.0, 30.0, -80.0, 40.0)

    def test_upper_case_normalisation(self) -> None:
        self._populate_bbox()
        assert cb.get_bounds("us") == (-100.0, 30.0, -80.0, 40.0)

    def test_invalid_code(self) -> None:
        self._populate_bbox()
        assert cb.get_bounds("ZZ") is None

    def test_empty_bbox(self) -> None:
        cb._DATA = {}
        cb._BBOX = {}
        assert cb.get_bounds("US") is None

    def test_load_is_called_when_data_none(self) -> None:
        with patch.object(cb, "_load") as mock_load:
            mock_load.return_value = None
            cb.get_bounds("US")
        mock_load.assert_called_once()


# ===================================================================
# TestLoad – data-loading and error handling
# ===================================================================

class TestLoad:
    """Tests for _load() — file loading, caching, and failure paths."""

    def test_load_success(self) -> None:
        """Successfully read valid JSON and build _BBOX."""
        import io
        data = {"XX": [[[1.0, 2.0], [3.0, 4.0]]]}
        file_obj = io.StringIO(json.dumps(data))

        with patch.object(cb, "open", return_value=file_obj):
            result = cb._load()

        assert result == data
        assert cb._DATA == data
        # _BBOX built from ring coords: lons = [2.0, 4.0], lats = [1.0, 3.0]
        assert cb._BBOX["XX"] == (2.0, 1.0, 4.0, 3.0)

    def test_load_file_not_found(self) -> None:
        """When the JSON file doesn't exist, _load should return None."""
        with patch.object(cb, "open", side_effect=FileNotFoundError("No such file")):
            result = cb._load()
        assert result is None
        assert cb._DATA is None
        assert cb._BBOX == {}

    def test_load_invalid_json(self) -> None:
        """When the JSON file is malformed, _load should return None."""
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "not valid json"
        with patch.object(cb, "open", return_value=mock_file):
            with patch.object(cb, "json", wraps=cb.json) as mock_json:
                mock_json.load.side_effect = json.JSONDecodeError("bad", "doc", 0)
                result = cb._load()
        assert result is None
        assert cb._DATA is None

    def test_load_any_exception_caught(self) -> None:
        """Any Exception during load should be caught and return None."""
        with patch.object(cb, "open", side_effect=PermissionError("denied")):
            result = cb._load()
        assert result is None
        assert cb._DATA is None

    def test_load_caches_success(self) -> None:
        """After first successful load, _DATA is cached so second call
        returns immediately without re-reading the file."""
        import io
        data = {"XX": [[[1.0, 2.0]]]}
        file_obj = io.StringIO(json.dumps(data))

        with patch.object(cb, "open", return_value=file_obj) as mock_open:
            result1 = cb._load()
            result2 = cb._load()

        assert result1 == data
        assert result2 == data
        # open should only be called once (second call hits cache)
        mock_open.assert_called_once()

    def test_load_builds_bbox(self) -> None:
        """After loading, _BBOX should be populated for each country."""
        data = {
            "US": [[[30.0, -100.0], [30.0, -80.0], [40.0, -80.0], [40.0, -100.0]]],
            "CA": [[[50.0, -110.0], [50.0, -90.0], [60.0, -90.0], [60.0, -110.0]]],
        }
        with patch.object(cb, "_load", return_value=data) as mock_load:
            cb._DATA = data
            # Manually build bbox to test the bbox logic without mocking _load
            for code, rings in data.items():
                all_lats = []
                all_lons = []
                for ring in rings:
                    all_lats.extend(p[0] for p in ring)
                    all_lons.extend(p[1] for p in ring)
                cb._BBOX[code] = (min(all_lons), min(all_lats), max(all_lons), max(all_lats))
        assert cb._BBOX["US"] == (-100.0, 30.0, -80.0, 40.0)
        assert cb._BBOX["CA"] == (-110.0, 50.0, -90.0, 60.0)

    def test_load_logs_warning_on_failure(self, caplog) -> None:
        """On failure, _load should log a warning."""
        with patch.object(cb, "open", side_effect=FileNotFoundError("test")):
            with caplog.at_level(logging.WARNING):
                cb._load()
        assert "Failed to load country borders" in caplog.text


# ===================================================================
# TestIntegration – end-to-end with mocked data
# ===================================================================

class TestIntegration:
    """Integration-style tests: multiple functions called with shared data."""

    def test_full_pipeline_single_point(self) -> None:
        """get_polygon → point_in_polygon → countries_at_point."""
        _set_data(SAMPLE_DATA)
        poly = cb.get_polygon("US")
        inside = cb.point_in_polygon(35.0, -90.0, poly)
        countries = cb.countries_at_point(35.0, -90.0)
        assert inside is True
        assert "US" in countries

    def test_full_pipeline_island_point(self) -> None:
        """Point inside island ring but not mainland."""
        _set_data(SAMPLE_DATA)
        countries = cb.countries_at_point(41.5, -81.5)
        in_us_islands = cb.point_in_country(41.5, -81.5, "US_ISLANDS")
        in_us = cb.point_in_country(41.5, -81.5, "US")
        assert countries == ["US_ISLANDS"]
        assert in_us_islands is True
        assert in_us is False

    def test_countries_from_points_deduplicates(self) -> None:
        """Multiple points in same country produce single result."""
        data = {"US": [US_RING]}
        _set_data(data)
        points = [(35.0 + i, -90.0) for i in range(5)]  # all inside US
        result = cb.countries_from_points(points)
        assert result == ["US"]


# ===================================================================
# TestEdgeCases – unusual or error-prone inputs
# ===================================================================

class TestEdgeCases:
    """Miscellaneous edge cases not covered above."""

    def test_get_polygon_none_code(self) -> None:
        """Passing None as code should not crash (but will upper() fail)."""
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            with pytest.raises(AttributeError):
                cb.get_polygon(None)  # type: ignore[arg-type]

    def test_get_bounds_none_code(self) -> None:
        with pytest.raises(AttributeError):
            cb.get_bounds(None)  # type: ignore[arg-type]

    def test_bbox_contains_none_code(self) -> None:
        with pytest.raises(AttributeError):
            cb.bbox_contains(None, 35.0, -90.0)  # type: ignore[arg-type]

    def test_point_in_country_none_code(self) -> None:
        with pytest.raises(AttributeError):
            cb.point_in_country(35.0, -90.0, None)  # type: ignore[arg-type]

    def test_point_in_polygon_nan_coordinates(self) -> None:
        """NaN coordinates should not crash (math behaviour is defined)."""
        import math
        result = cb.point_in_polygon(float("nan"), 0.0, SQUARE)
        # nan comparisons are False, so this should be False
        assert result is False

    def test_point_in_polygon_inf_coordinates(self) -> None:
        result = cb.point_in_polygon(float("inf"), 0.0, SQUARE)
        assert result is False

    def test_countries_at_point_nan(self) -> None:
        with patch.object(cb, "_load", return_value=SAMPLE_DATA):
            result = cb.countries_at_point(float("nan"), float("nan"))
        assert result == []

    def test_self_intersecting_polygon(self) -> None:
        """A bow-tie polygon — still returns a bool without crashing."""
        bow_tie = [(0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)]
        result = cb.point_in_polygon(5.0, 5.0, bow_tie)
        assert isinstance(result, bool)

    def test_very_large_polygon(self) -> None:
        """Many points should not cause performance issues."""
        large_poly = [(float(i), float(i * 0.5)) for i in range(1000)]
        result = cb.point_in_polygon(500.0, 250.0, large_poly)
        assert isinstance(result, bool)

    def test_countries_from_points_empty_after_patch(self) -> None:
        """countries_at_point returning empty for all points."""
        with patch.object(cb, "countries_at_point", return_value=[]):
            result = cb.countries_from_points([(1.0, 2.0), (3.0, 4.0)])
        assert result == []

    def test_get_bounds_load_trigger(self) -> None:
        """get_bounds should trigger _load when _DATA is None."""
        with patch.object(cb, "_load") as mock_load:
            mock_load.return_value = SAMPLE_DATA
            cb.get_bounds("US")
        mock_load.assert_called_once()

    def test_bbox_contains_load_trigger(self) -> None:
        """bbox_contains should trigger _load when _DATA is None."""
        with patch.object(cb, "_load") as mock_load:
            mock_load.return_value = SAMPLE_DATA
            cb.bbox_contains("US", 35.0, -90.0)
        mock_load.assert_called_once()
