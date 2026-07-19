"""Tests for ui/map/map_helpers.py — overlay creation, coordinate handling."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def map_widget():
    """Mock MapWidget JS bridge."""
    mw = MagicMock()
    mw.clear_overlays = MagicMock()
    mw.add_polyline = MagicMock()
    mw.add_marker = MagicMock()
    return mw


# =========================================================================
# clear_map_overlays
# =========================================================================


class TestClearMapOverlays:
    """Delegates to map_widget.clear_overlays."""

    def test_clears_overlays(self, map_widget):
        from ui.map.map_helpers import clear_map_overlays
        clear_map_overlays(map_widget)
        map_widget.clear_overlays.assert_called_once()

    def test_with_none_map(self):
        from ui.map.map_helpers import clear_map_overlays
        clear_map_overlays(None)  # must not crash

    def test_when_map_widget_raises(self, map_widget):
        map_widget.clear_overlays.side_effect = RuntimeError("fail")
        from ui.map.map_helpers import clear_map_overlays
        clear_map_overlays(map_widget)  # must not crash


# =========================================================================
# create_path_on_map
# =========================================================================


class TestCreatePathOnMap:
    """Route path creation with geometry, markers, and stops."""

    def test_returns_tuple(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        result = create_path_on_map(map_widget, [(44.4, 26.1), (46.7, 23.6)])
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_with_none_map_widget(self):
        from ui.map.map_helpers import create_path_on_map
        result = create_path_on_map(None, [(44.4, 26.1)])
        assert result == (None, None, None, [])

    def test_with_empty_geometry(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        result = create_path_on_map(map_widget, [])
        assert result == (None, None, None, [])

    def test_adds_polyline(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        create_path_on_map(map_widget, geometry)
        map_widget.add_polyline.assert_called_once_with(geometry)

    def test_clears_overlays_before_draw(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        create_path_on_map(map_widget, [(44.4, 26.1), (46.7, 23.6)])
        map_widget.clear_overlays.assert_called_once()

    def test_with_start_marker(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        coords, start_marker, end_marker, stops = create_path_on_map(
            map_widget, geometry, start_city="Bucharest",
        )
        map_widget.add_marker.assert_any_call(44.4, 26.1, "Bucharest", "green")
        assert start_marker == (44.4, 26.1, "Bucharest", "green")

    def test_with_end_marker(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        coords, start_marker, end_marker, stops = create_path_on_map(
            map_widget, geometry, end_city="Cluj",
        )
        map_widget.add_marker.assert_any_call(46.7, 23.6, "Cluj", "red")
        assert end_marker == (46.7, 23.6, "Cluj", "red")

    def test_with_both_start_and_end(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (45.0, 25.0), (46.7, 23.6)]
        coords, start_marker, end_marker, stops = create_path_on_map(
            map_widget, geometry,
            start_city="Bucharest", end_city="Cluj",
        )
        map_widget.add_marker.assert_any_call(44.4, 26.1, "Bucharest", "green")
        map_widget.add_marker.assert_any_call(46.7, 23.6, "Cluj", "red")
        assert start_marker is not None
        assert end_marker is not None

    def test_with_intermediate_stops(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (45.5, 24.5), (46.7, 23.6)]
        stops_data = [(45.5, 24.5, "Pitesti")]
        coords, start_marker, end_marker, stop_markers = create_path_on_map(
            map_widget, geometry, intermediate_stops=stops_data,
        )
        map_widget.add_marker.assert_any_call(45.5, 24.5, "Pitesti", "blue")
        assert (45.5, 24.5, "Pitesti", "blue") in stop_markers

    def test_with_create_markers_false(self, map_widget):
        """When create_markers=False, no markers are added despite city labels."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        coords, start_marker, end_marker, stops = create_path_on_map(
            map_widget, geometry,
            start_city="Bucharest", end_city="Cluj",
            create_markers=False,
        )
        map_widget.add_marker.assert_not_called()
        assert start_marker is None
        assert end_marker is None

    def test_start_marker_with_single_point_geometry(self, map_widget):
        """Single point geometry still draws start marker at index 0."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1)]
        coords, start, end, stops = create_path_on_map(
            map_widget, geometry, start_city="Only", end_city="Same",
        )
        # Start marker uses coords[0], end marker uses coords[-1]
        assert start == (44.4, 26.1, "Only", "green")
        assert end == (44.4, 26.1, "Same", "red")

    def test_geometry_bad_coords_filtered(self, map_widget):
        """Points with fewer than 2 elements are filtered out."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (1,), (46.7, 23.6)]
        result = create_path_on_map(map_widget, geometry)
        map_widget.add_polyline.assert_called_once()
        called_coords = map_widget.add_polyline.call_args[0][0]
        assert len(called_coords) == 2  # bad point filtered
        assert called_coords == [(44.4, 26.1), (46.7, 23.6)]

    def test_returns_coords_polyline(self, map_widget):
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        coords, start, end, stops = create_path_on_map(map_widget, geometry)
        assert coords == geometry

    def test_no_markers_when_only_intermediate(self, map_widget):
        """Intermediate stops without start/end city labels."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        coords, start, end, stops = create_path_on_map(
            map_widget, geometry,
            intermediate_stops=[(45.0, 25.0, "Mid")],
        )
        assert start is None
        assert end is None
        assert len(stops) == 1


# =========================================================================
# Error handling — map_widget raises
# =========================================================================


class TestMapWidgetErrors:
    """Graceful degradation when map_widget methods raise."""

    def test_clear_overlays_fail(self, map_widget):
        map_widget.clear_overlays.side_effect = RuntimeError("clear fail")
        from ui.map.map_helpers import create_path_on_map
        # Should not crash; polyline should still be attempted
        result = create_path_on_map(map_widget, [(44.4, 26.1), (46.7, 23.6)])
        coords, start, end, stops = result
        assert coords is not None

    def test_add_polyline_fail(self, map_widget):
        map_widget.add_polyline.side_effect = RuntimeError("poly fail")
        from ui.map.map_helpers import create_path_on_map
        result = create_path_on_map(
            map_widget, [(44.4, 26.1), (46.7, 23.6)],
            start_city="A", end_city="B",
        )
        # Markers still added
        coords, start, end, stops = result
        assert start is not None
        assert end is not None

    def test_add_marker_fail(self, map_widget):
        map_widget.add_marker.side_effect = RuntimeError("marker fail")
        from ui.map.map_helpers import create_path_on_map
        result = create_path_on_map(
            map_widget, [(44.4, 26.1), (46.7, 23.6)],
            start_city="A",
        )
        # start_marker stays None when add_marker fails
        coords, start, end, stops = result
        assert start is None  # because add_marker raised

    def test_intermediate_marker_fail(self, map_widget):
        """Failure of one intermediate stop marker doesn't block others."""
        # Start marker succeeds, end marker raises, intermediate marker succeeds
        map_widget.add_marker.side_effect = [None, RuntimeError("fail"), None]
        from ui.map.map_helpers import create_path_on_map
        result = create_path_on_map(
            map_widget, [(44.4, 26.1), (45.0, 25.0), (46.7, 23.6)],
            start_city="Start",
            end_city="End",
            intermediate_stops=[(45.0, 25.0, "Mid")],
        )
        coords, start, end, stops = result
        assert start is not None  # start marker succeeded
        assert end is None  # end marker raised
        assert len(stops) == 1  # intermediate marker succeeded


# =========================================================================
# Edge cases — null island, empty coordinates
# =========================================================================


class TestEdgeCases:
    """Edge cases: null island (0,0), extreme coordinates."""

    def test_null_island(self, map_widget):
        """Null island (0,0) is a valid coordinate pair."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(0.0, 0.0), (1.0, 1.0)]
        result = create_path_on_map(map_widget, geometry)
        coords, start, end, stops = result
        assert coords == geometry

    def test_single_point_geometry(self, map_widget):
        """Single point still creates polyline with that point."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1)]
        result = create_path_on_map(map_widget, geometry)
        coords, start, end, stops = result
        assert len(coords) == 1
        map_widget.add_polyline.assert_called_once()

    def test_large_coordinates(self, map_widget):
        """Very large coordinate values are handled."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(180.0, 90.0), (-180.0, -90.0)]
        result = create_path_on_map(map_widget, geometry)
        coords, start, end, stops = result
        assert len(coords) == 2

    def test_negative_coordinates(self, map_widget):
        """Negative lat/lon values."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(-33.8, 151.2), (-37.8, 144.9)]
        result = create_path_on_map(map_widget, geometry)
        coords, start, end, stops = result
        assert len(coords) == 2

    def test_float_conversion_from_int(self, map_widget):
        """Integer tuples are converted to float."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44, 26), (45, 27)]
        result = create_path_on_map(map_widget, geometry)
        coords, _, _, _ = result
        assert all(isinstance(v, float) for v in coords[0])
        assert coords[0] == (44.0, 26.0)

    def test_empty_intermediate_stops(self, map_widget):
        """Empty intermediate_stops list produces no stop markers."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        result = create_path_on_map(map_widget, geometry, intermediate_stops=[])
        coords, start, end, stops = result
        assert stops == []

    def test_multiple_intermediate_stops(self, map_widget):
        """Multiple intermediate stops all get markers."""
        from ui.map.map_helpers import create_path_on_map
        geometry = [(44.4, 26.1), (45.0, 25.0), (46.0, 24.0), (46.7, 23.6)]
        stops_data = [
            (45.0, 25.0, "Stop1"),
            (46.0, 24.0, "Stop2"),
        ]
        result = create_path_on_map(
            map_widget, geometry, intermediate_stops=stops_data,
        )
        coords, start, end, stops = result
        assert len(stops) == 2
        assert (45.0, 25.0, "Stop1", "blue") in stops
        assert (46.0, 24.0, "Stop2", "blue") in stops
