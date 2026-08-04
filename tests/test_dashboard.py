"""Tests for the QtFleetDashboard view."""
from __future__ import annotations

import contextlib
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame

# SP workaround: ui.widgets.SP may not exist since it re-exports SP as S
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


@pytest.fixture(autouse=True)
def run_workers_sync(monkeypatch):
    """Run WorkerPool tasks synchronously so refresh data lands inline.

    ``QtFleetDashboard.refresh_all`` delegates to ``WorkerPool.run``, which
    would otherwise deliver ``_fetch_data`` results asynchronously on a
    background thread — racing the synchronous assertions in these tests
    (mirrors ``tests/test_overview.py``).  Executing the callback inline
    makes every refresh deterministic; the ``on_error`` path is handled so
    failure tests stay deterministic too.
    """

    def _run_sync(fn, on_result=None, on_error=None, **kwargs):
        try:
            result = fn()
        except Exception as exc:
            if on_error is not None:
                on_error(f"{exc}\n")
            return None
        if on_result is not None:
            on_result(result)
        return None

    monkeypatch.setattr(
        "ui.views.dashboard.WorkerPool.run",
        _run_sync,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_analytics_svc():
    svc = MagicMock()
    svc.get_overdue_data.return_value = ([], None)
    svc.get_financial.return_value = []
    svc.get_fleet.return_value = []
    svc.get_driver.return_value = []
    return svc


@pytest.fixture
def mock_fleet_svc():
    svc = MagicMock()
    svc.get_trucks.return_value = []
    return svc


@pytest.fixture
def mock_trip_svc():
    svc = MagicMock()
    svc.get_all.return_value = []
    return svc


@pytest.fixture
def dashboard(qt_widget, qtbot, mock_db, monkeypatch, mock_analytics_svc, mock_fleet_svc, mock_trip_svc):
    from ui.views.dashboard import QtFleetDashboard

    monkeypatch.setattr(
        "services.analytics_service.AnalyticsService",
        lambda db: mock_analytics_svc,
    )
    monkeypatch.setattr(
        "services.fleet_service.FleetService",
        lambda db: mock_fleet_svc,
    )
    monkeypatch.setattr(
        "services.trip_service.TripService",
        lambda db: mock_trip_svc,
    )
    view = QtFleetDashboard(qt_widget, db=mock_db)
    qtbot.addWidget(view)
    yield view
    with contextlib.suppress(Exception):
        view.shutdown()


# ── Initialisation ────────────────────────────────────────────────────────────


class TestQtFleetDashboardInit:
    """Dashboard creation and initial state."""

    def test_creation_stores_references(self, dashboard, mock_db):
        assert dashboard.db is mock_db
        assert dashboard.prefs is not None  # created by PreferencesManager(mock_db)
        assert dashboard.ops is None

    def test_has_refresh_timer(self, dashboard):
        assert hasattr(dashboard, "_refresh_timer")
        assert dashboard._refresh_timer is not None
        assert dashboard._refresh_timer.isActive()

    def test_i18n_listener_registered(self, dashboard):
        from services.i18n import _listeners

        assert dashboard._language_callback in _listeners

    def test_initial_period_is_today(self, dashboard):
        assert dashboard._period == "today"

    def test_initial_grid_visible(self, dashboard):
        assert dashboard._grid_visible is True

    def test_kpi_cards_dict_initialized(self, dashboard):
        assert isinstance(dashboard._kpi_cards, dict)


# ── Wakeup ────────────────────────────────────────────────────────────────────


class TestQtFleetDashboardWakeup:
    """Re-activation on view switch."""

    def test_wakeup_calls_refresh_all(self, dashboard):
        dashboard.refresh_all = MagicMock()
        dashboard.wakeup()
        dashboard.refresh_all.assert_called_once()


# ── Shutdown ──────────────────────────────────────────────────────────────────


class TestQtFleetDashboardShutdown:
    """Cleanup lifecycle."""

    def test_shutdown_stops_timer(self, dashboard):
        dashboard._refresh_timer.stop = MagicMock()
        dashboard.shutdown()
        dashboard._refresh_timer.stop.assert_called_once()

    def test_shutdown_unregisters_i18n(self, dashboard, monkeypatch):
        from services.i18n import unregister_listener

        mock_unregister = MagicMock()
        monkeypatch.setattr(
            "ui.views.dashboard.unregister_listener", mock_unregister
        )
        dashboard.shutdown()
        mock_unregister.assert_called_once_with(dashboard._language_callback)

    def test_shutdown_sets_shutting_down(self, dashboard):
        assert not dashboard._shutting_down
        dashboard.shutdown()
        assert dashboard._shutting_down is True


# ── Refresh-all ───────────────────────────────────────────────────────────────


class TestQtFleetDashboardRefreshAll:
    """Error resilience of refresh_all / _load_data."""

    def test_refresh_all_error_handling(self, dashboard, mock_analytics_svc, monkeypatch, qtbot):
        # Prevent QMessageBox.warning from blocking in test mode
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: None,
        )
        mock_analytics_svc.get_financial.side_effect = Exception("Boom")
        # Must not raise
        dashboard.refresh_all()
        qtbot.wait(50)
        assert dashboard._refresh_timer.isActive()

    def test_refresh_all_loads_via_worker_pool(self, dashboard, monkeypatch, qtbot):
        """refresh_all fetches dashboard data off the GUI thread via WorkerPool."""
        from unittest.mock import patch

        calls = []

        def _run_sync(fn, on_result=None, on_error=None, **kwargs):
            """Run the WorkerPool task synchronously (mirrors test_overview)."""
            calls.append(fn)
            if on_result is not None:
                on_result(fn())
            return None

        monkeypatch.setattr("ui.views.dashboard.WorkerPool.run", _run_sync)
        # The constructor's initial refresh cycle has not completed; reset the
        # guard so this call starts a fresh cycle through WorkerPool.
        dashboard._refresh_in_flight = False
        dashboard._refresh_pending = False

        with patch.object(dashboard, "_fetch_data", wraps=dashboard._fetch_data) as spy_fetch:
            dashboard.refresh_all()
            qtbot.wait(50)

        assert len(calls) == 1
        # The background task delegates to the dashboard's data fetcher.
        spy_fetch.assert_called_once()
        # Content still renders (4 KPI cards) via the synchronous on_result.
        assert len(dashboard._kpi_cards) == 4

    def test_worker_pool_error_preserves_failure_behavior(
        self, dashboard, monkeypatch, qtbot
    ):
        """An error raised by the background fetch is surfaced on the main thread."""
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: None,
        )

        def _run_sync_error(fn, on_result=None, on_error=None, **kwargs):
            if on_error is not None:
                on_error("Boom\ntraceback line")
            return None

        monkeypatch.setattr("ui.views.dashboard.WorkerPool.run", _run_sync_error)
        dashboard._refresh_in_flight = False
        dashboard._refresh_pending = False
        # Must not raise and must not leave the guard stuck.
        dashboard.refresh_all()
        qtbot.wait(50)
        assert dashboard._refresh_in_flight is False


# ── KPI Cards ─────────────────────────────────────────────────────────────────


class TestQtFleetDashboardKPI:
    """KPI card row construction and value display."""

    def test_kpi_row_has_four_cards(self, dashboard, qtbot):
        dashboard._load_data()
        qtbot.wait(50)
        assert len(dashboard._kpi_cards) == 4

    def test_kpi_cards_show_correct_values(
        self,
        dashboard,
        mock_analytics_svc,
        mock_fleet_svc,
        mock_trip_svc,
        qtbot,
        monkeypatch,
    ):
        # Prevent QMessageBox from blocking (defensive)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **kw: None,
        )

        # Wire service mocks with known data
        mock_analytics_svc.get_financial.return_value = [{"revenue": 50000.0}]
        mock_analytics_svc.get_fleet.return_value = [
            {
                "truck": "ABC-123",
                "total_fuel_cost": 1500.0,
                "profit": 12000.0,
                "trip_count": 5,
            }
        ]
        mock_analytics_svc.get_driver.return_value = [
            {"driver": "John Doe", "profit": 8000.0, "trip_count": 4}
        ]
        mock_analytics_svc.get_overdue_data.return_value = (
            [{"type": "RED", "msg": "Factura vencida"}],
            None,
        )
        mock_fleet_svc.get_trucks.return_value = [
            {"active_status": 1, "plate_number": "ABC-123"}
        ]
        mock_trip_svc.get_all.return_value = [
            {"start_date": datetime.now().strftime("%Y-%m-%d"), "status": "In Transit"}
        ]

        dashboard._load_data()
        qtbot.wait(50)

        cards = dashboard._kpi_cards
        assert len(cards) == 4

        # active_trucks = 1
        assert cards["fleet_dashboard.kpi_active_trucks"].value_label.text() == "1"
        # trips_today = 1
        assert cards["fleet_dashboard.kpi_trips_today"].value_label.text() == "1"
        # revenue = 50000
        revenue_text = cards["fleet_dashboard.kpi_revenue"].value_label.text()
        assert "50000" in revenue_text or "50,000" in revenue_text or "50.000" in revenue_text
        # alert_count (len of RED alerts with "Factura") = 1
        assert cards["fleet_dashboard.kpi_alerts"].value_label.text() == "1"


# ── Charts ────────────────────────────────────────────────────────────────────


class TestQtFleetDashboardCharts:
    """Chart frame creation and data binding."""

    def test_chart_frames_created(self, dashboard, qtbot):
        dashboard._load_data()
        qtbot.wait(50)
        assert isinstance(dashboard._left_chart_frame, QFrame)
        assert isinstance(dashboard._right_chart_frame, QFrame)

    def test_charts_receive_data(self, dashboard, qtbot):
        render_trip = MagicMock()
        render_fleet = MagicMock()
        dashboard._render_trip_activity_chart = render_trip
        dashboard._render_fleet_status_chart = render_fleet

        dashboard.refresh_all()
        qtbot.wait(50)

        render_trip.assert_called()
        render_fleet.assert_called()


# ── Activity Feed ─────────────────────────────────────────────────────────────


class TestQtFleetDashboardActivityFeed:
    """Activity feed limits the number of visible rows."""

    def test_activity_feed_limited_max(self, dashboard, mock_trip_svc, qtbot):
        trips = [
            {
                "id": i,
                "created_at": "2026-07-23T10:00:00",
                "status": "Delivered",
                "truck_number": f"TRK-{i}",
                "client_name": f"Client {i}",
            }
            for i in range(25)
        ]
        mock_trip_svc.get_all.return_value = trips
        dashboard._load_data()
        qtbot.wait(50)

        # The activity feed sorts trips by id desc and takes at most 10 rows.
        # We verify by counting the QFrame rows inside the activity feed.
        # The rows are children of the feed frame which sits inside a QScrollArea.
        from PySide6.QtWidgets import QScrollArea

        scrolls = dashboard.findChildren(QScrollArea)
        assert len(scrolls) >= 1

        # The activity-feed row frames are grandchildren of the last scroll area.
        # Count the number of immediate QFrame children inside the feed's QFrame.
        feed_scroll = scrolls[-1]  # the right-column scroll area
        feed_frame = feed_scroll.widget()
        if feed_frame is not None:
            # Each trip row is a QFrame added to feed_frame's layout
            row_frames = [
                child
                for child in feed_frame.findChildren(QFrame)
                if child.parent() is feed_frame
            ]
            # Trip rows have 4 child widgets (timestamp, truck, status, client);
            # the header row only has 3 (title + stretch + view-all).
            trip_rows = [
                r for r in row_frames if r.layout() and r.layout().count() >= 4
            ]
            assert len(trip_rows) <= 10


# ── Period Filter ─────────────────────────────────────────────────────────────


class TestQtFleetDashboardPeriodFilter:
    """Period-based date range filtering."""

    def test_period_today_sets_today_range(self, dashboard):
        dashboard._set_period("today")
        today_str = datetime.now().strftime("%Y-%m-%d")
        assert dashboard._start_date == today_str
        assert dashboard._end_date == today_str

    def test_period_filter_dispatches_refresh(self, dashboard, monkeypatch):
        dashboard.refresh_all = MagicMock()
        dashboard._set_period("week")
        dashboard.refresh_all.assert_called_once()


# ── Grid Toggle ───────────────────────────────────────────────────────────────


class TestQtFleetDashboardGridToggle:
    """Chart grid-line visibility toggle."""

    def test_grid_toggle_flips_visible(self, dashboard):
        assert dashboard._grid_visible is True
        dashboard._toggle_grid()
        assert dashboard._grid_visible is False
        dashboard._toggle_grid()
        assert dashboard._grid_visible is True
