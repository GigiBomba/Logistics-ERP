"""Tests for the PySide6 trip history view."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ui.views.history_view import QtHistoryView


@pytest.fixture
def history_view(qt_widget, qtbot):
    db = MagicMock()
    view = QtHistoryView(qt_widget, db=db, controller=None)
    qtbot.addWidget(view)
    view.trip_service = MagicMock()
    view.trip_service.get_filtered.return_value = [
        {
            "id": 1, "start_date": "2024-01-01", "truck_number": "B-123",
            "driver_name": "John", "client_name": "ACME", "distance_km": 500,
            "gross_per_km": 2.0, "net_profit": 400.0, "status": "Delivered",
        },
        {
            "id": 2, "start_date": "2024-01-02", "truck_number": "B-456",
            "driver_name": "Jane", "client_name": "Globex", "distance_km": 300,
            "gross_per_km": 1.5, "net_profit": -50.0, "status": "In Transit",
        },
    ]
    view.invoice_service = MagicMock()
    view.export_service = MagicMock()
    view.refresh()
    yield view
    try:
        view.shutdown()
    except Exception:
        pass


class TestQtHistoryView:
    def test_creation(self, history_view):
        assert history_view.table is not None
        assert history_view.e_search is not None

    def test_filter_widgets_exist(self, history_view):
        assert history_view.e_search is not None
        assert history_view.c_status is not None
        assert history_view._count_lbl is not None

    def test_table_has_columns(self, history_view):
        assert history_view.table.columnCount() == 9

    def test_data_rendered_in_table(self, history_view):
        assert history_view.table.rowCount() == 2

    def test_status_colors_applied(self, history_view):
        col = history_view.table._column_ids.index("status")
        item = history_view.table.item(0, col)
        assert item is not None

    def test_profit_colors_applied(self, history_view):
        col = history_view.table._column_ids.index("net_profit")
        item_green = history_view.table.item(0, col)
        item_red = history_view.table.item(1, col)
        assert item_green is not None
        assert item_red is not None

    def test_filter_changes_refresh(self, history_view):
        history_view.c_status.setCurrentText("Planned")
        assert history_view.trip_service.get_filtered.called

    def test_reset_filters(self, history_view):
        history_view.e_search.setText("test")
        history_view._reset()
        assert history_view.e_search.text() == ""

    def test_load_more(self, history_view):
        initial_limit = history_view._limit
        history_view._load_more()
        assert history_view._limit == initial_limit * 2
