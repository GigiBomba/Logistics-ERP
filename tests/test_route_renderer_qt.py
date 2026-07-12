"""pytest-qt tests for QtRouteMapRenderer — route overlay rendering.

Expands the legacy tests in ``test_route_renderer.py`` with pytest-qt fixtures,
mock map widgets, and coverage for all public methods.

Tests
-----
- Initialization and map_widget reference
- Clear overlays (stop markers, route overlays, safe with None map)
- draw_route with geometry, downsample, alternative route, and edge cases
- should_redraw / mark_redrawn deduplication logic
- center_on_geometry
- update_stop_markers (start, stop, destination, unresolved, missing coords)
- draw_avoided_country_overlays
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui.map.route_renderer import QtRouteMapRenderer


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def map_widget():
    """Return a MagicMock standing in for a MapWidget JS bridge."""
    return MagicMock()


@pytest.fixture
def renderer(map_widget, qtbot):
    """Create a QtRouteMapRenderer with a mocked map widget."""
    r = QtRouteMapRenderer(map_widget)
    # No widget to add via qtbot.addWidget — the renderer is not a QWidget.
    yield r


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Renderer initializes correctly."""

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

    def test_clear_without_map_widget(self):
        r = QtRouteMapRenderer(None)
        r.clear_stop_markers()  # must not crash

    def test_clear_when_map_widget_raises(self, renderer):
        renderer.map_widget.clear_overlays.side_effect = RuntimeError("fail")
        renderer.clear_stop_markers()  # must not crash


# =========================================================================
# draw_route
# =========================================================================


class TestDrawRoute:
    """Route drawing with geometry, comparison, and downsample."""

    def test_empty_geometry_does_nothing(self, renderer):
        renderer.draw_route([])
        renderer.map_widget.add_polyline.assert_not_called()

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

    def test_draw_route_without_map(self):
        r = QtRouteMapRenderer(None)
        r.draw_route([(44.4, 26.1), (46.7, 23.6)])  # must not crash

    def test_draw_route_with_map_widget_error(self, renderer):
        renderer.map_widget.clear_overlays.side_effect = RuntimeError("boom")
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        renderer.draw_route(geometry)  # must not crash
        # Should still try to draw
        renderer.map_widget.add_polyline.assert_called()

    def test_downsample_long_geometry(self, renderer):
        """Routes with >500 points are downsampled to ~500 pts (plus endpoint if missing)."""
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

    def test_downsample_with_exact_boundary_no_duplicate(self, renderer):
        """501 pts -> step = 2 -> 251 pts, last is not duplicated."""
        geo = [(float(i), float(i)) for i in range(501)]
        renderer.draw_route(geo)
        drawn = renderer.map_widget.add_polyline.call_args[0][0]
        assert drawn[-1] == (500.0, 500.0)

    def test_dedup_via_should_redraw(self, renderer):
        """Repeated draw with same geometry is skipped within interval."""
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        renderer.draw_route(geometry)
        assert renderer.map_widget.add_polyline.call_count == 1

        # Second draw with same geometry — should be deduped
        renderer.map_widget.add_polyline.reset_mock()
        renderer.draw_route(geometry)
        renderer.map_widget.add_polyline.assert_not_called()

    def test_alternative_route_comparison(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {
            "original_route": {
                "geometry": [(44.0, 26.0), (46.0, 23.0)],
            },
        }
        renderer.draw_route(geometry, route=route)
        # add_polyline called twice: once for alt route, once for primary
        assert renderer.map_widget.add_polyline.call_count == 2

    def test_alternative_route_skipped_when_disabled(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {
            "original_route": {
                "geometry": [(44.0, 26.0), (46.0, 23.0)],
            },
        }
        renderer.draw_route(geometry, route=route, show_comparison=False)
        # Only primary route drawn
        assert renderer.map_widget.add_polyline.call_count == 1

    def test_alternative_route_skipped_without_orig(self, renderer):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        renderer.draw_route(geometry, route={"distance_km": 500})
        assert renderer.map_widget.add_polyline.call_count == 1

    def test_draw_route_with_highlight_avoided(self, renderer, monkeypatch):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {"excluded_countries_requested": ["RO", "BG"]}
        overlay_called = False

        def fake_overlay(country_codes):
            nonlocal overlay_called
            overlay_called = True
            assert country_codes == ["RO", "BG"]

        monkeypatch.setattr(renderer, "draw_avoided_country_overlays", fake_overlay)
        renderer.draw_route(geometry, route=route, highlight_avoided=True)
        assert overlay_called

    def test_highlight_avoided_skipped_when_no_exclusions(self, renderer, monkeypatch):
        geometry = [(44.4, 26.1), (46.7, 23.6)]
        route = {}
        overlay_called = False

        def fake_overlay(country_codes):
            nonlocal overlay_called
            overlay_called = True

        monkeypatch.setattr(renderer, "draw_avoided_country_overlays", fake_overlay)
        renderer.draw_route(geometry, route=route, highlight_avoided=True)
        assert not overlay_called


# =========================================================================
# should_redraw / mark_redrawn
# =========================================================================


class TestRedrawDedup:
    """Deduplication logic for re-drawing the same geometry."""

    def test_should_redraw_empty_geometry_returns_false(self, renderer):
        assert renderer.should_redraw([]) is False

    def test_should_redraw_true_on_first_call(self, renderer):
        assert renderer.should_redraw([(44.4, 26.1), (46.7, 23.6)]) is True

    def test_should_redraw_false_after_mark(self, renderer):
        geo = [(44.4, 26.1), (46.7, 23.6)]
        renderer.mark_redrawn(geo)
        assert renderer.should_redraw(geo) is False

    def test_should_redraw_true_for_different_geometry(self, renderer):
        renderer.mark_redrawn([(1.0, 2.0), (3.0, 4.0)])
        assert renderer.should_redraw([(5.0, 6.0), (7.0, 8.0)]) is True

    def test_mark_redrawn_empty_does_nothing(self, renderer):
        renderer.mark_redrawn([])
        assert renderer._last_geom_key is None

    def test_mark_redrawn_sets_timestamp(self, renderer):
        geo = [(44.4, 26.1), (46.7, 23.6)]
        renderer.mark_redrawn(geo)
        assert renderer._last_geom_key == (2, (44.4, 26.1), (46.7, 23.6))
        assert renderer._last_draw_time > 0


# =========================================================================
# center_on_geometry
# =========================================================================


class TestCenterOnGeometry:
    """Centering the map view."""

    def test_center_on_geometry(self, renderer):
        renderer.center_on_geometry([(44.4, 26.1), (46.7, 23.6)], zoom=7)
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, 7)

    def test_center_with_default_zoom(self, renderer):
        renderer.center_on_geometry([(44.4, 26.1)])
        renderer.map_widget.set_view.assert_called_once_with(44.4, 26.1, 6)

    def test_center_empty_does_nothing(self, renderer):
        renderer.center_on_geometry([])
        renderer.map_widget.set_view.assert_not_called()

    def test_center_without_map(self):
        r = QtRouteMapRenderer(None)
        r.center_on_geometry([(1.0, 2.0)])  # must not crash

    def test_center_when_map_widget_raises(self, renderer):
        renderer.map_widget.set_view.side_effect = RuntimeError("fail")
        renderer.center_on_geometry([(44.4, 26.1)])  # must not crash


# =========================================================================
# update_stop_markers
# =========================================================================


class TestUpdateStopMarkers:
    """Stop markers are added for each resolved stop."""

    def test_empty_stops_clears_markers(self, renderer):
        renderer.update_stop_markers([])
        renderer.map_widget.clear_overlays.assert_called_once()

    def test_unresolved_stop_skipped(self, renderer):
        stops = [{"resolved": False, "address": "Somewhere"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_not_called()

    def test_stop_without_coords_skipped(self, renderer):
        stops = [{"resolved": True, "address": "No coords"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_not_called()

    def test_regular_stop_marker(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1, "address": "Stop A"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(
            44.4, 26.1, label="Stop A", color="blue",
        )

    def test_start_marker_color(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1,
                   "type": "start", "address": "Start"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(
            44.4, 26.1, label="Start", color="green",
        )

    def test_destination_marker_color(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1,
                   "type": "destination", "address": "Dest"}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(
            44.4, 26.1, label="Dest", color="red",
        )

    def test_multiple_stops(self, renderer):
        stops = [
            {"resolved": True, "lat": 44.4, "lon": 26.1,
             "type": "start", "address": "Start"},
            {"resolved": True, "lat": 45.0, "lon": 27.0,
             "type": "stop", "address": "Middle"},
            {"resolved": True, "lat": 46.7, "lon": 23.6,
             "type": "destination", "address": "End"},
        ]
        renderer.update_stop_markers(stops)
        assert renderer.map_widget.add_marker.call_count == 3

    def test_marker_without_address(self, renderer):
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1}]
        renderer.update_stop_markers(stops)
        renderer.map_widget.add_marker.assert_called_once_with(
            44.4, 26.1, label="", color="blue",
        )

    def test_marker_with_map_widget_error(self, renderer):
        renderer.map_widget.add_marker.side_effect = RuntimeError("oops")
        stops = [{"resolved": True, "lat": 44.4, "lon": 26.1, "address": "Err"}]
        renderer.update_stop_markers(stops)  # must not crash

    def test_update_stop_without_map(self):
        r = QtRouteMapRenderer(None)
        r.update_stop_markers([{"resolved": True, "lat": 44.4, "lon": 26.1}])  # must not crash


# =========================================================================
# draw_avoided_country_overlays
# =========================================================================


class TestDrawAvoidedCountryOverlays:
    """Avoided country overlay polygons."""

    def test_empty_country_list_does_nothing(self, renderer):
        renderer.draw_avoided_country_overlays([])
        renderer.map_widget.add_polygon.assert_not_called()

    def test_without_map_widget(self):
        r = QtRouteMapRenderer(None)
        r.draw_avoided_country_overlays(["RO"])  # must not crash

    def test_clears_existing_overlays_first(self, renderer):
        with patch("services.country_borders.get_polygons", return_value=[[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]):
            renderer.draw_avoided_country_overlays(["RO"])
            renderer.map_widget.clear_overlays.assert_called()

    def test_adds_polygon_for_each_ring(self, renderer):
        rings = [
            [(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)],
            [(44.5, 26.5), (45.5, 27.5), (46.5, 28.5)],
        ]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
            assert renderer.map_widget.add_polygon.call_count == 2

    def test_skips_rings_with_fewer_than_3_points(self, renderer):
        rings = [
            [(44.0, 26.0), (45.0, 27.0)],
            [(44.5, 26.5), (45.5, 27.5), (46.5, 28.5)],
        ]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
            assert renderer.map_widget.add_polygon.call_count == 1

    def test_uses_avoide_color_and_fill_opacity(self, renderer):
        rings = [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
            renderer.map_widget.add_polygon.assert_called_once_with(
                rings[0],
                color="#cc0000",
                fill_opacity=0.15,
            )

    def test_logs_warning_on_add_polygon_error(self, renderer, caplog):
        renderer.map_widget.add_polygon.side_effect = Exception("poly fail")
        rings = [[(44.0, 26.0), (45.0, 27.0), (46.0, 28.0)]]
        with patch("services.country_borders.get_polygons", return_value=rings):
            renderer.draw_avoided_country_overlays(["RO"])
        assert any("Failed to draw overlay" in rec.message for rec in caplog.records)


# =========================================================================
# Edge cases — map_widget is None
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
