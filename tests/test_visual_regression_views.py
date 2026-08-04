"""Visual regression tests for main application views — Phase 9, Stage 9.3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

# ── Workaround: ui.widgets.__init__ imports SP as S but uses SP in several
#    places (lines 225, 258, 259, 296, 297, 319, 380).  Patch the namespace
#    so those lookups succeed at runtime.
import ui.widgets as _ui_widgets

_ui_widgets.SP = _ui_widgets.S

# ── Helper: a real QWidget that behaves like a MagicMock for unknown
#    attributes.  QLayout.addWidget() rejects plain MagicMock instances
#    because it checks the underlying C++ type; using a proper QWidget
#    subclass avoids that while still providing mock semantics.

from unittest.mock import MagicMock as _MagicMock


class _MockQWidget(QWidget):
    """QWidget-compatible mock for MapWidget and similar heavy widgets.

    Layout methods (addWidget) accept this because it IS a QWidget.
    Unknown attributes / methods fall through to an internal MagicMock
    so tests don't crash on ``.set_click_callback()`` etc.
    """

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _MagicMock()


pytestmark = pytest.mark.visual


class TestVisualDashboard:
    """Screenshot tests for QtFleetDashboard."""

    def test_dashboard_empty(self, qt_widget, qtbot, assert_snapshot):
        """Dashboard with no data loaded — shows skeleton/empty state."""
        from ui.views.dashboard import QtFleetDashboard

        # Services are imported lazily inside _load_data(); patch them
        # at their source so the method can complete without real DB.
        with (
            patch("services.analytics_service.AnalyticsService") as MockAna,
            patch("services.fleet_service.FleetService") as MockFlt,
            patch("services.trip_service.TripService") as MockTrp,
        ):
            MockAna.return_value.get_overdue_data.return_value = ([], None)
            MockAna.return_value.get_financial.return_value = []
            MockAna.return_value.get_fleet.return_value = []
            MockAna.return_value.get_driver.return_value = []
            MockFlt.return_value.get_trucks.return_value = []
            MockTrp.return_value.get_all.return_value = []

            # prefs mock: format_currency must return a real string
            prefs = MagicMock()
            prefs.format_currency.return_value = "\u20ac 0"

            dashboard = QtFleetDashboard(
                parent=qt_widget,
                db=MagicMock(),
                prefs=prefs,
                ops=MagicMock(),
            )
            qtbot.addWidget(dashboard)
            dashboard.resize(900, 600)
            # Let skeleton render and data load complete
            assert_snapshot(dashboard, delay_ms=300)
            dashboard.shutdown()


class TestVisualDispatchBoard:
    """Screenshot tests for QtDispatchBoardView."""

    def test_dispatch_board_empty(self, qt_widget, qtbot, assert_snapshot):
        """Dispatch board with no trips — shows empty kanban columns."""
        from ui.views.dispatch_board.dispatch_board import QtDispatchBoardView

        # db=None ensures all services are skipped; only UI is built
        view = QtDispatchBoardView(
            parent=qt_widget,
            db=None,
        )
        qtbot.addWidget(view)
        view.resize(1100, 650)
        assert_snapshot(view, delay_ms=200)
        view.shutdown()


class TestVisualDocumentCenter:
    """Screenshot tests for QtDocumentCenterView."""

    def test_document_center_empty(self, qt_widget, qtbot, assert_snapshot):
        """Document center with no documents — shows empty state."""
        from ui.views.document_center.document_center import QtDocumentCenterView

        # db=None keeps document_service=None, so no data is loaded
        view = QtDocumentCenterView(
            parent=qt_widget,
            db=None,
        )
        qtbot.addWidget(view)
        view.resize(1100, 650)
        assert_snapshot(view, delay_ms=200)
        view.shutdown()


class TestVisualRoutePlanner:
    """Screenshot tests for QtRoutePlannerView (sidebar portion)."""

    def test_route_planner_sidebar(self, qt_widget, qtbot, assert_snapshot):
        """Route planner sidebar controls with no route data."""
        from ui.views.route_planner_view import QtRoutePlannerView

        mock_map_widget = _MockQWidget()

        with (
            patch("ui.views.route_planner_view.MapWidget", return_value=mock_map_widget),
            patch("ui.views.route_planner_view.QtRouteMapRenderer"),
            patch("ui.views.route_planner_view.RouteStateManager"),
            patch("ui.views.route_planner_view.RoutePersistenceService"),
            patch("ui.views.route_planner_view.RouteHistoryService"),
        ):
            # db=None keeps _core=None; only sidebar UI is built
            view = QtRoutePlannerView(
                parent=qt_widget,
                db=None,
                controller=MagicMock(),
                api_client=MagicMock(),
            )
            qtbot.addWidget(view)
            # Narrow width captures only the sidebar before the map
            view.resize(700, 600)
            assert_snapshot(view, delay_ms=200)
            view.shutdown()


class TestVisualFleetTracking:
    """Screenshot tests for QtFleetTrackingView (vehicle panel)."""

    def test_fleet_tracking_sidebar(self, qt_widget, qtbot, assert_snapshot):
        """Fleet tracking vehicle panel with no vehicles."""
        from ui.views.fleet_tracking_view import QtFleetTrackingView

        mock_map = _MockQWidget()

        with (
            patch("ui.views.fleet_tracking_view.MapWidget", return_value=mock_map),
            patch("ui.views.fleet_tracking_view.fleet_tracking_service") as mock_svc,
        ):
            # Make the service appear configured so the full UI is built
            mock_svc.is_configured.return_value = True
            mock_svc.get_positions.return_value = []

            view = QtFleetTrackingView(
                parent=qt_widget,
                db=MagicMock(),
                prefs=MagicMock(),
                ops=MagicMock(),
            )
            qtbot.addWidget(view)
            view.resize(800, 600)
            assert_snapshot(view, delay_ms=200)
            view.shutdown()
