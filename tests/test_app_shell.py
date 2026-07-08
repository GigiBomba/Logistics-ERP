"""Tests for the application shell."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestAppShell:
    def test_creation(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell
        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        assert app_shell.top_bar is not None
        assert app_shell.nav is not None
        assert app_shell.view_container is not None

    def test_set_breadcrumb(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell
        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.set_breadcrumb("Dashboard")
        assert app_shell.top_bar._breadcrumb_label.text() == "Dashboard"

    def test_set_fuel_status(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell
        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.set_fuel_status("1.85 RON/L")

    def test_set_alert_count(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell
        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.set_alert_count(3)

    def test_destroy_cleanup(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell
        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.destroy()
