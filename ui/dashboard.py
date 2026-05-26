import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from services.i18n import t, register_listener, unregister_listener
from services.preferences import safe_float
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry

try:
    import matplotlib
    matplotlib.use('TkAgg') 
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

class DashboardView:
    def __init__(self, parent, db, prefs=None):
        self.win = tk.Toplevel(parent)
        self.win.title(f"📊 {t('dashboard.title')}")
        self.win.geometry("1450x950")
        Theme.apply(self.win)
        self.db = db
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        
        self.current_start = None
        self.current_end = None
        self._i18n_widgets = []
        self._chart_ax = None
        self._chart_canvas = None

        self._setup_filter_bar()
        self.content_frame = tk.Frame(self.win, bg=Theme.BG)
        self.content_frame.pack(fill="both", expand=True)
        
        self.refresh_stats()

        self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.win:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        self.win.title(f"📊 {t('dashboard.title')}")
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        self.c_period.configure(values=t("dashboard.period_options"))
        self.c_period.current(0)
        if self._chart_ax is not None:
            try:
                self._chart_ax.set_title(t("dashboard.chart_profit_evolution"), color=Theme.TEXT, fontsize=9)
                if self._chart_canvas is not None:
                    self._chart_canvas.draw_idle()
            except Exception:
                pass

    def _setup_filter_bar(self):
        fb = tk.Frame(self.win, bg=Theme.SURFACE, pady=18, padx=25)
        fb.pack(fill="x")

        lbl = tk.Label(fb, text=f"📅 {t('dashboard.period_label')}", bg=Theme.SURFACE, fg=Theme.TEXT, 
                 font=("Segoe UI", 10, "bold"))
        lbl.pack(side="left", padx=5)
        self._i18n_tag(lbl, "dashboard.period_label", "📅 ")
        
        self.c_period = ttk.Combobox(fb, values=t("dashboard.period_options"), state="readonly", width=22)
        self.c_period.current(0)
        self.c_period.pack(side="left", padx=10)
        self.c_period.bind("<<ComboboxSelected>>", self._on_period_change)

        self.extra_inputs = tk.Frame(fb, bg=Theme.SURFACE)
        self.extra_inputs.pack(side="left", padx=15)

        btn = ActionButton(fb, f"🔄 {t('dashboard.refresh_button')}", self.refresh_stats, color=Theme.ACCENT)
        btn.pack(side="right")
        self._i18n_tag(btn, "dashboard.refresh_button", "🔄 ")

    def _on_period_change(self, event):
        for widget in self.extra_inputs.winfo_children():
            widget.destroy()

        selection = self.c_period.get()
        today = datetime.now()

        po = t("dashboard.period_options")
        if selection == po[1]:
            self.current_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            self.current_end = today.strftime("%Y-%m-%d")
        elif selection == po[2]:
            self.current_start = today.strftime("%Y-%m-01")
            self.current_end = today.strftime("%Y-%m-%d")
        elif selection == po[3]:
            years = self.db.get_available_years()
            self.c_year = ttk.Combobox(self.extra_inputs, values=years, state="readonly", width=12)
            if years: self.c_year.current(0)
            self.c_year.pack(side="left")
        elif selection == po[4]:
            self.e_start = StyledEntry(self.extra_inputs, width=14)
            self.e_start.insert(0, today.strftime("%Y-%m-%d"))
            self.e_start.pack(side="left", padx=5)
            tk.Label(self.extra_inputs, text="➜", bg=Theme.SURFACE, fg=Theme.TEXT).pack(side="left")
            self.e_end = StyledEntry(self.extra_inputs, width=14)
            self.e_end.insert(0, today.strftime("%Y-%m-%d"))
            self.e_end.pack(side="left", padx=5)

    def refresh_stats(self):
        selection = self.c_period.get()
        po = t("dashboard.period_options")
        start, end = self.current_start, self.current_end
        if selection == po[3]:
            year = self.c_year.get()
            start, end = f"{year}-01-01", f"{year}-12-31"
        elif selection == po[4]:
            start, end = self.e_start.get(), self.e_end.get()
        elif selection == po[0]:
            start = end = None

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        try:
            stats = self.db.get_stats_by_period(start, end)
            kpi = self.db.get_kpi_stats()
            bt, bd, bm = self.db.get_advanced_analytics()
            top_clients, monthly_data = self.db.get_dashboard_charts()
            alerts, total_ov_amount = self.db.get_overdue_data()

            self._build_ui_content(stats, kpi, bm, bt, bd, top_clients, monthly_data, alerts, total_ov_amount)
        except Exception as e:
            messagebox.showerror(t("dashboard.error_title"), t("dashboard.error_msg").format(e))

    def _build_ui_content(self, stats, kpi, best_month, best_t, best_d, top_clients, monthly, alerts, total_overdue):
        container = tk.Frame(self.content_frame, bg=Theme.BG)
        container.pack(fill="both", expand=True, padx=30, pady=20)

        kpi_row = tk.Frame(container, bg=Theme.BG)
        kpi_row.pack(fill="x", pady=(0, 30))
        rev = safe_float(kpi.get('rev'), label="kpi.rev")
        profit = safe_float(kpi.get('profit'), label="kpi.profit")
        km_kpi = safe_float(kpi.get('km'), label="kpi.km")
        avg_p_km = (profit / km_kpi) if km_kpi else 0
        self._kpi_card(kpi_row, t("dashboard.kpi_monthly_revenue"), self.prefs.format_currency(rev, 0), Theme.ACCENT, 0)
        self._kpi_card(kpi_row, t("dashboard.kpi_monthly_profit"), self.prefs.format_currency(profit, 0), Theme.ACCENT_SUCCESS, 1)
        self._kpi_card(kpi_row, t("dashboard.kpi_avg_profit_per_km"), self.prefs.format_currency(avg_p_km), Theme.YELLOW, 2)
        self._kpi_card(kpi_row, t("dashboard.kpi_unpaid_invoices"), str(kpi.get('unpaid', 0)), Theme.DANGER, 3)
        self._kpi_card(kpi_row, t("dashboard.kpi_active_trips"), str(kpi.get('active', 0)), Theme.ACCENT, 4)

        main_body = tk.Frame(container, bg=Theme.BG)
        main_body.pack(fill="both", expand=True)

        left_f = tk.Frame(main_body, bg=Theme.BG)
        left_f.pack(side="left", fill="both", expand=True)

        tk.Label(left_f, text=f"📊 {t('dashboard.section_financial')}", font=("Segoe UI", 10, "bold"), bg=Theme.BG, fg=Theme.MUTED).pack(anchor="w", padx=10)
        r1 = tk.Frame(left_f, bg=Theme.BG); r1.pack(fill="x", pady=10)
        p, v, k = safe_float(stats['total_p'], label="stats.total_p"), safe_float(stats['total_rev'], label="stats.total_rev"), safe_float(stats['total_km'], label="stats.total_km")
        self._card(r1, t("dashboard.card_net_profit"), self.prefs.format_currency(p), 0, 0, Theme.ACCENT_SUCCESS)
        self._card(r1, t("dashboard.card_gross_revenue"), self.prefs.format_currency(v), 0, 1, Theme.ACCENT)
        avg_gross = (float(v) / float(k)) if k else 0
        avg_net = (float(p) / float(k)) if k else 0
        self._card(r1, t("dashboard.card_avg_gross_rate"), f"{avg_gross:.2f} {self.prefs.get_currency_symbol()}/km", 0, 2)
        self._card(r1, t("dashboard.card_avg_net_rate"), f"{avg_net:.2f} {self.prefs.get_currency_symbol()}/km", 0, 3)

        mid_f = tk.Frame(left_f, bg=Theme.BG); mid_f.pack(fill="both", expand=True, pady=10)
        mvp_f = tk.Frame(mid_f, bg=Theme.BG); mvp_f.pack(side="left", fill="y")
        m_val = f"{best_month['month']}\n({self.prefs.format_currency(safe_float(best_month['m_profit'], label='best_month.m_profit'), 0)})" if best_month else "N/A"
        self._card(mvp_f, t("dashboard.card_best_month"), m_val, 0, 0, Theme.YELLOW)
        t_val = f"{best_t['truck_number']}\n({self.prefs.format_currency(safe_float(best_t['p'], label='best_t.p'), 0)})" if best_t else "N/A"
        self._card(mvp_f, t("dashboard.card_top_truck"), t_val, 1, 0, Theme.YELLOW)
        d_val = f"{best_d['driver_name']}\n({self.prefs.format_currency(safe_float(best_d['p'], label='best_d.p'), 0)})" if best_d else "N/A"
        self._card(mvp_f, t("dashboard.card_top_driver"), d_val, 2, 0, Theme.PURPLE_SOFT)

        if HAS_PLOT and monthly: self._draw_chart(mid_f, monthly)

        right_f = tk.Frame(main_body, bg=Theme.SURFACE, width=350, highlightthickness=1, highlightbackground=Theme.BORDER)
        right_f.pack(side="right", fill="y", padx=(20, 0)); right_f.pack_propagate(False)
        tk.Label(right_f, text=f"🔔 {t('dashboard.section_alerts')}", font=("Segoe UI", 10, "bold"), bg=Theme.SURFACE, fg=Theme.ACCENT).pack(pady=15)
        
        canv = tk.Canvas(right_f, bg=Theme.SURFACE, highlightthickness=0); sb = ttk.Scrollbar(right_f, orient="vertical", command=canv.yview)
        act = tk.Frame(canv, bg=Theme.SURFACE); act.bind("<Configure>", lambda e: canv.configure(scrollregion=canv.bbox("all")))
        canv.create_window((0,0), window=act, anchor="nw", width=330); canv.configure(yscrollcommand=sb.set); canv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        if not alerts: tk.Label(act, text=t("dashboard.no_alerts"), bg=Theme.SURFACE, fg=Theme.MUTED).pack(pady=20)
        else:
            for a in alerts:
                c = Theme.DANGER if a['type'] == "RED" else Theme.WARNING
                b = tk.Frame(act, bg=Theme.SURFACE2, pady=8, padx=10, highlightthickness=1, highlightbackground=c)
                b.pack(fill="x", pady=4, padx=5); tk.Label(b, text=a['msg'], bg=Theme.SURFACE2, fg=Theme.TEXT, font=("Segoe UI", 8), wraplength=280, justify="left").pack()

        tk.Label(right_f, text=t("dashboard.total_overdue").format(total_overdue), bg=Theme.SURFACE, fg=Theme.DANGER, font=("Segoe UI", 9, "bold")).pack(pady=15)

    def _kpi_card(self, p, t, v, c, col):
        f = tk.Frame(p, bg=Theme.SURFACE, width=220, height=130, highlightthickness=2, highlightbackground=c)
        f.grid(row=0, column=col, padx=6); f.grid_propagate(False)
        tk.Label(f, text=t.upper(), bg=Theme.SURFACE, fg=Theme.MUTED, font=("Segoe UI", 8, "bold")).pack(pady=(25,0))
        tk.Label(f, text=v, bg=Theme.SURFACE, fg=Theme.TEXT, font=("Segoe UI", 17, "bold")).pack(expand=True)

    def _card(self, p, t, v, r, c, col=Theme.TEXT):
        f = tk.Frame(p, bg=Theme.SURFACE, width=240, height=110, highlightthickness=1, highlightbackground=Theme.BORDER)
        f.grid(row=r, column=c, padx=6, pady=6); f.grid_propagate(False)
        tk.Label(f, text=t, bg=Theme.SURFACE, fg=Theme.MUTED, font=("Segoe UI", 9)).pack(pady=(18,0))
        tk.Label(f, text=v, bg=Theme.SURFACE, fg=col, font=("Segoe UI", 12, "bold"), justify="center").pack(expand=True)

    def _draw_chart(self, p, d):
        fig, ax = plt.subplots(figsize=(6, 4), dpi=90); fig.patch.set_facecolor(Theme.BG); ax.set_facecolor(Theme.SURFACE)
        ax.bar([x['month'] for x in d], [x['p'] for x in d], color=Theme.ACCENT)
        ax.set_title(t("dashboard.chart_profit_evolution"), color=Theme.TEXT, fontsize=9); ax.tick_params(colors=Theme.TEXT, labelsize=8)
        canvas = FigureCanvasTkAgg(fig, master=p); canvas.draw(); canvas.get_tk_widget().pack(side="right", fill="both", expand=True)
        self._chart_ax = ax
        self._chart_canvas = canvas
