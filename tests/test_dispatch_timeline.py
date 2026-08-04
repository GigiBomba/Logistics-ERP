"""Tests for the dispatch timeline widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtDispatchTimeline:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.dispatch_timeline import QtDispatchTimeline
        timeline = QtDispatchTimeline(qt_widget)
        qtbot.addWidget(timeline)

    def test_set_trips(self, qt_widget, qtbot):
        from ui.widgets.dispatch_timeline import QtDispatchTimeline
        timeline = QtDispatchTimeline(qt_widget)
        qtbot.addWidget(timeline)
        trips = [
            {"id": 1, "client": "Test Co", "start_date": "2026-01-01", "truck": "AG01ABC"},
        ]
        timeline.refresh(trips)

    def test_clear(self, qt_widget, qtbot):
        from ui.widgets.dispatch_timeline import QtDispatchTimeline
        timeline = QtDispatchTimeline(qt_widget)
        qtbot.addWidget(timeline)
        timeline.refresh([])
