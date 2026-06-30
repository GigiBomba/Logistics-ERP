"""Tests for the PySide6 analytics dashboard."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ui.views.analytics import QtAnalyticsView


@pytest.fixture
def analytics_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.analytics.QtAnalyticsView._on_tab_changed",
        lambda self, idx: None,
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
        assert analytics_view._tab_widget is not None
        assert analytics_view._tab_widget.count() == 6

    def test_tab_labels(self, analytics_view):
        texts = [analytics_view._tab_widget.tabText(i) for i in range(6)]
        assert len(texts) == 6
        assert all(len(t) > 0 for t in texts)

    def test_wakeup_does_not_invalidate_cache(self, analytics_view):
        """``wakeup`` must NOT invalidate the service cache.

        The chart-render lifecycle was rewritten so the analytics
        view keeps its rendered ``QPixmap`` objects across
        view-switches.  The service cache is preserved so the
        lightweight data queries (KPIs, status distributions) reuse
        the previous result.  ``invalidate`` is now only called from
        the explicit ↻ refresh button — see
        ``_on_explicit_refresh``.
        """
        analytics_view._svc = MagicMock()
        analytics_view.wakeup()
        analytics_view._svc.invalidate.assert_not_called()

    def test_explicit_refresh_invalidates_cache(self, analytics_view):
        """The ↻ refresh button must invalidate the service cache
        and force a re-render of the current tab."""
        analytics_view._svc = MagicMock()
        analytics_view._on_explicit_refresh()
        analytics_view._svc.invalidate.assert_called_once()

    def test_shutdown_cleanup(self, analytics_view):
        analytics_view._tabs = {}
        analytics_view.shutdown()
        assert analytics_view._tabs == {}
