"""PySide6 overview dashboard view.

Replaces ``ui/overview.py``. Displays KPI cards, a profit chart, active trips,
alerts, top trucks, and recent activity.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
)

from ui.design_tokens import (
    ACCENT, ACCENT_TEXT, BG_SURFACE, BG_ELEVATED,
    BORDER_DEFAULT, BORDER_FAINT,
    DANGER, DANGER_TEXT, INFO, SUCCESS, SUCCESS_TEXT,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    WARNING, WARNING_TEXT, STATUS, SP,
)
from ui.components import (
    Card, KPICard, PageTitle, Label, Btn, MonoLabel,
)
from services.i18n import t, register_listener, unregister_listener
from services.operations.event_bus import (
    EventBus,
    TRIP_CREATED,
    TRIP_STATUS_CHANGED,
    TRIP_UPDATED,
    ALERT_CREATED,
    ALERT_RESOLVED,
    TRUCK_UPDATED,
)
from repositories.trip_repository import TripRepository
from repositories.fleet_repository import FleetRepository
from services.invoicing.config_manager import load_company_config

logger = logging.getLogger(__name__)


class QtOverviewView(QScrollArea):
    """Overview dashboard with KPIs, profit chart, and activity lists."""

    REFRESH_INTERVAL_MS = 30_000

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        ops=None,
    ):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        self._event_bus = EventBus()
        self._handlers: Dict[str, Any] = {}
        self._last_refresh_ts = 0
        self._shutting_down = False
        self._chart_render_ts = 0
        self._chart_last_size = None
        self._profit_fig = None
        self._resize_timer: Optional[QTimer] = None

        self._trip_repo = TripRepository(db) if db else None
        self._fleet_repo = FleetRepository(db) if db else None

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._subscribe_events()
        self.refresh()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWidget(self._container)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(SP["10"], SP["6"], SP["10"], SP["6"])
        layout.setSpacing(SP["4"])
        layout.setAlignment(Qt.AlignTop)

        self._build_header(layout)
        self._build_kpi_strip(layout)
        self._build_main_content(layout)

    def _build_header(self, layout):
        header = QFrame()
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        header_layout.setSpacing(SP["3"])

        name_lbl = PageTitle(None, "Operion ERP")
        header_layout.addWidget(name_lbl)

        conf = load_company_config()
        company = conf.get("company_name", "")
        if company:
            company_lbl = Label(None, f"— {company}", role="secondary")
            header_layout.addWidget(company_lbl)

        header_layout.addStretch(1)

        date_lbl = Label(None, datetime.now().strftime("%A, %d %B %Y"), role="secondary")
        header_layout.addWidget(date_lbl)

        layout.addWidget(header)

    def _build_kpi_strip(self, layout):
        self._kpi_strip = QFrame()
        self._kpi_strip_layout = QHBoxLayout(self._kpi_strip)
        self._kpi_strip_layout.setContentsMargins(0, 0, 0, 0)
        self._kpi_strip_layout.setSpacing(SP["2"])

        self._kpi_widgets: Dict[str, QFrame] = {}
        # Build initial KPI cards (values are filled on first refresh)
        self._rebuild_kpi_strip()

        layout.addWidget(self._kpi_strip)

    def _rebuild_kpi_strip(self):
        """Clear and rebuild KPI cards so values can be updated."""
        # Clear existing cards
        while self._kpi_strip_layout.count():
            item = self._kpi_strip_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._kpi_widgets.clear()

        kpi_defs = [
            ("kpi_active_trucks", t("kpi_active_trucks", default="TRUCKS"), "0"),
            ("kpi_trips_today", t("kpi_trips_today", default="TRIPS"), "0"),
            ("kpi_drivers_road", t("kpi_drivers_road", default="DRIVERS"), "0"),
            ("kpi_open_alerts", t("kpi_open_alerts", default="ALERTS"), "0"),
            ("kpi_revenue", t("kpi_revenue", default="REVENUE"), "€ 0"),
            ("kpi_unpaid", t("kpi_unpaid", default="UNPAID"), "0"),
        ]
        # Store the value MonoLabel for each so _refresh_kpis can update text
        self._kpi_value_labels: Dict[str, MonoLabel] = {}
        for key, label, default in kpi_defs:
            card = KPICard(self._kpi_strip, label, default)
            # Find the MonoLabel for value updates
            val_lbl = card.findChild(QLabel, "kpi-value")
            if val_lbl is not None:
                self._kpi_value_labels[key] = val_lbl
            self._kpi_strip_layout.addWidget(card, 1)
            self._kpi_widgets[key] = card

    def _build_main_content(self, layout):
        main = QFrame()
        main_layout = QHBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(SP["4"])

        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SP["3"])

        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SP["3"])

        self._build_profit_chart(left_layout)
        self._build_active_trips(left_layout)

        self._build_alert_strip(right_layout)
        self._build_top_trucks(right_layout)
        self._build_recent_activity(right_layout)

        main_layout.addWidget(left, 62)
        main_layout.addWidget(right, 38)
        layout.addWidget(main)

    def _build_profit_chart(self, layout):
        card_widget = Card(None)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = Label(None, t("home.profit_chart_title", default="Profit Trend"), role="section-title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        month = Label(None, t("home.profit_30_days", default="Past 30 Days"), role="muted")
        header_layout.addWidget(month)
        card_layout.addWidget(header)

        self._chart_container = QFrame()
        self._chart_container.setMinimumHeight(200)
        self._chart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QVBoxLayout(self._chart_container)
        card_layout.addWidget(self._chart_container, 1)

        footer = Label(None, t("home.profit_data_source", default="Based on trip data"), role="muted")
        card_layout.addWidget(footer)

        layout.addWidget(card_widget)

    def _build_active_trips(self, layout):
        card_widget = Card(None)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = Label(None, t("home.active_trips", default="Active Trips"), role="section-title")
        header_layout.addWidget(title)
        self._trips_count = Label(None, "0", role="muted")
        header_layout.addWidget(self._trips_count)
        card_layout.addWidget(header)

        self._trips_list = QVBoxLayout()
        self._trips_list.setSpacing(2)
        card_layout.addLayout(self._trips_list)

        layout.addWidget(card_widget)

    def _build_alert_strip(self, layout):
        card_widget = Card(None)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        title = Label(None, t("home.active_alerts", default="Active Alerts"), role="section-title")
        card_layout.addWidget(title)

        self._alerts_layout = QVBoxLayout()
        self._alerts_layout.setSpacing(2)
        card_layout.addLayout(self._alerts_layout)

        layout.addWidget(card_widget)

    def _build_top_trucks(self, layout):
        card_widget = Card(None)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        title = Label(None, t("home.top_trucks", default="Top Trucks"), role="section-title")
        card_layout.addWidget(title)

        self._top_trucks_layout = QVBoxLayout()
        self._top_trucks_layout.setSpacing(3)
        card_layout.addLayout(self._top_trucks_layout)

        layout.addWidget(card_widget)

    def _build_recent_activity(self, layout):
        card_widget = Card(None)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        title = Label(None, t("home.recent_activity", default="Recent Activity"), role="section-title")
        card_layout.addWidget(title)

        self._activity_layout = QVBoxLayout()
        self._activity_layout.setSpacing(2)
        card_layout.addLayout(self._activity_layout)

        layout.addWidget(card_widget)

    # ── Refresh / data population ──────────────────────────────────────────────

    def refresh(self):
        # Guard: skip if the widget is shutting down or the underlying
        # C++ object has been destroyed (can happen when a QTimer fires
        # after the widget is closed in tests).
        if getattr(self, "_shutting_down", False):
            return
        try:
            # Access a property to verify the C++ object is still alive.
            # If the widget was deleted by Qt, this raises RuntimeError.
            self.isVisible()
        except RuntimeError:
            return

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
            trucks = self._fleet_repo.get_all() if self._fleet_repo else []
            trips = self._trip_repo.get_all(limit=2000) if self._trip_repo else []
        except Exception:
            trucks = []
            trips = []

        today_str = datetime.now().strftime("%Y-%m-%d")
        active_trucks = len([t for t in trucks if t.get("status") == "Active" or t.get("active_status") == 1])
        trips_today = len([
            t for t in trips
            if t.get("start_date") == today_str
            or (t.get("status") in ["In Transit", "Loading"] and str(t.get("created_at", "")).startswith(today_str))
        ])

        active_drivers = set()
        for trip in trips:
            s = trip.get("status", "")
            if s not in ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"):
                d = trip.get("driver_name")
                if d:
                    active_drivers.add(d)

        month_start = datetime.now().strftime("01/%m/%Y")
        revenue = sum(
            float(t.get("total_price_eur") or 0)
            for t in trips
            if str(t.get("start_date", "")) >= month_start
        )

        unpaid = len([
            t for t in trips
            if t.get("status") not in ("Paid", "Delivered", "Completed", "Done")
        ])

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
            val_lbl = self._kpi_value_labels.get(key)
            if val_lbl is not None:
                val_lbl.setText(value)

    def _refresh_active_trips(self):
        self._clear_layout(self._trips_list)

        try:
            trips = self._trip_repo.get_all(limit=200) if self._trip_repo else []
        except Exception:
            trips = []

        non_active = ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced")
        active = [t for t in trips if t.get("status", "") not in non_active]
        self._trips_count.setText(str(len(active)))

        if not active:
            lbl = QLabel(t("home.no_active_trips", default="No active trips"))
            lbl.setProperty("fontRole", "muted")
            self._trips_list.addWidget(lbl)
            return

        for trip in active[:8]:
            row = self._trip_row(trip)
            self._trips_list.addWidget(row)

    def _trip_row(self, trip: Dict[str, Any]) -> QFrame:
        row = QFrame()
        row.setProperty("role", "card-elevated")
        row.setFixedHeight(34)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(SP["3"], 0, SP["3"], 0)
        layout.setSpacing(SP["2"])

        plate = trip.get("truck_number", "—")
        plate_lbl = QLabel(plate)
        plate_lbl.setProperty("fontRole", "body_bold")
        plate_lbl.setFixedWidth(72)
        layout.addWidget(plate_lbl)

        client = trip.get("client_name", "?")
        origin = trip.get("origin", "?")
        dest = trip.get("destination", "?")
        route = f"{origin} → {dest}" if origin != "?" else client
        if len(route) > 34:
            route = route[:31] + "…"
        route_lbl = QLabel(route)
        route_lbl.setProperty("fontRole", "small")
        layout.addWidget(route_lbl, 1)

        status = trip.get("status", "planned").lower().replace(" ", "_")
        chip_bg, _ = STATUS.get(status, (BG_ELEVATED, TEXT_SECONDARY))
        status_lbl = QLabel(trip.get("status", "").title())
        status_lbl.setProperty("fontRole", "label")
        status_lbl.setStyleSheet(
            f"background-color: {chip_bg}; border-radius: 4px; padding: 2px 6px;"
        )
        layout.addWidget(status_lbl)

        return row

    def _refresh_alerts(self):
        self._clear_layout(self._alerts_layout)

        alerts = []
        if self.ops:
            try:
                alerts = self.ops.get_active_alerts(limit=5)
            except Exception:
                pass

        if not alerts:
            lbl = QLabel(t("home.no_alerts", default="No active alerts"))
            lbl.setProperty("fontRole", "muted")
            self._alerts_layout.addWidget(lbl)
            return

        for a in alerts[:3]:
            row = QFrame()
            row.setProperty("role", "card-elevated")
            row.setFixedHeight(30)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(SP["3"], 0, SP["3"], 0)

            sev_color = {
                "CRITICAL": DANGER,
                "WARNING": WARNING,
            }.get(getattr(a, "severity", "INFO"), INFO)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {sev_color};")
            layout.addWidget(dot)

            title = getattr(a, "title", getattr(a, "message", "Alert"))
            if len(title) > 40:
                title = title[:37] + "…"
            title_lbl = QLabel(title)
            title_lbl.setProperty("fontRole", "small")
            layout.addWidget(title_lbl, 1)

            self._alerts_layout.addWidget(row)

        if len(alerts) > 3:
            more = QLabel(f"+ {len(alerts) - 3} more")
            more.setProperty("fontRole", "muted")
            self._alerts_layout.addWidget(more)

    def _refresh_top_trucks(self):
        self._clear_layout(self._top_trucks_layout)

        try:
            now = datetime.now()
            month_start = now.replace(day=1).strftime("%Y-%m-%d")
            month_end = now.strftime("%Y-%m-%d")
            top = self._trip_repo.get_top_trucks_by_revenue(month_start, month_end, limit=4) if self._trip_repo else []
        except Exception:
            top = []

        if not top:
            lbl = QLabel(t("common.no_data", default="No data"))
            lbl.setProperty("fontRole", "muted")
            self._top_trucks_layout.addWidget(lbl)
            return

        for i, row in enumerate(top, 1):
            plate = row.get("truck_number", "—")
            revenue = float(row.get("revenue", 0))

            r = QFrame()
            layout = QHBoxLayout(r)
            layout.setContentsMargins(0, 0, 0, 0)

            idx = QLabel(f"#{i}")
            idx.setProperty("fontRole", "body_bold")
            idx.setStyleSheet(f"color: {ACCENT_TEXT};")
            idx.setFixedWidth(24)
            layout.addWidget(idx)

            plate_lbl = QLabel(plate)
            plate_lbl.setProperty("fontRole", "body_bold")
            layout.addWidget(plate_lbl, 1)

            rev_lbl = QLabel(f"€ {revenue:,.0f}")
            rev_lbl.setProperty("fontRole", "mono")
            rev_lbl.setStyleSheet(f"color: {SUCCESS_TEXT};")
            layout.addWidget(rev_lbl)

            self._top_trucks_layout.addWidget(r)

    def _refresh_recent_activity(self):
        self._clear_layout(self._activity_layout)

        try:
            recent = self._trip_repo.get_all(limit=6) if self._trip_repo else []
        except Exception:
            recent = []

        if not recent:
            lbl = QLabel(t("common.no_data", default="No data"))
            lbl.setProperty("fontRole", "muted")
            self._activity_layout.addWidget(lbl)
            return

        for trip in recent:
            profit = float(trip.get("net_profit", 0) or 0)
            plate = trip.get("truck_number", "—")
            client = trip.get("client_name", "—")
            date = trip.get("start_date", "") or str(trip.get("created_at", ""))[:10]

            r = QFrame()
            layout = QHBoxLayout(r)
            layout.setContentsMargins(0, 0, 0, 0)

            date_lbl = QLabel(date)
            date_lbl.setProperty("fontRole", "muted")
            date_lbl.setFixedWidth(70)
            layout.addWidget(date_lbl)

            plate_lbl = QLabel(plate)
            plate_lbl.setProperty("fontRole", "muted")
            plate_lbl.setFixedWidth(60)
            layout.addWidget(plate_lbl)

            client_lbl = QLabel(client[:18])
            client_lbl.setProperty("fontRole", "small")
            layout.addWidget(client_lbl, 1)

            color = SUCCESS_TEXT if profit > 0 else DANGER_TEXT
            profit_lbl = QLabel(f"{profit:,.0f} €")
            profit_lbl.setProperty("fontRole", "muted")
            profit_lbl.setStyleSheet(f"color: {color};")
            layout.addWidget(profit_lbl)

            self._activity_layout.addWidget(r)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ── Chart rendering ────────────────────────────────────────────────────────

    def _render_profit_chart(self, _force: bool = False):
        import time
        now = time.time()
        if not _force and self._chart_render_ts and now - self._chart_render_ts < 0.8:
            return

        try:
            self._do_render_chart()
            self._chart_render_ts = now
        except Exception as exc:
            logger.exception("Profit chart render failed: %s", exc)

    def _do_render_chart(self):
        # Lazy imports so matplotlib is optional at import time.
        import matplotlib
        matplotlib.use("QtAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        self._clear_layout(self._chart_container.layout())
        if self._profit_fig is not None:
            try:
                plt.close(self._profit_fig)
            except Exception:
                pass
            self._profit_fig = None

        profit_map = {}
        now_dt = datetime.now()
        chart_start = now_dt - timedelta(days=30)
        chart_end = now_dt
        try:
            raw_data = self._trip_repo.get_daily_profit(
                chart_start.strftime("%Y-%m-%d"),
                chart_end.strftime("%Y-%m-%d"),
            ) if self._trip_repo else []
            for d, p in raw_data:
                try:
                    if "-" in d:
                        parts = d.split("-")
                        date_key = f"{int(parts[2]):02d}/{int(parts[1]):02d}"
                    else:
                        date_key = d
                    profit_map[date_key] = float(p or 0)
                except (ValueError, IndexError):
                    profit_map[d] = float(p or 0)
        except Exception as exc:
            logger.exception("Chart data fetch failed: %s", exc)

        num_days = 31
        day_labels = []
        for i in range(num_days):
            dt = chart_start + timedelta(days=i)
            day_labels.append(dt.strftime("%d/%m"))

        days = list(range(1, num_days + 1))
        profits = [abs(profit_map.get(day_labels[i], 0.0)) for i in range(num_days)]

        if not profit_map or all(p == 0 for p in profits):
            msg = t("home.profit_no_data", default="No profit data available yet.\nComplete trips to see analytics.")
            lbl = QLabel(msg)
            lbl.setProperty("fontRole", "muted")
            lbl.setAlignment(Qt.AlignCenter)
            self._chart_container.layout().addWidget(lbl)
            return

        cw = max(self._chart_container.width(), 300)
        ch = max(self._chart_container.height(), 180)
        self._chart_last_size = (cw, ch)

        dpi = 100
        fig_w = cw / dpi
        fig_h = ch / dpi

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        fig.patch.set_facecolor(BG_SURFACE)
        ax.set_facecolor(BG_SURFACE)
        fig.subplots_adjust(left=0.05, right=0.98, top=0.94, bottom=0.10)

        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER_DEFAULT)
            spine.set_linewidth(0.5)
        ax.tick_params(colors=TEXT_MUTED, labelsize=8, pad=4, length=3, width=0.5)
        ax.grid(axis="y", color=BORDER_DEFAULT, linewidth=0.4, linestyle="--", alpha=0.35)
        ax.set_axisbelow(True)

        nonzero = [p for p in profits if p != 0]
        if nonzero:
            y_min = min(0, min(nonzero) * 1.15)
            y_max = max(0, max(nonzero) * 1.20)
        else:
            y_min, y_max = 0, 100
        y_pad = (y_max - y_min) * 0.05
        ax.set_ylim(y_min - y_pad, y_max + y_pad)
        ax.set_xlim(0.5, num_days + 0.5)

        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x_val, _: f"{x_val:,.0f}"))

        tick_step = max(1, num_days // 6)
        tick_positions = [1] + list(range(tick_step, num_days + 1, tick_step))
        if num_days not in tick_positions:
            tick_positions.append(num_days)
        ax.set_xticks(tick_positions)
        tick_labels = [day_labels[p - 1] for p in tick_positions]
        ax.set_xticklabels(tick_labels)
        ax.set_xlabel(
            t("home.profit_day_label", default="Day"),
            fontsize=8,
            color=TEXT_MUTED,
            labelpad=6,
        )

        days_arr = np.array(days, dtype=float)
        profits_arr = np.array(profits, dtype=float)
        x_smooth, y_smooth = self._smooth_data(days_arr, profits_arr, num=len(days) * 20)

        line_color = ACCENT

        ax.fill_between(x_smooth, 0, y_smooth, alpha=0.25, color=line_color, zorder=1)
        ax.plot(x_smooth, y_smooth, color=line_color, linewidth=2.0, alpha=0.85,
                solid_capstyle="round", solid_joinstyle="round", zorder=3)
        ax.plot(days_arr, profits_arr, linestyle="none", marker="o", markersize=3.5,
                markerfacecolor=line_color, markeredgecolor="none", zorder=4)

        canvas = FigureCanvas(fig)
        self._chart_container.layout().addWidget(canvas)

        self._profit_fig = fig

    @staticmethod
    def _smooth_data(x, y, num=300):
        if len(x) < 2:
            return x, y
        x_dense = np.linspace(x[0], x[-1], num)
        y_dense = np.interp(x_dense, x, y)
        return x_dense, y_dense

    # ── Event handling ─────────────────────────────────────────────────────────

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
            if ev_type not in self._handlers:
                self._event_bus.subscribe(ev_type, handler)
                self._handlers[ev_type] = handler

    def _on_data_changed(self, ev):
        QTimer.singleShot(0, self.refresh)

    def _on_language_changed(self, lang: str):
        QTimer.singleShot(0, self.refresh)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self):
        self._subscribe_events()
        self._last_refresh_ts = 0
        self.refresh()

    def shutdown(self):
        self._shutting_down = True
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        if self._resize_timer is not None:
            self._resize_timer.stop()
        if self._profit_fig is not None:
            try:
                import matplotlib.pyplot as plt
                plt.close(self._profit_fig)
            except Exception:
                pass
            self._profit_fig = None
        # Remove chart canvas widgets from layout
        if self._chart_container is not None:
            layout = self._chart_container.layout()
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    if item is not None:
                        w = item.widget()
                        if w is not None:
                            w.deleteLater()
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        for ev_type, handler in list(self._handlers.items()):
            try:
                self._event_bus.unsubscribe(ev_type, handler)
            except Exception:
                pass
        self._handlers.clear()
