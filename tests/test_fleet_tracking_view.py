"""Tests for the fleet tracking view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def fleet_tracking(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.fleet_tracking_view.QtFleetTrackingView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    on_navigate = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.fleet_tracking_view", fromlist=["QtFleetTrackingView"]).QtFleetTrackingView(
        qt_widget, db=db, prefs=prefs, ops=ops,
        on_navigate=on_navigate, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtFleetTrackingView:
    def test_creation(self, fleet_tracking):
        assert fleet_tracking.db is not None

    def test_map_widget_created(self, fleet_tracking):
        assert hasattr(fleet_tracking, "_map_widget")

    def test_truck_list_created(self, fleet_tracking):
        assert hasattr(fleet_tracking, "_truck_list")

    def test_refresh_timer_exists(self, fleet_tracking):
        assert hasattr(fleet_tracking, "_refresh_timer")

    def test_on_navigate_callback(self, fleet_tracking):
        assert fleet_tracking._on_navigate is not None

    def test_shutdown_cleanup(self, fleet_tracking):
        fleet_tracking.shutdown()

    def test_wakeup_does_not_crash(self, fleet_tracking):
        fleet_tracking.wakeup()
