import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from services.i18n import t, register_listener, unregister_listener
from ui.styles import Theme
from ui.widgets import ActionButton, StyledCheckbutton, StyledEntry, section_header
from services.fleet_service import FleetService
from services.export_service import ExportService
from database.db_manager import DatabaseManager

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except Exception:
    HAS_MPL = False


class FleetTab:
    def __init__(self, parent, db_or_path, open_window=True):
        self.parent = parent
        if isinstance(db_or_path, DatabaseManager):
            self.db = db_or_path
        else:
            self.db = DatabaseManager(db_or_path)
        self.service = FleetService(self.db)                                
        self.exporter = ExportService()
        self._i18n_widgets = []
        self._tree_heading_keys = []
        self._kpi_title_refs = []
        if open_window:
            self.win = tk.Toplevel(parent)
            self.win.title(t("fleet.title"))
            self.win.geometry("1100x700")
            Theme.apply(self.win)
            self.frame = tk.Frame(self.win, bg=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = None
            self.frame = tk.Frame(parent, bg=Theme.BG)

        self._setup_ui()

        self.refresh_fleet()

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
            self.win.title(t("fleet.title"))
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        for col, key in self._tree_heading_keys:
            try:
                self.tree.heading(col, text=t(key))
            except Exception:
                pass
        for key in self._kpi_title_refs:
            try:
                lbl, k = key
                lbl.config(text=t(k))
            except Exception:
                pass

    def _setup_ui(self):
        header = tk.Frame(self.frame, bg=Theme.BG)
        header.pack(fill="x", padx=12, pady=(8, 4))
        lbl = tk.Label(header, text=t("fleet.title"), bg=Theme.BG, fg=Theme.ACCENT, font=Theme.FONT_TITLE)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "fleet.title")
        ex_f = tk.Frame(header, bg=Theme.BG)
        ex_f.pack(side="right")
        btn = ActionButton(ex_f, t("fleet.export_csv"), self._export_csv, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self._i18n_tag(btn, "fleet.export_csv")
        btn = ActionButton(ex_f, t("fleet.export_excel"), self._export_excel, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self._i18n_tag(btn, "fleet.export_excel")
        btn = ActionButton(ex_f, t("fleet.export_pdf"), self._export_pdf, color=Theme.SURFACE2)
        btn.pack(side="right", padx=6)
        self._i18n_tag(btn, "fleet.export_pdf")

        kpi_cont = tk.Frame(self.frame, bg=Theme.BG, pady=6)
        kpi_cont.pack(fill="x", padx=12)
        kpi_total_val, kpi_total_title = self._kpi_card(kpi_cont, t("fleet.kpi_total_trucks"), "0")
        self.kpi_total = kpi_total_val
        self._kpi_title_refs.append((kpi_total_title, "fleet.kpi_total_trucks"))
        kpi_active_val, kpi_active_title = self._kpi_card(kpi_cont, t("fleet.kpi_active"), "0")
        self.kpi_active = kpi_active_val
        self._kpi_title_refs.append((kpi_active_title, "fleet.kpi_active"))
        kpi_maint_val, kpi_maint_title = self._kpi_card(kpi_cont, t("fleet.kpi_service_due"), "0")
        self.kpi_maintenance = kpi_maint_val
        self._kpi_title_refs.append((kpi_maint_title, "fleet.kpi_service_due"))
        kpi_lease_val, kpi_lease_title = self._kpi_card(kpi_cont, t("fleet.kpi_monthly_rate"), "0")
        self.kpi_leasing = kpi_lease_val
        self._kpi_title_refs.append((kpi_lease_title, "fleet.kpi_monthly_rate"))

        main = tk.PanedWindow(self.frame, orient="horizontal", sashrelief="raised", bg=Theme.BG)
        main.pack(fill="both", expand=True, padx=12, pady=8)

        left = tk.Frame(main, bg=Theme.BG)
        right = tk.Frame(main, bg=Theme.BG, width=360)
        main.add(left, minsize=700)
        main.add(right, minsize=320)

        search_f = tk.Frame(left, bg=Theme.BG)
        search_f.pack(fill="x", padx=6, pady=(0, 6))
        lbl = tk.Label(search_f, text=t("fleet.search_label"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(side="left")
        self._i18n_tag(lbl, "fleet.search_label")
        self.e_search = StyledEntry(search_f)
        self.e_search.pack(side="left", fill="x", expand=True, padx=(8, 6))
        self.e_search.bind("<KeyRelease>", lambda e: self._filter_tree())
        btn = ActionButton(search_f, t("fleet.reset_button"), lambda: (self.e_search.delete(0, "end"), self._filter_tree()), color=Theme.SURFACE2)
        btn.pack(side="left")
        self._i18n_tag(btn, "fleet.reset_button")

        plate_f = tk.Frame(search_f, bg=Theme.BG)
        plate_f.pack(side="right")
        lbl = tk.Label(plate_f, text=t("fleet.plate_label"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(side="left", padx=(6,4))
        self._i18n_tag(lbl, "fleet.plate_label")
        self.e_plate_search = StyledEntry(plate_f, width=12)
        self.e_plate_search.pack(side="left", padx=(0,6))
        btn = ActionButton(plate_f, t("fleet.find_button"), lambda: self._find_plate(), color=Theme.SURFACE2, width=8)
        btn.pack(side="left")
        self._i18n_tag(btn, "fleet.find_button")

        table_f = tk.Frame(left, bg=Theme.BG)
        table_f.pack(fill="both", expand=True)
        cols = ("id", "plate", "model", "manufacturer", "year", "vin", "mileage", "fuel", "monthly_rate", "status", "ins_exp", "itp_exp", "maint_due", "active")
        headers = (
            t("fleet.table_id"), t("fleet.table_plate"), t("fleet.table_model"), t("fleet.table_manufacturer"),
            t("fleet.table_year"), t("fleet.table_vin"), t("fleet.table_km"), t("fleet.table_consumption"),
            t("fleet.table_rate"), t("fleet.table_status"), t("fleet.table_insurance"), t("fleet.table_inspection"),
            t("fleet.table_service_km"), t("fleet.table_active")
        )
        heading_keys = (
            "fleet.table_id", "fleet.table_plate", "fleet.table_model", "fleet.table_manufacturer",
            "fleet.table_year", "fleet.table_vin", "fleet.table_km", "fleet.table_consumption",
            "fleet.table_rate", "fleet.table_status", "fleet.table_insurance", "fleet.table_inspection",
            "fleet.table_service_km", "fleet.table_active"
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

        btns = tk.Frame(left, bg=Theme.BG, pady=8)
        btns.pack(fill="x")
        btn = ActionButton(btns, f"➕ {t('fleet.add_truck')}", self._add_truck_win, color=Theme.ACCENT_SUCCESS)
        btn.pack(side="left", padx=6)
        self._i18n_tag(btn, "fleet.add_truck", "➕ ")
        btn = ActionButton(btns, f"✏️ {t('fleet.edit_button')}", self._edit_truck_selected, color=Theme.ACCENT)
        btn.pack(side="left", padx=6)
        self._i18n_tag(btn, "fleet.edit_button", "✏️ ")
        btn = ActionButton(btns, f"🗑️ {t('fleet.delete_button')}", self._delete_truck, color=Theme.DANGER)
        btn.pack(side="right", padx=6)
        self._i18n_tag(btn, "fleet.delete_button", "🗑️ ")

        lbl = section_header(right, t("fleet.section_alerts"), _return=True)
        self._i18n_tag(lbl, "fleet.section_alerts")
        self.alerts_box = tk.Frame(right, bg=Theme.SURFACE, padx=8, pady=8)
        self.alerts_box.pack(fill="both", padx=8)
        self.alerts_list = tk.Listbox(
            self.alerts_box,
            bg=Theme.INPUT_BG,
            fg=Theme.TEXT,
            selectbackground=Theme.ACCENT,
            selectforeground=Theme.TEXT,
            bd=0,
            highlightthickness=0
        )
        self.alerts_list.pack(fill="both", expand=True)

        lbl = section_header(right, t("fleet.section_charts"), _return=True)
        self._i18n_tag(lbl, "fleet.section_charts")
        self.chart_area = tk.Frame(right, bg=Theme.BG)
        self.chart_area.pack(fill="both", padx=8, pady=6, expand=False)
        if HAS_MPL:
            self.fig = Figure(figsize=(4, 2), dpi=100)
            self.ax = self.fig.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_area)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            self.chart_canvas = tk.Canvas(self.chart_area, bg=Theme.SURFACE2, height=160, bd=0, highlightthickness=0)
            self.chart_canvas.pack(fill="x", expand=True)

        lbl = section_header(right, t("fleet.section_quick_add"), _return=True)
        self._i18n_tag(lbl, "fleet.section_quick_add")
        quick_f = tk.Frame(right, bg=Theme.BG)
        quick_f.pack(fill="x", padx=8, pady=6)
        lbl = tk.Label(quick_f, text=t("fleet.plate_quick"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "fleet.plate_quick")
        self.q_plate = StyledEntry(quick_f); self.q_plate.pack(fill="x", pady=4)
        lbl = tk.Label(quick_f, text=t("fleet.model_quick"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "fleet.model_quick")
        self.q_model = StyledEntry(quick_f); self.q_model.pack(fill="x", pady=4)
        lbl = tk.Label(quick_f, text=t("fleet.rate_quick"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "fleet.rate_quick")
        self.q_rate = StyledEntry(quick_f); self.q_rate.insert(0, "0"); self.q_rate.pack(fill="x", pady=4)
        btn = ActionButton(quick_f, t("fleet.save_quick"), self._save_quick, color=Theme.ACCENT_SUCCESS)
        btn.pack(fill="x", pady=6)
        self._i18n_tag(btn, "fleet.save_quick")

    def _kpi_card(self, parent, title, value):
        c = tk.Frame(parent, bg=Theme.SURFACE, padx=12, pady=10)
        c.pack(side="left", padx=6, fill="y")
        title_lbl = tk.Label(c, text=title, bg=Theme.SURFACE, fg=Theme.MUTED, font=Theme.FONT_MAIN)
        title_lbl.pack(anchor="w")
        val_lbl = tk.Label(c, text=value, bg=Theme.SURFACE, fg=Theme.TEXT, font=Theme.FONT_BOLD)
        val_lbl.pack(anchor="w")
        return val_lbl, title_lbl

    def refresh_fleet(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            rows = self.service.get_trucks()

            for r in rows:
                self.tree.insert("", "end", values=(
                    r[0],
                    r[1],
                    r[2] or "",
                    r[3] or "",
                    r[4] or "",
                    r[5] or "",
                    f"{(r[6] or 0):,}",
                    f"{(r[7] or 0):.1f}" if r[7] is not None else "",
                    f"{(r[8] or 0):.2f}",
                    r[9] or "",
                    r[10] or "",
                    r[11] or "",
                    r[12] or "",
                    "Yes" if (r[13] == 1 or r[13] == True) else "No"
                ))

            total = len(rows)
            active = sum(1 for r in rows if r[13] == 1 or r[13] == True)
            maint_due = sum(1 for r in rows if r[12] and r[6] and r[6] >= r[12])
            month_year = datetime.now().strftime("%m/%Y")
            total_leasing, total_maint = self.service.get_fleet_financials(month_year)

            self.kpi_total.config(text=str(total))
            self.kpi_active.config(text=str(active))
            self.kpi_maintenance.config(text=str(maint_due))
            self.kpi_leasing.config(text=f"{total_leasing:.2f} EUR")

            self._load_alerts()
            self._draw_charts(rows)
            self._filter_tree()
        except Exception as ex:
            messagebox.showerror(t("fleet.error_load").format(""), t("fleet.error_load").format(ex))

    def _load_alerts(self):
        self.alerts_list.delete(0, "end")
        try:
            alerts = self.service.get_truck_alerts()
            for a in alerts:
                self.alerts_list.insert("end", t("fleet.alert_format").format(type=a.get('type','INFO'), msg=a.get('msg')))
            if not alerts:
                self.alerts_list.insert("end", t("fleet.no_alerts"))
        except Exception:
            self.alerts_list.insert("end", t("fleet.alert_load_error"))

    def _draw_charts(self, rows):
        statuses = {}
        rates = []
        for r in rows:
            st = r[9] or "Unknown"
            statuses[st] = statuses.get(st, 0) + 1
            rates.append(float(r[8] or 0))

        labels = list(statuses.keys())
        counts = list(statuses.values())

        if HAS_MPL:
            self.ax.clear()
            if counts:
                self.ax.pie(counts, labels=labels, autopct="%1.0f%%", colors=[Theme.INFO, Theme.SUCCESS, Theme.DANGER])
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
        self._truck_form_window(title=t("fleet.truck_form_title"))

    def _edit_truck_selected(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            return
        row = self.service.get_truck(truck_id)
        if not row:
            messagebox.showerror(t("fleet.truck_not_found"), t("fleet.truck_not_found"))
            return
        self._truck_form_window(title=t("fleet.edit_button"), truck=row)

    def _truck_form_window(self, title="Truck", truck=None):
        win = tk.Toplevel(self.frame)
        win.title(title)
        Theme.apply(win)
        container = tk.Frame(win, bg=Theme.BG)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=Theme.BG, highlightthickness=0)
        scrollbar_v = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar_h = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)

        canvas.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)

        scrollbar_v.pack(side="right", fill="y")
        scrollbar_h.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        win_frame = tk.Frame(canvas, bg=Theme.BG, padx=14, pady=12)
        canvas.create_window((0, 0), window=win_frame, anchor="nw")

        def _on_config(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        win_frame.bind("<Configure>", _on_config)

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(_):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_mousewheel(_):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        parent_frame = win_frame

        def add_field(label_text, default=""):
            tk.Label(parent_frame, text=label_text, bg=Theme.BG, fg=Theme.TEXT).pack(anchor="w")
            e = StyledEntry(parent_frame)
            e.pack(fill="x", pady=6)
            e.insert(0, default)
            return e

        fields = {}
        fields['plate'] = add_field(t("fleet.form_plate"), truck[1] if truck else "")
        fields['model'] = add_field(t("fleet.form_model"), truck[2] if truck else "")
        fields['manufacturer'] = add_field(t("fleet.form_manufacturer"), truck[3] if truck else "")
        fields['year'] = add_field(t("fleet.form_year"), str(truck[4]) if truck and truck[4] else "")
        fields['vin'] = add_field(t("fleet.form_vin"), truck[5] if truck else "")
        fields['fuel'] = add_field(t("fleet.form_consumption"), str(truck[7]) if truck and truck[7] is not None else "")
        fields['mileage'] = add_field(t("fleet.form_km"), str(truck[6]) if truck and truck[6] is not None else "0")
        fields['monthly_rate'] = add_field(t("fleet.form_rate"), f"{truck[8]:.2f}" if truck and truck[8] is not None else "0")
        fields['status'] = add_field(t("fleet.form_status"), truck[9] if truck else "Active")
        fields['insurance'] = add_field(t("fleet.form_insurance"), truck[10] if truck else "")
        fields['inspection'] = add_field(t("fleet.form_inspection"), truck[11] if truck else "")
        fields['maint_due'] = add_field(t("fleet.form_service_km"), str(truck[12]) if truck and truck[12] is not None else "")

        active_var = tk.IntVar(value=(truck[13] if truck else 1))
        StyledCheckbutton(parent_frame, text=t("fleet.form_active"), variable=active_var).pack(anchor="w", pady=(6, 12))

        def save():
            plate = fields['plate'].get().strip().upper()
            if not plate:
                messagebox.showwarning(t("fleet.validation_plate_required"), t("fleet.validation_plate_required"))
                return
            try:
                year = int(fields['year'].get()) if fields['year'].get().strip() else None
            except ValueError:
                messagebox.showwarning(t("fleet.validation_year_invalid"), t("fleet.validation_year_invalid"))
                return
            try:
                fuel = float(fields['fuel'].get()) if fields['fuel'].get().strip() else None
            except ValueError:
                messagebox.showwarning(t("fleet.validation_consumption_invalid"), t("fleet.validation_consumption_invalid"))
                return
            try:
                mileage = float(fields['mileage'].get() or 0)
                monthly_rate = float(fields['monthly_rate'].get() or 0)
                maint_due = float(fields['maint_due'].get()) if fields['maint_due'].get().strip() else None
            except ValueError:
                messagebox.showwarning(t("fleet.validation_km_rate_service_invalid"), t("fleet.validation_km_rate_service_invalid"))
                return

            ins = fields['insurance'].get().strip()
            itp = fields['inspection'].get().strip()

            try:
                if truck:
                    self.service.update_truck(truck[0], {
                        "plate_number": plate,
                        "model": fields['model'].get(),
                        "manufacturer": fields['manufacturer'].get(),
                        "year": year,
                        "vin": fields['vin'].get(),
                        "fuel_consumption": fuel,
                        "mileage": mileage,
                        "monthly_rate": monthly_rate,
                        "status": fields['status'].get(),
                        "insurance_expiry": ins,
                        "inspection_expiry": itp,
                        "maintenance_due": maint_due,
                        "active_status": active_var.get()
                    })
                else:
                    self.service.add_truck({
                        "plate_number": plate,
                        "model": fields['model'].get(),
                        "manufacturer": fields['manufacturer'].get(),
                        "year": year,
                        "vin": fields['vin'].get(),
                        "fuel_consumption": fuel,
                        "mileage": mileage,
                        "monthly_rate": monthly_rate,
                        "status": fields['status'].get(),
                        "insurance_expiry": ins,
                        "inspection_expiry": itp,
                        "maintenance_due": maint_due,
                        "active_status": active_var.get()
                    })
                self.refresh_fleet()
                win.destroy()
            except Exception as ex:
                messagebox.showerror(t("fleet.error_save").format(""), t("fleet.error_save").format(ex))

        ActionButton(parent_frame, t("fleet.save_button"), save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=10)
        ActionButton(parent_frame, t("fleet.cancel_button"), win.destroy, color=Theme.SURFACE2).pack(fill="x")

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

        win = tk.Toplevel(self.frame)
        win.title(t("fleet.truck_detail_title").format(row[1]))
        win.geometry("900x600")
        Theme.apply(win)

        left = tk.Frame(win, bg=Theme.BG, width=320)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = tk.Frame(win, bg=Theme.BG)
        right.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        tk.Label(left, text=f"{row[1]} - {row[2]}", bg=Theme.BG, fg=Theme.ACCENT, font=Theme.FONT_BOLD).pack(anchor="nw")
        tk.Label(left, text=f"{t('fleet.detail_manufacturer')} {row[3]}", bg=Theme.BG, fg=Theme.TEXT).pack(anchor="nw", pady=2)
        tk.Label(left, text=f"{t('fleet.detail_year')} {row[4] or ''}", bg=Theme.BG, fg=Theme.TEXT).pack(anchor="nw")
        tk.Label(left, text=f"{t('fleet.detail_vin')} {row[5] or ''}", bg=Theme.BG, fg=Theme.TEXT).pack(anchor="nw", pady=2)
        tk.Label(left, text=f"{t('fleet.detail_km')} {(row[6] or 0):,}", bg=Theme.BG, fg=Theme.TEXT).pack(anchor="nw")
        tk.Label(left, text=f"{t('fleet.detail_rate')} {(row[8] or 0):.2f} EUR", bg=Theme.BG, fg=Theme.TEXT).pack(anchor="nw", pady=8)

        ActionButton(left, t("fleet.detail_edit_button"), lambda: (win.destroy(), self._truck_form_window(title=t("fleet.edit_button"), truck=row)), color=Theme.ACCENT).pack(fill="x", pady=6)
        ActionButton(left, t("fleet.detail_export_button"), lambda: self._export_truck_csv(row), color=Theme.SURFACE2).pack(fill="x", pady=6)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)

        maint_frame = tk.Frame(nb, bg=Theme.BG)
        nb.add(maint_frame, text=t("fleet.tab_maintenance"))
        self._populate_maintenance_tab(maint_frame, truck_id)

        ins_frame = tk.Frame(nb, bg=Theme.BG)
        nb.add(ins_frame, text=t("fleet.tab_insurance"))
        self._populate_insurance_tab(ins_frame, row)

        exp_frame = tk.Frame(nb, bg=Theme.BG)
        nb.add(exp_frame, text=t("fleet.tab_expenses"))
        self._populate_expenses_tab(exp_frame, truck_id)

    def _populate_maintenance_tab(self, parent, truck_id):
        list_f = tk.Frame(parent, bg=Theme.BG)
        list_f.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ("id", "date", "type", "km", "cost", "desc")
        tree = ttk.Treeview(list_f, columns=cols, show="headings")
        maint_headers = (t("fleet.maintenance_table_id"), t("fleet.maintenance_table_date"), t("fleet.maintenance_table_type"), t("fleet.maintenance_table_km"), t("fleet.maintenance_table_cost"), t("fleet.maintenance_table_desc"))
        for c, h in zip(cols, maint_headers):
            tree.heading(c, text=h)
            tree.column(c, anchor="center", width=100 if c != "desc" else 240)
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_f, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        def load():
            for i in tree.get_children():
                tree.delete(i)
            rows = self.service.get_maintenance(truck_id)   
            for r in rows:
                tree.insert("", "end", values=(r[0], r[1], r[2], f"{r[3] or ''}", f"{r[4]:.2f}" if r[4] else "", r[5] or ""))
        load()

        form = tk.Frame(parent, bg=Theme.BG, pady=8)
        form.pack(fill="x", padx=8)
        tk.Label(form, text=t("fleet.add_maintenance"), bg=Theme.BG, fg=Theme.ACCENT).pack(anchor="w")
        e_date = StyledEntry(form); e_date.insert(0, datetime.now().strftime("%d/%m/%Y")); e_date.pack(fill="x", pady=4)
        e_type = StyledEntry(form); e_type.insert(0, "General"); e_type.pack(fill="x", pady=4)
        e_km = StyledEntry(form); e_km.pack(fill="x", pady=4)
        e_cost = StyledEntry(form); e_cost.insert(0, "0"); e_cost.pack(fill="x", pady=4)
        e_desc = StyledEntry(form); e_desc.pack(fill="x", pady=4)

        def save_maint():
            try:
                km = float(e_km.get() or 0)
                cost = float(e_cost.get() or 0)
            except ValueError:
                messagebox.showwarning(t("fleet.validation_km_cost_invalid"), t("fleet.validation_km_cost_invalid"))
                return
            try:
                self.service.add_maintenance(truck_id, e_date.get(), e_type.get(), e_desc.get(), km, cost)
                load()
                self.refresh_fleet()
                e_date.delete(0, "end"); e_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
                e_type.delete(0, "end"); e_type.insert(0, "General")
                e_km.delete(0, "end"); e_cost.delete(0, "end"); e_desc.delete(0, "end")
            except Exception as ex:
                messagebox.showerror(t("fleet.error_save_maintenance").format(""), t("fleet.error_save_maintenance").format(ex))

        ActionButton(form, t("fleet.save_maintenance"), save_maint, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=6)

    def _populate_insurance_tab(self, parent, truck_row):
        parent.pack_propagate(False)
        f = tk.Frame(parent, bg=Theme.BG, padx=8, pady=8)
        f.pack(fill="both", expand=True)
        tk.Label(f, text=t("fleet.insurance_label"), bg=Theme.BG, fg=Theme.TEXT).pack(anchor="w")
        e_ins = StyledEntry(f); e_ins.insert(0, truck_row[10] or ""); e_ins.pack(fill="x", pady=4)
        tk.Label(f, text=t("fleet.inspection_label"), bg=Theme.BG, fg=Theme.TEXT).pack(anchor="w")
        e_itp = StyledEntry(f); e_itp.insert(0, truck_row[11] or ""); e_itp.pack(fill="x", pady=4)

        def save_ins():
            try:
                self.service.update_truck(truck_row[0], {
                    "insurance_expiry": e_ins.get(),    
                    "inspection_expiry": e_itp.get()
                })
                self.refresh_fleet()
                messagebox.showinfo(t("fleet.success_updated"), t("fleet.success_updated"))
            except Exception as ex:
                messagebox.showerror(t("fleet.error_save").format(""), t("fleet.error_save").format(ex))

        ActionButton(f, t("fleet.save_button"), save_ins, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=6)

    def _populate_expenses_tab(self, parent, truck_id):
        try:
            self.service.ensure_expenses_table()
        except Exception:
            pass

        list_f = tk.Frame(parent, bg=Theme.BG)
        list_f.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ("id", "date", "category", "amount", "desc")
        tree = ttk.Treeview(list_f, columns=cols, show="headings")
        exp_headers = (t("fleet.expenses_table_id"), t("fleet.expenses_table_date"), t("fleet.expenses_table_category"), t("fleet.expenses_table_amount"), t("fleet.expenses_table_desc"))
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

        form = tk.Frame(parent, bg=Theme.BG, pady=8)
        form.pack(fill="x", padx=8)
        tk.Label(form, text=t("fleet.add_expense"), bg=Theme.BG, fg=Theme.ACCENT).pack(anchor="w")
        e_date = StyledEntry(form); e_date.insert(0, datetime.now().strftime("%d/%m/%Y")); e_date.pack(fill="x", pady=4)
        e_cat = StyledEntry(form); e_cat.insert(0, "Altele"); e_cat.pack(fill="x", pady=4)
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
                "id": r[0],
                "plate_number": r[1],
                "model": r[2] or "",
                "manufacturer": r[3] or "",
                "year": r[4] or "",
                "vin": r[5] or "",
                "mileage": r[6] or 0,
                "fuel_consumption": r[7] or 0,
                "monthly_rate": r[8] or 0,
                "status": r[9] or "",
                "insurance_expiry": r[10] or "",
                "inspection_expiry": r[11] or "",
                "maintenance_due": r[12] or "",
                "active_status": r[13] or 0
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
                writer.writerow(["ID", "Plate", "Model", "Manufacturer", "Year", "VIN", "Mileage", "Fuel L/100", "Monthly Rate EUR", "Status", "Insurance", "Inspection", "Maintenance KM", "Active"])
                for t in trucks:
                    writer.writerow([t["id"], t["plate_number"], t["model"], t["manufacturer"], t["year"], t["vin"], t["mileage"], t["fuel_consumption"], t["monthly_rate"], t["status"], t["insurance_expiry"], t["inspection_expiry"], t["maintenance_due"], t["active_status"]])
            messagebox.showinfo(t("fleet.export_csv_success").format(""), t("fleet.export_csv_success").format(path))
        except Exception as ex:
            messagebox.showerror(t("fleet.export_csv_error").format(""), t("fleet.export_csv_error").format(ex))

    def _export_excel(self):
        trucks = self._gather_trucks_for_export()
        mapped = []
        for t in trucks:
            mapped.append({
                "id": t["id"],
                "created_at": "",
                "truck_number": t["plate_number"],
                "driver_name": "",
                "client_name": t["manufacturer"] or t["model"],
                "distance_km": t["mileage"],
                "total_price_eur": t["monthly_rate"],
                "gross_per_km": 0,
                "rate_per_km": 0,
                "net_profit": 0,
                "status": t["status"],
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
        for t in trucks:
            mapped.append({
                "created_at": "",
                "truck_number": t["plate_number"],
                "driver_name": t["manufacturer"] or t["model"],
                "client_name": "",
                "distance_km": t["mileage"],
                "gross_per_km": 0,
                "net_profit": t["monthly_rate"],
                "status": t["status"]
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
                writer.writerow(["ID", truck_row[0]])
                writer.writerow(["Plate", truck_row[1]])
                writer.writerow(["Model", truck_row[2]])
                writer.writerow(["Manufacturer", truck_row[3]])
                writer.writerow(["Year", truck_row[4]])
                writer.writerow(["VIN", truck_row[5]])
                writer.writerow(["Mileage", truck_row[6]])
                writer.writerow(["Fuel L/100", truck_row[7]])
                writer.writerow(["Monthly Rate EUR", truck_row[8]])
                writer.writerow(["Status", truck_row[9]])
                writer.writerow(["Insurance Expiry", truck_row[10]])
                writer.writerow(["Inspection Expiry", truck_row[11]])
                writer.writerow(["Maintenance KM", truck_row[12]])
                writer.writerow(["Active", truck_row[13]])
            messagebox.showinfo(t("fleet.export_truck_csv_success").format(""), t("fleet.export_truck_csv_success").format(path))
        except Exception as ex:
            messagebox.showerror(t("fleet.export_truck_csv_error").format(""), t("fleet.export_truck_csv_error").format(ex))
