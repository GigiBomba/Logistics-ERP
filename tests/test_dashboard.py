"""Tests for the dashboard view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def dashboard(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.dashboard.QtDashboardView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.dashboard", fromlist=["QtDashboardView"]).QtDashboardView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtDashboardView:
    def test_creation(self, dashboard):
        assert dashboard.db is not None

    def test_stats_section_created(self, dashboard):
        assert hasattr(dashboard, "_stat_cards")

    def test_charts_section_created(self, dashboard):
        assert hasattr(dashboard, "_chart_revenue")

    def test_recent_activity_section(self, dashboard):
        assert hasattr(dashboard, "_recent_table")

    def test_shutdown_cleanup(self, dashboard):
        dashboard.shutdown()

    def test_wakeup_does_not_crash(self, dashboard):
        dashboard.wakeup()
