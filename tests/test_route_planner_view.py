"""Tests for the route planner view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def route_planner(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.route_planner_view.QtRoutePlannerView._rebuild_ui",
        lambda self: None,
    )
    db = MagicMock()
    controller = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.route_planner_view", fromlist=["QtRoutePlannerView"]).QtRoutePlannerView(
        qt_widget, db=db, controller=controller, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtRoutePlannerView:
    def test_creation(self, route_planner):
        assert route_planner.db is not None
        assert route_planner.controller is not None

    def test_stop_list_created(self, route_planner):
        assert hasattr(route_planner, "_stops_container")

    def test_map_widget_created(self, route_planner):
        assert hasattr(route_planner, "map_widget")

    def test_calculate_button_exists(self, route_planner):
        assert hasattr(route_planner, "_btn_calculate")

    def test_shutdown_cleanup(self, route_planner):
        route_planner._stops = [{"address": "A"}]
        route_planner.shutdown()
        assert route_planner._stops == []

    def test_wakeup_does_not_crash(self, route_planner):
        route_planner.wakeup()

    def test_controller_provided(self, route_planner):
        assert route_planner.controller == route_planner.controller
