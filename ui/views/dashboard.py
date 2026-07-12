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

import contextlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.app_state import AppState
from services.i18n import register_listener, t, unregister_listener
from ui.components import (
    Btn,
    EmptyState,
    KPICard,
    PageTitle,
)
from ui.design_tokens import (
    ACCENT_TEXT,
    DANGER_TEXT,
    SP,
    SUCCESS_TEXT,
    WARNING_TEXT,
)
from ui.theme import CHART_PRIMARY, CHART_SECONDARY, COLORS

logger = logging.getLogger(__name__)


class QtFleetDashboard(QWidget):
    """Fleet overview dashboard with KPIs, charts, info cards and activity feed.

    Can be embedded in a parent QWidget. For standalone windowed mode use
    ``FleetDashboardDialog``.
    """

    REFRESH_INTERVAL_MS = 30_000

    def __init__(
        self,
        parent: QWidget | None = None,
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
        self._start_date: str | None = None
        self._end_date: str | None = None
        self._last_refresh: datetime | None = None
        self._shutting_down = False

        # ── Chart references (for cleanup) ──────────────────────────────────────
        self._chart_refs: list[Any] = []

        # ── i18n ────────────────────────────────────────────────────────────────
        self._i18n_widgets: list[tuple[Any, str, str]] = []
        self._period_button_refs: list[tuple[Btn, str, str]] = []
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        app_state = AppState()
        self._app_state_token = app_state.subscribe("language", self._language_callback)

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
        """Re-fetch data and rebuild all cards, charts and the activity feed.

        Business logic delegated to services:
        - ``AnalyticsService.get_financial()`` for revenue/profit aggregation
        - ``AnalyticsService.get_fleet()`` for per-truck stats
        - ``AnalyticsService.get_driver()`` for per-driver stats
        - ``AnalyticsService.get_overdue_data()`` for overdue alerts
        """
        self._last_refresh = datetime.now()
        self._update_last_refresh_label()

        try:
            from services.analytics_service import AnalyticsService
            from services.fleet_service import FleetService
            from services.trip_service import TripService

            analytics_svc = AnalyticsService(self.db) if self.db else None
            fleet_svc = FleetService(self.db) if self.db else None
            trip_svc = TripService(self.db) if self.db else None

            trucks = fleet_svc.get_trucks() if fleet_svc else []
            trips = trip_svc.get_all() if trip_svc else []

            # ── Delegate analytics calculations to AnalyticsService ────────────
            alerts, _ = analytics_svc.get_overdue_data() if analytics_svc else ([], None)

            if analytics_svc:
                financial_data = analytics_svc.get_financial(self._start_date, self._end_date)
                fleet_data = analytics_svc.get_fleet(self._start_date, self._end_date)
                driver_data = analytics_svc.get_driver(self._start_date, self._end_date)
            else:
                financial_data = []
                fleet_data = []
                driver_data = []

            # ── Derive display values from service results ────────────────────
            today_str = datetime.now().strftime("%Y-%m-%d")

            # Revenue: sum of monthly revenue from financial aggregate
            revenue = sum((r.get("revenue", 0) or 0) for r in financial_data)

            # Active trucks: count from FleetService (active_status == 1)
            active_trucks = sum(
                1 for t in trucks
                if t.get("active_status") == 1 or t.get("status") == "Active"
            )

            # Trips today: count of trips starting today or in-progress today
            trips_today = sum(
                1 for trip in trips
                if trip.get("start_date") == today_str
                or (
                    trip.get("status") in ("In Transit", "Loading")
                    and str(trip.get("created_at", ""))[:10] == today_str
                )
            )

            # Fuel stats from fleet data (per-truck aggregation)
            fuel_costs = [f["total_fuel_cost"] for f in fleet_data if f.get("total_fuel_cost")]
            total_fuel = sum(fuel_costs)
            fuel_count = len(fuel_costs)
            avg_fuel = total_fuel / fuel_count if fuel_count else 0

            # Per-truck trip/fuel dicts from fleet analytics
            truck_trips: dict[str, int] = {
                row["truck"]: row["trip_count"]
                for row in fleet_data
            }
            truck_fuel: dict[str, float] = {
                row["truck"]: (row.get("total_fuel_cost", 0) or 0)
                for row in fleet_data
            }

            # Top truck by profit (first row from fleet_data, sorted DESC)
            top_truck = (
                (fleet_data[0]["truck"], fleet_data[0]["profit"])
                if fleet_data
                else None
            )

            # Top fuel truck: truck with highest total_fuel_cost
            top_fuel_row = (
                max(fleet_data, key=lambda r: r.get("total_fuel_cost", 0) or 0)
                if fleet_data
                else None
            )
            top_fuel_truck = (
                (top_fuel_row["truck"], top_fuel_row["total_fuel_cost"])
                if top_fuel_row
                else None
            )

            # Best driver from driver analytics (first row = highest profit)
            best_driver = driver_data[0] if driver_data else None
            driver_trip_count = best_driver.get("trip_count", 0) if best_driver else 0
            avg_profit = (
                (best_driver.get("profit", 0) or 0) / driver_trip_count
                if best_driver and driver_trip_count
                else 0
            )

            # Unpaid/overdue invoice count from overdue alerts
            unpaid_count = sum(
                1 for a in alerts
                if a.get("type") == "RED" and "Factura" in a.get("msg", "")
            )

        except Exception as exc:
            logger.exception("FleetDashboard refresh_all failed")
            QMessageBox.warning(
                self,
                t("fleet_dashboard.error_title"),
                t("fleet_dashboard.error_msg").format(str(exc)),
            )
            return

        # ── Clear and rebuild content area ─────────────────────────────────────
        self._clear_content_area()

        self._build_kpi_row(
            active_trucks,
            trips_today,
            revenue,
            avg_fuel,
            len(alerts),
            unpaid_count,
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
        """Re-activate the dashboard (e.g. after it was hidden / detached).

        The previously-rendered chart widgets and their ``QPixmap``
        objects are kept alive across view-switches (see
        ``shutdown``), so the common case — re-entering the dashboard
        after visiting another module — does not trigger a
        re-render.  ``refresh_all`` re-queries the cheap data and
        updates the chart figures; if the chart signature is unchanged
        the existing ``QPixmap`` is reused.
        """
        self.refresh_all()

    def shutdown(self) -> None:
        """Clean up timers and listeners; keep chart widgets alive.

        The chart widgets and their rendered ``QPixmap`` objects are
        preserved across view-switches, so re-entering the dashboard
        does not require a re-render.  We only stop the timer
        and unsubscribe listeners here.
        """
        self._shutting_down = True
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

        # Unsubscribe i18n
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        with contextlib.suppress(Exception):
            AppState().unsubscribe("language", self._language_callback)

    def refresh_translations(self) -> None:
        """Update all visible text after a language change."""
        for widget, key, prefix in self._i18n_widgets:
            try:
                if isinstance(widget, (QLabel, QPushButton)):
                    widget.setText(f"{prefix}{t(key)}")
            except Exception:
                pass
        for btn, _pid, key in self._period_button_refs:
            with contextlib.suppress(Exception):
                btn.setText(t(key))
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
        content_layout.setContentsMargins(SP["10"], SP["6"], SP["10"], SP["6"])
        content_layout.setSpacing(SP["4"])
        content_layout.setAlignment(Qt.AlignTop)

        self._build_header(content_layout)

        # This frame holds the dynamically replaced content
        self._content_frame = QFrame()
        self._content_frame.setProperty("role", "card")
        self._content_layout_inner = QVBoxLayout(self._content_frame)
        self._content_layout_inner.setContentsMargins(0, 0, 0, 0)
        self._content_layout_inner.setSpacing(SP["4"])
        content_layout.addWidget(self._content_frame, 1)

        layout.addWidget(scroll)

    def _build_header(self, layout: QVBoxLayout) -> None:
        """Title bar + period filter buttons + refresh button."""
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title_lbl = PageTitle(None, t("fleet_dashboard.title"))
        header_layout.addWidget(title_lbl)
        self._i18n_widgets.append((title_lbl, "fleet_dashboard.title", ""))

        # Period buttons
        period_frame = QFrame()
        period_layout = QHBoxLayout(period_frame)
        period_layout.setContentsMargins(SP["5"], 0, 0, 0)
        period_layout.setSpacing(SP["2"])

        periods = [
            ("today", "fleet_dashboard.today"),
            ("week", "fleet_dashboard.this_week"),
            ("month", "fleet_dashboard.this_month"),
            ("custom", "fleet_dashboard.custom"),
        ]

        for period_id, key in periods:
            btn = Btn(
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
        refresh_layout.setSpacing(SP["2"])

        self._last_refresh_lbl = QLabel("")
        self._last_refresh_lbl.setProperty("fontRole", "muted")
        refresh_layout.addWidget(self._last_refresh_lbl)

        refresh_btn = Btn(
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
        kpi_layout.setSpacing(SP["2"])

        fmt_cur = self.prefs.format_currency if self.prefs else (lambda v, _: f"€ {v:,.0f}")

        kpi_colors = {
            "fleet_dashboard.kpi_active_trucks": ACCENT_TEXT,
            "fleet_dashboard.kpi_trips_today": SUCCESS_TEXT,
            "fleet_dashboard.kpi_revenue": ACCENT_TEXT,
            "fleet_dashboard.kpi_avg_fuel": WARNING_TEXT,
            "fleet_dashboard.kpi_alerts": DANGER_TEXT,
            "fleet_dashboard.kpi_unpaid": DANGER_TEXT,
        }
        kpi_defs: list[tuple[str, str]] = [
            ("fleet_dashboard.kpi_active_trucks", str(active_trucks)),
            ("fleet_dashboard.kpi_trips_today", str(trips_today)),
            ("fleet_dashboard.kpi_revenue", fmt_cur(revenue, 0)),
            ("fleet_dashboard.kpi_avg_fuel", fmt_cur(avg_fuel, 0)),
            ("fleet_dashboard.kpi_alerts", str(alert_count)),
            ("fleet_dashboard.kpi_unpaid", str(unpaid_count)),
        ]

        self._kpi_cards: dict[str, QFrame] = {}
        for key, value in kpi_defs:
            card = KPICard(kpi_frame, t(key), value,
                           value_color=kpi_colors.get(key))
            kpi_layout.addWidget(card, 1)
            self._kpi_cards[key] = card

        self._content_layout_inner.addWidget(kpi_frame)

    def _build_charts_row(self, trucks: list[dict], trips: list[dict]) -> None:
        """Matplotlib charts side by side."""
        charts_frame = QFrame()
        charts_layout = QHBoxLayout(charts_frame)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setSpacing(SP["4"])

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

    def _render_trip_activity_chart(self, trips: list[dict]) -> None:
        """Bar chart: daily completed / in-progress / cancelled trips."""
        from ui.plotly_charts import make_grouped_bar_chart
        from ui.plotly_renderer import PlotlyChartWidget

        # Clear previous content
        self._clear_widgets_from_layout(self._left_chart_frame.layout())

        filtered = self._filter_trips_by_period(trips)
        daily: dict[str, dict[str, int]] = defaultdict(
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
            empty = EmptyState(
                self._left_chart_frame,
                icon_name="mdi6.chart-bar",
                title=t("fleet_dashboard.no_data"),
            )
            self._left_chart_frame.layout().addWidget(empty)
            return

        dates = sorted(daily.keys())[-14:]
        completed = [daily[d]["completed"] for d in dates]
        in_progress = [daily[d]["in_progress"] for d in dates]
        cancelled = [daily[d]["cancelled"] for d in dates]

        fig = make_grouped_bar_chart(
            dates,
            [
                (t("fleet_dashboard.status_completed"), completed, CHART_PRIMARY),
                (t("fleet_dashboard.status_in_progress"), in_progress, "#6366f1"),
                (t("fleet_dashboard.status_cancelled"), cancelled, CHART_SECONDARY),
            ],
            title=t("fleet_dashboard.chart_trip_activity"),
            horizontal=False,
            show_title=True,
        )

        chart_widget = PlotlyChartWidget(min_height=200)
        chart_widget.set_figure(fig)
        self._left_chart_frame.layout().addWidget(chart_widget)
        self._chart_refs.append(chart_widget)

    def _render_fleet_status_chart(self, trucks: list[dict]) -> None:
        """Pie chart: fleet status distribution."""
        from ui.plotly_charts import make_pie_chart
        from ui.plotly_renderer import PlotlyChartWidget

        self._clear_widgets_from_layout(self._right_chart_frame.layout())

        status_labels_map = {
            "active": t("fleet_dashboard.status_active"),
            "idle": t("fleet_dashboard.status_idle"),
            "maintenance": t("fleet_dashboard.status_maintenance"),
            "inactive": t("fleet_dashboard.status_inactive"),
        }
        status_counts: dict[str, int] = dict.fromkeys(status_labels_map, 0)

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
            empty = EmptyState(
                self._right_chart_frame,
                icon_name="mdi6.chart-pie",
                title=t("fleet_dashboard.no_data"),
            )
            self._right_chart_frame.layout().addWidget(empty)
            return

        fig = make_pie_chart(
            sizes, labels,
            title=t("fleet_dashboard.chart_fleet_status"),
            colors=colors_pie,
            show_title=True,
        )

        chart_widget = PlotlyChartWidget(min_height=200)
        chart_widget.set_figure(fig)
        self._right_chart_frame.layout().addWidget(chart_widget)
        self._chart_refs.append(chart_widget)

    def _build_info_cards(
        self,
        top_truck: tuple[str, float] | None,
        best_driver: dict | None,
        truck_trips: dict[str, int],
        avg_profit: float,
        driver_trip_count: int,
        top_fuel_truck: tuple[str, float] | None,
        truck_fuel: dict[str, float],
        trucks: list[dict],
    ) -> None:
        """Three information cards: best truck, best driver, highest fuel."""
        cards_frame = QFrame()
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(SP["4"])

        # ── Best Truck ──────────────────────────────────────────────────────────
        truck_card = self._create_info_card(cards_frame, t("fleet_dashboard.card_best_truck"))
        truck_card_layout = QVBoxLayout(truck_card)
        truck_card_layout.setContentsMargins(SP["4"], SP["3"], SP["4"], SP["3"])
        truck_card_layout.setSpacing(SP["1"])

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
            empty = EmptyState(
                truck_card,
                icon_name="mdi6.truck",
                title=t("fleet_dashboard.no_data"),
            )
            truck_card_layout.addWidget(empty)

        # ── Best Driver ─────────────────────────────────────────────────────────
        driver_card = self._create_info_card(cards_frame, t("fleet_dashboard.card_best_driver"))
        driver_card_layout = QVBoxLayout(driver_card)
        driver_card_layout.setContentsMargins(SP["4"], SP["3"], SP["4"], SP["3"])
        driver_card_layout.setSpacing(SP["1"])

        if best_driver:
            driver_name = best_driver.get("driver", t("common.na"))
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
            empty = EmptyState(
                driver_card,
                icon_name="mdi6.account",
                title=t("fleet_dashboard.no_driver_data"),
            )
            driver_card_layout.addWidget(empty)

        # ── Highest Fuel ────────────────────────────────────────────────────────
        fuel_card = self._create_info_card(cards_frame, t("fleet_dashboard.card_highest_fuel"))
        fuel_card_layout = QVBoxLayout(fuel_card)
        fuel_card_layout.setContentsMargins(SP["4"], SP["3"], SP["4"], SP["3"])
        fuel_card_layout.setSpacing(SP["1"])

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
            empty = EmptyState(
                fuel_card,
                icon_name="mdi6.gas-station",
                title=t("fleet_dashboard.no_data"),
            )
            fuel_card_layout.addWidget(empty)

        cards_layout.addWidget(truck_card)
        cards_layout.addWidget(driver_card)
        cards_layout.addWidget(fuel_card)

        self._content_layout_inner.addWidget(cards_frame)

    def _build_activity_feed(self, trips: list[dict]) -> None:
        """Recent trips activity feed with status indicators."""
        feed_frame = QFrame()
        feed_frame.setProperty("role", "card")
        feed_layout = QVBoxLayout(feed_frame)
        feed_layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        feed_layout.setSpacing(SP["2"])

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
            empty = EmptyState(
                feed_frame,
                icon_name="mdi6.clipboard-text-outline",
                title=t("fleet_dashboard.no_data"),
            )
            feed_layout.addWidget(empty)
        else:
            for trip in recent_trips:
                self._create_activity_row(feed_layout, trip)

        self._content_layout_inner.addWidget(feed_frame)

    def _create_activity_row(self, parent_layout: QVBoxLayout, trip: dict) -> None:
        """Single row in the activity feed."""
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, SP["1"], 0, SP["1"])
        row_layout.setSpacing(SP["3"])

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
            return COLORS.get("chip_cancelled", "#6B7280")
        else:
            return COLORS["accent"]

    def _filter_trips_by_period(self, trips: list[dict]) -> list[dict]:
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
        for widget in self._chart_refs:
            try:
                widget.setParent(None)
                widget.deleteLater()
            except Exception:
                pass
        self._chart_refs.clear()

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
        if getattr(self, "_shutting_down", False):
            return
        try:
            self.isVisible()
        except RuntimeError:
            return
        self.refresh_all()

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _on_language_changed(self, lang: str) -> None:
        """Called when the application language changes."""
        QTimer.singleShot(0, self.refresh_translations)

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
        parent: QWidget | None = None,
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
