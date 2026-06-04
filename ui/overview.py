"""Overview / Home Dashboard — premium card-based layout."""
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk
import logging
from datetime import datetime, timedelta
import calendar

import numpy as np

from ui.theme import (
    COLORS, FONTS, S, RADIUS_CARD, RADIUS_CHIP,
    card, card_header, kpi_card, divider,
)
from services.i18n import t, register_listener, unregister_listener
from services.operations.event_bus import (
    EventBus, TRIP_CREATED, TRIP_STATUS_CHANGED, TRIP_UPDATED,
    ALERT_CREATED, ALERT_RESOLVED, TRUCK_UPDATED,
)
from repositories.trip_repository import TripRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from services.invoicing.config_manager import load_company_config

logger = logging.getLogger(__name__)

# Matplotlib imports (lazy on first use)
_plt = None
_animation = None
_FigureCanvasTkAgg = None


def _import_mpl():
    global _plt, _animation, _FigureCanvasTkAgg
    if _plt is None:
        import warnings
        warnings.filterwarnings(
            "ignore",
            message="Animation was deleted without rendering anything",
            category=UserWarning,
        )
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        plt.ioff()
        import matplotlib.animation as animation
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        _plt = plt
        _animation = animation
        _FigureCanvasTkAgg = FigureCanvasTkAgg
    return _plt, _animation, _FigureCanvasTkAgg


class OverviewDashboard(ctk.CTkFrame):

    def __init__(self, parent, db, ops=None, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_base"], **kwargs)
        self.db = db
        self.ops = ops
        self._event_bus = EventBus()
        self._trip_repo = TripRepository(db)
        self._fleet_repo = FleetRepository(db)
        self._driver_repo = DriverRepository(db)
        self._handlers = {}
        self._last_refresh_ts = 0
        self._i18n_widgets = []
        self._anim_after_id = None
        self._resize_after_id = None
        self._chart_last_size = None
        self._profit_fig = None
        self._profit_canvas = None
        self._profit_ani = None
        register_listener(self._on_language_changed)

        self._build_ui()
        self._subscribe_events()
        self.refresh()

    # ── UI Layout ─────────────────────────────────────────────────────

    def _build_ui(self):
        self.configure(fg_color=COLORS["bg_base"])

        # ── HEADER (fixed, 64px) ──
        self._build_header()

        # ── KPI STRIP (fixed) ──
        self._build_kpi_strip()

        # ── MAIN CONTENT (scrollable, 2 columns) ──
        self._build_main_content()

    def _build_header(self):
        header = ctk.CTkFrame(self,
                              fg_color=COLORS["bg_surface"],
                              corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Bottom border
        ctk.CTkFrame(header, fg_color=COLORS["border"],
                     height=1, corner_radius=0).pack(
                         side="bottom", fill="x")

        content = ctk.CTkFrame(header, fg_color="transparent")
        content.pack(fill="both", expand=True,
                     padx=S["10"])

        # App name
        ctk.CTkLabel(content,
                     text="Operion ERP",
                     font=FONTS["display"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(side="left",
                                        anchor="center")

        # Company name
        conf = load_company_config()
        company = conf.get("company_name", "")
        if company:
            ctk.CTkLabel(content,
                         text=f"— {company}",
                         font=FONTS["body"],
                         text_color=COLORS["text_muted"],
                         anchor="w").pack(side="left",
                                            padx=(S["3"], 0),
                                            anchor="center")

        # Right: current date
        date_str = datetime.now().strftime("%A, %d %B %Y")
        ctk.CTkLabel(content,
                     text=date_str,
                     font=FONTS["small"],
                     text_color=COLORS["text_muted"],
                     anchor="e").pack(side="right",
                                      anchor="center")

    def _build_kpi_strip(self):
        strip = ctk.CTkFrame(self,
                             fg_color=COLORS["bg_base"])
        strip.pack(fill="x", padx=S["10"],
                   pady=(S["6"], 0))

        for i in range(6):
            strip.columnconfigure(i, weight=1, uniform="kpi")

        kpis = [
            ("kpi_active_trucks",  "TRUCKS",       "0",
             COLORS["accent_text"]),
            ("kpi_trips_today",    "TRIPS",        "0",  None),
            ("kpi_drivers_road",   "DRIVERS",      "0",  None),
            ("kpi_open_alerts",    "ALERTS",       "0",
             COLORS["text_warning"]),
            ("kpi_revenue",        "REVENUE",      "€ 0",
             COLORS["text_success"]),
            ("kpi_unpaid",         "UNPAID",       "0",
             COLORS["text_danger"]),
        ]
        self._kpi_widgets: dict = {}
        for i, (key, label, default, color) in enumerate(kpis):
            card_outer = kpi_card(strip, label, default,
                                  value_color=color)
            card_outer.grid(row=0, column=i,
                            sticky="ew",
                            padx=(0 if i == 0 else S["2"], 0),
                            pady=(0, 0))
            self._kpi_widgets[key] = card_outer

    def _build_main_content(self):
        main = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_base"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_hover"]
        )
        main.pack(fill="both", expand=True,
                  padx=S["10"], pady=S["6"])

        main.columnconfigure(0, weight=62)
        main.columnconfigure(1, weight=38)

        # Left column
        left = ctk.CTkFrame(main, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew",
                  padx=(0, S["4"]))

        # Right column
        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        self._build_profit_chart(left)
        self._build_active_trips(left)

        self._build_alert_strip(right)
        self._build_top_trucks(right)
        self._build_recent_activity(right)

    # ── Profit chart (left, top) ──────────────────────────────────────

    def _build_profit_chart(self, parent):
        c = card(parent)
        c._outer.pack(fill="x", pady=(0, S["3"]))

        # Header row inside card
        hdr = ctk.CTkFrame(c, fg_color="transparent", height=34)
        hdr.pack(fill="x", padx=S["5"], pady=(S["5"], S["1"]))
        hdr.pack_propagate(False)

        title_lbl = ctk.CTkLabel(
            hdr,
            text=t("home.profit_chart_title"),
            font=FONTS["h3"],
            text_color=COLORS["text_primary"]
        )
        title_lbl.place(relx=0.0, rely=0.5, anchor="w")
        self._i18n_tag(title_lbl, "home.profit_chart_title")

        today = datetime.now()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        month_label = last_month_start.strftime("%B %Y")

        self._month_lbl_ref = ctk.CTkLabel(
            hdr, text=month_label,
            font=FONTS["label"],
            text_color=COLORS["text_muted"]
        )
        self._month_lbl_ref.place(relx=1.0, rely=0.5, anchor="e")

        # Chart container
        chart_area = ctk.CTkFrame(c, fg_color="transparent")
        chart_area.pack(fill="x", padx=S["3"],
                        pady=(0, S["5"]))
        self._chart_container = chart_area

        # Footer
        footer = ctk.CTkLabel(
            c,
            text=t("home.profit_data_source"),
            font=FONTS["label"],
            text_color=COLORS["text_muted"]
        )
        footer.pack(anchor="w", padx=S["5"], pady=(0, S["3"]))
        self._i18n_tag(footer, "home.profit_data_source")

        self._last_month_start = last_month_start
        self._last_month_end = last_month_end

    # ── Active trips (left, bottom, compact) ──────────────────────────

    def _build_active_trips(self, parent):
        c = card(parent)
        c._outer.pack(fill="x", pady=(0, S["3"]))

        hdr_row = ctk.CTkFrame(c, fg_color="transparent")
        hdr_row.pack(fill="x", padx=S["5"],
                     pady=(S["5"], S["3"]))
        ctk.CTkLabel(hdr_row, text=t("home.active_trips"),
                     font=FONTS["h3"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(side="left")

        self._trips_count = ctk.CTkLabel(
            hdr_row, text="0",
            font=FONTS["label"],
            fg_color=COLORS["bg_elevated"],
            text_color=COLORS["text_muted"],
            corner_radius=99, width=22, height=18
        )
        self._trips_count.pack(side="left", padx=(S["2"], 0))

        divider(c)

        self._trips_list = ctk.CTkScrollableFrame(
            c, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            height=220
        )
        self._trips_list.pack(fill="x",
                               padx=S["2"],
                               pady=S["2"])

    # ── Alert strip (right, top) ──────────────────────────────────────

    def _build_alert_strip(self, parent):
        c = card(parent)
        c._outer.pack(fill="x", pady=(0, S["3"]))
        card_header(c, t("home.active_alerts"))

        self._alerts_frame = ctk.CTkFrame(c, fg_color="transparent")
        self._alerts_frame.pack(fill="x", padx=S["5"],
                                 pady=(S["3"], S["5"]))

    # ── Top trucks (right, middle) ────────────────────────────────────

    def _build_top_trucks(self, parent):
        c = card(parent)
        c._outer.pack(fill="x", pady=(0, S["3"]))
        card_header(c, t("home.top_trucks"))

        self._top_trucks_frame = ctk.CTkFrame(c, fg_color="transparent")
        self._top_trucks_frame.pack(fill="x", padx=S["5"],
                                     pady=(S["3"], S["5"]))

    # ── Recent activity (right, bottom) ───────────────────────────────

    def _build_recent_activity(self, parent):
        c = card(parent)
        c._outer.pack(fill="x", pady=(0, S["3"]))
        card_header(c, t("home.recent_activity"))

        self._activity_frame = ctk.CTkFrame(c, fg_color="transparent")
        self._activity_frame.pack(fill="x", padx=S["5"],
                                  pady=(S["3"], S["5"]))

    # ── Chart rendering ───────────────────────────────────────────────

    def _render_profit_chart(self, _deferred=False, _force=False):
        import time
        now = time.time()
        if not _force and getattr(self, "_chart_render_ts", 0) and now - self._chart_render_ts < 0.8:
            logger.debug("[HOME] Chart render debounced")
            return

        plt, animation_mod, FigureCanvasTkAgg = _import_mpl()

        self._chart_container.update_idletasks()
        if self._chart_container.winfo_width() < 10 and not _deferred:
            self.after(150, lambda: self._render_profit_chart(_deferred=True))
            return

        for w in self._chart_container.winfo_children():
            w.destroy()
        if self._profit_fig is not None:
            try:
                plt.close(self._profit_fig)
            except Exception:
                pass
            self._profit_fig = None

        profit_map = {}
        try:
            raw_data = self._trip_repo.get_daily_profit(
                self._last_month_start.strftime("%Y-%m-%d"),
                self._last_month_end.strftime("%Y-%m-%d")
            )
            for d, p in raw_data:
                try:
                    day = int(d.split("-")[2]) if "-" in d else int(d)
                    profit_map[day] = float(p or 0)
                except (ValueError, IndexError):
                    pass
        except Exception as exc:
            logger.exception("[HOME] Data fetch failed: %s", exc)

        days_in_month = calendar.monthrange(
            self._last_month_start.year, self._last_month_start.month
        )[1]
        days = list(range(1, days_in_month + 1))
        profits = [profit_map.get(d, 0.0) for d in days]

        if not profit_map or all(p == 0 for p in profits):
            msg = t("home.profit_no_data",
                    default="No profit data available yet.\nComplete trips to see analytics.")
            ctk.CTkLabel(self._chart_container,
                         text=msg,
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"],
                         justify="center"
                         ).pack(expand=True)
            self._chart_render_ts = now
            return

        self._chart_render_ts = now

        self._chart_container.update_idletasks()
        cw = max(self._chart_container.winfo_width(), 300)
        ch = max(self._chart_container.winfo_height(), 180)
        self._chart_last_size = (cw, ch)

        dpi = 100
        fig_w = cw / dpi
        fig_h = ch / dpi

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        fig.patch.set_facecolor(COLORS["bg_surface"])
        ax.set_facecolor(COLORS["bg_surface"])

        fig.subplots_adjust(left=0.05, right=0.98, top=0.94, bottom=0.10)

        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS["border"])
            spine.set_linewidth(0.5)
        ax.tick_params(
            colors=COLORS["text_secondary"],
            labelsize=8,
            pad=4,
            length=3,
            width=0.5
        )
        ax.grid(
            axis="y",
            color=COLORS["border"],
            linewidth=0.4,
            linestyle="--",
            alpha=0.35
        )
        ax.set_axisbelow(True)

        nonzero = [p for p in profits if p != 0]
        if nonzero:
            y_min = min(0, min(nonzero) * 1.15)
            y_max = max(nonzero) * 1.20 if max(nonzero) > 0 else max(nonzero) * 0.80
        else:
            y_min, y_max = 0, 100
        y_pad = (y_max - y_min) * 0.05
        ax.set_ylim(y_min - y_pad, y_max + y_pad)
        ax.set_xlim(0.5, days_in_month + 0.5)

        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x_val, _: f"{x_val:,.0f}")
        )

        tick_step = max(1, days_in_month // 6)
        tick_positions = [1] + list(range(tick_step, days_in_month + 1, tick_step))
        if days_in_month not in tick_positions:
            tick_positions.append(days_in_month)
        ax.set_xticks(tick_positions)
        ax.set_xlabel(
            t("home.profit_day_label"),
            fontsize=8,
            color=COLORS["text_secondary"],
            labelpad=6
        )

        days_arr = np.array(days, dtype=float)
        profits_arr = np.array(profits, dtype=float)
        x_smooth, y_smooth = self._smooth_data(days_arr, profits_arr, num=len(days) * 20)

        line_color = COLORS.get("chart_green", "#4ADE80")
        fill_color = line_color

        ax.plot(
            x_smooth, y_smooth,
            color=line_color,
            linewidth=7.0,
            alpha=0.12,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=2,
        )
        ax.plot(
            x_smooth, y_smooth,
            color=line_color,
            linewidth=3.0,
            marker="o",
            markersize=5.0,
            markerfacecolor=line_color,
            markeredgecolor=COLORS["bg_surface"],
            markeredgewidth=1.5,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=3,
        )
        ax.fill_between(
            x_smooth, y_smooth, y2=y_min - y_pad,
            alpha=0.25, color=fill_color, zorder=2
        )

        canvas = FigureCanvasTkAgg(fig, master=self._chart_container)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.configure(bg=COLORS["bg_surface"])
        canvas_widget.pack(fill="both", expand=True)
        canvas.draw()

        canvas_widget.bind("<Configure>", self._on_chart_resize)

        self._profit_fig = fig
        self._profit_canvas = canvas
        self._profit_ani = None

    @staticmethod
    def _smooth_data(x, y, num=300):
        if len(x) < 2:
            return x, y
        x_dense = np.linspace(x[0], x[-1], num)
        y_dense = np.interp(x_dense, x, y)
        return x_dense, y_dense

    def _on_chart_resize(self, event=None):
        if self._resize_after_id:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
        self._resize_after_id = self.after(400, self._do_chart_resize)

    def _do_chart_resize(self):
        self._resize_after_id = None
        if not self.winfo_exists():
            return
        import time
        last_render = getattr(self, "_chart_render_ts", 0)
        if last_render and time.time() - last_render < 0.6:
            self._resize_after_id = self.after(350, self._do_chart_resize)
            return
        try:
            w = self._chart_container.winfo_width()
            h = self._chart_container.winfo_height()
        except tk.TclError:
            return
        if w < 100 or h < 80:
            return
        if self._chart_last_size:
            lw, lh = self._chart_last_size
            if abs(w - lw) < 40 and abs(h - lh) < 40:
                return
        self._render_profit_chart(_force=True)

    # ── Refresh / Data population ─────────────────────────────────────

    def refresh(self):
        now_ts = datetime.now().timestamp()
        if now_ts - self._last_refresh_ts < 2:
            return
        self._last_refresh_ts = now_ts

        self._refresh_kpis()
        self._render_profit_chart()
        self._refresh_active_trips()
        self._refresh_top_trucks()
        self._refresh_recent_activity()
        self._refresh_alerts()

    def _refresh_kpis(self):
        try:
            trucks = self._fleet_repo.get_all() if hasattr(self._fleet_repo, 'get_all') else []
            trips = self._trip_repo.get_all(limit=2000)
        except Exception:
            trucks = []
            trips = []
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        active_trucks = len([t for t in trucks
                               if t.get('status') == 'Active'
                               or t.get('active_status') == 1])
        trips_today = len([t for t in trips
                           if t.get('start_date') == today_str
                           or (t.get('status') in ['In Transit', 'Loading']
                               and t.get('created_at', '').startswith(today_str))])

        # Drivers on road = unique drivers in active trips
        active_drivers = set()
        for trip in trips:
            s = trip.get("status", "")
            if s not in ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"):
                d = trip.get("driver_name")
                if d:
                    active_drivers.add(d)

        # Revenue this month
        month_start = datetime.now().strftime("01/%m/%Y")
        revenue = sum(float(t.get("total_price_eur") or 0)
                        for t in trips
                        if t.get("start_date", "") >= month_start)

        # Unpaid trips
        unpaid = len([t for t in trips
                      if t.get("status") not in ("Paid", "Delivered", "Completed", "Done")])

        # Alerts
        alert_count = 0
        if self.ops:
            try:
                alerts = self.ops.get_active_alerts(limit=50)
                alert_count = len(alerts)
            except Exception:
                pass

        updates = {
            "kpi_active_trucks": str(active_trucks),
            "kpi_trips_today": str(trips_today),
            "kpi_drivers_road": str(len(active_drivers)),
            "kpi_open_alerts": str(alert_count),
            "kpi_revenue": f"€ {revenue:,.0f}",
            "kpi_unpaid": str(unpaid),
        }
        for key, value in updates.items():
            if key in self._kpi_widgets:
                # Find the value label inside the kpi_card and update it
                # kpi_card returns outer frame -> inner frame -> content frame
                # The value label is the second CTkLabel in the content frame
                try:
                    outer = self._kpi_widgets[key]
                    inner = outer.winfo_children()[0]  # inner frame
                    content = inner.winfo_children()[0]  # content frame
                    for w in content.winfo_children():
                        if isinstance(w, ctk.CTkLabel):
                            # Update the label that has mono_lg font (the value)
                            font = w.cget("font")
                            if font == FONTS["mono_lg"]:
                                w.configure(text=value)
                                break
                except Exception:
                    pass

    def _refresh_active_trips(self):
        for w in self._trips_list.winfo_children():
            w.destroy()

        try:
            trips = self._trip_repo.get_all(limit=200)
        except Exception:
            trips = []

        active = []
        for trip in trips:
            s = trip.get("status", "")
            if s not in ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"):
                active.append(trip)

        self._trips_count.configure(text=str(len(active)))

        if not active:
            ctk.CTkLabel(self._trips_list,
                         text=t("home.no_active_trips"),
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"]
                         ).pack(pady=S["8"])
            return

        for trip in active[:8]:
            row = ctk.CTkFrame(
                self._trips_list,
                fg_color=COLORS["bg_elevated"],
                corner_radius=RADIUS_CHIP,
                height=34
            )
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            plate = trip.get("truck_number", "—")
            ctk.CTkLabel(row, text=plate,
                         font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"],
                         width=72).pack(side="left",
                                        padx=(S["3"], 0))

            client = trip.get("client_name", "?")
            origin = trip.get("origin", "?")
            dest = trip.get("destination", "?")
            route = f"{origin} → {dest}" if origin != "?" else client
            if len(route) > 34:
                route = route[:31] + "…"
            ctk.CTkLabel(row, text=route,
                         font=FONTS["small"],
                         text_color=COLORS["text_secondary"],
                         anchor="w").pack(side="left",
                                          padx=S["3"],
                                          fill="x",
                                          expand=True)

            status = trip.get("status", "planned").lower().replace(" ", "_")
            chip_bg = COLORS.get(f"chip_{status}",
                                 COLORS["chip_idle"])
            ctk.CTkLabel(row, text=trip.get("status", "").title(),
                         font=FONTS["label"],
                         fg_color=chip_bg,
                         text_color=COLORS["text_primary"],
                         corner_radius=RADIUS_CHIP,
                         padx=S["2"], height=20
                         ).pack(side="right",
                                padx=(0, S["3"]))

    def _refresh_alerts(self):
        for w in self._alerts_frame.winfo_children():
            w.destroy()

        alerts = []
        if self.ops:
            try:
                alerts = self.ops.get_active_alerts(limit=5)
            except Exception:
                pass

        if not alerts:
            ctk.CTkLabel(self._alerts_frame, text=t("home.no_alerts"),
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"]
                         ).pack(pady=S["3"])
            return

        for a in alerts[:3]:
            row = ctk.CTkFrame(self._alerts_frame,
                               fg_color=COLORS["bg_elevated"],
                               corner_radius=RADIUS_CHIP,
                               height=30)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            sev_color = {
                "CRITICAL": COLORS["danger"],
                "WARNING": COLORS["warning"],
            }.get(getattr(a, "severity", "INFO"),
                  COLORS["info"])
            ctk.CTkLabel(row, text="●",
                         font=FONTS["small"],
                         text_color=sev_color,
                         width=20).pack(side="left",
                                        padx=(S["3"], 0))
            title = getattr(a, "title", getattr(a, "message", "Alert"))
            if len(title) > 40:
                title = title[:37] + "…"
            ctk.CTkLabel(row, text=title,
                         font=FONTS["small"],
                         text_color=COLORS["text_secondary"],
                         anchor="w").pack(side="left",
                                          padx=S["2"])

        if len(alerts) > 3:
            ctk.CTkLabel(self._alerts_frame,
                         text=f"+ {len(alerts)-3} more",
                         font=FONTS["label"],
                         text_color=COLORS["text_muted"]
                         ).pack(anchor="w",
                                pady=(S["2"], 0))

    def _refresh_top_trucks(self):
        for w in self._top_trucks_frame.winfo_children():
            w.destroy()

        try:
            now = datetime.now()
            month_start = now.replace(day=1).strftime("%Y-%m-%d")
            month_end = now.strftime("%Y-%m-%d")
            top = self._trip_repo.get_top_trucks_by_revenue(
                month_start, month_end, limit=4
            )
        except Exception:
            top = []

        if not top:
            ctk.CTkLabel(self._top_trucks_frame, text=t("common.no_data"),
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"]
                         ).pack(pady=S["4"])
            return

        for i, row in enumerate(top, 1):
            plate = row.get("truck_number", "—")
            revenue = float(row.get("revenue", 0))
            r = ctk.CTkFrame(self._top_trucks_frame,
                             fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=f"#{i}",
                         font=FONTS["body_bold"],
                         text_color=COLORS["accent_text"],
                         width=24).pack(side="left")
            ctk.CTkLabel(r, text=plate,
                         font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(side="left",
                                          padx=(S["2"], 0))
            ctk.CTkLabel(r, text=f"€ {revenue:,.0f}",
                         font=FONTS["mono"],
                         text_color=COLORS["text_success"],
                         anchor="e").pack(side="right")

    def _refresh_recent_activity(self):
        for w in self._activity_frame.winfo_children():
            w.destroy()

        try:
            recent = self._trip_repo.get_all(limit=6)
        except Exception:
            recent = []

        if not recent:
            ctk.CTkLabel(self._activity_frame, text=t("common.no_data"),
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"]
                         ).pack(pady=S["4"])
            return

        for trip in recent:
            profit = float(trip.get("net_profit", 0) or 0)
            plate = trip.get("truck_number", "—")
            client = trip.get("client_name", "—")
            date = trip.get("start_date", "") or trip.get("created_at", "")[:10]

            r = ctk.CTkFrame(self._activity_frame,
                             fg_color="transparent")
            r.pack(fill="x", pady=2)

            ctk.CTkLabel(r, text=date,
                         font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         width=70).pack(side="left",
                                        padx=(S["2"], 0))
            ctk.CTkLabel(r, text=plate,
                         font=FONTS["label"],
                         text_color=COLORS["text_primary"],
                         width=60).pack(side="left")
            ctk.CTkLabel(r, text=client[:18],
                         font=FONTS["label"],
                         text_color=COLORS["text_secondary"]
                         ).pack(side="left", padx=6)
            color = COLORS["success"] if profit > 0 else COLORS["danger"]
            ctk.CTkLabel(r, text=f"{profit:,.0f} €",
                         font=FONTS["label"],
                         text_color=color
                         ).pack(side="right", padx=(0, S["2"]))

    # ── Helpers ───────────────────────────────────────────────────────

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_language_changed(self, lang):
        try:
            self.after(0, self.refresh_translations)
        except tk.TclError:
            pass

    def refresh_translations(self):
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{t(key)}")
            except Exception:
                pass

    # ── Event handling ────────────────────────────────────────────────

    def _subscribe_events(self):
        events = {
            TRIP_CREATED: self._on_data_changed,
            TRIP_STATUS_CHANGED: self._on_data_changed,
            TRIP_UPDATED: self._on_data_changed,
            ALERT_CREATED: self._on_data_changed,
            ALERT_RESOLVED: self._on_data_changed,
            TRUCK_UPDATED: self._on_data_changed,
        }
        for ev_type, handler in events.items():
            self._event_bus.subscribe(ev_type, handler)
            self._handlers[ev_type] = handler
        logger.debug("OverviewDashboard subscribed to %d events", len(events))

    def _on_data_changed(self, ev):
        try:
            self.after(0, self.refresh)
        except tk.TclError:
            pass

    def shutdown(self):
        for after_id in (self._anim_after_id, self._resize_after_id):
            if after_id:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
        self._resize_after_id = None
        if self._profit_fig is not None:
            try:
                import matplotlib.pyplot as plt
                plt.close(self._profit_fig)
            except Exception:
                pass
        unregister_listener(self._on_language_changed)
        for ev_type, handler in list(self._handlers.items()):
            try:
                self._event_bus.unsubscribe(ev_type, handler)
            except Exception:
                pass
        self._handlers.clear()
        self._i18n_widgets.clear()
        logger.debug("OverviewDashboard unsubscribed events")

    def wakeup(self):
        self._subscribe_events()
        self._last_refresh_ts = 0
        self.refresh()
