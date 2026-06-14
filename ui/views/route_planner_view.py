"""PySide6 route planner view.

Replaces ``ui/route_planner.py``. Uses ``MapWidget`` for the map and
``RoutePlannerController`` for business logic. Fully embedded as a QWidget.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
)

from services.fleet_service import FleetService
from services.i18n import t, register_listener, unregister_listener
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_persistence import RoutePersistenceService
from services.route_planner_controller import RoutePlannerController
from services.route_profiles import GRAPHHOPPER_PROFILES
from services.route_result_presenter import format_history_loaded_info
from services.route_state import RouteStateManager
from services.stop_factory import normalize_existing_stop
from ui.map import MapWidget, QtRouteMapRenderer
from ui.views.country_exclusions_panel import CountryExclusionsPanel
from ui.widgets import (
    StyledLineEdit,
    StyledComboBox,
    StyledCheckBox,
    field,
)
from ui.design_tokens import SP
from ui.components import (
    Card, CardHeader, Btn, PageTitle, Label,
)
from ui.theme import COLORS

logger = logging.getLogger(__name__)


class QtRoutePlannerView(QWidget):
    """Route planner with sidebar controls and an interactive map."""

    SIDEBAR_MIN_WIDTH = 360

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        controller=None,
    ):
        super().__init__(parent)
        self.db = db
        self.controller = controller  # MainWindow reference for module switching

        self._core = RoutePlannerController(db)
        self.route_history_service = RouteHistoryService(db)
        self.route_state = RouteStateManager(db)
        self.fleet_service = FleetService(db)
        self._persistence = RoutePersistenceService(
            self.route_history_service,
            self.route_state,
            self._core.cost_engine,
        )
        self._core.bind_persistence(self._persistence)

        self.profile_map = GRAPHHOPPER_PROFILES
        self._profile_key_to_display: Dict[str, str] = {}
        self._profile_display_to_key: Dict[str, str] = {}

        self.stop_vars: Dict[str, str] = {}
        self._stop_rows: Dict[int, QWidget] = {}
        self._stop_ids: Dict[int, str] = {}
        self._trucks_map: Dict[str, Any] = {}
        self._truck_label_to_id: Dict[str, str] = {}
        self._selected_truck_id: Optional[str] = None

        self._last_route_result: Optional[Dict[str, Any]] = None
        self._last_route_history_id: Optional[int] = None
        self._last_route_calc_ctx = None
        self._pending_clear = False
        self._calc_token = 0
        self._dispatch_frame: Optional[QWidget] = None

        self.stops_state = [
            normalize_existing_stop({"type": "start"}),
            normalize_existing_stop({"type": "destination"}),
        ]

        self._build_ui()
        self._render_stops_list()

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(40, 0, 40, 0)
        hdr_layout.setSpacing(SP["1"])
        hdr.setFixedHeight(72)
        hdr_layout.addWidget(PageTitle(hdr, t("route.page_title", default="Route Planner")))
        hdr_layout.addWidget(Label(hdr, t("route.page_subtitle", default="Plan and optimise routes"), role="secondary"))
        outer.addWidget(hdr)

        self._content_widget = QWidget()
        content = QHBoxLayout(self._content_widget)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        # Sidebar
        sidebar = QFrame(self._content_widget)
        sidebar.setObjectName("card")
        sidebar.setFixedWidth(self.SIDEBAR_MIN_WIDTH)
        sidebar.setMinimumWidth(self.SIDEBAR_MIN_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])
        sidebar_layout.setSpacing(SP["3"])

        self._build_sidebar(sidebar_layout)
        content.addWidget(sidebar)

        # Map
        self.map_widget = MapWidget(self._content_widget)
        self._map_renderer = QtRouteMapRenderer(self.map_widget)
        self.map_widget.set_click_callback(self._on_map_click)
        self.map_widget.setMinimumWidth(1)
        self._click_to_add_enabled = False
        content.addWidget(self.map_widget, 1)

        outer.addWidget(self._content_widget, 1)

    def _build_sidebar(self, layout: QVBoxLayout) -> None:
        # Body — scrollable section between header and footer
        body = QScrollArea()
        body.setWidgetResizable(True)
        body.setFrameShape(QFrame.NoFrame)
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(SP["3"])
        body_layout.setAlignment(Qt.AlignTop)

        # ── Card 1: Route Inputs ──
        card1 = Card(body_widget)
        c1l = card1.layout()
        CardHeader(c1l, t("route.section_header"))

        # Stop list — always visible, no scroll wrapper
        self._stops_container = QWidget()
        self._stops_container_layout = QVBoxLayout(self._stops_container)
        self._stops_container_layout.setContentsMargins(0, 0, 0, 0)
        self._stops_container_layout.setSpacing(SP["1"])
        self._stops_container_layout.setAlignment(Qt.AlignTop)
        c1l.addWidget(self._stops_container)

        # Add/Remove buttons
        btn_row = QWidget(card1)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(SP["2"])
        add_btn = Btn(btn_row, t("route.add_stop"), variant="ghost", size="sm", command=self._add_stop_field)
        btn_layout.addWidget(add_btn, 1)
        remove_btn = Btn(btn_row, t("route.remove_stop"), variant="ghost", size="sm", command=self._remove_stop_field)
        btn_layout.addWidget(remove_btn, 1)
        c1l.addWidget(btn_row)

        body_layout.addWidget(card1)

        # ── Card 2: Options ──
        card2 = Card(body_widget)
        c2l = card2.layout()
        CardHeader(c2l, t("route.options_header", default="OPTIONS"))

        # Truck dropdown
        self.truck_combo = StyledComboBox(card2)
        self.truck_combo.currentIndexChanged.connect(self._on_truck_selected)
        c2l.addWidget(field(card2, t("route.select_truck"), self.truck_combo))

        # Profile dropdown
        self._rebuild_profile_display_names()
        self.profile_combo = StyledComboBox(card2, values=list(self._profile_key_to_display.values()))
        self.profile_combo.setCurrentText(self._profile_key_to_display.get("Recommended", "Recommended"))
        c2l.addWidget(field(card2, t("route.profile_label"), self.profile_combo))

        body_layout.addWidget(card2)

        # Country exclusions
        self._exclusions_panel = CountryExclusionsPanel(
            body_widget,
            self._core.country_avoidance,
            on_change=self._on_exclusions_changed,
        )
        body_layout.addWidget(self._exclusions_panel)

        # Compliance checkboxes (between cards 2 and 3)
        self._compare_check = StyledCheckBox(body_widget, text=t("route.show_comparison"))
        self._compare_check.setChecked(True)
        body_layout.addWidget(self._compare_check)

        self._click_add_check = StyledCheckBox(body_widget, text=t("route.click_to_add_stop"))
        self._click_add_check.stateChanged.connect(self._toggle_click_add)
        body_layout.addWidget(self._click_add_check)

        body_layout.addStretch()
        body.setWidget(body_widget)
        layout.addWidget(body, 1)

        # ── Card 3: Results & Actions (fixed at bottom) ──
        card3 = Card()
        c3l = card3.layout()

        self.calculate_btn = Btn(
            card3,
            t("route.calculate_button"),
            variant="primary",
            command=self._on_calculate_click,
        )
        c3l.addWidget(self.calculate_btn)

        # Export button
        export_btn = Btn(
            card3, t("route.export_metadata"), variant="secondary", size="sm",
            command=self._export_route_metadata,
        )
        c3l.addWidget(export_btn)

        self.lbl_info = QLabel(t("route.info_placeholder"))
        self.lbl_info.setProperty("fontRole", "muted")
        self.lbl_info.setWordWrap(True)
        c3l.addWidget(self.lbl_info)

        # Compliance texts
        self._summary_text = QLabel("")
        self._summary_text.setProperty("fontRole", "muted")
        self._summary_text.setWordWrap(True)
        c3l.addWidget(self._summary_text)

        self._explanation_text = QLabel("")
        self._explanation_text.setProperty("fontRole", "helper")
        self._explanation_text.setWordWrap(True)
        c3l.addWidget(self._explanation_text)

        self._dispatch_container = QWidget()
        self._dispatch_container_layout = QVBoxLayout(self._dispatch_container)
        self._dispatch_container_layout.setContentsMargins(0, 0, 0, 0)
        self._dispatch_container_layout.setSpacing(SP["2"])
        self._dispatch_container.hide()
        c3l.addWidget(self._dispatch_container)

        layout.addWidget(card3)

        self._load_trucks()

    # ── Profile names ──────────────────────────────────────────────────────────

    def _rebuild_profile_display_names(self) -> None:
        self._profile_key_to_display = {k: t(f"route.profile_{k.lower()}") for k in self.profile_map}
        self._profile_display_to_key = {v: k for k, v in self._profile_key_to_display.items()}

    # ── Trucks ─────────────────────────────────────────────────────────────────

    def _load_trucks(self) -> None:
        try:
            from services.conflict_service import TripConflictService
            conflict_svc = TripConflictService(self.fleet_service.db)
            rows = self.fleet_service.get_trucks()
            self._trucks_map = {}
            self._truck_label_to_id = {}
            self.truck_combo.clear()
            for row in rows:
                truck_id = str(row["id"])
                plate = row["plate_number"]
                label = f"{plate} - {row.get('model') or ''}"
                next_slot = conflict_svc.get_next_available_slot(plate)
                if next_slot:
                    label = f"{label}  [{t('dispatch_board.available_from').format(next_slot)}]"
                self._truck_label_to_id[label] = truck_id
                self._trucks_map[truck_id] = row
                self.truck_combo.addItem(label, truck_id)
            if rows:
                self.truck_combo.setCurrentIndex(0)
                self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())
        except Exception:
            logger.exception("Failed to load trucks")

    def _on_truck_selected(self, _index: int) -> None:
        self._selected_truck_id = self._truck_label_to_id.get(self.truck_combo.currentText())

    # ── Country exclusions ─────────────────────────────────────────────────────

    def _on_exclusions_changed(self) -> None:
        codes = self._core.get_excluded_countries()
        if self._map_renderer:
            self._map_renderer.draw_avoided_country_overlays(codes)

    # ── Stops ──────────────────────────────────────────────────────────────────

    def _add_stop_field(self) -> None:
        self.stops_state.insert(len(self.stops_state) - 1, normalize_existing_stop({"type": "stop"}))
        self._render_stops_list()

    def _remove_stop_field(self) -> None:
        for i in range(len(self.stops_state) - 2, 0, -1):
            if self.stops_state[i].get("type") == "stop":
                self.stops_state.pop(i)
                break
        self._render_stops_list()

    def _remove_stop_index(self, idx: int) -> None:
        if idx in (0, len(self.stops_state) - 1):
            return
        self.stops_state.pop(idx)
        self._render_stops_list()

    def _render_stops_list(self) -> None:
        # Clear existing rows
        for widget in self._stops_container_layout.parent().findChildren(QWidget):
            pass  # handled below via deleteLater
        while self._stops_container_layout.count():
            item = self._stops_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._stop_rows.clear()
        self._stop_ids.clear()

        for idx, stop in enumerate(self.stops_state):
            sid = stop.get("id") or uuid.uuid4().hex
            stop["id"] = sid
            if sid not in self.stop_vars:
                self.stop_vars[sid] = stop.get("address", "")

            row = QWidget(self._stops_container)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(SP["1"], 0, SP["1"], 0)
            row_layout.setSpacing(SP["2"])

            if stop["type"] == "start":
                label_text = t("route.stop_start")
            elif stop["type"] == "destination":
                label_text = t("route.stop_destination")
            else:
                label_text = t("route.stop_n").format(idx)

            lbl = QLabel(label_text)
            lbl.setProperty("fontRole", "label")
            row_layout.addWidget(lbl)

            entry = StyledLineEdit(row, text=stop.get("address", ""))
            entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            entry.textChanged.connect(
                lambda text, s=sid: self.stop_vars.__setitem__(s, text)
            )
            row_layout.addWidget(entry, 1)

            if stop["type"] == "stop":
                del_btn = Btn(row, "", variant="ghost", icon_name="mdi6.delete", command=lambda i=idx: self._remove_stop_index(i))
                del_btn.setFixedSize(28, 28)
                row_layout.addWidget(del_btn)

            self._stops_container_layout.addWidget(row)
            self._stop_rows[idx] = row
            self._stop_ids[idx] = sid

        # Bind Enter to calculate
        if self._stop_rows:
            last_row = self._stop_rows.get(len(self.stops_state) - 1)
            if last_row:
                for child in last_row.findChildren(StyledLineEdit):
                    child.returnPressed.connect(self._on_calculate_click)
                    break

    def _collect_stop_addresses(self) -> dict:
        return dict(self.stop_vars)

    def _row_address_pairs(self) -> list:
        result = []
        for idx, stop in enumerate(self.stops_state):
            sid = stop.get("id", "")
            addr = self.stop_vars.get(sid, stop.get("address", ""))
            result.append((idx, addr))
        return result

    def _toggle_click_add(self, state: int) -> None:
        self._click_to_add_enabled = bool(state)
        if self._click_to_add_enabled:
            js = (
                "var el = document.querySelector('.leaflet-container');"
                "if (el) el.style.cursor = 'crosshair';"
            )
        else:
            js = (
                "var el = document.querySelector('.leaflet-container');"
                "if (el) el.style.cursor = '';"
            )
        self.map_widget._run_js(js)

    def _on_map_click(self, lat: float, lng: float) -> None:
        if not self._click_to_add_enabled:
            return

        address = self._reverse_geocode(lat, lng)

        new_stop = normalize_existing_stop({
            "type": "stop",
            "lat": lat,
            "lon": lng,
            "address": address,
            "resolved": True,
        })
        self.stops_state.insert(len(self.stops_state) - 1, new_stop)
        self._render_stops_list()

    @staticmethod
    def _reverse_geocode(lat: float, lng: float) -> str:
        try:
            import requests
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {"lat": lat, "lon": lng, "format": "json", "zoom": 14}
            headers = {"User-Agent": "OperionERP/1.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=5)
            if resp.ok:
                data = resp.json()
                return data.get("display_name", "") or f"{lat:.5f}, {lng:.5f}"
        except Exception:
            pass
        return f"{lat:.5f}, {lng:.5f}"

    # ── Calculation ────────────────────────────────────────────────────────────

    def _on_calculate_click(self) -> None:
        ctx, err = self._core.validate_calculation_input(
            truck_id=self._selected_truck_id or "",
            trucks_map=self._trucks_map,
            profile_label=self._profile_display_to_key.get(
                self.profile_combo.currentText(), "Recommended"
            ),
            stops_state=self.stops_state,
            row_addresses=self._row_address_pairs(),
        )
        if err or ctx is None:
            self.lbl_info.setText(err or "Unknown error")
            self.lbl_info.setStyleSheet(f"color: {COLORS.get('warning', '#f59e0b')};")
            return

        self._calc_token += 1
        token = self._calc_token

        self.calculate_btn.setEnabled(False)
        self.calculate_btn.setText(f"\u23f3 {t('route.calculating')}")
        self.lbl_info.setText(f"\U0001f504 {t('route.processing')}")
        self.lbl_info.setStyleSheet("")

        def callback(result):
            QTimer.singleShot(0, lambda: self._on_route_result(result, ctx, token))

        self._core.start_calculation(ctx, callback)

    def _on_route_result(self, result, ctx, token: int) -> None:
        if token != self._calc_token:
            return

        self.calculate_btn.setEnabled(True)
        self.calculate_btn.setText(f"\U0001f50d {t('route.calculate_button')}")

        processed, err = self._core.process_calculation_result(
            result,
            ctx,
            self._collect_stop_addresses(),
        )
        if err:
            self.lbl_info.setText(err)
            self.lbl_info.setStyleSheet(f"color: {COLORS.get('danger', '#ef4444')};")
            return
        if not processed:
            self.lbl_info.setText(f"\u274c {t('route.calc_failed')}")
            self.lbl_info.setStyleSheet(f"color: {COLORS.get('danger', '#ef4444')};")
            return

        self._last_route_result = processed.route
        self._last_route_history_id = processed.route.get("history_id")
        self._last_route_calc_ctx = ctx
        self._populate_stops_from_route(processed.route)
        self.lbl_info.setText(processed.info_text)
        self.lbl_info.setStyleSheet("")
        self._apply_compliance(processed.compliance)
        self._draw_route_on_map(processed.route)
        self._show_dispatch_buttons()

    def _show_dispatch_buttons(self) -> None:
        # Clear existing
        while self._dispatch_container_layout.count():
            item = self._dispatch_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(SP["2"])

        calc_btn = Btn(
            btn_row,
            t("route.send_to_calculator"),
            variant="secondary",
            command=self._go_to_calculator,
        )
        btn_layout.addWidget(calc_btn, 1)

        discard_btn = Btn(btn_row, "", variant="danger", icon_name="mdi6.delete", command=self._discard_route)
        discard_btn.setFixedSize(36, 36)
        btn_layout.addWidget(discard_btn)

        self._dispatch_container_layout.addWidget(btn_row)
        self._dispatch_container.show()

    def _go_to_calculator(self) -> None:
        if self._last_route_history_id:
            truck_id = str(self._selected_truck_id) if self._selected_truck_id else None
            self._core.commit_route(self._last_route_history_id, truck_id=truck_id)
            self._pending_clear = True
        if self.controller and hasattr(self.controller, "_switch_module"):
            self.controller._switch_module("calculator")

    def _discard_route(self) -> None:
        if self._last_route_history_id:
            self._core.discard_route(self._last_route_history_id)
        self._clear_route_state()

    def _clear_route_state(self) -> None:
        self._last_route_result = None
        self._last_route_history_id = None
        self._last_route_calc_ctx = None
        self._dispatch_container.hide()
        while self._dispatch_container_layout.count():
            item = self._dispatch_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if self._map_renderer:
            self._map_renderer.clear_route_overlays()
            self._map_renderer.clear_stop_markers()
        self._summary_text.setText("")
        self._explanation_text.setText("")
        self.lbl_info.setText(t("route.info_placeholder"))
        self.lbl_info.setStyleSheet("")
        self.stops_state = [
            normalize_existing_stop({"type": "start"}),
            normalize_existing_stop({"type": "destination"}),
        ]
        self.stop_vars = {}
        self._stop_rows = {}
        self._stop_ids = {}
        self._render_stops_list()

    def _populate_stops_from_route(self, route: dict) -> None:
        stops = route.get("stops") or []
        for i, stop in enumerate(self.stops_state):
            if i < len(stops):
                try:
                    stop["lat"], stop["lon"] = float(stops[i][0]), float(stops[i][1])
                    stop["resolved"] = True
                except Exception:
                    pass

    def _apply_compliance(self, compliance) -> None:
        if not compliance:
            return
        self._summary_text.setText(compliance.summary_text)
        self._explanation_text.setText(compliance.explanation_text)

    def _draw_route_on_map(self, route: dict) -> None:
        if not self._map_renderer:
            return
        geometry = route.get("geometry") or []
        if not geometry:
            return
        try:
            self._map_renderer.draw_route(
                geometry,
                route,
                show_comparison=self._compare_check.isChecked(),
                highlight_avoided=True,
            )
            self._map_renderer.update_stop_markers(self.stops_state)
        except Exception:
            logger.exception("Failed to draw route on map")

    # ── History load ───────────────────────────────────────────────────────────

    def load_history_route(self, record: RouteHistoryRecord, draw: bool = True) -> None:
        patch = self._core.load_history_record(record)

        if len(patch.get("stops") or []) >= 2:
            self.stops_state = patch["stops"]
            self.stop_vars = {}
            self._render_stops_list()

        if patch.get("profile_label"):
            key = patch["profile_label"]
            self.profile_combo.setCurrentText(
                self._profile_key_to_display.get(key, key)
            )
        if patch.get("truck_id"):
            try:
                idx = self.truck_combo.findData(patch["truck_id"])
                if idx >= 0:
                    self.truck_combo.setCurrentIndex(idx)
            except Exception:
                pass

        self._exclusions_panel.set_selected(patch.get("excluded_countries") or [])

        route = patch["route"]
        self._last_route_result = route
        self.lbl_info.setText(format_history_loaded_info(record))

        if draw and route.get("geometry") and self._map_renderer:
            try:
                self._map_renderer.draw_route(
                    route["geometry"],
                    route,
                    show_comparison=self._compare_check.isChecked(),
                    highlight_avoided=True,
                )
                self._map_renderer.update_stop_markers(self.stops_state)
                self._map_renderer.center_on_geometry(route["geometry"])
            except Exception:
                logger.exception("Failed to draw history route on map")

    # ── Export ─────────────────────────────────────────────────────────────────

    def _export_route_metadata(self) -> None:
        path, err = self._core.export_route_metadata(self._last_route_result)
        if err:
            self.lbl_info.setText(err)
            self.lbl_info.setStyleSheet(f"color: {COLORS.get('warning', '#f59e0b')};")
            return
        self.lbl_info.setText(t("route.export_success").format(path))

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        try:
            old_key = self._profile_display_to_key.get(self.profile_combo.currentText(), "Recommended")
            self._rebuild_profile_display_names()
            self.profile_combo.clear()
            self.profile_combo.addItems(list(self._profile_key_to_display.values()))
            self.profile_combo.setCurrentText(
                self._profile_key_to_display.get(
                    old_key, self._profile_key_to_display.get("Recommended", "Recommended")
                )
            )
            self._exclusions_panel.refresh()
            self._render_stops_list()
        except Exception:
            logger.exception("Language refresh failed")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        if self._pending_clear:
            self._pending_clear = False
            self._clear_route_state()
        # Recreate map widget if it was destroyed by shutdown()
        try:
            self.map_widget.isWidgetType()
        except RuntimeError:
            from ui.map.map_widget import MapWidget
            self.map_widget = MapWidget(self._content_widget)
            self._map_renderer = QtRouteMapRenderer(self.map_widget)
            self.map_widget.set_click_callback(self._on_map_click)
            self.map_widget.setMinimumWidth(1)
            content_layout = self._content_widget.layout()
            if content_layout:
                content_layout.addWidget(self.map_widget, 1)

    def shutdown(self) -> None:
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        try:
            self.map_widget.destroy()
        except Exception:
            pass
        self._map_renderer = None
