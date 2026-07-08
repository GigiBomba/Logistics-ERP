"""Tests for plotly chart generation functions."""
from __future__ import annotations
import pytest

class TestPlotlyCharts:
    def test_make_pie_chart(self):
        from ui.plotly_charts import make_pie_chart
        labels = ["A", "B", "C"]
        values = [10, 20, 30]
        fig = make_pie_chart(labels, values, title="Test")
        assert fig is not None

    def test_make_line_chart(self):
        from ui.plotly_charts import make_line_chart
        x = [1, 2, 3]
        y = [10, 20, 30]
        fig = make_line_chart(x, y, title="Test")
        assert fig is not None

    def test_make_bar_chart(self):
        from ui.plotly_charts import make_bar_chart
        labels = ["A", "B"]
        values = [10, 20]
        fig = make_bar_chart(labels, values, title="Test")
        assert fig is not None

    def test_make_trend_chart(self):
        from ui.plotly_charts import make_trend_chart
        dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
        values = [100, 150, 200]
        fig = make_trend_chart(dates, values, title="Trend")
        assert fig is not None

    def test_make_sparkline_chart(self):
        from ui.plotly_charts import make_sparkline_chart
        values = [1, 2, 3, 4, 5]
        fig = make_sparkline_chart(values)
        assert fig is not None

    def test_make_waterfall_chart(self):
        from ui.plotly_charts import make_waterfall_chart
        labels = ["Start", "+", "="]
        values = [100, 50, 150]
        fig = make_waterfall_chart(labels, values)
        assert fig is not None

    def test_make_box_plot(self):
        from ui.plotly_charts import make_box_plot
        data = [[1, 2, 3], [4, 5, 6]]
        labels = ["A", "B"]
        fig = make_box_plot(data, labels)
        assert fig is not None

    def test_format_value(self):
        from ui.plotly_charts import _format_value
        assert _format_value(1000) is not None
        assert _format_value(0) is not None

    def test_chart_constants_defined(self):
        from ui.plotly_charts import CHART_FIGSIZE_TILE, CHART_FIGSIZE_WIDE
        assert CHART_FIGSIZE_TILE is not None
        assert CHART_FIGSIZE_WIDE is not None
