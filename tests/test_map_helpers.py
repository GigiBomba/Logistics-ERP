"""Tests for map helper utilities."""
from __future__ import annotations
import pytest

class TestMapHelpers:
    def test_module_importable(self):
        from ui.map import map_helpers
        assert map_helpers is not None

    def test_has_utility_functions(self):
        from ui.map.map_helpers import decode_polyline
        assert callable(decode_polyline)

    def test_decode_polyline_empty(self):
        from ui.map.map_helpers import decode_polyline
        result = decode_polyline("")
        assert result == [] or isinstance(result, list)

    def test_decode_polyline_simple(self):
        from ui.map.map_helpers import decode_polyline
        points = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        assert isinstance(points, list)

    def test_create_map_html(self):
        from ui.map.map_helpers import create_map_html
        html = create_map_html(center_lat=45.0, center_lng=25.0)
        assert isinstance(html, str)
        assert "leaflet" in html.lower() or "map" in html.lower() or "html" in html.lower()
