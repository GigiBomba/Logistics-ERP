"""Route Analytics tab — Top Routes Table, Profit/km, Country Treemap, Route Frequency."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.i18n import t
from ui.design_tokens import (
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_WARNING_DEFAULT,
    FONT_FAMILY,
    SP,
    TEXT_PRIMARY,
)
from ui.plotly_charts import (
    CHART_ACCENT,
    _value_colors,
    make_bar_chart,
    make_treemap_chart,
)
from ui.plotly_renderer import PlotlyChartWidget
from ui.views.analytics._tab_base import BaseTab
from ui.widgets import StyledTableWidget


def _profit_km_color(ppm: float) -> str:
    if ppm > 1.0:
        return COLOR_SUCCESS_DEFAULT
    if ppm >= 0.5:
        return COLOR_WARNING_DEFAULT
    return COLOR_ERROR_DEFAULT


class RouteAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    @staticmethod
    def _fmt_route_label(raw: str) -> str:
        if not raw:
            return "?"
        if len(raw) <= 25:
            return raw
        return raw[:25] + "\u2026"

    def _build(self):
        self._add_header("analytics.tab_route", "analytics.route_subtitle")
        self._chart_widget = QWidget()
        self._chart_layout = QVBoxLayout(self._chart_widget)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        self._chart_layout.setSpacing(8)
        self._content_layout.addWidget(self._chart_widget)

    def _do_refresh(self):
        self._build()
        self._render()

    def _render(self):
        if self._svc is None:
            self._add_no_data()
            return
        from_date, to_date = self._date_range()
        routes = self._svc.get_route_profitability(from_date, to_date) or []
        countries = self._svc.get_profit_per_km_by_country()
        if not routes:
            self._add_no_data(t("common.no_data"))
            return

        # ── KPI strip ────────────────────────────────────────────
        unique_routes = len(routes)
        most_frequent = max(routes, key=lambda r: r.get("trip_count", 0) or 0)
        most_freq_label = self._fmt_route_label(most_frequent.get("route_label", "?"))
        avg_profit = sum(r.get("avg_profit", 0) or 0 for r in routes) / max(unique_routes, 1)
        top_country = (
            max(countries, key=lambda c: c.get("profit", 0) or 0)
            if countries else {}
        )

        kpi_row = QWidget()
        kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0)
        kpi_l.setSpacing(SP["4"])
        kpi_l.addWidget(self._make_route_kpi(
            t("analytics.kpi_unique_routes", default="Unique Routes"),
            str(unique_routes),
        ))
        kpi_l.addWidget(self._make_route_kpi(
            t("analytics.kpi_most_frequent", default="Most Frequent"),
            most_freq_label,
        ))
        kpi_l.addWidget(self._make_route_kpi(
            t("analytics.kpi_avg_route_profit", default="Avg Profit/Route"),
            f"\u20ac {avg_profit:,.0f}",
            value_color=COLOR_SUCCESS_DEFAULT if avg_profit >= 0 else None,
        ))
        if top_country:
            kpi_l.addWidget(self._make_route_kpi(
                t("analytics.kpi_top_country_route", default="Top Country"),
                top_country.get("country", "?"),
            ))
        self._chart_layout.addWidget(kpi_row)

        # ── Top Routes Table (replaces bar chart) ────────────────
        self._add_section_header(
            t("analytics.section_route_performance", default="Route Performance"), ""
        )
        top = sorted(routes, key=lambda r: r.get("avg_profit", 0) or 0, reverse=True)[:12]

        def _fmt_cur(v):
            return f"\u20ac {float(v):,.0f}"

        def _fmt_rate(v):
            return f"\u20ac {float(v):.2f}/km"

        def _fmt_dist(v):
            return f"{float(v):,.0f} km"

        table_data = []
        for r in top:
            ppm = r.get("profit_per_km", 0) or 0
            table_data.append({
                "route": self._fmt_route_label(r.get("route_label", "?")),
                "trips": int(r.get("trip_count", 0) or 0),
                "km": f"{(r.get('avg_km', 0) or 0):,.0f} km",
                "revenue": r.get("avg_profit", 0) or 0,
                "profit": r.get("avg_profit", 0) or 0,
                "profit_km": ppm,
                "_ppm_raw": ppm,
            })

        route_table = StyledTableWidget(
            self._chart_widget,
            columns=[
                ("route", t("analytics.col_route", default="Route"), 170),
                ("trips", t("analytics.col_trips", default="Trips"), 55),
                ("km", t("analytics.col_km", default="KM Total"), 80),
                ("profit", t("analytics.profit_label"), 90),
                ("profit_km", t("analytics.col_profit_km", default="Profit/KM"), 85),
            ],
            formatters={
                "profit": _fmt_cur,
                "profit_km": _fmt_rate,
            },
        )
        route_table.set_data(table_data)
        route_table.setMinimumHeight(min(38 * len(table_data) + 38, 360))
        self._chart_layout.addWidget(route_table)

        # Color Profit/KM cells
        from PySide6.QtGui import QColor
        for r, row in enumerate(table_data):
            ppm = row.get("_ppm_raw", 0)
            color = _profit_km_color(ppm)
            profit_km_col = 4
            existing = route_table.item(r, profit_km_col)
            if existing:
                existing.setForeground(QColor(color))

        # ── Profit per KM chart ──────────────────────────────────
        route_labels = [self._fmt_route_label(r.get("route_label", "?")) for r in top]
        route_profit_km = [r.get("profit_per_km", 0) or 0 for r in top]
        bar_w = 0.4 if len(route_labels) <= 2 else 0.0
        fig2 = make_bar_chart(route_labels, route_profit_km,
                       title=t("analytics.route_profit_per_km"), horizontal=True,
                       color=_value_colors(route_profit_km), highlight_max=True,
                       is_currency=True, max_bar_width=bar_w)
        pw2 = PlotlyChartWidget(min_height=180)
        pw2.set_figure(fig2)
        self._chart_layout.addWidget(pw2)

        # ── Country Treemap ──────────────────────────────────────
        if countries and len(countries) >= 2:
            country_labels = [c.get("country", "?") or "?" for c in countries[:10]]
            country_revs = [c.get("profit", 0) or 0 for c in countries[:10]]
            country_margins = []
            for c in countries[:10]:
                ppm = c.get("profit_per_km", 0) or 0
                country_margins.append(
                    COLOR_SUCCESS_DEFAULT if ppm > 0.5 else (
                        COLOR_WARNING_DEFAULT if ppm >= 0 else COLOR_ERROR_DEFAULT
                    )
                )
            fig_tm = make_treemap_chart(
                country_labels, country_revs, colors=country_margins,
                title=t("analytics.route_country_treemap", default="Revenue by Country"),
                root_label=t("analytics.all_countries", default="All Countries"),
            )
            pw_tm = PlotlyChartWidget(min_height=200)
            pw_tm.set_figure(fig_tm)
            self._chart_layout.addWidget(pw_tm)

        # ── Route Frequency Chart ─────────────────────────────────
        freq_routes = sorted(routes, key=lambda r: r.get("trip_count", 0) or 0, reverse=True)[:12]
        if freq_routes and len(freq_routes) >= 2:
            freq_labels = [self._fmt_route_label(r.get("route_label", "?")) for r in freq_routes]
            freq_counts = [r.get("trip_count", 0) or 0 for r in freq_routes]
            fig_freq = make_bar_chart(
                freq_labels, freq_counts,
                title=t("analytics.route_frequency", default="Route Frequency"),
                horizontal=True,
                color=CHART_ACCENT, highlight_max=True,
            )
            pw_freq = PlotlyChartWidget(min_height=180)
            pw_freq.set_figure(fig_freq)
            self._chart_layout.addWidget(pw_freq)

        # ── Empty state for single-route edge case ───────────────
        if len(top) <= 1:
            from ui.components import EmptyState
            es = EmptyState(
                None,
                icon_name="mdi6.chart-bar",
                title=t("analytics.insufficient_route_data",
                       default="Insufficient data for chart — add more trips"),
            )
            self._chart_layout.addWidget(es)

    @staticmethod
    def _make_route_kpi(
        label: str, value: str, value_color: str | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("kpi-spark-card")
        card.setStyleSheet(
            f"QFrame#kpi-spark-card {{"
            f" background: {COLOR_BG_OVERLAY};"
            f" border: 1px solid {COLOR_BG_ELEVATED};"
            f" border-radius: 8px;"
            f" }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SP["2"], SP["2"], SP["2"], SP["2"])
        card_layout.setSpacing(SP["1"])

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 11px; font-weight: 600;"
            f" letter-spacing: 0.05em; background: transparent;"
        )
        card_layout.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(
            f"color: {value_color or COLOR_TEXT_PRIMARY}; font-size: 20px;"
            f" font-weight: 700; font-family: '{FONT_FAMILY}';"
            f" background: transparent; padding-top: 2px;"
        )
        card_layout.addWidget(val)
        return card
