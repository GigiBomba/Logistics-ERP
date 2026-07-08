"""Tests for the overview dashboard view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def overview_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.overview_view.QtOverviewView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.overview_view", fromlist=["QtOverviewView"]).QtOverviewView(
        qt_widget, db=db, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtOverviewView:
    def test_creation(self, overview_view):
        assert overview_view.db is not None

    def test_kpi_cards_created(self, overview_view):
        assert hasattr(overview_view, "_card_active_trips")

    def test_charts_created(self, overview_view):
        assert hasattr(overview_view, "_chart_revenue")

    def test_recent_activity_section(self, overview_view):
        assert hasattr(overview_view, "_recent_trips_table")

    def test_quick_actions_section(self, overview_view):
        assert hasattr(overview_view, "_btn_new_route")

    def test_shutdown_cleanup(self, overview_view):
        overview_view.shutdown()

    def test_wakeup_does_not_crash(self, overview_view):
        overview_view.wakeup()

    def test_refresh_timer_stopped_on_shutdown(self, overview_view):
        overview_view.shutdown()
        assert overview_view._refresh_timer is None or not overview_view._refresh_timer.isActive()
