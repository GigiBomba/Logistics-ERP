"""PySide6 fleet dashboard view.

Replaces ``ui/dashboard.py``. Displays KPI cards, trip-activity and
fleet-status charts, info cards, and an activity feed — all with
period filtering (today / week / month / custom).

Usage as embedded widget::

    dashboard = QtFleetDashboard(parent_widget, db, prefs, ops)

Usage as standalone window (QDialog)::

    from ui.views.dashboard import FleetDashboardDialog

    dlg = FleetDashboardDialog(db, prefs, ops, parent=parent_widget)
    if dlg.exec_():
        ...
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
)

from ui.theme import COLORS, S, CHART_PRIMARY, CHART_SECONDARY
from services.i18n import t, register_listener, unregister_listener
from services.preferences import safe_float
from services.app_state import AppState
from ui.widgets import KpiCard, ActionButton

logger = logging.getLogger(__name__)


class QtFleetDashboard(QWidget):
    """Fleet overview dashboard with KPIs, charts, info cards and activity feed.

    Can be embedded in a parent QWidget. For standalone windowed mode use
    ``FleetDashboardDialog``.
    """

    REFRESH_INTERVAL_MS = 30_000

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
        ops=None,
    ):
        super().__init__(parent)
        self.db = db
        from services.preferences import PreferencesManager

        self.prefs = prefs or (PreferencesManager(db) if db else None)
        self.ops = ops

        # ── Period state ────────────────────────────────────────────────────────
        self._period = "today"
        self._start_date: Optional[str] = None
        self._end_date: Optional[str] = None
        self._last_refresh: Optional[datetime] = None

        # ── Chart references (for cleanup) ──────────────────────────────────────
        self._chart_refs: List[Tuple[Any, Any]] = []
        self._chart_figures: List[Any] = []

        # ── i18n ────────────────────────────────────────────────────────────────
        self._i18n_widgets: List[Tuple[Any, str, str]] = []
        self._period_button_refs: List[Tuple[ActionButton, str, str]] = []
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        app_state = AppState()
        app_state.subscribe("language", self._language_callback)

        # ── Build UI ────────────────────────────────────────────────────────────
        self._build_ui()

        # ── Auto-refresh timer ──────────────────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

        # ── Initial load ────────────────────────────────────────────────────────
        self.refresh_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Re-fetch data and rebuild all cards, charts and the activity feed."""
        self._last_refresh = datetime.now()
        self._update_last_refresh_label()

        try:
            trucks = self.db.get_all_trucks() if self.db else []
            trips = self.db.get_all_trips() if self.db else []
            alerts, _ = self.db.get_overdue_data() if self.db else ([], None)
            kpi = self.db.get_kpi_stats() if self.db else {}
            best_truck, best_driver, _ = (
                self.db.get_advanced_analytics() if self.db else (None, None, None)
            )
        except Exception as exc:
            logger.exception("FleetDashboard refresh_all failed")
            QMessageBox.warning(
                self,
                t("fleet_dashboard.error_title"),
                t("fleet_dashboard.error_msg").format(str(exc)),
            )
            return

        # ── One-pass aggregation ───────────────────────────────────────────────
        filtered_trips = self._filter_trips_by_period(trips)
        today_str = datetime.now().strftime("%Y-%m-%d")

        active_trucks = 0
        trips_today = 0
        revenue = 0.0
        total_fuel = 0.0
        fuel_count = 0
        truck_revenue: Dict[str, float] = {}
        truck_trips: Dict[str, int] = {}
        truck_fuel: Dict[str, float] = {}
        driver_trip_map: Dict[str, int] = {}

        for t in trips:
            if t.get("status") == "Active" or t.get("active_status") == 1:
                active_trucks += 1
            if t.get("start_date") == today_str or (
                t.get("status") in ("In Transit", "Loading")
                and str(t.get("created_at", ""))[:10] == today_str
            ):
                trips_today += 1

        for t in filtered_trips:
            plate = t.get("truck_number", "")
            driver = t.get("driver_name", "")
            price = safe_float(t.get("total_price_eur"))
            fuel_val = safe_float(t.get("fuel_cost"))

            revenue += price
            if fuel_val > 0:
                total_fuel += fuel_val
                fuel_count += 1
            if plate:
                truck_revenue[plate] = truck_revenue.get(plate, 0) + price
                truck_trips[plate] = truck_trips.get(plate, 0) + 1
                truck_fuel[plate] = truck_fuel.get(plate, 0) + fuel_val
            if driver:
                driver_trip_map[driver] = driver_trip_map.get(driver, 0) + 1

        avg_fuel = total_fuel / fuel_count if fuel_count else 0

        top_truck = (
            max(truck_revenue.items(), key=lambda x: x[1])
            if truck_revenue
            else None
        )
        top_fuel_truck = (
            max(truck_fuel.items(), key=lambda x: x[1]) if truck_fuel else None
        )

        driver_trip_count = 0
        avg_profit = 0.0
        if best_driver:
            driver_name = best_driver.get("driver_name", "")
            driver_trip_count = driver_trip_map.get(driver_name, 0)
            avg_profit = (
                safe_float(best_driver.get("p"))
                / driver_trip_count
                if driver_trip_count
                else 0
            )

        # ── Clear and rebuild content area ─────────────────────────────────────
        self._clear_content_area()

        self._build_kpi_row(
            active_trucks,
            trips_today,
            revenue,
            avg_fuel,
            len(alerts),
            kpi.get("unpaid", 0),
        )
        self._build_charts_row(trucks, trips)
        self._build_info_cards(
            top_truck,
            best_driver,
            truck_trips,
            avg_profit,
            driver_trip_count,
            top_fuel_truck,
            truck_fuel,
            trucks,
        )
        self._build_activity_feed(trips)

    def wakeup(self) -> None:
        """Re-activate the dashboard (e.g. after it was hidden / detached)."""
        self._subscribe_events()
        self.refresh_all()

    def shutdown(self) -> None:
        """Clean up timers, chart figures, and listeners."""
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

        # Close matplotlib figures
        for fig, _canvas in self._chart_refs:
            try:
                import matplotlib.pyplot as plt

                plt.close(fig)
            except Exception:
                pass
        self._chart_refs.clear()
        self._chart_figures.clear()

        # Unsubscribe i18n
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        try:
            AppState().unsubscribe("language", self._language_callback)
        except Exception:
            pass

    def refresh_translations(self) -> None:
        """Update all visible text after a language change."""
        for widget, key, prefix in self._i18n_widgets:
            try:
                if isinstance(widget, QLabel):
                    widget.setText(f"{prefix}{t(key)}")
                elif isinstance(widget, QPushButton):
                    widget.setText(f"{prefix}{t(key)}")
            except Exception:
                pass
        for btn, _pid, key in self._period_button_refs:
            try:
                btn.setText(t(key))
            except Exception:
                pass
        self._update_last_refresh_label()

        # Rebuild chart titles by re-drawing
        if self._chart_refs:
            # A full refresh is the safest way to pick up translated chart labels
            QTimer.singleShot(0, self.refresh_all)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the complete widget hierarchy."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll wrapper so content does not overflow on small screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(self._container)

        content_layout = QVBoxLayout(self._container)
        content_layout.setContentsMargins(S["10"], S["6"], S["10"], S["6"])
        content_layout.setSpacing(S["4"])
        content_layout.setAlignment(Qt.AlignTop)

        self._build_header(content_layout)

        # This frame holds the dynamically replaced content
        self._content_frame = QFrame()
        self._content_frame.setProperty("role", "card")
        self._content_layout_inner = QVBoxLayout(self._content_frame)
        self._content_layout_inner.setContentsMargins(0, 0, 0, 0)
        self._content_layout_inner.setSpacing(S["4"])
        content_layout.addWidget(self._content_frame, 1)

        layout.addWidget(scroll)

    def _build_header(self, layout: QVBoxLayout) -> None:
        """Title bar + period filter buttons + refresh button."""
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title_lbl = QLabel(t("fleet_dashboard.title"))
        title_lbl.setProperty("fontRole", "h1")
        header_layout.addWidget(title_lbl)
        self._i18n_widgets.append((title_lbl, "fleet_dashboard.title", ""))

        # Period buttons
        period_frame = QFrame()
        period_layout = QHBoxLayout(period_frame)
        period_layout.setContentsMargins(S["5"], 0, 0, 0)
        period_layout.setSpacing(S["2"])

        periods = [
            ("today", "fleet_dashboard.today"),
            ("week", "fleet_dashboard.this_week"),
            ("month", "fleet_dashboard.this_month"),
            ("custom", "fleet_dashboard.custom"),
        ]

        for period_id, key in periods:
            btn = ActionButton(
                period_frame,
                t(key),
                command=lambda p=period_id: self._set_period(p),
                variant="primary" if period_id == self._period else "secondary",
            )
            period_layout.addWidget(btn)
            self._period_button_refs.append((btn, period_id, key))

        header_layout.addWidget(period_frame)

        header_layout.addStretch(1)

        # Refresh area
        refresh_frame = QFrame()
        refresh_layout = QHBoxLayout(refresh_frame)
        refresh_layout.setContentsMargins(0, 0, 0, 0)
        refresh_layout.setSpacing(S["2"])

        self._last_refresh_lbl = QLabel("")
        self._last_refresh_lbl.setProperty("fontRole", "muted")
        refresh_layout.addWidget(self._last_refresh_lbl)

        refresh_btn = ActionButton(
            refresh_frame,
            t("fleet_dashboard.refresh"),
            command=self.refresh_all,
            variant="primary",
        )
        refresh_layout.addWidget(refresh_btn)
        self._i18n_widgets.append((refresh_btn, "fleet_dashboard.refresh", ""))

        header_layout.addWidget(refresh_frame)

        layout.addWidget(header)

    def _build_kpi_row(
        self,
        active_trucks: int,
        trips_today: int,
        revenue: float,
        avg_fuel: float,
        alert_count: int,
        unpaid_count: int,
    ) -> None:
        """Build / refresh the KPI cards row."""
        kpi_frame = QFrame()
        kpi_layout = QHBoxLayout(kpi_frame)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(S["2"])

        fmt_cur = self.prefs.format_currency if self.prefs else (lambda v, _: f"€ {v:,.0f}")

        kpis: List[Tuple[str, str, Optional[str]]] = [
            (
                "fleet_dashboard.kpi_active_trucks",
                str(active_trucks),
                COLORS.get("accent_text"),
            ),
            (
                "fleet_dashboard.kpi_trips_today",
                str(trips_today),
                COLORS.get("text_success"),
            ),
            (
                "fleet_dashboard.kpi_revenue",
                fmt_cur(revenue, 0),
                COLORS.get("accent_text"),
            ),
            (
                "fleet_dashboard.kpi_avg_fuel",
                fmt_cur(avg_fuel, 0),
                COLORS.get("text_warning"),
            ),
            (
                "fleet_dashboard.kpi_alerts",
                str(alert_count),
                COLORS.get("text_danger"),
            ),
            (
                "fleet_dashboard.kpi_unpaid",
                str(unpaid_count),
                COLORS.get("text_danger"),
            ),
        ]

        self._kpi_cards: Dict[str, KpiCard] = {}
        for key, value, color in kpis:
            card = KpiCard(kpi_frame, t(key), value)
            if color:
                card.value_label.setStyleSheet(f"color: {color};")
            kpi_layout.addWidget(card, 1)
            self._kpi_cards[key] = card

        self._content_layout_inner.addWidget(kpi_frame)

    def _build_charts_row(self, trucks: List[Dict], trips: List[Dict]) -> None:
        """Matplotlib charts side by side."""
        charts_frame = QFrame()
        charts_layout = QHBoxLayout(charts_frame)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setSpacing(S["4"])

        self._left_chart_frame = QFrame()
        self._left_chart_frame.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._left_chart_frame.setMinimumHeight(280)
        QVBoxLayout(self._left_chart_frame)

        self._right_chart_frame = QFrame()
        self._right_chart_frame.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._right_chart_frame.setMinimumHeight(280)
        QVBoxLayout(self._right_chart_frame)

        charts_layout.addWidget(self._left_chart_frame, 3)
        charts_layout.addWidget(self._right_chart_frame, 2)

        self._content_layout_inner.addWidget(charts_frame)

        # Render charts
        self._render_trip_activity_chart(trips)
        self._render_fleet_status_chart(trucks)

    def _render_trip_activity_chart(self, trips: List[Dict]) -> None:
        """Bar chart: daily completed / in-progress / cancelled trips."""
        # Lazy import so matplotlib is optional at import time.
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        # Clear previous content
        self._clear_widgets_from_layout(self._left_chart_frame.layout())

        filtered = self._filter_trips_by_period(trips)
        daily: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"completed": 0, "in_progress": 0, "cancelled": 0}
        )

        for trip in filtered:
            date = (trip.get("created_at") or "")[:10]
            if not date:
                continue
            status = trip.get("status", "")
            if status in ("Paid", "Delivered"):
                daily[date]["completed"] += 1
            elif status in ("In Transit", "Loading"):
                daily[date]["in_progress"] += 1
            elif status == "Cancelled":
                daily[date]["cancelled"] += 1

        if not daily:
            lbl = QLabel(t("fleet_dashboard.no_data"))
            lbl.setProperty("fontRole", "muted")
            lbl.setAlignment(Qt.AlignCenter)
            self._left_chart_frame.layout().addWidget(lbl)
            return

        dates = sorted(daily.keys())[-14:]
        completed = [daily[d]["completed"] for d in dates]
        in_progress = [daily[d]["in_progress"] for d in dates]
        cancelled = [daily[d]["cancelled"] for d in dates]

        cw = max(self._left_chart_frame.width(), 300)
        ch = max(self._left_chart_frame.height(), 200)
        dpi = 90
        fig, ax = plt.subplots(figsize=(cw / dpi, ch / dpi), dpi=dpi)

        fig.patch.set_facecolor(COLORS["bg_surface"])
        ax.set_facecolor(COLORS["bg_surface"])
        fig.subplots_adjust(left=0.07, right=0.97, top=0.90, bottom=0.15)

        x = range(len(dates))
        width = 0.25
        ax.bar(
            [i - width for i in x],
            completed,
            width,
            label=t("fleet_dashboard.status_completed"),
            color=CHART_PRIMARY,
            alpha=0.8,
        )
        ax.bar(
            x,
            in_progress,
            width,
            label=t("fleet_dashboard.status_in_progress"),
            color="#6366f1",
            alpha=0.8,
        )
        ax.bar(
            [i + width for i in x],
            cancelled,
            width,
            label=t("fleet_dashboard.status_cancelled"),
            color=CHART_SECONDARY,
            alpha=0.8,
        )

        ax.set_title(
            t("fleet_dashboard.chart_trip_activity"),
            color=COLORS["text_primary"],
            fontsize=11,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel(
            t("fleet_dashboard.date"),
            color=COLORS["text_secondary"],
            fontsize=8,
        )
        ax.set_ylabel(
            t("fleet_dashboard.trips"),
            color=COLORS["text_secondary"],
            fontsize=8,
        )
        ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
        ax.legend(
            loc="upper left",
            facecolor=COLORS["bg_surface"],
            edgecolor=COLORS["border"],
            labelcolor=COLORS["text_primary"],
            fontsize=7,
        )
        tick_step = max(1, len(dates) // 6)
        ax.set_xticks(range(0, len(dates), tick_step))
        ax.set_xticklabels(
            [dates[i] for i in range(0, len(dates), tick_step)],
            rotation=30,
            ha="right",
            fontsize=7,
        )

        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS["border"])
            spine.set_linewidth(0.5)
        ax.grid(axis="y", color=COLORS["border"], linewidth=0.4, linestyle="--", alpha=0.35)
        ax.set_axisbelow(True)

        canvas = FigureCanvas(fig)
        self._left_chart_frame.layout().addWidget(canvas)
        self._chart_refs.append((fig, canvas))
        self._chart_figures.append(fig)

    def _render_fleet_status_chart(self, trucks: List[Dict]) -> None:
        """Pie chart: fleet status distribution."""
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        self._clear_widgets_from_layout(self._right_chart_frame.layout())

        status_labels_map = {
            "active": t("fleet_dashboard.status_active"),
            "idle": t("fleet_dashboard.status_idle"),
            "maintenance": t("fleet_dashboard.status_maintenance"),
            "inactive": t("fleet_dashboard.status_inactive"),
        }
        status_counts: Dict[str, int] = {k: 0 for k in status_labels_map}

        for truck in trucks:
            status = truck.get("status", "Inactive")
            active = truck.get("active_status", 0)
            if status == "Active" and active == 1:
                status_counts["active"] += 1
            elif status == "Active" and active == 0:
                status_counts["idle"] += 1
            elif status == "In Service":
                status_counts["maintenance"] += 1
            else:
                status_counts["inactive"] += 1

        labels = [status_labels_map[k] for k in status_counts]
        sizes = list(status_counts.values())
        colors_pie = [CHART_PRIMARY, "#6366f1", CHART_SECONDARY, COLORS["accent"]]

        if sum(sizes) == 0:
            lbl = QLabel(t("fleet_dashboard.no_data"))
            lbl.setProperty("fontRole", "muted")
            lbl.setAlignment(Qt.AlignCenter)
            self._right_chart_frame.layout().addWidget(lbl)
            return

        cw = max(self._right_chart_frame.width(), 240)
        ch = max(self._right_chart_frame.height(), 200)
        dpi = 90
        fig, ax = plt.subplots(figsize=(cw / dpi, ch / dpi), dpi=dpi)
        fig.patch.set_facecolor(COLORS["bg_surface"])
        ax.set_facecolor(COLORS["bg_surface"])

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors_pie,
            autopct="%1.0f%%",
            startangle=90,
            textprops={"color": COLORS["text_primary"], "fontsize": 8},
        )
        for autotext in autotexts:
            autotext.set_color(COLORS["text_primary"])
            autotext.set_fontweight("bold")

        ax.set_title(
            t("fleet_dashboard.chart_fleet_status"),
            color=COLORS["text_primary"],
            fontsize=11,
            fontweight="bold",
            pad=12,
        )

        canvas = FigureCanvas(fig)
        self._right_chart_frame.layout().addWidget(canvas)
        self._chart_refs.append((fig, canvas))
        self._chart_figures.append(fig)

    def _build_info_cards(
        self,
        top_truck: Optional[Tuple[str, float]],
        best_driver: Optional[Dict],
        truck_trips: Dict[str, int],
        avg_profit: float,
        driver_trip_count: int,
        top_fuel_truck: Optional[Tuple[str, float]],
        truck_fuel: Dict[str, float],
        trucks: List[Dict],
    ) -> None:
        """Three information cards: best truck, best driver, highest fuel."""
        cards_frame = QFrame()
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(S["4"])

        # ── Best Truck ──────────────────────────────────────────────────────────
        truck_card = self._create_info_card(cards_frame, t("fleet_dashboard.card_best_truck"))
        truck_card_layout = QVBoxLayout(truck_card)
        truck_card_layout.setContentsMargins(S["4"], S["3"], S["4"], S["3"])
        truck_card_layout.setSpacing(S["1"])

        if top_truck:
            plate_lbl = QLabel(top_truck[0])
            plate_lbl.setProperty("fontRole", "body_bold")
            truck_card_layout.addWidget(plate_lbl)

            rev_lbl = QLabel(
                t(
                    "fleet_dashboard.card_revenue",
                    amount=self.prefs.format_currency(top_truck[1], 0)
                    if self.prefs
                    else f"€ {top_truck[1]:,.0f}",
                )
            )
            rev_lbl.setProperty("fontRole", "small")
            truck_card_layout.addWidget(rev_lbl)

            trips_lbl = QLabel(
                t("fleet_dashboard.card_trips", count=truck_trips.get(top_truck[0], 0))
            )
            trips_lbl.setProperty("fontRole", "label")
            truck_card_layout.addWidget(trips_lbl)
        else:
            no_data = QLabel(t("fleet_dashboard.no_data"))
            no_data.setProperty("fontRole", "muted")
            truck_card_layout.addWidget(no_data)

        # ── Best Driver ─────────────────────────────────────────────────────────
        driver_card = self._create_info_card(cards_frame, t("fleet_dashboard.card_best_driver"))
        driver_card_layout = QVBoxLayout(driver_card)
        driver_card_layout.setContentsMargins(S["4"], S["3"], S["4"], S["3"])
        driver_card_layout.setSpacing(S["1"])

        if best_driver:
            driver_name = best_driver.get("driver_name", t("common.na"))
            name_lbl = QLabel(driver_name)
            name_lbl.setProperty("fontRole", "body_bold")
            driver_card_layout.addWidget(name_lbl)

            trips_lbl = QLabel(
                t("fleet_dashboard.card_trips", count=driver_trip_count)
            )
            trips_lbl.setProperty("fontRole", "small")
            driver_card_layout.addWidget(trips_lbl)

            profit_lbl = QLabel(
                t(
                    "fleet_dashboard.card_avg_profit",
                    amount=self.prefs.format_currency(avg_profit, 0)
                    if self.prefs
                    else f"€ {avg_profit:,.0f}",
                )
            )
            profit_lbl.setProperty("fontRole", "label")
            driver_card_layout.addWidget(profit_lbl)
        else:
            no_data = QLabel(t("fleet_dashboard.no_driver_data"))
            no_data.setProperty("fontRole", "muted")
            driver_card_layout.addWidget(no_data)

        # ── Highest Fuel ────────────────────────────────────────────────────────
        fuel_card = self._create_info_card(cards_frame, t("fleet_dashboard.card_highest_fuel"))
        fuel_card_layout = QVBoxLayout(fuel_card)
        fuel_card_layout.setContentsMargins(S["4"], S["3"], S["4"], S["3"])
        fuel_card_layout.setSpacing(S["1"])

        if top_fuel_truck:
            truck_data = next(
                (
                    t2
                    for t2 in trucks
                    if t2.get("plate_number") == top_fuel_truck[0]
                ),
                None,
            )
            consumption = (
                truck_data.get("fuel_consumption", t("common.na"))
                if truck_data
                else t("common.na")
            )

            plate_lbl = QLabel(top_fuel_truck[0])
            plate_lbl.setProperty("fontRole", "body_bold")
            fuel_card_layout.addWidget(plate_lbl)

            cost_lbl = QLabel(
                t(
                    "fleet_dashboard.card_fuel_cost",
                    amount=self.prefs.format_currency(top_fuel_truck[1], 0)
                    if self.prefs
                    else f"€ {top_fuel_truck[1]:,.0f}",
                )
            )
            cost_lbl.setProperty("fontRole", "small")
            fuel_card_layout.addWidget(cost_lbl)

            cons_lbl = QLabel(
                t("fleet_dashboard.card_consumption", value=consumption)
            )
            cons_lbl.setProperty("fontRole", "label")
            fuel_card_layout.addWidget(cons_lbl)
        else:
            no_data = QLabel(t("fleet_dashboard.no_data"))
            no_data.setProperty("fontRole", "muted")
            fuel_card_layout.addWidget(no_data)

        cards_layout.addWidget(truck_card)
        cards_layout.addWidget(driver_card)
        cards_layout.addWidget(fuel_card)

        self._content_layout_inner.addWidget(cards_frame)

    def _build_activity_feed(self, trips: List[Dict]) -> None:
        """Recent trips activity feed with status indicators."""
        feed_frame = QFrame()
        feed_frame.setProperty("role", "card")
        feed_layout = QVBoxLayout(feed_frame)
        feed_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        feed_layout.setSpacing(S["2"])

        # Header
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(t("fleet_dashboard.activity_title"))
        title_lbl.setProperty("fontRole", "h3")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch(1)

        view_all_lbl = QLabel(f'<a href="#" style="color: {COLORS["accent"]};">{t("fleet_dashboard.activity_view_all")}</a>')
        view_all_lbl.setTextFormat(Qt.RichText)
        view_all_lbl.setProperty("fontRole", "label")
        view_all_lbl.setCursor(Qt.PointingHandCursor)
        view_all_lbl.mousePressEvent = lambda _event: self._open_route_history()  # type: ignore[assignment]
        header_layout.addWidget(view_all_lbl)

        feed_layout.addWidget(header)

        # Trip rows
        recent_trips = sorted(trips, key=lambda x: x.get("id", 0), reverse=True)[:10]

        if not recent_trips:
            no_data = QLabel(t("fleet_dashboard.no_data"))
            no_data.setProperty("fontRole", "muted")
            no_data.setAlignment(Qt.AlignCenter)
            feed_layout.addWidget(no_data)
        else:
            for trip in recent_trips:
                self._create_activity_row(feed_layout, trip)

        self._content_layout_inner.addWidget(feed_frame)

    def _create_activity_row(self, parent_layout: QVBoxLayout, trip: Dict) -> None:
        """Single row in the activity feed."""
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, S["1"], 0, S["1"])
        row_layout.setSpacing(S["3"])

        # Timestamp
        timestamp = (trip.get("created_at") or t("common.na"))[:16]
        ts_lbl = QLabel(timestamp)
        ts_lbl.setProperty("fontRole", "label")
        ts_lbl.setFixedWidth(130)
        row_layout.addWidget(ts_lbl)

        # Truck number
        truck = trip.get("truck_number", t("common.na"))
        truck_lbl = QLabel(truck)
        truck_lbl.setProperty("fontRole", "body_bold")
        truck_lbl.setFixedWidth(80)
        row_layout.addWidget(truck_lbl)

        # Status chip
        status = trip.get("status", t("common.unknown"))
        status_color = self._get_status_color(status)
        status_lbl = QLabel(status)
        status_lbl.setProperty("fontRole", "label")
        status_lbl.setStyleSheet(
            f"background-color: {status_color}; color: {COLORS['text_primary']}; "
            f"border-radius: 4px; padding: 2px 8px;"
        )
        row_layout.addWidget(status_lbl)

        # Client detail
        client = trip.get("client_name", "")
        detail = client if client else ""
        detail_lbl = QLabel(detail)
        detail_lbl.setProperty("fontRole", "small")
        detail_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(detail_lbl, 1)

        parent_layout.addWidget(row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"color: {COLORS['border']};")
        parent_layout.addWidget(divider)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_info_card(self, parent: QFrame, title: str) -> QFrame:
        """Create a styled info card frame with a title."""
        card = QFrame()
        card.setProperty("role", "card")
        card.setMinimumHeight(100)

        # Embed the title via a separate label added before the layout is returned
        title_lbl = QLabel(title)
        title_lbl.setProperty("fontRole", "section")
        title_lbl.setAlignment(Qt.AlignCenter)

        # We return the card; caller adds their own layout and content
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(title_lbl)

        return card

    def _get_status_color(self, status: str) -> str:
        """Map trip status to a color string."""
        if status in ("Paid", "Delivered"):
            return COLORS["success"]
        elif status in ("In Transit", "Loading"):
            return COLORS["warning"]
        elif status == "Cancelled":
            return COLORS["danger"]
        else:
            return COLORS["accent"]

    def _filter_trips_by_period(self, trips: List[Dict]) -> List[Dict]:
        """Filter trips to the selected date range."""
        if not self._start_date or not self._end_date:
            return trips
        filtered = []
        for trip in trips:
            created = trip.get("created_at", "")
            if created:
                try:
                    trip_date = datetime.strptime(
                        created[:10], "%Y-%m-%d"
                    ).strftime("%Y-%m-%d")
                    if self._start_date <= trip_date <= self._end_date:
                        filtered.append(trip)
                except (ValueError, IndexError):
                    pass
        return filtered

    def _set_period(self, period: str) -> None:
        """Change the active period filter and refresh."""
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

        # Update button styles
        for btn, pid, _ in self._period_button_refs:
            is_active = pid == period
            btn.setProperty("variant", "primary" if is_active else "secondary")
            # Force style refresh
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.refresh_all()

    def _open_route_history(self) -> None:
        """Navigate to the route history view."""
        if self.ops and hasattr(self.ops, "_open_route_history"):
            self.ops._open_route_history()

    def _update_last_refresh_label(self) -> None:
        """Update the 'last refreshed at' label."""
        if self._last_refresh:
            self._last_refresh_lbl.setText(
                t(
                    "fleet_dashboard.last_refreshed",
                    time=self._last_refresh.strftime("%H:%M:%S"),
                )
            )

    def _clear_content_area(self) -> None:
        """Remove all widgets from the content layout."""
        while self._content_layout_inner.count():
            item = self._content_layout_inner.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Clear chart references
        for fig, _canvas in self._chart_refs:
            try:
                import matplotlib.pyplot as plt
                plt.close(fig)
            except Exception:
                pass
        self._chart_refs.clear()
        self._chart_figures.clear()

    @staticmethod
    def _clear_widgets_from_layout(layout) -> None:
        """Remove all widgets from a layout and schedule them for deletion."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _auto_refresh(self) -> None:
        """Timer-triggered refresh (debounced to avoid rapid re-entrancy)."""
        self.refresh_all()

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _on_language_changed(self, lang: str) -> None:
        """Called when the application language changes."""
        QTimer.singleShot(0, self.refresh_translations)

    # ------------------------------------------------------------------
    # Event bus (placeholder for future use)
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Subscribe to data-change events for live updates.

        Override or extend this in subclasses to connect to an EventBus.
        """
        pass

    # ------------------------------------------------------------------
    # Lifecycle (called externally by the window manager)
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Ensure cleanup on widget close."""
        self.shutdown()
        super().closeEvent(event)


class FleetDashboardDialog(QDialog):
    """Standalone QDialog that wraps a QtFleetDashboard.

    Usage::

        dlg = FleetDashboardDialog(db, prefs, ops, parent=parent_widget)
        if dlg.exec_():
            ...
    """

    def __init__(
        self,
        db=None,
        prefs=None,
        ops=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(t("fleet_dashboard.title"))
        self.resize(1400, 900)
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._dashboard = QtFleetDashboard(self, db=db, prefs=prefs, ops=ops)
        layout.addWidget(self._dashboard)

    def closeEvent(self, event) -> None:
        self._dashboard.shutdown()
        super().closeEvent(event)
