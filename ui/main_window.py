"""PySide6 main window controller for Operion ERP.

Replaces ``ui/main_window.py`` for the Qt branch. Manages the application shell,
sidebar navigation, view switching via ``QStackedWidget``, and service lifecycle.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from config import Config
from services.client_service import ClientService
from ui.mode_guard import ConnectionMode, detect_mode
from services.fleet_service import FleetService
from services.fuel_price_service import FuelPriceService
from services.i18n import t
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    SETTINGS_UPDATED,
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
        self._fuel_timer: QTimer | None = None

        self._page_anim: QPropertyAnimation | None = None

        self._init_services()

        # Connection mode guard — detect whether we're LOCAL, REMOTE, or UNKNOWN
        self._mode = detect_mode(self.db, self._api_client)
        logger.info("App connection mode: %s", self._mode.value)

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

    def _init_services(self):
        if self.db is not None:
            from services.preferences import PreferencesManager

            self.prefs = self.prefs or PreferencesManager(self.db)
            self.prefs.load()

            self.fleet_service = FleetService(self.db)
            self.trip_service = TripService(self.db)
            self.client_service = ClientService(self.db)

            if self.ops is None:
                from services.operations.operations_engine import OperationsEngine
                self.ops = OperationsEngine(self.db, prefs=self.prefs)
                self.ops.start()

            from services.fleet_tracking_service import fleet_tracking_service
            fleet_tracking_service.initialize(self.db)

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
                self.fleet_service = RemoteFleetService(self._api_client)
                self.trip_service = RemoteTripService(self._api_client)
                self.client_service = RemoteClientService(self._api_client)

                from client.remote_freight_exchange import RemoteFreightExchangeService
                from client.remote_copilot import RemoteCopilotService
                from client.remote_feature_flags import RemoteFeatureFlagService

                self.freight_service = RemoteFreightExchangeService(self._api_client)
                self.copilot_service = RemoteCopilotService(self._api_client)
                self.feature_flags = RemoteFeatureFlagService(self._api_client)
            else:
                self.fleet_service = None
                self.trip_service = None
                self.client_service = None
                self.freight_service = None
                self.copilot_service = None
                self.feature_flags = None

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
        self.app_shell.view_container.updateGeometry()

    def _build_nav(self):
        """Build the full navigation sidebar."""
        nav = self.nav

        nav.add_group(t("nav.group_overview"), "nav.group_overview")
        nav.add_item("overview", t("nav.overview"), i18n_key="nav.overview")
        nav.add_item("analytics", t("nav.analytics"), i18n_key="nav.analytics")

        nav.add_group(t("nav.group_operations"), "nav.group_operations")
        nav.add_item("route_planner", t("nav.routes"), i18n_key="nav.routes")
        nav.add_item("calculator", t("nav.calculator"), i18n_key="nav.calculator")
        nav.add_item("dispatch_board", t("nav.dispatch_board"), i18n_key="nav.dispatch_board")
        nav.add_item("tracking", t("nav.live_tracking"), i18n_key="nav.live_tracking")
        nav.add_item("freight_exchange", t("freight.title"), i18n_key="freight.title")

        nav.add_group(t("nav.group_fleet"), "nav.group_fleet")
        nav.add_item("fleet", t("nav.fleet"), i18n_key="nav.fleet")
        nav.add_item("driver_manager", t("nav.driver_manager"), i18n_key="nav.driver_manager")
        nav.add_item("clients", t("nav.clients"), i18n_key="nav.clients")
        nav.add_item("documents", t("nav.documents"), i18n_key="nav.documents")
        nav.add_item("maintenance", t("nav.maintenance_analytics"),
                     i18n_key="nav.maintenance_analytics")
        nav.add_item("maintenance_control", t("nav.maintenance_control"),
                     i18n_key="nav.maintenance_control")
        nav.add_item("tachograph", t("nav.tachograph"), i18n_key="nav.tachograph")

        nav.add_group(t("nav.group_finance"), "nav.group_finance")
        nav.add_item("invoices", t("nav.generators"), i18n_key="nav.generators")
        nav.add_item("history", t("nav.history"), i18n_key="nav.history")
        nav.add_item("route_history", t("nav.route_history"), i18n_key="nav.route_history")

        nav.add_group(t("nav.group_tools"), "nav.group_tools")
        nav.add_item("copilot", t("nav.copilot"), i18n_key="nav.copilot")
        nav.add_item("migration_center", t("nav.migration_center"), i18n_key="nav.migration_center")

        # ── Administration (manager / admin only) ──
        if self._user_role in ("admin", "manager"):
            nav.add_group(t("nav.group_administration"), "nav.group_administration")
            nav.add_item("team", t("nav.team"), i18n_key="nav.team")

        nav.add_settings_item("settings", t("nav.settings"))
        nav.select("overview")

    def _setup_shortcuts(self):
        self._shortcut_calculate = QWidgetShortcut(self, Qt.Key_S, Qt.ControlModifier, self._open_calculator)
        self._shortcut_history = QWidgetShortcut(self, Qt.Key_H, Qt.ControlModifier, self._open_history)

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

        Plan spec (Section 6, item 1): 120ms, ease-in-out, content area only.
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
        self._page_anim.setDuration(120)
        self._page_anim.setStartValue(0.0)
        self._page_anim.setEndValue(1.0)
        self._page_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._page_anim.start()

    def _switch_module(self, key: str, data: dict[str, Any] | None = None):
        # Track navigation for struggle detection
        self._struggle_detector.record_navigation(key)

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
            self._update_breadcrumb(key)
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
        self._update_breadcrumb(key)
        with contextlib.suppress(Exception):
            self.nav.highlight(key)

    def _update_breadcrumb(self, key: str) -> None:
        if key == "overview":
            crumb = t("nav.overview", default="Overview")
        else:
            crumb = t(f"nav.{key}", default=key.replace("_", " ").title())
        self.app_shell.set_breadcrumb(crumb)

    _VIEW_FACTORIES = None

    def _create_module(self, key: str):
        """Factory for view modules — registry pattern."""
        parent = self.app_shell.view_container

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
                # MODE: {self._mode.value}  — local DB only
                "overview": lambda: QtOverviewView(
                    parent, db=self.db, ops=self.ops,
                    trip_service=self.trip_service,
                    fleet_service=self.fleet_service,
                ),
                # MODE: {self._mode.value}
                "route_planner": lambda: QtRoutePlannerView(parent, db=self.db, controller=self, api_client=ac),
                # MODE: {self._mode.value}  — local DB only (analytics queries)
                "analytics": lambda: QtAnalyticsView(
                    parent, db=self.db, prefs=self.prefs,
                ),
                # MODE: {self._mode.value}  — local DB only
                "history": lambda: QtHistoryView(
                    parent, db=self.db, controller=self,
                    prefs=self.prefs, ops=self.ops,
                    trip_service=self.trip_service,
                ),
                # MODE: {self._mode.value}
                "route_history": lambda: QtRouteHistoryView(parent, db=self.db, controller=self, api_client=ac),
                # MODE: {self._mode.value}
                "dispatch_board": lambda: QtDispatchBoardView(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac),
                # MODE: {self._mode.value}  — local DB only (tracking uses local fleet_tracking_service)
                "tracking": lambda: QtFleetTrackingView(parent, db=self.db, prefs=self.prefs, ops=self.ops, on_navigate=self._switch_module),
                # MODE: {self._mode.value}
                "fleet": lambda: QtFleetTab(
                    parent, db=self.db, ops=self.ops,
                    fleet_service=self.fleet_service,
                    api_client=ac,
                ),
                # MODE: {self._mode.value}  — local DB only
                "driver_manager": lambda: QtDriverManager(
                    parent, db=self.db, prefs=self.prefs,
                    trip_svc=self.trip_service,
                ),
                # MODE: {self._mode.value}  — local DB only
                "clients": lambda: QtClientWorkspace(parent, db=self.db, prefs=self.prefs, ops=self.ops),
                # MODE: {self._mode.value}  — local DB only
                "documents": lambda: QtDocumentCenterView(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops,
                ),
                # MODE: {self._mode.value}  — local DB only (FleetRepository)
                "maintenance": lambda: QtMaintenanceAnalyticsView(parent, db=self.db),
                # MODE: {self._mode.value}  — local DB only
                "maintenance_control": lambda: QtMaintenanceControlPanel(parent, db=self.db, prefs=self.prefs, ops=self.ops),
                # MODE: {self._mode.value}
                "tachograph": lambda: QtTachoImportView(parent, db=self.db, api_client=ac),
                # MODE: {self._mode.value}  — local DB only
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
                # MODE: {self._mode.value}  — local DB only
                "migration_center": lambda: QtMigrationCenterView(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops,
                ),
                # MODE: {self._mode.value}  — local DB only (freight exchange)
                "freight_exchange": lambda: FreightSearchView(self.db, parent=parent),
                # MODE: {self._mode.value}
                "copilot": lambda: QtCopilotView(
                    parent,
                    controller=CoPilotController(remote=self.copilot_service) if self.copilot_service else None
                ),
            }

        factory = MainWindow._VIEW_FACTORIES.get(key)
        try:
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
