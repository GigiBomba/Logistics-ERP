import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, timedelta
import logging
import re
import os
from typing import Optional
import customtkinter as ctk
from ui.widgets import StyledEntry, ActionButton, section_header
from ui.styles import Theme
from ui.navigation import NavPanel
from services.trip_context import register_trip_listener, unregister_trip_listener
from services.fleet_service import FleetService
from services.i18n import t, register_listener, unregister_listener
from services.fuel_price_service import FuelPriceService
from services.operations.event_bus import EventBus, SETTINGS_UPDATED
from utils.tk_helpers import safe_destroy
from ui.theme import FONTS

logger = logging.getLogger(__name__)


from ui.i18n_mixin import I18nMixin

class MainWindow(I18nMixin):
    def __init__(self, root, db, api, prefs=None, ops=None):
        I18nMixin.__init__(self)
        self.root = root
        self.db = db
        self.api = api
        self.ops = ops
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self.fleet_service = FleetService(self.db)
        self._event_bus = EventBus()
        self._module_cache = {}
        self._active_module = None

        from services.calculator import TripCalculator
        self.calculator = TripCalculator()

        self._i18n_widgets: list = []

        from ui.app_shell import AppShell
        self.app_shell = AppShell(self.root, self.db, on_nav_select=self._switch_module, prefs=self.prefs, ops=self.ops)
        self.nav = self.app_shell.nav

        self._build_nav()
        self._setup_ui()
        try:
            register_trip_listener(self._on_trip_update)
        except Exception:
            pass

        self.root.bind("<Control-s>", lambda e: self._handle_calculate())
        self.root.bind("<Control-h>", lambda e: self._open_history())

        self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)

        self._fuel_service = FuelPriceService()
        self._fuel_service.refresh(background=True)
        self._init_fuel_status()

    def _on_language_changed(self, lang):
        logger.info("MainWindow language change -> %s | refreshing nav + title + combos", lang)
        self._refresh_nav_labels()
        self.app_shell.set_breadcrumb(self._active_module and t(f"nav.{self._active_module}") or t("nav.overview"))

    def refresh_translations(self):
        self.root.title(t("app.title"))
        currencies = t("main.currencies")
        if isinstance(currencies, str):
            currencies = ["EUR", "RON", "USD", "GBP"]
        try:
            self.c_val.configure(values=currencies)
        except Exception:
            pass
        self._update_fuel_status()

    def _open_fleet(self):
        from ui.fleet_tab import FleetTab
        FleetTab(self.root, self.db, ops=self.ops)

    def _open_maintenance_analytics(self):
        from ui.views.maintenance_analytics_view import MaintenanceAnalyticsView
        MaintenanceAnalyticsView(self.root, self.db)

    def _open_maintenance_control(self):
        from ui.maintenance_control_panel import MaintenanceControlPanel
        MaintenanceControlPanel(self.root, self.db, prefs=self.prefs)

    def _open_dispatch_board(self):
        from ui.views.dispatch_board_view import DispatchBoardView
        DispatchBoardView(self.root, self.db, prefs=self.prefs, ops=self.ops)

    def _open_driver_manager(self):
        from ui.driver_manager import DriverManager
        DriverManager(self.root, self.db, ops=self.ops)

    def _load_trucks_main(self):
        try:
            rows = self.fleet_service.get_trucks()
            menu = self.truck_dropdown['menu']
            menu.delete(0, 'end')
            self._main_trucks_map = {}
            for r in rows:
                tid = str(r["id"])
                label = f"{r['plate_number']} - {r['model'] or ''}"
                menu.add_command(label=label, command=lambda v=tid: self._on_main_truck_selected(v))
                try:
                    row_dict = {k: r[k] for k in r.keys()}
                except Exception:
                    row_dict = {'id': r['id'], 'plate_number': r['plate_number'], 'model': r['model'], 'fuel_consumption': r.get('fuel_consumption')}
                self._main_trucks_map[tid] = row_dict
            if rows:
                first = str(rows[0]["id"])
                self.truck_var.set(first)
                self._on_main_truck_selected(first)
        except Exception:
            pass

    def _on_main_truck_selected(self, truck_id):
        try:
            truck = self._main_trucks_map.get(str(truck_id))
            self.selected_truck = truck
            try:
                self.selected_truck_fuel = float(truck.get('fuel_consumption') or truck.get('fuel_consumption_l_per_100km') or 34.0)
            except Exception:
                self.selected_truck_fuel = 34.0
            try:
                self.truck_var.set(str(truck_id))
            except Exception:
                pass
        except Exception:
            pass

    def _open_route_planner(self):
        from ui.route_planner import RoutePlannerTab
        RoutePlannerTab(self.root, self.db, controller=self)

    def _open_route_history(self):
        from ui.route_history_view import RouteHistoryView
        RouteHistoryView(self.root, self.db, controller=self)

    def _on_settings_updated(self, ev):
        pass  # nav_mode no longer used

    def _rebuild_nav(self):
        """Build the full navigation sidebar (called once at init)."""
        nav = self.app_shell.nav

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
        nav.add_item("maintenance", "\U0001f527", t("nav.maintenance_analytics"), i18n_key="nav.maintenance_analytics")
        nav.add_item("maintenance_control", "\U0001f529", t("nav.maintenance_control"), i18n_key="nav.maintenance_control")
        nav.add_item("tachograph", "\U0001f4be", t("nav.tachograph"), i18n_key="nav.tachograph")

        nav.add_group(t("nav.group_finance"), "nav.group_finance")
        nav.add_item("invoices", "\U0001f9fe", t("nav.invoices"), i18n_key="nav.invoices")
        nav.add_item("history", "\U0001f4cb", t("nav.history"), i18n_key="nav.history")
        nav.add_item("route_history", "\U0001f5c2", t("nav.route_history"), i18n_key="nav.route_history")

        nav.add_settings_item("settings", "\u2699\ufe0f", t("nav.settings"))
        nav.select("overview")

    def _build_nav(self):
        self._rebuild_nav()

    def _refresh_nav_labels(self):
        """Refresh all nav item labels and group headers without creating duplicates."""
        nav = self.app_shell.nav
        # Update group labels
        for name, i18n_key in nav._group_i18n_keys.items():
            if name in nav._group_labels:
                try:
                    nav._group_labels[name].config(text=t(i18n_key))
                except Exception:
                    pass
        # Update item labels
        for key, i18n_key in nav._item_i18n_keys.items():
            if key in nav._labels:
                try:
                    nav._labels[key].config(text=t(i18n_key))
                except Exception:
                    pass
        logger.debug("NavPanel labels refreshed | %d items + %d groups",
                     sum(1 for k in nav._item_i18n_keys if k in nav._labels),
                     sum(1 for n in nav._group_i18n_keys if n in nav._group_labels))

    def _setup_ui(self):
        self._switch_module("overview")

    def _build_overview(self, parent):
        from ui.overview import OverviewDashboard
        self._overview = OverviewDashboard(parent, self.db, ops=self.ops)
        self._overview.pack(fill="both", expand=True)

    def _build_calculator_form(self, parent):
        calc_frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
        calc_frame.pack(fill="both", expand=True)

        self.scrollable_frame = ctk.CTkScrollableFrame(calc_frame, fg_color=Theme.BG)
        self.scrollable_frame.pack(fill="both", expand=True)

        ident_f = ctk.CTkFrame(self.scrollable_frame, fg_color=Theme.BG)
        ident_f.pack(fill="x")
        lbl = section_header(ident_f, t("main.section_identify"), _return=True)
        self.i18n_tag(lbl, "main.section_identify")
        lbl = ctk.CTkLabel(ident_f, text=t("main.truck_label"), fg_color=Theme.BG, text_color=Theme.TEXT, font=FONTS["label"])
        lbl.pack(anchor="w", pady=(8,0))
        self.i18n_tag(lbl, "main.truck_label")
        self.truck_var = tk.StringVar()
        self.truck_dropdown = tk.OptionMenu(ident_f, self.truck_var, t("app.loading"))
        Theme.style_option_menu(self.truck_dropdown)
        self.truck_dropdown.pack(fill="x", pady=2)
        self.e_client = self._add_field(ident_f, "main.client_label")
        self.selected_truck = None
        self.route_distance = 0.0
        self.route_toll = 0.0
        self.route_fuel_liters = 0.0
        self.selected_truck_fuel = None
        self._current_route_history_id: Optional[int] = None
        try:
            self._load_trucks_main()
        except Exception:
            pass

        fin_f = ctk.CTkFrame(self.scrollable_frame, fg_color=Theme.BG)
        fin_f.pack(fill="x")
        lbl = section_header(fin_f, t("main.section_finance"), _return=True)
        self.i18n_tag(lbl, "main.section_finance")
        self.e_price = self._add_field(fin_f, "main.offer_price")

        lbl = ctk.CTkLabel(fin_f, text=t("main.currency_label"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(anchor="w", pady=(8,0))
        self.i18n_tag(lbl, "main.currency_label")
        currencies = t("main.currencies")
        if isinstance(currencies, str):
            currencies = ["EUR", "RON", "USD", "GBP"]
        self.c_val = ctk.CTkComboBox(fin_f, values=currencies, state="readonly")
        self.c_val.set(currencies[0])
        self.c_val.pack(fill="x", pady=5)

        cost_f = ctk.CTkFrame(self.scrollable_frame, fg_color=Theme.BG)
        cost_f.pack(fill="x")
        lbl = section_header(cost_f, t("main.section_costs"), _return=True)
        self.i18n_tag(lbl, "main.section_costs")
        self.e_sal = self._add_field(cost_f, "main.salary_label"); self.e_sal.insert(0, "0")
        self.e_tax = None
        self.e_extra = self._add_field(cost_f, "main.extra_costs_label"); self.e_extra.insert(0, "0")

        time_f = ctk.CTkFrame(self.scrollable_frame, fg_color=Theme.BG)
        time_f.pack(fill="x")
        lbl = section_header(time_f, t("main.section_planning"), _return=True)
        self.i18n_tag(lbl, "main.section_planning")
        self.e_start = self._add_field(time_f, "main.start_date_label")
        self.e_start.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.e_days = self._add_field(time_f, "main.duration_label"); self.e_days.insert(0, "1")
        self.e_term = self._add_field(time_f, "main.payment_term_label"); self.e_term.insert(0, "30")

        btn_f = ctk.CTkFrame(self.scrollable_frame, fg_color=Theme.BG)
        btn_f.pack(fill="x")
        self._calc_btn = ActionButton(btn_f, t("main.calculate_button"), self._handle_calculate,
                     color=Theme.ACCENT_SUCCESS)
        self._calc_btn.pack(fill="x")
        self.i18n_tag(self._calc_btn, "main.calculate_button")

        self.res_box = ctk.CTkFrame(self.scrollable_frame, fg_color=Theme.SURFACE)
        self.res_box.pack(fill="x", padx=40, pady=(0, 50))
        self.l_res = ctk.CTkLabel(self.res_box, text=t("main.placeholder_info"),
                                fg_color=Theme.SURFACE, text_color=Theme.MUTED, font=FONTS["body_bold"],
                                justify="center", wraplength=650)
        self.l_res.pack()
        self.i18n_tag(self.l_res, "main.placeholder_info")

        self._fuel_status_lbl = ctk.CTkLabel(self.scrollable_frame, text="",
                                          fg_color=Theme.BG, text_color=Theme.MUTED,                                           font=FONTS["label"])
        self._fuel_status_lbl.pack(anchor="se", padx=10, pady=(0, 5))

        return calc_frame

    def _switch_module(self, key):
        old_key = self._active_module
        if old_key and old_key in self._module_cache:
            cache = self._module_cache[old_key]
            obj = cache.get("obj")
            if hasattr(obj, "shutdown"):
                try:
                    obj.shutdown()
                except Exception:
                    pass
            frame = cache.get("frame")
            if frame is not None:
                try:
                    frame.pack_forget()
                except Exception:
                    pass

        vc = self.app_shell.view_container
        self.app_shell.set_breadcrumb(t(f"nav.{key}") if key != "overview" else t("nav.overview"))

        if key not in self._module_cache:
            self._module_cache[key] = self._create_module(key, vc)

        cache = self._module_cache.get(key)
        if cache and cache.get("frame") is not None:
            cache["frame"].pack(fill="both", expand=True)
            obj = cache.get("obj")
            if obj and hasattr(obj, "wakeup"):
                try:
                    obj.wakeup()
                except Exception:
                    pass
        self._active_module = key

    def _create_module(self, key, parent):
        """Factory for view modules."""
        if key == "overview":
            from ui.overview import OverviewDashboard
            obj = OverviewDashboard(parent, self.db, ops=self.ops)
            return {"frame": obj, "obj": obj}
        
        if key == "calculator":
            frame = self._build_calculator_form(parent)
            return {"frame": frame, "obj": None}

        # Lazy imports for other modules
        view_map = {
            "dispatch_board": ("ui.views.dispatch_board_view", "DispatchBoardView", {"prefs": self.prefs, "ops": self.ops, "embedded": True}),
            "route_planner": ("ui.route_planner", "RoutePlannerTab", {"open_window": False, "controller": self}),
            "fleet": ("ui.fleet_tab", "FleetTab", {"open_window": False, "ops": self.ops}),
            "driver_manager": ("ui.driver_manager", "DriverManager", {"open_window": False, "ops": self.ops}),
            "invoices": ("ui.invoice_tab", "InvoiceTab", {"prefs": self.prefs}),
            "settings": ("ui.settings_view", "SettingsView", {"prefs": self.prefs, "ops": self.ops, "embedded": True}),
            "dashboard": ("ui.dashboard", "FleetDashboard", {"prefs": self.prefs, "ops": self.ops, "embedded": True}),
            "analytics": ("ui.analytics_view", "AnalyticsView", {"prefs": self.prefs, "embedded": True}),
            "history": ("ui.history_view", "HistoryView", {"controller": self, "prefs": self.prefs, "ops": self.ops, "embedded": True}),
            "route_history": ("ui.route_history_view", "RouteHistoryView", {"controller": self, "embedded": True}),
            "maintenance": ("ui.views.maintenance_analytics_view", "MaintenanceAnalyticsView", {"embedded": True}),
            "maintenance_control": ("ui.maintenance_control_panel", "MaintenanceControlPanel", {"prefs": self.prefs, "ops": self.ops, "embedded": True}),
            "tachograph": ("ui.views.tacho_import_view", "TachoImportView", {}),
            "tracking": ("ui.views.fleet_tracking_view", "FleetTrackingView", {
    "on_navigate": self._switch_module,
    "embedded": True
}),
        }

        if key in view_map:
            module_path, class_name, extra_args = view_map[key]
            import importlib
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)

            import inspect
            sig = inspect.signature(cls.__init__)
            valid_keys = {k for k in sig.parameters.keys() if k not in ("self", "parent", "db")}
            filtered = {k: v for k, v in extra_args.items() if k in valid_keys}
            obj = cls(parent, self.db, **filtered)

            frame = getattr(obj, "frame", obj)
            return {"frame": frame, "obj": obj}
        
        return {}

    def _fuel_status_text(self):
        if self._fuel_service.is_available():
            age = self._fuel_service.age_seconds()
            if age is not None and age < 3600:
                age_str = f"{int(age/60)}m" if age >= 60 else f"{int(age)}s"
            elif age is not None:
                age_str = f"{age/3600:.1f}h"
            else:
                age_str = "?"
            return f"⛽ {t('main.fuel_updated_at').format(self._fuel_service.last_updated_str())} ({t('main.fuel_age').format(age_str)})"
        return f"⛽ {t('main.fuel_offline')}"

    def _init_fuel_status(self):
        self._update_fuel_status()
        self._fuel_timer_id = self.root.after(60000, self._periodic_fuel_status)

    def _periodic_fuel_status(self):
        self._update_fuel_status()
        self._fuel_timer_id = self.root.after(60000, self._periodic_fuel_status)

    def shutdown(self):
        """Cancel all repeating after() callbacks and clean up."""
        if hasattr(self, "_fuel_timer_id") and self._fuel_timer_id:
            try:
                self.root.after_cancel(self._fuel_timer_id)
            except Exception:
                pass
            self._fuel_timer_id = None
        try:
            self.app_shell.destroy()
        except Exception:
            pass

    def _update_fuel_status(self):
        text = self._fuel_status_text()
        try:
            self._fuel_status_lbl.config(text=text)
        except Exception:
            pass

    def _open_settings(self):
        from ui.settings_view import SettingsView
        SettingsView(self.root, self.db, prefs=self.prefs, ops=self.ops)

    def _add_field(self, parent, label_key):
        lbl = ctk.CTkLabel(parent, text=t(label_key), fg_color=Theme.BG, text_color=Theme.TEXT, font=FONTS["label"])
        lbl.pack(anchor="w", pady=(8,0))
        self.i18n_tag(lbl, label_key)
        e = StyledEntry(parent)
        e.pack(fill="x", pady=2)
        if label_key == "main.client_label":
            self._route_badge = ctk.CTkLabel(parent, text="", fg_color=Theme.BG, text_color=Theme.ACCENT,
                                          font=FONTS["label"])
            self._route_badge.pack(anchor="w", pady=(2, 0))
        return e

    def _handle_calculate(self):
        try:
            km = float(self.route_distance or 0)
            price = float(self.e_price.get() or 0)
            if km <= 0 or price <= 0:
                messagebox.showwarning(t("main.warning_title"), t("main.fields_required"))
                return

            rates = self.api.get_rates()
            rate_eur = rates.get(self.c_val.get(), 1.0)
            pret_eur = price / rate_eur

            try:
                cons = float(self.selected_truck_fuel) if self.selected_truck_fuel is not None else 34.0
            except Exception:
                cons = 34.0

            selected_currency = self.c_val.get()
            fuel_price = self._fuel_service.get_price("DEFAULT", selected_currency)

            fuel_cost_from_route = None
            if hasattr(self, 'route_fuel_liters') and self.route_fuel_liters > 0:
                fuel_cost_from_route = self.route_fuel_liters * fuel_price

            res = self.calculator.calculate(
                km, pret_eur, fuel_price,
                int(self.e_days.get() or 1), cons,
                float(self.e_extra.get() or 0), float(self.e_sal.get() or 0), float(self.route_toll or 0),
                fuel_cost_from_route
            )

            try:
                dt_s = datetime.strptime(self.e_start.get(), "%d/%m/%Y")
            except Exception:
                dt_s = datetime.now()
            dt_end = dt_s + timedelta(days=int(self.e_days.get() or 1))
            dt_inc = dt_end + timedelta(days=int(self.e_term.get() or 0))

            color = Theme.ACCENT_SUCCESS if res.net_profit > 400 else (Theme.TEXT if res.net_profit > 0 else Theme.DANGER)
            summary = (
                f"💰 {t('main.net_profit').format(res.net_profit)}\n"
                f"📈 {t('main.gross_rate').format(res.gross_per_km, res.rate_per_km)}\n"
                f"📊 {t('main.margin').format(res.margin_percent, dt_inc.strftime('%d/%m/%Y'))}\n"
                f"{t('main.separator')}\n"
                f"⛽ {t('main.cost_breakdown').format(res.fuel_cost, res.toll_cost, res.salary_cost)}"
            )
            self.l_res.config(text=summary, fg=color)

            truck_plate = (self.selected_truck.get('plate_number') if isinstance(self.selected_truck, dict) and self.selected_truck else
                          (self.selected_truck[1] if self.selected_truck and len(self.selected_truck) > 1 else None))
            driver_id = (self.selected_truck.get('driver_id') if isinstance(self.selected_truck, dict) and self.selected_truck else None)

            from services.conflict_service import TripConflictService
            cfs = TripConflictService(self.db)
            conflicts = cfs.check_conflicts({
                "truck_plate": truck_plate or "",
                "driver_id": driver_id,
                "start_date": dt_s.strftime("%d/%m/%Y"),
                "end_date": dt_end.strftime("%d/%m/%Y"),
                "distance_km": km,
            })
            if conflicts:
                conflict_msgs = [cfs.describe_conflict(c) for c in conflicts]
                msg = t("dispatch_board.conflict_warning_title") + "\n\n" + "\n".join(conflict_msgs)
                if not messagebox.askyesno(t("dispatch_board.conflict_warning_title"), msg):
                    return

            self.db.add_trip({
                "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "truck_number": (self.selected_truck.get('plate_number') if isinstance(self.selected_truck, dict) and self.selected_truck else (self.selected_truck[1] if self.selected_truck and len(self.selected_truck) > 1 else None)),
                "driver_name": (self.selected_truck.get('driver_name') if isinstance(self.selected_truck, dict) and self.selected_truck and 'driver_name' in self.selected_truck else (self.selected_truck['driver_name'] if self.selected_truck and hasattr(self.selected_truck, 'keys') and 'driver_name' in self.selected_truck.keys() else None)),
                "client_name": self.e_client.get(),
                "distance_km": km,
                "total_price_eur": round(pret_eur, 2),
                "rate_per_km": res.rate_per_km,
                "gross_per_km": res.gross_per_km,
                "net_profit": res.net_profit,
                "start_date": dt_s.strftime("%d/%m/%Y"),
                "end_date": dt_end.strftime("%d/%m/%Y"),
                "payment_date": dt_inc.strftime("%d/%m/%Y"),
                "currency": self.c_val.get(),
                "status": "Planned",
                "fuel_cost": res.fuel_cost,
                "toll_cost": res.toll_cost,
                "salary_cost": res.salary_cost,
                "extra_costs": res.extra_costs,
                "route_history_v2_id": self._current_route_history_id,
                "truck_consumption_l_per_100km": self.selected_truck_fuel,
            })
            self._show_toast(f"✅ {t('main.save_success')}")

        except Exception as e:
            messagebox.showerror(t("main.error_title"), f"{t('main.check_data').format(str(e))}")

    def _show_toast(self, msg):
        t2 = tk.Toplevel(self.root)
        Theme.apply(t2)
        t2.overrideredirect(True)
        x = self.root.winfo_x() + 300; y = self.root.winfo_y() + 200
        t2.geometry(f"+{x}+{y}")
        tk.Label(t2, text=msg, bg=Theme.ACCENT_SUCCESS, fg=Theme.TEXT,
                 font=FONTS["small"], padx=25, pady=12).pack()
        self.root.after(2500, lambda: safe_destroy(t2))

    def _on_trip_update(self, tc, changed_fields):
        try:
            def apply_update():
                try:
                    if tc.route and tc.route.distance_km is not None:
                        self.route_distance = float(tc.route.distance_km)
                        try:
                            self._route_badge.config(
                                text=f"\U0001f5fa\ufe0f Route loaded: {tc.route.distance_km:,.0f} km"
                            )
                        except Exception:
                            pass

                    if tc.route and tc.route.route_history_v2_id is not None:
                        self._current_route_history_id = tc.route.route_history_v2_id

                    if tc.costs and tc.costs.toll_cost is not None:
                        self.route_toll = float(tc.costs.toll_cost)

                    if tc.costs and tc.costs.fuel_liters is not None:
                        self.route_fuel_liters = float(tc.costs.fuel_liters)
                        if tc.truck and tc.truck.fuel_consumption_l_per_100km is not None:
                            try:
                                self.selected_truck_fuel = float(tc.truck.fuel_consumption_l_per_100km)
                            except Exception:
                                logger.exception("_on_trip_update apply_inner failed")

                    if tc.profit and tc.profit.total_cost is not None:
                        self.e_price.delete(0, 'end')
                        self.e_price.insert(0, f"{tc.profit.total_cost:.2f}")

                    if tc.profit and tc.profit.net_profit is not None:
                        color = Theme.ACCENT_SUCCESS if tc.profit.net_profit > 400 else (Theme.TEXT if tc.profit.net_profit > 0 else Theme.DANGER)
                        summary = f"💰 PROFIT NET (TRIP): {tc.profit.net_profit:.2f}"
                        self.l_res.config(text=summary, fg=color)
                except Exception:
                    logger.exception("_on_trip_update apply_update failed")
            self.root.after(0, apply_update)
        except Exception:
            logger.exception("_on_trip_update failed")

    def _open_history(self):
        from ui.history_view import HistoryView
        HistoryView(self.root, self.db, self, prefs=self.prefs, ops=self.ops)

    def _open_dashboard(self):
        from ui.dashboard import FleetDashboard
        FleetDashboard(self.root, self.db, prefs=self.prefs, ops=self.ops)

    def _open_analytics(self):
        from ui.analytics_view import AnalyticsView
        AnalyticsView(self.root, self.db, prefs=self.prefs)

    def _open_invoices(self):
        from ui.invoice_tab import InvoiceTab
        win = ctk.CTkToplevel(self.root)
        win.title(t("invoice.section_company"))
        win.geometry("950x850")
        Theme.apply(win)
        win.configure(fg_color=Theme.BG)
        InvoiceTab(win, self.db, prefs=self.prefs).frame.pack(fill="both", expand=True)

    def get_timestamp(self):
        return datetime.now().strftime("%d/%m/%Y %H:%M")

    def destroy(self):
        try:
            self._event_bus.unsubscribe(SETTINGS_UPDATED, self._on_settings_updated)
        except Exception:
            pass
        try:
            unregister_trip_listener(self._on_trip_update)
        except Exception:
            pass
        try:
            unregister_listener(self._on_language_changed)
        except Exception:
            pass
        try:
            self.root.after_cancel(self._fuel_timer_id)
        except Exception:
            pass
