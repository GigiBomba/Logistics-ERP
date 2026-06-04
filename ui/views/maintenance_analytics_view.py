import tkinter as tk
import customtkinter as ctk
from tkinter import ttk
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from services.fleet_maintenance_service import FleetMaintenanceService, MaintType, MAINT_DISPLAY
from repositories.fleet_repository import FleetRepository
from database.db_manager import DatabaseManager
from ui.styles import Theme
from ui.widgets import ActionButton
from services.i18n import t
import ui.icons as icons
from services import i18n

from ui.theme import CHART_PALETTE as COLOR_CYCLE, CHART_PRIMARY, CHART_SECONDARY, FONTS, apply_chart_style


class MaintenanceAnalyticsView:
    def __init__(self, parent, db, embedded=False):
        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.configure(fg_color=Theme.BG)
            self.win.title(icons.iconed("maint_analytics.title"))
            self.win.geometry("1400x850")
            Theme.apply(self.win)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)

        self.db = db
        self.repo = FleetRepository(db)
        self.service = FleetMaintenanceService(db)

        self._fig_ref = None
        self._canvas_ref = None
        self._tree_ref = None
        self._i18n_widgets = []
        self._tree_heading_keys = []

        self._build_ui()
        self._load_data()
        if self.win:
            self.win.bind("<Destroy>", self._on_destroy)
        i18n.register_listener(self._on_language_changed)

    def _on_destroy(self, e=None):
        if e is not None and e.widget != self.win:
            return
        i18n.unregister_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_language_changed(self, lang):
        if self.win:
            self.win.title(icons.iconed("maint_analytics.title"))
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{(icons.iconed(key) if key.startswith('maint') else t(key))}")
            except Exception:
                pass
        self._load_data()

    def _build_ui(self):
        top = ctk.CTkFrame(self.frame, fg_color=Theme.SURFACE)
        top.pack(fill="x")
        self._title_lbl = ctk.CTkLabel(top, text=icons.iconed("maint_analytics.title"),
                                       fg_color=Theme.SURFACE, text_color=Theme.TEXT,
                                       font=FONTS["h2"])
        self._title_lbl.pack(side="left")
        self._i18n_tag(self._title_lbl, "maint_analytics.title")
        self._refresh_btn = ActionButton(top, icons.iconed("maint.refresh"),
                                         self._load_data, color=Theme.ACCENT)
        self._refresh_btn.pack(side="right", padx=4)
        self._i18n_tag(self._refresh_btn, "maint.refresh")

        self._chart_frame = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        self._chart_frame.pack(fill="both", expand=True, padx=12, pady=6)

        self._table_frame = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        self._table_frame.pack(fill="both", padx=12, pady=(0, 12))

    def _load_data(self):
        now = datetime.now()
        twelve_ago = now - timedelta(days=365)
        ytd_start = datetime(now.year, 1, 1)

        since_charts = twelve_ago.strftime("%Y-%m-%d")
        since_ytd = ytd_start.strftime("%Y-%m-%d")

        self._truck_map: Dict[int, str] = {}
        for rec in self.repo.get_all():
            self._truck_map[rec["id"]] = rec.get("plate_number", icons.iconed("maint_analytics.truck_fallback", rec['id']))

        self._cost_by_truck_month = self.repo.get_maintenance_cost_truck_monthly(since_charts)
        self._cost_by_month = self.repo.get_maintenance_cost_monthly(since_charts)
        self._truck_summary = self.repo.get_maintenance_truck_summary(since_ytd)
        self._top_categories = self.repo.get_maintenance_most_expensive_category(since_ytd)

        self._render_charts()
        self._render_table()

    def _render_charts(self):
        for w in self._chart_frame.winfo_children():
            w.destroy()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
        fig.patch.set_facecolor(Theme.BG)
        for ax in (ax1, ax2):
            apply_chart_style(fig, ax)

        self._draw_cost_by_truck_month(ax1)
        self._draw_fleet_trend(ax2)

        fig.tight_layout(pad=3)
        canvas = FigureCanvasTkAgg(fig, self._chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._fig_ref = fig
        self._canvas_ref = canvas

    def _draw_cost_by_truck_month(self, ax):
        ax.set_title(icons.iconed("maint_analytics.chart_cost_per_truck"), color=Theme.TEXT, fontsize=10)

        if not self._cost_by_truck_month:
            ax.text(0.5, 0.5, icons.iconed("maint_analytics.no_records"), color=Theme.MUTED,
                    ha="center", va="center", transform=ax.transAxes)
            return

        months = sorted(set(r["ym"] for r in self._cost_by_truck_month))
        truck_ids = sorted(set(r["truck_id"] for r in self._cost_by_truck_month))

        lookup: Dict[tuple, float] = {}
        for r in self._cost_by_truck_month:
            lookup[(r["truck_id"], r["ym"])] = r["total"]

        x = list(range(len(months)))
        n = len(truck_ids)
        w = 0.8 / n

        for i, tid in enumerate(truck_ids):
            vals = [lookup.get((tid, m), 0) for m in months]
            color = COLOR_CYCLE[i % len(COLOR_CYCLE)]
            label = self._truck_map.get(tid, icons.iconed("maint_analytics.truck_fallback", tid))
            ax.bar([xi + i * w - 0.4 + w / 2 for xi in x], vals, w,
                   label=label, color=color, edgecolor=Theme.BG, linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels([_label_month(m) for m in months], rotation=45, ha="right", fontsize=7)
        ax.set_ylabel(icons.iconed("maint_analytics.cost_label"), color=Theme.MUTED, fontsize=8)
        ax.legend(fontsize=6, facecolor=Theme.SURFACE2, labelcolor=Theme.TEXT, edgecolor=Theme.SURFACE2)

    def _draw_fleet_trend(self, ax):
        ax.set_title(icons.iconed("maint_analytics.chart_fleet_trend"), color=Theme.TEXT, fontsize=10)

        if not self._cost_by_month:
            ax.text(0.5, 0.5, icons.iconed("maint_analytics.no_data_12mo"), color=Theme.MUTED,
                    ha="center", va="center", transform=ax.transAxes)
            return

        months = [r["ym"] for r in self._cost_by_month]
        totals = [r["total"] for r in self._cost_by_month]

        ax.plot(range(len(months)), totals, marker="o", color=CHART_PRIMARY, linewidth=2, markersize=5,
                markerfacecolor=CHART_SECONDARY, markeredgecolor="none")
        ax.fill_between(range(len(months)), totals, alpha=0.12, color=CHART_PRIMARY)

        ax.set_xticks(range(len(months)))
        ax.set_xticklabels([_label_month(m) for m in months], rotation=45, ha="right", fontsize=7)
        ax.set_ylabel(icons.iconed("maint_analytics.total_cost_label"), color=Theme.MUTED, fontsize=8)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"\u20AC{v:,.0f}"))

    def _render_table(self):
        for w in self._table_frame.winfo_children():
            w.destroy()

        top_cat_map: Dict[int, str] = {}
        for r in self._top_categories:
            raw = r.get("maintenance_type", "")
            try:
                disp = MAINT_DISPLAY.get(MaintType(raw), raw.replace("_", " ").title())
            except ValueError:
                disp = raw.replace("_", " ").title()
            top_cat_map[r["truck_id"]] = disp

        self._tree_heading_keys.clear()
        cols = ("truck", "ytd_cost", "avg_cost", "count", "top_category")
        tree = ttk.Treeview(self._table_frame, columns=cols, show="headings", height=8)
        col_headings = [
            ("truck", "maint_analytics.col_truck", "Truck"),
            ("ytd_cost", "maint_analytics.col_ytd_cost", "YTD Cost"),
            ("avg_cost", "maint_analytics.col_avg_cost", "Avg. Cost"),
            ("count", "maint_analytics.col_count", "Services"),
            ("top_category", "maint_analytics.col_top_category", "Top Category"),
        ]
        for col, key, heading in col_headings:
            tree.heading(col, text=t(key, default=heading))
            self._tree_heading_keys.append((col, key))
        tree.column("truck", width=120)
        tree.column("ytd_cost", width=140, anchor="e")
        tree.column("avg_cost", width=140, anchor="e")
        tree.column("count", width=100, anchor="center")
        tree.column("top_category", width=180)

        if not self._truck_summary:
            tree.insert("", "end", values=(icons.iconed("maint_analytics.no_data"), "", "", "", ""))
        else:
            for r in self._truck_summary:
                tid = r["truck_id"]
                plate = self._truck_map.get(tid, icons.iconed("maint_analytics.truck_fallback", tid))
                tree.insert("", "end", values=(
                    plate,
                    f"\u20AC{r['total_ytd']:,.2f}",
                    f"\u20AC{r['avg_cost']:,.2f}",
                    r["service_count"],
                    top_cat_map.get(tid, "\u2014"),
                ))

        sb = ttk.Scrollbar(self._table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")
        self._tree_ref = tree


_MONTH_KEYS = [
    "maint_analytics.month_jan", "maint_analytics.month_feb",
    "maint_analytics.month_mar", "maint_analytics.month_apr",
    "maint_analytics.month_may", "maint_analytics.month_jun",
    "maint_analytics.month_jul", "maint_analytics.month_aug",
    "maint_analytics.month_sep", "maint_analytics.month_oct",
    "maint_analytics.month_nov", "maint_analytics.month_dec",
]
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def _label_month(ym: str) -> str:
    try:
        parts = ym.split("-")
        m = int(parts[1])
        return f"{t(_MONTH_KEYS[m - 1], default=_MONTH_NAMES[m - 1])} {parts[0][2:]}"
    except Exception:
        return ym
