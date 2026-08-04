"""Visual regression tests for core standalone widgets — Phase 9, Stage 9.2."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from ui.components import CompactKPICard, KPICard
from ui.widgets.stat_card import StatCard
from ui.widgets.toast import Toast
from ui.widgets.trip_card import QtTripCard

pytestmark = pytest.mark.visual


# ── Sample data ─────────────────────────────────────────────────────────

TRIP_BASIC = {
    "trip_id": 1042,
    "origin": "București",
    "destination": "Cluj-Napoca",
    "status": "in_progress",
    "start_date": "2026-07-20T08:00:00",
    "end_date": "2026-07-21T16:00:00",
    "truck_plate": "TR-01-MNT",
    "driver_name": "Ion Popescu",
    "alerts_count": 0,
    "distance_km": 450,
}

TRIP_WITH_ASSIGNMENTS = {
    **TRIP_BASIC,
    "truck_label": "TR-01-MNT",
    "driver_name": "Ion Popescu",
}

TRIP_DELAYED = {**TRIP_BASIC, "status": "delayed"}

TRIP_WITH_ALERTS = {**TRIP_BASIC, "alerts_count": 3, "status": "attention"}


# ── Test classes ────────────────────────────────────────────────────────


class TestVisualStatCard:
    """Screenshot tests for StatCard widgets."""

    def test_stat_card_default(self, qt_widget, qtbot, assert_snapshot):
        """Default stat card with revenue value."""
        card = StatCard(parent=qt_widget, label="Revenue", value="€12,450")
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=50, resize=(200, 88))

    def test_stat_card_with_status(self, qt_widget, qtbot, assert_snapshot):
        """Stat card with colored status dot."""
        card = StatCard(
            parent=qt_widget,
            label="Fleet Utilization",
            value="87%",
            status_dot_color="good",
        )
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=50, resize=(200, 88))


class TestVisualToast:
    """Screenshot tests for Toast notification popups."""

    def test_toast_success(self, qt_widget, qtbot, assert_snapshot):
        """Success toast notification."""
        toast = Toast.show_success(parent=qt_widget, message="Operation completed successfully")
        qtbot.addWidget(toast)
        toast.show()
        assert_snapshot(toast, delay_ms=300)

    def test_toast_error(self, qt_widget, qtbot, assert_snapshot):
        """Error toast notification."""
        toast = Toast.show_error(parent=qt_widget, message="Failed to save document")
        qtbot.addWidget(toast)
        toast.show()
        assert_snapshot(toast, delay_ms=300)


class TestVisualTripCard:
    """Screenshot tests for QtTripCard."""

    def test_trip_card_default(self, qt_widget, qtbot, assert_snapshot):
        """Minimal trip card with basic info."""
        card = QtTripCard(parent=qt_widget, trip_data=TRIP_BASIC)
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=100, resize=(320, 200))

    def test_trip_card_delayed(self, qt_widget, qtbot, assert_snapshot):
        """Trip card with delayed status."""
        card = QtTripCard(parent=qt_widget, trip_data=TRIP_DELAYED)
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=100, resize=(320, 200))

    def test_trip_card_with_alerts(self, qt_widget, qtbot, assert_snapshot):
        """Trip card with alert badges."""
        card = QtTripCard(parent=qt_widget, trip_data=TRIP_WITH_ALERTS)
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=100, resize=(320, 200))


class TestVisualKPICards:
    """Screenshot tests for KPI card components."""

    def test_kpi_card_legacy(self, qt_widget, qtbot, assert_snapshot):
        """Legacy KPICard with value and subtitle."""
        card = KPICard(
            parent=qt_widget,
            label="TOTAL KM",
            value="45,230",
            subtitle="+12% vs last month",
        )
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=50, resize=(240, 160))

    def test_kpi_card_compact(self, qt_widget, qtbot, assert_snapshot):
        """Compact KPI card with icon."""
        card = CompactKPICard(
            parent=qt_widget,
            label="Active Drivers",
            value="24",
            icon_name="fa5s.truck",
        )
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=50, resize=(280, 88))

    def test_kpi_card_compact_trend(self, qt_widget, qtbot, assert_snapshot):
        """Compact KPI card with trend indicator."""
        card = CompactKPICard(
            parent=qt_widget,
            label="Revenue",
            value="€89K",
            trend="+8.3%",
            trend_positive=True,
        )
        qtbot.addWidget(card)
        assert_snapshot(card, delay_ms=50, resize=(280, 88))
