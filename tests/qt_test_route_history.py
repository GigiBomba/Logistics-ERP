"""Tests for the PySide6 route history view."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui.qt_views.qt_route_history_view import QtRouteHistoryView


@pytest.fixture
def route_history(qt_widget, qtbot):
    db = MagicMock()
    with patch(
        "ui.qt_map.qt_map_widget.MapWidget",
        side_effect=RuntimeError("test stub"),
    ):
        view = QtRouteHistoryView(qt_widget, db=db, controller=None)
        qtbot.addWidget(view)
        view.service = MagicMock()
        view.service.search_routes.return_value = []
        view.service.get_statistics.return_value = {"total": 0, "active": 0, "archived": 0}
        yield view
        try:
            view.shutdown()
        except Exception:
            pass


class TestQtRouteHistoryView:
    def test_creation(self, route_history):
        assert route_history.table is not None
        assert route_history.e_search is not None

    def test_filter_widgets_exist(self, route_history):
        assert route_history.e_search is not None
        assert route_history.c_profile is not None
        assert route_history.e_truck is not None
        assert route_history._archived_check is not None

    def test_table_has_columns(self, route_history):
        assert route_history.table.columnCount() > 0

    def test_header_click_changes_sort(self, route_history):
        initial = (route_history.sort_by, route_history.sort_dir)
        route_history._on_header_clicked(0)
        assert route_history.sort_by != initial[0] or route_history.sort_dir != initial[1]

    def test_map_placeholder_visible(self, route_history):
        assert route_history._map_placeholder is not None

    def test_reset_filters(self, route_history):
        route_history.e_search.setText("test")
        route_history.c_profile.setCurrentIndex(2)
        route_history._archived_check.setChecked(True)
        route_history._reset_filters()
        assert route_history.e_search.text() == ""
        assert route_history.c_profile.currentIndex() == 0
        assert not route_history._archived_check.isChecked()

    def test_clear_preview(self, route_history):
        route_history._clear_preview()
        assert route_history._route_info.text() == ""
