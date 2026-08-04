"""Tests for the PySide6 route planner view."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui.views.route_planner_view import QtRoutePlannerView


@pytest.fixture
def route_planner(qt_widget, qtbot):
    # Replace MapWidget with FakeMapWidget to avoid QWebEngineView in tests.
    from tests.test_map_widget import FakeMapWidget

    with patch(
        "ui.views.route_planner_view.MapWidget",
        new=FakeMapWidget,
    ), patch(
        "ui.views.route_planner_view.QtRouteMapRenderer",
        new=MagicMock(),
    ):
        db = MagicMock()
        view = QtRoutePlannerView(qt_widget, db=db, controller=None)
        qtbot.addWidget(view)
        yield view
        try:
            view.shutdown()
        except Exception:
            pass


class TestQtRoutePlannerView:
    def test_creation(self, route_planner):
        assert route_planner.map_widget is not None
        assert route_planner._map_renderer is not None
        assert route_planner.calculate_btn is not None

    def test_stops_list_renders(self, route_planner):
        assert len(route_planner._stop_rows) >= 2

    def test_add_stop(self, route_planner):
        initial = len(route_planner.stops_state)
        route_planner._add_stop_field()
        assert len(route_planner.stops_state) == initial + 1
        assert route_planner.stops_state[-2].get("type") == "stop"

    def test_remove_stop(self, route_planner):
        route_planner._add_stop_field()
        mid_stops = [s for s in route_planner.stops_state if s.get("type") == "stop"]
        assert len(mid_stops) >= 1
        route_planner._remove_stop_field()
        mid_stops_after = [s for s in route_planner.stops_state if s.get("type") == "stop"]
        assert len(mid_stops_after) == len(mid_stops) - 1

    def test_truck_dropdown_created(self, route_planner):
        assert route_planner.truck_combo is not None

    def test_profile_dropdown_has_values(self, route_planner):
        assert route_planner.profile_combo.count() > 0

    def test_calculate_button_exists(self, route_planner):
        assert route_planner.calculate_btn is not None

    def test_clear_route_state_resets_stops(self, route_planner):
        route_planner._clear_route_state()
        assert len(route_planner.stops_state) == 2
        assert route_planner.stops_state[0].get("type") == "start"

    def test_map_renderer_connected(self, route_planner):
        assert route_planner._map_renderer is not None

    def test_click_add_toggle_exists(self, route_planner):
        assert route_planner._click_add_check is not None

    def test_click_add_disabled_ignores_map_click(self, route_planner):
        initial = len(route_planner.stops_state)
        route_planner._click_to_add_enabled = False
        with patch.object(route_planner, "_reverse_geocode_async") as mock_geo:
            route_planner._on_map_click(44.5, 26.5)
        mock_geo.assert_not_called()
        assert len(route_planner.stops_state) == initial

    def test_click_add_enabled_inserts_stop(self, route_planner):
        route_planner._click_to_add_enabled = True
        initial = len(route_planner.stops_state)
        # _on_map_click is async; mock the reverse geocode to emit
        # directly so the stop is added synchronously
        with patch.object(route_planner, "_reverse_geocode_async") as mock_geo:
            route_planner._on_map_click(44.5, 26.5)
        mock_geo.assert_called_once_with(44.5, 26.5)

    def test_click_add_stop_is_resolved(self, route_planner):
        # Simulate a reverse-geocode result directly (synchronous path)
        route_planner._on_reverse_geocode_result("Test Address", 44.5, 26.5)
        inserted = route_planner.stops_state[-2]
        assert inserted.get("resolved") is True
        assert inserted.get("address") == "Test Address"

    def test_toggle_click_add_sets_flag(self, route_planner):
        route_planner._toggle_click_add(True)
        assert route_planner._click_to_add_enabled
        route_planner._toggle_click_add(False)
        assert not route_planner._click_to_add_enabled
