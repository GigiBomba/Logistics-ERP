"""Tests for the service timeline widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtServiceTimelineWidget:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.service_timeline_widget import QtServiceTimelineWidget
        widget = QtServiceTimelineWidget(qt_widget)
        qtbot.addWidget(widget)

    def test_set_events(self, qt_widget, qtbot):
        from ui.widgets.service_timeline_widget import QtServiceTimelineWidget
        widget = QtServiceTimelineWidget(qt_widget)
        qtbot.addWidget(widget)
        events = [
            {"date": "2026-01-01", "description": "Oil change", "type": "maintenance"},
            {"date": "2026-03-15", "description": "Tire rotation", "type": "maintenance"},
        ]
        widget.set_events(events)

    def test_clear(self, qt_widget, qtbot):
        from ui.widgets.service_timeline_widget import QtServiceTimelineWidget
        widget = QtServiceTimelineWidget(qt_widget)
        qtbot.addWidget(widget)
        widget.clear()
