"""Tests for the driver manager view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def driver_manager(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.driver_manager.QtDriverManager._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.driver_manager", fromlist=["QtDriverManager"]).QtDriverManager(
        qt_widget, db=db, prefs=prefs, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtDriverManager:
    def test_creation(self, driver_manager):
        assert driver_manager.db is not None

    def test_driver_table_created(self, driver_manager):
        assert hasattr(driver_manager, "_driver_table")

    def test_add_button_exists(self, driver_manager):
        assert hasattr(driver_manager, "_btn_add")

    def test_search_bar_exists(self, driver_manager):
        assert hasattr(driver_manager, "_search_input")

    def test_kpi_cards_created(self, driver_manager):
        assert hasattr(driver_manager, "_kpi_active")

    def test_shutdown_cleanup(self, driver_manager):
        driver_manager.shutdown()

    def test_wakeup_does_not_crash(self, driver_manager):
        driver_manager.wakeup()

    def test_edit_button_exists(self, driver_manager):
        assert hasattr(driver_manager, "_btn_edit")
