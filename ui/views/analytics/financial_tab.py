"""Financial Analytics tab — Revenue, Profit, Margin, Top Clients, Top Countries.

Optimal chart choices per metric:
- Time series: trend_chart (line + area fill)
- Top-N ranking: lollipop_chart (cleaner than horizontal bars)
- Part-to-whole: pie_chart (donut with center value)
- Composition over time: stacked_area_chart
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ERROR_DEFAULT,
    COLOR_INFO_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_WARNING_DEFAULT,
    DANGER,
    FONT_FAMILY,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
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
    make_line_chart,
    make_lollipop_chart,
    make_pie_chart,
    make_scatter_chart,
    make_stacked_area_chart,
    make_stacked_bar_chart,
)
from ui.views.analytics._tab_base import BaseTab


class FinancialAnalyticsTab(BaseTab):
    """Am I making money? — Revenue, profit, margin trends, top clients, top countries."""

    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_financial", "analytics.financial_subtitle")

    def _do_refresh(self):
        self._build()
        self._render()

    def _render(self):
        if self._svc is None:
            self._add_no_data()
            return

        months = self._months()
        quarters = self._quarters()
        from_date, to_date = self._date_range()
        monthly = self._svc.get_monthly_financial(months, from_date, to_date) or []
        if not monthly:
            self._add_no_data(t("analytics.no_financial_data"))
            return

        spark_monthly = self._svc.get_monthly_financial(12, from_date, to_date) or []
        spark_rev_vals = self._sparkline_values(spark_monthly, "revenue", 0)
        spark_profit_vals = self._sparkline_values(spark_monthly, "profit", 0)

        # Sanitize margin_pct
        try:
            first_margin = float(monthly[-1].get("margin_pct", 0) or 0)
        except (TypeError, ValueError):
            first_margin = 0.0

        # ── KPI strip (4 cards: Revenue, Profit, Margin, DSO) ────
        total_rev = sum(float(r.get("revenue", 0) or 0) for r in monthly)
        total_profit = sum(float(r.get("profit", 0) or 0) for r in monthly)
        last_margin = first_margin

        revenue_series = [float(r.get("revenue", 0) or 0) for r in monthly]
        profit_series = [float(r.get("profit", 0) or 0) for r in monthly]
        margin_series = [float(r.get("margin_pct", 0) or 0) for r in monthly]

        def _delta_color(v):
            return SUCCESS if v > 0 else (DANGER if v < 0 else TEXT_MUTED)

        def _fmt_delta(v, as_pct=False):
            if v == 0:
                return ""
            sign = "+" if v > 0 else ""
            if as_pct:
                return f"{sign}{v:.1f} pts"
            return f"{sign}{v:,.0f} \u20ac"

        rev_delta = revenue_series[-1] - revenue_series[0] if revenue_series else 0
        profit_delta = profit_series[-1] - profit_series[0] if profit_series else 0
        margin_delta = margin_series[-1] - margin_series[0] if margin_series else 0

        # DSO estimation: (invoiced - paid) / revenue * period_days
        last_month = monthly[-1]
        invoiced = last_month.get("invoiced_count", 0) or 0
        paid = last_month.get("paid_count", 0) or 0
        unpaid = max(invoiced - paid, 0)
        dso_days = round(
            (unpaid / max(total_rev, 1)) * max(self._days(), 30)
        ) if total_rev > 0 else 0

        # Margin progress bar: fill = current margin / 30% target
        margin_pct_clamped = min(max(last_margin, 0), 30)

        self._add_kpi_row_with_sparklines([
            {"label": t("analytics.kpi_total_revenue"),
             "value": f"{total_rev:,.0f} \u20ac",
             "subtitle": _fmt_delta(rev_delta),
             "subtitle_color": _delta_color(rev_delta),
             "sparkline_values": spark_rev_vals,
             "sparkline_color": CHART_ACCENT},
            {"label": t("analytics.kpi_total_profit"),
             "value": f"{total_profit:,.0f} \u20ac",
             "value_color": SUCCESS if total_profit >= 0 else DANGER,
             "subtitle": _fmt_delta(profit_delta),
             "subtitle_color": _delta_color(profit_delta),
             "sparkline_values": spark_profit_vals,
             "sparkline_color": CHART_SUCCESS if total_profit >= 0 else CHART_DANGER},
            {"label": t("analytics.kpi_avg_margin"),
             "value": f"{last_margin:.1f}%",
             "subtitle": _fmt_delta(margin_delta, as_pct=True),
             "subtitle_color": _delta_color(margin_delta),
             "sparkline_values": margin_series,
             "sparkline_color": CHART_SECONDARY},
            {"label": t("analytics.kpi_dso", default="DSO (Days)"),
             "value": f"{dso_days} days",
             "value_color": COLOR_WARNING_DEFAULT if dso_days > 45 else (
                 COLOR_SUCCESS_DEFAULT if dso_days <= 30 else COLOR_INFO_DEFAULT
             ),
             "subtitle": t("analytics.kpi_dso_subtitle", default="Avg collection period"),
             "sparkline_values": [],
             "sparkline_color": CHART_INFO},
         ])

        # ── Visual margin progress bar (below KPI row) ──────────
        if last_margin > 0:
            from PySide6.QtWidgets import QProgressBar
            margin_bar = QProgressBar()
            margin_bar.setMaximum(30)
            margin_bar.setValue(int(margin_pct_clamped))
            margin_bar.setFixedHeight(6)
            margin_bar.setMaximumWidth(400)
            margin_bar.setTextVisible(False)
            margin_bar.setStyleSheet(
                f"QProgressBar {{"
                f" background: {TEXT_MUTED}22;"
                f" border: none;"
                f" border-radius: 3px;"
                f" }}"
                f"QProgressBar::chunk {{"
                f" background: {COLOR_ACCENT_PRIMARY};"
                f" border-radius: 3px;"
                f" }}"
            )
            self._content_layout.addWidget(margin_bar)

        month_labels = [self._fmt_month_label(r.get("month", "")) for r in monthly]

        # ── Revenue Trend Line Chart (full width) ─────────────────
        if monthly and len(monthly) >= 2:
            self._add_section_header(
                t("analytics.section_revenue_trend", default="Revenue & Profit Trend"), ""
            )
            fig_trend = make_line_chart(
                month_labels,
                [
                    (revenue_series, t("analytics.revenue_label"), CHART_ACCENT),
                    (profit_series, t("analytics.profit_label"), CHART_SUCCESS),
                ],
                title=t("analytics.revenue_profit_trend", default="Revenue vs Profit Trend"),
                show_title=False,
            )
            self._add_plotly_chart(fig_trend)

        # ── Invoice Aging Breakdown ───────────────────────────────
        self._add_section_header(
            t("analytics.section_invoice_aging", default="Invoice Aging"), ""
        )
        aging = self._svc.get_invoice_aging()
        if aging:
            current_val = aging.get("current_bucket", 0) or 0
            b31_60 = aging.get("bucket_31_60", 0) or 0
            b61_90 = aging.get("bucket_61_90", 0) or 0
            overdue_val = aging.get("overdue_bucket", 0) or 0
            total_out = aging.get("total_outstanding", 0) or 0
            if total_out > 0:
                aging_labels = [
                    t("analytics.aging_current", default="Current (0-30d)"),
                    t("analytics.aging_31_60", default="31-60 days"),
                    t("analytics.aging_61_90", default="61-90 days"),
                    t("analytics.aging_overdue", default="90+ days"),
                ]
                aging_colors = [
                    COLOR_SUCCESS_DEFAULT,
                    COLOR_WARNING_DEFAULT,
                    "#F97316",
                    COLOR_ERROR_DEFAULT,
                ]
                fig_aging = make_stacked_bar_chart(
                    [t("analytics.outstanding", default="Outstanding")],
                    [(lbl, [v], clr) for lbl, v, clr in zip(
                        aging_labels,
                        [current_val, b31_60, b61_90, overdue_val],
                        aging_colors,
                    )],
                    title=t("analytics.invoice_aging", default="Outstanding Invoices by Age"),
                    horizontal=True, is_currency=True,
                    show_title=False,
                )
                self._add_plotly_chart(
                    fig_aging,
                    t("analytics.invoice_aging", default="Outstanding Invoices by Age"),
                )
        else:
            # Fallback: invoiced vs paid card
            last_month = monthly[-1]
            inv_count = last_month.get("invoiced_count", 0) or 0
            paid_count = last_month.get("paid_count", 0) or 0
            if inv_count > 0 or paid_count > 0:
                card = QFrame()
                card.setStyleSheet(
                    f"background: {COLOR_ACCENT_PRIMARY}0D; border: 1px solid {COLOR_ACCENT_PRIMARY}33;"
                    f" border-radius: 6px; padding: 8px;"
                )
                card_l = QHBoxLayout(card)
                card_l.setContentsMargins(12, 8, 12, 8)
                card_l.setSpacing(16)
                inv_lbl = QLabel(
                    f"<span style='color:{COLOR_INFO_DEFAULT}; font-size:11px;'>{t('analytics.invoiced', default='Invoiced')}</span>"
                    f"<br><span style='color:{TEXT_PRIMARY}; font-size:18px; font-weight:600;'>{inv_count:.0f}</span>"
                )
                inv_lbl.setTextFormat(Qt.RichText)
                card_l.addWidget(inv_lbl)
                paid_lbl = QLabel(
                    f"<span style='color:{COLOR_SUCCESS_DEFAULT}; font-size:11px;'>{t('analytics.paid', default='Paid')}</span>"
                    f"<br><span style='color:{TEXT_PRIMARY}; font-size:18px; font-weight:600;'>{paid_count:.0f}</span>"
                )
                paid_lbl.setTextFormat(Qt.RichText)
                card_l.addWidget(paid_lbl)
                unpaid = int(max(inv_count - paid_count, 0))
                if unpaid > 0:
                    unpaid_lbl = QLabel(
                        f"<span style='color:{COLOR_WARNING_DEFAULT}; font-size:11px;'>{t('analytics.unpaid', default='Unpaid')}</span>"
                        f"<br><span style='color:{COLOR_WARNING_DEFAULT}; font-size:18px; font-weight:600;'>{unpaid}</span>"
                    )
                    unpaid_lbl.setTextFormat(Qt.RichText)
                    card_l.addWidget(unpaid_lbl)
                card_l.addStretch()
                self._content_layout.addWidget(card)

        # ── Section: Client & Geographic ─────────────────────────
        self._add_section_header(t("analytics.section_client_geographic"), "")

        client_figs: list = []
        client_titles: list[str] = []
        top_clients = self._svc.get_revenue_by_client(from_date, to_date) or []

        client_labels: list[str] = []
        if top_clients:
            client_labels = [c.get("client", "?") or "?" for c in top_clients[:8]]
            client_revenues = [c.get("revenue", 0) or 0 for c in top_clients[:8]]
            fig = make_lollipop_chart(
                client_labels, client_revenues,
                title=t("analytics.client_revenue"),
                color=_value_colors(client_revenues),
                is_currency=True,
                show_title=False,
            )
            client_figs.append(fig)
            client_titles.append(t("analytics.client_revenue"))

        # Profit by Client
        if top_clients and client_labels:
            client_profits = [c.get("profit", 0) or 0 for c in top_clients[:8]]
            fig = make_lollipop_chart(
                client_labels, client_profits,
                title=t("analytics.client_profit"),
                color=_value_colors(client_profits),
                is_currency=True,
                show_title=False,
            )
            client_figs.append(fig)
            client_titles.append(t("analytics.client_profit"))

        # Revenue by Country
        countries = self._svc.get_revenue_by_country(from_date, to_date) or []
        if countries:
            fig = make_lollipop_chart(
                [c.get("country", "?") or "?" for c in countries[:6]],
                [c.get("revenue", 0) or 0 for c in countries[:6]],
                title=t("analytics.country_revenue"),
                color=CHART_SECONDARY,
                is_currency=True,
                show_title=False,
            )
            client_figs.append(fig)
            client_titles.append(t("analytics.country_revenue"))

        # Trip Status (Fixed — translated labels)
        status_dist = self._svc.get_trip_status_distribution(from_date, to_date) or []
        if status_dist:
            _status_label_map = {
                "planned": t("status.planned"),
                "loading": t("status.loading"),
                "in transit": t("status.in_transit"),
                "in_transit": t("status.in_transit"),
                "delivered": t("status.delivered"),
                "cancelled": t("status.cancelled"),
                "invoiced": t("status.invoiced"),
                "paid": t("status.paid"),
            }

            def _tr_status(raw: str) -> str:
                key = (raw or "").strip().lower()
                return _status_label_map.get(key, raw or t("status.unknown"))

            fig = make_pie_chart(
                [s.get("count", 0) or 0 for s in status_dist],
                [_tr_status(s.get("status", "")) for s in status_dist],
                title=t("analytics.trip_status_distribution"),
                show_title=False,
            )
            client_figs.append(fig)
            client_titles.append(t("analytics.trip_status_distribution"))

        if client_figs:
            self._add_plotly_chart_grid(client_figs, client_titles, columns=2)

        # ── Section: Volume & Cost ────────────────────────────────
        self._add_section_header(t("analytics.section_volume_cost"), "")

        volume_figs: list = []
        volume_titles: list[str] = []
        _vol_kpis: list[dict] = []
        spark_trip_vals = self._sparkline_values(spark_monthly, "trip_count", 0)

        spark_total_cost_vals: list[float] = []
        _cost_base = self._svc.get_cost_breakdown(12, from_date, to_date) or []
        for _cr in _cost_base:
            _t = (
                self._safe_float(_cr.get("fuel_cost", 0))
                + self._safe_float(_cr.get("toll_cost", 0))
                + self._safe_float(_cr.get("salary_cost", 0))
                + self._safe_float(_cr.get("extra_costs", 0))
            )
            spark_total_cost_vals.append(_t)

        # Monthly Trip Volume
        trip_vol = self._svc.get_monthly_trip_volume(months, from_date, to_date) or []
        if isinstance(trip_vol, list) and trip_vol:
            if len(trip_vol) < 3:
                _vol_kpis.append({
                    "label": t("analytics.monthly_trip_volume"),
                    "value": self._safe_fmt(
                        trip_vol[-1].get("trip_count", 0), ",.0f"
                    ),
                    "sparkline_values": spark_trip_vals,
                    "sparkline_color": CHART_SUCCESS,
                })
            else:
                vol_months = [self._fmt_month_label(r.get("month", "")) for r in trip_vol]
                fig = make_area_chart(
                    vol_months,
                    [r.get("trip_count", 0) or 0 for r in trip_vol],
                    title=t("analytics.monthly_trip_volume"),
                    color=CHART_SUCCESS,
                    show_title=False,
                )
                volume_figs.append(fig)
                volume_titles.append(t("analytics.monthly_trip_volume"))

        # Cost Breakdown
        cost_data = self._svc.get_cost_breakdown(months, from_date, to_date) or []
        if isinstance(cost_data, list) and cost_data:
            if len(cost_data) < 3:
                _row = cost_data[-1]
                _total = sum(
                    self._safe_float(_row.get(k, 0))
                    for k in ("fuel_cost", "toll_cost", "salary_cost", "extra_costs")
                )
                _vol_kpis.append({
                    "label": t("analytics.cost_breakdown"),
                    "value": f"{self._safe_fmt(_total)} \u20ac",
                    "subtitle": t("analytics.total_costs", default="Total costs"),
                    "sparkline_values": spark_total_cost_vals,
                    "sparkline_color": CHART_INFO,
                })
            else:
                cost_months = [self._fmt_month_label(r.get("month", "")) for r in cost_data]
                fig = make_stacked_area_chart(
                    cost_months,
                    [
                        (t("analytics.fuel"),
                         [r.get("fuel_cost", 0) or 0 for r in cost_data], CHART_WARNING),
                        (t("analytics.toll"),
                         [r.get("toll_cost", 0) or 0 for r in cost_data], CHART_ACCENT),
                        (t("analytics.salary"),
                         [r.get("salary_cost", 0) or 0 for r in cost_data], CHART_INFO),
                        (t("analytics.extra_costs"),
                         [r.get("extra_costs", 0) or 0 for r in cost_data], CHART_SECONDARY),
                    ],
                    title=t("analytics.cost_breakdown"),
                    is_currency=True,
                    empty_message=t("common.no_data"),
                    show_title=False,
                )
                volume_figs.append(fig)
                volume_titles.append(t("analytics.cost_breakdown"))

        if _vol_kpis:
            self._add_kpi_row_with_sparklines(_vol_kpis)
        if volume_figs:
            self._add_plotly_chart_grid(volume_figs, volume_titles, columns=2)


