"""Financial Analytics tab — Revenue, Profit, Margin, Top Clients, Top Countries."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from ui.views.analytics._tab_base import BaseTab
from ui.design_tokens import SUCCESS, DANGER
from ui.charts import make_trend_chart, make_bar_chart, CHART_ACCENT, CHART_SECONDARY, CHART_SUCCESS
from ui.components import KPICard
from services.i18n import t


class FinancialAnalyticsTab(BaseTab):
    """Am I making money? — Revenue, profit, margin trends, top clients, top countries."""

    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_financial", "analytics.financial_subtitle")
        # Chart container
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
        import matplotlib
        matplotlib.use("QtAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        if self._svc is None:
            self._add_no_data()
            return

        data = self._svc.get_monthly_financial(24)
        if not data:
            self._add_no_data(t("analytics.no_financial_data"))
            return

        # KPI strip
        total_rev = sum(r.get("revenue", 0) or 0 for r in data)
        total_profit = sum(r.get("profit", 0) or 0 for r in data)
        last_margin = data[-1].get("margin_pct", 0) or 0 if data else 0
        top_clients = self._svc.get_revenue_by_client()
        top_client_name = top_clients[0].get("client", "—") if top_clients else "—"

        kpi_row = QWidget()
        kpi_layout = QHBoxLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(12)
        kpi_layout.addWidget(KPICard(kpi_row, t("analytics.kpi_total_revenue"), f"{total_rev:,.0f} €"))
        kpi_layout.addWidget(KPICard(kpi_row, t("analytics.kpi_total_profit"), f"{total_profit:,.0f} €",
                                     value_color=SUCCESS if total_profit >= 0 else DANGER))
        kpi_layout.addWidget(KPICard(kpi_row, t("analytics.kpi_avg_margin"), f"{last_margin:.1f}%"))
        kpi_layout.addWidget(KPICard(kpi_row, t("analytics.kpi_top_client"), top_client_name))
        self._chart_layout.addWidget(kpi_row)

        # Revenue + Profit trend
        months = [r.get("month", "") for r in data]
        fig1, ax1 = plt.subplots(figsize=(12, 3.5), dpi=90)
        self._track_figure(fig1)
        make_trend_chart(fig1, ax1, months, [r.get("revenue", 0) or 0 for r in data],
                         title=f"{t('analytics.revenue_label')} — 24 {t('analytics.months')}",
                         color=CHART_ACCENT)
        fig1.tight_layout(pad=1.0)
        c1 = FigureCanvas(fig1)
        self._chart_layout.addWidget(c1)

        fig2, ax2 = plt.subplots(figsize=(12, 2), dpi=90)
        self._track_figure(fig2)
        make_trend_chart(fig2, ax2, months, [r.get("profit", 0) or 0 for r in data],
                         title=f"{t('analytics.profit_label')} — 24 {t('analytics.months')}",
                         color=CHART_SUCCESS)
        fig2.tight_layout(pad=1.0)
        c2 = FigureCanvas(fig2)
        self._chart_layout.addWidget(c2)

        # Margin trend
        fig3, ax3 = plt.subplots(figsize=(12, 2), dpi=90)
        self._track_figure(fig3)
        make_trend_chart(fig3, ax3, months, [r.get("margin_pct", 0) or 0 for r in data],
                         title=f"{t('analytics.profit_ratio_title')} — 24 {t('analytics.months')}",
                         color=CHART_SECONDARY)
        fig3.tight_layout(pad=1.0)
        c3 = FigureCanvas(fig3)
        self._chart_layout.addWidget(c3)

        # Revenue by Client + Revenue by Country side-by-side
        row_w = QWidget()
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(8)

        clients = self._svc.get_revenue_by_client()
        if clients:
            fig4, ax4 = plt.subplots(figsize=(5.5, 3), dpi=90)
            self._track_figure(fig4)
            make_bar_chart(fig4, ax4, [c.get("client", "?") for c in clients[:8]],
                           [c.get("revenue", 0) or 0 for c in clients[:8]],
                           title=t("analytics.top_trucks_title"), horizontal=True,
                           color=CHART_ACCENT, highlight_max=True,
                           empty_message=t("common.no_data"))
            fig4.tight_layout(pad=1.0)
            row_l.addWidget(FigureCanvas(fig4))

        countries = self._svc.get_revenue_by_country()
        if countries:
            fig5, ax5 = plt.subplots(figsize=(5.5, 3), dpi=90)
            self._track_figure(fig5)
            make_bar_chart(fig5, ax5, [c.get("country", "?") for c in countries[:6]],
                           [c.get("revenue", 0) or 0 for c in countries[:6]],
                           title=t("analytics.country_revenue"), horizontal=True,
                           color=CHART_SECONDARY, highlight_max=True,
                           empty_message=t("common.no_data"))
            fig5.tight_layout(pad=1.0)
            row_l.addWidget(FigureCanvas(fig5))

        if clients or countries:
            self._chart_layout.addWidget(row_w)
