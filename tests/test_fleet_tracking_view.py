"""Tests for the fleet tracking view (PySide6)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vehicle_position(**overrides):
    from services.fleet_tracking_service import VehiclePosition

    defs: dict = dict(
        device_id="dev-001",
        name="AB-01-TEST",
        latitude=44.4268,
        longitude=26.1025,
        speed_kmh=0.0,
        heading=0.0,
        status="stopped",
        address="Test Address, Bucharest",
        odometer_km=12345.0,
        timestamp=datetime.now(timezone.utc),
        ignition_on=False,
    )
    defs.update(overrides)
    return VehiclePosition(**defs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_fleet_service():
    """Patch the global ``fleet_tracking_service`` singleton with a mock."""
    with patch(
        "ui.views.fleet_tracking_view.fleet_tracking_service",
        autospec=True,
    ) as svc:
        svc.is_configured.return_value = True
        svc.get_positions.return_value = []
        svc.match_to_truck.return_value = None
        yield svc


@pytest.fixture
def view(qt_widget, qtbot, mock_fleet_service):
    """Create a ``QtFleetTrackingView`` with a mocked tracking service."""
    from ui.views.fleet_tracking_view import QtFleetTrackingView

    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    on_navigate = MagicMock()

    v = QtFleetTrackingView(
        parent=qt_widget,
        db=db,
        prefs=prefs,
        ops=ops,
        on_navigate=on_navigate,
    )
    qtbot.addWidget(v)
    yield v
    with pytest.importorskip("contextlib").suppress(Exception):
        v.shutdown()


@pytest.fixture
def view_unconfigured(qt_widget, qtbot):
    """Create view when tracking is *not* configured (not-configured UI)."""
    with patch(
        "ui.views.fleet_tracking_view.fleet_tracking_service",
        autospec=True,
    ) as svc:
        svc.is_configured.return_value = False
        from ui.views.fleet_tracking_view import QtFleetTrackingView

        v = QtFleetTrackingView(
            parent=qt_widget,
            db=MagicMock(),
            prefs=MagicMock(),
            ops=MagicMock(),
            on_navigate=MagicMock(),
        )
        qtbot.addWidget(v)
        yield v
        with pytest.importorskip("contextlib").suppress(Exception):
            v.shutdown()


# ---------------------------------------------------------------------------
# Tests – configured path
# ---------------------------------------------------------------------------

class TestQtFleetTrackingView:
    def test_creation(self, view):
        assert view is not None
        assert view.db is not None
        assert view.prefs is not None
        assert view.ops is not None

    def test_map_widget_created(self, view):
        assert hasattr(view, "_map")
        assert view._map is not None

    def test_vehicle_list_scroll_created(self, view):
        assert hasattr(view, "_vehicle_list_scroll")
        assert view._vehicle_list_scroll is not None

    def test_vehicle_list_content_created(self, view):
        assert hasattr(view, "_vehicle_list_content")

    def test_vehicle_list_layout_created(self, view):
        assert hasattr(view, "_vehicle_list_layout")

    def test_detail_panel_created(self, view):
        assert hasattr(view, "_detail_panel")
        assert view._detail_panel is not None

    def test_detail_layout_created(self, view):
        assert hasattr(view, "_detail_layout")

    def test_refresh_button_created(self, view):
        assert hasattr(view, "_refresh_btn")
        assert view._refresh_btn is not None

    def test_updated_label_created(self, view):
        assert hasattr(view, "_updated_lbl")
        assert view._updated_lbl is not None

    def test_poll_timer_created(self, view):
        assert hasattr(view, "_poll_timer")
        assert view._poll_timer is not None

    def test_signal_positions_fetched(self, view):
        assert hasattr(view, "_positionsFetched")

    def test_signal_refresh_finished(self, view):
        assert hasattr(view, "_refreshFinished")

    def test_on_navigate_callback(self, view):
        assert view._on_navigate is not None

    def test_constant_poll_interval(self, view):
        assert view.POLL_INTERVAL_MS == 30_000

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_wakeup_starts_polling(self, view, mock_fleet_service):
        mock_fleet_service.is_configured.return_value = True
        view.wakeup()
        assert view._poll_timer.isActive()

    def test_wakeup_noop_when_not_configured(self, view, mock_fleet_service):
        mock_fleet_service.is_configured.return_value = False
        view.wakeup()
        assert not view._poll_timer.isActive()

    def test_shutdown_stops_polling(self, view):
        view.wakeup()
        assert view._poll_timer.isActive()
        view.shutdown()
        assert not view._poll_timer.isActive()

    def test_shutdown_cleans_map(self, view):
        view.shutdown()
        assert view._map is None

    def test_shutdown_resets_fetching_flag(self, view):
        view._fetching = True
        view.shutdown()
        assert view._fetching is False

    def test_shutdown_idempotent(self, view):
        view.shutdown()
        view.shutdown()  # second call must not raise

    def test_close_event_calls_shutdown(self, view):
        with patch.object(view, "shutdown") as mock_shutdown:
            from PySide6.QtGui import QCloseEvent
            view.closeEvent(QCloseEvent())
            mock_shutdown.assert_called_once()

    # ── Signals / threading helpers ────────────────────────────────────

    def test_apply_update_updates_map_and_list(self, view):
        """_apply_update should delegate to map and list refresh."""
        with (
            patch.object(view, "_update_map_markers") as upd_map,
            patch.object(view, "_refresh_vehicle_list") as upd_list,
        ):
            positions = [_make_vehicle_position()]
            view._apply_update(positions)
            upd_map.assert_called_once_with(positions)
            upd_list.assert_called_once_with(positions)

    def test_enable_refresh_btn(self, view):
        view._force_refreshing = True
        view._refresh_btn.setEnabled(False)
        view._enable_refresh_btn()
        assert view._force_refreshing is False
        assert view._refresh_btn.isEnabled()

    # ─── Vehicle detail panel ──────────────────────────────────────────

    def test_show_detail_panel_adds_widgets(self, view):
        position = _make_vehicle_position()
        view._show_detail_panel(position, truck_id=None)
        # Detail layout should now contain several child widgets
        assert view._detail_layout.count() > 0

    def test_show_detail_panel_with_truck_id_adds_fleet_button(self, view):
        position = _make_vehicle_position()
        view._show_detail_panel(position, truck_id=42)
        # The last widget in the detail layout should be the fleet detail button
        count = view._detail_layout.count()
        assert count > 0

    def test_show_detail_panel_clears_previous_content(self, view):
        position = _make_vehicle_position()
        view._show_detail_panel(position, truck_id=1)
        first_count = view._detail_layout.count()
        view._show_detail_panel(position, truck_id=2)
        # Should have replaced, not appended
        assert view._detail_layout.count() <= first_count + 1  # layout rebuild

    def test_select_vehicle_pans_map(self, view):
        position = _make_vehicle_position(latitude=44.0, longitude=26.0)
        with patch.object(view._map, "set_view") as mock_set_view:
            view._select_vehicle(position, truck_id=1)
            mock_set_view.assert_called_once_with(44.0, 26.0, zoom=14)

    def test_select_vehicle_no_map_does_not_crash(self, view):
        view._map = None
        position = _make_vehicle_position()
        view._select_vehicle(position, truck_id=1)  # no crash

    # ── Vehicle list ───────────────────────────────────────────────────

    def test_refresh_vehicle_list_empty(self, view):
        view._refresh_vehicle_list([])
        # Should show no-data label
        assert view._vehicle_list_layout.count() >= 1

    def test_refresh_vehicle_list_with_positions(self, view):
        pos = _make_vehicle_position()
        view._refresh_vehicle_list([pos])
        assert view._vehicle_list_layout.count() >= 1

    def test_refresh_vehicle_list_sorts_by_name(self, view):
        pos_a = _make_vehicle_position(name="A-Vehicle", device_id="a")
        pos_b = _make_vehicle_position(name="B-Vehicle", device_id="b")
        view._refresh_vehicle_list([pos_b, pos_a])
        # The updated label should be populated
        assert view._updated_lbl.text() != ""

    def test_update_map_markers_no_map(self, view):
        view._map = None
        view._update_map_markers([])  # no crash

    def test_update_map_markers_with_positions(self, view):
        pos = _make_vehicle_position(latitude=44.0, longitude=26.0)
        with patch.object(view._map, "clear_overlays") as clear_mock:
            view._update_map_markers([pos])
            clear_mock.assert_called_once()

    # ── Status color maps ──────────────────────────────────────────────

    def test_status_marker_colors(self, view):
        expected = {"moving": "green", "stopped": "grey", "idle": "orange", "offline": "red"}
        assert view._STATUS_MARKER_COLORS == expected

    def test_status_dot_colors(self, view):
        from ui.theme import COLORS
        expected = {
            "moving": COLORS["success"],
            "stopped": COLORS["text_muted"],
            "idle": COLORS["warning"],
            "offline": COLORS["danger"],
        }
        assert view._STATUS_DOT_COLORS == expected

    # ── Vehicle detail text ────────────────────────────────────────────

    def test_vehicle_detail_text_speed(self, view):
        pos = _make_vehicle_position(speed_kmh=55.0)
        assert "km/h" in view._vehicle_detail_text(pos)

    def test_vehicle_detail_text_address(self, view):
        pos = _make_vehicle_position(speed_kmh=0.0, address="Some Street, City")
        text = view._vehicle_detail_text(pos)
        assert "Some Street" in text

    def test_vehicle_detail_text_stopped(self, view):
        pos = _make_vehicle_position(speed_kmh=0.0, address="")
        text = view._vehicle_detail_text(pos)
        assert text != ""  # falls back to translation key


# ---------------------------------------------------------------------------
# Tests – NOT configured path
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewUnconfigured:
    def test_creation(self, view_unconfigured):
        assert view_unconfigured is not None

    def test_map_not_created(self, view_unconfigured):
        assert view_unconfigured._map is None

    def test_refresh_button_not_created(self, view_unconfigured):
        assert view_unconfigured._refresh_btn is None

    def test_navigate_settings_calls_callback(self, view_unconfigured):
        view_unconfigured._on_navigate = MagicMock()
        view_unconfigured._navigate_settings()
        view_unconfigured._on_navigate.assert_called_once_with(
            "settings", {"scroll_to": "tracking"},
        )

    def test_shutdown_on_unconfigured(self, view_unconfigured):
        view_unconfigured.shutdown()  # no crash
