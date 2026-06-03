import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, ttk
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from services.i18n import t, register_listener, unregister_listener
from services.analytics_service import AnalyticsService
from ui.styles import Theme
from ui.theme import COLORS, CHART_PRIMARY, CHART_SECONDARY, CHART_INDIGO, FONTS, apply_chart_style
from ui.widgets import StyledEntry, ActionButton
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class AnalyticsView:
    def __init__(self, parent, db, prefs=None, embedded=False):
        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.configure(fg_color=Theme.BG)
            if self.win:
                self.win.title(f"\U0001f4c8 {t('analytics.title')}")
            self.win.geometry("1400x850")
            Theme.apply(self.win)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        self.db = db
        self.analytics_service = AnalyticsService(db)
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self._i18n_widgets = []
        self._chart_texts = []
        self._leg_lines = []
        self._pie_texts = []
        self._pie_keys = []
        self._fig = None
        self._canvas = None
        self._axes = None
        self._no_data_text = None

        now = datetime.now()
        self._start_date = now.replace(day=1, hour=0, minute=0, second=0)
        self._end_date = now

        self._setup_ui()
        self._load_data()
        if self.win:
            self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win:
            if self.win:
                self.win.title(f"📈 {t('analytics.title')}")
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        for text_obj, key in self._chart_texts:
            try:
                text_obj.set_text(t(key))
            except Exception:
                pass
        for line, key in self._leg_lines:
            try:
                line.set_label(t(key))
            except Exception:
                pass
        for text_obj, key in zip(self._pie_texts, self._pie_keys):
            try:
                text_obj.set_text(t(key))
            except Exception:
                pass
        if self._no_data_text is not None:
            try:
                self._no_data_text.set_text(t("analytics.no_financial_data"))
            except Exception:
                pass
        if self._fig is not None and self._canvas is not None:
            try:
                if self._leg_lines:
                    for ax in self._axes.flat:
                        try:
                            ax.legend()
                        except Exception:
                            pass
                self._fig.tight_layout()
                self._canvas.draw_idle()
            except Exception:
                pass

    def _build_period_controls(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=Theme.SURFACE)
        bar.pack(fill="x", padx=12, pady=(8, 4))

        prev_btn = ActionButton(bar, "\u25c0", self._prev_month, color=Theme.SURFACE2, width=3)
        prev_btn.pack(side="left", padx=(12, 4))

        self._period_lbl = ctk.CTkLabel(bar, text="", fg_color=Theme.SURFACE, text_color=Theme.TEXT,
                                     font=FONTS["small"])
        self._period_lbl.pack(side="left", padx=8)

        next_btn = ActionButton(bar, "\u25b6", self._next_month, color=Theme.SURFACE2, width=3)
        next_btn.pack(side="left", padx=4)

        ctk.CTkLabel(bar, text=" | ", fg_color=Theme.SURFACE, text_color=Theme.MUTED).pack(side="left", padx=8)

        from_lbl = ctk.CTkLabel(bar, text=t("common.from_date"), fg_color=Theme.SURFACE, text_color=Theme.TEXT, font=FONTS["label"])
        from_lbl.pack(side="left", padx=4)
        self._i18n_tag(from_lbl, "common.from_date")
        self._from_entry = StyledEntry(bar, width=12)
        self._from_entry.pack(side="left", padx=4)
        self._from_entry.insert(0, self._start_date.strftime("%d/%m/%Y"))

        to_lbl = ctk.CTkLabel(bar, text=t("common.to_date"), fg_color=Theme.SURFACE, text_color=Theme.TEXT, font=FONTS["label"])
        to_lbl.pack(side="left", padx=4)
        self._i18n_tag(to_lbl, "common.to_date")
        self._to_entry = StyledEntry(bar, width=12)
        self._to_entry.pack(side="left", padx=4)
        self._to_entry.insert(0, self._end_date.strftime("%d/%m/%Y"))

        apply_btn = ActionButton(bar, t("dispatch_board.retry"), self._apply_custom, color=Theme.ACCENT, width=6)
        apply_btn.pack(side="left", padx=8)

        self._update_period_label()

    def _update_period_label(self):
        self._period_lbl.configure(text=self._start_date.strftime("%B %Y"))

    def _prev_month(self):
        try:
            self._start_date = self._start_date - relativedelta(months=1)
            self._end_date = self._start_date + relativedelta(months=1) - timedelta(days=1)
            if self._end_date > datetime.now():
                self._end_date = datetime.now()
            self._from_entry.delete(0, "end")
            self._from_entry.insert(0, self._start_date.strftime("%d/%m/%Y"))
            self._to_entry.delete(0, "end")
            self._to_entry.insert(0, self._end_date.strftime("%d/%m/%Y"))
            self._update_period_label()
            self._load_data()
        except Exception:
            pass

    def _next_month(self):
        try:
            candidate = self._start_date + relativedelta(months=1)
            if candidate > datetime.now():
                return
            self._start_date = candidate
            self._end_date = self._start_date + relativedelta(months=1) - timedelta(days=1)
            if self._end_date > datetime.now():
                self._end_date = datetime.now()
            self._from_entry.delete(0, "end")
            self._from_entry.insert(0, self._start_date.strftime("%d/%m/%Y"))
            self._to_entry.delete(0, "end")
            self._to_entry.insert(0, self._end_date.strftime("%d/%m/%Y"))
            self._update_period_label()
            self._load_data()
        except Exception:
            pass

    def _apply_custom(self):
        try:
            from_date = datetime.strptime(self._from_entry.get().strip(), "%d/%m/%Y")
            to_date = datetime.strptime(self._to_entry.get().strip(), "%d/%m/%Y")
            self._start_date = from_date
            self._end_date = to_date
            self._update_period_label()
            self._load_data()
        except ValueError:
            messagebox.showwarning(t("analytics.title"), t("analytics.invalid_date_format"))

    def _setup_ui(self):
        self._build_period_controls(self.frame)
        self._chart_container = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        self._chart_container.pack(fill="both", expand=True, padx=12, pady=4)

    def _load_data(self):
        if self._fig:
            for ax in self._axes.flat:
                ax.clear()
        else:
            for w in self._chart_container.winfo_children():
                w.destroy()
        self._chart_texts.clear()
        self._leg_lines.clear()
        self._pie_texts.clear()
        self._pie_keys.clear()
        self._no_data_text = None

        try:
            from_date = self._start_date.strftime("%d/%m/%Y")
            to_date = self._end_date.strftime("%d/%m/%Y")

            p_truck, p_driver, rev_exp = self.analytics_service.get_data(from_date, to_date)
            from repositories.trip_repository import TripRepository
            repo = TripRepository(self.db)
            filtered = repo.get_by_date_range(from_date, to_date)

            if not filtered and not p_truck and not p_driver and not rev_exp:
                lbl = ctk.CTkLabel(self._chart_container, text=t("analytics.empty_state"),
                               fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["body"])
                lbl.pack(expand=True)
                self._i18n_tag(lbl, "analytics.empty_state")
                return

            truck_profits = {}
            driver_profits = {}
            for row in filtered:
                truck = row.get("truck_number") or t("common.unknown")
                driver = row.get("driver_name") or t("common.unknown")
                profit = float(row.get("net_profit") or 0)
                truck_profits[truck] = truck_profits.get(truck, 0) + profit
                driver_profits[driver] = driver_profits.get(driver, 0) + profit

            if not self._fig:
                fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=90)
                fig.patch.set_facecolor(Theme.BG)
                self._fig = fig
                self._axes = axes
            else:
                fig, axes = self._fig, self._axes

            ax1 = axes[0, 0]
            apply_chart_style(fig, ax1)
            if truck_profits:
                sorted_trucks = sorted(truck_profits.items(), key=lambda x: x[1], reverse=True)[:8]
                trucks = [x[0] for x in sorted_trucks]
                profits_t = [x[1] for x in sorted_trucks]
                bars = ax1.barh(trucks, profits_t, color=CHART_PRIMARY, height=0.6)
                max_idx = profits_t.index(max(profits_t))
                bars[max_idx].set_color(CHART_SECONDARY)
            title1 = ax1.set_title(t("analytics.chart_top_trucks"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title1, "analytics.chart_top_trucks"))

            ax2 = axes[0, 1]
            apply_chart_style(fig, ax2)
            if rev_exp:
                months = [str(x['month']) for x in rev_exp]
                revs = [float(x['rev']) for x in rev_exp]
                exps = [float(x['exp']) for x in rev_exp]
                line1 = ax2.plot(months, revs, marker='o', label=t("analytics.legend_revenue"),
                                 color=CHART_PRIMARY, linewidth=2, markerfacecolor=CHART_SECONDARY,
                                 markeredgecolor="none")[0]
                line2 = ax2.plot(months, exps, marker='o', label=t("analytics.legend_expenses"),
                                 color=CHART_INDIGO, linewidth=2, markerfacecolor=COLORS["accent"],
                                 markeredgecolor="none")[0]
                ax2.fill_between(months, revs, alpha=0.12, color=CHART_PRIMARY)
                self._leg_lines = [(line1, "analytics.legend_revenue"), (line2, "analytics.legend_expenses")]
                ax2.legend(fontsize=8, facecolor=Theme.SURFACE, labelcolor='white')
            title2 = ax2.set_title(t("analytics.chart_revenue_vs_expenses"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title2, "analytics.chart_revenue_vs_expenses"))

            ax3 = axes[1, 0]
            apply_chart_style(fig, ax3)
            if driver_profits:
                sorted_drivers = sorted(driver_profits.items(), key=lambda x: x[1], reverse=True)[:8]
                drivers = [x[0] for x in sorted_drivers]
                profits_d = [x[1] for x in sorted_drivers]
                bars = ax3.bar(drivers, profits_d, color=CHART_PRIMARY, width=0.6)
                max_idx = profits_d.index(max(profits_d))
                bars[max_idx].set_color(CHART_SECONDARY)
                ax3.tick_params(axis='x', rotation=30)
            title3 = ax3.set_title(t("analytics.chart_profit_per_driver"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title3, "analytics.chart_profit_per_driver"))

            ax4 = axes[1, 1]
            apply_chart_style(fig, ax4)
            total_profit = sum(truck_profits.values()) if truck_profits else 0
            total_exp = sum([float(x['exp']) for x in rev_exp]) if rev_exp else 0
            if total_profit + total_exp > 0:
                sizes = [max(0, total_profit), max(0, total_exp)]
                patches, texts, autotexts = ax4.pie(sizes, labels=[t("analytics.pie_profit"), t("analytics.pie_expenses")],
                        autopct='%1.1f%%', colors=[CHART_PRIMARY, CHART_INDIGO],
                        textprops={'color':"w", 'fontsize':9}, startangle=140)
                self._pie_texts = texts
                self._pie_keys = ["analytics.pie_profit", "analytics.pie_expenses"]
            else:
                self._no_data_text = ax4.text(0.5, 0.5, t("analytics.no_financial_data"),
                                              color=Theme.MUTED, ha='center')
            title4 = ax4.set_title(t("analytics.chart_profit_expenses_ratio"), color=Theme.TEXT, fontsize=10)
            self._chart_texts.append((title4, "analytics.chart_profit_expenses_ratio"))

            fig.tight_layout()
            if self._canvas:
                self._canvas.draw()
            else:
                canvas = FigureCanvasTkAgg(fig, master=self._chart_container)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)
                self._canvas = canvas

        except Exception as e:
            msg = t("analytics.render_error")
            try:
                msg = msg.format(e)
            except Exception:
                msg = f"{msg}: {e}"
            lbl = ctk.CTkLabel(self._chart_container, text=msg,
                           fg_color=Theme.BG, text_color=Theme.DANGER)
            lbl.pack(expand=True)
