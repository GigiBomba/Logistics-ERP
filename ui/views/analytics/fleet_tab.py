"""Fleet Analytics tab — Profitability, Fuel Efficiency, Utilization, Maintenance."""

from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from ui.views.analytics._tab_base import BaseTab
from ui.design_tokens import SUCCESS, DANGER, WARNING, TEXT_MUTED, SP, FONT_FAMILY
from ui.charts import make_bar_chart, CHART_ACCENT, CHART_SECONDARY, CHART_DANGER
from ui.components import KPICard
from services.i18n import t


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

    def refresh(self):
        self.cleanup()
        self._build()
        self._render()

    def _render(self):
        import matplotlib; matplotlib.use("QtAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        if self._svc is None:
            self._add_no_data(); return

        fleet = self._svc.get_fleet()
        util = self._svc.get_truck_utilization()
        maint = self._svc.get_maintenance_alerts() or []
        if not fleet:
            self._add_no_data(t("common.no_data")); return

        # KPI strip
        kpi_row = QWidget()
        kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0); kpi_l.setSpacing(12)
        total_km = sum(r.get("total_km", 0) or 0 for r in fleet)
        truck_count = len(fleet)
        avg_consumption = sum(r.get("avg_consumption", 0) or 0 for r in fleet) / max(truck_count, 1)
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_active_trucks"), str(truck_count)))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_total_km"), f"{total_km:,.0f} km"))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_avg_consumption"), f"{avg_consumption:.1f} L/100km"))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_maint_alerts"), str(len(maint)),
                                value_color=WARNING if maint else SUCCESS))
        self._chart_layout.addWidget(kpi_row)

        # Profitability ranking
        if fleet:
            fig1, ax1 = plt.subplots(figsize=(12, 3.5), dpi=90)
            self._track_figure(fig1)
            trucks = sorted(fleet, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:12]
            make_bar_chart(fig1, ax1,
                           [r.get("truck", "?") for r in trucks],
                           [r.get("profit", 0) or 0 for r in trucks],
                           title=t("analytics.fleet_profitability"), horizontal=True,
                           color=CHART_ACCENT, highlight_max=True)
            fig1.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig1))

        # Fuel efficiency
        if fleet:
            fig2, ax2 = plt.subplots(figsize=(12, 3), dpi=90)
            self._track_figure(fig2)
            make_bar_chart(fig2, ax2,
                           [r.get("truck", "?") for r in fleet[:12]],
                           [r.get("avg_consumption", 0) or 0 for r in fleet[:12]],
                           title=t("analytics.fleet_fuel_efficiency"), horizontal=True,
                           color=CHART_SECONDARY, highlight_max=True)
            fig2.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig2))

        # Utilization + Maintenance alerts row
        row_w = QWidget()
        row_l = QHBoxLayout(row_w); row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(8)
        if util:
            fig3, ax3 = plt.subplots(figsize=(5.5, 2.5), dpi=90)
            self._track_figure(fig3)
            make_bar_chart(fig3, ax3,
                           [r.get("truck", "?") for r in util[:8]],
                           [r.get("trip_count", 0) or 0 for r in util[:8]],
                           title=t("analytics.fleet_utilization"), horizontal=True,
                           color=CHART_ACCENT, highlight_max=True)
            fig3.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig3))
        if maint:
            maint_label = QLabel()
            maint_text = "\n".join(f"{m.get('truck', '?')}: {m.get('next_due_date', '—')}" for m in maint[:8])
            maint_label.setText(f"Upcoming Maintenance:\n{maint_text}")
            maint_label.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;font-family:{FONT_FAMILY};padding:12px;")
            maint_label.setWordWrap(True)
            row_l.addWidget(maint_label)
        self._chart_layout.addWidget(row_w)
