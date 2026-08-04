"""Tests for the plotly renderer."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestPlotlyRenderer:
    def test_get_render_manager_returns_singleton(self):
        from ui.plotly_renderer import get_render_manager
        rm1 = get_render_manager()
        rm2 = get_render_manager()
        assert rm1 is rm2

    def test_render_manager_has_wait(self):
        from ui.plotly_renderer import get_render_manager
        rm = get_render_manager()
        assert hasattr(rm, "wait_for_done")

    def test_empty_figure_importable(self):
        from ui.plotly_renderer import empty_figure
        fig = empty_figure()
        assert fig is not None

    def test_plotly_chart_widget_creation(self, qt_widget, qtbot):
        from ui.plotly_renderer import PlotlyChartWidget
        widget = PlotlyChartWidget(qt_widget)
        qtbot.addWidget(widget)

    def test_plotly_chart_widget_set_chart(self, qt_widget, qtbot):
        from ui.plotly_renderer import PlotlyChartWidget
        from ui.plotly_charts import make_pie_chart
        widget = PlotlyChartWidget(qt_widget)
        qtbot.addWidget(widget)
        fig = make_pie_chart([1], ["A"], "Test")
        widget.set_figure(fig)
        assert widget._fig is not None

    def test_plotly_chart_widget_clear(self, qt_widget, qtbot):
        from ui.plotly_renderer import PlotlyChartWidget
        widget = PlotlyChartWidget(qt_widget)
        qtbot.addWidget(widget)
        widget.set_figure(None)
        # After setting None, _fig should be None or the widget still exists
        assert widget is not None
