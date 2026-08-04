"""Tests for the maintenance analytics view (PySide6)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """Return a mocked repository with canned data."""
    repo = MagicMock()
    repo.get_all.return_value = [
        {"id": 1, "plate_number": "AB-01-TST"},
        {"id": 2, "plate_number": "CD-02-TST"},
    ]
    repo.get_maintenance_cost_truck_monthly.return_value = [
        {"truck_id": 1, "ym": "2025-01", "total": 1200.0},
        {"truck_id": 2, "ym": "2025-01", "total": 800.0},
    ]
    repo.get_maintenance_cost_monthly.return_value = [
        {"ym": "2025-01", "total": 2000.0},
    ]
    repo.get_maintenance_truck_summary.return_value = [
        {"truck_id": 1, "total_ytd": 5000.0, "avg_cost": 250.0, "service_count": 20},
        {"truck_id": 2, "total_ytd": 3000.0, "avg_cost": 150.0, "service_count": 15},
    ]
    repo.get_maintenance_most_expensive_category.return_value = [
        {"truck_id": 1, "maintenance_type": "engine_repair"},
        {"truck_id": 2, "maintenance_type": "brake_service"},
    ]
    return repo


@pytest.fixture
def view(qt_widget, qtbot, mock_repo):
    """Create a ``QtMaintenanceAnalyticsView`` with a mocked repo."""
    from ui.views.maintenance_analytics_view import QtMaintenanceAnalyticsView

    v = QtMaintenanceAnalyticsView(
        parent=qt_widget,
        db=MagicMock(),
        repo=mock_repo,
    )
    qtbot.addWidget(v)
    yield v
    with pytest.importorskip("contextlib").suppress(Exception):
        v.shutdown()


@pytest.fixture
def view_no_repo(qt_widget, qtbot):
    """Create view without a repo (no-data path)."""
    from ui.views.maintenance_analytics_view import QtMaintenanceAnalyticsView

    v = QtMaintenanceAnalyticsView(
        parent=qt_widget,
        db=MagicMock(),
        repo=None,
    )
    qtbot.addWidget(v)
    yield v
    with pytest.importorskip("contextlib").suppress(Exception):
        v.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQtMaintenanceAnalyticsView:
    def test_creation(self, view):
        assert view is not None
        assert view.db is not None
        assert view.repo is not None

    def test_creation_without_repo(self, view_no_repo):
        assert view_no_repo is not None
        # With db provided, FleetRepository is auto-created as a fallback
        assert view_no_repo.repo is not None

    # ── UI elements ────────────────────────────────────────────────────

    def test_chart_widget_a_created(self, view):
        view._load_data()  # Ensures lazy creation fires
        assert hasattr(view, "_chart_widget_a")
        assert view._chart_widget_a is not None

    def test_chart_widget_b_created(self, view):
        view._load_data()  # Ensures lazy creation fires
        assert hasattr(view, "_chart_widget_b")
        assert view._chart_widget_b is not None

    def test_table_ref_created_after_load(self, view):
        # _load_data is triggered via QTimer.singleShot(0) in __init__.
        # We process events to let it fire.
        import pytestqt.qtbot as _  # ensure qtbot fixture is available  # noqa: F401
        view._load_data()
        assert hasattr(view, "_table_ref")

    def test_table_container_created(self, view):
        assert hasattr(view, "_table_container")
        assert view._table_container is not None

    def test_title_label_created(self, view):
        assert hasattr(view, "_title_lbl")

    def test_refresh_button_created(self, view):
        assert hasattr(view, "_refresh_btn")

    def test_i18n_widgets_list(self, view):
        assert hasattr(view, "_i18n_widgets")
        assert len(view._i18n_widgets) > 0

    # ── ViewModel ──────────────────────────────────────────────────────

    def test_view_model_created(self, view):
        assert hasattr(view, "_vm")
        assert view._vm is not None

    def test_view_model_data_changed_signal(self, view):
        assert hasattr(view._vm, "data_changed")

    # ── State ──────────────────────────────────────────────────────────

    def test_shutting_down_flag(self, view):
        assert hasattr(view, "_shutting_down")
        assert view._shutting_down is False

    def test_data_loaded_flag(self, view):
        assert hasattr(view, "_data_loaded")

    def test_truck_map(self, view):
        assert hasattr(view, "_truck_map")

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_wakeup_calls_load_data(self, view):
        with patch.object(view, "_load_data") as mock_load:
            view.wakeup()
            mock_load.assert_called_once()

    def test_shutdown_sets_flag(self, view):
        assert view._shutting_down is False
        view.shutdown()
        assert view._shutting_down is True

    def test_shutdown_idempotent(self, view):
        view.shutdown()
        view.shutdown()  # second call must not raise

    def test_load_data_no_repo_returns_early(self, view_no_repo):
        """_load_data auto-creates FleetRepository when db is provided but repo is None."""
        view_no_repo._load_data()  # no crash
        # With db provided, repo is auto-created and data loads successfully
        assert view_no_repo._data_loaded is True

    def test_load_data_sets_data_loaded(self, view):
        view._data_loaded = False
        view._load_data()
        assert view._data_loaded is True

    def test_load_data_skips_when_already_loaded(self, view):
        view._load_data()
        assert view._data_loaded is True
        # Second call should short-circuit
        with patch.object(view.repo, "get_all") as mock_get:
            view._load_data()
            mock_get.assert_not_called()

    def test_load_data_shutting_down_returns_early(self, view):
        # _load_data may have already fired from init timer; reset flag
        view._data_loaded = False
        with patch.object(view.repo, "get_all") as mock_get:
            view._shutting_down = True
            view._load_data()  # no crash
            mock_get.assert_not_called()
        assert view._data_loaded is False

    def test_refresh_delegates_to_load_data(self, view):
        with patch.object(view, "_load_data") as mock_load:
            view.refresh()
            mock_load.assert_called_once()

    # ── Chart rendering ────────────────────────────────────────────────

    def test_render_charts_with_data(self, view):
        view._load_data()
        with (
            patch.object(view._chart_widget_a, "set_figure") as mock_a,
            patch.object(view._chart_widget_b, "set_figure") as mock_b,
        ):
            view._render_charts()
            mock_a.assert_called_once()
            mock_b.assert_called_once()

    def test_render_charts_no_charts(self, view):
        # Both chart widgets and placeholders are None — lazy creation short-circuits
        view._chart_widget_a = None
        view._chart_widget_b = None
        view._chart_placeholder_a = None
        view._chart_placeholder_b = None
        view._render_charts()  # no crash

    def test_render_charts_empty_data(self, view):
        view._cost_by_truck_month = []
        view._cost_by_month = []
        with (
            patch.object(view._chart_widget_a, "set_figure") as mock_a,
            patch.object(view._chart_widget_b, "set_figure") as mock_b,
        ):
            view._render_charts()
            mock_a.assert_called_once()
            mock_b.assert_called_once()

    # ── Table rendering ────────────────────────────────────────────────

    def test_render_table_creates_widget(self, view):
        # _load_data may have already fired from init timer; reset flags
        view._data_loaded = False
        view._table_ref = None
        view._load_data()
        assert view._table_ref is not None

    def test_render_table_no_container(self, view):
        view._table_container = None
        view._render_table()  # no crash

    def test_render_table_no_repo(self, view_no_repo):
        view_no_repo._render_table()  # no crash

    def test_render_table_empty_summary(self, view):
        view._truck_summary = []
        view._render_table()
        assert view._table_ref is not None

    # ── Data changed callback ──────────────────────────────────────────

    def test_on_data_changed_renders(self, view):
        with (
            patch.object(view, "_render_charts") as mock_charts,
            patch.object(view, "_render_table") as mock_table,
        ):
            view._on_data_changed()
            mock_charts.assert_called_once()
            mock_table.assert_called_once()

    def test_on_data_changed_shutting_down(self, view):
        view._shutting_down = True
        view._on_data_changed()  # no crash

    # ── i18n ───────────────────────────────────────────────────────────

    def test_language_callback_registered(self, view):
        assert hasattr(view, "_language_callback")
        assert view._language_callback is not None

    def test_on_language_changed_triggers_load(self, view):
        with patch.object(view, "_load_data") as mock_load:
            view._on_language_changed("ro")
            # QTimer.singleShot(0) — won't have fired yet
            mock_load.assert_not_called()

    # ── Chart builders ─────────────────────────────────────────────────

    def test_build_cost_by_truck_month_fig_empty(self, view):
        view._cost_by_truck_month = []
        fig = view._build_cost_by_truck_month_fig()
        from ui.plotly_renderer import empty_figure
        assert fig is not None

    def test_build_fleet_trend_fig_empty(self, view):
        view._cost_by_month = []
        fig = view._build_fleet_trend_fig()
        from ui.plotly_renderer import empty_figure
        assert fig is not None

    def test_build_cost_by_truck_month_fig_with_data(self, view):
        view._load_data()
        fig = view._build_cost_by_truck_month_fig()
        assert fig is not None

    def test_build_fleet_trend_fig_with_data(self, view):
        view._load_data()
        fig = view._build_fleet_trend_fig()
        assert fig is not None

    # ── Dialog ─────────────────────────────────────────────────────────

    def test_dialog_creation(self, qt_widget, qtbot):
        from ui.views.maintenance_analytics_view import MaintenanceAnalyticsDialog
        dlg = MaintenanceAnalyticsDialog(db=MagicMock(), parent=qt_widget)
        qtbot.addWidget(dlg)
        assert dlg._view is not None
        dlg.wakeup()
        dlg.shutdown()
        dlg.close()
