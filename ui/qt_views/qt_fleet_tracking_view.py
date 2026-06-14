"""PySide6 live fleet tracking view — map + vehicle list with polling.

Replaces ``ui/views/fleet_tracking_view.py``. Uses ``MapWidget`` for the map
and ``QTimer`` for polling. Fully embedded as a QWidget.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
)

from services.fleet_tracking_service import (
    VehiclePosition,
    fleet_tracking_service,
)
from services.i18n import t
from ui.theme import COLORS, S
from ui.qt_map.qt_map_widget import MapWidget
from ui.qt_widgets import ActionButton

logger = logging.getLogger(__name__)


class QtFleetTrackingView(QWidget):
    """Live fleet tracking map with a sidebar vehicle list.

    Call ``wakeup()`` when the view becomes active and ``shutdown()`` when
    hidden to manage the polling timer.
    """

    POLL_INTERVAL_MS = 30_000

    # Emitted from background thread; main thread slot applies the update
    _positionsFetched = Signal(list)

    # Status → leaflet marker color name for MapWidget
    _STATUS_MARKER_COLORS = {
        "moving":  "green",
        "stopped": "grey",
        "idle":    "orange",
        "offline": "red",
    }

    # Status → indicator dot colour (hex)
    _STATUS_DOT_COLORS = {
        "moving":  COLORS["success"],
        "stopped": COLORS["text_muted"],
        "idle":    COLORS["warning"],
        "offline": COLORS["danger"],
    }

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
        ops=None,
        on_navigate: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._on_navigate = on_navigate

        # ── State ──────────────────────────────────────────────────────
        self._map: Optional[MapWidget] = None
        self._vehicle_list_scroll: Optional[QScrollArea] = None
        self._vehicle_list_content: Optional[QWidget] = None
        self._vehicle_list_layout: Optional[QVBoxLayout] = None
        self._detail_panel: Optional[QFrame] = None
        self._detail_layout: Optional[QVBoxLayout] = None
        self._refresh_btn: Optional[ActionButton] = None
        self._updated_lbl: Optional[QLabel] = None
        self._selected_position: Optional[VehiclePosition] = None
        self._selected_truck_id: Optional[int] = None

        # ── Signal: thread-safe UI updates ─────────────────────────────
        self._positionsFetched.connect(self._apply_update)

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

    # ── Build ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not fleet_tracking_service.is_configured():
            self._build_not_configured_state(layout)
            return

        # ── Map area (72 %) ────────────────────────────────────────────
        map_container = QFrame()
        map_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_map(map_container)
        layout.addWidget(map_container, 72)

        # ── Vehicle panel (28 %) ───────────────────────────────────────
        panel = QFrame()
        panel.setStyleSheet(
            f"background-color: {COLORS['bg_surface']};"
            f"border-left: 1px solid {COLORS['border']};"
        )
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self._build_vehicle_panel(panel)

        layout.addWidget(panel, 28)

    def _build_not_configured_state(self, layout: QHBoxLayout) -> None:
        """Centred message when no tracking platform is configured."""
        container = QFrame()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QVBoxLayout(container)
        cl.setAlignment(Qt.AlignCenter)
        cl.setSpacing(S["3"])

        # Globe icon
        icon_lbl = QLabel("\U0001f5fa")
        icon_lbl.setStyleSheet(f"font-size: 64px; color: {COLORS['text_muted']};")
        icon_lbl.setAlignment(Qt.AlignCenter)
        cl.addWidget(icon_lbl)

        # Title
        title_lbl = QLabel(t("tracking.not_configured_title"))
        title_lbl.setProperty("fontRole", "h2")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
        cl.addWidget(title_lbl)

        # Hint
        hint_lbl = QLabel(t("tracking.not_configured_hint"))
        hint_lbl.setProperty("fontRole", "body")
        hint_lbl.setAlignment(Qt.AlignCenter)
        hint_lbl.setMaximumWidth(360)
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        cl.addWidget(hint_lbl)

        # Settings button
        settings_btn = ActionButton(
            container,
            t("tracking.go_to_settings"),
            command=lambda: self._navigate_settings(),
            variant="primary",
        )
        btn_wrapper = QFrame()
        btn_wrapper_layout = QHBoxLayout(btn_wrapper)
        btn_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        btn_wrapper_layout.setAlignment(Qt.AlignCenter)
        btn_wrapper_layout.addWidget(settings_btn)
        cl.addWidget(btn_wrapper)

        layout.addWidget(container)

    def _navigate_settings(self) -> None:
        if self._on_navigate:
            self._on_navigate("settings")

    def _build_map(self, parent: QFrame) -> None:
        map_layout = QVBoxLayout(parent)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        self._map = MapWidget(parent)
        map_layout.addWidget(self._map)

    def _build_vehicle_panel(self, parent: QFrame) -> None:
        layout: QVBoxLayout = parent.layout()  # type: ignore[assignment]

        # ── Header row ─────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(52)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(S["5"], 0, S["3"], 0)
        header_layout.setSpacing(S["2"])

        title_lbl = QLabel(t("tracking.panel_title"))
        title_lbl.setProperty("fontRole", "h3")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch(1)

        # Last-updated label
        self._updated_lbl = QLabel("")
        self._updated_lbl.setProperty("fontRole", "label")
        self._updated_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        header_layout.addWidget(self._updated_lbl)

        # Refresh button
        self._refresh_btn = ActionButton(
            header,
            "\u21bb",
            command=self._force_refresh,
            variant="ghost",
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
        self._detail_layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        self._detail_layout.setSpacing(S["1"])
        self._detail_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._detail_panel)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {COLORS['border']};")
        line.setFixedHeight(1)
        return line

    # ── Vehicle rows ──────────────────────────────────────────────────

    def _build_vehicle_row(
        self,
        position: VehiclePosition,
        matched_truck_id: Optional[int],
    ) -> None:
        row = QFrame()
        row.setFixedHeight(52)
        row.setCursor(Qt.PointingHandCursor)
        row.setProperty("class", "vehicle-row")
        row.setStyleSheet(
            "QFrame {"
            f"  background-color: transparent;"
            f"  border-radius: {S['1']}px;"
            "}"
            "QFrame:hover {"
            f"  background-color: {COLORS['bg_elevated']};"
            "}"
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["3"], 0, S["3"], 0)
        row_layout.setSpacing(S["2"])

        # ── Status indicator dot ───────────────────────────────────────
        dot_color = self._STATUS_DOT_COLORS.get(
            position.status, COLORS["text_muted"]
        )
        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background-color: {dot_color}; border-radius: 5px;"
        )
        row_layout.addWidget(dot)

        # ── Vehicle info ───────────────────────────────────────────────
        info = QFrame()
        info.setStyleSheet("background-color: transparent;")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)

        name_lbl = QLabel(position.name)
        name_lbl.setProperty("fontRole", "body_bold")
        info_layout.addWidget(name_lbl)

        detail_str = self._vehicle_detail_text(position)
        detail_lbl = QLabel(detail_str)
        detail_lbl.setProperty("fontRole", "small")
        detail_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; "
                                 "background-color: transparent;")
        info_layout.addWidget(detail_lbl)

        row_layout.addWidget(info, 1)

        # ── Click handler ──────────────────────────────────────────────
        def on_click(e, p=position, tid=matched_truck_id):
            self._select_vehicle(p, tid)

        row.mousePressEvent = on_click

        self._vehicle_list_layout.addWidget(row)

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
        truck_id: Optional[int],
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
        truck_id: Optional[int],
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
        name_lbl.setStyleSheet(f"color: {COLORS['text_primary']};")
        self._detail_layout.addWidget(name_lbl)

        # Detail rows
        details: List[tuple] = [
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
            row_f_layout.setSpacing(S["2"])

            label_w = QLabel(label_text)
            label_w.setProperty("fontRole", "label")
            label_w.setStyleSheet(f"color: {COLORS['text_muted']};")
            label_w.setFixedWidth(90)
            row_f_layout.addWidget(label_w)

            value_w = QLabel(value_text)
            value_w.setProperty("fontRole", "small")
            value_w.setStyleSheet(f"color: {COLORS['text_primary']};")
            row_f_layout.addWidget(value_w)

            row_f_layout.addStretch(1)
            self._detail_layout.addWidget(row_f)

        # Fleet detail button (when a db match exists)
        if truck_id:
            def on_fleet_detail():
                if self._on_navigate:
                    self._on_navigate("fleet")

            fleet_btn = ActionButton(
                self._detail_panel,
                t("tracking.btn_fleet_detail"),
                command=on_fleet_detail,
                variant="ghost",
            )
            self._detail_layout.addWidget(fleet_btn)

    # ── Map markers ───────────────────────────────────────────────────

    def _update_map_markers(self, positions: List[VehiclePosition]) -> None:
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

    def _refresh_vehicle_list(self, positions: List[VehiclePosition]) -> None:
        """Clear and rebuild the vehicle list."""
        # Remove existing rows
        while self._vehicle_list_layout.count():
            item = self._vehicle_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not positions:
            no_data = QLabel(t("tracking.no_vehicles"))
            no_data.setProperty("fontRole", "body")
            no_data.setStyleSheet(f"color: {COLORS['text_muted']};")
            no_data.setAlignment(Qt.AlignCenter)
            no_data.setFixedHeight(80)
            self._vehicle_list_layout.addWidget(no_data)
            return

        for pos in sorted(positions, key=lambda p: p.name.lower()):
            truck_id = fleet_tracking_service.match_to_truck(pos)
            self._build_vehicle_row(pos, truck_id)

        self._updated_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    # ── Polling ───────────────────────────────────────────────────────

    def _poll_and_update(self) -> None:
        """Start a background thread to fetch positions."""
        thread = threading.Thread(target=self._fetch_positions, daemon=True)
        thread.start()

    def _fetch_positions(self) -> None:
        """Fetch positions in background — emits signal to update UI."""
        try:
            positions = fleet_tracking_service.get_positions(
                force_refresh=True,
            )
            self._positionsFetched.emit(positions)
        except Exception as e:
            logger.error("Tracking poll error: %s", e)

    def _apply_update(self, positions: List[VehiclePosition]) -> None:
        """Main-thread slot: update map markers and vehicle list."""
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
        if self._refresh_btn:
            self._refresh_btn.setEnabled(False)

        def do():
            try:
                positions = fleet_tracking_service.get_positions(
                    force_refresh=True,
                )
                # Re-enable button on main thread
                QTimer.singleShot(0, self._enable_refresh_btn)
                self._positionsFetched.emit(positions)
            except Exception as e:
                logger.error("Force refresh failed: %s", e)
                QTimer.singleShot(0, self._enable_refresh_btn)

        thread = threading.Thread(target=do, daemon=True)
        thread.start()

    def _enable_refresh_btn(self) -> None:
        if self._refresh_btn:
            self._refresh_btn.setEnabled(True)

    # ── Cleanup ───────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Ensure cleanup on close."""
        self.shutdown()
        super().closeEvent(event)
