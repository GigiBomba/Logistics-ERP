import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from datetime import datetime, timedelta
import re
import os
from typing import Optional
from ui.widgets import StyledEntry, ActionButton, section_header
from ui.styles import Theme
from ui.fleet_tab import FleetTab
from ui.route_planner import RoutePlannerTab
from services.trip_context import register_trip_listener, unregister_trip_listener
from services.fleet_service import FleetService
from services.i18n import t, register_listener
from services.fuel_price_service import FuelPriceService


class MainWindow:
    def __init__(self, root, db, api, safety, prefs=None):
        self.root = root
        self.db = db
        self.api = api
        self.safety = safety
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self.fleet_service = FleetService(self.db)

        from services.calculator import TripCalculator
        self.calculator = TripCalculator()

        self.root.title(t("app.title"))
        self.root.geometry("800x950")
        Theme.apply(self.root)

        self._i18n_widgets: list = []  # (widget, "key", prefix) for refresh_translations()

        self._setup_ui()
        try:
            register_trip_listener(self._on_trip_update)
        except Exception:
            pass

        self.root.bind("<Control-s>", lambda e: self._handle_calculate())
        self.root.bind("<Control-h>", lambda e: self._open_history())

        register_listener(self._on_language_changed)

        self._fuel_service = FuelPriceService()
        self._fuel_service.refresh(background=True)
        self._init_fuel_status()

    def _i18n_tag(self, widget, key, prefix=""):
        """Register a widget whose text should be refreshed on language change."""
        self._i18n_widgets.append((widget, key, prefix))

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        self.root.title(t("app.title"))
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        currencies = t("main.currencies")
        if isinstance(currencies, str):
            currencies = ["EUR", "RON", "USD", "GBP"]
        try:
            self.c_val.configure(values=currencies)
        except Exception:
            pass
        self._update_fuel_status()
        # Update combobox with translated currency options
        currencies = t("main.currencies")
        if isinstance(currencies, str):
            currencies = ["EUR", "RON", "USD", "GBP"]
        try:
            self.c_val.configure(values=currencies)
        except Exception:
            pass

    def _open_fleet(self):
        from ui.fleet_tab import FleetTab
        FleetTab(self.root, self.db)

    def _load_trucks_main(self):
        try:
            rows = self.fleet_service.get_trucks()
            menu = self.truck_dropdown['menu']
            menu.delete(0, 'end')
            self._main_trucks_map = {}
            for r in rows:
                tid = str(r[0])
                label = f"{r[1]} - {r[2] or ''}"
                menu.add_command(label=label, command=lambda v=tid: self._on_main_truck_selected(v))
                try:
                    row_dict = {k: r[k] for k in r.keys()}
                except Exception:
                    row_dict = {'id': r[0], 'plate_number': r[1], 'model': r[2], 'fuel_consumption': r[7] if len(r) > 7 else None}
                self._main_trucks_map[tid] = row_dict
            if rows:
                first = str(rows[0][0])
                self.truck_var.set(first)
                self._on_main_truck_selected(first)
        except Exception:
            pass

    def _on_main_truck_selected(self, truck_id):
        try:
            t = self._main_trucks_map.get(str(truck_id))
            self.selected_truck = t
            try:
                self.selected_truck_fuel = float(t.get('fuel_consumption') or t.get('fuel_consumption_l_per_100km') or 34.0)
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

    def _setup_ui(self):
        self.nav_frame = tk.Frame(self.root, bg=Theme.SURFACE, pady=12)
        self.nav_frame.pack(fill="x")
        self._nav_buttons = []
        self._build_nav(self.nav_frame)

        self.canvas = tk.Canvas(self.root, bg=Theme.BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=Theme.BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=760)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        ident_f = tk.Frame(self.scrollable_frame, bg=Theme.BG, padx=40, pady=10)
        ident_f.pack(fill="x")
        lbl = section_header(ident_f, t("main.section_identify"), _return=True)
        self._i18n_tag(lbl, "main.section_identify")
        lbl = tk.Label(ident_f, text=t("main.truck_label"), bg=Theme.BG, fg=Theme.TEXT, font=("Segoe UI", 9))
        lbl.pack(anchor="w", pady=(8,0))
        self._i18n_tag(lbl, "main.truck_label")
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

        fin_f = tk.Frame(self.scrollable_frame, bg=Theme.BG, padx=40, pady=10)
        fin_f.pack(fill="x")
        lbl = section_header(fin_f, t("main.section_finance"), _return=True)
        self._i18n_tag(lbl, "main.section_finance")
        self.e_price = self._add_field(fin_f, "main.offer_price")

        lbl = tk.Label(fin_f, text=t("main.currency_label"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w", pady=(8,0))
        self._i18n_tag(lbl, "main.currency_label")
        currencies = t("main.currencies")
        if isinstance(currencies, str):
            currencies = ["EUR", "RON", "USD", "GBP"]
        self.c_val = ttk.Combobox(fin_f, values=currencies, state="readonly")
        self.c_val.current(0)
        self.c_val.pack(fill="x", pady=5)

        cost_f = tk.Frame(self.scrollable_frame, bg=Theme.BG, padx=40, pady=10)
        cost_f.pack(fill="x")
        lbl = section_header(cost_f, t("main.section_costs"), _return=True)
        self._i18n_tag(lbl, "main.section_costs")
        self.e_sal = self._add_field(cost_f, "main.salary_label"); self.e_sal.insert(0, "0")
        self.e_tax = None
        self.e_extra = self._add_field(cost_f, "main.extra_costs_label"); self.e_extra.insert(0, "0")

        time_f = tk.Frame(self.scrollable_frame, bg=Theme.BG, padx=40, pady=10)
        time_f.pack(fill="x")
        lbl = section_header(time_f, t("main.section_planning"), _return=True)
        self._i18n_tag(lbl, "main.section_planning")
        self.e_start = self._add_field(time_f, "main.start_date_label")
        self.e_start.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.e_days = self._add_field(time_f, "main.duration_label"); self.e_days.insert(0, "1")
        self.e_term = self._add_field(time_f, "main.payment_term_label"); self.e_term.insert(0, "30")

        btn_f = tk.Frame(self.scrollable_frame, bg=Theme.BG, padx=40, pady=30)
        btn_f.pack(fill="x")
        self._calc_btn = ActionButton(btn_f, t("main.calculate_button"), self._handle_calculate,
                     color=Theme.ACCENT_SUCCESS)
        self._calc_btn.pack(fill="x")
        self._i18n_tag(self._calc_btn, "main.calculate_button")

        self.res_box = tk.Frame(self.scrollable_frame, bg=Theme.SURFACE, padx=25, pady=25)
        self.res_box.pack(fill="x", padx=40, pady=(0, 50))
        self.l_res = tk.Label(self.res_box, text=t("main.placeholder_info"),
                               bg=Theme.SURFACE, fg=Theme.MUTED, font=("Segoe UI", 11, "bold"),
                               justify="center", wraplength=650)
        self.l_res.pack()

        self._fuel_status_lbl = tk.Label(self.scrollable_frame, text="",
                                          bg=Theme.BG, fg=Theme.MUTED, font=("Segoe UI", 8))
        self._fuel_status_lbl.pack(anchor="se", padx=10, pady=(0, 5))

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
        self.root.after(60000, self._periodic_fuel_status)

    def _periodic_fuel_status(self):
        self._update_fuel_status()
        self.root.after(60000, self._periodic_fuel_status)

    def _update_fuel_status(self):
        text = self._fuel_status_text()
        try:
            self._fuel_status_lbl.config(text=text)
        except Exception:
            pass

    def _build_nav(self, nav):
        lbl = tk.Label(nav, text=f"🚛 {t('app.name')}", font=("Segoe UI", 12, "bold"),
                 bg=Theme.SURFACE, fg=Theme.TEXT)
        lbl.pack(side="left", padx=25)
        self._i18n_tag(lbl, "app.name", "🚛 ")

        nav_items = [
            ("🛡️", "nav.safety", self._open_safety_menu, Theme.SURFACE2),
            ("📈", "nav.analytics", self._open_analytics, Theme.GREEN),
            ("🧾", "nav.invoices", self._open_invoices, Theme.ACCENT),
            ("📊", "nav.dashboard", self._open_dashboard, Theme.SURFACE2),
            ("📋", "nav.history", self._open_history, Theme.SURFACE2),
            ("⚙️", "nav.settings", self._open_settings, Theme.SURFACE2),
            ("🗂️", "nav.route_history", self._open_route_history, Theme.SURFACE2),
            ("📍", "nav.routes", self._open_route_planner, Theme.ACCENT),
            ("🚛", "nav.fleet", self._open_fleet, Theme.INFO),
        ]
        for emoji, key, cmd, color in reversed(nav_items):
            btn = ActionButton(nav, f"{emoji} {t(key)}", cmd, color=color)
            btn.pack(side="right", padx=5)
            self._nav_buttons.append(btn)
            self._i18n_tag(btn, key, f"{emoji} ")

    def _open_settings(self):
        from ui.settings_view import SettingsView
        SettingsView(self.root, self.db, prefs=self.prefs)

    def _add_field(self, parent, label_key):
        lbl = tk.Label(parent, text=t(label_key), bg=Theme.BG, fg=Theme.TEXT, font=("Segoe UI", 9))
        lbl.pack(anchor="w", pady=(8,0))
        self._i18n_tag(lbl, label_key)
        e = StyledEntry(parent)
        e.pack(fill="x", pady=2)
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
            except:
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
                 font=("Segoe UI", 10, "bold"), padx=25, pady=12).pack()
        self.root.after(2500, t2.destroy)

    def _on_trip_update(self, tc, changed_fields):
        try:
            def apply_update():
                try:
                    if tc.route and tc.route.distance_km is not None:
                        self.route_distance = float(tc.route.distance_km)

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
                                pass

                    if tc.profit and tc.profit.total_cost is not None:
                        self.e_price.delete(0, 'end')
                        self.e_price.insert(0, f"{tc.profit.total_cost:.2f}")

                    if tc.profit and tc.profit.net_profit is not None:
                        color = Theme.ACCENT_SUCCESS if tc.profit.net_profit > 400 else (Theme.TEXT if tc.profit.net_profit > 0 else Theme.DANGER)
                        summary = f"💰 PROFIT NET (TRIP): {tc.profit.net_profit:.2f}"
                        self.l_res.config(text=summary, fg=color)
                except Exception:
                    pass
            self.root.after(0, apply_update)
        except Exception:
            pass

    def _open_history(self):
        from ui.history_view import HistoryView
        HistoryView(self.root, self.db, self, prefs=self.prefs)

    def _open_dashboard(self):
        from ui.dashboard import DashboardView
        DashboardView(self.root, self.db, prefs=self.prefs)

    def _open_analytics(self):
        from ui.analytics_view import AnalyticsView
        AnalyticsView(self.root, self.db, prefs=self.prefs)

    def _open_invoices(self):
        from ui.invoice_tab import InvoiceTab
        win = tk.Toplevel(self.root)
        win.title(t("invoice.section_company"))
        win.geometry("950x850")
        Theme.apply(win)
        InvoiceTab(win, self.db, prefs=self.prefs).frame.pack(fill="both", expand=True)

    def _open_safety_menu(self):
        win = tk.Toplevel(self.root)
        win.title(f"🛡️ {t('safety.title')}")
        win.geometry("450x400")
        Theme.apply(win)
        win.configure(padx=40, pady=40)

        tk.Label(win, text=f"🛡️ {t('safety.management')}", font=("Segoe UI", 13, "bold"), bg=Theme.BG, fg=Theme.ACCENT).pack(pady=(0, 25))

        def handle_exp():
            path = self.safety.export_to_json(self.db.get_all_trips())
            messagebox.showinfo(t("main.save_success"), t("safety.export_success").format(path))

        def handle_imp():
            f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
            if f and messagebox.askyesno(t("safety.import_confirm").split("?")[0] if "?" in t("safety.import_confirm") else t("main.warning_title"), t("safety.import_confirm")):
                count = self.safety.import_from_json(f, self.db)
                messagebox.showinfo(t("main.save_success"), t("safety.import_success").format(count))

        ActionButton(win, f"📤 {t('safety.export_button')}", handle_exp, color=Theme.ACCENT).pack(fill="x", pady=10)
        ActionButton(win, f"📥 {t('safety.import_button')}", handle_imp, color=Theme.SURFACE2).pack(fill="x", pady=10)

        tk.Label(win, text=t("safety.backup_info"),
                 bg=Theme.BG, fg=Theme.MUTED, font=("Segoe UI", 8), justify="center").pack(pady=30)

    def get_timestamp(self):
        return datetime.now().strftime("%d/%m/%Y %H:%M")

    def destroy(self):
        try:
            unregister_trip_listener(self._on_trip_update)
        except Exception:
            pass
