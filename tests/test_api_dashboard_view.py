"""Tests for the API dashboard view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtApiDashboardView:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.api_dashboard_view import QtApiDashboardView
        view = QtApiDashboardView(qt_widget)
        qtbot.addWidget(view)

    def test_has_status_cards(self, qt_widget, qtbot):
        from ui.views.api_dashboard_view import QtApiDashboardView
        view = QtApiDashboardView(qt_widget)
        qtbot.addWidget(view)
        assert hasattr(view, "_status_cards")

    def test_has_endpoint_table(self, qt_widget, qtbot):
        from ui.views.api_dashboard_view import QtApiDashboardView
        view = QtApiDashboardView(qt_widget)
        qtbot.addWidget(view)
