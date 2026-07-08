"""Tests for the plotly theme configuration."""
from __future__ import annotations
import pytest

class TestPlotlyTheme:
    def test_theme_importable(self):
        from ui.plotly_theme import PLOTLY_THEME
        assert PLOTLY_THEME is not None

    def test_theme_colors_defined(self):
        from ui.plotly_theme import PLOTLY_THEME
        assert "colors" in PLOTLY_THEME or hasattr(PLOTLY_THEME, "colors")

    def test_theme_can_be_applied(self):
        import plotly.io as pio
        from ui.plotly_theme import PLOTLY_THEME
        pio.templates["operion"] = PLOTLY_THEME
        assert "operion" in pio.templates
