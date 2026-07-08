"""PySide6 dispatch board view — kanban board for trip dispatching.

Replaces the legacy 2282‑line dispatch_board_view.py.
Split into a sub‑package: dispatch_board.py (UI + lifecycle),
board_state.py (data loading / filtering / caches) and
board_actions.py (drag‑drop / assignments / transitions).
"""

from __future__ import annotations

import contextlib
import logging
import threading
from datetime import datetime
from typing import Any

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from repositories.route_repository import RouteRepository
from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from repositories.trip_repository import TripRepository
from services.client_service import ClientService
from services.conflict_service import TripConflictService
from services.driver_truck_service import DriverTruckService
from services.fleet_service import FleetService
from services.i18n import t
from ui.base_view import BaseView
from services.operations.alert_manager import AlertManager, AlertType
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    DRIVER_DELETED,
    DRIVER_UPDATED,
    TRIP_ASSIGNED,
    TRIP_CREATED,
    TRIP_STATUS_CHANGED,
    TRIP_UPDATED,
    TRUCK_CREATED,
    TRUCK_DELETED,
    TRUCK_UPDATED,
)
from services.operations.trip_status_engine import TripStatusEngine
from services.trip_service import TripService
from ui.components import Btn, EmptyState, Label, PageTitle
from ui.design_tokens import BORDER_DEFAULT, COLOR_NEUTRAL_DEFAULT, INFO, SP, SUCCESS, WARNING
from ui.widgets.dispatch_alerts_panel import QtDispatchAlertsPanel
from ui.widgets.dispatch_search_bar import STATUS_OPTIONS, QtDispatchSearchBar
from ui.widgets.dispatch_tabs import QtDispatchTabs
from ui.widgets.dispatch_timeline import QtDispatchTimeline
from ui.widgets.kanban_column import QtKanbanColumn
from ui.widgets.stat_card import StatCard
from ui.widgets.stat_card_row import StatCardRowContainer
from ui.widgets.trip_card import QtTripCard

from .board_actions import BoardActionsMixin
from .board_state import (
    COLUMN_DEFS,
    DELIVERED_DEFAULT_DAYS,
    STATUS_TO_COLUMN,
    BoardStateMixin,
)

logger = logging.getLogger(__name__)


class QtDispatchBoardView(BoardStateMixin, BoardActionsMixin, BaseView):
    """Kanban dispatch board for trip management.

    Embedded in a QStackedWidget in the main window.  Provides three tabs:
    - **Board** — horizontal scroll of ``QtKanbanColumn`` widgets
    - **Timeline** — Gantt-like ``QtDispatchTimeline``
    - **Alerts** — KPIs/alerts panel ``QtDispatchAlertsPanel``
    """

    REFRESH_INTERVAL_MS = 30_000

    # Cross-thread signal used to marshal work from background loaders
    # and event-bus subscribers into the GUI thread.
    _dispatchSignal = Signal(object)   # zero-arg callable

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
        ops=None,
        tacho_repo=None,
        api_client=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self._db = db
        self.prefs = prefs
        self.ops = ops
        self._tacho_repo = tacho_repo
        self._api_client = api_client

        # ── State ────────────────────────────────────────────────────────────
        self._columns: dict[str, QtKanbanColumn] = {}
        self._loading = False
        self._delivered_days = DELIVERED_DEFAULT_DAYS
        self._destroyed = False
        self._load_thread: threading.Thread | None = None

        # Repositories / services
        if db is not None:
            self._trip_repo = TripRepository(db)
            self._fleet_repo = FleetRepository(db)
            self._driver_repo = DriverRepository(db)
            self._route_repo = RouteRepository(db)
            self._status_engine = TripStatusEngine(db)
            self._trip_service = TripService(db)
            self._fleet_service = FleetService(db)
            self._client_service = ClientService(db)
            self._dta_service = DriverTruckService(db)
            self._conflict_service = TripConflictService(db)
        else:
            self._trip_repo = None
            self._fleet_repo = None
            self._driver_repo = None
            self._route_repo = None
            self._status_engine = None
            self._trip_service = None
            self._fleet_service = None
            self._client_service = None
            self._dta_service = None
            self._conflict_service = None
        self._alert_mgr = AlertManager()

        # Caches
        self._driver_cache: dict[int, dict | None] = {}
        self._route_cache: dict[str, dict | None] = {}
        self._alert_counts: dict[int, int] = {}
        self._event_handlers: dict[str, Any] = {}
        self._all_card_data: list[dict[str, Any]] = []
        self._search_query = ""
        self._search_statuses = list(STATUS_OPTIONS)
        self._conflict_alerts: dict[int, list] = {}

        # Selection / bulk
        self._detail_panel = None
        self._selected_cards: list[QtTripCard] = []

        # Drag-drop state
        self._drag_card: QtTripCard | None = None
        self._drag_source_col: QtKanbanColumn | None = None
        self._drag_target_col: QtKanbanColumn | None = None

        # Timers
        self._refresh_timer: QTimer | None = None
        self._delay_timer: QTimer | None = None
        self._live_timer: QTimer | None = None

        # i18n
        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        # Cross-thread marshal
        self._dispatchSignal.connect(self._run_dispatched)

        # ── Build ────────────────────────────────────────────────────────────
        self._build_ui()
        self.setAcceptDrops(True)
        self._subscribe_events()
        self._start_load()

        # ── Auto-refresh timer ───────────────────────────────────────────────
        self._refresh_timer = self._add_timer(self.REFRESH_INTERVAL_MS, self._start_load)

    # ══════════════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        _STATUS_DOT_COLORS = {
            "Planned": "#6B7280",
            "Loading": "#F59E0B",
            "In Transit": "#3B82F6",
            "Delivered": "#22C55E",
            "Cancelled": "#6B7280",
        }

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
        board_layout.setSpacing(SP["2"])

        # Search / filter bar
        self._search_bar = QtDispatchSearchBar(
            self._board_tab,
            on_search=self._on_search_filter,
        )
        board_layout.addWidget(self._search_bar)

        # ── Status card row ──────────────────────────────────────────────────
        self._status_container = QFrame()
        self._status_container.setObjectName("stat-card")
        status_layout = QVBoxLayout(self._status_container)
        status_layout.setContentsMargins(SP["5"], SP["5"], SP["5"], SP["5"])
        status_layout.setSpacing(0)

        self._status_row = StatCardRowContainer(self._status_container)
        self._status_cards: dict[str, StatCard] = {}
        for status_key, title_key, _accent in COLUMN_DEFS:
            card = StatCard(
                parent=None,
                label=t(title_key).upper(),
                value="0",
                status_dot_color=_STATUS_DOT_COLORS[status_key],
            )
            self._status_row.add_card(card)
            self._status_cards[status_key] = card

        status_layout.addWidget(self._status_row)
        board_layout.addWidget(self._status_container)

        # ── Bulk toolbar (hidden by default) ──────────────────────────────
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

        # ── Kanban columns + EmptyState (stacked) ─────────────────────────
        self._board_stack = QStackedWidget()

        # Page 0: Kanban columns
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

        for _i, (status_key, title_key, accent_color) in enumerate(COLUMN_DEFS):
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
            col.tripDropped.connect(self._on_card_dropped_on_column)

        scroll_area.setWidget(columns_container)
        self._board_stack.addWidget(scroll_area)  # index 0

        # Page 1: Empty state
        self._board_empty = EmptyState(
            parent=self._board_tab,
            icon_name="mdi6.truck",
            title=t("dispatch_board.no_results_title", default="No trips found"),
            subtitle=t("dispatch_board.no_results_subtitle", default="Try adjusting your search or filter criteria"),
        )
        self._board_stack.addWidget(self._board_empty)  # index 1

        board_layout.addWidget(self._board_stack, 1)

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
            TRUCK_CREATED: self._on_truck_updated_ev,
            TRUCK_UPDATED: self._on_truck_updated_ev,
            TRUCK_DELETED: self._on_truck_updated_ev,
            DRIVER_UPDATED: self._on_driver_updated_ev,
            DRIVER_DELETED: self._on_driver_deleted_ev,
        }
        for event_type, handler in handlers.items():
            self._subscribe(event_type, handler)
            self._event_handlers[event_type] = handler
        logger.debug("QtDispatchBoardView subscribed to %d event types", len(handlers))

    # ── Dispatch helpers ─────────────────────────────────────────────────────

    def _dispatch(self, fn) -> None:
        """Schedule *fn* to run on the Qt main event loop."""
        if self._destroyed:
            return
        self._dispatchSignal.emit(fn)

    def _run_dispatched(self, fn) -> None:
        """Slot for :attr:`_dispatchSignal` — runs *fn* on the GUI thread."""
        try:
            fn()
        except Exception:
            logger.exception("Dispatched callback raised")

    # ── Event dispatchers ─────────────────────────────────────────────────────

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

    # ── Card helpers used by event handlers and mixins ────────────────────────

    def _find_card_by_trip_id(self, trip_id: int):
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

    def _evaluate_single_delay(self, card) -> None:
        try:
            now = datetime.now()
            is_delayed, minutes_overdue = self._is_trip_delayed(card.trip_data, now)
            card.set_delayed(is_delayed, minutes_overdue)
            if is_delayed:
                self._create_delay_alert(card, minutes_overdue)
        except Exception:
            pass

    def _resolve_delay_alert(self, card) -> None:
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

    def handle_nav_data(self, data: dict[str, Any]) -> None:
        """Store trip_id from alert navigation — used to highlight the trip after load."""
        self._pending_nav_trip_id = data.get("trip_id")
        self._start_load()

    def shutdown(self) -> None:
        """Called when the view is hidden or the application is shutting down."""
        self._destroyed = True

        if self._load_thread is not None and self._load_thread.is_alive():
            self._load_thread.join(timeout=2)
            self._load_thread = None

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
            with contextlib.suppress(Exception):
                self._detail_panel.close()
            self._detail_panel = None

        with contextlib.suppress(Exception):
            self._status_engine.shutdown()

        super().shutdown()
