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
from services.fleet_service import FleetService
from services.fuel_price_service import FuelPriceService
from services.i18n import t
from services.operations.event_bus import ALERT_CREATED, ALERT_RESOLVED, SETTINGS_UPDATED, EventBus
from services.trip_service import TripService
from ui.app_shell import AppShell
from ui.views import (
    QtAnalyticsView,
    QtCalculatorView,
    QtClientWorkspace,
    QtDispatchBoardView,
    QtDocumentCenterView,
    QtDriverManager,
    QtFleetTab,
    QtFleetTrackingView,
    QtGeneratorsView,
    QtHistoryView,
    QtMaintenanceAnalyticsView,
    QtMaintenanceControlPanel,
    QtOverviewView,
    QtRouteHistoryView,
    QtRoutePlannerView,
    QtSettingsView,
    QtTachoImportView,
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
        self._build_ui()
        self._setup_shortcuts()
        self._init_fuel_status()

        self._sub_settings = self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)
        self._sub_alert_created = self._event_bus.subscribe(ALERT_CREATED, self._on_alert_event)
        self._sub_alert_resolved = self._event_bus.subscribe(ALERT_RESOLVED, self._on_alert_event)

        # Initial alert refresh
        QTimer.singleShot(500, self._refresh_alerts)

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
            else:
                self.fleet_service = None
                self.trip_service = None
                self.client_service = None

            if self.ops is None:
                from client.remote_ops_stub import RemoteOpsStub
                self.ops = RemoteOpsStub(api_client=self._api_client)

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
        frame.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        self.app_shell.view_container.setCurrentWidget(frame)

        self._page_anim = QPropertyAnimation(effect, b"opacity")
        self._page_anim.setDuration(120)
        self._page_anim.setStartValue(0.0)
        self._page_anim.setEndValue(1.0)
        self._page_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._page_anim.start()

    def _switch_module(self, key: str, data: dict[str, Any] | None = None):
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
        if key == "overview":
            crumb = t("nav.overview", default="Overview")
        else:
            # Humanise the key as a last-ditch fallback so the breadcrumb
            # never shows a raw i18n key (e.g. "nav.documents").
            crumb = t(f"nav.{key}", default=key.replace("_", " ").title())
        self.app_shell.set_breadcrumb(crumb)
        with contextlib.suppress(Exception):
            self.nav.highlight(key)

    _VIEW_FACTORIES = None

    def _create_module(self, key: str):
        """Factory for view modules — registry pattern."""
        parent = self.app_shell.view_container

        if MainWindow._VIEW_FACTORIES is None:
            ac = self._api_client
            MainWindow._VIEW_FACTORIES = {
                "calculator": lambda: QtCalculatorView(
                    parent, db=self.db, fleet_service=self.fleet_service,
                    trip_service=self.trip_service, client_service=self.client_service,
                    prefs=self.prefs, ops=self.ops, fuel_service=self._fuel_service,
                    api=self.api, api_client=ac,
                ),
                "overview": lambda: QtOverviewView(parent, db=self.db, ops=self.ops, api_client=ac),
                "route_planner": lambda: QtRoutePlannerView(parent, db=self.db, controller=self, api_client=ac),
                "analytics": lambda: QtAnalyticsView(parent, db=self.db, prefs=self.prefs, api_client=ac),
                "history": lambda: QtHistoryView(parent, db=self.db, controller=self, prefs=self.prefs, ops=self.ops, api_client=ac),
                "route_history": lambda: QtRouteHistoryView(parent, db=self.db, controller=self, api_client=ac),
                "dispatch_board": lambda: QtDispatchBoardView(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac),
                "tracking": lambda: QtFleetTrackingView(parent, db=self.db, prefs=self.prefs, ops=self.ops, on_navigate=self._switch_module, api_client=ac),
                "fleet": lambda: QtFleetTab(
                    parent, db=self.db, ops=self.ops,
                    fleet_service=self.fleet_service, api_client=ac,
                ),
                "driver_manager": lambda: QtDriverManager(parent, db=self.db, prefs=self.prefs, api_client=ac),
                "clients": lambda: QtClientWorkspace(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac),
                "documents": lambda: QtDocumentCenterView(
                    parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac,
                ),
                "maintenance": lambda: QtMaintenanceAnalyticsView(parent, db=self.db, api_client=ac),
                "maintenance_control": lambda: QtMaintenanceControlPanel(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac),
                "tachograph": lambda: QtTachoImportView(parent, db=self.db, api_client=ac),
                "invoices": lambda: QtGeneratorsView(
                    parent, db=self.db, prefs=self.prefs,
                    client_service=self.client_service,
                    fleet_service=self.fleet_service,
                    trip_service=self.trip_service,
                    api_client=ac,
                ),
                "settings": lambda: QtSettingsView(parent, db=self.db, prefs=self.prefs, ops=self.ops, api_client=ac),
            }

        factory = MainWindow._VIEW_FACTORIES.get(key)
        widget = factory() if factory else PlaceholderView(parent, key)
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

    def _on_settings_updated(self, ev):
        if self.ops is not None and hasattr(self.ops, '_configure_smtp_from_db'):
            with contextlib.suppress(Exception):
                self.ops._configure_smtp_from_db()

    def _on_alert_event(self, ev):
        """Refresh alert count and data when alerts are created or resolved."""
        QTimer.singleShot(0, self._refresh_alerts)

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
            if event.key() == self._key and event.modifiers() == self._modifier:
                self._callback()
                return True
        return False
