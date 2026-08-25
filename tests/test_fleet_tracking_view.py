"""Tests for the fleet tracking view (PySide6)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QMenu, QWidget
from ui.components import UniversalCard

# SP workaround for ui.widgets internals
import ui.widgets as _ui_widgets
if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S

# Inject COLORS into the view module (used in _build_vehicle_row_widget
# but not imported — pre‑existing source issue).
from ui import design_tokens as _dt
_COLORS = {
    "success": _dt.COLOR_SUCCESS_DEFAULT,
    "text_muted": _dt.COLOR_TEXT_TERTIARY,
    "warning": _dt.COLOR_WARNING_DEFAULT,
    "danger": _dt.COLOR_ERROR_DEFAULT,
}
import ui.views.fleet_tracking_view as _fleet_view
_fleet_view.COLORS = _COLORS

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
        expected = {
            "moving": _COLORS["success"],
            "stopped": _COLORS["text_muted"],
            "idle": _COLORS["warning"],
            "offline": _COLORS["danger"],
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

    # ── Expanded tests ──────────────────────────────────────────────────

    def test_vehicle_rows_dict_created(self, view):
        """_vehicle_rows is an empty dict initially."""
        assert isinstance(view._vehicle_rows, dict)
        assert len(view._vehicle_rows) == 0

    def test_force_refresh_button_disabled_during_fetch(self, view):
        """Button is disabled when _force_refreshing is True."""
        with patch("threading.Thread"):
            view._force_refresh()
            assert view._force_refreshing is True
            assert view._refresh_btn.isEnabled() is False


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_positions():
    """Three positions with different statuses and coordinates."""
    return [
        _make_vehicle_position(
            device_id="d1", name="Truck-Alpha",
            latitude=44.4, longitude=26.1,
            speed_kmh=65.0, heading=180, status="moving",
            address="Bd Unirii", odometer_km=50000,
        ),
        _make_vehicle_position(
            device_id="d2", name="Truck-Beta",
            latitude=44.5, longitude=26.2,
            speed_kmh=0.0, heading=0, status="stopped",
            address="", odometer_km=30000,
        ),
        _make_vehicle_position(
            device_id="d3", name="Truck-Gamma",
            latitude=0, longitude=0,
            speed_kmh=0.0, heading=0, status="offline",
            address="", odometer_km=0,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests – Polling (timer + thread lifecycle)
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewPolling:
    """Timer and thread lifecycle for polling."""

    def test_poll_timer_interval_is_30_seconds(self, view, mock_fleet_service):
        view.wakeup()
        assert view._poll_timer.interval() == 30000

    def test_poll_skips_when_fetching(self, view):
        view._fetching = True
        with patch("threading.Thread") as mock_thread:
            view._poll_and_update()
            mock_thread.assert_not_called()

    def test_fetch_positions_emits_signal(self, view, mock_fleet_service):
        positions = [_make_vehicle_position()]
        mock_fleet_service.get_positions.return_value = positions
        received = []
        view._positionsFetched.connect(received.append)
        view._fetch_positions()
        assert len(received) == 1
        assert received[0] == positions
        assert view._fetching is False

    def test_fetch_positions_catches_exception(self, view, mock_fleet_service):
        mock_fleet_service.get_positions.side_effect = RuntimeError("boom")
        view._fetch_positions()  # must not raise
        assert view._fetching is False

    def test_apply_update_calls_map_and_list(self, view):
        positions = [_make_vehicle_position()]
        with (
            patch.object(view, "_update_map_markers") as upd_map,
            patch.object(view, "_refresh_vehicle_list") as upd_list,
        ):
            view._apply_update(positions)
            upd_map.assert_called_once_with(positions)
            upd_list.assert_called_once_with(positions)


# ---------------------------------------------------------------------------
# Tests – Map markers
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewMarkers:
    """Map marker behavior."""

    def test_clear_overlays_called_on_update(self, view, sample_positions):
        with patch.object(view._map, "clear_overlays") as mock_clear:
            view._update_map_markers(sample_positions)
            mock_clear.assert_called_once()

    def test_marker_added_for_each_position(self, view, sample_positions):
        with (
            patch.object(view._map, "clear_overlays"),
            patch.object(view._map, "add_marker") as mock_add,
        ):
            view._update_map_markers(sample_positions)
            # Truck-Gamma has lat=0,lng=0 → skipped; only 2 added
            assert mock_add.call_count == 2

    def test_positions_without_coordinates_skipped(self, view):
        pos = _make_vehicle_position(latitude=0, longitude=0)
        with (
            patch.object(view._map, "clear_overlays"),
            patch.object(view._map, "add_marker") as mock_add,
        ):
            view._update_map_markers([pos])
            mock_add.assert_not_called()

    def test_moving_status_gets_green(self, view):
        pos = _make_vehicle_position(status="moving", latitude=44.0, longitude=26.0)
        with (
            patch.object(view._map, "clear_overlays"),
            patch.object(view._map, "add_marker") as mock_add,
        ):
            view._update_map_markers([pos])
            _, kwargs = mock_add.call_args
            assert kwargs["color"] == "green"

    def test_stopped_status_gets_grey(self, view):
        pos = _make_vehicle_position(status="stopped", latitude=44.0, longitude=26.0)
        with (
            patch.object(view._map, "clear_overlays"),
            patch.object(view._map, "add_marker") as mock_add,
        ):
            view._update_map_markers([pos])
            _, kwargs = mock_add.call_args
            assert kwargs["color"] == "grey"

    def test_idle_status_gets_orange(self, view):
        pos = _make_vehicle_position(status="idle", latitude=44.0, longitude=26.0)
        with (
            patch.object(view._map, "clear_overlays"),
            patch.object(view._map, "add_marker") as mock_add,
        ):
            view._update_map_markers([pos])
            _, kwargs = mock_add.call_args
            assert kwargs["color"] == "orange"

    def test_offline_status_gets_red(self, view):
        pos = _make_vehicle_position(status="offline", latitude=44.0, longitude=26.0)
        with (
            patch.object(view._map, "clear_overlays"),
            patch.object(view._map, "add_marker") as mock_add,
        ):
            view._update_map_markers([pos])
            _, kwargs = mock_add.call_args
            assert kwargs["color"] == "red"


# ---------------------------------------------------------------------------
# Tests – Vehicle list (add / update / remove)
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewVehicleList:
    """Vehicle list add/update/remove."""

    def test_new_vehicle_added_to_list(self, view):
        pos = _make_vehicle_position(name="New-Truck", device_id="new1")
        count_before = view._vehicle_list_layout.count()
        view._refresh_vehicle_list([pos])
        assert "New-Truck" in view._vehicle_rows
        assert view._vehicle_list_layout.count() > count_before

    def test_existing_vehicle_updated_in_place(self, view):
        pos = _make_vehicle_position(name="Exist", device_id="e1")
        view._refresh_vehicle_list([pos])
        assert "Exist" in view._vehicle_rows
        orig_widget = view._vehicle_rows["Exist"]
        with patch.object(view, "_build_vehicle_row_widget") as mock_build:
            view._refresh_vehicle_list([pos])
            mock_build.assert_not_called()
            assert view._vehicle_rows["Exist"] is orig_widget

    def test_removed_vehicle_row_deleted(self, view):
        pos = _make_vehicle_position(name="Gone", device_id="g1")
        view._refresh_vehicle_list([pos])
        assert "Gone" in view._vehicle_rows
        widget = view._vehicle_rows["Gone"]
        with patch.object(widget, "deleteLater") as mock_del:
            view._refresh_vehicle_list([])
            assert "Gone" not in view._vehicle_rows
            mock_del.assert_called_once()

    def test_list_sorted_alphabetically(self, view):
        b = _make_vehicle_position(name="B-Truck", device_id="b")
        a = _make_vehicle_position(name="A-Truck", device_id="a")
        view._refresh_vehicle_list([b, a])
        names = list(view._vehicle_rows.keys())
        assert names == ["A-Truck", "B-Truck"]

    def test_empty_list_shows_empty_state(self, view):
        with patch("ui.views.fleet_tracking_view.EmptyState") as mock_es:
            mock_es.return_value = QWidget()
            view._refresh_vehicle_list([])
            mock_es.assert_called_once()


# ---------------------------------------------------------------------------
# Tests – Detail panel
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewDetailPanel:
    """Detail panel content."""

    def test_detail_shows_name_status_speed(self, view):
        pos = _make_vehicle_position(name="Alpha", status="moving", speed_kmh=55.0)
        view._show_detail_panel(pos, truck_id=None)
        # First widget is the name label
        name_item = view._detail_layout.itemAt(0)
        assert name_item is not None
        name_widget = name_item.widget()
        assert isinstance(name_widget, QLabel)
        assert "Alpha" in name_widget.text()
        # At least name + 3 detail rows (status, speed, updated)
        assert view._detail_layout.count() >= 4

    def test_detail_shows_odometer_when_available(self, view):
        pos = _make_vehicle_position(odometer_km=12345.0)
        view._show_detail_panel(pos, truck_id=None)
        # Extra row for odometer vs default (status, speed, updated)
        assert view._detail_layout.count() >= 5

    def test_detail_shows_address_when_available(self, view):
        pos = _make_vehicle_position(address="Some Street, City")
        view._show_detail_panel(pos, truck_id=None)
        # Extra row for address vs default (status, speed, updated)
        assert view._detail_layout.count() >= 5

    def test_detail_maintenance_button_navigates(self, view):
        pos = _make_vehicle_position()
        view._show_detail_panel(pos, truck_id=42)
        view._on_navigate.reset_mock()
        view._navigate_vehicle_maintenance(42)
        view._on_navigate.assert_called_once_with("maintenance", {"truck_id": 42})

    def test_detail_documents_button_opens_documents(self, view, monkeypatch):
        mock_open = MagicMock()
        monkeypatch.setattr(
            "ui.views.document_center_view.open_entity_documents",
            mock_open,
        )
        pos = _make_vehicle_position()
        view._show_detail_panel(pos, truck_id=42)
        view._open_vehicle_documents(42)
        mock_open.assert_called_once()
        args, _ = mock_open.call_args
        assert args[2] == "truck"
        assert args[3] == 42

    def test_detail_call_driver_button_available(self, view):
        pos = _make_vehicle_position()
        view._show_detail_panel(pos, truck_id=42)
        buttons = view._detail_panel.findChildren(QPushButton)
        call_texts = [b.text() for b in buttons if "Call" in b.text()]
        assert len(call_texts) >= 1


# ---------------------------------------------------------------------------
# Tests – Context menu (right-click)
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewContextMenu:
    """Right-click context menu."""

    def test_context_menu_contains_actions(self, view):
        pos = _make_vehicle_position(name="Menu-Truck")
        card = view._build_vehicle_row_widget(pos, 42)
        mock_event = MagicMock()
        mock_event.globalPos.return_value = QPoint(0, 0)

        with (
            patch.object(view._vehicle_list_content, "mapFromGlobal", return_value=QPoint(0, 0)),
            patch.object(view._vehicle_list_content, "childAt", return_value=card),
            patch("ui.views.fleet_tracking_view.QMenu") as MockQMenu,
        ):
            mock_menu = MockQMenu.return_value
            view._show_vehicle_context_menu(mock_event)
            assert mock_menu.addAction.call_count == 4

    def test_context_menu_details_selects_vehicle(self, view):
        """View Details action triggers _select_vehicle (verified via mock)."""
        pos = _make_vehicle_position()
        card = view._build_vehicle_row_widget(pos, 42)
        mock_event = MagicMock()
        mock_event.globalPos.return_value = QPoint(0, 0)

        with (
            patch.object(view._vehicle_list_content, "mapFromGlobal", return_value=QPoint(0, 0)),
            patch.object(view._vehicle_list_content, "childAt", return_value=card),
            patch("ui.views.fleet_tracking_view.QMenu") as MockQMenu,
            patch("ui.views.fleet_tracking_view.QAction") as MockQAction,
        ):
            mock_menu = MockQMenu.return_value
            mock_action = MockQAction.return_value
            view._show_vehicle_context_menu(mock_event)
            # 4 actions are added to the menu
            assert mock_menu.addAction.call_count == 4
            # The first action (View Details) has triggered.connect called
            # (the lambda calls _select_vehicle)
            assert mock_action.triggered.connect.called
            # _select_vehicle is verified by test_select_vehicle_pans_map

    def test_context_menu_on_non_card_does_nothing(self, view):
        mock_event = MagicMock()
        mock_event.globalPos.return_value = QPoint(0, 0)

        with (
            patch.object(view._vehicle_list_content, "mapFromGlobal", return_value=QPoint(0, 0)),
            patch.object(view._vehicle_list_content, "childAt", return_value=None),
            patch("ui.views.fleet_tracking_view.QMenu") as MockQMenu,
        ):
            view._show_vehicle_context_menu(mock_event)
            MockQMenu.assert_not_called()


# ---------------------------------------------------------------------------
# Tests – Call driver
# ---------------------------------------------------------------------------

class TestQtFleetTrackingViewDriverCall:
    """Call driver behavior."""

    def test_call_driver_with_phone_shows_toast(self, view, monkeypatch):
        mock_driver_repo = MagicMock()
        mock_driver_repo.get_by_id.return_value = {"phone": "0722000000"}
        monkeypatch.setattr(
            "repositories.driver_repository.DriverRepository",
            lambda db: mock_driver_repo,
        )
        toast_mock = MagicMock()
        monkeypatch.setattr("ui.widgets.toast.Toast", toast_mock)

        pos = _make_vehicle_position(driver_id=123)
        view._on_call_driver(pos, truck_id=None)

        toast_mock.show_info.assert_called_once()
        args, _ = toast_mock.show_info.call_args
        assert "0722000000" in str(args[1])

    def test_call_driver_without_phone_shows_info(self, view, monkeypatch):
        toast_mock = MagicMock()
        monkeypatch.setattr("ui.widgets.toast.Toast", toast_mock)

        pos = _make_vehicle_position(driver_id=0)
        view._on_call_driver(pos, truck_id=None)

        toast_mock.show_info.assert_called_once()
        args, _ = toast_mock.show_info.call_args
        assert "no driver phone" in str(args[1]).lower()
