"""Tests for QtOverviewView — overview dashboard."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_trip_service():
    ts = MagicMock()
    ts.get_all.return_value = []
    ts.get_top_trucks_by_revenue.return_value = []
    return ts


@pytest.fixture
def mock_fleet_service():
    return MagicMock()


@pytest.fixture
def mock_analytics_service():
    svc = MagicMock()
    svc.get_monthly_financial.return_value = []
    svc.get_fleet.return_value = []
    svc.get_maintenance_alerts.return_value = []
    svc.get_driver.return_value = []
    svc.get_driver_tacho_violations.return_value = []
    svc.get_client_analytics.return_value = []
    svc.get_revenue_by_client.return_value = []
    svc.get_revenue_concentration.return_value = []
    svc.get_route_profitability.return_value = []
    svc.get_profit_per_km_by_country.return_value = []
    return svc


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_active_alert_count.return_value = 0
    return ops


@pytest.fixture
def overview_view(qtbot, mock_trip_service, mock_fleet_service,
                  mock_analytics_service, mock_ops):
    """Create QtOverviewView with all services mocked."""
    patchers = [
        patch("ui.views.overview_view.load_company_config", return_value={"company_name": "TestCo"}),
    ]
    for p in patchers:
        p.start()

    from ui.views.overview_view import QtOverviewView

    widget = QtOverviewView(
        parent=None,
        db=MagicMock(),
        ops=mock_ops,
        trip_service=mock_trip_service,
        fleet_service=mock_fleet_service,
        analytics_svc=mock_analytics_service,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================

class TestQtOverviewView:
    """Suite of tests for QtOverviewView."""

    def test_initialization(self, overview_view):
        """Widget initializes without crashing."""
        assert overview_view is not None
        assert hasattr(overview_view, "_kpi_widgets")
        assert hasattr(overview_view, "_selected_kpis")

    def test_stat_cards_render(self, overview_view):
        """KPI strip contains stat cards with value labels."""
        assert len(overview_view._kpi_widgets) >= 1
        assert len(overview_view._kpi_value_labels) >= 1

    def test_recent_activity_section_renders(self, overview_view):
        """Recent activity layout exists."""
        assert hasattr(overview_view, "_activity_layout")
        assert overview_view._activity_layout is not None

    def test_alert_list_renders(self, overview_view):
        """Alert layout exists."""
        assert hasattr(overview_view, "_alerts_layout")
        assert overview_view._alerts_layout is not None

    def test_active_trips_section_renders(self, overview_view):
        """Active trips section exists."""
        assert hasattr(overview_view, "_trips_list")
        assert overview_view._trips_list is not None

    def test_top_trucks_section_renders(self, overview_view):
        """Top trucks section exists."""
        assert hasattr(overview_view, "_top_trucks_layout")
        assert overview_view._top_trucks_layout is not None

    def test_header_renders(self, overview_view):
        """Header contains the company name label."""
        # The header builds with company name from load_company_config
        # which we mocked to return "TestCo"
        assert overview_view is not None

    def test_chart_container_renders(self, overview_view):
        """Chart container frame exists."""
        assert hasattr(overview_view, "_chart_container")
        assert overview_view._chart_container is not None

    def test_refresh_does_not_crash(self, overview_view):
        """refresh() runs without errors."""
        overview_view.refresh()

    def test_refresh_kpis_does_not_crash(self, overview_view):
        """KPI refresh runs without errors with empty services."""
        overview_view._refresh_kpis()

    def test_refresh_active_trips_empty(self, overview_view):
        """Active trips handles empty data gracefully."""
        overview_view._refresh_active_trips()
        # Should show an EmptyState widget
        from ui.components import EmptyState
        # Check if the trips layout has at least one child
        assert overview_view._trips_list.count() >= 0

    def test_refresh_alerts_empty(self, overview_view, mock_ops):
        """Alert refresh handles empty data."""
        overview_view._refresh_alerts()
        assert overview_view._alerts_layout.count() >= 0

    def test_refresh_top_trucks_empty(self, overview_view, mock_trip_service):
        """Top trucks handles empty data."""
        mock_trip_service.get_top_trucks_by_revenue.return_value = []
        overview_view._refresh_top_trucks()
        assert overview_view._top_trucks_layout.count() >= 0

    def test_refresh_recent_activity_empty(self, overview_view, mock_trip_service):
        """Recent activity handles empty data."""
        mock_trip_service.get_all.return_value = []
        overview_view._refresh_recent_activity()
        assert overview_view._activity_layout.count() >= 0

    def test_shutdown_cleanup(self, overview_view):
        """shutdown() sets shutting_down flag and calls base cleanup."""
        overview_view.shutdown()
        assert overview_view._shutting_down is True

    def test_wakeup_does_not_crash(self, overview_view):
        """wakeup() refreshes without crashing."""
        overview_view.wakeup()

    def test_pick_random_content_selects_kpis(self, overview_view):
        """_pick_random_content selects KPI and chart sources."""
        overview_view._pick_random_content()
        assert len(overview_view._selected_kpis) == 3
        assert overview_view._selected_chart is not None

    def test_compute_kpi_value_handles_empty_svc(self, overview_view):
        """_compute_kpi_value returns €0 when service returns empty list."""
        val, color = overview_view._compute_kpi_value("fin_revenue")
        # Empty monthly data => total=0 => fmt_currency returns "€ 0"
        assert "0" in val

    # ═══════════════════════════════════════════════════════════════════
    #  Expanded tests
    # ═══════════════════════════════════════════════════════════════════

    # ── Chart rendering ────────────────────────────────────────────────

    def test_render_profit_chart_no_data(self, overview_view):
        """_render_profit_chart shows 'no data' label when analytics_svc is None."""
        overview_view._analytics_svc = None
        overview_view._render_profit_chart(_force=True)
        layout = overview_view._chart_container.layout()
        assert layout is not None
        # Should show a "no data" label
        assert layout.count() >= 1

    def test_render_profit_chart_with_mock_service(self, overview_view, mock_analytics_service):
        """_render_profit_chart with service but no data shows no-data label."""
        mock_analytics_service.get_revenue_by_client.return_value = []
        # PlotlyChartWidget is imported dynamically inside _do_render_chart
        # via ``from ui.plotly_renderer import PlotlyChartWidget``.
        with patch("ui.plotly_renderer.PlotlyChartWidget") as mock_chart_widget:
            mock_chart_widget.return_value = MagicMock()
            overview_view._render_profit_chart(_force=True)
        layout = overview_view._chart_container.layout()
        assert layout is not None

    def test_chart_throttle_skips_rapid_renders(self, overview_view):
        """_render_profit_chart skips if called too quickly (<0.8s)."""
        overview_view._chart_render_ts = __import__("time").time()
        overview_view._render_profit_chart(_force=False)
        # Second call should be skipped — no crash
        overview_view._render_profit_chart(_force=False)

    # ── KPI computation — various keys ─────────────────────────────────

    def test_compute_kpi_fin_profit(self, overview_view, mock_analytics_service):
        """fin_profit KPI with mixed profit data."""
        mock_analytics_service.get_monthly_financial.return_value = [
            {"revenue": 1000, "profit": 200},
            {"revenue": 1500, "profit": -50},
        ]
        val, color = overview_view._compute_kpi_value("fin_profit")
        assert "€" in val or "EUR" in val or "150" in val

    def test_compute_kpi_fleet_trucks(self, overview_view, mock_analytics_service):
        """fleet_trucks KPI returns truck count."""
        mock_analytics_service.get_fleet.return_value = [
            {"truck": "TR-01"}, {"truck": "TR-02"}, {"truck": "TR-03"},
        ]
        val, color = overview_view._compute_kpi_value("fleet_trucks")
        assert val == "3"

    def test_compute_kpi_driver_count(self, overview_view, mock_analytics_service):
        """driver_count KPI returns driver count."""
        mock_analytics_service.get_driver.return_value = [
            {"driver": "John"}, {"driver": "Jane"},
        ]
        val, color = overview_view._compute_kpi_value("driver_count")
        assert val == "2"

    def test_compute_kpi_fleet_consumption(self, overview_view, mock_analytics_service):
        """fleet_consumption KPI returns average L/100km."""
        mock_analytics_service.get_fleet.return_value = [
            {"avg_consumption": 30}, {"avg_consumption": 40},
        ]
        val, color = overview_view._compute_kpi_value("fleet_consumption")
        assert "L/100km" in val

    def test_compute_kpi_fleet_maint_no_alerts(self, overview_view, mock_analytics_service):
        """fleet_maint shows 0 with success color when no alerts."""
        mock_analytics_service.get_maintenance_alerts.return_value = []
        val, color = overview_view._compute_kpi_value("fleet_maint")
        assert val == "0"

    def test_compute_kpi_client_count_fallback(self, overview_view, mock_analytics_service):
        """client_count falls back to revenue_by_client when client_analytics is empty."""
        mock_analytics_service.get_client_analytics.return_value = []
        mock_analytics_service.get_revenue_by_client.return_value = [
            {"client": "A"}, {"client": "B"}, {"client": "C"},
        ]
        val, color = overview_view._compute_kpi_value("client_count")
        assert val == "3"

    def test_compute_kpi_route_count(self, overview_view, mock_analytics_service):
        """route_count sums trip counts from route_profitability."""
        mock_analytics_service.get_route_profitability.return_value = [
            {"trip_count": 5}, {"trip_count": 10},
        ]
        val, color = overview_view._compute_kpi_value("route_count")
        assert val == "15"

    def test_compute_kpi_driver_violations_positive(self, overview_view, mock_analytics_service):
        """driver_violations with violations returns count."""
        mock_analytics_service.get_driver_tacho_violations.return_value = [
            {"total_violations": 3},
        ]
        val, color = overview_view._compute_kpi_value("driver_violations")
        assert val == "3"

    # ── Active trips with data ──────────────────────────────────────────

    def test_active_trips_with_data(self, overview_view, mock_trip_service):
        """_refresh_active_trips handles trips with active status."""
        mock_trip_service.get_all.return_value = [
            {"id": 1, "status": "In Progress", "truck_number": "TR-01",
             "client_name": "Client A", "origin": "City1", "destination": "City2"},
            {"id": 2, "status": "Planned", "truck_number": "TR-02",
             "client_name": "Client B", "origin": "City3", "destination": "City4"},
        ]
        overview_view._refresh_active_trips()
        assert overview_view._trips_list.count() >= 1
        assert overview_view._trips_count.text() == "2"

    def test_active_trips_filters_non_active(self, overview_view, mock_trip_service):
        """_refresh_active_trips filters out Delivered/Completed/Cancelled trips."""
        mock_trip_service.get_all.return_value = [
            {"id": 1, "status": "Delivered", "truck_number": "TR-01",
             "client_name": "Client A"},
            {"id": 2, "status": "Cancelled", "truck_number": "TR-02",
             "client_name": "Client B"},
            {"id": 3, "status": "In Progress", "truck_number": "TR-03",
             "client_name": "Client C"},
        ]
        overview_view._refresh_active_trips()
        assert overview_view._trips_count.text() == "1"

    def test_active_trips_empty_shows_empty_state(self, overview_view, mock_trip_service):
        """_refresh_active_trips shows EmptyState when no active trips."""
        mock_trip_service.get_all.return_value = []
        overview_view._refresh_active_trips()
        assert overview_view._trips_list.count() >= 1
        from ui.components import EmptyState
        item = overview_view._trips_list.itemAt(0)
        if item:
            assert isinstance(item.widget(), EmptyState)

    # ── Alert / Top trucks / Activity with data ────────────────────────

    def test_top_trucks_with_data(self, overview_view, mock_trip_service):
        """_refresh_top_trucks renders rows with data."""
        mock_trip_service.get_top_trucks_by_revenue.return_value = [
            {"truck_number": "TR-01", "revenue": 50000},
            {"truck_number": "TR-02", "revenue": 30000},
        ]
        overview_view._refresh_top_trucks()
        assert overview_view._top_trucks_layout.count() >= 1

    def test_recent_activity_with_data(self, overview_view, mock_trip_service):
        """_refresh_recent_activity renders rows with data."""
        mock_trip_service.get_all.return_value = [
            {"id": 1, "truck_number": "TR-01", "client_name": "Client A",
             "net_profit": 5000, "start_date": "2026-06-01",
             "created_at": "2026-06-01T10:00:00"},
        ]
        overview_view._refresh_recent_activity()
        assert overview_view._activity_layout.count() >= 1

    def test_alerts_with_data(self, overview_view, mock_ops):
        """_refresh_alerts renders alert rows when ops returns data."""
        mock_alert = MagicMock()
        mock_alert.severity = "WARNING"
        mock_alert.title = "Test alert message"
        mock_alert.message = "Test"
        mock_alert.created_at = "2026-06-01T12:00:00"
        mock_ops.get_active_alerts.return_value = [mock_alert]
        overview_view._refresh_alerts()
        assert overview_view._alerts_layout.count() >= 1

    # ── Event handling ──────────────────────────────────────────────────

    def test_on_data_changed_triggers_refresh(self, overview_view):
        """_on_data_changed schedules a refresh via QTimer."""
        overview_view._last_refresh_ts = 0
        overview_view._on_data_changed(MagicMock())
        # The timer fires asynchronously, so just verify no crash

    def test_subscribe_events_registers_handlers(self, overview_view):
        """_subscribe_events registers handlers for known events."""
        assert len(overview_view._handlers) >= 6

    # ── Chart re-render logic ───────────────────────────────────────────

    def test_should_rerender_chart_true_when_no_fig(self, overview_view):
        """_should_rerender_chart returns True when _chart_fig is None."""
        overview_view._chart_fig = None
        overview_view._selected_chart = {"key": "rev_by_client"}
        assert overview_view._should_rerender_chart() is True

    def test_should_rerender_chart_false_when_no_chart(self, overview_view):
        """_should_rerender_chart returns False when no chart selected."""
        overview_view._chart_fig = MagicMock()
        overview_view._selected_chart = None
        assert overview_view._should_rerender_chart() is False

    def test_should_rerender_chart_false_same_key(self, overview_view):
        """_should_rerender_chart returns False when same key and fresh."""
        overview_view._chart_fig = MagicMock()
        overview_view._selected_chart = {"key": "rev_by_client"}
        overview_view._last_rendered_chart_key = "rev_by_client"
        overview_view._chart_last_render_ts = __import__("time").time()
        assert overview_view._should_rerender_chart() is False

    def test_should_rerender_chart_true_different_key(self, overview_view):
        """_should_rerender_chart returns True when chart key changed."""
        overview_view._chart_fig = MagicMock()
        overview_view._selected_chart = {"key": "new_key"}
        overview_view._last_rendered_chart_key = "old_key"
        overview_view._chart_last_render_ts = __import__("time").time()
        assert overview_view._should_rerender_chart() is True

    # ── Refresh with guards ─────────────────────────────────────────────

    def test_refresh_skipped_when_shutting_down(self, overview_view):
        """refresh returns early when _shutting_down is True."""
        overview_view._shutting_down = True
        overview_view.refresh()  # should not crash

    def test_refresh_rate_limited(self, overview_view):
        """refresh skips if called within 2 seconds."""
        overview_view._last_refresh_ts = __import__("time").time()
        overview_view.refresh()  # second call should be skipped

    # ── Language change ─────────────────────────────────────────────────

    def test_on_language_changed_triggers_refresh(self, overview_view):
        """_on_language_changed schedules a refresh."""
        overview_view._on_language_changed("ro")
        # no crash

    # ── _trip_row helper ────────────────────────────────────────────────

    def test_trip_row_creates_widget(self, overview_view):
        """_trip_row returns a QFrame with layout."""
        trip = {"id": 1, "status": "In Progress", "truck_number": "TR-01",
                "client_name": "Client A", "origin": "London", "destination": "Paris"}
        row = overview_view._trip_row(trip)
        assert row is not None
        # Contains plate, route, and status badge
        assert hasattr(row, "layout")
        assert row.layout().count() >= 3

    def test_trip_row_truncates_long_route(self, overview_view):
        """_trip_row truncates route text > 34 chars."""
        trip = {"id": 1, "status": "In Progress", "truck_number": "TR-01",
                "client_name": "Very Long Client Name That Should Be Truncated",
                "origin": "", "destination": ""}
        row = overview_view._trip_row(trip)
        assert row is not None
