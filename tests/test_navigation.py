"""Navigation integration tests — recent-section clicks and badge refresh.

Covers the Phase 6 nav rework wiring: clicking a recent-section item
navigates through the normal select path, and trip-status / invoice events
trigger a badge refresh on the sidebar (via the event bus).
"""
from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent


@pytest.fixture
def nav_window(qtbot, monkeypatch):
    """MainWindow with mocked services but a REAL EventBus.

    A real event bus lets the nav-badge subscriptions actually fire when
    trip/invoice events are published. ``_init_services``/``_build_ui`` are
    stubbed, and repo mocks are attached so ``_refresh_nav_badges`` has data.
    """
    from ui.main_window import MainWindow
    from services.operations.event_bus import EventBus

    monkeypatch.setattr("ui.main_window.MainWindow._init_services", lambda self: None)
    monkeypatch.setattr("ui.main_window.MainWindow._init_fuel_status", lambda self: None)
    monkeypatch.setattr("ui.main_window.MainWindow._start_warmup", lambda self: None)
    monkeypatch.setattr("ui.main_window.MainWindow._build_ui", lambda self: None)

    app_shell = MagicMock()
    app_shell.view_container = MagicMock()
    app_shell.view_container.addWidget = MagicMock()
    app_shell.view_container.setCurrentWidget = MagicMock()
    app_shell.top_bar = MagicMock()

    ops = MagicMock()
    ops.event_bus = EventBus()
    ops.get_active_alerts.return_value = []
    ops.get_active_alert_count.return_value = 0

    with patch("ui.main_window.AppShell", return_value=app_shell), \
         patch("ui.main_window.Config"), \
         patch("ui.main_window.QWidgetShortcut"):
        widget = MainWindow(
            db=MagicMock(),
            api=MagicMock(),
            prefs=MagicMock(),
            ops=ops,
            api_client=MagicMock(),
        )

    widget.app_shell = app_shell
    widget.nav = MagicMock()
    widget.trip_repo = MagicMock()
    widget.trip_repo.get_active_excluding_statuses.return_value = [{"id": 1}]
    widget.invoice_repo = MagicMock()
    widget.invoice_repo.get_unpaid_with_client_trip_data.return_value = [{"id": 1}, {"id": 2}]

    qtbot.addWidget(widget)
    yield widget

    with contextlib.suppress(Exception):
        widget.close()


class TestRecentSectionNavigation:
    def test_recent_item_click_navigates(self, qt_main_window, qtbot):
        """Clicking a recent section item dispatches through the select path."""
        from ui.widgets.sidebar import Sidebar

        selected = []
        sidebar = Sidebar(
            parent=qt_main_window,
            on_select=lambda k, _: selected.append(k),
            prefs=None,
        )
        qtbot.addWidget(sidebar)
        sidebar.set_recent_items([("analytics", "Analytics")])
        frame = sidebar._recent_frames[0]

        event = MagicMock()
        event.type.return_value = QEvent.MouseButtonPress
        sidebar.eventFilter(frame, event)

        assert selected == ["analytics"]
        # Recent clicks never mark the item active.
        assert sidebar.get_active_key() is None
        sidebar._destroy()


class TestBadgeRefreshOnEvents:
    def test_trip_status_event_refreshes_dispatch_badge(self, nav_window, qtbot):
        """A TRIP_STATUS_CHANGED event re-counts the dispatch_board badge."""
        from services.operations.event_bus import TRIP_STATUS_CHANGED

        nav_window._event_bus.publish(TRIP_STATUS_CHANGED, {"trip_id": 1, "status": "Delivered"})

        qtbot.waitUntil(lambda: nav_window.nav.set_badge.called, timeout=2000)
        calls = {c.args[0]: c.args[1] for c in nav_window.nav.set_badge.call_args_list}
        assert calls["dispatch_board"] == 1
        assert calls["invoices"] == 2

    def test_invoice_event_refreshes_invoice_badge(self, nav_window, qtbot):
        """An INVOICE_PAID event re-counts the invoices badge."""
        from services.operations.event_bus import INVOICE_PAID

        nav_window._event_bus.publish(INVOICE_PAID, {"invoice_id": 1})

        qtbot.waitUntil(lambda: nav_window.nav.set_badge.called, timeout=2000)
        calls = {c.args[0]: c.args[1] for c in nav_window.nav.set_badge.call_args_list}
        assert calls["invoices"] == 2