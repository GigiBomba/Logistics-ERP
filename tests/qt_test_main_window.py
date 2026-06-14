"""Tests for the PySide6 main window controller."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLabel

from config import Config
from database.db_manager import DatabaseManager
from services.preferences import PreferencesManager
from ui.qt_main_window import MainWindow
from ui.qt_views import QtCalculatorView


@pytest.fixture
def main_window(qtbot, qapp, monkeypatch):
    """Build a MainWindow with a temporary DB and mocked heavy services."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)

    prefs = PreferencesManager(db)
    prefs.load()

    ops = MagicMock()
    ops.start = MagicMock()
    ops.stop = MagicMock()

    # Avoid network calls for fuel prices during tests.
    monkeypatch.setattr(
        "services.fuel_price_service.FuelPriceService.refresh_if_stale",
        lambda self: True,
    )

    Config.ensure_dirs()

    window = MainWindow(db, api=MagicMock(), prefs=prefs, ops=ops)
    qtbot.addWidget(window)
    yield window

    window.close()
    db.conn.close()
    try:
        os.remove(tmp.name)
    except OSError:
        pass


class TestMainWindow:
    def test_creation(self, main_window):
        assert main_window.windowTitle() == Config.APP_NAME
        assert main_window.app_shell is not None
        assert main_window.nav is not None

    def test_initial_module_is_overview(self, main_window):
        assert main_window._active_module == "overview"
        current = main_window.app_shell.view_container.currentWidget()
        assert current is not None

    def test_switch_module_changes_stack(self, main_window, qtbot):
        main_window._switch_module("calculator")
        assert main_window._active_module == "calculator"
        current = main_window.app_shell.view_container.currentWidget()
        assert isinstance(current, QtCalculatorView)

    def test_nav_callback_wired(self, main_window):
        # The nav panel's on_select callback should be MainWindow._switch_module.
        assert main_window.nav._on_select == main_window._switch_module

    def test_shortcuts_exist(self, main_window):
        assert main_window._shortcut_calculate is not None
        assert main_window._shortcut_history is not None

    def test_close_event_stops_services(self, main_window):
        main_window.close()
        assert main_window._fuel_timer.isActive() is False
