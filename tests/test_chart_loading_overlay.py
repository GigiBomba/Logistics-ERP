"""Tests for the chart loading overlay widget."""
from __future__ import annotations
import pytest

class TestChartLoadingOverlay:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay
        overlay = ChartLoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)

    def test_show_hide(self, qt_widget, qtbot):
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay
        overlay = ChartLoadingOverlay(qt_widget)
        qtbot.addWidget(overlay)
        overlay.show()
        assert overlay.isVisible()
        overlay.hide()
        assert not overlay.isVisible()

    def test_set_message(self, qt_widget, qtbot):
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay
        overlay = ChartLoadingOverlay(qt_widget, message="Loading charts...")
        qtbot.addWidget(overlay)
