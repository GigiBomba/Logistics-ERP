import csv
import logging
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from services.i18n import t, register_listener, unregister_listener
from services.operations.event_bus import EventBus, TRUCK_UPDATED
from services.driver_truck_service import DriverTruckService
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry, section_header, kpi_card
from services.fleet_service import FleetService
from services.export_service import ExportService
from database.db_manager import DatabaseManager
from ui.dialogs.truck_form import TruckFormDialog
from ui.theme import CHART_PRIMARY, CHART_SECONDARY, CHART_INDIGO, FONTS, apply_chart_style

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except Exception:
    HAS_MPL = False


from ui.i18n_mixin import I18nMixin

class FleetTab(I18nMixin):
    STATUS_KEYS = {
        "Active": "fleet.status_active",
        "Inactive": "fleet.status_inactive",
    }

    def __init__(self, parent, db_or_path, open_window=True, ops=None):
        I18nMixin.__init__(self)
        self.parent = parent
        if isinstance(db_or_path, DatabaseManager):
            self.db = db_or_path
        else:
            self.db = DatabaseManager(db_or_path)
        self.ops = ops
        self.service = FleetService(self.db)                                
        self.exporter = ExportService()
        self._event_bus = EventBus()
        self._dta_service = DriverTruckService(self.db)
        self._i18n_widgets = []
        self._tree_heading_keys = []
        self._kpi_title_refs = []
        self._expenses_tree = None
        self._expenses_tree_heading_keys = []
        if open_window:
            self.win = ctk.CTkToplevel(parent)
            self.win.configure(fg_color=Theme.BG)
            self.win.title(t("fleet.title"))
            self.win.geometry("1100x700")
            Theme.apply(self.win)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)

        self._setup_ui()

        self.refresh_fleet()

        self.frame.bind("<Destroy>", self._on_destroy)
        self._event_bus.subscribe(TRUCK_UPDATED, self._on_truck_updated_ev)

    def _on_truck_updated_ev(self, ev):
        try:
            self.frame.after(0, self.refresh_fleet)
        except Exception:
            pass

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.frame:
            return
        self._event_bus.unsubscribe(TRUCK_UPDATED, self._on_truck_updated_ev)
        self.i18n_cleanup()

    def refresh_translations(self):
        if self.win is not None:
            self.win.title(t("fleet.title"))
        for col, key in self._tree_heading_keys:
            try:
                self.tree.heading(col, text=t(key))
            except Exception:
                pass
        if self._expenses_tree is not None:
            for col, key in self._expenses_tree_heading_keys:
                try:
                    self._expenses_tree.heading(col, text=t(key))
                except Exception:
                    pass
        for key in self._kpi_title_refs:
            try:
                lbl, k = key
                lbl.config(text=t(k))
            except Exception:
                pass
        self.refresh_fleet()

    def _setup_ui(self):
        header = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        header.pack(fill="x", padx=12, pady=(8, 4))
        lbl = ctk.CTkLabel(header, text=t("fleet.title"), fg_color=Theme.BG, text_color=Theme.ACCENT, font=Theme.FONT_TITLE)
        lbl.pack(side="left")
        self.i18n_tag(lbl, "fleet.title")
        ex_f = ctk.CTkFrame(header, fg_color=Theme.BG)
        ex_f.pack(side="right")
        btn = ActionButton(ex_f, t("fleet.export_csv"), self._export_csv, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self.i18n_tag(btn, "fleet.export_csv")
        btn = ActionButton(ex_f, t("fleet.export_excel"), self._export_excel, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self.i18n_tag(btn, "fleet.export_excel")
        btn = ActionButton(ex_f, t("fleet.export_pdf"), self._export_pdf, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self.i18n_tag(btn, "fleet.export_pdf")

        kpi_cont = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        kpi_cont.pack(fill="x", padx=12)
        kpi_total_val, kpi_total_title = kpi_card(kpi_cont, t("fleet.kpi_total_trucks"), "0")
        self.kpi_total = kpi_total_val
        self._kpi_title_refs.append((kpi_total_title, "fleet.kpi_total_trucks"))
        kpi_active_val, kpi_active_title = kpi_card(kpi_cont, t("fleet.kpi_active"), "0")
        self.kpi_active = kpi_active_val
        self._kpi_title_refs.append((kpi_active_title, "fleet.kpi_active"))
        kpi_lease_val, kpi_lease_title = kpi_card(kpi_cont, t("fleet.kpi_monthly_rate"), "0")
        self.kpi_leasing = kpi_lease_val
        self._kpi_title_refs.append((kpi_lease_title, "fleet.kpi_monthly_rate"))

        kpi_alert_val, kpi_alert_title = kpi_card(kpi_cont, t("fleet.kpi_alerts"), "0")
        self.kpi_alerts = kpi_alert_val
        self._kpi_title_refs.append((kpi_alert_title, "fleet.kpi_alerts"))

        # KPIs section complete — maintenance KPIs are in the dedicated MaintenanceView

        main = tk.PanedWindow(self.frame, orient="horizontal", sashrelief="raised", bg=Theme.BG)
        main.pack(fill="both", expand=True, padx=12, pady=8)

        left = ctk.CTkFrame(main, fg_color=Theme.BG)
        right = ctk.CTkFrame(main, fg_color=Theme.BG, width=360)
        main.add(left, minsize=700)
        main.add(right, minsize=320)

        search_f = ctk.CTkFrame(left, fg_color=Theme.BG)
        search_f.pack(fill="x", padx=6, pady=(0, 6))
        lbl = ctk.CTkLabel(search_f, text=t("fleet.search_label"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(side="left")
        self.i18n_tag(lbl, "fleet.search_label")
        self.e_search = StyledEntry(search_f)
        self.e_search.pack(side="left", fill="x", expand=True, padx=(8, 6))
        self.e_search.bind("<KeyRelease>", lambda e: self._filter_tree())
        btn = ActionButton(search_f, t("fleet.reset_button"), lambda: (self.e_search.delete(0, "end"), self._filter_tree()), color=Theme.SURFACE2)
        btn.pack(side="left")
        self.i18n_tag(btn, "fleet.reset_button")

        plate_f = ctk.CTkFrame(search_f, fg_color=Theme.BG)
        plate_f.pack(side="right")
        lbl = ctk.CTkLabel(plate_f, text=t("fleet.plate_label"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(side="left", padx=(6,4))
        self.i18n_tag(lbl, "fleet.plate_label")
        self.e_plate_search = StyledEntry(plate_f, width=12)
        self.e_plate_search.pack(side="left", padx=(0,6))
        btn = ActionButton(plate_f, t("fleet.find_button"), lambda: self._find_plate(), color=Theme.SURFACE2, width=8)
        btn.pack(side="left")
        self.i18n_tag(btn, "fleet.find_button")

        table_f = ctk.CTkFrame(left, fg_color=Theme.BG)
        table_f.pack(fill="both", expand=True)
        cols = ("id", "plate", "model", "manufacturer", "year", "vin", "mileage", "fuel", "monthly_rate", "status", "active", "driver")
        headers = (
            t("fleet.table_id"), t("fleet.table_plate"), t("fleet.table_model"), t("fleet.table_manufacturer"),
            t("fleet.table_year"), t("fleet.table_vin"), t("fleet.table_km"), t("fleet.table_consumption"),
            t("fleet.table_rate"), t("fleet.table_status"), t("fleet.table_active"), t("fleet.table_driver")
        )
        heading_keys = (
            "fleet.table_id", "fleet.table_plate", "fleet.table_model", "fleet.table_manufacturer",
            "fleet.table_year", "fleet.table_vin", "fleet.table_km", "fleet.table_consumption",
            "fleet.table_rate", "fleet.table_status", "fleet.table_active", "fleet.table_driver"
        )
        self.tree = ttk.Treeview(table_f, columns=cols, show="headings")
        for c, h, k in zip(cols, headers, heading_keys):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=100 if c not in ("model", "manufacturer") else 150, anchor="center")
            self._tree_heading_keys.append((c, k))
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(table_f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(table_f, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")

        for c in cols:
            self.tree.column(c, stretch=True)

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        self.tree.bind('<FocusIn>', lambda e: self.tree.focus_set())

        btns = ctk.CTkFrame(left, fg_color=Theme.BG)
        btns.pack(fill="x")
        btn = ActionButton(btns, f"➕ {t('fleet.add_truck')}", self._add_truck_win, color=Theme.ACCENT_SUCCESS)
        btn.pack(side="left", padx=6)
        self.i18n_tag(btn, "fleet.add_truck", "➕ ")
        btn = ActionButton(btns, f"✏️ {t('fleet.edit_button')}", self._edit_truck_selected, color=Theme.ACCENT)
        btn.pack(side="left", padx=6)
        self.i18n_tag(btn, "fleet.edit_button", "✏️ ")
        btn = ActionButton(btns, f"🗑️ {t('fleet.delete_button')}", self._delete_truck, color=Theme.DANGER)
        btn.pack(side="right", padx=6)
        self.i18n_tag(btn, "fleet.delete_button", "🗑️ ")
        btn = ActionButton(btns, f"\U0001F4C2 {t('fleet.documents_button')}", self._open_truck_documents, color=Theme.ACCENT)
        btn.pack(side="right", padx=6)
        self.i18n_tag(btn, "fleet.documents_button", "\U0001F4C2 ")

        # ── Alerts panel from OperationsEngine ──
        self.alerts_frame = ctk.CTkFrame(right, fg_color=Theme.BG)
        section_header(self.alerts_frame, t("fleet.section_alerts"))
        self.alerts_container = ctk.CTkFrame(self.alerts_frame, fg_color=Theme.BG)
        self.alerts_container.pack(fill="both", expand=True, padx=4, pady=2)
        self.alerts_frame.pack(fill="both", padx=8, pady=(4,0), expand=True)

        lbl = section_header(right, t("fleet.section_charts"), _return=True)
        self.i18n_tag(lbl, "fleet.section_charts")
        self.chart_area = ctk.CTkFrame(right, fg_color=Theme.BG)
        self.chart_area.pack(fill="both", padx=8, pady=6, expand=False)
        if HAS_MPL:
            self.fig = Figure(figsize=(4, 2), dpi=100)
            self.ax = self.fig.add_subplot(111)
            apply_chart_style(self.fig, self.ax)
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_area)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            self.chart_canvas = tk.Canvas(self.chart_area, bg=Theme.SURFACE2, height=160, bd=0, highlightthickness=0)
            self.chart_canvas.pack(fill="x", expand=True)

        lbl = section_header(right, t("fleet.section_quick_add"), _return=True)
        self.i18n_tag(lbl, "fleet.section_quick_add")
        quick_f = ctk.CTkFrame(right, fg_color=Theme.BG)
        quick_f.pack(fill="x", padx=8, pady=6)
        lbl = ctk.CTkLabel(quick_f, text=t("fleet.plate_quick"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(anchor="w")
        self.i18n_tag(lbl, "fleet.plate_quick")
        self.q_plate = StyledEntry(quick_f); self.q_plate.pack(fill="x", pady=4)
        lbl = ctk.CTkLabel(quick_f, text=t("fleet.model_quick"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(anchor="w")
        self.i18n_tag(lbl, "fleet.model_quick")
        self.q_model = StyledEntry(quick_f); self.q_model.pack(fill="x", pady=4)
        lbl = ctk.CTkLabel(quick_f, text=t("fleet.rate_quick"), fg_color=Theme.BG, text_color=Theme.TEXT)
        lbl.pack(anchor="w")
        self.i18n_tag(lbl, "fleet.rate_quick")
        self.q_rate = StyledEntry(quick_f); self.q_rate.insert(0, "0"); self.q_rate.pack(fill="x", pady=4)
        btn = ActionButton(quick_f, t("fleet.save_quick"), self._save_quick, color=Theme.ACCENT_SUCCESS)
        btn.pack(fill="x", pady=6)
        self.i18n_tag(btn, "fleet.save_quick")

    def _build_maintenance_kpi_strip(self, parent, truck_id, truck_row):
        from repositories.fleet_repository import FleetRepository
        repo = FleetRepository(self.db)

        section_lbl = ctk.CTkLabel(parent, text=t("fleet.maint_kpi_title"), fg_color=Theme.BG, text_color=Theme.ACCENT, font=Theme.FONT_BOLD)
        section_lbl.pack(anchor="nw", pady=(12, 4))

        kpi_frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
        kpi_frame.pack(fill="x", pady=(0, 8))

        # Odometer display
        odometer_km = truck_row.get("mileage", 0) or 0
        odometer_str = f"{odometer_km:,.0f} {t('fleet.unit_km')}"
        self._maint_kpi_card(kpi_frame, t("fleet.maint_kpi_odometer"), odometer_str, Theme.ACCENT)

        last_service = repo.get_maintenance_last_date(truck_id)
        self._maint_kpi_card(kpi_frame, t("fleet.maint_kpi_last_service"), last_service or "—", Theme.SUCCESS)

        schedules = repo.get_maintenance_schedules(truck_id)
        next_due = None
        for sched in schedules:
            fixed_date = sched.get("fixed_expiry_date")
            if fixed_date:
                try:
                    sched_dt = datetime.strptime(fixed_date, "%Y-%m-%d")
                    if next_due is None or sched_dt < next_due:
                        next_due = sched_dt
                except Exception:
                    pass
        next_due_str = next_due.strftime("%d/%m/%Y") if next_due else "—"
        self._maint_kpi_card(kpi_frame, t("fleet.maint_kpi_next_due"), next_due_str, Theme.WARNING)

        month_start = datetime.now().strftime("%Y-%m-01")
        cost_month = repo.sum_maintenance_cost(since_date=month_start)
        self._maint_kpi_card(kpi_frame, t("fleet.maint_kpi_cost_month"), f"{cost_month:.0f}", Theme.INFO)

        alert_count = 0
        if self.ops:
            try:
                alerts = self.ops.get_alerts(truck_id=str(truck_id), resolved=False, limit=100)
                alert_count = len(alerts)
            except Exception:
                pass
        alert_card = self._maint_kpi_card(kpi_frame, t("fleet.maint_kpi_alerts"), str(alert_count), Theme.DANGER)
        if alert_count > 0:
            alert_card.bind("<Button-1>", lambda e: self._jump_to_alerts(truck_id))
            alert_card.configure(cursor="hand2")
            for child in alert_card.winfo_children():
                child.bind("<Button-1>", lambda e: self._jump_to_alerts(truck_id))
                child.configure(cursor="hand2")

        tacho_expiry = truck_row.get("tachograph_expiry") or ""
        tacho_color = Theme.MUTED
        tacho_display = "—"
        if tacho_expiry:
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    tacho_dt = datetime.strptime(tacho_expiry, fmt)
                    days_left = (tacho_dt - datetime.now()).days
                    tacho_display = tacho_dt.strftime("%d/%m/%Y")
                    if days_left <= 7:
                        tacho_color = Theme.DANGER
                    elif days_left <= 30:
                        tacho_color = Theme.WARNING
                    else:
                        tacho_color = Theme.SUCCESS
                    break
                except Exception:
                    continue
            else:
                tacho_color = Theme.DANGER
                tacho_display = tacho_expiry
        self._maint_kpi_card(kpi_frame, t("fleet.maint_kpi_tacho"), tacho_display, tacho_color)

    def _maint_kpi_card(self, parent, title, value, accent_color):
        card = ctk.CTkFrame(parent, fg_color=Theme.SURFACE, border_width=1, border_color=accent_color)
        card.pack(side="left", padx=3, pady=2, fill="x", expand=True)
        title_lbl = ctk.CTkLabel(card, text=title.upper(), fg_color=Theme.SURFACE, text_color=Theme.MUTED, font=FONTS["label"])
        title_lbl.pack(anchor="w")
        val_lbl = ctk.CTkLabel(card, text=str(value), fg_color=Theme.SURFACE, text_color=accent_color, font=FONTS["small"])
        val_lbl.pack(anchor="w")
        return card

    def _jump_to_alerts(self, truck_id):
        row = self.service.get_truck(truck_id)
        if row:
            self._open_maintenance_view(truck_id, row["plate_number"])

    def refresh_fleet(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            rows = self.service.get_trucks()

            for r in rows:
                driver_name = self._dta_service.get_driver_name_for_truck(r["id"]) or t("fleet.table_driver_unassigned")
                self.tree.insert("", "end", values=(
                    r["id"],
                    r["plate_number"],
                    r["model"] or "",
                    r["manufacturer"] or "",
                    r["year"] or "",
                    r["vin"] or "",
                    f"{(r['mileage'] or 0):,}",
                    f"{(r['fuel_consumption'] or 0):.1f}" if r.get("fuel_consumption") is not None else "",
                    f"{(r['monthly_rate'] or 0):.2f}",
                    r["status"] or "",
                    t("common.yes") if (r["active_status"] == 1 or r["active_status"] == True) else t("common.no"),
                    driver_name,
                ))

            total = len(rows)
            active = sum(1 for r in rows if r["active_status"] == 1 or r["active_status"] == True)

            self.kpi_total.config(text=str(total))
            self.kpi_active.config(text=str(active))
            self.kpi_leasing.config(text="")

            # Alerts KPI from OperationsEngine
            if self.ops:
                self.kpi_alerts.config(text=str(self.ops.get_active_alert_count()))
                self._refresh_alerts()
            else:
                self.kpi_alerts.config(text="N/A")

            self._draw_charts(rows)
            self._filter_tree()
        except Exception as ex:
            logger.exception("refresh_fleet failed")
            messagebox.showerror(t("main.error_title"), t("fleet.error_load").format(ex))

    def _draw_charts(self, rows):
        statuses = {}
        rates = []
        for r in rows:
            st_raw = r.get("status") or ""
            key = self.STATUS_KEYS.get(st_raw.title() if st_raw else "")
            st = t(key) if key else (st_raw or t("fleet.status_unknown"))
            statuses[st] = statuses.get(st, 0) + 1
            rates.append(float(r.get("monthly_rate") or 0))

        labels = list(statuses.keys())
        counts = list(statuses.values())

        if HAS_MPL:
            self.ax.clear()
            if counts:
                self.ax.pie(counts, labels=labels, autopct="%1.0f%%", colors=[CHART_PRIMARY, CHART_INDIGO, CHART_SECONDARY])
            else:
                self.ax.text(0.5, 0.5, t("fleet.no_data_chart"), ha="center")
            self.fig.tight_layout()
            try:
                self.canvas.draw()
            except Exception:
                pass
        else:
            self.chart_canvas.delete("all")
            w = self.chart_canvas.winfo_width() or 300
            h = 140
            if not counts:
                self.chart_canvas.create_text(10, 10, anchor="nw", text=t("fleet.no_data_chart"), fill=Theme.MUTED)
                return
            max_c = max(counts) or 1
            bar_h = 18
            y = 8
            for label, cnt in zip(labels, counts):
                bar_w = int((w - 120) * (cnt / max_c))
                self.chart_canvas.create_rectangle(10, y, 10 + bar_w, y + bar_h, fill=Theme.ACCENT, outline="")
                self.chart_canvas.create_text(15 + bar_w, y + bar_h / 2, anchor="w", text=f"{label}: {cnt}", fill=Theme.TEXT)
                y += bar_h + 8

    def _refresh_alerts(self):
        for w in self.alerts_container.winfo_children():
            w.destroy()
        if not self.ops:
            ctk.CTkLabel(self.alerts_container, text=t("fleet.no_engine"), fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["label"]).pack()
            return
        alerts = self.ops.get_active_alerts(limit=20)
        if not alerts:
            ctk.CTkLabel(self.alerts_container, text=t("fleet.no_alerts"), fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["label"]).pack(pady=10)
            return
        c = tk.Canvas(self.alerts_container, bg=Theme.BG, highlightthickness=0)
        sb = ttk.Scrollbar(self.alerts_container, orient="vertical", command=c.yview)
        inner = ctk.CTkFrame(c, fg_color=Theme.BG)
        inner.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0, 0), window=inner, anchor="nw", width=300)
        c.configure(yscrollcommand=sb.set)
        c.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for a in alerts:
            sev_color = Theme.DANGER if a.severity.value == 'critical' else (Theme.WARNING if a.severity.value == 'warning' else Theme.INFO)
            card = ctk.CTkFrame(inner, fg_color=Theme.SURFACE2, border_width=1, border_color=sev_color)
            card.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(card, text=a.title, fg_color=Theme.SURFACE2, text_color=Theme.TEXT, font=FONTS["label"], wraplength=280, justify="left").pack()
            ctk.CTkLabel(card, text=a.message, fg_color=Theme.SURFACE2, text_color=Theme.MUTED, font=FONTS["label"], wraplength=280, justify="left").pack()

    def _filter_tree(self):
        query = self.e_search.get().strip().lower()
        for iid in self.tree.get_children():
            vals = [str(v).lower() for v in self.tree.item(iid)["values"]]
            visible = (query == "") or any(query in v for v in vals)
            if visible:
                try:
                    self.tree.reattach(iid, "", "end")
                except Exception:
                    pass
            else:
                try:
                    self.tree.detach(iid)
                except Exception:
                    pass

    def _find_plate(self):
        plate = (self.e_plate_search.get() or "").strip().upper()
        if not plate:
            messagebox.showinfo(t("fleet.search_info_title"), t("fleet.search_info_msg"))
            return
        for iid in self.tree.get_children():
            vals = self.tree.item(iid)["values"]
            if len(vals) > 1 and str(vals[1]).upper() == plate:
                try:
                    self.tree.reattach(iid, "", "end")
                except Exception:
                    pass
                self.tree.selection_set(iid)
                self.tree.see(iid)
                return
        messagebox.showinfo(t("fleet.search_info_title"), t("fleet.search_not_found").format(plate))

    def _on_tree_double_click(self, event):
        self._open_selected_truck_detail()

    def _get_selected_truck_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(t("fleet.select_first"), t("fleet.select_first"))
            return None
        return self.tree.item(sel[0])["values"][0]

    # CRUD operations
    def _add_truck_win(self):
        TruckFormDialog(self.frame, self.service, title=t("fleet.truck_form_title"),
                        on_save=self.refresh_fleet, dta_service=self._dta_service)

    def _edit_truck_selected(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            return
        row = self.service.get_truck(truck_id)
        if not row:
            messagebox.showerror(t("fleet.truck_not_found"), t("fleet.truck_not_found"))
            return
        TruckFormDialog(self.frame, self.service, title=t("fleet.edit_button"),
                        truck=row, on_save=self.refresh_fleet, dta_service=self._dta_service)

    def _save_quick(self):
        plate = self.q_plate.get().strip().upper()
        if not plate:
            messagebox.showwarning(t("fleet.validation_plate_required"), t("fleet.validation_plate_required"))
            return
        try:
            rate = float(self.q_rate.get() or 0)
        except ValueError:
            messagebox.showwarning(t("fleet.validation_rate_invalid"), t("fleet.validation_rate_invalid"))
            return
        try:
            self.service.add_truck({
                "plate_number": plate,
                "model": self.q_model.get().strip(),
                "monthly_rate": rate,
                "mileage": 0,
                "status": "Active",
                "active_status": 1
            })
            self.q_plate.delete(0, "end")
            self.q_model.delete(0, "end")
            self.q_rate.delete(0, "end")
            self.q_rate.insert(0, "0")
            self.refresh_fleet()
            messagebox.showinfo(t("fleet.success_added"), t("fleet.success_added"))
        except Exception as ex:
            messagebox.showerror(t("fleet.error_save").format(""), t("fleet.error_save").format(ex))

    def _delete_truck(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            return
        if not messagebox.askyesno(t("fleet.delete_button"), t("fleet.confirm_delete")):
            return
        try:
            self.service.delete_truck(truck_id)
            self.refresh_fleet()
        except Exception as ex:
            messagebox.showerror(t("fleet.error_delete").format(""), t("fleet.error_delete").format(ex))

    def _open_selected_truck_detail(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            return
        self._open_truck_detail(truck_id)

    def _open_truck_detail(self, truck_id):
        row = self.service.get_truck(truck_id)
        if not row:
            messagebox.showerror(t("fleet.truck_not_found"), t("fleet.truck_not_found"))
            return

        win = ctk.CTkToplevel(self.frame)
        win.title(t("fleet.truck_detail_title").format(row["plate_number"]))
        win.geometry("900x650")
        Theme.apply(win)

        left = ctk.CTkFrame(win, fg_color=Theme.BG, width=320)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ctk.CTkFrame(win, fg_color=Theme.BG)
        right.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(left, text=f"{row['plate_number']} - {row['model']}", fg_color=Theme.BG, text_color=Theme.ACCENT, font=Theme.FONT_BOLD).pack(anchor="nw")
        ctk.CTkLabel(left, text=f"{t('fleet.detail_manufacturer')} {row['manufacturer']}", fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="nw", pady=2)
        ctk.CTkLabel(left, text=f"{t('fleet.detail_year')} {row['year'] or ''}", fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="nw")
        ctk.CTkLabel(left, text=f"{t('fleet.detail_vin')} {row['vin'] or ''}", fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="nw", pady=2)
        ctk.CTkLabel(left, text=f"{t('fleet.detail_km')} {(row['mileage'] or 0):,}", fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="nw")
        ctk.CTkLabel(left, text=f"{t('fleet.detail_rate')} {(row['monthly_rate'] or 0):.2f} {t('common.currency_eur')}", fg_color=Theme.BG, text_color=Theme.TEXT).pack(anchor="nw", pady=8)

        self._build_maintenance_kpi_strip(left, truck_id, row)

        ActionButton(left, t("fleet.detail_edit_button"), lambda: (win.destroy(), TruckFormDialog(self.frame, self.service, title=t("fleet.edit_button"), truck=row, on_save=self.refresh_fleet)), color=Theme.ACCENT).pack(fill="x", pady=6)
        ActionButton(left, t("fleet.detail_export_button"), lambda: self._export_truck_csv(row), color=Theme.SURFACE2).pack(fill="x", pady=6)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)

        # Maintenance tab — opens the full maintenance manager
        maint_frame = ctk.CTkFrame(nb, fg_color=Theme.BG)
        nb.add(maint_frame, text=f"\U0001F527 {t('fleet.tab_maintenance')}")
        ActionButton(
            maint_frame,
            f"\U0001F527 {t('fleet.open_maintenance_manager')}",
            lambda: self._open_maintenance_view(row["id"], row["plate_number"]),
            color=Theme.ACCENT,
        ).pack(pady=40)
        ctk.CTkLabel(
            maint_frame,
            text=t("fleet.maint_history_desc"),
            fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["label"],
        ).pack()

        exp_frame = ctk.CTkFrame(nb, fg_color=Theme.BG)
        nb.add(exp_frame, text=t("fleet.tab_expenses"))
        self._populate_expenses_tab(exp_frame, truck_id)

    def _populate_expenses_tab(self, parent, truck_id):
        try:
            self.service.ensure_expenses_table()
        except Exception:
            pass

        list_f = ctk.CTkFrame(parent, fg_color=Theme.BG)
        list_f.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ("id", "date", "category", "amount", "desc")
        exp_heading_keys = ("fleet.expenses_table_id", "fleet.expenses_table_date", "fleet.expenses_table_category", "fleet.expenses_table_amount", "fleet.expenses_table_desc")
        self._expenses_tree_heading_keys = list(zip(cols, exp_heading_keys))
        tree = ttk.Treeview(list_f, columns=cols, show="headings")
        self._expenses_tree = tree
        exp_headers = tuple(t(k) for k in exp_heading_keys)
        for c, h in zip(cols, exp_headers):
            tree.heading(c, text=h)
            tree.column(c, anchor="center", width=100 if c != "desc" else 240)
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_f, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        def load():
            for i in tree.get_children():
                tree.delete(i)
            rows = self.service.get_expenses(truck_id)
            for r in rows:
                tree.insert("", "end", values=(r[0], r[1], r[2], f"{r[3]:.2f}", r[4] or ""))

        load()

        form = ctk.CTkFrame(parent, fg_color=Theme.BG)
        form.pack(fill="x", padx=8)
        ctk.CTkLabel(form, text=t("fleet.add_expense"), fg_color=Theme.BG, text_color=Theme.ACCENT).pack(anchor="w")
        e_date = StyledEntry(form); e_date.insert(0, datetime.now().strftime("%Y-%m-%d")); e_date.pack(fill="x", pady=4)
        e_cat = StyledEntry(form); e_cat.insert(0, t("fleet.expense_default_category")); e_cat.pack(fill="x", pady=4)
        e_amount = StyledEntry(form); e_amount.insert(0, "0"); e_amount.pack(fill="x", pady=4)
        e_desc = StyledEntry(form); e_desc.pack(fill="x", pady=4)

        def save_exp():
            try:
                amt = float(e_amount.get() or 0)
            except ValueError:
                messagebox.showwarning(t("fleet.validation_amount_invalid"), t("fleet.validation_amount_invalid"))
                return
            try:
                self.service.add_expense(truck_id, e_date.get(), e_cat.get(), e_desc.get(), amt)
                load()
                self.refresh_fleet()
            except Exception as ex:
                messagebox.showerror(t("fleet.error_save_expense").format(""), t("fleet.error_save_expense").format(ex))

        ActionButton(form, t("fleet.save_expense"), save_exp, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=6)

    # Export helpers
    def _gather_trucks_for_export(self):
        rows = self.service.get_trucks()
        trucks = []
        for r in rows:
            trucks.append({
                "id": r["id"],
                "plate_number": r["plate_number"],
                "model": r["model"] or "",
                "manufacturer": r["manufacturer"] or "",
                "year": r["year"] or "",
                "vin": r["vin"] or "",
                "mileage": r["mileage"] or 0,
                "fuel_consumption": r["fuel_consumption"] or 0,
                "monthly_rate": r["monthly_rate"] or 0,
                "status": r["status"] or "",
                "active_status": r["active_status"] or 0
            })
        return trucks

    def _export_csv(self):
        trucks = self._gather_trucks_for_export()
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title=t("fleet.save_csv_title"))
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Plate", "Model", "Manufacturer", "Year", "VIN", "Mileage", "Fuel L/100", "Monthly Rate EUR", "Status", "Active"])
                for truck in trucks:
                    writer.writerow([truck["id"], truck["plate_number"], truck["model"], truck["manufacturer"], truck["year"], truck["vin"], truck["mileage"], truck["fuel_consumption"], truck["monthly_rate"], truck["status"], truck["active_status"]])
            messagebox.showinfo(t("fleet.export_csv_success").format(""), t("fleet.export_csv_success").format(path))
        except Exception as ex:
            messagebox.showerror(t("fleet.export_csv_error").format(""), t("fleet.export_csv_error").format(ex))

    def _export_excel(self):
        trucks = self._gather_trucks_for_export()
        mapped = []
        for truck in trucks:
            mapped.append({
                "id": truck["id"],
                "created_at": "",
                "truck_number": truck["plate_number"],
                "driver_name": "",
                "client_name": truck["manufacturer"] or truck["model"],
                "distance_km": truck["mileage"],
                "total_price_eur": truck["monthly_rate"],
                "gross_per_km": 0,
                "rate_per_km": 0,
                "net_profit": 0,
                "status": truck["status"],
                "fuel_cost": 0,
                "toll_cost": 0,
                "salary_cost": 0
            })
        try:
            path = self.exporter.generate_excel(mapped, filename=f"trucks_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
            messagebox.showinfo(t("fleet.export_excel_success").format(""), t("fleet.export_excel_success").format(path))
        except Exception as ex:
            messagebox.showerror(t("fleet.export_excel_error").format(""), t("fleet.export_excel_error").format(ex))

    def _export_pdf(self):
        trucks = self._gather_trucks_for_export()
        mapped = []
        for truck in trucks:
            mapped.append({
                "created_at": "",
                "truck_number": truck["plate_number"],
                "driver_name": truck["manufacturer"] or truck["model"],
                "client_name": "",
                "distance_km": truck["mileage"],
                "gross_per_km": 0,
                "net_profit": truck["monthly_rate"],
                "status": truck["status"]
            })
        try:
            path = self.exporter.generate_pdf(mapped, filename=f"fleet_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
            messagebox.showinfo(t("fleet.export_pdf_success").format(""), t("fleet.export_pdf_success").format(path))
        except Exception as ex:
            messagebox.showerror(t("fleet.export_pdf_error").format(""), t("fleet.export_pdf_error").format(ex))

    def _export_truck_csv(self, truck_row):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title=t("fleet.save_truck_csv_title"))
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Value"])
                writer.writerow(["ID", truck_row["id"]])
                writer.writerow(["Plate", truck_row["plate_number"]])
                writer.writerow(["Model", truck_row["model"]])
                writer.writerow(["Manufacturer", truck_row["manufacturer"]])
                writer.writerow(["Year", truck_row["year"]])
                writer.writerow(["VIN", truck_row["vin"]])
                writer.writerow(["Mileage", truck_row["mileage"]])
                writer.writerow(["Fuel L/100", truck_row["fuel_consumption"]])
                writer.writerow(["Monthly Rate EUR", truck_row["monthly_rate"]])
                writer.writerow(["Status", truck_row["status"]])
                writer.writerow(["Active", truck_row["active_status"]])
            messagebox.showinfo(t("fleet.export_truck_csv_success").format(""), t("fleet.export_truck_csv_success").format(path))
        except Exception as ex:
            messagebox.showerror(t("fleet.export_truck_csv_error").format(""), t("fleet.export_truck_csv_error").format(ex))

    def _open_maintenance_view(self, truck_id, truck_plate):
        from ui.maintenance_view import MaintenanceView
        MaintenanceView(self.frame, self.db, truck_id, truck_plate)

    def _open_truck_documents(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            messagebox.showinfo(t("fleet.documents_button"), t("fleet.select_truck_first"))
            return
        from ui.views.document_center_view import open_entity_documents
        truck = self.service._repo.get_by_id(truck_id)
        plate = truck.get("plate_number", "Unknown") if truck else "Unknown"
        open_entity_documents(self.frame, self.db, "truck", truck_id, f"Truck {plate}")
