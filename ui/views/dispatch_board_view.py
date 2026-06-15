"""PySide6 dispatch board view — kanban board for trip dispatching.

Replaces ``ui/views/dispatch_board_view.py`` (2135 lines of CustomTkinter).
Built as a QWidget for embedding in a QStackedWidget.
"""

from __future__ import annotations

import csv
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QMimeData, QPoint, QTimer
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t, register_listener, unregister_listener
from services.trip_service import TripService
from services.fleet_service import FleetService
from services.client_service import ClientService
from services.operations.event_bus import (
    EventBus,
    TRIP_CREATED,
    TRIP_STATUS_CHANGED,
    TRIP_UPDATED,
    TRIP_ASSIGNED,
    ALERT_CREATED,
    ALERT_RESOLVED,
    TRUCK_UPDATED,
    DRIVER_UPDATED,
    DRIVER_DELETED,
    VALID_TRANSITIONS,
)
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.operations.trip_status_engine import TripStatusEngine
from services.driver_truck_service import DriverTruckService
from services.conflict_service import TripConflictService
from repositories.trip_repository import TripRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from repositories.route_repository import RouteRepository
from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from utils.dates import parse_date
from ui.components import Btn, PageTitle, Label
from ui.design_tokens import (
    BORDER_DEFAULT, WARNING, INFO, SUCCESS, DANGER, SP,
)
from ui.widgets.dispatch_search_bar import QtDispatchSearchBar, STATUS_OPTIONS
from ui.widgets.dispatch_tabs import QtDispatchTabs
from ui.widgets.kanban_column import QtKanbanColumn
from ui.widgets.trip_card import QtTripCard
from ui.widgets.dispatch_timeline import QtDispatchTimeline
from ui.widgets.dispatch_alerts_panel import QtDispatchAlertsPanel
from ui.widgets.assignment_dropdown import QtAssignmentDropdown
from ui.widgets.toast import Toast
from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

STATUS_TO_COLUMN = {
    "Planned": "Planned",
    "Scheduled": "Planned",
    "Pending": "Planned",
    "Loading": "Loading",
    "Preparing": "Loading",
    "Pickup": "Loading",
    "In Transit": "In Transit",
    "InTransit": "In Transit",
    "Active": "In Transit",
    "InProgress": "In Transit",
    "Delivered": "Delivered",
    "Completed": "Delivered",
    "Done": "Delivered",
    "Invoiced": "Delivered",
    "Paid": "Delivered",
    "Cancelled": "Cancelled",
}

COLUMN_DEFS = [
    ("Planned", "dispatch_board.col_planned", BORDER_DEFAULT),
    ("Loading", "dispatch_board.col_loading", WARNING),
    ("In Transit", "dispatch_board.col_in_transit", INFO),
    ("Delivered", "dispatch_board.col_delivered", SUCCESS),
    ("Cancelled", "dispatch_board.col_cancelled", DANGER),
]

DELIVERED_DEFAULT_DAYS = 30


class QtDispatchBoardView(QWidget):
    """Kanban dispatch board for trip management.

    Embedded in a QStackedWidget in the main window.  Provides three tabs:
    - **Board** — horizontal scroll of ``QtKanbanColumn`` widgets
    - **Timeline** — Gantt-like ``QtDispatchTimeline``
    - **Alerts** — KPIs/alerts panel ``QtDispatchAlertsPanel``
    """

    REFRESH_INTERVAL_MS = 30_000

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
        ops=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self._db = db
        self.prefs = prefs
        self.ops = ops

        # ── State ────────────────────────────────────────────────────────────
        self._columns: Dict[str, QtKanbanColumn] = {}
        self._loading = False
        self._delivered_days = DELIVERED_DEFAULT_DAYS
        self._destroyed = False

        # Repositories / services
        self._trip_repo = TripRepository(db)
        self._fleet_repo = FleetRepository(db)
        self._driver_repo = DriverRepository(db)
        self._route_repo = RouteRepository(db)
        self._status_engine = TripStatusEngine(db)
        self._event_bus = EventBus()
        self._trip_service = TripService(db)
        self._fleet_service = FleetService(db)
        self._client_service = ClientService(db)
        self._alert_mgr = AlertManager()
        self._dta_service = DriverTruckService(db)
        self._conflict_service = TripConflictService(db)

        # Caches
        self._driver_cache: Dict[int, Optional[Dict]] = {}
        self._route_cache: Dict[str, Optional[Dict]] = {}
        self._alert_counts: Dict[int, int] = {}
        self._event_handlers: Dict[str, Any] = {}
        self._all_card_data: List[Dict[str, Any]] = []
        self._search_query = ""
        self._search_statuses = list(STATUS_OPTIONS)
        self._conflict_alerts: Dict[int, list] = {}

        # Selection / bulk
        self._detail_panel: Optional[QtDispatchDetailPanel] = None
        self._selected_cards: list[QtTripCard] = []

        # Drag-drop state
        self._drag_card: Optional[QtTripCard] = None
        self._drag_source_col: Optional[QtKanbanColumn] = None
        self._drag_target_col: Optional[QtKanbanColumn] = None

        # Timers
        self._refresh_timer: Optional[QTimer] = None
        self._delay_timer: Optional[QTimer] = None
        self._live_timer: Optional[QTimer] = None

        # i18n
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        # ── Build ────────────────────────────────────────────────────────────
        self._build_ui()
        self._subscribe_events()
        self._start_load()

        # ── Auto-refresh timer ───────────────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._start_load)
        self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

    # ══════════════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)

        self._title_lbl = PageTitle(header, t("dispatch_board.title"))
        header_layout.addWidget(self._title_lbl)

        self._subtitle_lbl = Label(header, t("dispatch_board.subtitle"), role="secondary")
        header_layout.addWidget(self._subtitle_lbl)

        header_layout.addStretch(1)

        self._export_csv_btn = Btn(
            header, t("dispatch_board.export_csv"),
            variant="ghost", command=self._export_csv,
        )
        header_layout.addWidget(self._export_csv_btn)

        self._export_pdf_btn = Btn(
            header, t("dispatch_board.export_pdf"),
            variant="ghost", command=self._export_pdf,
        )
        header_layout.addWidget(self._export_pdf_btn)

        self._refresh_btn = Btn(
            header,
            f"\u21bb {t('dispatch_board.refresh')}",
            variant="primary", command=self._start_load,
        )
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # ── Tabs ─────────────────────────────────────────────────────────────
        self._tabs = QtDispatchTabs(self)
        layout.addWidget(self._tabs)

        # ── Tab: Board ───────────────────────────────────────────────────────
        self._board_tab = QWidget()
        board_layout = QVBoxLayout(self._board_tab)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setSpacing(0)

        # Search / filter bar
        self._search_bar = QtDispatchSearchBar(
            self._board_tab,
            on_search=self._on_search_filter,
        )
        board_layout.addWidget(self._search_bar)

        # Bulk toolbar (hidden by default)
        self._bulk_toolbar = QFrame()
        self._bulk_toolbar.setProperty("role", "bulk-toolbar")
        self._bulk_toolbar.setFixedHeight(36)
        bulk_layout = QHBoxLayout(self._bulk_toolbar)
        bulk_layout.setContentsMargins(SP["3"], 0, SP["3"], 0)
        bulk_layout.setSpacing(SP["2"])

        self._bulk_count_lbl = QLabel("")
        self._bulk_count_lbl.setProperty("fontRole", "small")
        bulk_layout.addWidget(self._bulk_count_lbl)

        bulk_layout.addStretch(1)

        self._bulk_clear_btn = Btn(
            self._bulk_toolbar,
            t("dispatch_board.bulk_clear_selection"),
            variant="ghost",
            command=self._clear_all_selections,
        )
        bulk_layout.addWidget(self._bulk_clear_btn)

        self._bulk_assign_driver_btn = Btn(
            self._bulk_toolbar,
            t("dispatch_board.bulk_assign_driver"),
            variant="primary",
            command=self._on_bulk_assign_driver,
        )
        bulk_layout.addWidget(self._bulk_assign_driver_btn)

        self._bulk_assign_truck_btn = Btn(
            self._bulk_toolbar,
            t("dispatch_board.bulk_assign_truck"),
            variant="primary",
            command=self._on_bulk_assign_truck,
        )
        bulk_layout.addWidget(self._bulk_assign_truck_btn)

        self._bulk_toolbar.hide()
        board_layout.addWidget(self._bulk_toolbar)

        # Kanban columns in a horizontal scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        columns_container = QWidget()
        columns_container.setProperty("role", "kanban-columns-container")
        columns_layout = QHBoxLayout(columns_container)
        columns_layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["2"])
        columns_layout.setSpacing(SP["3"])

        for i, (status_key, title_key, accent_color) in enumerate(COLUMN_DEFS):
            is_delivered = status_key == "Delivered"
            col = QtKanbanColumn(
                columns_container,
                status_key=status_key,
                title_key=title_key,
                accent_color=accent_color,
                on_card_click=self._on_card_click,
                on_drag_start=self._on_drag_start,
                on_assign_truck=self._on_assign_truck,
                on_assign_driver=self._on_assign_driver,
                on_select_changed=self._on_card_select_changed,
                on_assign_both=self._on_assign_both,
                show_load_older=is_delivered,
                on_load_older=self._on_load_older_delivered,
                on_retry=lambda sk=status_key: self._start_load(),
            )
            columns_layout.addWidget(col)
            self._columns[status_key] = col

        scroll_area.setWidget(columns_container)
        board_layout.addWidget(scroll_area, 1)

        # ── Tab: Alerts ──────────────────────────────────────────────────────
        self._alerts_tab = QWidget()
        alerts_layout = QVBoxLayout(self._alerts_tab)
        alerts_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])

        self._alerts_panel = QtDispatchAlertsPanel(
            self._alerts_tab, self.db, ops=self.ops,
            on_assign_truck=self._on_quick_assign_truck,
            on_assign_driver=self._on_quick_assign_driver,
            on_resolve_alert=self._on_resolve_alert_refresh,
        )
        alerts_layout.addWidget(self._alerts_panel)

        # ── Tab: Timeline ────────────────────────────────────────────────────
        self._timeline_tab = QWidget()
        timeline_layout = QVBoxLayout(self._timeline_tab)
        timeline_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])

        self._timeline = QtDispatchTimeline(self._timeline_tab)
        timeline_layout.addWidget(self._timeline)

        # Register tabs
        self._tabs.add_tab("board", t("dispatch_board.tabs_board"), self._board_tab)
        self._tabs.add_tab("alerts", t("dispatch_board.tabs_alerts"), self._alerts_tab)
        self._tabs.add_tab("timeline", t("dispatch_board.tabs_timeline"), self._timeline_tab)

        self._tabs.on_switch(self._on_tab_switch)
        self._tabs.switch_to("board")

    # ══════════════════════════════════════════════════════════════════════════
    # Data Loading
    # ══════════════════════════════════════════════════════════════════════════

    def _start_load(self) -> None:
        if self._loading:
            return
        self._loading = True
        # Clear shared state on main thread before starting bg work
        self._alert_counts.clear()
        if self.ops:
            try:
                self.ops.undo_stack.clear()
            except Exception:
                pass
        for col in self._columns.values():
            col.show_loading()
        thread = threading.Thread(target=self._load_data_background, daemon=True)
        thread.start()

    def _load_data_background(self) -> None:
        try:
            self._preload_alerts()

            all_statuses = list(STATUS_TO_COLUMN.keys())
            all_trips = self._trip_repo.get_by_statuses(all_statuses)

            column_trips: Dict[str, List[Dict[str, Any]]] = {
                col: [] for col, _, _ in COLUMN_DEFS
            }

            cutoff = (datetime.now() - timedelta(days=self._delivered_days)).strftime("%Y-%m-%d")

            for trip in all_trips:
                raw_status = trip.get("status", "")
                column = STATUS_TO_COLUMN.get(raw_status)
                if not column:
                    continue

                if column in ("Delivered", "Cancelled"):
                    created = trip.get("created_at", "")
                    trip_date = created[:10] if len(created) >= 10 else created
                    if trip_date and trip_date < cutoff:
                        continue

                card_data = self._build_card_data(trip)
                column_trips[column].append(card_data)

            self._dispatch(lambda ct=column_trips: self._populate_columns(ct))

        except Exception as e:
            logger.exception("Dispatch board data load failed")
            self._dispatch(lambda err=str(e): self._show_error_all(err))

    def _preload_alerts(self) -> None:
        if not self.ops:
            return
        try:
            alerts = self.ops.get_active_alerts(limit=2000)
            for alert in alerts:
                trip_id = getattr(alert, "trip_id", None)
                if trip_id is not None:
                    try:
                        tid = int(trip_id)
                    except (ValueError, TypeError):
                        continue
                    self._alert_counts[tid] = self._alert_counts.get(tid, 0) + 1
        except Exception:
            logger.debug("Could not preload alerts", exc_info=True)

    def _build_card_data(self, trip: Dict[str, Any]) -> Dict[str, Any]:
        trip_id = trip.get("id", 0)
        status = trip.get("status", "Planned")
        truck_plate = trip.get("truck_number", "") or ""
        driver_name = trip.get("driver_name", "") or ""
        driver_id = trip.get("driver_id")
        truck_id = trip.get("truck_id")

        if driver_id and not driver_name:
            driver_name = self._resolve_driver_name(driver_id)

        origin, destination = self._resolve_route(trip)

        departure = trip.get("start_date", "") or ""
        eta = trip.get("end_date", "") or ""

        alerts_count = self._alert_counts.get(trip_id, 0)

        return {
            "trip_id": f"{t('dispatch_board.trip_id_prefix')}{trip_id}",
            "trip_id_num": trip_id,
            "status": status,
            "truck_plate": truck_plate,
            "truck_id": truck_id,
            "driver_name": driver_name,
            "driver_id": driver_id,
            "origin": origin,
            "destination": destination,
            "departure_date": departure,
            "eta": eta,
            "alerts_count": alerts_count,
        }

    def _resolve_driver_name(self, driver_id: int) -> str:
        if driver_id in self._driver_cache:
            cached = self._driver_cache[driver_id]
            return cached.get("name", "") if cached else ""
        try:
            driver = self._driver_repo.get_by_id(driver_id)
            self._driver_cache[driver_id] = driver
            return driver.get("name", "") if driver else ""
        except Exception:
            self._driver_cache[driver_id] = None
            return ""

    def _resolve_route(self, trip: Dict[str, Any]):
        route_id = trip.get("route_history_v2_id")
        if not route_id:
            return "", ""

        route_key = str(route_id)
        if route_key in self._route_cache:
            cached = self._route_cache[route_key]
            if cached is None:
                return "", ""
            return cached.get("origin", ""), cached.get("destination", "")

        try:
            route = self._route_repo.get_by_id(int(route_id))
            if not route:
                self._route_cache[route_key] = None
                return "", ""

            origin, destination = self._extract_stops(route)
            result = {"origin": origin, "destination": destination}
            self._route_cache[route_key] = result
            return origin, destination
        except Exception:
            self._route_cache[route_key] = None
            return "", ""

    def _extract_stops(self, route: Dict[str, Any]):
        summary = route.get("route_summary_json")
        if summary:
            try:
                summary_data = json.loads(summary) if isinstance(summary, str) else summary
                origin = summary_data.get("origin", "")
                dest = summary_data.get("destination", "")
                if origin or dest:
                    return origin, dest
            except (json.JSONDecodeError, TypeError):
                pass

        stops_raw = route.get("stops_json", "")
        if not stops_raw:
            return "", ""

        try:
            stops = json.loads(stops_raw) if isinstance(stops_raw, str) else stops_raw
        except (json.JSONDecodeError, TypeError):
            return "", ""

        if not stops or not isinstance(stops, list):
            return "", ""

        def _label(stop):
            if isinstance(stop, dict):
                return stop.get("address") or stop.get("label") or stop.get("value") or ""
            if isinstance(stop, (list, tuple)) and len(stop) >= 3:
                return str(stop[2]) if stop[2] else ""
            return ""

        origin = _label(stops[0]) if stops else ""
        destination = _label(stops[-1]) if stops else ""
        return origin, destination

    def _populate_columns(self, column_trips: Dict[str, List[Dict[str, Any]]]) -> None:
        self._loading = False
        all_cards = []
        for status_key, col in self._columns.items():
            trips = column_trips.get(status_key, [])
            col.set_trips(trips)
            all_cards.extend(trips)
        self._all_card_data = all_cards

        # Defer post-load operations
        QTimer.singleShot(100, self._evaluate_all_delays)
        QTimer.singleShot(200, self._refresh_live_indicators)
        QTimer.singleShot(500, self._run_conflict_scan)
        QTimer.singleShot(600, self._refresh_side_panels)
        QTimer.singleShot(700, self._apply_filters)

    def _show_error_all(self, error_msg: str) -> None:
        self._loading = False
        for col in self._columns.values():
            col.show_error(error_msg)

    # ── Live position tracking ───────────────────────────────────────────────

    def _get_truck_position(self, truck_id, positions=None):
        if not truck_id:
            return None
        try:
            from services.fleet_tracking_service import fleet_tracking_service
            if positions is None:
                if not fleet_tracking_service.is_configured():
                    return None
                positions = fleet_tracking_service.get_positions()
            truck = self._fleet_repo.get_by_id(int(truck_id))
            if not truck:
                return None
            plate = (truck.get("plate_number") or "").upper()
            device_id = truck.get("tracking_device_id") or ""
            for pos in positions:
                if ((pos.name or "").upper() == plate
                        or pos.device_id == device_id):
                    return pos
        except Exception:
            pass
        return None

    def _refresh_live_indicators(self) -> None:
        try:
            self.isWidgetType()
        except RuntimeError:
            return
        try:
            from services.fleet_tracking_service import fleet_tracking_service
            if not fleet_tracking_service.is_configured():
                return
            positions = fleet_tracking_service.get_positions()
            for col in self._columns.values():
                for card in col._cards:
                    status = card.trip_data.get("status", "")
                    truck_id = card.trip_data.get("truck_id")
                    if status == "In Transit" and truck_id:
                        pos = self._get_truck_position(truck_id, positions=positions)
                        card.set_live_position(pos)
                    else:
                        card.set_live_position(None)
        except Exception:
            pass

    def _on_load_older_delivered(self) -> None:
        self._delivered_days += 30
        self._start_load()

    # ══════════════════════════════════════════════════════════════════════════
    # Tab switching
    # ══════════════════════════════════════════════════════════════════════════

    def _on_tab_switch(self, tab_id: str) -> None:
        if tab_id == "alerts":
            self._alerts_panel.refresh(self._all_card_data)
        elif tab_id == "timeline":
            self._timeline.refresh(self._all_card_data)

    # ══════════════════════════════════════════════════════════════════════════
    # Search / Filter
    # ══════════════════════════════════════════════════════════════════════════

    def _on_search_filter(self, query: str, statuses: list) -> None:
        self._search_query = query
        self._search_statuses = statuses
        self._apply_filters()

    def _apply_filters(self) -> None:
        visible = 0
        total = 0
        for col in self._columns.values():
            for card in col._cards:
                total += 1
                status = card.trip_data.get("status", "")
                column = STATUS_TO_COLUMN.get(status, "")
                show = True

                if column not in self._search_statuses:
                    show = False

                if show and self._search_query:
                    text = " ".join([
                        str(card.trip_data.get("trip_id", "")),
                        str(card.trip_data.get("truck_plate", "")),
                        str(card.trip_data.get("driver_name", "")),
                        str(card.trip_data.get("origin", "")),
                        str(card.trip_data.get("destination", "")),
                        str(card.trip_data.get("status", "")),
                    ]).lower()
                    if self._search_query not in text:
                        show = False

                if show:
                    card.show()
                    visible += 1
                else:
                    card.hide()

        self._search_bar.set_result_count(visible, total)

    # ══════════════════════════════════════════════════════════════════════════
    # Detail panel
    # ══════════════════════════════════════════════════════════════════════════

    def _on_card_click(self, trip_data: dict) -> None:
        if self._detail_panel is not None:
            try:
                self._detail_panel.close()
            except Exception:
                pass
            self._detail_panel = None
        self._detail_panel = QtDispatchDetailPanel(
            self, trip_data, self.db,
            ops=self.ops,
            on_close=self._on_detail_close,
        )
        self._detail_panel.show()

    def _on_detail_close(self) -> None:
        self._detail_panel = None

    # ══════════════════════════════════════════════════════════════════════════
    # Quick Assign (from Alerts panel)
    # ══════════════════════════════════════════════════════════════════════════

    def _on_quick_assign_truck(self, item: dict) -> None:
        trip_id = item.get("trip_id_num") or item.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if card:
            self._tabs.switch_to("board")
            self._on_assign_truck(card)

    def _on_quick_assign_driver(self, item: dict) -> None:
        trip_id = item.get("trip_id_num") or item.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if card:
            self._tabs.switch_to("board")
            self._on_assign_driver(card)

    def _on_resolve_alert_refresh(self) -> None:
        self._alerts_panel.refresh(self._all_card_data)
        self._preload_alerts()
        for col in self._columns.values():
            for card in col._cards:
                trip_id = card.trip_data.get("trip_id_num")
                if trip_id:
                    card.trip_data["alerts_count"] = self._alert_counts.get(trip_id, 0)

    # ══════════════════════════════════════════════════════════════════════════
    # Bulk Selection
    # ══════════════════════════════════════════════════════════════════════════

    def _on_card_select_changed(self, card: QtTripCard, selected: bool) -> None:
        if selected:
            if card not in self._selected_cards:
                self._selected_cards.append(card)
        else:
            if card in self._selected_cards:
                self._selected_cards.remove(card)
        self._update_bulk_toolbar()

    def _clear_all_selections(self) -> None:
        for card in list(self._selected_cards):
            card.set_selected(False)
        self._selected_cards.clear()
        self._update_bulk_toolbar()

    def _update_bulk_toolbar(self) -> None:
        count = len(self._selected_cards)
        if count > 0:
            self._bulk_count_lbl.setText(
                t("dispatch_board.bulk_selected_count").format(n=count)
            )
            self._bulk_toolbar.show()
        else:
            self._bulk_toolbar.hide()

    def _on_bulk_assign_truck(self) -> None:
        if not self._selected_cards:
            return

        def fetch_trucks():
            active_trucks = self._fleet_repo.get_active_trucks()
            items = []
            for truck in active_trucks:
                items.append({
                    "id": truck.get("id"),
                    "label": truck.get("plate_number", ""),
                    "sublabel": truck.get("model", ""),
                    "available": True,
                    "status_text": "",
                })
            items.sort(key=lambda x: x["label"])
            return items

        def on_select(truck_id):
            self._assign_truck_to_selected(truck_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=self._bulk_assign_truck_btn,
            title=t("dispatch_board.select_truck"),
            fetch_func=fetch_trucks,
            on_select=on_select,
        )
        dropdown.show_anchored(self._bulk_assign_truck_btn)

    def _on_bulk_assign_driver(self) -> None:
        if not self._selected_cards:
            return

        def fetch_drivers():
            active_drivers = self._driver_repo.get_active_drivers()
            items = []
            for d in active_drivers:
                items.append({
                    "id": d.get("id"),
                    "label": d.get("name", ""),
                    "sublabel": d.get("license_category", ""),
                    "available": True,
                    "status_text": "",
                })
            items.sort(key=lambda x: x["label"])
            return items

        def on_select(driver_id):
            self._assign_driver_to_selected(driver_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=self._bulk_assign_driver_btn,
            title=t("dispatch_board.select_driver"),
            fetch_func=fetch_drivers,
            on_select=on_select,
        )
        dropdown.show_anchored(self._bulk_assign_driver_btn)

    def _assign_truck_to_selected(self, truck_id: int) -> None:
        try:
            truck = self._fleet_repo.get_by_id(truck_id)
            if not truck:
                return
            plate = truck.get("plate_number", "")
            ok_count = 0
            failed = 0
            for card in list(self._selected_cards):
                try:
                    trip_id = card.trip_data.get("trip_id_num")
                    self._trip_service.update(trip_id, {"truck_number": plate, "truck_id": truck_id})
                    card.update_truck(plate, truck_id)
                    self._event_bus.publish(TRIP_ASSIGNED, {"trip_id": trip_id, "truck_id": truck_id})
                    ok_count += 1
                except Exception:
                    failed += 1
            if failed:
                self._show_toast(t("dispatch_board.bulk_partial").format(ok=ok_count, failed=failed), "warning")
            else:
                self._show_toast(t("dispatch_board.bulk_success").format(count=ok_count), "success")
            self._clear_all_selections()
        except Exception as e:
            self._show_toast(str(e), "error")

    def _assign_driver_to_selected(self, driver_id: int) -> None:
        try:
            driver = self._driver_repo.get_by_id(driver_id)
            if not driver:
                return
            name = driver.get("name", "")
            ok_count = 0
            failed = 0
            for card in list(self._selected_cards):
                try:
                    trip_id = card.trip_data.get("trip_id_num")
                    self._trip_service.update(trip_id, {"driver_id": driver_id, "driver_name": name})
                    card.update_driver(name, driver_id)
                    self._event_bus.publish(TRIP_ASSIGNED, {"trip_id": trip_id, "driver_id": driver_id})
                    ok_count += 1
                except Exception:
                    failed += 1
            if failed:
                self._show_toast(t("dispatch_board.bulk_partial").format(ok=ok_count, failed=failed), "warning")
            else:
                self._show_toast(t("dispatch_board.bulk_success").format(count=ok_count), "success")
            self._clear_all_selections()
        except Exception as e:
            self._show_toast(str(e), "error")

    # ══════════════════════════════════════════════════════════════════════════
    # Undo / Redo
    # ══════════════════════════════════════════════════════════════════════════

    def _on_undo(self) -> None:
        if not self.ops:
            self._show_toast(t("dispatch_board.undo_nothing"), "error")
            return
        stack = self.ops.undo_stack
        cmd = stack.last_undo_command()
        if not cmd:
            self._show_toast(t("dispatch_board.undo_nothing"), "error")
            return
        ok = self.ops.undo_last()
        if ok:
            self._show_toast(
                t("dispatch_board.undo_success").format(
                    trip_id=cmd.trip_id, old_status=cmd.old_status, new_status=cmd.new_status
                ),
                "success",
            )
            QTimer.singleShot(500, self._start_load)

    def _on_redo(self) -> None:
        if not self.ops:
            self._show_toast(t("dispatch_board.redo_nothing"), "error")
            return
        stack = self.ops.undo_stack
        cmd = stack.last_redo_command()
        if not cmd:
            self._show_toast(t("dispatch_board.redo_nothing"), "error")
            return
        ok = self.ops.redo_last()
        if ok:
            self._show_toast(
                t("dispatch_board.redo_success").format(
                    trip_id=cmd.trip_id, old_status=cmd.old_status, new_status=cmd.new_status
                ),
                "success",
            )
            QTimer.singleShot(500, self._start_load)

    # ══════════════════════════════════════════════════════════════════════════
    # Conflict Scan
    # ══════════════════════════════════════════════════════════════════════════

    def _run_conflict_scan(self) -> None:
        try:
            all_trips = self._trip_repo.get_all(limit=2000)
            active_trips = [
                t for t in all_trips
                if t.get("status", "") not in (
                    "Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"
                )
            ]
            conflict_found = False
            trip_conflict_map: Dict[int, list] = {}

            for trip in active_trips:
                conflicts = self._conflict_service.check_conflicts(trip)
                if conflicts:
                    tid = trip.get("id")
                    if tid not in trip_conflict_map:
                        trip_conflict_map[tid] = []
                    trip_conflict_map[tid] = conflicts
                    conflict_found = True

            self._conflict_alerts = trip_conflict_map
            if conflict_found:
                logger.info("Conflict scan: %d trips with resource conflicts", len(trip_conflict_map))
        except Exception:
            logger.debug("Conflict scan failed", exc_info=True)

    def _refresh_side_panels(self) -> None:
        try:
            self._alerts_panel.refresh(self._all_card_data)
        except Exception:
            pass
        try:
            self._timeline.refresh(self._all_card_data)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════════════════

    def _export_csv(self) -> None:
        if not self._all_card_data:
            self._show_toast(t("dispatch_board.export_error").format(error="No data"), "error")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("dispatch_board.export_csv"),
            f"dispatch_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Trip ID", "Status", "Truck", "Driver", "Origin", "Destination",
                    "Departure", "ETA", "Alerts",
                ])
                for cd in self._all_card_data:
                    writer.writerow([
                        cd.get("trip_id", ""),
                        cd.get("status", ""),
                        cd.get("truck_plate", ""),
                        cd.get("driver_name", ""),
                        cd.get("origin", ""),
                        cd.get("destination", ""),
                        cd.get("departure_date", ""),
                        cd.get("eta", ""),
                        cd.get("alerts_count", 0),
                    ])
            self._show_toast(t("dispatch_board.export_success").format(path=path), "success")
        except Exception as e:
            self._show_toast(t("dispatch_board.export_error").format(error=str(e)), "error")

    def _export_pdf(self) -> None:
        if not self._all_card_data:
            self._show_toast(t("dispatch_board.export_error").format(error="No data"), "error")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("dispatch_board.export_pdf"),
            f"dispatch_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF files (*.pdf)",
        )
        if not path:
            return
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.units import mm

            doc = SimpleDocTemplate(path, pagesize=landscape(A4), topMargin=10 * mm, bottomMargin=10 * mm)
            styles = getSampleStyleSheet()
            elements: list = []

            title_style = ParagraphStyle(
                "Title", parent=styles["Title"], fontSize=14,
                textColor=rl_colors.HexColor("#fafafa"),
            )
            elements.append(
                Paragraph(f"Dispatch Board \u2014 {datetime.now().strftime('%d/%m/%Y %H:%M')}", title_style)
            )
            elements.append(Spacer(1, 6 * mm))

            status_colors = {
                "Planned": rl_colors.HexColor("#1c1917"),
                "Loading": rl_colors.HexColor("#341a00"),
                "In Transit": rl_colors.HexColor("#0f1f4a"),
                "Delivered": rl_colors.HexColor("#052e16"),
                "Cancelled": rl_colors.HexColor("#3b0000"),
            }
            header_style = ParagraphStyle(
                "Header", textColor=rl_colors.HexColor("#fafafa"),
                fontSize=9, fontName="Helvetica-Bold",
            )
            cell_style = ParagraphStyle(
                "Cell", textColor=rl_colors.HexColor("#a1a1aa"), fontSize=8,
            )

            for col_key in ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]:
                col_trips = [
                    cd for cd in self._all_card_data
                    if STATUS_TO_COLUMN.get(cd.get("status", "")) == col_key
                ]
                bg = status_colors.get(col_key, rl_colors.grey)

                elements.append(Paragraph(f"{col_key} ({len(col_trips)})", header_style))
                elements.append(Spacer(1, 2 * mm))

                if col_trips:
                    table_data = [["Trip ID", "Truck", "Driver", "Route", "Departure", "ETA"]]
                    for cd in col_trips[:50]:
                        table_data.append([
                            cd.get("trip_id", ""),
                            cd.get("truck_plate", ""),
                            cd.get("driver_name", ""),
                            f"{cd.get('origin','?')} \u2192 {cd.get('destination','?')}",
                            cd.get("departure_date", ""),
                            cd.get("eta", ""),
                        ])
                    tbl = Table(table_data, colWidths=[45 * mm, 40 * mm, 45 * mm, 60 * mm, 40 * mm, 40 * mm])
                    tbl.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), bg),
                        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.HexColor("#fafafa")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#27272a")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                         [rl_colors.HexColor("#111113"), rl_colors.HexColor("#18181b")]),
                    ]))
                    elements.append(tbl)
                else:
                    elements.append(Paragraph("No trips", cell_style))
                elements.append(Spacer(1, 4 * mm))

            doc.build(elements)
            self._show_toast(t("dispatch_board.export_success").format(path=path), "success")
        except Exception as e:
            self._show_toast(t("dispatch_board.export_error").format(error=str(e)), "error")

    # ══════════════════════════════════════════════════════════════════════════
    # Drag-Drop
    # ══════════════════════════════════════════════════════════════════════════

    def _on_drag_start(self, card: QtTripCard, event: QMouseEvent) -> None:
        if self._drag_card is not None:
            return
        self._drag_card = card
        self._drag_source_col = self._find_column_for_card(card)

        # Initiate Qt drag
        drag = QDrag(card)
        mime = QMimeData()
        trip_id = card.trip_data.get("trip_id_num", "")
        mime.setText(str(trip_id))
        drag.setMimeData(mime)

        # Highlight source column
        if self._drag_source_col is not None:
            self._drag_source_col.highlight_drop_zone()

        # Execute drag (blocks until drop/finish)
        result = drag.exec(Qt.MoveAction)

        # Cleanup highlight
        if self._drag_source_col is not None:
            self._drag_source_col.unhighlight_drop_zone()
        if self._drag_target_col is not None and self._drag_target_col != self._drag_source_col:
            self._drag_target_col.unhighlight_drop_zone()

        # If the drag was accepted (drop on a valid target), handle after
        self._drag_card = None
        self._drag_source_col = None
        self._drag_target_col = None

    def _find_column_for_card(self, card: QtTripCard) -> Optional[QtKanbanColumn]:
        for col in self._columns.values():
            if card in col._cards:
                return col
        return None

    def _find_column_for_widget(self, widget: Optional[QWidget]) -> Optional[QtKanbanColumn]:
        if widget is None:
            return None
        for col in self._columns.values():
            if self._widget_is_child(col, widget):
                return col
        return None

    def _widget_is_child(self, parent: QWidget, child: QWidget) -> bool:
        while child is not None:
            if child is parent:
                return True
            child = child.parentWidget()
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # Drag-Drop: accept drops on columns
    # ══════════════════════════════════════════════════════════════════════════

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasText():
            return
        trip_id_str = event.mimeData().text()
        if not trip_id_str:
            return
        try:
            trip_id = int(trip_id_str)
        except ValueError:
            return

        # Find target column under cursor
        target_col = self._find_column_for_widget(self.childAt(event.position().toPoint()))
        if target_col is None:
            return

        # Find card by trip_id
        card = self._find_card_by_trip_id(trip_id)
        if card is None:
            return

        source_col = self._find_column_for_card(card)
        if source_col is None or target_col is None or source_col == target_col:
            return

        old_status = source_col.status_key
        new_status = target_col.status_key

        event.accept()
        self._handle_transition(trip_id, old_status, new_status, card, source_col, target_col)

    # ══════════════════════════════════════════════════════════════════════════
    # Status transition
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_transition(
        self,
        trip_id: int,
        old_status: str,
        new_status: str,
        card: QtTripCard,
        source_col: QtKanbanColumn,
        target_col: QtKanbanColumn,
    ) -> None:
        column_order = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]
        old_idx = column_order.index(old_status) if old_status in column_order else -1
        new_idx = column_order.index(new_status) if new_status in column_order else -1
        is_backward = new_idx < old_idx

        if is_backward:
            reply = QMessageBox.question(
                self,
                t("dispatch_board.confirm_title"),
                t(
                    "dispatch_board.confirm_backward",
                    old_status=old_status,
                    new_status=new_status,
                    trip_id=trip_id,
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        card_backup = dict(card.trip_data)

        # Create new card in target column
        new_card = QtTripCard(
            target_col,
            {**card_backup, "status": new_status},
            on_click=self._on_card_click,
            on_drag_start=self._on_drag_start,
            on_assign_truck=self._on_assign_truck,
            on_assign_driver=self._on_assign_driver,
            on_select_changed=self._on_card_select_changed,
            on_assign_both=self._on_assign_both,
        )
        target_col.add_card(new_card)

        if source_col:
            source_col.remove_card(card)

        new_card.trip_data["status"] = new_status

        try:
            if self.ops:
                ok = self.ops.force_trip_status(trip_id, new_status)
                if not ok:
                    raise RuntimeError(f"Status transition failed for trip {trip_id}")
            else:
                self._status_engine.transition(trip_id, new_status)
            self._show_toast(
                t("dispatch_board.transition_success").format(new_status=new_status),
                "success",
            )
        except Exception as e:
            # Rollback visual
            try:
                target_col.remove_card(new_card)
                new_card.deleteLater()
            except Exception:
                pass

            restored = QtTripCard(
                source_col if source_col else self._columns.get(old_status, self),
                {**card_backup, "status": old_status},
                on_click=self._on_card_click,
                on_drag_start=self._on_drag_start,
                on_assign_truck=self._on_assign_truck,
                on_assign_driver=self._on_assign_driver,
                on_select_changed=self._on_card_select_changed,
                on_assign_both=self._on_assign_both,
            )
            if source_col:
                source_col.add_card(restored)

            self._show_toast(
                t("dispatch_board.transition_error").format(
                    old_status=old_status, new_status=new_status
                ),
                "error",
            )

    # ══════════════════════════════════════════════════════════════════════════
    # Toast notifications
    # ══════════════════════════════════════════════════════════════════════════

    def _show_toast(self, message: str, variant: str = "success") -> None:
        icons = {"success": "\u2705", "error": "\u274c", "warning": "\u26a0\ufe0f"}
        icon = icons.get(variant, "\u2705")
        toast = Toast(self, message=message, icon=icon)
        toast.show_at(self, QPoint(self.width() // 2 - 100, 80))

    # ══════════════════════════════════════════════════════════════════════════
    # Assignment (single trip)
    # ══════════════════════════════════════════════════════════════════════════

    def _on_assign_truck(self, card: QtTripCard, clear: bool = False) -> None:
        if clear:
            self._clear_truck_assignment(card)
            return

        def fetch_trucks():
            active_trucks = self._fleet_repo.get_active_trucks()
            card_data = card.trip_data
            from datetime import datetime

            truck_conflicts: Dict[str, list] = {}
            truck_blocks: Dict[str, list] = {}
            now = datetime.now()
            for truck_entry in active_trucks:
                plate = truck_entry.get("plate_number", "")
                truck_id = truck_entry.get("id")

                conflicts = self._conflict_service.check_conflicts({
                    "truck_plate": plate,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                if conf:
                    truck_conflicts[plate] = conf

                blocks = []
                if truck_entry.get("status") == "In Service":
                    blocks.append(t("dispatch_board.resource_in_service"))
                try:
                    insurance = truck_entry.get("insurance_expiry", "")
                    if insurance:
                        exp = datetime.strptime(insurance, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_insurance_expired"))
                except Exception:
                    pass
                try:
                    inspection = truck_entry.get("inspection_expiry", "")
                    if inspection:
                        exp = datetime.strptime(inspection, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_inspection_expired"))
                except Exception:
                    pass
                try:
                    maint_due = truck_entry.get("maintenance_due")
                    mileage = truck_entry.get("mileage")
                    if maint_due is not None and mileage is not None:
                        if float(mileage) >= float(maint_due):
                            blocks.append(t("dispatch_board.resource_maintenance_due"))
                except Exception:
                    pass
                if blocks:
                    truck_blocks[plate] = blocks

            items = []
            for truck in active_trucks:
                plate = truck.get("plate_number", "")
                model = truck.get("model", "")
                truck_id = truck.get("id")

                conflicting = truck_conflicts.get(plate)
                blocked = truck_blocks.get(plate)
                available = not conflicting and not blocked

                if blocked:
                    status_text = t("dispatch_board.assign_truck_blocked").format(
                        reason=", ".join(blocked)
                    )
                elif conflicting:
                    trip_ref = conflicting[0].get("trip_id", "")
                    overlap = conflicting[0].get("overlap_description", "")
                    status_text = t("dispatch_board.unavailable_overlap").format(
                        f"{t('dispatch_board.trip_id_prefix')}{trip_ref} ({overlap})"
                    )
                else:
                    status_text = ""

                items.append({
                    "id": truck_id,
                    "label": plate,
                    "sublabel": model,
                    "available": available,
                    "status_text": status_text,
                    "plate": plate,
                })

            items.sort(key=lambda x: (not x["available"], x["label"]))
            return items

        def on_select(truck_id):
            self._assign_truck_to_trip(card, truck_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=card,
            title=t("dispatch_board.select_truck"),
            fetch_func=fetch_trucks,
            on_select=on_select,
        )
        dropdown.show_anchored(card)

    def _on_assign_driver(self, card: QtTripCard, clear: bool = False) -> None:
        if clear:
            self._clear_driver_assignment(card)
            return

        def fetch_drivers():
            active_drivers = self._driver_repo.get_active_drivers()
            card_data = card.trip_data
            from datetime import datetime, date, timedelta

            driver_conflicts: Dict[int, list] = {}
            driver_blocks: Dict[int, list] = {}
            driver_hours: Dict[int, tuple] = {}
            now = datetime.now()
            cutoff_7 = date.today() - timedelta(days=7)
            tacho_repo = TachoDriverActivityRepository(self._db)

            for d in active_drivers:
                did = d.get("id")
                conflicts = self._conflict_service.check_conflicts({
                    "driver_id": did,
                    "start_date": card_data.get("departure_date", ""),
                    "end_date": card_data.get("eta", ""),
                    "distance_km": 0,
                })
                conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
                if conf:
                    driver_conflicts[did] = conf

                blocks = []
                try:
                    license_expiry = d.get("license_expiry", "")
                    if license_expiry:
                        exp = datetime.strptime(license_expiry, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_license_expired"))
                except Exception:
                    pass
                try:
                    medical_expiry = d.get("medical_expiry", "")
                    if medical_expiry:
                        exp = datetime.strptime(medical_expiry, "%Y-%m-%d")
                        if now.date() > exp.date():
                            blocks.append(t("dispatch_board.resource_medical_expired"))
                except Exception:
                    pass

                weekly_h = 0.0
                violations = 0
                try:
                    records = tacho_repo.get_by_driver(int(did or 0), cutoff_7)
                    weekly_h = sum(r.get("driving_minutes", 0) or 0 for r in records) / 60
                    violations = sum(
                        len(json.loads(r.get("violations") or "[]"))
                        for r in records
                    )
                except Exception:
                    pass
                if weekly_h > 56:
                    blocks.append(t("dispatch_board.driver_hours_exceeded", hours=weekly_h, max_h=56))
                driver_hours[did] = (weekly_h, violations)

                if blocks:
                    driver_blocks[did] = blocks

            items = []
            for driver in active_drivers:
                driver_id = driver.get("id")
                name = driver.get("name", "")
                license_cat = driver.get("license_category", "")
                wh, vc = driver_hours.get(driver_id, (0, 0))

                conflicting = driver_conflicts.get(driver_id)
                blocked = driver_blocks.get(driver_id)
                available = not conflicting and not blocked

                hours_label = t("dispatch_board.driver_hours_weekly", hours=wh, max_h=56)
                sublabel = f"{license_cat} | {hours_label}"
                if vc > 0:
                    sublabel += f" | \u26a0 {vc}"

                if blocked:
                    status_text = t("dispatch_board.assign_driver_blocked").format(
                        reason=", ".join(blocked)
                    )
                elif conflicting:
                    trip_ref = conflicting[0].get("trip_id", "")
                    status_text = t("dispatch_board.unavailable_overlap").format(
                        f"{t('dispatch_board.trip_id_prefix')}{trip_ref}"
                    )
                else:
                    status_text = ""

                items.append({
                    "id": driver_id,
                    "label": name,
                    "sublabel": sublabel,
                    "available": available,
                    "status_text": status_text,
                    "name": name,
                })

            items.sort(key=lambda x: (not x["available"], x["label"]))
            return items

        def on_select(driver_id):
            self._assign_driver_to_trip(card, driver_id)

        dropdown = QtAssignmentDropdown(
            self,
            anchor_widget=card,
            title=t("dispatch_board.select_driver"),
            fetch_func=fetch_drivers,
            on_select=on_select,
        )
        dropdown.show_anchored(card)

    def _score_items(self, truck_items: list, driver_items: list, card_data: dict) -> None:
        from datetime import datetime
        now = datetime.now()

        for item in truck_items:
            if not item["available"]:
                continue
            score = 0
            truck_id = item.get("id")
            truck_plate = item.get("label", "")
            try:
                next_free = self._conflict_service.get_next_available_slot(
                    truck_plate=truck_plate, truck_id=truck_id
                )
                if next_free:
                    try:
                        nf_dt = datetime.strptime(next_free, "%d/%m/%Y %H:%M")
                        hours_until = max(0, (nf_dt - now).total_seconds() / 3600)
                        score += max(0, 40 - hours_until * 2)
                    except Exception:
                        score += 40
                else:
                    score += 40
            except Exception:
                score += 40
            try:
                truck = self._fleet_repo.get_by_id(int(truck_id)) if truck_id else None
                if truck:
                    fuel = float(truck.get("fuel_consumption") or 34)
                    score += max(0, 20 - (fuel - 20) * 1.5)
            except Exception:
                pass
            try:
                health = self._fleet_repo.get_truck_health(int(truck_id)) if truck_id else None
                if health:
                    score += (float(health.get("score", 0)) / 100) * 10
            except Exception:
                pass
            item["score"] = round(score, 1)

        for item in driver_items:
            if not item["available"]:
                continue
            score = 0
            driver_id = item.get("id")
            try:
                next_free = self._conflict_service.get_next_available_slot_for_driver(
                    int(driver_id)
                ) if driver_id else None
                if next_free:
                    try:
                        nf_dt = datetime.strptime(next_free, "%d/%m/%Y %H:%M")
                        hours_until = max(0, (nf_dt - now).total_seconds() / 3600)
                        score += max(0, 40 - hours_until * 2)
                    except Exception:
                        score += 40
                else:
                    score += 40
            except Exception:
                score += 40
            try:
                tacho_repo = TachoDriverActivityRepository(self._db)
                from datetime import date, timedelta
                records = tacho_repo.get_by_driver(
                    int(driver_id), date.today() - timedelta(days=7)
                )
                violations = sum(
                    len(json.loads(r.get("violations") or "[]")) for r in records
                )
                score += max(0, 10 - violations * 3)
            except Exception:
                pass
            item["score"] = round(score, 1)

    def _on_assign_both(self, card: QtTripCard) -> None:
        card_data = card.trip_data
        from datetime import datetime, date, timedelta
        active_trucks = self._fleet_repo.get_active_trucks()
        active_drivers = self._driver_repo.get_active_drivers()
        now = datetime.now()
        cutoff_7 = date.today() - timedelta(days=7)
        tacho_repo = TachoDriverActivityRepository(self._db)

        truck_items = []
        for trk in active_trucks:
            plate = trk.get("plate_number", "")
            model = trk.get("model", "")
            tid = trk.get("id")
            conflicts = self._conflict_service.check_conflicts({
                "truck_plate": plate,
                "start_date": card_data.get("departure_date", ""),
                "end_date": card_data.get("eta", ""),
                "distance_km": 0,
            })
            conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
            blocks = []
            if trk.get("status") == "In Service":
                blocks.append(t("dispatch_board.resource_in_service"))
            try:
                ins_ = trk.get("insurance_expiry", "")
                if ins_:
                    exp = datetime.strptime(ins_, "%Y-%m-%d")
                    if now.date() > exp.date():
                        blocks.append(t("dispatch_board.resource_insurance_expired"))
            except Exception:
                pass
            try:
                insp_ = trk.get("inspection_expiry", "")
                if insp_:
                    exp = datetime.strptime(insp_, "%Y-%m-%d")
                    if now.date() > exp.date():
                        blocks.append(t("dispatch_board.resource_inspection_expired"))
            except Exception:
                pass
            try:
                md = trk.get("maintenance_due")
                mi = trk.get("mileage")
                if md is not None and mi is not None and float(mi) >= float(md):
                    blocks.append(t("dispatch_board.resource_maintenance_due"))
            except Exception:
                pass
            avail = not conf and not blocks
            st = ""
            if blocks:
                st = ", ".join(blocks)
            elif conf:
                st = t("dispatch_board.unavailable_overlap").format(
                    f"{t('dispatch_board.trip_id_prefix')}{conf[0].get('trip_id','?')}")
            truck_items.append({
                "id": tid, "label": plate, "sublabel": model,
                "available": avail, "status_text": st, "score": 0,
            })

        driver_items = []
        for d in active_drivers:
            did = d.get("id")
            name = d.get("name", "")
            lcat = d.get("license_category", "")
            conflicts = self._conflict_service.check_conflicts({
                "driver_id": did,
                "start_date": card_data.get("departure_date", ""),
                "end_date": card_data.get("eta", ""),
                "distance_km": 0,
            })
            conf = [c for c in conflicts if c.get("trip_id") != card_data.get("trip_id_num")]
            blocks = []
            try:
                le = d.get("license_expiry", "")
                if le:
                    exp = datetime.strptime(le, "%Y-%m-%d")
                    if now.date() > exp.date():
                        blocks.append(t("dispatch_board.resource_license_expired"))
            except Exception:
                pass
            try:
                me = d.get("medical_expiry", "")
                if me:
                    exp = datetime.strptime(me, "%Y-%m-%d")
                    if now.date() > exp.date():
                        blocks.append(t("dispatch_board.resource_medical_expired"))
            except Exception:
                pass
            weekly_h = 0.0
            try:
                records = tacho_repo.get_by_driver(int(did or 0), cutoff_7)
                weekly_h = sum(r.get("driving_minutes", 0) or 0 for r in records) / 60
            except Exception:
                pass
            if weekly_h > 56:
                blocks.append(t("dispatch_board.driver_hours_exceeded", hours=weekly_h, max_h=56))
            hours_label = t("dispatch_board.driver_hours_weekly", hours=weekly_h, max_h=56)
            avail = not conf and not blocks
            st = ""
            if blocks:
                st = ", ".join(blocks)
            elif conf:
                st = t("dispatch_board.unavailable_overlap").format(
                    f"{t('dispatch_board.trip_id_prefix')}{conf[0].get('trip_id','?')}")
            driver_items.append({
                "id": did, "label": name, "sublabel": f"{lcat} | {hours_label}",
                "available": avail, "status_text": st, "score": 0,
            })

        self._score_items(truck_items, driver_items, card_data)
        truck_items.sort(key=lambda x: (-x.get("score", 0), x["label"]))
        driver_items.sort(key=lambda x: (-x.get("score", 0), x["label"]))

        paired_hint = ""
        try:
            driver_tname = self._dta_service.get_driver_name_for_truck(
                card_data.get("truck_id")
            ) if card_data.get("truck_id") else None
            if driver_tname:
                paired_hint = t("dispatch_board.pair_suggestion").format(
                    driver=driver_tname, truck=card_data.get("truck_plate", "?")
                )
        except Exception:
            pass

        def do_assign_both(truck_id, driver_id):
            self._assign_both_to_trip(card, truck_id, driver_id)

        def do_assign_truck_only(truck_id):
            self._assign_truck_to_trip(card, truck_id)

        def do_assign_driver_only(driver_id):
            self._assign_driver_to_trip(card, driver_id)

        QtPairedAssignmentDialog(
            self, card_data,
            truck_items, driver_items,
            paired_hint=paired_hint,
            on_assign_both=do_assign_both,
            on_assign_truck=do_assign_truck_only,
            on_assign_driver=do_assign_driver_only,
        ).show()

    def _assign_both_to_trip(self, card: QtTripCard, truck_id, driver_id) -> None:
        rolled_back_truck = False
        try:
            if truck_id is not None:
                self._assign_truck_to_trip(card, truck_id)
                rolled_back_truck = True
            if driver_id is not None:
                self._assign_driver_to_trip(card, driver_id)
            if truck_id is not None and driver_id is not None:
                try:
                    self._dta_service.assign_driver_to_truck(driver_id, truck_id)
                except Exception:
                    pass
        except Exception as e:
            if rolled_back_truck and truck_id is not None:
                try:
                    self._clear_truck_assignment(card)
                except Exception:
                    pass
            card.show_error("both", str(e))

    def _assign_truck_to_trip(self, card: QtTripCard, truck_id: int) -> None:
        try:
            truck = self._fleet_repo.get_by_id(truck_id)
            if not truck:
                raise ValueError(t("dispatch_board.truck_not_found"))
            plate = truck.get("plate_number", "")
            trip_id = card.trip_data.get("trip_id_num")
            self._trip_service.update(trip_id, {"truck_number": plate, "truck_id": truck_id})
            card.update_truck(plate, truck_id)
            self._event_bus.publish(TRIP_ASSIGNED, {
                "trip_id": trip_id,
                "truck_id": truck_id,
            })
            logger.info("Assigned truck %s to trip %d", plate, trip_id)
        except Exception as e:
            logger.error("Failed to assign truck: %s", e)
            card.show_error("truck", str(e))

    def _assign_driver_to_trip(self, card: QtTripCard, driver_id: int) -> None:
        try:
            driver = self._driver_repo.get_by_id(driver_id)
            if not driver:
                raise ValueError(t("dispatch_board.driver_not_found"))
            name = driver.get("name", "")
            trip_id = card.trip_data.get("trip_id_num")
            self._trip_service.update(trip_id, {"driver_id": driver_id, "driver_name": name})
            card.update_driver(name, driver_id)
            self._event_bus.publish(TRIP_ASSIGNED, {
                "trip_id": trip_id,
                "driver_id": driver_id,
            })
            logger.info("Assigned driver %s to trip %d", name, trip_id)
        except Exception as e:
            logger.error("Failed to assign driver: %s", e)
            card.show_error("driver", str(e))

    def _clear_truck_assignment(self, card: QtTripCard) -> None:
        try:
            trip_id = card.trip_data.get("trip_id_num")
            self._trip_service.update(trip_id, {"truck_number": "", "truck_id": None})
            card.update_truck("", None)
            logger.info("Cleared truck assignment for trip %d", trip_id)
        except Exception as e:
            logger.error("Failed to clear truck: %s", e)
            card.show_error("truck", str(e))

    def _clear_driver_assignment(self, card: QtTripCard) -> None:
        try:
            trip_id = card.trip_data.get("trip_id_num")
            self._trip_service.update(trip_id, {"driver_id": None, "driver_name": ""})
            card.update_driver("", None)
            logger.info("Cleared driver assignment for trip %d", trip_id)
        except Exception as e:
            logger.error("Failed to clear driver: %s", e)
            card.show_error("driver", str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # Delay evaluation
    # ══════════════════════════════════════════════════════════════════════════

    def _evaluate_all_delays(self) -> None:
        try:
            now = datetime.now()
            for col in self._columns.values():
                for card in col._cards:
                    trip_data = card.trip_data
                    is_delayed, minutes_overdue = self._is_trip_delayed(trip_data, now)
                    card.set_delayed(is_delayed, minutes_overdue)
                    if is_delayed:
                        self._create_delay_alert(card, minutes_overdue)
        except Exception:
            logger.debug("Delay evaluation skipped", exc_info=True)

    def _is_trip_delayed(self, trip_data: dict, now: datetime):
        status = trip_data.get("status", "")
        eta = trip_data.get("eta", "")
        departure = trip_data.get("departure_date", "")

        if status in ("In Transit", "InTransit", "Active", "InProgress"):
            if not eta:
                return False, 0
            try:
                eta_dt = self._parse_date(eta)
                if not eta_dt:
                    return False, 0
                if now > eta_dt:
                    minutes = int((now - eta_dt).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass

        elif status in ("Loading", "Preparing", "Pickup"):
            if not departure:
                return False, 0
            try:
                dep_dt = self._parse_date(departure)
                if not dep_dt:
                    return False, 0
                threshold = dep_dt + timedelta(hours=2)
                if now > threshold:
                    minutes = int((now - threshold).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass

        elif status in ("Planned", "Scheduled", "Pending"):
            if not departure:
                return False, 0
            try:
                dep_dt = self._parse_date(departure)
                if not dep_dt:
                    return False, 0
                threshold = now - timedelta(hours=24)
                if dep_dt < threshold:
                    minutes = int((threshold - dep_dt).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass

        return False, 0

    def _parse_date(self, date_str: str):
        return parse_date(date_str, "%d/%m/%Y")

    def _create_delay_alert(self, card: QtTripCard, minutes_overdue: int) -> None:
        trip_id = card.trip_data.get("trip_id_num")
        if not trip_id:
            return

        existing = self._alert_mgr.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000,
        )
        for alert in existing:
            if alert.trip_id == str(trip_id):
                return

        severity = Severity.CRITICAL if minutes_overdue > 120 else Severity.WARNING
        truck_plate = card.trip_data.get("truck_plate", "")
        driver_name = card.trip_data.get("driver_name", "")

        title = t("dispatch_board.delay_alert_title").format(trip_id)
        message = t("dispatch_board.delay_alert_message").format(
            minutes_overdue, truck_plate or t("common.na"), driver_name or t("common.na")
        )

        self._alert_mgr.create_alert(
            alert_type=AlertType.TRIP_DELAY,
            severity=severity,
            title=title,
            message=message,
            truck_id=truck_plate if truck_plate else None,
            trip_id=str(trip_id),
            metadata={
                "minutes_overdue": minutes_overdue,
                "status": card.trip_data.get("status", ""),
            },
        )
        logger.info("Created delay alert for trip %d (%d minutes overdue)", trip_id, minutes_overdue)

    # ══════════════════════════════════════════════════════════════════════════
    # Event Bus subscription
    # ══════════════════════════════════════════════════════════════════════════

    def _subscribe_events(self) -> None:
        handlers = {
            TRIP_CREATED: self._on_trip_created_ev,
            TRIP_STATUS_CHANGED: self._on_status_changed_ev,
            TRIP_UPDATED: self._on_trip_updated_ev,
            TRIP_ASSIGNED: self._on_trip_assigned_ev,
            ALERT_CREATED: self._on_alert_created_ev,
            ALERT_RESOLVED: self._on_alert_resolved_ev,
            TRUCK_UPDATED: self._on_truck_updated_ev,
            DRIVER_UPDATED: self._on_driver_updated_ev,
            DRIVER_DELETED: self._on_driver_deleted_ev,
        }
        for event_type, handler in handlers.items():
            self._event_bus.subscribe(event_type, handler)
            self._event_handlers[event_type] = handler
        logger.debug("QtDispatchBoardView subscribed to %d event types", len(handlers))

    def _unsubscribe_events(self) -> None:
        for event_type, handler in list(self._event_handlers.items()):
            try:
                self._event_bus.unsubscribe(event_type, handler)
            except Exception:
                pass
        self._event_handlers.clear()
        logger.debug("QtDispatchBoardView unsubscribed all events")

    # ── Dispatch helpers ─────────────────────────────────────────────────────

    def _dispatch(self, fn) -> None:
        """Schedule *fn* to run on the Qt main event loop."""
        if self._destroyed:
            return
        QTimer.singleShot(0, fn)

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_trip_created_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_trip_created(e))

    def _on_status_changed_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_status_changed(e))

    def _on_trip_updated_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_trip_updated(e))

    def _on_trip_assigned_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_trip_assigned(e))

    def _on_alert_created_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_alert_created(e))

    def _on_alert_resolved_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_alert_resolved(e))

    def _on_truck_updated_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_truck_updated(e))

    def _on_driver_updated_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_driver_updated(e))

    def _on_driver_deleted_ev(self, ev):
        self._dispatch(lambda e=ev: self._handle_driver_deleted(e))

    # ── Event handlers implementation ────────────────────────────────────────

    def _handle_trip_created(self, ev) -> None:
        data = ev.get("data", {})
        trip_id = data.get("trip_id")
        if not trip_id:
            return
        try:
            trip = self._trip_repo.get_by_id(int(trip_id))
            if not trip:
                return
            card_data = self._build_card_data(trip)
            planned_col = self._columns.get("Planned")
            if planned_col:
                card = QtTripCard(
                    planned_col,
                    card_data,
                    on_click=self._on_card_click,
                    on_drag_start=self._on_drag_start,
                    on_assign_truck=self._on_assign_truck,
                    on_assign_driver=self._on_assign_driver,
                    on_select_changed=self._on_card_select_changed,
                    on_assign_both=self._on_assign_both,
                )
                planned_col.add_card(card, index=0)
            logger.debug("Trip %d card added to Planned column", trip_id)
        except Exception:
            logger.debug("Failed to handle trip.created for %s", trip_id, exc_info=True)

    def _handle_status_changed(self, ev) -> None:
        try:
            data = ev.get("data", {})
            trip_id = data.get("trip_id")
            new_status = data.get("new_status")
            if not trip_id or not new_status:
                return
            column_key = STATUS_TO_COLUMN.get(new_status)
            if not column_key:
                return
            card = self._find_card_by_trip_id(trip_id)
            if not card:
                return
            target = self._columns.get(column_key)
            if not target:
                return
            source = self._find_column_for_card(card)
            if source == target:
                card.trip_data["status"] = new_status
                card.set_delayed(False, 0)
                return

            card_data = dict(card.trip_data)
            card_data["status"] = new_status

            if source:
                source.remove_card(card)

            new_card = QtTripCard(
                target,
                card_data,
                on_click=self._on_card_click,
                on_drag_start=self._on_drag_start,
                on_assign_truck=self._on_assign_truck,
                on_assign_driver=self._on_assign_driver,
                on_select_changed=self._on_card_select_changed,
                on_assign_both=self._on_assign_both,
            )
            target.add_card(new_card, index=0)

            if new_status == "Delivered":
                self._resolve_delay_alert(new_card)
            self._evaluate_single_delay(new_card)
            logger.debug("Trip %d moved to %s column via event", trip_id, column_key)
        except Exception:
            logger.exception("Failed to handle status change for trip %s", trip_id)

    def _handle_trip_updated(self, ev) -> None:
        data = ev.get("data", {})
        trip_id = data.get("trip_id")
        if not trip_id:
            return
        self._refresh_card_in_place(trip_id)

    def _handle_trip_assigned(self, ev) -> None:
        data = ev.get("data", {})
        trip_id = data.get("trip_id")
        if not trip_id:
            return
        card = self._find_card_by_trip_id(trip_id)
        if not card:
            return
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if trip:
                card.trip_data["truck_plate"] = trip.get("truck_number", "")
                card.trip_data["driver_name"] = trip.get("driver_name", "")
                card.trip_data["driver_id"] = trip.get("driver_id")
                card.update_truck(trip.get("truck_number", ""))
                card.update_driver(trip.get("driver_name", ""), trip.get("driver_id"))
        except Exception:
            logger.debug("Failed to refresh assignment for trip %d", trip_id, exc_info=True)

    def _handle_alert_created(self, ev) -> None:
        data = ev.get("data", {})
        alert = data.get("alert", {})
        trip_id = alert.get("trip_id")
        if not trip_id:
            return
        try:
            tid = int(trip_id)
        except (ValueError, TypeError):
            return
        self._alert_counts[tid] = self._alert_counts.get(tid, 0) + 1
        card = self._find_card_by_trip_id(tid)
        if card:
            card.trip_data["alerts_count"] = self._alert_counts[tid]

    def _handle_alert_resolved(self, ev) -> None:
        data = ev.get("data", {})
        alert = data.get("alert", {})
        trip_id = alert.get("trip_id")
        if not trip_id:
            return
        try:
            tid = int(trip_id)
        except (ValueError, TypeError):
            return
        current = self._alert_counts.get(tid, 0)
        self._alert_counts[tid] = max(0, current - 1)
        card = self._find_card_by_trip_id(tid)
        if card:
            card.trip_data["alerts_count"] = self._alert_counts.get(tid, 0)

    def _handle_truck_updated(self, ev) -> None:
        data = ev.get("data", {})
        truck_id = data.get("truck_id")
        truck_plate = data.get("plate_number")
        if not truck_id and not truck_plate:
            return
        for col in self._columns.values():
            for card in col._cards:
                card_plate = card.trip_data.get("truck_plate", "")
                card_truck_id = card.trip_data.get("truck_id")
                if (truck_plate and card_plate == truck_plate) or \
                   (truck_id is not None and card_truck_id == truck_id):
                    try:
                        trip_id = card.trip_data.get("trip_id_num")
                        self._refresh_card_in_place(trip_id)
                    except Exception:
                        pass

    def _handle_driver_updated(self, ev) -> None:
        try:
            data = ev.get("data", {})
            driver_id = data.get("driver_id")
            if not driver_id:
                return
            for col in self._columns.values():
                for card in col._cards:
                    if card.trip_data.get("driver_id") == driver_id:
                        card.update_driver(
                            data.get("name", card.trip_data.get("driver_name", "")),
                            driver_id,
                        )
        except Exception:
            pass

    def _handle_driver_deleted(self, ev) -> None:
        try:
            data = ev.get("data", {})
            driver_id = data.get("driver_id")
            if not driver_id:
                return
            for col in self._columns.values():
                for card in col._cards:
                    if card.trip_data.get("driver_id") == driver_id:
                        card.update_driver("", None)
        except Exception:
            pass

    def _find_card_by_trip_id(self, trip_id: int) -> Optional[QtTripCard]:
        for col in self._columns.values():
            for card in col._cards:
                if card.trip_data.get("trip_id_num") == trip_id:
                    return card
        return None

    def _refresh_card_in_place(self, trip_id: int) -> None:
        card = self._find_card_by_trip_id(trip_id)
        if not card:
            return
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if not trip:
                return
            card.trip_data["truck_plate"] = trip.get("truck_number", "")
            card.trip_data["driver_name"] = trip.get("driver_name", "")
            card.trip_data["driver_id"] = trip.get("driver_id")
            card.trip_data["eta"] = trip.get("end_date", "")
            card.trip_data["departure_date"] = trip.get("start_date", "")
            card.update_truck(trip.get("truck_number", ""))
            card.update_driver(trip.get("driver_name", ""), trip.get("driver_id"))
            card.trip_data["alerts_count"] = self._alert_counts.get(trip_id, 0)
            self._evaluate_single_delay(card)
        except Exception:
            logger.debug("Failed to refresh card for trip %d", trip_id, exc_info=True)

    def _evaluate_single_delay(self, card: QtTripCard) -> None:
        try:
            now = datetime.now()
            is_delayed, minutes_overdue = self._is_trip_delayed(card.trip_data, now)
            card.set_delayed(is_delayed, minutes_overdue)
            if is_delayed:
                self._create_delay_alert(card, minutes_overdue)
        except Exception:
            pass

    def _resolve_delay_alert(self, card: QtTripCard) -> None:
        trip_id = card.trip_data.get("trip_id_num")
        if not trip_id:
            return
        existing = self._alert_mgr.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000,
        )
        for alert in existing:
            if alert.trip_id == str(trip_id):
                self._alert_mgr.resolve_alert(alert.id)
                logger.info("Resolved delay alert for trip %d", trip_id)
                return

    # ══════════════════════════════════════════════════════════════════════════
    # i18n
    # ══════════════════════════════════════════════════════════════════════════

    def _on_language_changed(self, lang: str) -> None:
        try:
            self._title_lbl.setText(t("dispatch_board.title"))
            self._subtitle_lbl.setText(t("dispatch_board.subtitle"))
            self._refresh_btn.setText(f"\u21bb {t('dispatch_board.refresh')}")
            tab_labels = {
                "board": t("dispatch_board.tabs_board"),
                "alerts": t("dispatch_board.tabs_alerts"),
                "timeline": t("dispatch_board.tabs_timeline"),
            }
            self._tabs.refresh_translations(tab_labels)
            self._export_csv_btn.setText(t("dispatch_board.export_csv"))
            self._export_pdf_btn.setText(t("dispatch_board.export_pdf"))
        except Exception:
            pass
        for col in self._columns.values():
            col.refresh_title()

    # ══════════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════════════════

    def wakeup(self) -> None:
        """Called when the view becomes visible (e.g. tab switch)."""
        if self._destroyed:
            return
        self._subscribe_events()
        self._start_load()
        if self._refresh_timer is not None and not self._refresh_timer.isActive():
            self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

    def handle_nav_data(self, data: Dict[str, Any]) -> None:
        """Store trip_id from alert navigation — used to highlight the trip after load."""
        self._pending_nav_trip_id = data.get("trip_id")
        self._start_load()

    def shutdown(self) -> None:
        """Called when the view is hidden or the application is shutting down."""
        self._destroyed = True

        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

        if self._delay_timer is not None:
            self._delay_timer.stop()
            self._delay_timer = None

        if self._live_timer is not None:
            self._live_timer.stop()
            self._live_timer = None

        if self._detail_panel is not None:
            try:
                self._detail_panel.close()
            except Exception:
                pass
            self._detail_panel = None

        self._unsubscribe_events()
        try:
            self._status_engine.shutdown()
        except Exception:
            pass

        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
