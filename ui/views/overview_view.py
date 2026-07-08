"""PySide6 overview dashboard view.

Replaces ``ui/overview.py``. Displays KPI cards, a profit chart, active trips,
alerts, top trucks, and recent activity.
"""

from __future__ import annotations

import contextlib
import logging
import random
import time
from datetime import datetime
from typing import Any

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.base_view import BaseView
from services.invoicing.config_manager import load_company_config
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    TRIP_CREATED,
    TRIP_STATUS_CHANGED,
    TRIP_UPDATED,
    TRUCK_UPDATED,
)
from ui.components import (
    Card,
    CompactKPICard,
    EmptyState,
    Label,
    PageTitle,
    StatusBadge,
)
from ui.design_tokens import (
    ACCENT,
    COLOR_TEXT_TERTIARY,
    DANGER_TEXT,
    FONT_MONO,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    INFO_TEXT,
    SP,
    SUCCESS_TEXT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_TEXT,
)
from ui.widgets.layout_utils import clear_layout
from utils.formatters import fmt_currency, fmt_distance, fmt_percentage

logger = logging.getLogger(__name__)


class QtOverviewView(BaseView):
    """Overview dashboard with KPIs, profit chart, and activity lists."""

    REFRESH_INTERVAL_MS = 30_000
    # Staleness window for the profit chart on ``wakeup``.  When the
    # chart was last rendered within this many seconds, the cached
    # pixmap is reused (no render activity).
    CHART_STALENESS_SECONDS = 300

    _KPI_SOURCES: list[dict[str, str]] = [
        {"key": "fin_revenue",      "category": "analytics.tab_financial", "label": "analytics.kpi_total_revenue"},
        {"key": "fin_profit",        "category": "analytics.tab_financial", "label": "analytics.kpi_total_profit"},
        {"key": "fin_margin",        "category": "analytics.tab_financial", "label": "analytics.kpi_avg_margin"},
        {"key": "fleet_trucks",      "category": "analytics.tab_fleet",     "label": "analytics.kpi_active_trucks"},
        {"key": "fleet_km",          "category": "analytics.tab_fleet",     "label": "analytics.kpi_total_km"},
        {"key": "fleet_consumption", "category": "analytics.tab_fleet",     "label": "analytics.kpi_avg_consumption"},
        {"key": "fleet_maint",       "category": "analytics.tab_fleet",     "label": "analytics.kpi_maint_alerts"},
        {"key": "driver_count",      "category": "analytics.tab_driver",    "label": "analytics.kpi_total_drivers"},
        {"key": "driver_top",        "category": "analytics.tab_driver",    "label": "analytics.kpi_top_driver"},
        {"key": "driver_avg_trips",  "category": "analytics.tab_driver",    "label": "analytics.kpi_avg_trips"},
        {"key": "driver_violations", "category": "analytics.tab_driver",    "label": "analytics.kpi_total_violations"},
        {"key": "client_count",      "category": "analytics.tab_client",    "label": "analytics.kpi_total_clients"},
        {"key": "client_top",        "category": "analytics.tab_client",    "label": "analytics.kpi_top_client"},
        {"key": "client_delay",      "category": "analytics.tab_client",    "label": "analytics.kpi_avg_payment_delay"},
        {"key": "client_conc",       "category": "analytics.tab_client",    "label": "analytics.kpi_revenue_concentration"},
        {"key": "route_top",         "category": "analytics.tab_route",     "label": "analytics.kpi_top_route"},
        {"key": "route_profit_km",   "category": "analytics.tab_route",     "label": "analytics.kpi_avg_profit_km"},
        {"key": "route_count",       "category": "analytics.tab_route",     "label": "analytics.kpi_total_routes"},
        {"key": "route_country",     "category": "analytics.tab_route",     "label": "analytics.kpi_top_country"},
    ]

    _CHART_SOURCES: list[dict[str, str]] = [
        {"key": "rev_by_client",     "category": "analytics.tab_financial", "title": "analytics.client_revenue"},
        {"key": "cost_breakdown",    "category": "analytics.tab_financial", "title": "analytics.cost_breakdown"},
        {"key": "trip_status",       "category": "analytics.tab_financial", "title": "analytics.trip_status_distribution"},
        {"key": "quarterly_rev",     "category": "analytics.tab_financial", "title": "analytics.quarterly_revenue"},
        {"key": "monthly_trip_vol",  "category": "analytics.tab_financial", "title": "analytics.monthly_trip_volume"},
        {"key": "fleet_profitability","category": "analytics.tab_fleet",    "title": "analytics.fleet_profitability"},
        {"key": "fleet_utilization", "category": "analytics.tab_fleet",     "title": "analytics.fleet_utilization"},
        {"key": "idle_vs_active",    "category": "analytics.tab_fleet",     "title": "analytics.idle_vs_active"},
        {"key": "mileage_ranking",   "category": "analytics.tab_fleet",     "title": "analytics.mileage_ranking"},
        {"key": "fleet_fuel_eff",    "category": "analytics.tab_fleet",     "title": "analytics.fleet_fuel_efficiency"},
        {"key": "driver_profit",     "category": "analytics.tab_driver",    "title": "analytics.driver_profit"},
        {"key": "driver_efficiency", "category": "analytics.tab_driver",    "title": "analytics.driver_efficiency"},
        {"key": "driver_trips",      "category": "analytics.tab_driver",    "title": "analytics.driver_trips"},
        {"key": "driver_violations_chart", "category": "analytics.tab_driver", "title": "analytics.driver_tacho"},
        {"key": "client_revenue",    "category": "analytics.tab_client",    "title": "analytics.client_revenue"},
        {"key": "client_growth",     "category": "analytics.tab_client",    "title": "analytics.client_growth"},
        {"key": "client_retention",  "category": "analytics.tab_client",    "title": "analytics.client_retention"},
        {"key": "route_profitability","category": "analytics.tab_route",    "title": "analytics.route_profitability"},
        {"key": "profit_vs_distance","category": "analytics.tab_route",     "title": "analytics.profit_vs_distance"},
        {"key": "country_corridors", "category": "analytics.tab_route",     "title": "analytics.country_corridors"},
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        ops=None,
        trip_service=None,
        fleet_service=None,
        analytics_svc=None,
    ):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        self._trip_repo = trip_service
        self._fleet_repo = fleet_service
        self._analytics_svc = analytics_svc
        self._handlers: dict[str, Any] = {}
        self._last_refresh_ts = 0
        self._shutting_down = False
        self._chart_render_ts = 0
        self._chart_last_size = None
        self._chart_fig = None
        # Key of the chart last rendered into the profit chart slot.
        # ``wakeup`` compares against ``_selected_chart['key']`` to skip
        # a re-render when the user has not changed the chart.
        self._last_rendered_chart_key: str | None = None
        # Wall-clock timestamp of the most recent successful chart
        # render.  Used by ``wakeup`` for staleness detection.
        self._chart_last_render_ts: float = 0.0

        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        self._selected_kpis: list[dict[str, str]] = []
        self._selected_chart: dict[str, str] | None = None
        self._pick_random_content()

        self._build_ui()
        self._subscribe_events()
        self.refresh()

        self._add_timer(self.REFRESH_INTERVAL_MS, self.refresh)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _pick_random_content(self):
        sources = self._KPI_SOURCES
        self._selected_kpis = random.sample(sources, min(3, len(sources)))
        self._selected_chart = random.choice(self._CHART_SOURCES) if self._CHART_SOURCES else None

    def _kpi_label(self, kpi_def: dict[str, str]) -> str:
        cat = t(kpi_def["category"])
        lbl = t(kpi_def["label"])
        return f"{cat.upper()} \u2014 {lbl}"

    def _build_ui(self):
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget(self)
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

        self._kpi_widgets: dict[str, QFrame] = {}
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

        kpi_defs: list[tuple] = []
        for src in self._selected_kpis:
            key = src["key"]
            label = self._kpi_label(src)
            kpi_defs.append((key, label, "\u2014"))

        # Store the value label for each so _refresh_kpis can update text
        self._kpi_value_labels: dict[str, QLabel] = {}
        for key, label, default in kpi_defs:
            card = CompactKPICard(self._kpi_strip, label=label, value=default)
            self._kpi_value_labels[key] = card.value_label
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
        card_widget = Card(self)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        header = QFrame(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        chart_title = t("home.profit_chart_title", default="Analytics Highlight")
        if self._selected_chart:
            cat = t(self._selected_chart["category"])
            title = t(self._selected_chart.get("title", ""))
            chart_title = f"{cat.upper()} \u2014 {title}"

        title = Label(card_widget, chart_title, role="section-title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        month = Label(card_widget, t("home.profit_30_days", default="Past 30 Days"), role="muted")
        header_layout.addWidget(month)
        card_layout.addWidget(header)

        self._chart_container = QFrame(card_widget)
        self._chart_container.setMinimumHeight(200)
        self._chart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QVBoxLayout(self._chart_container)
        card_layout.addWidget(self._chart_container, 1)

        footer = Label(card_widget, t("home.profit_data_source", default="Based on analytics data"), role="muted")
        card_layout.addWidget(footer)

        layout.addWidget(card_widget)

    def _build_active_trips(self, layout):
        card_widget = Card(self)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        header = QFrame(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = Label(card_widget, t("home.active_trips", default="Active Trips"), role="section-title")
        header_layout.addWidget(title)
        self._trips_count = Label(card_widget, "0", role="muted")
        header_layout.addWidget(self._trips_count)
        card_layout.addWidget(header)

        self._trips_list = QVBoxLayout()
        self._trips_list.setSpacing(2)
        card_layout.addLayout(self._trips_list)

        layout.addWidget(card_widget)

    def _build_alert_strip(self, layout):
        card_widget = Card(self)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        title = Label(card_widget, t("home.active_alerts", default="Active Alerts"), role="section-title")
        card_layout.addWidget(title)

        self._alerts_layout = QVBoxLayout()
        self._alerts_layout.setSpacing(2)
        card_layout.addLayout(self._alerts_layout)

        layout.addWidget(card_widget)

    def _build_top_trucks(self, layout):
        card_widget = Card(self)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        title = Label(card_widget, t("home.top_trucks", default="Top Trucks"), role="section-title")
        card_layout.addWidget(title)

        self._top_trucks_layout = QVBoxLayout()
        self._top_trucks_layout.setSpacing(3)
        card_layout.addLayout(self._top_trucks_layout)

        layout.addWidget(card_widget)

    def _build_recent_activity(self, layout):
        card_widget = Card(self)
        card_layout = card_widget.layout()
        card_layout.setSpacing(SP["3"])

        title = Label(card_widget, t("home.recent_activity", default="Recent Activity"), role="section-title")
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
        if not self._analytics_svc:
            return
        for src in self._selected_kpis:
            key = src["key"]
            val_lbl = self._kpi_value_labels.get(key)
            if val_lbl is None:
                continue
            value, color = self._compute_kpi_value(key)
            val_lbl.setText(value)
            if color:
                val_lbl.setStyleSheet(f"color: {color};")

    def _compute_kpi_value(self, key: str) -> tuple:
        """Compute (value_text, value_color) for the given KPI key."""
        from ui.design_tokens import (
            COLOR_ERROR_TEXT,
            COLOR_SUCCESS_TEXT,
            COLOR_TEXT_PRIMARY,
            COLOR_WARNING_TEXT,
        )
        svc = self._analytics_svc
        try:
            if key == "fin_revenue":
                monthly = svc.get_monthly_financial(1) or []
                total = sum(float(r.get("revenue", 0) or 0) for r in monthly)
                return (fmt_currency(total, decimals=0), COLOR_TEXT_PRIMARY)
            elif key == "fin_profit":
                monthly = svc.get_monthly_financial(1) or []
                total = sum(float(r.get("profit", 0) or 0) for r in monthly)
                color = COLOR_SUCCESS_TEXT if total >= 0 else COLOR_ERROR_TEXT
                return (fmt_currency(total, decimals=0), color)
            elif key == "fin_margin":
                monthly = svc.get_monthly_financial(1) or []
                margin = float(monthly[-1].get("margin_pct", 0) or 0) if monthly else 0.0
                color = COLOR_SUCCESS_TEXT if margin >= 0 else COLOR_ERROR_TEXT
                return (fmt_percentage(margin), color)
            elif key == "fleet_trucks":
                fleet = svc.get_fleet() or []
                return (str(len(fleet)), COLOR_TEXT_PRIMARY)
            elif key == "fleet_km":
                fleet = svc.get_fleet() or []
                total_km = sum(r.get("total_km", 0) or 0 for r in fleet)
                return (fmt_distance(total_km), COLOR_TEXT_PRIMARY)
            elif key == "fleet_consumption":
                fleet = svc.get_fleet() or []
                n = len(fleet) or 1
                avg = sum(r.get("avg_consumption", 0) or 0 for r in fleet) / n
                return (f"{avg:.1f} L/100km", COLOR_TEXT_PRIMARY)
            elif key == "fleet_maint":
                maint = svc.get_maintenance_alerts() or []
                color = COLOR_WARNING_TEXT if maint else COLOR_SUCCESS_TEXT
                return (str(len(maint)), color)
            elif key == "driver_count":
                drivers = svc.get_driver() or []
                return (str(len(drivers)), COLOR_TEXT_PRIMARY)
            elif key == "driver_top":
                drivers = svc.get_driver() or []
                top = drivers[0].get("driver", "\u2014") if drivers else "\u2014"
                return (top, COLOR_TEXT_PRIMARY)
            elif key == "driver_avg_trips":
                drivers = svc.get_driver() or []
                n = len(drivers) or 1
                avg = sum(d.get("trip_count", 0) or 0 for d in drivers) / n
                return (f"{avg:.1f}", COLOR_TEXT_PRIMARY)
            elif key == "driver_violations":
                tacho = svc.get_driver_tacho_violations() or []
                total = sum(d.get("total_violations", 0) or 0 for d in tacho)
                color = COLOR_WARNING_TEXT if total > 0 else COLOR_SUCCESS_TEXT
                return (str(total), color)
            elif key == "client_count":
                clients = svc.get_client_analytics() or []
                rev_clients = svc.get_revenue_by_client() or []
                count = len(clients) or len(rev_clients)
                return (str(count), "")
            elif key == "client_top":
                clients = svc.get_client_analytics() or []
                rev_clients = svc.get_revenue_by_client() or []
                all_c = clients or rev_clients
                top = max(all_c, key=lambda r: r.get("revenue", 0) or 0) if all_c else {}
                return (top.get("client", "\u2014"), "")
            elif key == "client_delay":
                clients = svc.get_client_analytics() or []
                delays = [c.get("avg_payment_delay_days", 0) or 0 for c in clients]
                avg = sum(delays) / max(len(delays), 1)
                from ui.design_tokens import DANGER, SUCCESS, WARNING
                color = DANGER if avg > 30 else (WARNING if avg > 15 else SUCCESS)
                return (f"{avg:.1f} d", color)
            elif key == "client_conc":
                conc = svc.get_revenue_concentration() or []
                if conc and len(conc) > 1:
                    total_rev = sum(c.get("revenue", 0) or 0 for c in conc)
                    top_rev = sum(c.get("revenue", 0) or 0 for c in conc[:3])
                    pct = (top_rev / total_rev * 100) if total_rev > 0 else 0
                else:
                    pct = 0
                from ui.design_tokens import DANGER, SUCCESS, WARNING
                color = DANGER if pct > 70 else (WARNING if pct > 50 else SUCCESS)
                return (f"{pct:.0f}%", color)
            elif key == "route_top":
                routes = svc.get_route_profitability() or []
                top = max(routes, key=lambda r: r.get("avg_profit", 0) or 0) if routes else {}
                return (top.get("route_label", "\u2014"), "")
            elif key == "route_profit_km":
                routes = svc.get_route_profitability() or []
                profit = sum(r.get("profit", 0) or 0 for r in routes)
                km = sum(r.get("total_km", 0) or 0 for r in routes)
                avg = profit / max(km, 1)
                from ui.design_tokens import DANGER, SUCCESS
                color = SUCCESS if avg >= 0 else DANGER
                return (f"\u20ac {avg:.2f}/km", color)
            elif key == "route_count":
                routes = svc.get_route_profitability() or []
                total = sum(r.get("trip_count", 0) or 0 for r in routes)
                return (str(total), "")
            elif key == "route_country":
                countries = svc.get_profit_per_km_by_country() or []
                top = max(countries, key=lambda c: c.get("profit_per_km", 0) or 0) if countries else {}
                return (top.get("country", "\u2014"), "")
        except Exception as exc:
            logger.warning("KPI compute failed for key=%s: %s", key, exc)
        return ("\u2014", "")

    def _refresh_active_trips(self):
        self._clear_layout(self._trips_list)

        try:
            trips = self._trip_repo.get_all(limit=200) if self._trip_repo else []
        except Exception:
            trips = []

        non_active = ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced", "LOADING")
        active = [t for t in trips if t.get("status", "") not in non_active]
        self._trips_count.setText(str(len(active)))

        if not active:
            empty = EmptyState(
                None,
                icon_name="mdi6.truck-check-outline",
                title=t("home.no_active_trips", default="No active trips"),
            )
            self._trips_list.addWidget(empty)
            return

        for trip in active[:8]:
            row = self._trip_row(trip)
            self._trips_list.addWidget(row)

    def _trip_row(self, trip: dict[str, Any]) -> QFrame:
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

        status_key = trip.get("status", "Planned")
        status_badge = StatusBadge(row, status_key=status_key)
        layout.addWidget(status_badge)

        return row

    def _refresh_alerts(self):
        self._clear_layout(self._alerts_layout)

        alerts = []
        if self.ops:
            with contextlib.suppress(Exception):
                alerts = self.ops.get_active_alerts(limit=5)

        if not alerts:
            empty = EmptyState(
                None,
                icon_name="mdi6.bell-outline",
                title=t("home.no_alerts", default="No active alerts"),
            )
            self._alerts_layout.addWidget(empty)
            return

        for a in alerts[:3]:
            row = QFrame()
            row.setFixedHeight(48)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(SP["3"], 0, SP["3"], 0)

            sev = getattr(a, "severity", "INFO")
            sev_icon = {
                "CRITICAL": "mdi6.alert-circle",
                "WARNING": "mdi6.alert",
            }.get(sev, "mdi6.information-outline")
            sev_color = {
                "CRITICAL": DANGER_TEXT,
                "WARNING": WARNING_TEXT,
            }.get(sev, INFO_TEXT)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(sev_icon, color=sev_color).pixmap(14, 14))
            layout.addWidget(icon_lbl)

            title = getattr(a, "title", getattr(a, "message", "Alert"))
            if len(title) > 40:
                title = title[:37] + "…"
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_BASE}px; color: {TEXT_PRIMARY};"
            )
            layout.addWidget(title_lbl, 1)

            ts = getattr(a, "created_at", "")
            if ts:
                ts_lbl = QLabel(str(ts)[:16])
                ts_lbl.setStyleSheet(
                    f"font-size: {FONT_SIZE_SM}px; color: {COLOR_TEXT_TERTIARY};"
                )
                layout.addWidget(ts_lbl)

            self._alerts_layout.addWidget(row)

        if len(alerts) > 3:
            more = QLabel(f'+ {len(alerts) - 3} {t("home.more", default="more")}')
            more.setStyleSheet(f"color: {ACCENT}; font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_MEDIUM};")
            more.setCursor(Qt.PointingHandCursor)
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
            empty = EmptyState(
                None,
                icon_name="mdi6.trophy-outline",
                title=t("common.no_data", default="No data"),
            )
            self._top_trucks_layout.addWidget(empty)
            return

        for i, row in enumerate(top, 1):
            plate = row.get("truck_number", "—")
            revenue = float(row.get("revenue", 0))

            r = QFrame()
            layout = QHBoxLayout(r)
            layout.setContentsMargins(0, 0, 0, 0)

            idx = QLabel(f"#{i}")
            idx.setFixedWidth(24)
            rank_colors = {
                1: "#F59E0B",  # gold
                2: "#9CA3AF",  # silver
                3: "#B45309",  # bronze
            }
            idx.setStyleSheet(
                f"color: {rank_colors.get(i, COLOR_TEXT_TERTIARY)}; "
                f"font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
            )
            layout.addWidget(idx)

            plate_lbl = QLabel(plate)
            plate_lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_BASE}px; color: {TEXT_PRIMARY};"
            )
            layout.addWidget(plate_lbl, 1)

            rev_lbl = QLabel(fmt_currency(revenue, decimals=0))
            rev_lbl.setStyleSheet(
                f"font-family: '{FONT_MONO}'; font-size: {FONT_SIZE_BASE}px; color: {SUCCESS_TEXT};"
            )
            rev_lbl.setAlignment(Qt.AlignRight)
            layout.addWidget(rev_lbl)

            self._top_trucks_layout.addWidget(r)

    def _refresh_recent_activity(self):
        self._clear_layout(self._activity_layout)

        try:
            recent = self._trip_repo.get_all(limit=6) if self._trip_repo else []
        except Exception:
            recent = []

        if not recent:
            empty = EmptyState(
                None,
                icon_name="mdi6.clipboard-text-outline",
                title=t("common.no_data", default="No data"),
            )
            self._activity_layout.addWidget(empty)
            return

        for trip in recent:
            profit = float(trip.get("net_profit", 0) or 0)
            plate = trip.get("truck_number", "—")
            client = trip.get("client_name", "—")
            date_raw = trip.get("start_date", "") or str(trip.get("created_at", ""))[:10]
            from utils.formatters import fmt_date
            date = fmt_date(date_raw)

            r = QFrame()
            layout = QHBoxLayout(r)
            layout.setContentsMargins(0, 0, 0, 0)

            date_lbl = QLabel(date)
            date_lbl.setStyleSheet(f"font-size: {FONT_SIZE_SM}px; color: {COLOR_TEXT_TERTIARY};")
            date_lbl.setFixedWidth(80)
            layout.addWidget(date_lbl)

            plate_lbl = QLabel(plate)
            plate_lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_BASE}px; color: {TEXT_SECONDARY}; font-weight: {FONT_WEIGHT_MEDIUM};"
            )
            plate_lbl.setFixedWidth(70)
            layout.addWidget(plate_lbl)

            client_lbl = QLabel(client[:22])
            client_lbl.setStyleSheet(f"font-size: {FONT_SIZE_BASE}px; color: {TEXT_PRIMARY};")
            layout.addWidget(client_lbl, 1)

            color = SUCCESS_TEXT if profit > 0 else DANGER_TEXT
            profit_lbl = QLabel(fmt_currency(profit, decimals=0))
            profit_lbl.setStyleSheet(
                f"font-family: '{FONT_MONO}'; font-size: {FONT_SIZE_BASE}px; color: {color};"
            )
            profit_lbl.setAlignment(Qt.AlignRight)
            layout.addWidget(profit_lbl)

            self._activity_layout.addWidget(r)

    def _clear_layout(self, layout):
        clear_layout(layout)

    # ── Chart rendering ────────────────────────────────────────────────────────

    def _render_profit_chart(self, _force: bool = False):
        now = time.time()
        if not _force and self._chart_render_ts and now - self._chart_render_ts < 0.8:
            return

        try:
            self._do_render_chart()
            self._chart_render_ts = now
        except Exception as exc:
            logger.warning("Chart render failed: %s", exc)
            self._clear_layout(self._chart_container.layout())
            msg = t("home.profit_no_data", default="Chart unavailable.\nComplete trips to see analytics.")
            lbl = QLabel(msg)
            lbl.setProperty("role", "muted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
            lbl.setAlignment(Qt.AlignCenter)
            self._chart_container.layout().addWidget(lbl)

    def _do_render_chart(self):
        from ui.plotly_renderer import PlotlyChartWidget

        if not self._selected_chart or not self._analytics_svc:
            self._show_chart_no_data()
            self._last_rendered_chart_key = None
            return

        key = self._selected_chart["key"]
        # If the same chart key was already rendered, keep the existing
        # widget and pixmap.  ``wakeup`` calls this method with
        # ``_force=True`` only when the key changed or the chart is
        # stale.
        if (
            key == self._last_rendered_chart_key
            and self._chart_container.layout() is not None
            and self._chart_container.layout().count() > 0
        ):
            return

        # Tear down the previous widget only when we are about to
        # replace it with a different chart.
        self._clear_layout(self._chart_container.layout())
        self._chart_fig = None

        try:
            fig = self._build_analytics_chart(key)
        except Exception as exc:
            logger.warning("Analytics chart build failed: %s", exc)
            self._show_chart_no_data()
            return

        if fig is None:
            self._show_chart_no_data()
            return

        chart_widget = PlotlyChartWidget(min_height=180)
        chart_widget.set_figure(fig)
        self._chart_container.layout().addWidget(chart_widget)
        self._last_rendered_chart_key = key
        self._chart_last_render_ts = time.time()

    def _show_chart_no_data(self):
        msg = t("home.profit_no_data", default="No analytics data available.\nComplete trips to see analytics.")
        lbl = QLabel(msg)
        lbl.setProperty("fontRole", "muted")
        lbl.setAlignment(Qt.AlignCenter)
        self._chart_container.layout().addWidget(lbl)

    def _build_analytics_chart(self, key: str):
        from ui.plotly_charts import (
            CHART_ACCENT,
            CHART_DANGER,
            CHART_INFO,
            CHART_SECONDARY,
            CHART_SUCCESS,
            CHART_WARNING,
            _value_colors,
            make_area_chart,
            make_grouped_bar_chart,
            make_lollipop_chart,
            make_pie_chart,
            make_scatter_chart,
            make_stacked_area_chart,
            make_trend_chart,
        )

        svc = self._analytics_svc

        if key == "rev_by_client":
            data = svc.get_revenue_by_client() or []
            if not data:
                return None
            top = sorted(data, key=lambda r: r.get("revenue", 0) or 0, reverse=True)[:8]
            return make_lollipop_chart(
                [r.get("client", "?") for r in top],
                [r.get("revenue", 0) or 0 for r in top],
                title=t("analytics.client_revenue"), color=CHART_ACCENT,
                is_currency=True, show_title=False)

        elif key == "cost_breakdown":
            data = svc.get_cost_breakdown(12) or []
            if not data:
                return None
            months = [r.get("month", "") for r in data]
            return make_stacked_area_chart(months, [
                (t("analytics.fuel"), [r.get("fuel_cost", 0) or 0 for r in data], CHART_WARNING),
                (t("analytics.toll"), [r.get("toll_cost", 0) or 0 for r in data], CHART_ACCENT),
                (t("analytics.salary"), [r.get("salary_cost", 0) or 0 for r in data], CHART_INFO),
                (t("analytics.extra_costs"), [r.get("extra_costs", 0) or 0 for r in data], CHART_SECONDARY),
            ], is_currency=True, empty_message=t("common.no_data"), show_title=False)

        elif key == "trip_status":
            data = svc.get_trip_status_distribution() or []
            if not data:
                return None
            return make_pie_chart(
                [s.get("count", 0) or 0 for s in data],
                [t(f"status.{s.get('status', 'unknown')}") for s in data],
                title=t("analytics.trip_status_distribution"), show_title=False)

        elif key == "quarterly_rev":
            data = svc.get_revenue_quarterly(4) or []
            if not data or len(data) < 2:
                return None
            quarters = [r.get("quarter", "") for r in data]
            return make_grouped_bar_chart(quarters, [
                (t("analytics.revenue_label"), [r.get("revenue", 0) or 0 for r in data], CHART_ACCENT),
                (t("analytics.profit_label"), [r.get("profit", 0) or 0 for r in data], CHART_SUCCESS),
            ], horizontal=False, is_currency=True, show_title=False)

        elif key == "monthly_trip_vol":
            data = svc.get_monthly_trip_volume(12) or []
            if not data or len(data) < 3:
                return None
            months = [r.get("month", "") for r in data]
            return make_area_chart(months,
                [r.get("trip_count", 0) or 0 for r in data],
                title=t("analytics.monthly_trip_volume"), color=CHART_SUCCESS,
                show_title=False)

        elif key == "fleet_profitability":
            data = svc.get_fleet() or []
            if not data:
                return None
            top = sorted(data, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:8]
            profits = [r.get("profit", 0) or 0 for r in top]
            return make_lollipop_chart(
                [r.get("truck", "?") for r in top], profits,
                title=t("analytics.fleet_profitability"),
                color=_value_colors(profits), is_currency=True, show_title=False)

        elif key == "fleet_utilization":
            data = svc.get_truck_utilization() or []
            if not data:
                return None
            top = sorted(data, key=lambda r: r.get("trip_count", 0) or 0, reverse=True)[:8]
            return make_lollipop_chart(
                [r.get("truck", "?") for r in top],
                [r.get("trip_count", 0) or 0 for r in top],
                title=t("analytics.fleet_utilization"), color=CHART_SUCCESS,
                show_title=False)

        elif key == "idle_vs_active":
            fleet = svc.get_fleet() or []
            if not fleet or len(fleet) < 3:
                return None
            active = sum(1 for r in fleet if (r.get("trip_count", 0) or 0) > 0)
            idle = len(fleet) - active
            if active + idle == 0:
                return None
            return make_pie_chart([active, idle],
                [t("analytics.active"), t("analytics.idle")],
                title=t("analytics.idle_vs_active"),
                colors=[CHART_SUCCESS, CHART_WARNING], show_title=False)

        elif key == "mileage_ranking":
            data = svc.get_fleet() or []
            if not data:
                return None
            top = sorted(data, key=lambda r: r.get("total_km", 0) or 0, reverse=True)[:8]
            return make_lollipop_chart(
                [r.get("truck", "?") for r in top],
                [r.get("total_km", 0) or 0 for r in top],
                title=t("analytics.mileage_ranking"), color=CHART_SECONDARY,
                show_title=False)

        elif key == "fleet_fuel_eff":
            data = svc.get_fleet() or []
            if not data:
                return None
            top = sorted(data, key=lambda r: r.get("avg_consumption", 0) or 0)[:8]
            return make_lollipop_chart(
                [r.get("truck", "?") for r in top],
                [r.get("avg_consumption", 0) or 0 for r in top],
                title=t("analytics.fleet_fuel_efficiency"), color=CHART_SECONDARY,
                show_title=False)

        elif key == "driver_profit":
            data = svc.get_driver() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:8]
            profits = [d.get("profit", 0) or 0 for d in top]
            return make_lollipop_chart(
                [d.get("driver", "?") for d in top], profits,
                title=t("analytics.driver_profit"),
                color=_value_colors(profits), is_currency=True, show_title=False)

        elif key == "driver_efficiency":
            data = svc.get_driver_profit_per_km() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda r: r.get("profit_per_km", 0) or 0, reverse=True)[:8]
            vals = [d.get("profit_per_km", 0) or 0 for d in top]
            return make_lollipop_chart(
                [d.get("driver_name", "?") for d in top], vals,
                title=t("analytics.driver_efficiency"),
                color=_value_colors(vals), is_currency=True, show_title=False)

        elif key == "driver_trips":
            data = svc.get_driver() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda r: r.get("trip_count", 0) or 0, reverse=True)[:8]
            return make_lollipop_chart(
                [d.get("driver", "?") for d in top],
                [d.get("trip_count", 0) or 0 for d in top],
                title=t("analytics.driver_trips"), color=CHART_ACCENT,
                show_title=False)

        elif key == "driver_violations_chart":
            data = svc.get_driver_tacho_violations() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda r: r.get("total_violations", 0) or 0, reverse=True)[:8]
            return make_lollipop_chart(
                [d.get("driver", "?") for d in top],
                [d.get("total_violations", 0) or 0 for d in top],
                title=t("analytics.driver_tacho"), color=CHART_DANGER,
                show_title=False)

        elif key == "client_revenue":
            data = svc.get_revenue_by_client() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda r: r.get("revenue", 0) or 0, reverse=True)[:8]
            return make_lollipop_chart(
                [r.get("client", "?") for r in top],
                [r.get("revenue", 0) or 0 for r in top],
                title=t("analytics.client_revenue"), color=CHART_ACCENT,
                is_currency=True, show_title=False)

        elif key == "client_growth":
            data = svc.get_client_growth(12) or []
            if not data or len(data) < 3:
                return None
            return make_trend_chart(
                [g.get("month", "") for g in data],
                [g.get("new_clients", 0) or 0 for g in data],
                title=t("analytics.client_growth"), color=CHART_ACCENT,
                show_title=False)

        elif key == "client_retention":
            data = svc.get_client_retention() or []
            if not data or not isinstance(data, list) or len(data) < 1:
                return None
            active_ct = float(data[0].get("active_count", 0) or 0)
            inactive_ct = float(data[0].get("inactive_count", 0) or 0)
            if active_ct + inactive_ct == 0:
                return None
            return make_pie_chart([active_ct, inactive_ct],
                [t("analytics.active"), t("analytics.inactive")],
                title=t("analytics.client_retention"),
                colors=[CHART_SUCCESS, CHART_DANGER], show_title=False)

        elif key == "route_profitability":
            data = svc.get_route_profitability() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda r: r.get("avg_profit", 0) or 0, reverse=True)[:8]
            profits = [r.get("avg_profit", 0) or 0 for r in top]
            return make_lollipop_chart(
                [r.get("route_label", "?") for r in top], profits,
                title=t("analytics.route_profitability"),
                color=_value_colors(profits), is_currency=True, show_title=False)

        elif key == "profit_vs_distance":
            data = svc.get_profit_vs_distance(200) or []
            if not data:
                return None
            return make_scatter_chart(
                [d.get("distance_km", 0) or 0 for d in data],
                [d.get("net_profit", 0) or 0 for d in data],
                [d.get("truck_number", "") or "" for d in data],
                title=t("analytics.profit_vs_distance"),
                x_label=t("analytics.distance_label"),
                y_label=t("analytics.net_profit_label"),
                color=CHART_ACCENT, is_currency=True, show_title=False)

        elif key == "country_corridors":
            data = svc.get_profit_per_km_by_country() or []
            if not data or len(data) < 2:
                return None
            top = sorted(data, key=lambda c: c.get("profit_per_km", 0) or 0, reverse=True)[:8]
            vals = [c.get("profit_per_km", 0) or 0 for c in top]
            return make_lollipop_chart(
                [c.get("country", "?") for c in top], vals,
                title=t("analytics.country_corridors"),
                color=_value_colors(vals), is_currency=True, show_title=False)

        return None

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
                self._subscribe(ev_type, handler)
                self._handlers[ev_type] = handler

    def _on_data_changed(self, ev):
        QTimer.singleShot(0, self.refresh)

    def _on_language_changed(self, lang: str):
        QTimer.singleShot(0, self.refresh)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self):
        """Re-display the overview.

        The previously-rendered chart widget and its ``QPixmap`` are
        kept alive (see ``shutdown``), so the common case — re-entering
the overview after visiting another module — does not trigger
a re-render.  Only the cheap KPI / active-trips /
alerts lists are refreshed.
        """
        self._subscribe_events()
        self._register_i18n(self._language_callback)
        self._last_refresh_ts = 0
        self.refresh()
        if self._should_rerender_chart():
            self._render_profit_chart(_force=True)

    def _should_rerender_chart(self) -> bool:
        """Return True if the profit chart must be re-rendered on wakeup."""
        if self._chart_fig is None:
            return True
        if not self._selected_chart:
            return False
        key = self._selected_chart.get("key")
        if key != self._last_rendered_chart_key:
            return True
        if self._chart_last_render_ts == 0.0:
            return True
        return (time.time() - self._chart_last_render_ts) > self.CHART_STALENESS_SECONDS

    def shutdown(self):
        self._shutting_down = True
        super().shutdown()
