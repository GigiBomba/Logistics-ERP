"""Tests: login → dashboard (overview) navigation (Stage 13.1).

Uses the same mock-heavy patterns as ``tests/test_main_window.py`` to
create a ``MainWindow`` with patched services and mock view factories.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def main_window(qtbot, monkeypatch):
    """Create ``MainWindow`` with all services and UI construction mocked.

    * ``_init_services`` → no-op
    * ``_init_fuel_status`` → no-op
    * ``_build_ui`` → no-op (avoids building real ``AppShell`` / nav)
    * ``_start_warmup`` → no-op (avoids creating all view modules on init)
    * ``_VIEW_FACTORIES`` entries return ``MagicMock()`` widgets

    A mock ``app_shell`` with a ``MagicMock`` ``view_container`` is
    attached so that ``_switch_module`` / ``_create_module`` work without
    instantiating real Qt widgets.
    """
    # ── Patch unsafe init methods ────────────────────────────────────
    monkeypatch.setattr("ui.main_window.MainWindow._init_services", lambda self: None)
    monkeypatch.setattr(
        "ui.main_window.MainWindow._init_fuel_status", lambda self: None
    )
    monkeypatch.setattr("ui.main_window.MainWindow._build_ui", lambda self: None)
    monkeypatch.setattr("ui.main_window.MainWindow._start_warmup", lambda self: None)

    # ── Mock AppShell ────────────────────────────────────────────────
    mock_app_shell = MagicMock()
    mock_app_shell.view_container = MagicMock()
    mock_app_shell.view_container.addWidget = MagicMock()
    mock_app_shell.view_container.setCurrentWidget = MagicMock()
    mock_app_shell.set_breadcrumb = MagicMock()
    mock_app_shell.top_bar = MagicMock()
    mock_app_shell.nav = MagicMock()
    mock_app_shell.nav.highlight = MagicMock()

    patcher_appshell = patch("ui.main_window.AppShell", return_value=mock_app_shell)
    patcher_appshell.start()

    patcher_eb = patch("ui.main_window.EventBus", return_value=MagicMock())
    patcher_eb.start()

    patchers = [
        patch("ui.main_window.Config"),
        patch("ui.main_window.QWidgetShortcut"),
    ]
    for p in patchers:
        p.start()

    from ui.main_window import MainWindow

    # ── Mock view factories ──────────────────────────────────────────
    # All views are MagicMock objects so _create_module never
    # instantiates real Qt widgets with mocked dependencies.
    MainWindow._VIEW_FACTORIES = {
        "overview": lambda: MagicMock(),
    }

    widget = MainWindow(
        db=MagicMock(),
        api=MagicMock(),
        prefs=MagicMock(),
        ops=MagicMock(),
        api_client=MagicMock(),
    )

    # Attach services that _init_services would normally provide
    widget.trip_service = MagicMock()
    widget.client_service = MagicMock()
    widget.fleet_service = MagicMock()
    widget._fuel_service = MagicMock()

    # Attach mock shell / nav directly (since _build_ui was skipped)
    widget.app_shell = mock_app_shell
    widget.nav = mock_app_shell.nav

    # Replace page animation (it calls real Qt methods on the frame
    # which is a MagicMock in this fixture).
    monkeypatch.setattr(
        "ui.main_window.MainWindow._animate_page_switch",
        lambda self, frame: None,
    )

    qtbot.addWidget(widget)
    yield widget

    with contextlib.suppress(Exception):
        widget.close()
    for p in patchers:
        p.stop()
    patcher_appshell.stop()
    patcher_eb.stop()


class TestLoginToDashboard:
    """Login → dashboard (overview) navigation tests."""

    # ── Test 1: switching creates and caches the view ────────────────

    def test_switch_to_overview_creates_view(self, main_window):
        """``_switch_module("overview")`` creates the view and caches it."""
        main_window._switch_module("overview")

        assert main_window._active_module == "overview"
        assert "overview" in main_window._module_cache
        cache = main_window._module_cache["overview"]
        assert cache is not None
        assert cache.get("obj") is not None
        assert cache.get("frame") is not None

    # ── Test 2: wakeup is called on the view object ──────────────────

    def test_overview_view_wakeup_refreshes_data(self, main_window):
        """After switching to overview, ``wakeup()`` is called on the view."""
        main_window._switch_module("overview")

        obj = main_window._module_cache["overview"]["obj"]
        # ``_switch_module`` calls ``wakeup`` on the view object after
        # it has been created and added to the container.
        obj.wakeup.assert_called_once()

    # ── Test 3: UI elements are placed in view_container ─────────────

    def test_overview_view_shows_ui_elements(self, main_window):
        """After switching, the overview frame lives in ``view_container``."""
        main_window._switch_module("overview")

        cache = main_window._module_cache["overview"]
        frame = cache["frame"]

        # ``_create_module`` calls ``view_container.addWidget(frame)``
        main_window.app_shell.view_container.addWidget.assert_called_with(frame)
