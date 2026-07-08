"""Tests for the client manager view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def client_manager(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.client_manager.QtClientManager._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.client_manager", fromlist=["QtClientManager"]).QtClientManager(
        qt_widget, db=db, prefs=prefs, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtClientManager:
    def test_creation(self, client_manager):
        assert client_manager.db is not None

    def test_client_table_created(self, client_manager):
        assert hasattr(client_manager, "_client_table")

    def test_add_button_exists(self, client_manager):
        assert hasattr(client_manager, "_btn_add")

    def test_search_bar_exists(self, client_manager):
        assert hasattr(client_manager, "_search_input")

    def test_shutdown_cleanup(self, client_manager):
        client_manager.shutdown()

    def test_wakeup_does_not_crash(self, client_manager):
        client_manager.wakeup()
