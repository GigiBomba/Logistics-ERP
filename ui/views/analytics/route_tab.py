"""Route Analytics tab — Most/Least profitable routes, Profit/km, Fuel/km, Country corridors."""

from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from ui.views.analytics._tab_base import BaseTab
from ui.charts import make_bar_chart, CHART_ACCENT, CHART_SECONDARY, CHART_DANGER
from services.i18n import t


class RouteAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_route", "analytics.route_subtitle")
        self._chart_widget = QWidget()
        self._chart_layout = QVBoxLayout(self._chart_widget)
        self._chart_layout.setContentsMargins(0, 0, 0, 0); self._chart_layout.setSpacing(8)
        self._content_layout.addWidget(self._chart_widget)

    def refresh(self):
        self.cleanup(); self._build(); self._render()

    def _render(self):
        import matplotlib; matplotlib.use("QtAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        if self._svc is None: self._add_no_data(); return
        routes = self._svc.get_route_profitability()
        countries = self._svc.get_profit_per_km_by_country()
        if not routes: self._add_no_data(t("common.no_data")); return

        # Most profitable routes
        fig1, ax1 = plt.subplots(figsize=(12, 4), dpi=90); self._track_figure(fig1)
        top = sorted(routes, key=lambda r: r.get("avg_profit", 0) or 0, reverse=True)[:12]
        make_bar_chart(fig1, ax1, [r.get("route_label", "?") for r in top],
                       [r.get("avg_profit", 0) or 0 for r in top],
                       title=t("analytics.route_profitability"), horizontal=True,
                       color=CHART_ACCENT, highlight_max=True)
        fig1.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig1))

        # Profit/km + Fuel/km row
        row_w = QWidget(); row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(8)
        fig2, ax2 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig2)
        make_bar_chart(fig2, ax2, [r.get("route_label", "?") for r in top],
                       [r.get("profit_per_km", 0) or 0 for r in top],
                       title=t("analytics.route_profit_per_km"), horizontal=True,
                       color=CHART_SECONDARY, highlight_max=True)
        fig2.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig2))
        fig3, ax3 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig3)
        make_bar_chart(fig3, ax3, [r.get("route_label", "?") for r in top],
                       [r.get("fuel_per_km", 0) or 0 for r in top],
                       title=t("analytics.route_fuel_per_km"), horizontal=True,
                       color=CHART_DANGER, highlight_max=True)
        fig3.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig3))
        self._chart_layout.addWidget(row_w)

        # Country corridors
        if countries:
            fig4, ax4 = plt.subplots(figsize=(12, 3), dpi=90); self._track_figure(fig4)
            make_bar_chart(fig4, ax4, [c.get("country", "?") for c in countries[:10]],
                           [c.get("profit_per_km", 0) or 0 for c in countries[:10]],
                           title=t("analytics.route_country_profit_km"), horizontal=True,
                           color=CHART_ACCENT, highlight_max=True)
            fig4.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig4))
