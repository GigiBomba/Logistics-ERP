"""Tests for the client activity timeline widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtClientActivityTimeline:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.client_activity_timeline import QtClientActivityTimeline
        timeline = QtClientActivityTimeline(qt_widget)
        qtbot.addWidget(timeline)

    def test_set_client_id(self, qt_widget, qtbot):
        from ui.widgets.client_activity_timeline import QtClientActivityTimeline
        timeline = QtClientActivityTimeline(qt_widget)
        qtbot.addWidget(timeline)
        timeline.set_client_id(1)

    def test_refresh(self, qt_widget, qtbot):
        from ui.widgets.client_activity_timeline import QtClientActivityTimeline
        timeline = QtClientActivityTimeline(qt_widget)
        qtbot.addWidget(timeline)
        timeline.refresh()
