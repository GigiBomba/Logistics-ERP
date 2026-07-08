"""Tests for the route history view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def route_history(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.route_history_view.QtRouteHistoryView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    controller = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.route_history_view", fromlist=["QtRouteHistoryView"]).QtRouteHistoryView(
        qt_widget, db=db, controller=controller, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtRouteHistoryView:
    def test_creation(self, route_history):
        assert route_history.db is not None

    def test_route_table_created(self, route_history):
        assert hasattr(route_history, "_route_table")

    def test_search_bar_exists(self, route_history):
        assert hasattr(route_history, "_search_input")

    def test_date_filters_exist(self, route_history):
        assert hasattr(route_history, "_date_from")

    def test_shutdown_cleanup(self, route_history):
        route_history.shutdown()

    def test_wakeup_does_not_crash(self, route_history):
        route_history.wakeup()

    def test_replay_button_exists(self, route_history):
        assert hasattr(route_history, "_btn_replay")
