"""Tests for the client revenue chart widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtClientRevenueChart:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.client_revenue_chart import QtClientRevenueChart
        chart = QtClientRevenueChart(qt_widget)
        qtbot.addWidget(chart)

    def test_set_client_id(self, qt_widget, qtbot):
        from ui.widgets.client_revenue_chart import QtClientRevenueChart
        chart = QtClientRevenueChart(qt_widget)
        qtbot.addWidget(chart)
        chart.set_client_id(1)

    def test_refresh(self, qt_widget, qtbot):
        from ui.widgets.client_revenue_chart import QtClientRevenueChart
        chart = QtClientRevenueChart(qt_widget)
        qtbot.addWidget(chart)
        chart.refresh()
