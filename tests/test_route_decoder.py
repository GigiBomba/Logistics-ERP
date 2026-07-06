"""Tests for route_decoder.decode_polyline."""

from __future__ import annotations

import pytest

from services.route_decoder import decode_polyline


class TestDecodePolyline:
    """Tests for the polyline decoder."""

    def test_empty_string_returns_empty_list(self):
        assert decode_polyline("") == []

    def test_none_returns_empty_list(self):
        """None is falsy, so the early return triggers returning []."""
        assert decode_polyline(None) == []  # type: ignore[arg-type]

    def test_known_polyline_precision_5(self):
        """Known polyline _p~iF~ps|U decodes to a single point near (38.5, -120.2)."""
        result = decode_polyline("_p~iF~ps|U", precision=5)
        assert len(result) == 1
        lat, lon = result[0]
        assert lat == pytest.approx(38.5, abs=1e-4)
        assert lon == pytest.approx(-120.2, abs=1e-4)

    def test_simple_polyline_two_coordinates(self):
        """A longer polyline with multiple points."""
        result = decode_polyline("_p~iF~ps|U_ulLnnqC", precision=5)
        assert len(result) == 2
        # First point
        assert result[0][0] == pytest.approx(38.5, abs=1e-4)
        assert result[0][1] == pytest.approx(-120.2, abs=1e-4)
        # Second point (delta from first)
        assert result[1][0] == pytest.approx(40.7, abs=1e-4)
        assert result[1][1] == pytest.approx(-120.95, abs=1e-4)

    def test_precision_parameter(self):
        """Changing precision affects the coordinate scaling."""
        result = decode_polyline("_p~iF~ps|U", precision=6)
        assert len(result) == 1
        lat, lon = result[0]
        assert lat == pytest.approx(3.85, abs=1e-5)
        assert lon == pytest.approx(-12.02, abs=1e-5)

    def test_invalid_input_raises_value_error(self):
        """Garbage string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid encoded polyline string"):
            # A string with characters that start a coordinate but end abruptly
            decode_polyline("_p~iF")

    def test_partial_garbage_raises_value_error(self):
        """Partially valid then garbage should raise."""
        with pytest.raises(ValueError):
            decode_polyline("_p~iF~ps|U_invalid_garbage")

    def test_encoding_preserves_coordinate_order(self):
        """Coordinates are decoded in the order they were encoded."""
        result = decode_polyline("_p~iF~ps|U_ulLnnqC", precision=5)
        assert len(result) == 2
        # Points should be sequential (lat increasing)
        lats = [p[0] for p in result]
        assert lats == sorted(lats), "latitudes should be monotonically increasing for this route"

    def test_high_precision(self):
        """Higher precision (e.g. 6) is supported."""
        points = decode_polyline("_p~iF~ps|U_ulLnnqC", precision=6)
        assert len(points) == 2
        # Just verify they decode without error and values are smaller scale
        assert all(abs(p[0]) < 100 for p in points)

    def test_single_character_invalid(self):
        """Too few characters to decode a full coordinate."""
        with pytest.raises(ValueError):
            decode_polyline("a")

    def test_odd_number_of_chunks_incomplete(self):
        """Incomplete coordinate (lon missing) raises error."""
        with pytest.raises(ValueError):
            # A valid lat group followed by truncated lon
            decode_polyline("_p~iF~ps")
