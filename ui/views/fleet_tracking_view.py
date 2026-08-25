"""PySide6 live fleet tracking view — map + vehicle list with polling.

Replaces ``ui/views/fleet_tracking_view.py``. Uses ``MapWidget`` for the map
and ``QTimer`` for polling. Fully embedded as a QWidget.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from datetime import datetime
from typing import Callable

import qtawesome as qta
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.components import UniversalCard

from services.fleet_tracking_service import (
    VehiclePosition,
    fleet_tracking_service,
)
from services.i18n import t
from ui.components import Btn, EmptyState, UniversalCard
from ui.performance_timer import PerfTimer
from ui.design_tokens import (
    COLOR_BG_ELEVATED,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    SP,
)
from ui.map.map_widget import MapWidget

logger = logging.getLogger(__name__)


class QtFleetTrackingView(QWidget):
    """Live fleet tracking map with a sidebar vehicle list.

    Call ``wakeup()`` when the view becomes active and ``shutdown()`` when
    hidden to manage the polling timer.
    """

    POLL_INTERVAL_MS = 30_000

    # Emitted from background thread; main thread slot applies the update
    _positionsFetched = Signal(list)
    # Emitted from the force-refresh worker thread to re-enable the
    # refresh button on the GUI thread.  (Previously we used
    # ``QTimer.singleShot(0, ...)`` from a worker thread — Qt creates
    # the timer in the calling thread and its event loop never runs,
    # so the button never came back.)
    _refreshFinished = Signal()

    # Status → leaflet marker color name for MapWidget
    _STATUS_MARKER_COLORS = {
        "moving":  "green",
        "stopped": "grey",
        "idle":    "orange",
        "offline": "red",
    }

    # Status → indicator dot colour (hex)
    _STATUS_DOT_COLORS = {
        "moving":  COLOR_SUCCESS_DEFAULT,
        "stopped": COLOR_TEXT_TERTIARY,
        "idle":    COLOR_WARNING_DEFAULT,
        "offline": COLOR_ERROR_DEFAULT,
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
        ops=None,
        fleet_service=None,
        api_client=None,
        on_navigate: Callable[[str, dict | None], None] | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._fleet_service = fleet_service
        self._api_client = api_client
        self._on_navigate = on_navigate

        # ── State ──────────────────────────────────────────────────────
        self._map: MapWidget | None = None
        self._vehicle_list_scroll: QScrollArea | None = None
        self._vehicle_list_content: QWidget | None = None
        self._vehicle_list_layout: QVBoxLayout | None = None
        self._detail_panel: QFrame | None = None
        self._detail_layout: QVBoxLayout | None = None
        self._refresh_btn: QPushButton | None = None
        self._updated_lbl: QLabel | None = None
        self._selected_position: VehiclePosition | None = None
        self._selected_truck_id: int | None = None
        self._fetching = False
        self._force_refreshing = False
        self._lock = threading.Lock()
        self._vehicle_rows: dict[str, UniversalCard] = {}  # Track widget rows by vehicle name

        # ── Signal: thread-safe UI updates ─────────────────────────────
        self._positionsFetched.connect(self._apply_update)
        self._refreshFinished.connect(self._enable_refresh_btn)

        # ── Polling timer ──────────────────────────────────────────────
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_and_update)

        # ── Build ──────────────────────────────────────────────────────
        self._build_ui()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Start polling if the tracking service is configured."""
        if fleet_tracking_service.is_configured():
            self._start_polling()

    def shutdown(self) -> None:
        """Stop polling and clean up resources."""
        self._stop_polling()
        with self._lock:
            self._fetching = False
        if hasattr(self, "_map") and self._map:
            with contextlib.suppress(Exception):
                self._map._destroy()
            self._map = None

    # ── Build ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setAccessibleName("Fleet tracking")
        self.setAccessibleDescription("Live fleet tracking map with vehicle list")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Remote mode (db=None + api_client): pull the tracking config from
        # the server so the panel reflects the server-side credentials
        # instead of always showing the not-configured state.
        self._maybe_init_remote_config()

        if not fleet_tracking_service.is_configured():
            self._build_not_configured_state(layout)
            return

        # ── Splitter: map + vehicle panel ──────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setChildrenCollapsible(False)

        map_container = QFrame()
        map_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_map(map_container)
        splitter.addWidget(map_container)

        panel = QFrame()
        panel.setStyleSheet(
            f"background-color: {COLOR_BG_ELEVATED};"
            f"border-left: 1px solid {COLOR_BORDER_SUBTLE};"
        )
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        panel.setMinimumWidth(240)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self._build_vehicle_panel(panel)
        splitter.addWidget(panel)

        # Default ratio ~72:28
        splitter.setSizes([720, 280])

        layout.addWidget(splitter, 1)

    def _build_not_configured_state(self, layout: QHBoxLayout) -> None:
        """Centred message when no tracking platform is configured."""
        container = QFrame()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QVBoxLayout(container)
        cl.setAlignment(Qt.AlignCenter)
        cl.setSpacing(SP["3"])

        # Globe icon
        icon_lbl = QLabel("\U0001f5fa")
        icon_lbl.setStyleSheet(f"font-size: 64px; color: {COLOR_TEXT_TERTIARY};")
        icon_lbl.setAlignment(Qt.AlignCenter)
        cl.addWidget(icon_lbl)

        # Title
        title_lbl = QLabel(t("tracking.not_configured_title"))
        title_lbl.setProperty("fontRole", "h2")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        cl.addWidget(title_lbl)

        # Hint
        hint_lbl = QLabel(t("tracking.not_configured_hint"))
        hint_lbl.setProperty("fontRole", "body")
        hint_lbl.setAlignment(Qt.AlignCenter)
        hint_lbl.setMaximumWidth(360)
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        cl.addWidget(hint_lbl)

        # Settings button
        if self.db is None and self._api_client is not None:
            settings_btn = Btn(
                container,
                t("tracking.configure", default="Configure Tracking"),
                variant="primary",
                command=lambda: self._open_remote_settings(),
            )
        else:
            settings_btn = Btn(
                container,
                t("tracking.go_to_settings"),
                variant="primary",
                command=lambda: self._navigate_settings(),
            )
        btn_wrapper = QFrame()
        btn_wrapper_layout = QHBoxLayout(btn_wrapper)
        btn_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        btn_wrapper_layout.setAlignment(Qt.AlignCenter)
        btn_wrapper_layout.addWidget(settings_btn)
        cl.addWidget(btn_wrapper)

        layout.addWidget(container)

    def _navigate_settings(self) -> None:
        logger.debug("Navigate to settings from fleet tracking not-configured state")
        if self._on_navigate:
            self._on_navigate("settings", {"scroll_to": "tracking"})

    # ── Remote-mode tracking config ──────────────────────────────────

    def _maybe_init_remote_config(self) -> None:
        """Load the server-side tracking config into the service (remote mode).

        Local mode (``db`` present) is untouched — the service is initialized
        from the settings table at app startup.  In remote mode the config is
        pulled from ``GET /settings/tracking``; when no platform is configured
        the service stays in the graceful "not configured" state.
        """
        if self.db is not None or self._api_client is None:
            return
        try:
            fleet_tracking_service.initialize(db=None, api_client=self._api_client)
        except Exception:
            logger.exception("Failed to initialize remote tracking config")

    def get_remote_tracking_config(self) -> dict:
        """Return the server-side tracking config dict (remote mode).

        Shape: ``{"platform", "tokens", "interval_seconds", "enabled"}``.
        Returns ``{}`` when no API client is available or on error.
        """
        if self._api_client is None:
            return {}
        try:
            from client.remote_tracking_config import RemoteTrackingConfig
            return RemoteTrackingConfig(self._api_client).get_config()
        except Exception:
            logger.exception("Failed to load remote tracking config")
            return {}

    def save_remote_tracking_config(self, config: dict) -> bool:
        """Persist a tracking config via the API and re-initialize the service.

        Returns ``True`` when the server accepted the config.
        """
        if self._api_client is None:
            return False
        try:
            from client.remote_tracking_config import RemoteTrackingConfig
            RemoteTrackingConfig(self._api_client).save_config(config)
        except Exception:
            logger.exception("Failed to save remote tracking config")
            return False
        try:
            fleet_tracking_service.initialize(db=None, api_client=self._api_client)
        except Exception:
            logger.exception("Failed to re-initialize tracking service after save")
        return True

    def _open_remote_settings(self) -> None:
        """Remote mode: edit tracking credentials through the API.

        A minimal functional dialog (platform + credential fields) — no
        styling/design work.  Saving persists via ``PUT /settings/tracking``
        and rebuilds the panel.
        """
        from PySide6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLineEdit,
        )

        config = self.get_remote_tracking_config()
        tokens = config.get("tokens") or {}
        if not isinstance(tokens, dict):
            tokens = {}

        dlg = QDialog(self)
        dlg.setWindowTitle(
            t("tracking.remote_settings_title", default="Fleet Tracking Settings")
        )
        form = QFormLayout(dlg)

        platform_edit = QComboBox(dlg)
        platform_edit.setEditable(True)
        platforms = ["", "wialon", "frotcom", "navixy", "traccar", "generic rest"]
        for p in platforms:
            platform_edit.addItem(p)
        current = str(config.get("platform") or "").lower()
        platform_edit.setCurrentIndex(
            platforms.index(current) if current in platforms else 0
        )
        form.addRow(t("tracking.platform", default="Platform"), platform_edit)

        entries: dict[str, QLineEdit] = {}
        for key in ("token", "host", "username", "password", "account"):
            edit = QLineEdit(str(tokens.get(key) or ""), dlg)
            if key == "password":
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            entries[key] = edit
            form.addRow(t(f"tracking.{key}", default=key.title()), edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=dlg,
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec_() != QDialog.Accepted:
            return

        config["platform"] = platform_edit.currentText().strip()
        tokens["token"] = entries["token"].text().strip()
        tokens["host"] = entries["host"].text().strip()
        tokens["username"] = entries["username"].text().strip()
        tokens["password"] = entries["password"].text().strip()
        tokens["account"] = entries["account"].text().strip()
        config["tokens"] = tokens
        if self.save_remote_tracking_config(config):
            self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the panel after the tracking config changes."""
        layout = self.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._build_ui()

    def _build_map(self, parent: QFrame) -> None:
        map_layout = QVBoxLayout(parent)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        self._map = MapWidget(parent)
        map_layout.addWidget(self._map, 1)

    def _build_vehicle_panel(self, parent: QFrame) -> None:
        layout: QVBoxLayout = parent.layout()  # type: ignore[assignment]

        # ── Header row ─────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(52)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["5"], 0, SP["3"], 0)
        header_layout.setSpacing(SP["2"])

        title_lbl = QLabel(t("tracking.panel_title"))
        title_lbl.setProperty("fontRole", "h3")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch(1)

        # Last-updated label
        self._updated_lbl = QLabel("")
        self._updated_lbl.setProperty("fontRole", "label")
        self._updated_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        header_layout.addWidget(self._updated_lbl)

        # Refresh button
        self._refresh_btn = Btn(
            header,
            "\u21bb",
            variant="ghost",
            command=self._force_refresh,
        )
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # ── Divider ────────────────────────────────────────────────────
        layout.addWidget(self._make_divider())

        # ── Vehicle list (scrollable) ──────────────────────────────────
        self._vehicle_list_scroll = QScrollArea()
        self._vehicle_list_scroll.setWidgetResizable(True)
        self._vehicle_list_scroll.setFrameShape(QFrame.NoFrame)
        self._vehicle_list_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self._vehicle_list_scroll.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        self._vehicle_list_content = QWidget()
        self._vehicle_list_content.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._vehicle_list_content.installEventFilter(self)
        self._vehicle_list_layout = QVBoxLayout(self._vehicle_list_content)
        self._vehicle_list_layout.setContentsMargins(0, 0, 0, 0)
        self._vehicle_list_layout.setSpacing(1)
        self._vehicle_list_layout.setAlignment(Qt.AlignTop)

        self._vehicle_list_scroll.setWidget(self._vehicle_list_content)
        layout.addWidget(self._vehicle_list_scroll, 1)

        # ── Divider ────────────────────────────────────────────────────
        layout.addWidget(self._make_divider())

        # ── Detail panel (bottom, fixed height) ────────────────────────
        self._detail_panel = QFrame()
        self._detail_panel.setFixedHeight(200)
        self._detail_layout = QVBoxLayout(self._detail_panel)
        self._detail_layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])
        self._detail_layout.setSpacing(SP["1"])
        self._detail_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._detail_panel)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {COLOR_BORDER_SUBTLE};")
        line.setFixedHeight(1)
        return line

    # ── Vehicle rows ──────────────────────────────────────────────────

    def _build_vehicle_row_widget(
        self,
        position: VehiclePosition,
        matched_truck_id: int | None,
    ) -> UniversalCard:
        dot_color = self._STATUS_DOT_COLORS.get(
            position.status, COLOR_TEXT_TERTIARY
        )
        detail_str = self._vehicle_detail_text(position)

        card = UniversalCard(
            title=position.name,
            primary=position.status.title(),
            secondary=detail_str,
            icon_name="fa5s.truck",
            icon_color=dot_color,
            action_icon="fa5s.chevron-right",
            action_tooltip=t("tracking.details"),
            on_action=lambda p=position, tid=matched_truck_id: (
                self._select_vehicle(p, tid)
            ),
            on_click=lambda p=position, tid=matched_truck_id: (
                self._select_vehicle(p, tid)
            ),
        )
        # Store data for context menu lookup
        card._position = position
        card._truck_id = matched_truck_id
        # Lower case — more compact in the sidebar
        card.setMinimumHeight(72)
        return card

    @staticmethod
    def _vehicle_detail_text(position: VehiclePosition) -> str:
        if position.speed_kmh > 3:
            return f"{position.speed_kmh:.0f} km/h"
        if position.address:
            return position.address[:30] + "\u2026" if len(position.address) > 30 else position.address
        return t("tracking.stopped")

    def _select_vehicle(
        self,
        position: VehiclePosition,
        truck_id: int | None,
    ) -> None:
        """Pan map to vehicle and show detail panel."""
        self._selected_position = position
        self._selected_truck_id = truck_id

        if self._map and position.latitude and position.longitude:
            self._map.set_view(position.latitude, position.longitude, zoom=14)

        self._show_detail_panel(position, truck_id)

    def _show_detail_panel(
        self,
        position: VehiclePosition,
        truck_id: int | None,
    ) -> None:
        """Rebuild the detail panel for the selected vehicle."""
        # Clear existing detail content
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Name
        name_lbl = QLabel(position.name)
        name_lbl.setProperty("fontRole", "h3")
        name_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        self._detail_layout.addWidget(name_lbl)

        # Detail rows
        details: list[tuple] = [
            (t("tracking.d_status"), position.status.title()),
            (t("tracking.d_speed"), f"{position.speed_kmh:.0f} km/h"),
            (t("tracking.d_updated"),
             position.timestamp.strftime("%H:%M:%S")),
        ]
        if position.odometer_km:
            details.append(
                (t("tracking.d_odometer"),
                 f"{position.odometer_km:,.0f} km"),
            )
        if position.address:
            addr = position.address[:40] + "\u2026" if len(
                position.address) > 40 else position.address
            details.append((t("tracking.d_address"), addr))

        for label_text, value_text in details:
            row_f = QFrame()
            row_f.setStyleSheet("background-color: transparent;")
            row_f_layout = QHBoxLayout(row_f)
            row_f_layout.setContentsMargins(0, 0, 0, 0)
            row_f_layout.setSpacing(SP["2"])

            label_w = QLabel(label_text)
            label_w.setProperty("fontRole", "label")
            label_w.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
            label_w.setFixedWidth(90)
            row_f_layout.addWidget(label_w)

            value_w = QLabel(value_text)
            value_w.setProperty("fontRole", "small")
            value_w.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            row_f_layout.addWidget(value_w)

            row_f_layout.addStretch(1)
            self._detail_layout.addWidget(row_f)

        # Fleet detail button (when a db match exists)
        if truck_id:
            def on_fleet_detail():
                if self._on_navigate:
                    self._on_navigate("fleet", None)

            fleet_btn = Btn(
                self._detail_panel,
                t("tracking.btn_fleet_detail"),
                variant="ghost",
                command=on_fleet_detail,
            )
            self._detail_layout.addWidget(fleet_btn)

            # ── Quick action buttons ─────────────────────────────────
            action_row = QFrame()
            action_row.setStyleSheet("background-color: transparent;")
            action_layout = QHBoxLayout(action_row)
            action_layout.setContentsMargins(0, SP["2"], 0, 0)
            action_layout.setSpacing(SP["2"])

            maint_btn = Btn(
                action_row,
                t("tracking.maintenance", "Maintenance"),
                variant="secondary",
                command=lambda tid=truck_id: self._navigate_vehicle_maintenance(tid),
            )
            action_layout.addWidget(maint_btn)

            docs_btn = Btn(
                action_row,
                t("tracking.documents", "Documents"),
                variant="secondary",
                command=lambda tid=truck_id: self._open_vehicle_documents(tid),
            )
            action_layout.addWidget(docs_btn)

            call_btn = Btn(
                action_row,
                t("tracking.call_driver", "Call Driver"),
                variant="secondary",
                command=lambda: self._on_call_driver(position, truck_id),
            )
            action_layout.addWidget(call_btn)

            action_layout.addStretch(1)
            self._detail_layout.addWidget(action_row)

    # ── Context menu (right-click on vehicle rows) ────────────────────

    def eventFilter(self, obj, event) -> bool:
        """Catch right-clicks on the vehicle list to show a context menu."""
        if obj is self._vehicle_list_content and event.type() == QEvent.ContextMenu:
            self._show_vehicle_context_menu(event)
            return True
        return super().eventFilter(obj, event)

    def _show_vehicle_context_menu(self, event) -> None:
        """Show a context menu for the vehicle card under the cursor."""
        # Find the UniversalCard at the event position
        pos = self._vehicle_list_content.mapFromGlobal(event.globalPos())
        child = self._vehicle_list_content.childAt(pos)
        while child is not None and not isinstance(child, UniversalCard):
            child = child.parent()

        if child is None:
            return

        # Retrieve stored position data from the card
        position = getattr(child, "_position", None)
        truck_id = getattr(child, "_truck_id", None)
        if position is None:
            return

        menu = QMenu(self)

        detail_action = QAction(qta.icon("fa5s.eye"), t("tracking.view_details", "View Details"), self)
        detail_action.triggered.connect(lambda: self._select_vehicle(position, truck_id))
        menu.addAction(detail_action)

        maint_action = QAction(qta.icon("fa5s.wrench"), t("tracking.maintenance", "Maintenance"), self)
        maint_action.triggered.connect(lambda: self._navigate_vehicle_maintenance(truck_id))
        menu.addAction(maint_action)

        docs_action = QAction(qta.icon("fa5s.folder-open"), t("tracking.documents", "Documents"), self)
        docs_action.triggered.connect(lambda: self._open_vehicle_documents(truck_id))
        menu.addAction(docs_action)

        map_action = QAction(qta.icon("fa5s.map-marker-alt"), t("tracking.show_on_map", "Show on Map"), self)
        map_action.triggered.connect(lambda: self._select_vehicle(position, truck_id))
        menu.addAction(map_action)

        menu.exec(event.globalPos())

    def _navigate_vehicle_maintenance(self, truck_id: int | None) -> None:
        """Navigate to the maintenance view for this vehicle."""
        if self._on_navigate:
            nav_data = {"truck_id": truck_id} if truck_id else None
            self._on_navigate("maintenance", nav_data)

    def _open_vehicle_documents(self, truck_id: int | None) -> None:
        """Open documents for this vehicle."""
        if truck_id is None:
            QMessageBox.information(
                self,
                t("tracking.documents", "Documents"),
                t("tracking.no_truck_match", "No matching vehicle found in the fleet database."),
            )
            return
        try:
            from ui.views.document_center_view import open_entity_documents
            open_entity_documents(
                self,
                self.db,
                "truck",
                truck_id,
                t("tracking.truck_documents_title", default="Vehicle #{} Documents").format(truck_id),
            )
        except Exception:
            logger.exception("Failed to open vehicle documents")

    def _on_call_driver(self, position: VehiclePosition, truck_id: int | None) -> None:
        """Show the driver's phone number in a toast if available."""
        phone = None
        if position.driver_id:
            try:
                if self.db is not None:
                    from repositories.driver_repository import DriverRepository
                    repo = DriverRepository(self.db)
                    driver = repo.get_by_id(position.driver_id)
                    if driver:
                        phone = driver.get("phone", "") or driver.get("phone_number", "")
                else:
                    # Remote mode — no local driver lookup; degrade gracefully.
                    logger.debug(
                        "Driver phone lookup unavailable in remote mode for id %s",
                        position.driver_id,
                    )
            except Exception:
                logger.warning("Could not look up driver phone for id %s", position.driver_id)
        elif truck_id:
            try:
                if self.db is not None:
                    from repositories.driver_repository import DriverRepository
                    from repositories.fleet_repository import FleetRepository
                    fleet_repo = FleetRepository(self.db)
                    truck = fleet_repo.get_by_id(truck_id)
                    if truck and truck.get("driver_id"):
                        repo = DriverRepository(self.db)
                        driver = repo.get_by_id(truck["driver_id"])
                        if driver:
                            phone = driver.get("phone", "") or driver.get("phone_number", "")
                elif self._fleet_service is not None:
                    # Remote mode: resolve the truck via the injected fleet
                    # service; there is no remote driver-phone endpoint, so
                    # the phone stays None and the caller shows the info toast.
                    truck = self._fleet_service.get_truck(truck_id)
                    if truck and truck.get("driver_id"):
                        logger.debug(
                            "Driver phone lookup unavailable in remote mode "
                            "(truck %s)", truck_id,
                        )
            except Exception:
                logger.warning("Could not look up driver phone via truck %s", truck_id)

        if phone:
            from ui.widgets.toast import Toast
            Toast.show_info(
                self,
                t("tracking.driver_phone", default="Driver phone: {}").format(phone),
                anchor=self,
            )
        else:
            from ui.widgets.toast import Toast
            Toast.show_info(
                self,
                t("tracking.no_driver_phone", default="No driver phone number available."),
                anchor=self,
            )

    # ── Map markers ───────────────────────────────────────────────────

    def _update_map_markers(self, positions: list[VehiclePosition]) -> None:
        if not self._map:
            return

        self._map.clear_overlays()

        for pos in positions:
            if not pos.latitude or not pos.longitude:
                continue

            color = self._STATUS_MARKER_COLORS.get(pos.status, "grey")

            marker_text = f"\U0001f69b {pos.name}"
            if pos.speed_kmh > 3:
                marker_text += f" {pos.speed_kmh:.0f}km/h"

            self._map.add_marker(
                pos.latitude, pos.longitude,
                label=marker_text,
                color=color,
            )

    # ── Vehicle list refresh ──────────────────────────────────────────

    def _update_vehicle_row(self, row: UniversalCard, position: VehiclePosition,
                            matched_truck_id: int | None) -> None:
        """Update an existing vehicle row's content in-place."""
        dot_color = self._STATUS_DOT_COLORS.get(
            position.status, COLOR_TEXT_TERTIARY
        )
        row._position = position
        row._truck_id = matched_truck_id
        row.set_icon_color(dot_color)
        row.set_title(position.name)
        row.set_primary(position.status.title())
        row.set_secondary(self._vehicle_detail_text(position))
        row._on_click = lambda p=position, tid=matched_truck_id: (
            self._select_vehicle(p, tid)
        )

    def _refresh_vehicle_list(self, positions: list[VehiclePosition]) -> None:
        """Update vehicle list — add new rows, remove gone, update existing."""
        with PerfTimer("fleet_tracking.refresh_vehicle_list"):
            new_names = {p.name for p in positions}

            # Remove rows for vehicles that disappeared
            to_remove = []
            for name in list(self._vehicle_rows.keys()):
                if name not in new_names:
                    to_remove.append(name)
            for name in to_remove:
                widget = self._vehicle_rows.pop(name)
                self._vehicle_list_layout.removeWidget(widget)
                widget.deleteLater()

            if not positions:
                # Show "no vehicles" empty state when list is empty
                empty = EmptyState(
                    None,
                    icon_name="fa5s.truck-moving",
                    title=t("tracking.no_vehicles_title", default="No vehicles in your fleet"),
                    subtitle=t("tracking.no_vehicles_desc", default="Add your first vehicle to start tracking."),
                    cta_button=Btn(
                        None,
                        text=t("tracking.add_vehicle", default="Add Your First Vehicle"),
                        variant="primary",
                    ),
                )
                self._vehicle_list_layout.addWidget(empty)
                return

            # Update existing, add new (sorted alphabetically)
            for pos in sorted(positions, key=lambda p: p.name.lower()):
                truck_id = fleet_tracking_service.match_to_truck(pos)
                if pos.name in self._vehicle_rows:
                    # Update existing row in-place
                    self._update_vehicle_row(self._vehicle_rows[pos.name], pos, truck_id)
                else:
                    # Add new vehicle
                    row = self._build_vehicle_row_widget(pos, truck_id)
                    self._vehicle_rows[pos.name] = row
                    self._vehicle_list_layout.addWidget(row)

            self._updated_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    # ── Polling ───────────────────────────────────────────────────────

    def _poll_and_update(self) -> None:
        """Start a background thread to fetch positions."""
        with self._lock:
            if self._fetching:
                return
        thread = threading.Thread(target=self._fetch_positions, daemon=True)
        thread.start()

    def _fetch_positions(self) -> None:
        """Fetch positions in background — emits signal to update UI."""
        with self._lock:
            if self._fetching:
                return
            self._fetching = True
        try:
            # Do NOT access QWidget (self._map) from background thread;
            # just fetch data and emit the signal so the main-thread slot
            # handles map updates.
            positions = fleet_tracking_service.get_positions(
                force_refresh=True,
            )
            self._positionsFetched.emit(positions)
        except Exception as e:
            logger.error("Tracking poll error: %s", e)
        finally:
            with self._lock:
                self._fetching = False

    def _apply_update(self, positions: list[VehiclePosition]) -> None:
        """Main-thread slot: update map markers and vehicle list."""
        with PerfTimer("fleet_tracking.apply_update"):
            self._update_map_markers(positions)
            self._refresh_vehicle_list(positions)

    def _start_polling(self) -> None:
        # Initial load immediately
        self._poll_and_update()
        # Start timer for subsequent polls
        self._poll_timer.start(self.POLL_INTERVAL_MS)

    def _stop_polling(self) -> None:
        self._poll_timer.stop()

    # ── Refresh button ────────────────────────────────────────────────

    def _force_refresh(self) -> None:
        with self._lock:
            if self._force_refreshing:
                return
            self._force_refreshing = True
        if self._refresh_btn:
            self._refresh_btn.setEnabled(False)

        def do():
            try:
                positions = fleet_tracking_service.get_positions(
                    force_refresh=True,
                )
                # Emit signals from background thread is safe (queued
                # connection marshals them to the GUI thread).
                self._refreshFinished.emit()
                self._positionsFetched.emit(positions)
            except Exception as e:
                logger.error("Force refresh failed: %s", e)
                self._refreshFinished.emit()

        thread = threading.Thread(target=do, daemon=True)
        thread.start()

    def _enable_refresh_btn(self) -> None:
        with self._lock:
            self._force_refreshing = False
        if self._refresh_btn:
            self._refresh_btn.setEnabled(True)

    # ── Cleanup ───────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Ensure cleanup on close."""
        self.shutdown()
        super().closeEvent(event)
