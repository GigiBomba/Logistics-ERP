"""Tests for the route planner view (QtRoutePlannerView)."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QPushButton, QStackedWidget, QWidget

# ── SP workaround ──────────────────────────────────────────────────────────
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_route_controller():
    core = MagicMock()
    core.cost_engine = MagicMock()
    core.country_avoidance = MagicMock()
    core.country_avoidance.get_selected.return_value = []
    core.validate_calculation_input.return_value = (MagicMock(), None)
    core.process_calculation_result.return_value = (MagicMock(), None)
    core.cancel_calculation = MagicMock()
    core.get_excluded_countries.return_value = []
    return core


@pytest.fixture
def mock_fleet_service_route():
    svc = MagicMock()
    svc.get_trucks.return_value = [
        {
            "id": 1,
            "plate_number": "B-123-ABC",
            "model": "Volvo FH",
            "active_status": 1,
        }
    ]
    return svc


class _FakeMapWidget(QWidget):
    """QWidget subclass that ducks the MapWidget interface used by _build_ui."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loadFinished = MagicMock()

    def set_click_callback(self, cb):
        self._test_cb = cb

    def setMinimumWidth(self, w):
        pass

    def _run_js(self, js):
        pass


@pytest.fixture
def route_planner(
    qt_widget, qtbot, monkeypatch, mock_db, mock_route_controller, mock_fleet_service_route
):
    from ui.views.route_planner_view import QtRoutePlannerView

    monkeypatch.setattr(
        "ui.views.route_planner_view.MapWidget", lambda *a, **kw: _FakeMapWidget()
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.QtRouteMapRenderer",
        lambda *a, **kw: MagicMock(),
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.RouteStateManager", lambda db: MagicMock()
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.RoutePersistenceService",
        lambda *a, **kw: MagicMock(),
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.RouteHistoryService", lambda db: MagicMock()
    )
    view = QtRoutePlannerView(
        qt_widget,
        db=mock_db,
        controller=MagicMock(),
        api_client=MagicMock(),
        route_controller=mock_route_controller,
        fleet_service=mock_fleet_service_route,
    )
    qtbot.addWidget(view)
    yield view
    with contextlib.suppress(Exception):
        view.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Initialisation
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewInit:
    def test_creation_stores_references(self, route_planner):
        assert route_planner.db is not None
        assert route_planner.controller is not None
        assert route_planner._api_client is not None

    def test_sidebar_has_stops_container(self, route_planner):
        assert hasattr(route_planner, "_stops_container")
        assert isinstance(route_planner._stops_container, QWidget)

    def test_map_widget_created(self, route_planner):
        assert hasattr(route_planner, "map_widget")
        assert route_planner.map_widget is not None

    def test_calculate_button_created(self, route_planner):
        assert hasattr(route_planner, "calc_btn")
        assert isinstance(route_planner.calc_btn, QPushButton)
        assert route_planner.calc_btn.isEnabled() is False

    def test_profile_combo_populated(self, route_planner):
        assert hasattr(route_planner, "profile_combo")
        assert route_planner.profile_combo.count() > 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Stops
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewStops:
    def test_initial_stops_are_start_and_destination(self, route_planner):
        assert len(route_planner.stops_state) == 2
        assert route_planner.stops_state[0]["type"] == "start"
        assert route_planner.stops_state[1]["type"] == "destination"

    def test_add_stop_inserts_before_destination(self, route_planner):
        route_planner._add_stop_field()
        assert len(route_planner.stops_state) == 3
        assert route_planner.stops_state[0]["type"] == "start"
        assert route_planner.stops_state[1]["type"] == "stop"
        assert route_planner.stops_state[2]["type"] == "destination"

    def test_remove_stop_protects_first_and_last(self, route_planner):
        route_planner._add_stop_field()
        initial_len = len(route_planner.stops_state)
        # Removing index 0 (start) should be a no-op
        route_planner._remove_stop_index(0)
        assert len(route_planner.stops_state) == initial_len
        # Removing last index (destination) should be a no-op
        route_planner._remove_stop_index(len(route_planner.stops_state) - 1)
        assert len(route_planner.stops_state) == initial_len

    def test_remove_stop_deletes_middle(self, route_planner):
        route_planner._add_stop_field()
        route_planner._add_stop_field()
        route_planner._add_stop_field()
        assert len(route_planner.stops_state) == 5
        route_planner._remove_stop_index(1)
        assert len(route_planner.stops_state) == 4

    def test_stop_text_change_updates_stop_vars(self, route_planner):
        sid = route_planner.stops_state[0].get("id", "test_id")
        route_planner._on_stop_text_changed(sid, "Bucuresti")
        assert route_planner.stop_vars.get(sid) == "Bucuresti"

    def test_calc_button_enabled_with_addresses(self, route_planner):
        # Initially disabled
        assert route_planner.calc_btn.isEnabled() is False
        # Set addresses for start and destination
        for i, stop in enumerate(route_planner.stops_state):
            sid = stop.get("id", f"s{i}")
            route_planner.stop_vars[sid] = f"Address {i}"
        route_planner._update_calc_button_state()
        assert route_planner.calc_btn.isEnabled() is True


# ═══════════════════════════════════════════════════════════════════════════
# 3. Calculation
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewCalculation:
    def test_on_calculate_validates_input(self, route_planner):
        route_planner._core.validate_calculation_input.reset_mock()
        route_planner._on_calculate_click()
        route_planner._core.validate_calculation_input.assert_called()

    def test_on_calculate_shows_error_on_fail(self, route_planner):
        route_planner._core.validate_calculation_input.return_value = (
            None,
            "Test error",
        )
        route_planner._on_calculate_click()
        assert route_planner._result_stack.currentIndex() == 0

    def test_on_calculate_starts_calculation(self, route_planner):
        route_planner._core.validate_calculation_input.return_value = (
            MagicMock(),
            None,
        )
        route_planner._on_calculate_click()
        route_planner._core.start_calculation.assert_called()

    def test_on_route_result_stale_token_ignored(self, route_planner):
        # Set calc_token to 1 then emit with token 0 (stale)
        route_planner._calc_token = 1
        route_planner._core.process_calculation_result.reset_mock()
        route_planner._on_route_result(MagicMock(), MagicMock(), 0)
        route_planner._core.process_calculation_result.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# 4. Results
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewResults:
    def test_route_result_displays_pills(self, route_planner):
        result = {
            "distance_km": 150.0,
            "duration_min": 120.0,
            "stops": [[25.0, 45.0], [26.0, 46.0]],
        }
        processed = MagicMock()
        processed.route = result
        processed.cost_info = {"fuel_cost": 45.0}
        processed.compliance = None
        route_planner._core.process_calculation_result.return_value = (
            processed,
            None,
        )
        # Simulate route result
        route_planner._calc_token = 1
        route_planner._on_route_result(result, MagicMock(), 1)
        # Pills should be populated (value labels set to formatted text)
        assert route_planner.pill_distance.value_label.text() != "\u2014"

    def test_dispatch_buttons_visible(self, route_planner):
        result = {
            "distance_km": 100.0,
            "duration_min": 60.0,
            "stops": [[25.0, 45.0], [26.0, 46.0]],
        }
        processed = MagicMock()
        processed.route = result
        processed.cost_info = {"fuel_cost": 45.0}
        processed.compliance = None
        route_planner._core.process_calculation_result.return_value = (
            processed,
            None,
        )
        route_planner._calc_token = 1
        route_planner._on_route_result(result, MagicMock(), 1)
        # The dispatch container was hidden by default and then shown by
        # _show_dispatch_buttons.  isVisibleTo checks relative visibility
        # within the widget hierarchy regardless of top-level show state.
        assert route_planner._dispatch_container.isVisibleTo(
            route_planner
        ) is True

    def test_create_trip_noop_without_result(self, route_planner):
        route_planner._last_route_result = None
        # Should not raise
        route_planner._on_create_trip()


# ═══════════════════════════════════════════════════════════════════════════
# 5. Truck Loading
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewTruckLoading:
    def test_load_trucks_populates_combo(self, route_planner):
        assert hasattr(route_planner, "truck_combo")
        route_planner._on_trucks_loaded(
            {
                "trucks": [
                    {
                        "id": 1,
                        "plate_number": "B-123-ABC",
                        "model": "Volvo FH",
                    }
                ]
            }
        )
        assert route_planner.truck_combo.count() > 0

    def test_truck_selection_updates_selected_id(self, route_planner):
        route_planner._on_trucks_loaded(
            {
                "trucks": [
                    {
                        "id": 42,
                        "plate_number": "B-456-XYZ",
                        "model": "Scania",
                    }
                ]
            }
        )
        route_planner.truck_combo.setCurrentIndex(0)
        assert route_planner._selected_truck_id == "42"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Share / Export
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewShareExport:
    def test_share_route_noop_without_result(self, route_planner):
        route_planner._last_route_result = None
        # Should not raise
        route_planner._on_share_route()

    def test_open_in_gmaps_no_result(self, route_planner):
        route_planner._last_route_result = None
        # Should return early without raising
        route_planner._on_open_in_gmaps()


# ═══════════════════════════════════════════════════════════════════════════
# 7. Map
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewMap:
    def test_map_click_disabled_by_default(self, route_planner):
        assert route_planner._click_to_add_enabled is False

    def test_toggle_click_add_enables(self, route_planner):
        route_planner._toggle_click_add(True)
        assert route_planner._click_to_add_enabled is True


# ═══════════════════════════════════════════════════════════════════════════
# 8. History
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewHistory:
    def test_load_history_route_populates_stops(self, route_planner):
        from services.route_history_service import RouteHistoryRecord

        record = MagicMock(spec=RouteHistoryRecord)
        patch = {
            "stops": [
                {"type": "start", "address": "Berlin", "lat": 52.52, "lon": 13.40},
                {
                    "type": "stop",
                    "address": "Warsaw",
                    "lat": 52.23,
                    "lon": 21.01,
                },
                {
                    "type": "destination",
                    "address": "Minsk",
                    "lat": 53.90,
                    "lon": 27.56,
                },
            ],
            "profile_label": "Recommended",
            "truck_id": 1,
            "excluded_countries": [],
            "route": {
                "distance_km": 800.0,
                "duration_min": 480.0,
                "stops": [[52.52, 13.40], [52.23, 21.01], [53.90, 27.56]],
            },
        }
        route_planner._core.load_history_record.return_value = patch
        route_planner.load_history_route(record)
        assert len(route_planner.stops_state) == 3
        assert route_planner.stops_state[0]["address"] == "Berlin"
        assert route_planner.stops_state[-1]["address"] == "Minsk"


# ═══════════════════════════════════════════════════════════════════════════
# 9. Lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewLifecycle:
    def test_wakeup_clears_pending_state(self, route_planner):
        route_planner._pending_clear = True
        route_planner.wakeup()
        assert route_planner._pending_clear is False

    def test_wakeup_recreates_map(self, route_planner):
        # Destroy the map widget to simulate a prior shutdown
        old_map = route_planner.map_widget
        old_map_id = id(old_map)
        # Properly delete the underlying C++ object so that
        # wakeup()'s isWidgetType() guard raises RuntimeError.
        import shiboken6
        shiboken6.delete(old_map)
        route_planner.wakeup()
        assert id(route_planner.map_widget) != old_map_id

    def test_shutdown_unregisters_i18n(self, route_planner):
        with patch(
            "ui.views.route_planner_view.unregister_listener"
        ) as mock_unreg:
            route_planner.shutdown()
            mock_unreg.assert_called()

    def test_shutdown_unsubscribes_event_bus(self, route_planner):
        route_planner.shutdown()
        assert route_planner._event_subscribed is False

    def test_shutdown_cancels_calculation(self, route_planner):
        route_planner.shutdown()
        route_planner._core.cancel_calculation.assert_called()


# ═══════════════════════════════════════════════════════════════════════════
# 10. i18n
# ═══════════════════════════════════════════════════════════════════════════


class TestQtRoutePlannerViewI18N:
    def test_on_language_changed_rebuilds_profiles(self, route_planner):
        original_count = route_planner.profile_combo.count()
        route_planner._on_language_changed("ro")
        # Profile combo should still have items (refreshed)
        assert route_planner.profile_combo.count() == original_count
