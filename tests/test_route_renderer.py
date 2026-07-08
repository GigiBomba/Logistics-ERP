"""Tests for the route renderer."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestRouteRenderer:
    def test_creation(self, qt_widget, qtbot):
        from ui.map.route_renderer import RouteRenderer
        renderer = RouteRenderer(qt_widget)
        qtbot.addWidget(renderer)

    def test_set_route_data(self, qt_widget, qtbot):
        from ui.map.route_renderer import RouteRenderer
        renderer = RouteRenderer(qt_widget)
        qtbot.addWidget(renderer)
        route_data = {
            "distance_km": 500,
            "duration_h": 6.5,
            "geometry": "encoded_polyline",
            "stops": [{"lat": 44.4, "lng": 26.1}, {"lat": 46.7, "lng": 23.6}],
        }
        renderer.set_route_data(route_data)

    def test_clear(self, qt_widget, qtbot):
        from ui.map.route_renderer import RouteRenderer
        renderer = RouteRenderer(qt_widget)
        qtbot.addWidget(renderer)
        renderer.clear()
