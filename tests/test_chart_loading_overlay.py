"""Tests for the chart loading overlay widget."""
from __future__ import annotations
import pytest

class TestChartLoadingOverlay:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay
        overlay = ChartLoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)
        assert overlay is not None

    def test_show_hide(self, qt_widget, qtbot):
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay
        overlay = ChartLoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)
        overlay.setVisible(True)
        qtbot.wait(10)
        overlay.setVisible(False)
        qtbot.wait(10)
        assert not overlay.isVisible()

    def test_set_progress(self, qt_widget, qtbot):
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay
        overlay = ChartLoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)
        overlay.set_progress(3, 10)
        assert overlay._expected == 10
        assert overlay._received == 3
