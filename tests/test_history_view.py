"""Tests for the history view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def history_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.history_view.QtHistoryView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    controller = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.history_view", fromlist=["QtHistoryView"]).QtHistoryView(
        qt_widget, db=db, controller=controller, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtHistoryView:
    def test_creation(self, history_view):
        assert history_view.db is not None

    def test_trip_table_created(self, history_view):
        assert hasattr(history_view, "_trip_table")

    def test_date_filters_exist(self, history_view):
        assert hasattr(history_view, "_date_from")

    def test_search_bar_exists(self, history_view):
        assert hasattr(history_view, "_search_input")

    def test_export_button_exists(self, history_view):
        assert hasattr(history_view, "_btn_export")

    def test_shutdown_cleanup(self, history_view):
        history_view.shutdown()

    def test_wakeup_does_not_crash(self, history_view):
        history_view.wakeup()
