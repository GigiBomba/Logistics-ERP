"""A1 regression tests: api_dashboard_view must offload HTTP to the WorkerPool,
guard against overlapping polls, and update status cards in place (no teardown).
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from PySide6.QtTest import QTest


@pytest.fixture
def dashboard(qapp, qtbot):
    """A QtApiDashboardView with a mocked api client (no real network)."""
    from ui.views.api_dashboard_view import QtApiDashboardView

    mock_api = MagicMock()
    mock_api.is_online.return_value = False
    view = QtApiDashboardView(api_client=mock_api)
    qtbot.addWidget(view)
    view._refresh_timer.stop()
    # Wait for the construction-triggered async refresh to settle so the
    # in-flight guard (_refreshing) is clear before a test calls _refresh_status.
    qtbot.waitUntil(lambda: view._refreshing is False, timeout=5000)
    yield view
    view.shutdown()


def test_network_dispatched_off_calling_thread(dashboard, qtbot):
    """is_online/health_check must run on a worker thread, not the caller's."""
    main_tid = threading.get_ident()
    seen: dict = {}

    def fake_is_online():
        seen["is_online"] = threading.get_ident()
        return True

    def fake_health():
        seen["health"] = threading.get_ident()
        return {"database": "ok", "version": "1.2.3"}

    dashboard._api.is_online = fake_is_online
    dashboard._api.health_check = fake_health

    dashboard._refresh_status()

    # Immediately after scheduling, the network call must not have run
    # synchronously on the main thread.
    assert seen.get("is_online") is None or seen["is_online"] != main_tid

    qtbot.waitUntil(lambda: "is_online" in seen, timeout=5000)
    qtbot.waitUntil(lambda: "health" in seen, timeout=5000)
    assert seen["is_online"] != main_tid
    assert seen["health"] != main_tid


def test_refresh_skipped_when_in_flight(dashboard, qtbot):
    """A second poll while one is in flight must be skipped (no overlap)."""
    calls: list = []
    started = threading.Event()
    release = threading.Event()

    def fake_is_online():
        calls.append(threading.get_ident())
        started.set()
        release.wait(5)
        return True

    def fake_health():
        return {"database": "ok", "version": "1.2.3"}

    dashboard._api.is_online = fake_is_online
    dashboard._api.health_check = fake_health

    dashboard._refresh_status()
    assert started.wait(5)  # first poll actually started
    dashboard._refresh_status()  # should be skipped (already in flight)
    release.set()
    qtbot.waitUntil(lambda: dashboard._refreshing is False, timeout=5000)
    assert len(calls) == 1


def test_refresh_updates_cards_in_place(dashboard, qtbot):
    """A second refresh updates the SAME card widget instead of recreating it."""
    dashboard._api.is_online = lambda: True
    dashboard._api.health_check = lambda: {"database": "ok", "version": "1.2.3"}

    dashboard._refresh_status()
    qtbot.waitUntil(lambda: (0, 0) in dashboard._status_cards, timeout=5000)
    qtbot.waitUntil(lambda: (1, 0) in dashboard._status_cards, timeout=5000)

    api_card = dashboard._status_cards[(0, 0)]
    dashboard._refresh_status()
    qtbot.waitUntil(lambda: dashboard._refreshing is False, timeout=5000)
    # The card object must be preserved (updated in place, not recreated).
    assert dashboard._status_cards[(0, 0)] is api_card
