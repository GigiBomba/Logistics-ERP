"""Tests for the dispatch board view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def dispatch_board(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.dispatch_board_view.QtDispatchBoardView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.event_bus.subscribe = MagicMock(return_value="sub_id")
    ops.event_bus.unsubscribe = MagicMock()
    api_client = MagicMock()
    board = __import__("ui.views.dispatch_board_view", fromlist=["QtDispatchBoardView"]).QtDispatchBoardView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(board)
    yield board
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        board.shutdown()


class TestQtDispatchBoardView:
    def test_creation(self, dispatch_board):
        assert dispatch_board.db is not None
        assert dispatch_board._tabs is not None

    def test_kanban_columns_created(self, dispatch_board):
        assert hasattr(dispatch_board, "_columns")
        assert dispatch_board._columns is not None

    def test_stat_cards_created(self, dispatch_board):
        assert hasattr(dispatch_board, "_status_cards")
        assert dispatch_board._status_cards is not None

    def test_tabs_present(self, dispatch_board):
        assert hasattr(dispatch_board, "_tabs")

    def test_search_bar_created(self, dispatch_board):
        assert hasattr(dispatch_board, "_search_bar")
        assert dispatch_board._search_bar is not None

    def test_shutdown_unsubscribes(self, dispatch_board):
        dispatch_board.shutdown()
        dispatch_board.ops.event_bus.unsubscribe.assert_called()

    def test_wakeup_refreshes(self, dispatch_board):
        dispatch_board._start_load = MagicMock()
        dispatch_board.wakeup()
        dispatch_board._start_load.assert_called_once()
