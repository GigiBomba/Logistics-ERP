"""Tests for the charts bridge module."""
from __future__ import annotations
import pytest

class TestCharts:
    def test_module_importable(self):
        from ui import charts
        assert charts is not None

    def test_exports_plotly_functions(self):
        from ui.charts import DEFAULT_THEME
        assert DEFAULT_THEME is not None
