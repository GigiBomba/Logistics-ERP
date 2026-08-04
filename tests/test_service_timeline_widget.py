"""Tests for the service timeline widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def service_mock():
    srv = MagicMock()
    srv.get_history.return_value = []
    srv.format_date.side_effect = lambda d, *a: str(d)
    return srv

class TestQtServiceTimelineWidget:
    def test_creation(self, qt_widget, qtbot, service_mock):
        from ui.widgets.service_timeline_widget import QtServiceTimelineWidget
        widget = QtServiceTimelineWidget(qt_widget, service=service_mock, truck_id=1, truck_plate="AB123CD")
        qtbot.addWidget(widget)
        assert widget is not None

    def test_set_events(self, qt_widget, qtbot, service_mock):
        from ui.widgets.service_timeline_widget import QtServiceTimelineWidget
        widget = QtServiceTimelineWidget(qt_widget, service=service_mock, truck_id=1, truck_plate="AB123CD")
        qtbot.addWidget(widget)
        # refresh() loads from the service mock
        widget.refresh()
        assert widget is not None

    def test_clear(self, qt_widget, qtbot, service_mock):
        from ui.widgets.service_timeline_widget import QtServiceTimelineWidget
        widget = QtServiceTimelineWidget(qt_widget, service=service_mock, truck_id=1, truck_plate="AB123CD")
        qtbot.addWidget(widget)
        # _clear_scroll() clears the scroll area content
        widget._clear_scroll()
        assert widget is not None
