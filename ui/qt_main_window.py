"""PySide6 main window controller for Operion ERP.

Replaces ``ui/main_window.py`` for the Qt branch. Manages the application shell,
sidebar navigation, view switching via ``QStackedWidget``, and service lifecycle.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QObject
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
)

from config import Config
from ui.qt_app_shell import AppShell
from services.i18n import t
from services.trip_service import TripService
from services.client_service import ClientService
from services.fleet_service import FleetService
from services.fuel_price_service import FuelPriceService
from services.operations.event_bus import EventBus, SETTINGS_UPDATED, ALERT_CREATED, ALERT_RESOLVED
from ui.qt_views import (
    QtCalculatorView, QtOverviewView, QtRoutePlannerView,
    QtAnalyticsView, QtRouteHistoryView, QtHistoryView,
    QtDispatchBoardView, QtFleetTrackingView, QtFleetTab,
    QtDriverManager, QtClientWorkspace, QtDocumentCenterView,
    QtMaintenanceAnalyticsView, QtMaintenanceControlPanel,
    QtTachoImportView, QtGeneratorsView, QtSettingsView,
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
    ):
        super().__init__()
        self.db = db
        self.api = api
        self.ops = ops
        self.prefs = prefs

        self._event_bus = EventBus()
        self._module_cache: dict = {}
        self._active_module: Optional[str] = None

        self._init_services()
        self._build_ui()
        self._setup_shortcuts()
        self._init_fuel_status()

        self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)
        self._event_bus.subscribe(ALERT_CREATED, self._on_alert_event)
        self._event_bus.subscribe(ALERT_RESOLVED, self._on_alert_event)

        # Initial alert refresh
        QTimer.singleShot(500, self._refresh_alerts)

    def _init_services(self):
        from services.preferences import PreferencesManager

        self.prefs = self.prefs or PreferencesManager(self.db)
        self.prefs.load()

        self.fleet_service = FleetService(self.db)
        self.trip_service = TripService(self.db)
        self.client_service = ClientService(self.db)

        self.api = self.api

        if self.ops is None:
            from services.operations.operations_engine import OperationsEngine
            self.ops = OperationsEngine(self.db, prefs=self.prefs)
            self.ops.start()

        from services.fleet_tracking_service import fleet_tracking_service
        fleet_tracking_service.initialize(self.db)

        self._fuel_service = FuelPriceService()
        self._fuel_service.refresh_if_stale()

    def _build_ui(self):
        self.setWindowTitle(Config.APP_NAME)
        self.resize(1400, 900)

        self.app_shell = AppShell(
            self,
            self.db,
            on_nav_select=self._switch_module,
            prefs=self.prefs,
            ops=self.ops,
        )
        self.nav = self.app_shell.nav

        self._build_nav()
        self._switch_module("overview")

    def _build_nav(self):
        """Build the full navigation sidebar."""
        nav = self.nav

        nav.add_group(t("nav.group_overview"), "nav.group_overview")
        nav.add_item("overview", "\U0001f3e0", t("nav.overview"), i18n_key="nav.overview")
        nav.add_item("analytics", "\U0001f4c8", t("nav.analytics"), i18n_key="nav.analytics")

        nav.add_group(t("nav.group_operations"), "nav.group_operations")
        nav.add_item("route_planner", "\U0001f5fa", t("nav.routes"), i18n_key="nav.routes")
        nav.add_item("calculator", "\U0001f4b0", t("nav.calculator"), i18n_key="nav.calculator")
        nav.add_item("dispatch_board", "\U0001f69a", t("nav.dispatch_board"), i18n_key="nav.dispatch_board")
        nav.add_item("tracking", "\U0001f4cd", t("nav.live_tracking"), i18n_key="nav.live_tracking")

        nav.add_group(t("nav.group_fleet"), "nav.group_fleet")
        nav.add_item("fleet", "\U0001f69b", t("nav.fleet"), i18n_key="nav.fleet")
        nav.add_item("driver_manager", "\U0001f464", t("nav.driver_manager"), i18n_key="nav.driver_manager")
        nav.add_item("clients", "\U0001f465", t("nav.clients"), i18n_key="nav.clients")
        nav.add_item("documents", "\U0001F4C2", t("nav.documents"), i18n_key="nav.documents")
        nav.add_item("maintenance", "\U0001f527", t("nav.maintenance_analytics"),
                     i18n_key="nav.maintenance_analytics")
        nav.add_item("maintenance_control", "\U0001f529", t("nav.maintenance_control"),
                     i18n_key="nav.maintenance_control")
        nav.add_item("tachograph", "\U0001f4be", t("nav.tachograph"), i18n_key="nav.tachograph")

        nav.add_group(t("nav.group_finance"), "nav.group_finance")
        nav.add_item("invoices", "\U0001f9fe", t("nav.generators"), i18n_key="nav.generators")
        nav.add_item("history", "\U0001f4cb", t("nav.history"), i18n_key="nav.history")
        nav.add_item("route_history", "\U0001f5c2", t("nav.route_history"), i18n_key="nav.route_history")

        nav.add_settings_item("settings", "\u2699\ufe0f", t("nav.settings"))
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
        try:
            self.app_shell.set_fuel_status(text)
        except Exception:
            pass

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

    def _switch_module(self, key: str):
        old_key = self._active_module
        if old_key and old_key in self._module_cache:
            cache = self._module_cache[old_key]
            obj = cache.get("obj")
            if hasattr(obj, "shutdown"):
                try:
                    obj.shutdown()
                except Exception:
                    pass

        if key not in self._module_cache:
            self._module_cache[key] = self._create_module(key)

        cache = self._module_cache.get(key)
        if cache and cache.get("frame") is not None:
            frame = cache["frame"]
            self.app_shell.view_container.setCurrentWidget(frame)
            obj = cache.get("obj")
            if obj and hasattr(obj, "wakeup"):
                try:
                    obj.wakeup()
                except Exception:
                    pass

        self._active_module = key
        self.app_shell.set_breadcrumb(t(f"nav.{key}") if key != "overview" else t("nav.overview"))
        try:
            self.nav.highlight(key)
        except Exception:
            pass

    def _create_module(self, key: str):
        """Factory for view modules."""
        parent = self.app_shell.view_container
        if key == "calculator":
            widget = QtCalculatorView(
                parent,
                db=self.db,
                fleet_service=self.fleet_service,
                trip_service=self.trip_service,
                client_service=self.client_service,
                prefs=self.prefs,
                ops=self.ops,
                fuel_service=self._fuel_service,
                api=self.api,
            )
        elif key == "overview":
            widget = QtOverviewView(parent, db=self.db, ops=self.ops)
        elif key == "route_planner":
            widget = QtRoutePlannerView(parent, db=self.db, controller=self)
        elif key == "analytics":
            widget = QtAnalyticsView(parent, db=self.db, prefs=self.prefs)
        elif key == "history":
            widget = QtHistoryView(parent, db=self.db, controller=self, prefs=self.prefs, ops=self.ops)
        elif key == "route_history":
            widget = QtRouteHistoryView(parent, db=self.db, controller=self)
        elif key == "dispatch_board":
            widget = QtDispatchBoardView(parent, db=self.db, prefs=self.prefs, ops=self.ops)
        elif key == "tracking":
            widget = QtFleetTrackingView(parent, db=self.db, prefs=self.prefs, ops=self.ops, on_navigate=self._switch_module)
        elif key == "fleet":
            widget = QtFleetTab(parent, db=self.db, ops=self.ops)
        elif key == "driver_manager":
            widget = QtDriverManager(parent, db=self.db, prefs=self.prefs)
        elif key == "clients":
            widget = QtClientWorkspace(parent, db=self.db, prefs=self.prefs)
        elif key == "documents":
            widget = QtDocumentCenterView(parent, db=self.db)
        elif key == "maintenance":
            widget = QtMaintenanceAnalyticsView(parent, db=self.db)
        elif key == "maintenance_control":
            widget = QtMaintenanceControlPanel(parent, db=self.db, prefs=self.prefs, ops=self.ops)
        elif key == "tachograph":
            widget = QtTachoImportView(parent, db=self.db)
        elif key == "invoices":
            widget = QtGeneratorsView(parent, db=self.db, prefs=self.prefs)
        elif key == "settings":
            widget = QtSettingsView(parent, db=self.db, prefs=self.prefs, ops=self.ops)
        else:
            widget = PlaceholderView(parent, key)
        self.app_shell.view_container.addWidget(widget)
        return {"frame": widget, "obj": widget}

    def _open_calculator(self):
        self._switch_module("calculator")

    def _open_history(self):
        self._switch_module("history")

    def _on_settings_updated(self, ev):
        pass

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
        try:
            self.app_shell.destroy()
        except Exception:
            pass
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
        event.accept()


class PlaceholderView(QWidget):
    """Empty placeholder view used until a module is fully migrated."""

    def __init__(self, parent: Optional[QWidget], key: str):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(f"{key}\n(Module not yet migrated)")
        label.setProperty("fontRole", "muted")
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
