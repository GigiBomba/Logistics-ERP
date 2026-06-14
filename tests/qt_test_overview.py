"""Tests for the PySide6 overview dashboard view."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QFrame

from ui.qt_views.qt_overview_view import QtOverviewView


@pytest.fixture
def overview_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.qt_views.qt_overview_view.load_company_config",
        lambda: {"company_name": "TestCo"},
    )

    fake_trip_repo = MagicMock()
    fake_trip_repo.get_all.return_value = [
        {
            "id": 1,
            "truck_number": "B-123-ABC",
            "client_name": "ACME",
            "status": "In Transit",
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_price_eur": 1500.0,
            "net_profit": 400.0,
            "driver_name": "John",
        },
        {
            "id": 2,
            "truck_number": "B-456-DEF",
            "client_name": "Globex",
            "status": "Delivered",
            "start_date": "2020-01-01",
            "created_at": "2020-01-01 00:00",
            "total_price_eur": 800.0,
            "net_profit": 100.0,
            "driver_name": "Jane",
        },
    ]
    fake_trip_repo.get_daily_profit.return_value = [
        (datetime.now().strftime("%Y-%m-%d"), 400.0),
    ]
    fake_trip_repo.get_top_trucks_by_revenue.return_value = [
        {"truck_number": "B-123-ABC", "revenue": 1500.0},
    ]

    fake_fleet_repo = MagicMock()
    fake_fleet_repo.get_all.return_value = [
        {"id": 1, "plate_number": "B-123-ABC", "model": "Volvo", "status": "Active"},
    ]

    with patch("ui.qt_views.qt_overview_view.TripRepository", return_value=fake_trip_repo), \
         patch("ui.qt_views.qt_overview_view.FleetRepository", return_value=fake_fleet_repo):
        view = QtOverviewView(qt_widget, db=MagicMock(), ops=None)
        qtbot.addWidget(view)
        yield view
        try:
            view.shutdown()
        except Exception:
            pass


class TestQtOverviewView:
    def test_creation(self, overview_view):
        assert overview_view._kpi_widgets is not None
        assert len(overview_view._kpi_widgets) == 6

    def test_header_shows_company(self, overview_view):
        labels = overview_view.findChildren(QLabel)
        assert any("TestCo" in (lbl.text() or "") for lbl in labels)

    def test_kpi_values_after_refresh(self, overview_view, qtbot):
        overview_view.refresh()
        assert overview_view._kpi_widgets["kpi_active_trucks"].value_label.text() == "1"
        assert "€" in overview_view._kpi_widgets["kpi_revenue"].value_label.text()

    def test_active_trips_list_renders(self, overview_view, qtbot):
        overview_view.refresh()
        assert overview_view._trips_count.text() == "1"
        rows = [w for w in overview_view.findChildren(QFrame) if w.property("role") == "card-elevated"]
        assert len(rows) >= 1

    def test_chart_container_has_widget(self, overview_view, qtbot):
        overview_view.refresh()
        # Allow chart render to complete via singleShot event.
        qtbot.wait(200)
        assert overview_view._chart_container.layout().count() > 0

    def test_top_trucks_renders(self, overview_view, qtbot):
        overview_view.refresh()
        assert any("B-123-ABC" in (lbl.text() or "") for lbl in overview_view.findChildren(QLabel))

    def test_recent_activity_renders(self, overview_view, qtbot):
        overview_view.refresh()
        assert any("ACME" in (lbl.text() or "") for lbl in overview_view.findChildren(QLabel))
