import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from services.i18n import t, register_listener, unregister_listener
from services.preferences import safe_float
from services.app_state import AppState

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.patches import FancyBboxPatch
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False


from ui.theme import COLORS, CHART_PRIMARY, CHART_SECONDARY, CHART_INDIGO, FONTS, apply_chart_style

class FleetDashboard:
    def __init__(self, parent, db, prefs=None, ops=None, embedded=False):
        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_base"])
            self.frame.pack(fill="both", expand=True)
        else:
            self.win = ctk.CTkToplevel(parent)
            if self.win:
                self.win.title(f"\U0001f4ca {t('fleet_dashboard.title')}")
            self.win.geometry("1400x900")
            self.win.configure(fg_color=COLORS["bg_base"])
            self.frame = ctk.CTkFrame(self.win, fg_color=COLORS["bg_base"])
            self.frame.pack(fill="both", expand=True)

        self.db = db
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self.ops = ops

        self._period = "today"
        self._start_date = None
        self._end_date = None
        self._last_refresh = None
        self._i18n_widgets = []
        self._chart_refs = []
        self._period_buttons = []

        self._build_header()
        self._build_content()
        self.refresh_all()

        app_state = AppState()
        app_state.subscribe("language", self._on_language_changed)
        register_listener(self._on_language_changed)
        if self.win:
            self.win.protocol("WM_DELETE_WINDOW", self._on_close)
            self.win.bind("<Destroy>", self._on_destroy)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        unregister_listener(self._on_language_changed)
        app_state = AppState()
        app_state.unsubscribe("language", self._on_language_changed)

    def _on_close(self):
        if self.win:
            self.win.destroy()

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win:
            if self.win:
                self.win.title(f"📊 {t('fleet_dashboard.title')}")
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        self.refresh_all()

    def _build_header(self):
        header = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_base"])
        header.pack(fill="x")

        title_lbl = ctk.CTkLabel(header, text=t('fleet_dashboard.title'),
                            fg_color=COLORS["bg_base"], text_color=COLORS["text_primary"],
                            font=FONTS["h1"])
        title_lbl.pack(side="left")
        self._i18n_tag(title_lbl, "fleet_dashboard.title")

        period_frame = ctk.CTkFrame(header, fg_color=COLORS["bg_base"])
        period_frame.pack(side="left", padx=30)

        periods = [
            ("today", "fleet_dashboard.today"),
            ("week", "fleet_dashboard.this_week"),
            ("month", "fleet_dashboard.this_month"),
            ("custom", "fleet_dashboard.custom")
        ]

        for period_id, key in periods:
            btn = ctk.CTkButton(period_frame, text=t(key),
                          fg_color=COLORS["bg_surface"] if period_id != self._period else COLORS["accent"],
                          text_color=COLORS["text_primary"],
                          font=FONTS["small"],
                          cursor="hand2",
                          command=lambda p=period_id: self._set_period(p))
            btn.pack(side="left", padx=2)
            self._period_buttons.append((btn, period_id, key))
            self._i18n_tag(btn, key)

        refresh_frame = ctk.CTkFrame(header, fg_color=COLORS["bg_base"])
        refresh_frame.pack(side="right")

        refresh_btn = ctk.CTkButton(refresh_frame, text=f"🔄 {t('fleet_dashboard.refresh')}",
                               fg_color=COLORS["accent"], text_color=COLORS["text_primary"],
                          font=FONTS["small"],
                               cursor="hand2",
                               command=self.refresh_all)
        refresh_btn.pack(side="right")
        self._i18n_tag(refresh_btn, "fleet_dashboard.refresh", "🔄 ")

        self.last_refresh_lbl = ctk.CTkLabel(refresh_frame, text="",
                                        fg_color=COLORS["bg_base"], text_color=COLORS["text_secondary"],
                                        font=FONTS["label"])
        self.last_refresh_lbl.pack(side="right", padx=10)

    def _set_period(self, period):
        self._period = period
        today = datetime.now()

        if period == "today":
            self._start_date = self._end_date = today.strftime("%Y-%m-%d")
        elif period == "week":
            monday = today - timedelta(days=today.weekday())
            self._start_date = monday.strftime("%Y-%m-%d")
            self._end_date = today.strftime("%Y-%m-%d")
        elif period == "month":
            self._start_date = today.strftime("%Y-%m-01")
            self._end_date = today.strftime("%Y-%m-%d")
        else:
            self._start_date = self._end_date = None

        for btn, pid, _ in self._period_buttons:
            btn.configure(fg_color=COLORS["accent"] if pid == period else COLORS["bg_surface"])

        self.refresh_all()

    def _build_content(self):
        self.content_frame = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_base"])
        self.content_frame.pack(fill="both", expand=True, padx=30, pady=10)

    def refresh_all(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self._chart_refs.clear()

        self._last_refresh = datetime.now()
        self.last_refresh_lbl.configure(
            text=t('fleet_dashboard.last_refreshed',
                  time=self._last_refresh.strftime("%H:%M:%S"))
        )

        try:
            trucks = self.db.get_all_trucks()
            trips = self.db.get_all_trips()
            alerts, _ = self.db.get_overdue_data()
            kpi = self.db.get_kpi_stats()
            best_truck, best_driver, _ = self.db.get_advanced_analytics()

            self._build_kpi_row(trucks, trips, alerts, kpi)
            self._build_charts_row(trucks, trips)
            self._build_info_cards(best_truck, best_driver, trucks, trips)
            self._build_activity_feed(trips)
        except Exception as e:
            messagebox.showerror(t('fleet_dashboard.error_title'),
                               t('fleet_dashboard.error_msg').format(str(e)))

    def _build_kpi_row(self, trucks, trips, alerts, kpi):
        kpi_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_base"])
        kpi_frame.pack(fill="x", pady=(0, 20))

        active_trucks = len([t for t in trucks if t.get('status') == 'Active' or t.get('active_status') == 1])
        today_str = datetime.now().strftime("%d/%m/%Y")
        trips_today = len([t for t in trips if t.get('start_date') == today_str or
                          (t.get('status') in ['In Transit', 'Loading'] and
                           t.get('created_at', '').startswith(today_str))])

        filtered_trips = self._filter_trips_by_period(trips)
        revenue = sum(safe_float(t.get('total_price_eur')) for t in filtered_trips)
        fuel_costs = [safe_float(t.get('fuel_cost')) for t in filtered_trips if t.get('fuel_cost')]
        avg_fuel = sum(fuel_costs) / len(fuel_costs) if fuel_costs else 0

        kpis = [
            ("fleet_dashboard.kpi_active_trucks", str(active_trucks), COLORS["accent"]),
            ("fleet_dashboard.kpi_trips_today", str(trips_today), COLORS["success"]),
            ("fleet_dashboard.kpi_revenue", self.prefs.format_currency(revenue, 0), COLORS["accent"]),
            ("fleet_dashboard.kpi_avg_fuel", self.prefs.format_currency(avg_fuel, 0), COLORS["warning"]),
            ("fleet_dashboard.kpi_alerts", str(len(alerts)), COLORS["danger"]),
            ("fleet_dashboard.kpi_unpaid", str(kpi.get('unpaid', 0)), COLORS["danger"])
        ]

        for i, (key, value, color) in enumerate(kpis):
            self._create_kpi_card(kpi_frame, t(key), value, color, i)

    def _create_kpi_card(self, parent, label, value, color, col):
        card = tk.Canvas(parent, width=200, height=120, bg=COLORS["bg_surface"],
                        highlightthickness=0, bd=0)
        card.grid(row=0, column=col, padx=8, pady=8)

        card.create_rounded_rect = lambda x1, y1, x2, y2, r, **kw: card.create_polygon(
            [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r,
             x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2,
             x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r,
             x1, y1+r, x1, y1], smooth=True, **kw
        )

        card.create_rounded_rect(0, 0, 200, 120, 12, fill=COLORS["bg_surface"], outline=color, width=2)

        card.create_text(100, 35, text=label.upper(), fill=COLORS["text_secondary"],
                        font=FONTS["label"], anchor="center")
        card.create_text(100, 75, text=value, fill=COLORS["text_primary"],
                        font=FONTS["display"], anchor="center")

    def _build_charts_row(self, trucks, trips):
        charts_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_base"])
        charts_frame.pack(fill="both", expand=True, pady=10)

        left_frame = ctk.CTkFrame(charts_frame, fg_color=COLORS["bg_base"])
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_frame = ctk.CTkFrame(charts_frame, fg_color=COLORS["bg_base"])
        right_frame.pack(side="right", fill="both", expand=True)

        if HAS_PLOT:
            self._draw_trip_activity_chart(left_frame, trips)
            self._draw_fleet_status_chart(right_frame, trucks)
        else:
            ctk.CTkLabel(left_frame, text=t('fleet_dashboard.charts_unavailable'), fg_color=COLORS["bg_base"],
                    text_color=COLORS["text_secondary"]).pack(expand=True)

    def _draw_trip_activity_chart(self, parent, trips):
        filtered = self._filter_trips_by_period(trips)

        from collections import defaultdict
        daily = defaultdict(lambda: {'completed': 0, 'in_progress': 0, 'cancelled': 0})

        for trip in filtered:
            date = trip.get('created_at', '')[:10] if trip.get('created_at') else ''
            if date:
                status = trip.get('status', '')
                if status in ['Paid', 'Delivered']:
                    daily[date]['completed'] += 1
                elif status in ['In Transit', 'Loading']:
                    daily[date]['in_progress'] += 1
                elif status == 'Cancelled':
                    daily[date]['cancelled'] += 1

        if not daily:
            ctk.CTkLabel(parent, text=t('fleet_dashboard.no_data'),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                    font=FONTS["small"]).pack(expand=True, fill="both")
            return

        dates = sorted(daily.keys())[-14:]
        completed = [daily[d]['completed'] for d in dates]
        in_progress = [daily[d]['in_progress'] for d in dates]
        cancelled = [daily[d]['cancelled'] for d in dates]

        fig, ax = plt.subplots(figsize=(7, 4), dpi=90)
        apply_chart_style(fig, ax)

        x = range(len(dates))
        width = 0.25
        ax.bar([i - width for i in x], completed, width, label=t('fleet_dashboard.status_completed'),
               color=CHART_PRIMARY, alpha=0.8)
        ax.bar(x, in_progress, width, label=t('fleet_dashboard.status_in_progress'),
               color=CHART_INDIGO, alpha=0.8)
        ax.bar([i + width for i in x], cancelled, width, label=t('fleet_dashboard.status_cancelled'),
               color=CHART_SECONDARY, alpha=0.8)

        ax.set_title(t('fleet_dashboard.chart_trip_activity'), color=COLORS["text_primary"],
                    fontsize=12, fontweight='bold', pad=15)
        ax.set_xlabel(t('fleet_dashboard.date'), color=COLORS["text_secondary"], fontsize=9)
        ax.set_ylabel(t('fleet_dashboard.trips'), color=COLORS["text_secondary"], fontsize=9)
        ax.tick_params(colors=COLORS["text_secondary"], labelsize=8)
        ax.legend(loc='upper left', facecolor=COLORS["bg_surface"],
                 edgecolor=COLORS["border"], labelcolor=COLORS["text_primary"])

        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS["border"])

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._chart_refs.append((fig, canvas))

    def _draw_fleet_status_chart(self, parent, trucks):
        status_labels_map = {
            'active': t('fleet_dashboard.status_active'),
            'idle': t('fleet_dashboard.status_idle'),
            'maintenance': t('fleet_dashboard.status_maintenance'),
            'inactive': t('fleet_dashboard.status_inactive'),
        }
        status_counts = {k: 0 for k in status_labels_map}

        for truck in trucks:
            status = truck.get('status', 'Inactive')
            active = truck.get('active_status', 0)

            if status == 'Active' and active == 1:
                status_counts['active'] += 1
            elif status == 'Active' and active == 0:
                status_counts['idle'] += 1
            elif status == 'In Service':
                status_counts['maintenance'] += 1
            else:
                status_counts['inactive'] += 1

        labels = [status_labels_map[k] for k in status_counts.keys()]
        sizes = list(status_counts.values())
        colors = [CHART_PRIMARY, CHART_INDIGO, CHART_SECONDARY, COLORS["accent"]]

        if sum(sizes) == 0:
            ctk.CTkLabel(parent, text=t('fleet_dashboard.no_data'),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                    font=FONTS["small"]).pack(expand=True, fill="both")
            return

        fig, ax = plt.subplots(figsize=(5, 4), dpi=90)
        fig.patch.set_facecolor(COLORS["bg_surface"])
        ax.set_facecolor(COLORS["bg_surface"])

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
                                          autopct='%1.0f%%', startangle=90,
                                          textprops={'color': COLORS["text_primary"], 'fontsize': 9})

        for autotext in autotexts:
            autotext.set_color(COLORS["text_primary"])
            autotext.set_fontweight('bold')

        ax.set_title(t('fleet_dashboard.chart_fleet_status'), color=COLORS["text_primary"],
                    fontsize=12, fontweight='bold', pad=15)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._chart_refs.append((fig, canvas))

    def _build_info_cards(self, best_truck, best_driver, trucks, trips):
        cards_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_base"])
        cards_frame.pack(fill="x", pady=10)

        filtered_trips = self._filter_trips_by_period(trips)

        truck_revenue = {}
        truck_trips = {}
        truck_fuel = {}

        for trip in filtered_trips:
            truck_num = trip.get('truck_number', '')
            if truck_num:
                truck_revenue[truck_num] = truck_revenue.get(truck_num, 0) + safe_float(trip.get('total_price_eur'))
                truck_trips[truck_num] = truck_trips.get(truck_num, 0) + 1
                truck_fuel[truck_num] = truck_fuel.get(truck_num, 0) + safe_float(trip.get('fuel_cost'))

        best_truck_card = self._create_info_card(cards_frame, t('fleet_dashboard.card_best_truck'))
        if best_truck and truck_revenue:
            top_truck = max(truck_revenue.items(), key=lambda x: x[1])
            ctk.CTkLabel(best_truck_card, text=top_truck[0], fg_color=COLORS["bg_surface"],
                    text_color=COLORS["text_primary"], font=FONTS["small"]).pack(pady=(5, 0))
            ctk.CTkLabel(best_truck_card,
                    text=t('fleet_dashboard.card_revenue',
                          amount=self.prefs.format_currency(top_truck[1], 0)),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["label"]).pack()
            ctk.CTkLabel(best_truck_card,
                    text=t('fleet_dashboard.card_trips', count=truck_trips.get(top_truck[0], 0)),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["label"]).pack()
        else:
            ctk.CTkLabel(best_truck_card, text=t('fleet_dashboard.no_data'),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                    font=FONTS["label"]).pack(pady=10)

        best_driver_card = self._create_info_card(cards_frame, t('fleet_dashboard.card_best_driver'))
        if best_driver:
            driver_trips = [t for t in filtered_trips if t.get('driver_name') == best_driver.get('driver_name')]
            avg_profit = safe_float(best_driver.get('p')) / len(driver_trips) if driver_trips else 0

            ctk.CTkLabel(best_driver_card, text=best_driver.get('driver_name', t('common.na')),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["small"]).pack(pady=(5, 0))
            ctk.CTkLabel(best_driver_card,
                    text=t('fleet_dashboard.card_trips', count=len(driver_trips)),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["label"]).pack()
            ctk.CTkLabel(best_driver_card,
                    text=t('fleet_dashboard.card_avg_profit',
                          amount=self.prefs.format_currency(avg_profit, 0)),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["label"]).pack()
        else:
            ctk.CTkLabel(best_driver_card, text=t('fleet_dashboard.no_driver_data'),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                    font=FONTS["label"]).pack(pady=10)

        fuel_card = self._create_info_card(cards_frame, t('fleet_dashboard.card_highest_fuel'))
        if truck_fuel:
            top_fuel_truck = max(truck_fuel.items(), key=lambda x: x[1])
            truck_data = next((t for t in trucks if t.get('plate_number') == top_fuel_truck[0]), None)
            consumption = truck_data.get('fuel_consumption', t('common.na')) if truck_data else t('common.na')

            ctk.CTkLabel(fuel_card, text=top_fuel_truck[0], fg_color=COLORS["bg_surface"],
                    text_color=COLORS["text_primary"], font=FONTS["small"]).pack(pady=(5, 0))
            ctk.CTkLabel(fuel_card,
                    text=t('fleet_dashboard.card_fuel_cost',
                          amount=self.prefs.format_currency(top_fuel_truck[1], 0)),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["label"]).pack()
            ctk.CTkLabel(fuel_card,
                    text=t('fleet_dashboard.card_consumption', value=consumption),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                    font=FONTS["label"]).pack()
        else:
            ctk.CTkLabel(fuel_card, text=t('fleet_dashboard.no_data'),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                    font=FONTS["label"]).pack(pady=10)

    def _create_info_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"], width=400, height=140)
        card.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        card.pack_propagate(False)

        title_lbl = ctk.CTkLabel(card, text=title, fg_color=COLORS["bg_surface"],
                            text_color=COLORS["text_primary"], font=FONTS["small"])
        title_lbl.pack(pady=(12, 5))

        return card

    def _build_activity_feed(self, trips):
        feed_frame = ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_base"])
        feed_frame.pack(fill="both", expand=True, pady=10)

        header = ctk.CTkFrame(feed_frame, fg_color=COLORS["bg_base"])
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(header, text=t('fleet_dashboard.activity_title'),
                fg_color=COLORS["bg_base"], text_color=COLORS["text_primary"],
                font=FONTS["h3"]).pack(side="left")

        view_all = ctk.CTkLabel(header, text=t('fleet_dashboard.activity_view_all'),
                           fg_color=COLORS["bg_base"], text_color=COLORS["accent"],
                           font=FONTS["label"], cursor="hand2")
        view_all.pack(side="right")
        view_all.bind("<Button-1>", lambda e: self._open_route_history())

        recent_trips = sorted(trips, key=lambda x: x.get('id', 0), reverse=True)[:10]

        feed_container = ctk.CTkFrame(feed_frame, fg_color=COLORS["bg_surface"])
        feed_container.pack(fill="both", expand=True)

        if not recent_trips:
            ctk.CTkLabel(feed_container, text=t('fleet_dashboard.no_data'),
                    fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                     font=FONTS["label"]).pack(expand=True)
            return

        for trip in recent_trips:
            self._create_activity_row(feed_container, trip)

    def _create_activity_row(self, parent, trip):
        row = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"])
        row.pack(fill="x")

        timestamp = trip.get('created_at', t('common.na'))[:16]
        ctk.CTkLabel(row, text=timestamp, fg_color=COLORS["bg_surface"], text_color=COLORS["text_secondary"],
                font=FONTS["label"], width=18, anchor="w").pack(side="left")

        truck = trip.get('truck_number', t('common.na'))
        ctk.CTkLabel(row, text=truck, fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                font=FONTS["small"], width=15, anchor="w").pack(side="left")

        status = trip.get('status', t('common.unknown'))
        status_color = self._get_status_color(status)
        status_chip = ctk.CTkLabel(row, text=status, fg_color=status_color, text_color=COLORS["text_primary"],
                              font=FONTS["label"], padx=8, pady=2)
        status_chip.pack(side="left", padx=10)

        client = trip.get('client_name', '')
        detail = f"{client}" if client else ""
        ctk.CTkLabel(row, text=detail, fg_color=COLORS["bg_surface"], text_color=COLORS["text_primary"],
                font=FONTS["label"], anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkFrame(parent, fg_color=COLORS["accent"], height=1).pack(fill="x", padx=15)

    def _get_status_color(self, status):
        if status in ['Paid', 'Delivered']:
            return COLORS["success"]
        elif status in ['In Transit', 'Loading']:
            return COLORS["warning"]
        elif status == 'Cancelled':
            return COLORS["danger"]
        else:
            return COLORS["accent"]

    def _filter_trips_by_period(self, trips):
        if not self._start_date or not self._end_date:
            return trips

        filtered = []
        for trip in trips:
            created = trip.get('created_at', '')
            if created:
                try:
                    trip_date = datetime.strptime(created[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
                    if self._start_date <= trip_date <= self._end_date:
                        filtered.append(trip)
                except Exception:
                    pass
        return filtered

    def _open_route_history(self):
        if self.ops and hasattr(self.ops, '_open_route_history'):
            self.ops._open_route_history()
        if self.win:
            self.win.destroy()
