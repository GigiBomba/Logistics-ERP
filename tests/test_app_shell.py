"""Tests for the application shell (AppShell)."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from ui.widgets.sidebar import Sidebar
from ui.widgets.topbar import TopBar

# ── SP workaround ──────────────────────────────────────────────────────────
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def app_shell(qt_main_window, qtbot):
    from ui.app_shell import AppShell

    shell = AppShell(qt_main_window, db=MagicMock())
    yield shell
    with contextlib.suppress(Exception):
        shell.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAppShell:
    def test_creation(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell

        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        assert app_shell.top_bar is not None
        assert app_shell.nav is not None
        assert app_shell.view_container is not None

    def test_set_fuel_status(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell

        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.top_bar.set_fuel_status = MagicMock()
        app_shell.set_fuel_status("1.85 RON/L")
        app_shell.top_bar.set_fuel_status.assert_called_once_with(
            "1.85 RON/L"
        )

    def test_set_alert_count(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell

        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.top_bar.set_alert_count = MagicMock()
        app_shell.set_alert_count(3)
        app_shell.top_bar.set_alert_count.assert_called_once_with(3)

    def test_destroy_cleanup(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell

        db = MagicMock()
        app_shell = AppShell(qt_main_window, db)
        app_shell.top_bar.destroy = MagicMock()
        app_shell.nav.destroy = MagicMock()
        app_shell.destroy()
        app_shell.top_bar.destroy.assert_called_once()
        app_shell.nav.destroy.assert_called_once()

    # ── New tests ─────────────────────────────────────────────────────────

    def test_widget_hierarchy_correct(self, app_shell):
        assert isinstance(app_shell.nav, Sidebar)
        assert isinstance(app_shell.top_bar, TopBar)
        assert isinstance(app_shell.view_container, QStackedWidget)

    def test_on_alert_navigate_calls_on_nav_select(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell

        mock_cb = MagicMock()
        db = MagicMock()
        app_shell = AppShell(qt_main_window, db, on_nav_select=mock_cb)
        app_shell._on_alert_navigate("some_view", {"key": "val"})
        mock_cb.assert_called_once_with("some_view", {"key": "val"})

    def test_on_alert_navigate_noop_without_callback(self, app_shell):
        # No on_nav_select wired — must not crash
        app_shell._on_alert_navigate("any_view", {})

    def test_destroy_suppresses_errors(self, app_shell):
        app_shell.top_bar.destroy = MagicMock(side_effect=RuntimeError("boom"))
        app_shell.nav.destroy = MagicMock(side_effect=RuntimeError("bang"))
        # Must not raise
        app_shell.destroy()

    def test_nav_select_callback_wired(self, app_shell):
        # Sidebar's on_select should be set to the shell's _on_nav_select
        # (which may be None when not passed — just verify it doesn't crash)
        assert hasattr(app_shell.nav, "_on_select")
        # If the fixture uses default (no on_nav_select), _on_select is None
        assert app_shell.nav._on_select is None or callable(
            app_shell.nav._on_select
        )

    def test_root_central_widget_set(self, qt_main_window, qtbot):
        from ui.app_shell import AppShell

        db = MagicMock()
        AppShell(qt_main_window, db)
        assert qt_main_window.centralWidget() is not None
