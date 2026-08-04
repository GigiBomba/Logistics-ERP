"""Fleet Analytics tab — Profitability, Fuel Efficiency, Utilization, Maintenance."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.i18n import t
from ui.components import KPICard
from ui.design_tokens import (
    COLOR_SUCCESS_DEFAULT,
    COLOR_WARNING_DEFAULT,
    DANGER,
    FONT_FAMILY,
    SP,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
)
from ui.plotly_charts import (
    CHART_ACCENT,
    CHART_DANGER,
    CHART_INFO,
    CHART_SECONDARY,
    CHART_SUCCESS,
    CHART_WARNING,
    _value_colors,
    make_bar_chart,
    make_trend_chart,
)
from ui.plotly_renderer import PlotlyChartWidget
from ui.views.analytics._tab_base import BaseTab


def _fmt_truck_label(raw: str | None) -> str:
    """Return a display label for a truck, never blank."""
    if not raw or str(raw).strip() in ("", "None", "Unknown", "?"):
        return t("fleet.unnamed_truck", default="(Unnamed Truck)")
    return str(raw)


class FleetAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_fleet", "analytics.fleet_subtitle")
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
        fleet = self._svc.get_fleet(from_date, to_date) or []
        util = self._svc.get_truck_utilization()
        maint = self._svc.get_maintenance_alerts() or []
        if not fleet:
            self._add_no_data(t("common.no_data"))
            return

        total_km = sum(r.get("total_km", 0) or 0 for r in fleet)
        truck_count = len(fleet)
        avg_consumption = sum(
            r.get("avg_consumption", 0) or 0 for r in fleet
        ) / max(truck_count, 1)
        total_fuel_cost = sum(r.get("total_fuel_cost", 0) or 0 for r in fleet)
        avg_cost_per_km = total_fuel_cost / max(total_km, 1)

        # ── KPI strip ─────────────────────────────────────────────
        kpi_row = QWidget()
        kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0)
        kpi_l.setSpacing(SP["4"])
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_active_trucks"), str(truck_count)))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_total_km"), f"{total_km:,.0f} km"))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_avg_consumption"),
                                f"{avg_consumption:.1f} L/100km"))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_cost_per_km", default="Avg Cost/km"),
                                f"\u20ac {avg_cost_per_km:.2f}/km"))
        otd_raw = self._svc.get_otd_percentage(from_date, to_date)
        otd_pct = otd_raw if isinstance(otd_raw, (int, float)) else 0.0
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_otd", default="On-Time Delivery"),
                                f"{otd_pct:.1f}%"))
        maint_count = len(maint)
        maint_color = SUCCESS
        if maint_count >= 4:
            maint_color = DANGER
        elif maint_count >= 1:
            maint_color = WARNING
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_maint_alerts"), str(maint_count),
                                value_color=maint_color))
        self._chart_layout.addWidget(kpi_row)

        # ── Profitability ranking ─────────────────────────────────
        if fleet:
            trucks = sorted(fleet, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:12]
            truck_labels = [_fmt_truck_label(r.get("truck")) for r in trucks]
            truck_profits = [r.get("profit", 0) or 0 for r in trucks]
            fig1 = make_bar_chart(
                truck_labels,
                truck_profits,
                title=t("analytics.fleet_profitability"), horizontal=True,
                color=_value_colors(truck_profits), highlight_max=True,
                is_currency=True,
            )
            pw1 = PlotlyChartWidget(min_height=180)
            pw1.set_figure(fig1)
            self._chart_layout.addWidget(pw1)

        # ── Fuel efficiency ───────────────────────────────────────
        if fleet:
            eff_trucks = fleet[:12]
            eff_labels = [_fmt_truck_label(r.get("truck")) for r in eff_trucks]
            eff_values = []
            eff_colors = []
            _has_fuel_data = False
            for r in eff_trucks:
                v = r.get("avg_consumption", 0) or 0
                _has_real = bool(
                    v and v > 0
                    and r.get("total_fuel_cost", 0)
                    and r.get("total_fuel_cost", 0) > 0
                )
                if _has_real:
                    _has_fuel_data = True
                    eff_values.append(v)
                    if v < 35:
                        eff_colors.append(COLOR_SUCCESS_DEFAULT)
                    elif v <= 50:
                        eff_colors.append(COLOR_WARNING_DEFAULT)
                    else:
                        eff_colors.append(CHART_DANGER)
                else:
                    eff_values.append(0)
                    eff_colors.append(TEXT_MUTED)

            fig2 = make_bar_chart(
                eff_labels,
                eff_values,
                title=t("analytics.fleet_fuel_efficiency"), horizontal=True,
                color=eff_colors, highlight_max=False,
            )
            if _has_fuel_data:
                fig2.add_vline(x=32, line={"color": COLOR_WARNING_DEFAULT, "width": 1.5, "dash": "dash"},
                               annotation_text=t("fleet.fuel_target", default="Target 32"),
                               annotation_position="top")
            pw2 = PlotlyChartWidget(min_height=180)
            pw2.set_figure(fig2)
            self._chart_layout.addWidget(pw2)

            if not _has_fuel_data:
                note = QLabel(
                    t("fleet.no_fuel_data", default="No fuel consumption data recorded — showing estimates")
                )
                note.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px; font-family: {FONT_FAMILY};"
                    f" padding: 2px 8px;"
                )
                self._chart_layout.addWidget(note)

        # ── Utilization table ─────────────────────────────────────
        if util:
            util_header = QLabel(t("analytics.fleet_utilization"))
            util_header.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
                f" font-family: '{FONT_FAMILY}'; padding: 8px 0 4px 0;"
            )
            self._chart_layout.addWidget(util_header)
            for u in util[:8]:
                truck_name = _fmt_truck_label(u.get("truck"))
                trips = u.get("trip_count", 0) or 0
                km = u.get("total_km", 0) or 0
                row = QLabel(f"  {truck_name}  ·  {trips} trips  ·  {km:,.0f} km")
                row.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px; font-family: '{FONT_FAMILY}';"
                    f" padding: 2px 8px;"
                )
                self._chart_layout.addWidget(row)

        # ── Maintenance row ───────────────────────────────────────
        if maint:
            maint_label = QLabel()
            _em = "\u2014"
            maint_text = "\n".join(
                f"{_fmt_truck_label(m.get('truck'))}: {m.get('next_due_date', _em)}"
                for m in maint[:6]
            )
            maint_label.setText(f"{t('analytics.kpi_maint_alerts')}:\n{maint_text}")
            maint_label.setStyleSheet(
                f"color:{TEXT_MUTED};font-size:12px;font-family:{FONT_FAMILY};padding:12px;"
            )
            maint_label.setWordWrap(True)
            self._chart_layout.addWidget(maint_label)

        # ── Fuel Cost Trend ───────────────────────────────────────
        cost_data = self._svc.get_cost_breakdown(self._months(), from_date, to_date) or []
        if cost_data and len(cost_data) >= 2:
            cost_months = [self._fmt_month_label(r.get("month", "")) for r in cost_data]
            fuel_costs = [r.get("fuel_cost", 0) or 0 for r in cost_data]
            if any(v > 0 for v in fuel_costs):
                fig5 = make_trend_chart(
                    cost_months, fuel_costs,
                    title=t("analytics.fuel_cost_trend"), color=CHART_WARNING,
                    is_currency=True,
                )
                pw5 = PlotlyChartWidget(min_height=180)
                pw5.set_figure(fig5)
                self._chart_layout.addWidget(pw5)
