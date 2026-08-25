"""PySide6 main window controller for Operion ERP.

Replaces ``ui/main_window.py`` for the Qt branch. Manages the application shell,
sidebar navigation, view switching via ``QStackedWidget``, and service lifecycle.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from config import Config
from services.client_service import ClientService
from ui.design_tokens import FADE_MS
from ui.mode_guard import ConnectionMode, detect_mode
from services.fleet_service import FleetService
from services.fuel_price_service import FuelPriceService
from services.i18n import t
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    SETTINGS_UPDATED,
    SYNC_COMPLETED,
    TOUR_REPLAY_REQUESTED,
    EventBus,
)
from services.trip_service import TripService
from ui.app_shell import AppShell
from services.csv_service import CsvService
from services.draft_service import DraftService
from services.numbering_service import NumberingService
from services.status_service import canonical_status
from ui.copilot.controllers.copilot_controller import CoPilotController
from ui.copilot.controllers.tour_controller import TourController
from ui.copilot.controllers.struggle_detector import StruggleDetector
from ui.copilot.controllers.ask_ai_menu import AskAIMenu
from ui.copilot.widgets.guided_overlay_widget import GuidedOverlayWidget
from ui.copilot import tour_tracker
from ui.performance_timer import PerfTimer, timing_report, timing_table, reset_timings
from ui.views import (
    QtAnalyticsView,
    QtCalculatorView,
    QtClientWorkspace,
    QtCopilotView,
    QtDispatchBoardView,
    QtDocumentCenterView,
    QtDriverManager,
    QtFleetTab,
    QtFleetTrackingView,
    FreightSearchView,
    QtGeneratorsView,
    QtHistoryView,
    QtMaintenanceAnalyticsView,
    QtMaintenanceControlPanel,
    QtMigrationCenterView,
    QtOverviewView,
    QtRouteHistoryView,
    QtRoutePlannerView,
    QtSettingsView,
    QtTachoImportView,
    QtTeamView,
)

logger = logging.getLogger(__name__)

# ── Connection-mode aware module availability ─────────────────────────────
# Every module in ``_ALL_MODULE_KEYS`` is now remote-capable: each view
# either receives a remote service through its view factory (Tier-1: analytics,
# history, fleet, driver_manager, maintenance, invoices, freight_exchange,
# clients; Tier-2: dispatch_board, tracking, documents, maintenance_control)
# or degrades gracefully when no local database is available.
#
# ``_modules_available_in`` is kept as the single per-instance availability
# decision point; all modules are available in every mode.
_ALL_MODULE_KEYS: frozenset[str] = frozenset({
    "calculator", "overview", "route_planner", "analytics", "history",
    "route_history", "dispatch_board", "tracking", "fleet", "driver_manager",
    "clients", "documents", "maintenance", "maintenance_control",
    "tachograph", "invoices", "team", "settings", "migration_center",
    "freight_exchange", "copilot",
})


def _modules_available_in(mode: ConnectionMode) -> set[str]:
    """Factory keys that may be created in *mode*.

    All modules are remote-capable now; this hook is kept so availability
    policy stays centralised if a future module needs LOCAL-only gating.
    """
    return set(_ALL_MODULE_KEYS)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(
        self,
        db,
        api,
        prefs=None,
        ops=None,
        api_client=None,
    ):
        super().__init__()
        self.db = db
        self.api = api
        self.ops = ops
        self.prefs = prefs
        self._api_client = api_client

        self._event_bus = ops.event_bus if ops is not None else EventBus()
        self._module_cache: dict = {}
        self._active_module: str | None = None
        self._nav_stack: list[tuple[str, dict[str, Any] | None]] = []
        self._max_nav_stack = 20
        self._fuel_timer: QTimer | None = None

        self._page_anim: QPropertyAnimation | None = None

        self._init_services()

        # Connection mode guard — detect whether we're LOCAL, REMOTE, or UNKNOWN
        self._mode = detect_mode(self.db, self._api_client)
        logger.info("App connection mode: %s", self._mode.value)

        # Modules that require local DB access are hidden/disabled outside
        # LOCAL mode.  Availability is decided per instance; the class-level
        # factory registry (``MainWindow._VIEW_FACTORIES``) keeps every module
        # so LOCAL-mode behaviour is unchanged.
        self._available_modules = _modules_available_in(self._mode)

        # Determine user role for conditional nav items
        self._user_role = "dispatcher"  # fallback
        try:
            from client.auth_manager import get_auth
            auth_mgr = get_auth()
            if auth_mgr is not None:
                self._user_role = auth_mgr.role or "dispatcher"
        except Exception:
            pass

        # ── Guided Tour System (§34) — must init before _build_ui (nav triggers _switch_module) ──
        self._struggle_detector = StruggleDetector(self)
        self._struggle_detector.struggle_detected.connect(self._on_struggle_detected)
        self._tour_overlay = GuidedOverlayWidget(self)
        self._tour_controller = TourController(self)
        self._tour_controller.set_overlay(self._tour_overlay)

        self._build_ui()
        self._setup_shortcuts()
        self._init_fuel_status()
        self._warmup_started = False

        self._sub_settings = self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)
        self._sub_alert_created = self._event_bus.subscribe(ALERT_CREATED, self._on_alert_event)
        self._sub_alert_resolved = self._event_bus.subscribe(ALERT_RESOLVED, self._on_alert_event)
        self._sub_tour_replay = self._event_bus.subscribe(TOUR_REPLAY_REQUESTED, self._on_tour_replay_requested)

        # ── Ask AI context menu (§34.12) ────────────────────────────────
        self._ask_ai_menu = AskAIMenu(self)
        self._ask_ai_menu.set_active_screen_getter(lambda: self._active_module or "")
        self._ask_ai_menu.ask_ai_requested.connect(self._on_ask_ai_requested)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._ask_ai_menu)

        # Check for first-launch onboarding (after UI is fully settled)
        QTimer.singleShot(1500, self._check_onboarding)

        # Initial alert refresh
        QTimer.singleShot(500, self, self._refresh_alerts)

        # ── Performance: pre-create all pages in background ──
        # After the UI is visible, warm up all view modules so
        # navigation is instant (no lazy creation cost).
        self._start_warmup()

    def _init_services(self):
        if self.db is not None:
            from services.preferences import PreferencesManager

            self.prefs = self.prefs or PreferencesManager(self.db)
            self.prefs.load()

            self.fleet_service = FleetService(self.db)
            self.trip_service = TripService(self.db)
            self.client_service = ClientService(self.db)

            from repositories.driver_repository import DriverRepository
            from repositories.fleet_repository import FleetRepository
            from services.analytics_service import AnalyticsService
            from services.driver_truck_service import DriverTruckService
            from services.invoicing.service import InvoiceService

            self.analytics_service = AnalyticsService(self.db)
            self.driver_service = DriverRepository(self.db)
            self.dta_service = DriverTruckService(self.db)
            self.maintenance_service = FleetRepository(self.db)
            self.invoice_service = InvoiceService(self.db, prefs=self.prefs)

            if self.ops is None:
                from services.operations.operations_engine import OperationsEngine
                self.ops = OperationsEngine(self.db, prefs=self.prefs)
                self.ops.start()

            from services.fleet_tracking_service import fleet_tracking_service
            fleet_tracking_service.initialize(self.db)

            # Remote-only service slots — unused in LOCAL mode (views build
            # their own local services from the DB handle).
            self.dispatch_service = None
            self.control_panel_service = None
            self.document_service = None
            self.migration_service = None

            # API-backed services — no local equivalents exist
            self.freight_service = None
            self.copilot_service = None
            self.feature_flags = None
        else:
            if self.prefs is None:
                from client.remote_preferences import RemotePreferences
                self.prefs = RemotePreferences()
            self.prefs.load()

            if self._api_client is not None:
                from client.remote_services import (
                    RemoteClientService,
                    RemoteFleetService,
                    RemoteTripService,
                )
                from client.remote_dispatch_service import RemoteDispatchService
                from client.remote_control_panel_service import RemoteControlPanelService
                from client.remote_document_service import RemoteDocumentService

                self.fleet_service = RemoteFleetService(self._api_client)
                self.trip_service = RemoteTripService(self._api_client)
                self.client_service = RemoteClientService(self._api_client)
                self.dispatch_service = RemoteDispatchService(self._api_client)
                self.control_panel_service = RemoteControlPanelService(self._api_client)
                self.document_service = RemoteDocumentService(self._api_client)

                from client.remote_freight_exchange import RemoteFreightExchangeService
                from client.remote_copilot import RemoteCopilotService
                from client.remote_feature_flags import RemoteFeatureFlagService
                from client.remote_analytics import RemoteAnalyticsService
                from client.remote_driver_service import RemoteDriverService
                from client.remote_maintenance import RemoteMaintenanceService
                from client.remote_invoice_service import RemoteInvoiceService
                from client.remote_migration_service import RemoteMigrationService

                self.analytics_service = RemoteAnalyticsService(self._api_client)
                self.driver_service = RemoteDriverService(self._api_client)
                self.dta_service = self.driver_service
                self.maintenance_service = RemoteMaintenanceService(self._api_client)
                self.invoice_service = RemoteInvoiceService(self._api_client)

                self.freight_service = RemoteFreightExchangeService(self._api_client)
                self.copilot_service = RemoteCopilotService(self._api_client)
                self.feature_flags = RemoteFeatureFlagService(self._api_client)
                self.migration_service = RemoteMigrationService(self._api_client)

                # NOTE: fleet_tracking_service stays LOCAL-only — it is never
                # initialized in remote mode (no API equivalent).
            else:
                self.fleet_service = None
                self.trip_service = None
                self.client_service = None
                self.dispatch_service = None
                self.control_panel_service = None
                self.document_service = None
                self.analytics_service = None
                self.driver_service = None
                self.dta_service = None
                self.maintenance_service = None
                self.invoice_service = None
                self.freight_service = None
                self.copilot_service = None
                self.feature_flags = None
                self.migration_service = None

            if self.ops is None:
                from client.remote_ops_stub import RemoteOpsStub
                self.ops = RemoteOpsStub(api_client=self._api_client)

        # Shared centralized services
        self._csv_service = CsvService()
        self._draft_service = DraftService()
        self._numbering_service = NumberingService(self.db) if self.db else None

        self._fuel_service = FuelPriceService()
        self._fuel_service.refresh_if_stale()

    def _build_ui(self):
        self.setWindowTitle(Config.APP_NAME)
        self.resize(1400, 900)
        self.setMinimumSize(1024, 600)

        self.app_shell = AppShell(
            self,
            self.db,
            on_nav_select=self._switch_module,
            prefs=self.prefs,
            ops=self.ops,
        )
        self.nav = self.app_shell.nav

        self._build_nav()
        self.app_shell.top_bar.back_clicked.connect(self._go_back)
        self.app_shell.top_bar.recent_clicked.connect(lambda vk: self._switch_module(vk))
        self.app_shell.top_bar.report_issue_clicked.connect(
            self._on_report_issue,
        )
        self.app_shell.view_container.updateGeometry()

    def _build_nav(self):
        """Build the full navigation sidebar."""
        nav = self.nav
        available = self._available_modules

        def _add_group(group_key: str, items: list[tuple[str, str, str]]) -> None:
            """Add a group + its items, skipping modules unavailable in the
            current connection mode (remote mode hides local-DB-only modules).

            The group label is only added when at least one of its items
            survives the filter, avoiding orphan group headers.
            """
            kept = [(k, label, i18n) for k, label, i18n in items if k in available]
            if not kept:
                return
            nav.add_group(t(group_key), group_key)
            for key, label, i18n_key in kept:
                nav.add_item(key, label, i18n_key=i18n_key)

        _add_group("nav.group_overview", [
            ("overview", t("nav.overview"), "nav.overview"),
            ("analytics", t("nav.analytics"), "nav.analytics"),
        ])

        _add_group("nav.group_operations", [
            ("route_planner", t("nav.routes"), "nav.routes"),
            ("calculator", t("nav.calculator"), "nav.calculator"),
            ("dispatch_board", t("nav.dispatch_board"), "nav.dispatch_board"),
            ("tracking", t("nav.live_tracking"), "nav.live_tracking"),
            ("freight_exchange", t("freight.title"), "freight.title"),
        ])

        _add_group("nav.group_fleet", [
            ("fleet", t("nav.fleet"), "nav.fleet"),
            ("driver_manager", t("nav.driver_manager"), "nav.driver_manager"),
            ("clients", t("nav.clients"), "nav.clients"),
            ("documents", t("nav.documents"), "nav.documents"),
            ("maintenance", t("nav.maintenance_analytics"), "nav.maintenance_analytics"),
            ("maintenance_control", t("nav.maintenance_control"), "nav.maintenance_control"),
            ("tachograph", t("nav.tachograph"), "nav.tachograph"),
        ])

        _add_group("nav.group_finance", [
            ("invoices", t("nav.generators"), "nav.generators"),
            ("history", t("nav.history"), "nav.history"),
            ("route_history", t("nav.route_history"), "nav.route_history"),
        ])

        _add_group("nav.group_tools", [
            ("copilot", t("nav.copilot"), "nav.copilot"),
            ("migration_center", t("nav.migration_center"), "nav.migration_center"),
        ])

        # ── Administration (manager / admin only) ──
        if self._user_role in ("admin", "manager"):
            _add_group("nav.group_administration", [
                ("team", t("nav.team"), "nav.team"),
            ])

        nav.add_settings_item("settings", t("nav.settings"))

        # Show the first available module on startup.  In remote mode the
        # local-DB-only modules (including the usual default, ``overview``)
        # are hidden, so fall back to the first available module.
        initial_key = "overview" if "overview" in available else self._first_available_key()
        nav.select(initial_key)

    def _first_available_key(self) -> str:
        """First available module following the canonical warmup order."""
        for key in self._WARMUP_KEYS:
            if key in self._available_modules:
                return key
        return next(iter(self._available_modules), "overview")

    def _setup_shortcuts(self):
        self._shortcut_calculate = QWidgetShortcut(self, Qt.Key_S, Qt.ControlModifier, self._open_calculator)
        self._shortcut_history = QWidgetShortcut(self, Qt.Key_H, Qt.ControlModifier, self._open_history)

        # ── Back navigation (Alt+Left) ──
        self._shortcut_back = QShortcut(QKeySequence("Alt+Left"), self, self._go_back)

        # ── Navigation shortcuts (Ctrl+1..Ctrl+9) ──
        self._nav_shortcuts: list[QShortcut] = []
        _nav_keys = [
            ("Ctrl+1", "overview"),
            ("Ctrl+2", "analytics"),
            ("Ctrl+3", "route_planner"),
            ("Ctrl+4", "calculator"),
            ("Ctrl+5", "dispatch_board"),
            ("Ctrl+6", "tracking"),
            ("Ctrl+7", "fleet"),
            ("Ctrl+8", "driver_manager"),
            ("Ctrl+9", "clients"),
        ]
        for seq, module_key in _nav_keys:
            if module_key not in self._available_modules:
                continue
            sc = QShortcut(QKeySequence(seq), self, lambda k=module_key: self._switch_module(k))
            sc.setAutoRepeat(False)
            self._nav_shortcuts.append(sc)

    def _init_fuel_status(self):
        self._update_fuel_status()
        self._fuel_timer = QTimer(self)
        self._fuel_timer.timeout.connect(self._update_fuel_status)
        self._fuel_timer.start(60_000)

    def _update_fuel_status(self):
        text = self._fuel_status_text()
        logger.debug("Fuel status: %s", text)
        with contextlib.suppress(Exception):
            self.app_shell.set_fuel_status(text)

    def _fuel_status_text(self) -> str:
        if self._fuel_service.is_available():
            age = self._fuel_service.age_seconds()
            if age is not None and age < 3600:
                age_str = f"{int(age/60)}m" if age >= 60 else f"{int(age)}s"
            elif age is not None:
                age_str = f"{age/3600:.1f}h"
            else:
                age_str = "?"
            return (
                f"⛽ {t('main.fuel_updated_at').format(self._fuel_service.last_updated_str())}"
                f" ({t('main.fuel_age').format(age_str)})"
            )
        return f"⛽ {t('main.fuel_offline')}"

    def _animate_page_switch(self, frame: QWidget) -> None:
        """Cross-fade to *frame* using QPropertyAnimation on opacity.

        Phase 10 spec: FADE_MS (150ms), OutCubic, content area only.
        """
        if self._page_anim is not None:
            self._page_anim.stop()
            self._page_anim.deleteLater()
            self._page_anim = None

        prev_effect = frame.graphicsEffect()
        if isinstance(prev_effect, QGraphicsOpacityEffect):
            prev_effect.deleteLater()

        effect = QGraphicsOpacityEffect(frame)
        # Set opacity to 0.0 BEFORE applying the effect so the DWM never
        # renders a one-frame flash at full opacity (the default) during
        # the first paint, which would appear as a ghost box at (0,0).
        effect.setOpacity(0.0)
        frame.setGraphicsEffect(effect)
        self.app_shell.view_container.setCurrentWidget(frame)

        self._page_anim = QPropertyAnimation(effect, b"opacity")
        self._page_anim.setDuration(FADE_MS)
        self._page_anim.setStartValue(0.0)
        self._page_anim.setEndValue(1.0)
        self._page_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._page_anim.start()

    def _switch_module(self, key: str, data: dict[str, Any] | None = None):
        # Track navigation for struggle detection
        self._struggle_detector.record_navigation(key)

        # Push current view onto nav stack before switching (skip duplicates)
        current = self._active_module
        if current and current != key:
            if not self._nav_stack or self._nav_stack[-1][0] != current:
                self._nav_stack.append((current, None))
                if len(self._nav_stack) > self._max_nav_stack:
                    self._nav_stack.pop(0)

        # Update back button and recent menu state
        self._update_back_button()

        with PerfTimer(f"nav.switch.{key}", log_level=logging.DEBUG):
            # If switching to the same view, avoid shutdown/recreate cycle.
            # Just re-show the frame, wakeup, and handle any nav data.
            if key == self._active_module:
                cache = self._module_cache.get(key)
                if cache and cache.get("frame") is not None:
                    obj = cache.get("obj")
                    if obj and hasattr(obj, "wakeup"):
                        with contextlib.suppress(Exception):
                            obj.wakeup()
                    if data and obj and hasattr(obj, "handle_nav_data"):
                        with contextlib.suppress(Exception):
                            obj.handle_nav_data(data)
                return

            # If a guided tour is active, cancel it on navigation away
            if self._tour_controller.is_tour_active():
                self._tour_controller.cancel_current()
                logger.info("Tour cancelled: user navigated away from active tour")

            old_key = self._active_module
            if old_key and old_key in self._module_cache:
                cache = self._module_cache[old_key]
                obj = cache.get("obj")
                if hasattr(obj, "shutdown"):
                    with contextlib.suppress(Exception):
                        obj.shutdown()

            if key not in self._module_cache:
                self._module_cache[key] = self._create_module(key)

            cache = self._module_cache.get(key)
            if cache and cache.get("frame") is not None:
                frame = cache["frame"]
                self._animate_page_switch(frame)
                obj = cache.get("obj")
                if obj and hasattr(obj, "wakeup"):
                    with contextlib.suppress(Exception):
                        obj.wakeup()
                if data and obj and hasattr(obj, "handle_nav_data"):
                    with contextlib.suppress(Exception):
                        obj.handle_nav_data(data)

            self._active_module = key
            with contextlib.suppress(Exception):
                self.nav.highlight(key)

    def _go_back(self) -> None:
        """Navigate to the previous view in the navigation stack."""
        # Close any open drawers/modals first
        if hasattr(self, '_views'):
            for view in self._views.values():
                if hasattr(view, '_detail_drawer') and view._detail_drawer and view._detail_drawer.isVisible():
                    view._close_detail_drawer()
                    return  # Don't navigate, just close the drawer
                if hasattr(view, '_detail_backdrop') and view._detail_backdrop and view._detail_backdrop.isVisible():
                    view._close_detail_drawer()
                    return

        if not self._nav_stack:
            return
        view_key, data = self._nav_stack.pop()
        self._active_module = None  # prevent re-push of current view
        self._switch_module(view_key, data)
        self._update_back_button()

    def _update_back_button(self) -> None:
        """Update back button visibility and populate recent items menu."""
        has_history = len(self._nav_stack) > 0
        self.app_shell.top_bar.set_back_enabled(has_history)

        # Build recent items list for the dropdown
        recent: list[tuple[str, str]] = []
        seen: set[str] = set()
        for view_key, _ in reversed(self._nav_stack):
            if view_key in seen:
                continue
            seen.add(view_key)
            name = t(f"nav.{view_key}", default=view_key.replace("_", " ").title())
            recent.append((view_key, name))
            if len(recent) >= 5:
                break
        recent.reverse()  # chronological order
        self.app_shell.top_bar._update_recent_menu(recent)

    def _on_report_issue(self) -> None:
        """Open the Report Issue dialog."""
        from ui.dialogs.report_issue_dialog import QtReportIssueDialog

        dlg = QtReportIssueDialog(
            parent=self, api_client=self._api_client,
        )
        dlg.exec()

    # ── Offline-first sync (Phase 4b) ────────────────────────────────────

    def setup_sync_ui(self, engine, outbox=None, pull=None, conflict_service=None):
        """Wire the sync engine's signals to the status indicator + journal.

        Called by ``main.setup_sync`` after the window is shown.  Connects
        the engine's signals to the top-bar status label and stores the
        services the conflict journal dialog needs.
        """
        self._sync_engine = engine
        self._sync_outbox = outbox
        self._sync_pull = pull
        self._sync_conflict_count = 0
        if conflict_service is None and self.db is not None:
            from services.sync_conflict_service import SyncConflictService
            conflict_service = SyncConflictService(self.db)
        self._sync_conflict_service = conflict_service

        engine.sync_status_changed.connect(self._on_sync_status_changed)
        engine.sync_finished.connect(self._on_sync_finished)
        engine.sync_error.connect(self._on_sync_error)
        self.app_shell.top_bar.sync_clicked.connect(self._open_sync_conflicts)
        self.app_shell.top_bar.set_sync_status("idle", 0)

    def _on_sync_status_changed(self, status: str) -> None:
        """Update the status label from ``sync_status_changed``."""
        from ui.widgets.sync_status import resolve_status

        self.app_shell.top_bar.set_sync_status(
            resolve_status(status, self._sync_conflict_count), self._sync_conflict_count
        )

    def _on_sync_finished(self, summary: dict) -> None:
        """Update the status label from ``sync_finished`` and notify views."""
        from ui.widgets.sync_status import resolve_status

        self._sync_conflict_count = int(summary.get("conflicts", 0) or 0)
        status = resolve_status(summary.get("status", "idle"), self._sync_conflict_count)
        self.app_shell.top_bar.set_sync_status(status, self._sync_conflict_count)
        # Views listening for data-change events refresh after a sync cycle.
        self._event_bus.publish(SYNC_COMPLETED, {"summary": summary})

    def _on_sync_error(self, message: str) -> None:
        """Log sync errors (the engine already surfaced them via the status)."""
        logger.warning("Sync error: %s", message)

    def _open_sync_conflicts(self) -> None:
        """Open the sync conflict journal dialog."""
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        dlg = SyncConflictDialog(
            parent=self,
            conflict_service=self._sync_conflict_service,
            pull_service=self._sync_pull,
            outbox_service=self._sync_outbox,
            engine=self._sync_engine,
        )
        dlg.exec()

    # ── Startup warmup: pre-create all pages ──────────────────────────

    _WARMUP_KEYS = [
        "overview", "analytics", "route_planner", "calculator",
        "dispatch_board", "tracking", "fleet", "driver_manager",
        "clients", "documents", "maintenance", "maintenance_control",
        "tachograph", "invoices", "history", "route_history",
        "copilot", "migration_center", "settings",
    ]

    def _start_warmup(self) -> None:
        """Pre-create all view modules after startup with staggered timing.

        Each page is created with a 200ms gap to keep the UI responsive during
        warmup. By the time the user navigates, most pages are ready.
        """
        # Never warm up modules that are unavailable in the current connection
        # mode (local-DB-only modules are skipped in remote mode).
        keys = [
            k for k in self._WARMUP_KEYS
            if k in self._available_modules and k not in self._module_cache
        ]
        if not keys:
            return

        logger.info("[PERF] Starting view warmup: %d pages", len(keys))
        self._warmup_started = True

        _WARMUP_STAGGER_MS = 200   # gap between view creations (was 50ms)

        def _warmup_next(idx: int = 0) -> None:
            if not self._warmup_started or idx >= len(keys):
                if idx >= len(keys):
                    logger.info("[PERF] View warmup complete")
                return
            key = keys[idx]
            if key not in self._module_cache:
                try:
                    with PerfTimer(f"warmup.create.{key}"):
                        self._module_cache[key] = self._create_module(key)
                except Exception:
                    # A single failing module must never abort the whole
                    # warmup chain — log and continue with the next module.
                    logger.exception(
                        "View warmup failed for module '%s'; continuing", key
                    )
            QTimer.singleShot(_WARMUP_STAGGER_MS, lambda: _warmup_next(idx + 1))

        # Start warmup after the window is fully rendered
        QTimer.singleShot(2000, lambda: _warmup_next(0))

    _VIEW_FACTORIES = None

    def _build_copilot_controller(self):
        """Build the Co-Pilot controller for the current connection mode.

        REMOTE mode: wraps the HTTP-backed ``RemoteCopilotService``.
        LOCAL mode: wraps :class:`client.local_copilot.LocalCopilotService`,
        which runs the Co-Pilot pipeline in-process against the local database
        — so the AI Co-Pilot works without a backend server or an LLM API key
        (Phase-1 keyword intents execute Level-0 tools locally).  The panel is
        therefore never left without a controller in a mode that can support it.

        Returns ``None`` only when neither a remote service nor a local
        database is available (degraded/unknown mode) — the panel then shows a
        clear setup message instead of failing silently.
        """
        if self.copilot_service is not None:
            return CoPilotController(remote=self.copilot_service, event_bus=self._event_bus)
        if self.db is not None:
            from client.local_copilot import LocalCopilotService

            local = LocalCopilotService(db=self.db, prefs=self.prefs)
            return CoPilotController(remote=local, event_bus=self._event_bus)
        logger.warning(
            "Co-Pilot controller unavailable: no remote service and no local DB"
        )
        return None

    def _create_module(self, key: str):
        """Factory for view modules — registry pattern."""
        parent = self.app_shell.view_container

        # Modules unavailable in the current connection mode are never
        # constructed — return a friendly placeholder instead of raising
        # (e.g. local-DB-only modules in remote mode).
        if key not in self._available_modules:
            logger.info(
                "Module '%s' is not available in %s mode — showing placeholder",
                key, self._mode.value,
            )
            widget = UnavailableModuleView(parent, key, self._mode.value)
            self.app_shell.view_container.addWidget(widget)
            return {"frame": widget, "obj": widget}

        if MainWindow._VIEW_FACTORIES is None:
            ac = self._api_client
            MainWindow._VIEW_FACTORIES = {
                # MODE: {self._mode.value}
                "calculator": lambda: QtCalculatorView(
                    parent, db=self.db, fleet_service=self.fleet_service,
                    trip_service=self.trip_service, client_service=self.client_service,
                    prefs=self.prefs, ops=self.ops, fuel_service=self._fuel_service,
                    api=self.api, api_client=ac,
                ),
                # MODE: {self._mode.value}  — remote-capable (degrades gracefully)
                "overview": lambda: QtOverviewView(
                    parent, db=self.db, ops=self.ops,
                    trip_service=self.trip_service,
                    fleet_service=self.fleet_service,
                ),
                # MODE: {self._mode.value}
                "route_planner": lambda: QtRoutePlannerView(parent, db=self.db, controller=self, api_client=ac),
                # MODE: {self._mode.value}  — remote-capable via analytics_service
                "analytics": lambda: QtAnalyticsView(
                    parent, db=self.db, prefs=self.prefs,
                    analytics_service=self.analytics_service,
                ),
                # MODE: {self._mode.value}  — remote-capable via trip/invoice services
                "history": lambda: QtHistoryView(
                    parent, db=self.db, controller=self,
                    prefs=self.prefs, ops=self.ops,
                    trip_service=self.trip_service,
                    invoice_service=self.invoice_service,
                ),
                # MODE: {self._mode.value}
                "route_history": lambda: QtRouteHistoryView(parent, db=self.db, controller=self, api_client=ac),
                # MODE: {self._mode.value}  — remote-capable via dispatch_service
                "dispatch_board": lambda: QtDispatchBoardView(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac, dispatch_service=self.dispatch_service, on_navigate=self._switch_module),
                # MODE: {self._mode.value}  — remote-capable via fleet_service (truck matching)
                "tracking": lambda: QtFleetTrackingView(parent, db=self.db, prefs=self.prefs, ops=self.ops, fleet_service=self.fleet_service, api_client=ac, on_navigate=self._switch_module),
                # MODE: {self._mode.value}  — remote-capable via fleet_service
                "fleet": lambda: QtFleetTab(
                    parent, db=self.db, ops=self.ops,
                    fleet_service=self.fleet_service,
                    api_client=ac,
                ),
                # MODE: {self._mode.value}  — remote-capable via driver/trip services
                "driver_manager": lambda: QtDriverManager(
                    parent, db=self.db, prefs=self.prefs,
                    driver_svc=self.driver_service,
                    trip_svc=self.trip_service,
                    dta_svc=self.dta_service,
                    tacho_repo=None,
                ),
                # MODE: {self._mode.value}  — remote-capable via client_service
                "clients": lambda: QtClientWorkspace(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops,
                    client_service=self.client_service,
                ),
                # MODE: {self._mode.value}  — remote-capable via document_service
                "documents": lambda: QtDocumentCenterView(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops,
                    document_service=self.document_service, api_client=ac,
                ),
                # MODE: {self._mode.value}  — remote-capable via maintenance_service
                "maintenance": lambda: QtMaintenanceAnalyticsView(
                    parent, db=self.db, repo=self.maintenance_service,
                ),
                # MODE: {self._mode.value}  — remote-capable via control/maintenance services
                "maintenance_control": lambda: QtMaintenanceControlPanel(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops,
                    control_service=self.control_panel_service,
                    maintenance_service=self.maintenance_service,
                    api_client=ac,
                ),
                # MODE: {self._mode.value}
                "tachograph": lambda: QtTachoImportView(parent, db=self.db, api_client=ac),
                # MODE: {self._mode.value}  — remote-capable via client/fleet/trip services
                "invoices": lambda: QtGeneratorsView(
                    parent, db=self.db, prefs=self.prefs,
                    client_service=self.client_service,
                    fleet_service=self.fleet_service,
                    trip_service=self.trip_service,
                ),
                # MODE: {self._mode.value}
                "team": lambda: QtTeamView(
                    parent, db=self.db, api_client=ac,
                ),
                # MODE: {self._mode.value}
                "settings": lambda: QtSettingsView(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac),
                # MODE: {self._mode.value}  — remote-capable via migration_service
                "migration_center": lambda: QtMigrationCenterView(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops,
                    migration_service=self.migration_service,
                ),
                # MODE: {self._mode.value}  — remote-capable via freight_service
                "freight_exchange": lambda: FreightSearchView(
                    self.db, parent=parent,
                    freight_service=self.freight_service,
                ),
                # MODE: {self._mode.value}  — controller always wired (local mode runs the pipeline in-process)
                "copilot": lambda: QtCopilotView(
                    parent,
                    controller=self._build_copilot_controller(),
                ),
            }

        factory = MainWindow._VIEW_FACTORIES.get(key)
        try:
            with PerfTimer(f"create.{key}"):
                widget = factory() if factory else PlaceholderView(parent, key)
        except Exception as exc:
            logger.exception("Failed to create module '%s'", key)
            widget = ErrorPlaceholderView(parent, key, str(exc))
        self.app_shell.view_container.addWidget(widget)
        return {"frame": widget, "obj": widget}

    def open_route_url(self, url: str) -> None:
        """Switch to the route planner and load a route from a share URL."""
        self._switch_module("route_planner", {"share_url": url})

    def open_route_file(self, path: str) -> None:
        """Switch to the route planner and load a route from a .operionroute file."""
        self._switch_module("route_planner", {"share_file": path})

    def _open_calculator(self):
        self._switch_module("calculator")

    def _open_history(self):
        self._switch_module("history")

    def _open_freight_exchange(self):
        self._switch_module("freight_exchange")

    # ── Guided Tour / Struggle Detection (§34) ────────────────────────────

    def _check_onboarding(self) -> None:
        """Start onboarding tour if this is the first launch."""
        try:
            if self._tour_controller.can_show_onboarding():
                logger.info("First launch detected — starting onboarding tour")
                self._tour_controller.start_onboarding()
            else:
                logger.debug("Onboarding already completed, skipping tour")
        except Exception as exc:
            logger.warning("Failed to check onboarding status: %s", exc)

    def _on_tour_replay_requested(self, ev: dict) -> None:
        """Handle tour replay request from settings."""
        workflow_id = ev.get("workflow_id", "app_overview")
        if workflow_id == "all":
            from ui.copilot import tour_tracker
            tour_tracker.clear_all_tours()
            # Default to onboarding
            self.replay_onboarding_tour()
        else:
            self._tour_controller.replay_tour(workflow_id)

    def _on_struggle_detected(self, workflow_id: str, tooltip_key: str) -> None:
        """Handle struggle detection — show a brief nudge tooltip."""
        try:
            if self._tour_controller.is_tour_active():
                return  # Don't interrupt an active tour

            # Show the overlay briefly with just the nudge tooltip
            script = None
            from ui.copilot.tour_scripts import ALL_SCRIPTS
            script_data = ALL_SCRIPTS.get(workflow_id)
            if script_data:
                steps = script_data.get("steps", [])
                if steps:
                    # Show just the first step as a nudge
                    nudge_step = dict(steps[0])
                    nudge_step["tooltip_key"] = tooltip_key
                    nudge_step["type"] = "dim"  # No highlight for nudges
                    nudge_step["target_element_id"] = None
                    self._tour_overlay.start_tour([nudge_step], title_key="")

                    # Auto-dismiss after 8 seconds
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(8000, self._tour_overlay.cancel)
        except Exception as exc:
            logger.debug("Struggle nudge failed: %s", exc)

    def replay_onboarding_tour(self) -> None:
        """Replay the onboarding tour (called from settings)."""
        self._tour_controller.replay_tour("app_overview")

    # ── Ask AI context menu (§34.12) ─────────────────────────────────────

    def _on_ask_ai_requested(self, question: str, active_screen: str) -> None:
        """Handle 'Ask AI about this' — navigate to Co-Pilot and send question."""
        self._switch_module("copilot")
        cache = self._module_cache.get("copilot")
        if cache:
            view = cache.get("obj")
            if view is not None and hasattr(view, "ask_about_element"):
                view.ask_about_element(question, active_screen or None)

    # ── Struggle detection integration ─────────────────────────────────────

    def _on_settings_updated(self, ev):
        if self.ops is not None and hasattr(self.ops, '_configure_smtp_from_db'):
            with contextlib.suppress(Exception):
                self.ops._configure_smtp_from_db()

    def _on_alert_event(self, ev):
        """Refresh alert count and data when alerts are created or resolved."""
        QTimer.singleShot(0, self, self._refresh_alerts)

    def _refresh_alerts(self):
        """Query OperationsEngine for active alerts and push to top bar."""
        try:
            if self.ops is not None:
                alerts = self.ops.get_active_alerts(limit=50)
                count = self.ops.get_active_alert_count()
                self.app_shell.set_alert_count(count)
                self.app_shell.top_bar.set_alerts(alerts)
        except Exception:
            logger.debug("Could not refresh alerts", exc_info=True)

    def closeEvent(self, event):
        if self._page_anim is not None:
            self._page_anim.stop()
            self._page_anim.deleteLater()
            self._page_anim = None
        for key, cached in list(self._module_cache.items()):
            try:
                obj = cached.get("obj") or cached.get("frame")
                if obj is not None:
                    if hasattr(obj, "shutdown"):
                        obj.shutdown()
                    obj.deleteLater()
            except Exception:
                logger.debug("Error shutting down module %s", key, exc_info=True)
        self._module_cache.clear()
        with contextlib.suppress(Exception):
            self.app_shell.destroy()
        try:
            if self.ops is not None:
                self.ops.stop()
        except Exception:
            pass
        try:
            from services.document_service import DocumentService
            DocumentService.shutdown()
        except Exception:
            pass
        if self._fuel_timer is not None:
            self._fuel_timer.stop()
        self._event_bus.unsubscribe(SETTINGS_UPDATED, self._sub_settings)
        self._event_bus.unsubscribe(ALERT_CREATED, self._sub_alert_created)
        self._event_bus.unsubscribe(ALERT_RESOLVED, self._sub_alert_resolved)
        self._event_bus.unsubscribe(TOUR_REPLAY_REQUESTED, self._sub_tour_replay)
        event.accept()


class PlaceholderView(QWidget):
    """Empty placeholder view used until a module is fully migrated."""

    def __init__(self, parent: QWidget | None, key: str):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(f"{key}\n(Module not yet migrated)")
        label.setProperty("role", "muted")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)


class ErrorPlaceholderView(QWidget):
    """Shown when a view module raises an exception during construction."""

    def __init__(self, parent: QWidget | None, key: str, error: str):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(f"⚠ {key}")
        title.setProperty("role", "heading")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        msg = QLabel(f"Failed to load module.\n{error}")
        msg.setProperty("role", "muted")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)


class UnavailableModuleView(QWidget):
    """Shown when a module is not available in the current connection mode.

    Replaces a hard error for local-DB-only modules while the app runs in
    remote (API-only) mode, so navigation degrades gracefully instead of
    showing the raw ``RuntimeError`` from ``guard_local_access``.
    """

    def __init__(self, parent: QWidget | None, key: str, mode: str):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(key)
        title.setProperty("role", "heading")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        msg = QLabel(
            f"{key} requires local database access and is not available "
            f"in {mode} mode.\nConnect to a local database to use this module."
        )
        msg.setProperty("role", "muted")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)


class QWidgetShortcut(QObject):
    """Small helper to attach a key sequence to a QWidget callback."""

    def __init__(self, parent: QWidget, key: Qt.Key, modifier: Qt.KeyboardModifier, callback):
        super().__init__(parent)
        self._key = key
        self._modifier = modifier
        self._callback = callback
        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress:
            if event.key() == self._key and (event.modifiers() & self._modifier) == self._modifier:
                self._callback()
                return True
        return False
