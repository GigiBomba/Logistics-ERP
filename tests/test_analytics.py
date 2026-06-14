"""Tests for the PySide6 analytics dashboard."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ui.views.analytics_view import QtAnalyticsView


@pytest.fixture
def analytics_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.analytics_view.QtAnalyticsView._load_data",
        lambda self: None,
    )
    db = MagicMock()
    view = QtAnalyticsView(qt_widget, db=db, prefs=None)
    qtbot.addWidget(view)
    yield view
    try:
        view.shutdown()
    except Exception:
        pass


class TestQtAnalyticsView:
    def test_creation(self, analytics_view):
        assert analytics_view._period_lbl is not None
        assert analytics_view._chart_container is not None

    def test_period_navigation(self, analytics_view):
        initial_month = analytics_view._month
        analytics_view._prev_month()
        if initial_month == 1:
            assert analytics_view._month == 12
        else:
            assert analytics_view._month == initial_month - 1

    def test_next_month(self, analytics_view):
        initial_month = analytics_view._month
        analytics_view._next_month()
        if initial_month == 12:
            assert analytics_view._month == 1
        else:
            assert analytics_view._month == initial_month + 1

    def test_filter_widgets_exist(self, analytics_view):
        assert analytics_view._from_date is not None
        assert analytics_view._to_date is not None
        assert analytics_view._period_lbl.text() != ""

    def test_period_label_updates(self, analytics_view):
        analytics_view._year = 2024
        analytics_view._month = 3
        analytics_view._update_period_label()
        assert "2024" in analytics_view._period_lbl.text()
