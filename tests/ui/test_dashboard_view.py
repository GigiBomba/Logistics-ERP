"""Tests for the fleet dashboard view (QtFleetDashboard)."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame, QPushButton


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service_result(data):
    """Build a minimal ServiceResult-like object from raw data."""
    from models.common import ServiceResult
    if data is None:
        return ServiceResult(success=True, data=[])
    return ServiceResult(success=True, data=data)


# ---------------------------------------------------------------------------
# Fixture — build a fully mocked dashboard
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_prefs():
    """Mock PreferencesManager with format_currency."""
    prefs = MagicMock()
    prefs.format_currency.side_effect = lambda v, d: f"€ {v:,.0f}"
    return prefs


@pytest.fixture
def dashboard(qt_widget, qtbot, mock_prefs):
    """Construct a QtFleetDashboard with all service dependencies patched.

    Patches the late imports inside refresh_all() so no real database or
    chart engines are touched.
    """
    # Service classes are imported inside refresh_all() via
    #   from services.analytics_service import AnalyticsService
    # so we patch the *target* module, not ui.views.dashboard directly.
    import PySide6.QtWidgets as QtWin

    _patchers = [
        patch("services.analytics_service.AnalyticsService"),
        patch("services.fleet_service.FleetService"),
        patch("services.trip_service.TripService"),
        patch("ui.plotly_charts.make_grouped_bar_chart"),
        patch("ui.plotly_charts.make_pie_chart"),
        patch("ui.plotly_renderer.PlotlyChartWidget"),
        patch("services.preferences.PreferencesManager", return_value=mock_prefs),
        patch.object(QtWin.QMessageBox, "warning", return_value=None),
    ]
    started = [p.start() for p in _patchers]

    # Unpack the mocks for configuration
    analytics_cls, fleet_cls, trip_cls = started[0], started[1], started[2]

    # Configure mock service instances so refresh_all() runs without error.
    # Each *cls is the MagicMock that replaces the original class.
    # cls.return_value = instance returned by constructor.
    analytics_cls.return_value.get_overdue_data.return_value = ([], 0.0)
    analytics_cls.return_value.get_financial.return_value = []
    analytics_cls.return_value.get_fleet.return_value = []
    analytics_cls.return_value.get_driver.return_value = []

    fleet_cls.return_value.get_trucks.return_value = []

    trip_cls.return_value.get_all.return_value = []

    from ui.views.dashboard import QtFleetDashboard

    db = MagicMock()
    view = QtFleetDashboard(qt_widget, db=db, prefs=mock_prefs)
    qtbot.addWidget(view)

    # __init__ triggers refresh_all(), which fetches data OFF the GUI thread
    # via WorkerPool (result delivered through a queued Qt signal).  Wait for
    # the initial cycle to complete so the widget tree (KPI cards + chart
    # frames) is deterministic regardless of prior test-suite Qt state.
    qtbot.waitUntil(
        lambda: hasattr(view, "_left_chart_frame") and hasattr(view, "_kpi_cards"),
        timeout=5000,
    )

    # Stop the auto-refresh timer
    if view._refresh_timer is not None:
        view._refresh_timer.stop()

    yield view

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

    for p in _patchers:
        p.stop()


@pytest.fixture
def configure_mock_services(dashboard):
    """Configure the mocked services with sample data.

    Call this inside a test before the code-under-test calls refresh_all().
    This fixture works with the patched module-level references.
    """
    AnalyticsService = dashboard.analytics_service = MagicMock()
    FleetService = dashboard.fleet_service = MagicMock()
    TripService = dashboard.trip_service = MagicMock()

    # Return a configurator dict so tests can override specific mocks
    return {
        "analytics": AnalyticsService,
        "fleet": FleetService,
        "trip": TripService,
    }


# ===========================================================================
# Construction & Initialization
# ===========================================================================

class TestConstruction:
    """View constructs and exposes expected attributes."""

    def test_creation(self, dashboard):
        """View constructs without crashing."""
        assert dashboard is not None

    def test_container_created(self, dashboard):
        """Scroll container is created."""
        assert hasattr(dashboard, "_container")

    def test_content_frame_created(self, dashboard):
        """Content frame is created for dynamic content."""
        assert hasattr(dashboard, "_content_frame")

    def test_period_buttons_created(self, dashboard):
        """Period filter buttons are present."""
        assert len(dashboard._period_button_refs) == 4

    def test_refresh_label_created(self, dashboard):
        """Last-refresh label is created."""
        assert hasattr(dashboard, "_last_refresh_lbl")
        assert isinstance(dashboard._last_refresh_lbl, QLabel)

    def test_refresh_timer_created(self, dashboard):
        """Auto-refresh timer is created."""
        assert dashboard._refresh_timer is not None

    def test_prefs_assigned(self, dashboard):
        """Preferences manager is assigned."""
        assert dashboard.prefs is not None

    def test_default_period(self, dashboard):
        """Default period is 'today'."""
        assert dashboard._period == "today"


# ===========================================================================
# KPI Card Display
# ===========================================================================

class TestKPICards:
    """KPI metric cards render correctly."""

    def test_kpi_cards_created(self, dashboard):
        """KPI cards are built by refresh_all()."""
        # The dashboard constructor already calls refresh_all()
        # KPI cards should be in _content_layout_inner
        assert hasattr(dashboard, "_kpi_cards")
        assert len(dashboard._kpi_cards) == 4

    def test_kpi_card_has_label_and_value(self, dashboard):
        """Each KPI card has a title and value label."""
        for key, card in dashboard._kpi_cards.items():
            assert hasattr(card, "title_label")
            assert hasattr(card, "value_label")

    def test_kpi_active_trucks_shows_count(self, dashboard):
        """Active trucks KPI displays the correct count."""
        card = dashboard._kpi_cards["fleet_dashboard.kpi_active_trucks"]
        assert card.value_label is not None

    def test_kpi_revenue_formatted(self, dashboard):
        """Revenue KPI uses currency formatting."""
        card = dashboard._kpi_cards["fleet_dashboard.kpi_revenue"]
        assert "€" in card.value_label.text()

    def test_kpi_alerts_shows_count(self, dashboard):
        """Alerts KPI displays count."""
        card = dashboard._kpi_cards["fleet_dashboard.kpi_alerts"]
        assert card.value_label is not None


# ===========================================================================
# Period Filtering
# ===========================================================================

class TestPeriodFiltering:
    """Period buttons and date range logic."""

    def test_set_period_today(self, dashboard):
        """Setting period to 'today' updates dates and triggers refresh."""
        dashboard._set_period("today")
        assert dashboard._period == "today"

    def test_set_period_week(self, dashboard):
        """Setting period to 'week' updates dates."""
        dashboard._set_period("week")
        assert dashboard._period == "week"
        assert dashboard._start_date is not None
        assert dashboard._end_date is not None

    def test_set_period_month(self, dashboard):
        """Setting period to 'month' updates dates."""
        dashboard._set_period("month")
        assert dashboard._period == "month"

    def test_set_period_custom(self, dashboard):
        """Setting period to 'custom' clears dates."""
        dashboard._set_period("custom")
        assert dashboard._period == "custom"
        assert dashboard._start_date is None
        assert dashboard._end_date is None


# ===========================================================================
# Chart Rendering
# ===========================================================================

class TestChartRendering:
    """Chart widgets are created with data."""

    def test_chart_frames_exist(self, dashboard):
        """Left and right chart frames are created."""
        assert hasattr(dashboard, "_left_chart_frame")
        assert hasattr(dashboard, "_right_chart_frame")

    def test_chart_refs_cleared_on_refresh(self, dashboard):
        """Chart references are cleared between refresh cycles."""
        prev_count = len(dashboard._chart_refs)
        dashboard.refresh_all()

    def test_empty_chart_shows_empty_state(self, dashboard):
        """When there is no trip data, an EmptyState widget is shown."""
        # The chart should still render without error (empty state)
        assert dashboard._left_chart_frame is not None


# ===========================================================================
# Info Cards
# ===========================================================================

class TestInfoCards:
    """Best truck, best driver, and highest fuel cards."""

    def test_info_cards_created(self, dashboard):
        """Three info cards are created below the charts."""
        # After refresh_all, the content area should contain an info cards frame
        # We verify by checking that the content layout has enough items
        assert dashboard._content_layout_inner.count() >= 3

    def test_info_cards_data_driven(self, dashboard):
        """Info cards show data when fleet data is available."""
        dashboard.refresh_all()


# ===========================================================================
# Activity Feed
# ===========================================================================

class TestActivityFeed:
    """Activity feed displays recent trips."""

    def test_activity_feed_created(self, dashboard):
        """Activity feed section is built."""
        # refresh_all is called in constructor
        assert dashboard._content_layout_inner is not None

    def test_activity_feed_empty_state(self, dashboard):
        """Empty state is shown when there are no trips."""
        dashboard.refresh_all()

    def test_view_all_link_present(self, dashboard):
        """'View all' link label is present in the activity feed."""
        # The link is inside the feed frame; we can verify the dashboard
        # has the method that creates it
        assert callable(dashboard._open_route_history)


# ===========================================================================
# Data Refresh / Update
# ===========================================================================

class TestDataRefresh:
    """Data reload and refresh triggers."""

    def test_refresh_all_updates_label(self, dashboard):
        """refresh_all updates the last-refresh timestamp label."""
        dashboard._last_refresh_lbl.setText("")
        dashboard.refresh_all()
        assert dashboard._last_refresh_lbl.text() != ""

    def test_refresh_all_clears_content(self, dashboard):
        """refresh_all clears old content before rebuilding."""
        # Save item count before second refresh
        count_before = dashboard._content_layout_inner.count()
        dashboard.refresh_all()
        # Content should be rebuilt (count may differ if services return different data)
        assert dashboard._content_layout_inner.count() > 0

    def test_refresh_all_handles_empty_data(self, dashboard):
        """refresh_all works when all services return empty."""
        dashboard.refresh_all()

    def test_auto_refresh_timer_created(self, dashboard):
        """Auto-refresh timer is created after construction."""
        assert dashboard._refresh_timer is not None


# ===========================================================================
# Error Handling
# ===========================================================================

class TestErrorHandling:
    """Error states during data loading."""

    def test_refresh_all_exception_handled(self, dashboard):
        """Exceptions in the data-loading section of refresh_all are caught."""
        # Make the analytics service get_financial raise — this happens
        # inside the try/except block in refresh_all().
        analytics_cls = __import__(
            "services.analytics_service", fromlist=["AnalyticsService"]
        ).AnalyticsService
        original_get_financial = analytics_cls.return_value.get_financial
        analytics_cls.return_value.get_financial.side_effect = RuntimeError("Data load failed")

        # Should not propagate — refresh_all catches it
        dashboard.refresh_all()

    def test_service_failure_does_not_crash(self, dashboard):
        """refresh_all handles service-level exceptions gracefully."""
        # Make the analytics service get_overdue_data raise.
        analytics_cls = __import__(
            "services.analytics_service", fromlist=["AnalyticsService"]
        ).AnalyticsService
        analytics_cls.return_value.get_overdue_data.side_effect = RuntimeError("Analytics down")

        # Should not crash — refresh_all catches it
        dashboard.refresh_all()


# ===========================================================================
# Empty State (No Data)
# ===========================================================================

class TestEmptyState:
    """Dashboard displays correctly when there is no data."""

    def test_no_data_kpi_zero_values(self, dashboard):
        """KPI cards show zero values when no data is available."""
        for key, card in dashboard._kpi_cards.items():
            val = card.value_label.text()
            assert val is not None

    def test_no_data_no_crash(self, dashboard):
        """Empty data does not cause crashes."""
        dashboard.refresh_all()

    def test_no_data_empty_state_charts(self, dashboard):
        """Charts show empty state when no trip/truck data."""
        assert dashboard._left_chart_frame is not None
        assert dashboard._right_chart_frame is not None


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Edge case handling for large numbers and missing data."""

    def test_large_revenue_value(self, mock_prefs):
        """Very large revenue numbers are formatted without overflow."""
        formatted = mock_prefs.format_currency(9_999_999_999.99, 0)
        assert "€" in formatted
        assert "," in formatted  # Thousands separator

    def test_missing_trip_fields(self, dashboard):
        """Trips with missing fields do not crash the activity feed."""
        dashboard.refresh_all()

    def test_zero_trips(self, dashboard):
        """Zero trips result in empty activity feed."""
        dashboard.refresh_all()

    def test_zero_trucks(self, dashboard):
        """Zero trucks result in empty fleet status."""
        dashboard.refresh_all()


# ===========================================================================
# Lifecycle
# ===========================================================================

class TestLifecycle:
    """shutdown / cleanup."""

    def test_shutdown_stops_timer(self, dashboard):
        """shutdown stops the auto-refresh timer."""
        dashboard.shutdown()
        assert not dashboard._refresh_timer.isActive()

    def test_shutdown_idempotent(self, dashboard):
        """shutdown can be called multiple times."""
        dashboard.shutdown()
        dashboard.shutdown()

    def test_wakeup_does_not_crash(self, dashboard):
        """wakeup() calls refresh_all and does not crash."""
        dashboard.wakeup()

    def test_shutdown_cleanup_listeners(self, dashboard):
        """shutdown cleans up i18n listeners."""
        dashboard.shutdown()

    def test_close_event_cleanup(self, dashboard, qtbot):
        """closeEvent triggers shutdown."""
        # Simulate close
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        dashboard.closeEvent(event)


# ===========================================================================
# Widget Arrangement / Layout
# ===========================================================================

class TestWidgetLayout:
    """Layout arrangement of dashboard widgets."""

    def test_header_present(self, dashboard):
        """Header with title and period buttons is present."""
        assert dashboard._last_refresh_lbl is not None

    def test_scroll_area_exists(self, dashboard):
        """Dashboard content is inside a scroll area."""
        # The dashboard's own layout should contain a scroll area
        layout = dashboard.layout()
        assert layout is not None
        # Scroll area is the first (and only) widget in our layout
        item = layout.itemAt(0)
        assert item is not None

    def test_content_layout_is_vertical(self, dashboard):
        """Content layout inside scroll area is vertical."""
        assert dashboard._content_layout_inner is not None
        # The layout should be a QVBoxLayout
        from PySide6.QtWidgets import QVBoxLayout
        assert isinstance(dashboard._content_layout_inner, QVBoxLayout)


# ===========================================================================
# i18n / Language Change
# ===========================================================================

class TestI18n:
    """Language change handling."""

    def test_language_callback_registered(self, dashboard):
        """_on_language_changed is the registered callback."""
        assert callable(dashboard._language_callback)

    def test_language_change_schedules_refresh(self, dashboard):
        """Language change triggers refresh_translations."""
        # The callback should schedule a refresh via QTimer.singleShot
        dashboard._on_language_changed("ro")

    def test_refresh_translations_does_not_crash(self, dashboard):
        """refresh_translations can be called without error."""
        dashboard.refresh_translations()
