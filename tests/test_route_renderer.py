"""Tests for QtRouteMapRenderer — route rendering, markers, overlays, edge cases."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui.map.route_renderer import QtRouteMapRenderer


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def map_widget():
    """Mock MapWidget JS bridge."""
    return MagicMock()


@pytest.fixture
def renderer(map_widget, qtbot):
    """Create a QtRouteMapRenderer with a mocked map widget."""
    r = QtRouteMapRenderer(map_widget)
    yield r


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Renderer initialises correctly."""

    def test_creation(self, map_widget):
        r = QtRouteMapRenderer(map_widget)
        assert r.map_widget is map_widget

    def test_defaults(self, renderer):
        assert renderer._last_geom_key is None
        assert renderer._last_draw_time == 0.0
        assert renderer._min_redraw_interval_s == 0.3
        assert renderer.MARKER_COLOR_START == "green"
        assert renderer.MARKER_COLOR_STOP == "blue"
        assert renderer.MARKER_COLOR_DEST == "red"
        assert renderer.ALT_ROUTE_COLOR == "gray"
        assert renderer.AVOID_COLOR == "#cc0000"
        assert renderer.AVOID_FILL_OPACITY == 0.15

    def test_without_map_widget(self):
        r = QtRouteMapRenderer(None)
        assert r.map_widget is None


# =========================================================================
# Clear overlays
# =========================================================================


class TestClear:
    """Clearing overlays delegates to map_widget."""

    def test_clear_stop_markers(self, renderer):
        renderer.clear_stop_markers()
        renderer.map_widget.clear_overlays.assert_called_once()

    def test_clear_route_overlays(self, renderer):
        renderer.clear_route_overlays()
        renderer.map_widget.clear_overlays.assert_called_once()

    def test_clear_without_map(self):
        r = QtRouteMapRenderer(None)
        r.clear_stop_markers()  # must not crash
        r.clear_route_overlays()  # must not crash

    def test_clear_when_map_raises(self, renderer):
        renderer.map_widget.clear_overlays.side_effect = RuntimeError("boom")
        renderer.clear_stop_markers()  # must not crash
        renderer.clear_route_overlays()  # must not crash


# =========================================================================
# draw_route — rendering options
# =========================================================================


class TestDrawRoute:
    """Route line rendering: geometry, downsample, comparison, avoided countries."""

    def test_empty_geometry_does_nothing(self, renderer):
        renderer.draw_route([])
        renderer.map_widget.clear_overlays.assert_not_called()

    def test_single_point_does_nothing(self, renderer):
        renderer.draw_route([(44.4, 26.1)])
        renderer.map_widget.add_polyline.assert_not_called()

    def test_basic_route(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        renderer.draw_route(geometry)
        renderer.map_widget.clear_overlays.assert_called()
        renderer.map_widget.add_polyline.assert_called_once()
        args = renderer.map_widget.add_polyline.call_args[0]
        assert args[0] == geometry

    def test_without_map_widget(self):
        r = QtRouteMapRenderer(None)
        r.draw_route([(1.0, 2.0), (3.0, 4.0)])  # must not crash

    def test_with_map_widget_error(self, renderer):
        renderer.map_widget.clear_overlays.side_effect = RuntimeError("clear fail")
        renderer.draw_route([(44.4, 26.1), (46.7, 23.6)])
        # Should still attempt to draw the polyline
        renderer.map_widget.add_polyline.assert_called()

    def test_downsample_long_geometry(self, renderer):
        """Routes with >500 points are downsampled to ~500 pts."""
        long_geo = [(float(i), float(i)) for i in range(1000)]
        renderer.draw_route(long_geo)
        renderer.map_widget.add_polyline.assert_called_once()
        drawn = renderer.map_widget.add_polyline.call_args[0][0]
        # 1000 pts with step=2 gives 500 pts, plus endpoint if different = up to 501
        assert 1 <= len(drawn) <= 501

    def test_downsample_preserves_endpoint(self, renderer):
        long_geo = [(float(i), float(i)) for i in range(1000)]
        renderer.draw_route(long_geo)
        drawn = renderer.map_widget.add_polyline.call_args[0][0]
        assert drawn[-1] == (999.0, 999.0)

    def test_downsample_exact_boundary_no_duplicate(self, renderer):
        """501 pts -> step=2 -> 251 pts, no duplicate endpoint."""
        geo = [(float(i), float(i)) for i in range(501)]
        renderer.draw_route(geo)
        drawn = renderer.map_widget.add_polyline.call_args[0][0]
        assert drawn[-1] == (500.0, 500.0)

    def test_bad_geometry_filtered(self, renderer):
        """Points with fewer than 2 elements are filtered out."""
        geometry = [(44.4, 26.1), (1,), (46.7, 23.6)]
        renderer.draw_route(geometry)
        called_coords = renderer.map_widget.add_polyline.call_args[0][0]
        assert len(called_coords) == 2

    def test_geometry_after_filter_too_short(self, renderer):
        """If filtering leaves < 2 points, nothing is drawn."""
        geometry = [(1,)]
        renderer.draw_route(geometry)
        renderer.map_widget.add_polyline.assert_not_called()

    # ── Comparison route ────────────────────────────────────────────

    def test_comparison_route_shown(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"original_route": {"geometry": [(44.0, 26.0), (46.0, 23.0)]}}
        renderer.draw_route(geometry, route=route, show_comparison=True)
        # add_polyline called twice: once for alt, once for primary
        assert renderer.map_widget.add_polyline.call_count == 2

    def test_comparison_route_disabled(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"original_route": {"geometry": [(44.0, 26.0), (46.0, 23.0)]}}
        renderer.draw_route(geometry, route=route, show_comparison=False)
        assert renderer.map_widget.add_polyline.call_count == 1

    def test_comparison_route_skipped_without_orig(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        renderer.draw_route(geometry, route={"distance_km": 500})
        assert renderer.map_widget.add_polyline.call_count == 1

    def test_comparison_route_handles_error(self, renderer):
        """If alt route draw fails, primary route still drawn."""
        renderer.map_widget.add_polyline.side_effect = [RuntimeError("alt fail"), None]
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"original_route": {"geometry": [(44.0, 26.0), (46.0, 23.0)]}}
        renderer.draw_route(geometry, route=route)
        # Primary was the second call — it was attempted even after alt failed
        assert renderer.map_widget.add_polyline.call_count == 2

    # ── Comparison with alt route having bad coords ─────────────────

    def test_comparison_bad_alt_coords_filtered(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"original_route": {"geometry": [(1,), (44.0, 26.0), (46.0, 23.0)]}}
        renderer.draw_route(geometry, route=route)
        # Both alt (filtered to 2 valid coords) and primary drawn
        assert renderer.map_widget.add_polyline.call_count == 2

    # ── Highlight avoided countries ─────────────────────────────────

    def test_highlight_avoided_calls_overlay(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"excluded_countries_requested": ["RO", "BG"]}
        with patch.object(renderer, "draw_avoided_country_overlays") as mock_ao:
            renderer.draw_route(geometry, route=route, highlight_avoided=True)
            mock_ao.assert_called_once_with(["RO", "BG"])

    def test_highlight_avoided_skipped_when_no_exclusions(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {}
        with patch.object(renderer, "draw_avoided_country_overlays") as mock_ao:
            renderer.draw_route(geometry, route=route, highlight_avoided=True)
            mock_ao.assert_not_called()

    def test_highlight_avoided_skipped_when_flag_false(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"excluded_countries_requested": ["RO"]}
        with patch.object(renderer, "draw_avoided_country_overlays") as mock_ao:
            renderer.draw_route(geometry, route=route, highlight_avoided=False)
            mock_ao.assert_not_called()

    def test_highlight_avoided_empty_exclusion_list(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"excluded_countries_requested": []}
        with patch.object(renderer, "draw_avoided_country_overlays") as mock_ao:
            renderer.draw_route(geometry, route=route, highlight_avoided=True)
            mock_ao.assert_not_called()

    # ── Both comparison + highlight together ────────────────────────

    def test_both_comparison_and_highlight(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {
            "original_route": {"geometry": [(44.0, 26.0), (46.0, 23.0)]},
            "excluded_countries_requested": ["RO"],
        }
        with patch.object(renderer, "draw_avoided_country_overlays") as mock_ao:
            renderer.draw_route(geometry, route=route, show_comparison=True, highlight_avoided=True)
            assert renderer.map_widget.add_polyline.call_count == 2
            mock_ao.assert_called_once_with(["RO"])

    # ── Dedup via should_redraw ─────────────────────────────────────

    def test_dedup_same_geometry(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        renderer.draw_route(geometry)
        assert renderer.map_widget.add_polyline.call_count == 1
        renderer.map_widget.add_polyline.reset_mock()
        renderer.draw_route(geometry)
        renderer.map_widget.add_polyline.assert_not_called()

    def test_different_geometry_redraws(self, renderer):
        renderer.draw_route([(1.0, 2.0), (3.0, 4.0)])
        renderer.map_widget.add_polyline.reset_mock()
        renderer.draw_route([(5.0, 6.0), (7.0, 8.0)])
        renderer.map_widget.add_polyline.assert_called_once()


# =========================================================================
# should_redraw / mark_redrawn
# =========================================================================


class TestRedrawDedup:
    """Deduplication logic for re-drawing the same geometry."""

    def test_should_redraw_empty_false(self, renderer):
        assert renderer.should_redraw([]) is False

    def test_should_redraw_true_first_call(self, renderer):
        assert renderer.should_redraw([(1.0, 2.0), (3.0, 4.0)]) is True

    def test_should_redraw_false_after_mark(self, renderer):
        geo = [(1.0, 2.0), (3.0, 4.0)]
        renderer.mark_redrawn(geo)
        assert renderer.should_redraw(geo) is False

    def test_should_redraw_true_different_geo(self, renderer):
        renderer.mark_redrawn([(1.0, 2.0), (3.0, 4.0)])
        assert renderer.should_redraw([(5.0, 6.0), (7.0, 8.0)]) is True

    def test_should_redraw_with_none_geo(self, renderer):
        """None or falsy geometry returns False."""
        assert renderer.should_redraw(None) is False
        assert renderer.should_redraw([]) is False

    def test_mark_redrawn_empty_does_nothing(self, renderer):
        renderer.mark_redrawn([])
        assert renderer._last_geom_key is None

    def test_mark_redrawn_sets_timestamp(self, renderer):
        geo = [(1.0, 2.0), (3.0, 4.0)]
        renderer.mark_redrawn(geo)
        assert renderer._last_geom_key == (2, (1.0, 2.0), (3.0, 4.0))
        assert renderer._last_draw_time > 0

    def test_mark_redrawn_none_does_nothing(self, renderer):
        renderer.mark_redrawn(None)
        assert renderer._last_geom_key is None

    def test_time_based_redraw_expiry(self, renderer):
        """After the min_redraw_interval expires, same geometry redraws."""
        import time
        geo = [(1.0, 2.0), (3.0, 4.0)]
        renderer.mark_redrawn(geo)
        # Fast forward past the interval
        renderer._last_draw_time = time.time() - renderer._min_redraw_interval_s - 0.1
        assert renderer.should_redraw(geo) is True


# =========================================================================
# center_on_geometry
# =========================================================================


class TestCenterOnGeometry:
    """Centering the map view on a geometry."""

    def test_center_on_geometry(self, renderer):
        renderer.center_on_geometry([(44.4, 26.1), (46.7, 23.6)], zoom=7)
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, 7)

    def test_default_zoom(self, renderer):
        renderer.center_on_geometry([(44.4, 26.1)])
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, 6)

    def test_empty_does_nothing(self, renderer):
        renderer.center_on_geometry([])
        renderer.map_widget.set_view.assert_not_called()

    def test_without_map(self):
        r = QtRouteMapRenderer(None)
        r.center_on_geometry([(1.0, 2.0)])  # must not crash

    def test_when_map_raises(self, renderer):
        renderer.map_widget.set_view.side_effect = RuntimeError("view fail")
        renderer.center_on_geometry([(44.4, 26.1)])  # must not crash

    def test_zoom_zero(self, renderer):
        renderer.center_on_geometry([(44.4, 26.1)], zoom=0)
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, 0)

    def test_zoom_negative(self, renderer):
        renderer.center_on_geometry([(44.4, 26.1)], zoom=-1)
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, -1)

    def test_single_point_convenience(self, renderer):
        """center_on_geometry uses the first point."""
        renderer.center_on_geometry([(44.4, 26.1)])
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, 6)


# =========================================================================
# update_stop_markers
# =========================================================================


class TestUpdateStopMarkers:
    """Stop markers for waypoints: start, stop, destination, unresolved."""

    def test_empty_stops_clears(self, renderer):
        renderer.update_stop_markers([])
        renderer.map_widget.clear_overlays.assert_called_once()

    def test_unresolved_stop_skipped(self, renderer):
        stops = [{"resolved": False, "address": "Somewhere"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_not_called()

    def test_missing_coords_skipped(self, renderer):
        stops = [{"resolved": True, "address": "No Coords"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_not_called()

    def test_none_lat_lon_skipped(self, renderer):
        stops = [{"resolved": True, "lat": None, "lon": None, "address": "Null"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_not_called()

    def test_partial_none_lat(self, renderer):
        stops = [{"resolved": True, "lat": None, "lon": 26.1, "address": "No lat"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_not_called()

    def test_regular_stop(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1, "address": "Pitesti"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(44.4, 26.1, label="Pitesti", color="blue")

    def test_start_marker(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1, "type": "start", "address": "Start"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(44.4, 26.1, label="Start", color="green")

    def test_destination_marker(self, renderer):
        stops = [{"resolved": True, "lat": 46.7, "lon": 23.6, "type": "destination", "address": "Dest"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(46.7, 23.6, label="Dest", color="red")

    def test_marker_without_address(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(44.4, 26.1, label="", color="blue")

    def test_mixed_resolved_unresolved(self, renderer):
        stops = [
            {"resolved": False, "lat": 44.0, "lon": 26.0, "address": "Skip"},
            {"resolved": True, "lat": 45.0, "lon": 25.0, "address": "Draw"},
            {"resolved": True, "lat": None, "lon": 24.0, "address": "Skip too"},
        ]
        renderer.update_stop_markers(stops)
        assert renderer.map_widget.add_marker.call_count == 1

    def test_multiple_stops(self, renderer):
        stops = [
            {"resolved": True, "lat": 44.4, "lon": 26.1, "type": "start", "address": "A"},
            {"resolved": True, "lat": 45.0, "lon": 25.0, "address": "B"},
            {"resolved": True, "lat": 46.7, "lon": 23.6, "type": "destination", "address": "C"},
        ]
        renderer.update_stop_markers(stops)
        assert renderer.map_widget.add_marker.call_count == 3

    def test_map_widget_error(self, renderer):
        renderer.map_widget.add_marker.side_effect = RuntimeError("marker fail")
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1, "address": "Err"}]
        renderer.update_stop_markers(stops)  # must not crash

    def test_without_map(self):
        r = QtRouteMapRenderer(None)
        r.update_stop_markers([{"resolved": True, "lat": 1.0, "lon": 2.0}])  # must not crash


# =========================================================================
# draw_avoided_country_overlays
# =========================================================================


class TestDrawAvoidedCountryOverlays:
    """Country polygon overlays for avoided regions."""

    def test_empty_list_does_nothing(self, renderer):
        renderer.draw_avoided_country_overlays([])
        renderer.map_widget.add_polygon.assert_not_called()

    def test_without_map(self):
        r = QtRouteMapRenderer(None)
        r.draw_avoided_country_overlays(["RO"])  # must not crash

    def test_clears_existing_first(self, renderer):
        with patch("services.country_borders.get_polygons", return_value=[[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]):
            renderer.draw_avoided_country_overlays(["RO"])
            renderer.map_widget.clear_overlays.assert_called()

    def test_adds_polygon_per_ring(self, renderer):
        rings = [
            [(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)],
            [(44.5, 26.5), (45.5, 27.5), (46.5, 28.5)],
        ]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
            assert renderer.map_widget.add_polygon.call_count == 2

    def test_skips_rings_with_under_3_points(self, renderer):
        rings = [
            [(44.0, 26.0), (45.0, 27.0)],
            [(44.5, 26.5), (45.5, 27.5), (46.5, 28.5)],
        ]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
            assert renderer.map_widget.add_polygon.call_count == 1

    def test_uses_correct_style(self, renderer):
        rings = [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
            renderer.map_widget.add_polygon.assert_called_once_with(
                rings[0], color="#cc0000", fill_opacity=0.15,
            )

    def test_multiple_countries(self, renderer):
        with patch("services.country_borders.get_polygons") as mock_gp:
            mock_gp.side_effect = [
                [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]],
                [[(47.0, 20.0), (48.0, 21.0), (49.0, 22.0)]],
            ]
            renderer.draw_avoided_country_overlays(["RO", "BG"])
            assert renderer.map_widget.add_polygon.call_count == 2

    def test_country_with_no_polygons(self, renderer):
        """Country with no polygon data is skipped."""
        with patch("services.country_borders.get_polygons", return_value=[]):
            renderer.draw_avoided_country_overlays(["XY"])
            renderer.map_widget.add_polygon.assert_not_called()

    def test_mixed_valid_invalid_countries(self, renderer):
        with patch("services.country_borders.get_polygons") as mock_gp:
            mock_gp.side_effect = [
                [],  # XY — no polygons
                [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]],  # RO — has polygon
            ]
            renderer.draw_avoided_country_overlays(["XY", "RO"])
            assert renderer.map_widget.add_polygon.call_count == 1

    def test_logs_warning_on_error(self, renderer, caplog):
        renderer.map_widget.add_polygon.side_effect = RuntimeError("poly fail")
        rings = [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
        assert any("Failed to draw overlay" in rec.message for rec in caplog.records)

    def test_country_code_uppercased(self, renderer):
        """Lowercase country codes are uppercased before lookup."""
        with patch("services.country_borders.get_polygons") as mock_gp:
            mock_gp.return_value = [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]
            renderer.draw_avoided_country_overlays(["ro"])
            mock_gp.assert_called_with("RO")


# =========================================================================
# Edge cases — all methods safe with None map_widget
# =========================================================================


class TestNoMapWidget:
    """All methods are safe when map_widget is None."""

    def test_all_methods_safe(self):
        r = QtRouteMapRenderer(None)
        r.clear_stop_markers()
        r.clear_route_overlays()
        r.draw_route([(1.0, 2.0), (3.0, 4.0)])
        r.center_on_geometry([(1.0, 2.0)])
        r.update_stop_markers([{"resolved": True, "lat": 1.0, "lon": 2.0}])
        r.draw_avoided_country_overlays(["RO"])
        r.mark_redrawn([(1.0, 2.0)])
        assert r.should_redraw([(1.0, 2.0), (3.0, 4.0)]) is True


# =========================================================================
# Edge cases — extreme coordinates, empty route dict, null island
# =========================================================================


class TestEdgeCases:
    """Edge cases: null island, empty route dict, single point track."""

    def test_null_island_route(self, renderer):
        """Null island (0,0) is a valid coordinate."""
        geometry = [(0.0, 0.0), (1.0, 1.0)]
        renderer.draw_route(geometry)
        renderer.map_widget.add_polyline.assert_called_once()
        args = renderer.map_widget.add_polyline.call_args[0]
        assert args[0] == geometry

    def test_route_dict_none(self, renderer):
        """route=None does not crash."""
        renderer.draw_route([(44.4, 26.1), (46.7, 23.6)], route=None)
        renderer.map_widget.add_polyline.assert_called_once()

    def test_route_dict_empty(self, renderer):
        """route={} does not crash."""
        renderer.draw_route([(44.4, 26.1), (46.7, 23.6)], route={})
        renderer.map_widget.add_polyline.assert_called_once()

    def test_draw_route_with_only_bad_points(self, renderer):
        """All points are invalid (< 2 coords each) -> nothing drawn."""
        geometry = [(1,), (2,)]
        renderer.draw_route(geometry)
        renderer.map_widget.add_polyline.assert_not_called()

    def test_negative_coordinates(self, renderer):
        geometry = [(-33.8, 151.2), (-37.8, 144.9)]
        renderer.draw_route(geometry)
        renderer.map_widget.add_polyline.assert_called_once()
        args = renderer.map_widget.add_polyline.call_args[0]
        assert args[0] == geometry

    def test_center_on_null_island(self, renderer):
        renderer.center_on_geometry([(0.0, 0.0)])
        renderer.map_widget.set_view.assert_called_once_with(0.0, 0.0, 6)

    def test_update_stop_markers_with_negative_coords(self, renderer):
        stops = [{"resolved": True, "lat": -33.8, "lon": 151.2, "address": "Sydney"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(-33.8, 151.2, label="Sydney", color="blue")

    def test_downsample_with_0_and_negative_coords(self, renderer):
        """Downsample still works with zero and negative coords."""
        geo = [(float(i - 500), float(i - 500)) for i in range(1000)]
        renderer.draw_route(geo)
        renderer.map_widget.add_polyline.assert_called_once()
        drawn = renderer.map_widget.add_polyline.call_args[0][0]
        # Should still be downsampled
        assert len(drawn) < 1000
        assert drawn[-1] == (499.0, 499.0)
