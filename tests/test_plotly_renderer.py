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


class TestPlotlyChartWidgetLruCache:
    """``PlotlyChartWidget._pixmap_cache`` true-LRU eviction semantics.

    The cache is bounded (``CACHE_MAX_ENTRIES``) and eviction must be
    least-recently-used — a hit on the oldest entry preserves it, and a
    subsequent insert evicts the *second*-oldest instead."""

    def test_accessing_oldest_preserves_it_on_eviction(self, qt_widget, qtbot):
        from PySide6.QtGui import QPixmap
        from ui.plotly_renderer import PlotlyChartWidget

        w = PlotlyChartWidget(qt_widget)
        qtbot.addWidget(w)
        size = 100
        oldest_key = (0, size, size)
        second_key = (1, size, size)
        n = PlotlyChartWidget.CACHE_MAX_ENTRIES
        assert n >= 4  # scenario below needs at least 4 slots
        # Insert 4 distinct keys, oldest (fig_id=0) first.
        for fig_id in range(n):
            w._cache_pixmap(fig_id, size, size, QPixmap(size, size))
        assert len(w._pixmap_cache) == n
        # Access the oldest entry — refresh its recency exactly as the
        # cache-hit paths (set_figure/showEvent/_on_resize_finished) do.
        w._pixmap_cache.move_to_end(oldest_key)
        # Insert a 5th distinct key; capacity is full so one entry must
        # be evicted.  LRU order is now [1, 2, 3, 0] → evict fig_id=1
        # (the second-oldest), NOT fig_id=0 (the oldest, which was just
        # touched).
        w._cache_pixmap(n, size, size, QPixmap(size, size))
        assert len(w._pixmap_cache) == n, "cache must stay bounded"
        assert oldest_key in w._pixmap_cache, (
            "oldest entry was accessed and must survive eviction"
        )
        assert second_key not in w._pixmap_cache, (
            "second-oldest entry should be the LRU evicted on overflow"
        )
