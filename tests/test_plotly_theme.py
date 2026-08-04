"""Tests for the plotly theme configuration."""
from __future__ import annotations
import pytest

class TestPlotlyTheme:
    def test_theme_importable(self):
        from ui.plotly_theme import create_operion_template
        template = create_operion_template()
        assert template is not None

    def test_theme_colors_defined(self):
        from ui.plotly_theme import create_operion_template
        template = create_operion_template()
        assert template.layout is not None

    def test_theme_can_be_applied(self):
        import plotly.io as pio
        from ui.plotly_theme import create_operion_template
        template = create_operion_template()
        pio.templates["operion"] = template
        assert "operion" in pio.templates
