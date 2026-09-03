"""A5 regression tests: the 60s fuel status timer must no-op when the fuel
status indicator (window) is not visible, avoiding pointless work/network.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMainWindow


@pytest.fixture
def window(qapp):
    """A plain QMainWindow with the fuel-status method under test bound to it."""
    from ui.main_window import MainWindow

    win = QMainWindow()
    win.app_shell = MagicMock()
    fuel = MagicMock()
    fuel.is_available.return_value = False
    win._fuel_service = fuel
    # Bind the real MainWindow implementation to this bare window so the test
    # exercises the exact method body without constructing the full app shell.
    win._update_fuel_status = MainWindow._update_fuel_status.__get__(
        win, QMainWindow
    )
    win._fuel_status_text = MainWindow._fuel_status_text.__get__(
        win, QMainWindow
    )
    yield win
    win.close()


def test_update_fuel_status_noops_when_hidden(window):
    """Hidden window -> _update_fuel_status must return before any work."""
    window.hide()  # never shown -> isVisible() is False
    window._update_fuel_status()
    window.app_shell.set_fuel_status.assert_not_called()


def test_update_fuel_status_runs_when_visible(window):
    """Visible window -> _update_fuel_status updates the fuel indicator."""
    window.show()
    window._update_fuel_status()
    window.app_shell.set_fuel_status.assert_called_once()