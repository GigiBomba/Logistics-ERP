"""
Route Planner UI — presentation and events only.

Business logic: services/route_planner_controller.py
Map overlays: ui/route_map_renderer.py
Country exclusions UI: ui/route_planner_exclusions.py
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import uuid

try:
    from tkintermapview import TkinterMapView

    HAS_TKMAP = True
except Exception:
    HAS_TKMAP = False

from services.fleet_service import FleetService
from services.route_history_service import RouteHistoryRecord, RouteHistoryService
from services.route_persistence import RoutePersistenceService
from services.route_planner_controller import RoutePlannerController
from services.route_profiles import GRAPHHOPPER_PROFILES
from services.route_result_presenter import format_history_loaded_info
from services.route_state import RouteStateManager
from services.stop_factory import normalize_existing_stop

from ui.route_map_renderer import RouteMapRenderer
from ui.route_planner_exclusions import CountryExclusionsPanel
from services.i18n import t, register_listener, unregister_listener
from ui.styles import Theme
from ui.widgets import ActionButton, StyledCheckbutton, StyledEntry


class RoutePlannerTab:
    """Route Planner window/tab — UI layer only."""

    def __init__(self, parent, db, open_window=True, controller=None):
        self.db = db
        self.controller = controller

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
        self.stop_vars: dict = {}
        self._row_widgets: list = []
        self._trucks_map: dict = {}
        self._last_route_result = None
        self._calc_token = 0
        self._i18n_widgets = []

        if open_window:
            self.win = tk.Toplevel(parent)
            self.win.title(t("route.planner_title"))
            self.win.geometry("1200x800")
            Theme.apply(self.win)
            self.frame = tk.Frame(self.win, bg=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = None
            self.frame = tk.Frame(parent, bg=Theme.BG)
            self.frame.pack(fill="both", expand=True)

        self.stops_state = [
            normalize_existing_stop({"type": "start"}),
            normalize_existing_stop({"type": "destination"}),
        ]

        self._setup_ui()
        self._map_renderer: RouteMapRenderer | None = None

        self.frame.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.frame:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win is not None:
            self.win.title(t("route.planner_title"))
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        self._exclusions_panel.refresh()

    # --- UI construction ---

    def _setup_ui(self) -> None:
        sidebar = tk.Frame(self.frame, bg=Theme.SURFACE, width=360)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self.sidebar_footer = tk.Frame(sidebar, bg=Theme.SURFACE)
        self.sidebar_footer.pack(side="bottom", fill="x", padx=16, pady=(8, 16))

        sidebar_body = self._build_sidebar_scroll_area(sidebar)

        lbl = tk.Label(
            sidebar_body,
            text=f"📍 {t('route.section_header')}",
            font=Theme.FONT_BOLD,
            bg=Theme.SURFACE,
            fg=Theme.ACCENT,
        )
        lbl.pack(pady=20)
        self._i18n_tag(lbl, "route.section_header", "📍 ")

        lbl = tk.Label(sidebar_body, text=t("route.destinations_label"), bg=Theme.SURFACE, fg=Theme.TEXT)
        lbl.pack(anchor="w", padx=20)
        self._i18n_tag(lbl, "route.destinations_label")

        stops_frame = tk.Frame(sidebar_body, bg=Theme.SURFACE)
        stops_frame.pack(fill="x", padx=10, pady=(5, 0))

        self.stops_canvas = tk.Canvas(stops_frame, bg=Theme.SURFACE, height=88, highlightthickness=0)
        self.stops_scroll = tk.Scrollbar(stops_frame, orient="vertical", command=self.stops_canvas.yview)
        self.stops_container_inner = tk.Frame(self.stops_canvas, bg=Theme.SURFACE)
        self.stops_container_inner.bind(
            "<Configure>",
            lambda e: self.stops_canvas.configure(scrollregion=self.stops_canvas.bbox("all")),
        )
        self._stops_window = self.stops_canvas.create_window(
            (0, 0), window=self.stops_container_inner, anchor="nw"
        )
        self.stops_canvas.bind(
            "<Configure>",
            lambda e: self.stops_canvas.itemconfigure(self._stops_window, width=e.width),
        )
        self.stops_canvas.configure(yscrollcommand=self.stops_scroll.set)
        self.stops_canvas.pack(side="left", fill="both", expand=True)
        self.stops_scroll.pack(side="right", fill="y")
        self.stops_container = self.stops_container_inner

        btn_frame = tk.Frame(sidebar_body, bg=Theme.SURFACE)
        btn_frame.pack(fill="x", padx=20, pady=10)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn = ActionButton(btn_frame, t("route.add_stop"), self._add_stop_field, color=Theme.SURFACE2)
        btn.grid(row=0, column=0, sticky="ew", padx=4)
        self._i18n_tag(btn, "route.add_stop")
        btn = ActionButton(btn_frame, t("route.remove_stop"), self._remove_stop_field, color=Theme.SURFACE2)
        btn.grid(row=0, column=1, sticky="ew", padx=4)
        self._i18n_tag(btn, "route.remove_stop")

        self._render_stops_list()

        self._compliance_frame = tk.Frame(sidebar_body, bg=Theme.SURFACE)
        self._compliance_frame.pack(fill="x", padx=20, pady=(4, 8))
        self._summary_text = tk.Label(
            self._compliance_frame, text="", bg=Theme.SURFACE, fg=Theme.TEXT, justify="left", wraplength=300
        )
        self._summary_text.pack(fill="x")
        self._explanation_text = tk.Label(
            self._compliance_frame, text="", bg=Theme.SURFACE, fg=Theme.MUTED, justify="left", wraplength=300
        )
        self._explanation_text.pack(fill="x", pady=(6, 0))

        opts = tk.Frame(sidebar_body, bg=Theme.SURFACE)
        opts.pack(fill="x", padx=20, pady=(6, 12))
        self._highlight_var = tk.BooleanVar(value=False)
        cb = StyledCheckbutton(
            opts,
            text=t("route.highlight_avoided"),
            variable=self._highlight_var,
            bg=Theme.SURFACE,
            activebackground=Theme.SURFACE,
        )
        cb.pack(anchor="w")
        self._i18n_tag(cb, "route.highlight_avoided")
        self._compare_var = tk.BooleanVar(value=True)
        cb = StyledCheckbutton(
            opts,
            text=t("route.show_comparison"),
            variable=self._compare_var,
            bg=Theme.SURFACE,
            activebackground=Theme.SURFACE,
        )
        cb.pack(anchor="w")
        self._i18n_tag(cb, "route.show_comparison")

        btn = ActionButton(
            sidebar_body,
            t("route.export_metadata"),
            self._export_route_metadata,
            color=Theme.SURFACE2,
        )
        btn.pack(fill="x", padx=20, pady=(6, 12))
        self._i18n_tag(btn, "route.export_metadata")

        lbl = tk.Label(sidebar_body, text=t("route.select_truck"), bg=Theme.SURFACE, fg=Theme.TEXT)
        lbl.pack(anchor="w", padx=20, pady=(10, 0))
        self._i18n_tag(lbl, "route.select_truck")
        self.truck_var = tk.StringVar()
        self.truck_dropdown = tk.OptionMenu(sidebar_body, self.truck_var, "")
        self.truck_dropdown.config(bg=Theme.INPUT_BG)
        Theme.style_option_menu(self.truck_dropdown)
        self.truck_dropdown.pack(fill="x", padx=20, pady=5)
        self._load_trucks()

        lbl = tk.Label(sidebar_body, text=t("route.profile_label"), bg=Theme.SURFACE, fg=Theme.TEXT)
        lbl.pack(anchor="w", padx=20, pady=(10, 0))
        self._i18n_tag(lbl, "route.profile_label")
        self.profile_var = tk.StringVar(value="Recommended")
        self.profile_menu = tk.OptionMenu(sidebar_body, self.profile_var, *self.profile_map.keys())
        self.profile_menu.config(bg=Theme.INPUT_BG)
        Theme.style_option_menu(self.profile_menu)
        self.profile_menu.pack(fill="x", padx=20, pady=5)

        self._exclusions_panel = CountryExclusionsPanel(
            sidebar_body,
            self._core.country_avoidance,
        )

        self.btn_search = ActionButton(
            self.sidebar_footer,
            f"🔍 {t('route.calculate_button')}",
            self._on_calculate_click,
            color=Theme.ACCENT,
        )
        self.btn_search.pack(fill="x", pady=(0, 10))
        self._i18n_tag(self.btn_search, "route.calculate_button", "🔍 ")

        self.lbl_info = tk.Label(
            self.sidebar_footer,
            text=t("route.info_placeholder"),
            bg=Theme.SURFACE,
            fg=Theme.MUTED,
            justify="left",
            wraplength=300,
        )
        self.lbl_info.pack(fill="x")
        self._i18n_tag(self.lbl_info, "route.info_placeholder")

        if HAS_TKMAP:
            self.map_widget = TkinterMapView(self.frame, corner_radius=0)
            self.map_widget.pack(side="right", fill="both", expand=True)
            self.map_widget.set_position(44.4268, 26.1025)
            self.map_widget.set_zoom(6)
        else:
            self.map_widget = tk.Canvas(self.frame, bg=Theme.SURFACE2)
            self.map_widget.pack(side="right", fill="both", expand=True)

        self._map_renderer = RouteMapRenderer(self.map_widget)

    def _build_sidebar_scroll_area(self, parent: tk.Widget) -> tk.Frame:
        shell = tk.Frame(parent, bg=Theme.SURFACE)
        shell.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=Theme.SURFACE, highlightthickness=0)
        scrollbar = tk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=Theme.SURFACE)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(body_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        body.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        body.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return body

    # --- Stops UI (presentation only) ---

    def _load_trucks(self) -> None:
        try:
            rows = self.fleet_service.get_trucks()
            menu = self.truck_dropdown["menu"]
            menu.delete(0, "end")
            self._trucks_map = {}
            for row in rows:
                truck_id = str(row[0])
                label = f"{row[1]} - {row[2] or ''}"
                menu.add_command(label=label, command=lambda v=truck_id: self.truck_var.set(v))
                self._trucks_map[truck_id] = row
            if rows:
                self.truck_var.set(str(rows[0][0]))
        except Exception as exc:
            print(exc)

    def _add_stop_field(self) -> None:
        self.stops_state.insert(len(self.stops_state) - 1, normalize_existing_stop({"type": "stop"}))
        self._render_stops_list()

    def _remove_stop_field(self) -> None:
        for i in range(len(self.stops_state) - 2, 0, -1):
            if self.stops_state[i]["type"] == "stop":
                self.stops_state.pop(i)
                break
        self._render_stops_list()

    def _remove_stop_index(self, idx: int) -> None:
        if idx in (0, len(self.stops_state) - 1):
            return
        self.stops_state.pop(idx)
        self._render_stops_list()

    def _render_stops_list(self) -> None:
        for widget in self.stops_container_inner.winfo_children():
            widget.destroy()
        self._row_widgets = []

        for idx, stop in enumerate(self.stops_state):
            row = tk.Frame(self.stops_container_inner, bg=Theme.SURFACE, pady=4)
            row.pack(fill="x", padx=2, pady=2)

            if stop["type"] == "start":
                label = t("route.stop_start")
            elif stop["type"] == "destination":
                label = t("route.stop_destination")
            else:
                label = t("route.stop_n").format(idx)

            tk.Label(row, text=label, bg=Theme.SURFACE, fg=Theme.TEXT).pack(side="left")

            sid = stop.get("id") or uuid.uuid4().hex
            stop["id"] = sid
            if sid not in self.stop_vars:
                self.stop_vars[sid] = tk.StringVar(value=stop.get("address", ""))

            entry = StyledEntry(row, textvariable=self.stop_vars[sid])
            entry.pack(side="left", fill="x", expand=True, padx=8)

            if stop["type"] == "stop":
                tk.Button(
                    row,
                    text="🗑",
                    bg=Theme.SURFACE2,
                    command=lambda i=idx: self._remove_stop_index(i),
                ).pack(side="right")

            self._row_widgets.append((idx, entry))

        visible_rows = min(max(len(self.stops_state), 2), 6)
        self.stops_canvas.configure(height=visible_rows * 44)

    def _collect_stop_addresses(self) -> dict:
        return {sid: var.get().strip() for sid, var in self.stop_vars.items()}

    def _row_address_pairs(self) -> list:
        return [(idx, entry.get().strip()) for idx, entry in self._row_widgets]

    # --- Route calculation (delegates to controller) ---

    def _on_calculate_click(self) -> None:
        ctx, err = self._core.validate_calculation_input(
            truck_id=self.truck_var.get(),
            trucks_map=self._trucks_map,
            profile_label=self.profile_var.get(),
            stops_state=self.stops_state,
            row_addresses=self._row_address_pairs(),
        )
        if err:
            self.lbl_info.config(text=err, fg=Theme.WARNING)
            return

        self._calc_token += 1
        token = self._calc_token

        self.btn_search.config(state="disabled", text=f"⏳ {t('route.calculating')}")
        self.lbl_info.config(text=f"🔄 {t('route.processing')}", fg=Theme.TEXT)

        def callback(result):
            self._schedule_ui(lambda: self._on_route_result(result, ctx, token))

        self._core.start_calculation(ctx, callback)

    def _schedule_ui(self, fn) -> None:
        root = self.win or self.frame
        try:
            root.after(0, fn)
        except tk.TclError:
            pass

    def _on_route_result(self, result, ctx, token: int) -> None:
        if token != self._calc_token:
            return

        if self.btn_search.winfo_exists():
            self.btn_search.config(state="normal", text=f"🔍 {t('route.calculate_button')}")

        processed, err = self._core.process_calculation_result(
            result,
            ctx,
            self._collect_stop_addresses(),
        )
        if err:
            self.lbl_info.config(text=err, fg=Theme.DANGER)
            return
        if not processed:
            self.lbl_info.config(text=f"❌ {t('route.calc_failed')}", fg=Theme.DANGER)
            return

        self._last_route_result = processed.route
        self.lbl_info.config(
            text=processed.info_text,
            fg=Theme.SUCCESS if hasattr(Theme, "SUCCESS") else Theme.TEXT,
        )
        self._apply_compliance(processed.compliance)
        self._draw_route_on_map(processed.route)

    def _apply_compliance(self, compliance) -> None:
        if not compliance:
            return
        self._summary_text.config(text=compliance.summary_text)
        self._explanation_text.config(text=compliance.explanation_text)

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
                show_comparison=self._compare_var.get(),
                highlight_avoided=self._highlight_var.get(),
            )
            self._map_renderer.update_stop_markers(self.stops_state)
        except Exception:
            pass

    # --- History load ---

    def load_history_route(self, record: RouteHistoryRecord, draw: bool = True) -> None:
        patch = self._core.load_history_record(record)

        if len(patch.get("stops") or []) >= 2:
            self.stops_state = patch["stops"]
            self.stop_vars = {}
            self._render_stops_list()

        if patch.get("profile_label"):
            self.profile_var.set(patch["profile_label"])
        if patch.get("truck_id"):
            try:
                self.truck_var.set(patch["truck_id"])
            except Exception:
                pass

        self._exclusions_panel.set_selected(patch.get("excluded_countries") or [])

        route = patch["route"]
        self._last_route_result = route
        self.lbl_info.config(text=format_history_loaded_info(record), fg=Theme.SUCCESS)

        if draw and route.get("geometry") and self._map_renderer:
            try:
                self._map_renderer.draw_route(
                    route["geometry"],
                    route,
                    show_comparison=self._compare_var.get(),
                    highlight_avoided=False,
                )
                self._map_renderer.update_stop_markers(self.stops_state)
                self._map_renderer.center_on_geometry(route["geometry"])
            except Exception:
                pass

    # --- Export ---

    def _export_route_metadata(self) -> None:
        path, err = self._core.export_route_metadata(self._last_route_result)
        if err:
            self.lbl_info.config(text=err, fg=Theme.WARNING)
            return
        self.lbl_info.config(
            text=t("route.export_success").format(path),
            fg=Theme.SUCCESS if hasattr(Theme, "SUCCESS") else Theme.TEXT,
        )
