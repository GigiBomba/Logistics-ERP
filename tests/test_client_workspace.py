"""Tests for the client workspace view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def client_workspace(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.client_workspace.QtClientWorkspace._load_clients",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.client_workspace", fromlist=["QtClientWorkspace"]).QtClientWorkspace(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtClientWorkspace:
    def test_creation(self, client_workspace):
        assert client_workspace.db is not None

    def test_client_table_created(self, client_workspace):
        assert hasattr(client_workspace, "_client_table")

    def test_search_bar_created(self, client_workspace):
        assert hasattr(client_workspace, "_search_input")

    def test_detail_tabs_created(self, client_workspace):
        assert hasattr(client_workspace, "_detail_tabs")
        assert client_workspace._detail_tabs.count() >= 3

    def test_kpi_cards_created(self, client_workspace):
        assert hasattr(client_workspace, "_kpi_total_trips")

    def test_add_client_button_exists(self, client_workspace):
        assert hasattr(client_workspace, "_btn_add")

    def test_shutdown_cleanup(self, client_workspace):
        client_workspace.shutdown()

    def test_wakeup_does_not_crash(self, client_workspace):
        client_workspace.wakeup()
