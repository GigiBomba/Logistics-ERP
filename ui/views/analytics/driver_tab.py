"""Driver Analytics tab — Trips, Profit, Efficiency, Tacho compliance."""

from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from ui.views.analytics._tab_base import BaseTab
from ui.charts import make_bar_chart, CHART_ACCENT, CHART_SECONDARY, CHART_SUCCESS, CHART_WARNING
from services.i18n import t


class DriverAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_driver", "analytics.driver_subtitle")
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
        drivers = self._svc.get_driver()
        ppm = self._svc.get_driver_profit_per_km()
        tacho = self._svc.get_driver_tacho_violations()
        if not drivers: self._add_no_data(t("common.no_data")); return

        # Trips completed
        fig1, ax1 = plt.subplots(figsize=(12, 3), dpi=90); self._track_figure(fig1)
        top = sorted(drivers, key=lambda r: r.get("trip_count", 0) or 0, reverse=True)[:10]
        make_bar_chart(fig1, ax1, [d.get("driver", "?") for d in top],
                       [d.get("trip_count", 0) or 0 for d in top],
                       title=t("analytics.driver_trips"), horizontal=True,
                       color=CHART_ACCENT, highlight_max=True)
        fig1.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig1))

        # Profit per driver
        fig2, ax2 = plt.subplots(figsize=(12, 3), dpi=90); self._track_figure(fig2)
        top_p = sorted(drivers, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:10]
        make_bar_chart(fig2, ax2, [d.get("driver", "?") for d in top_p],
                       [d.get("profit", 0) or 0 for d in top_p],
                       title=t("analytics.driver_profit"), horizontal=True,
                       color=CHART_SUCCESS, highlight_max=True)
        fig2.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig2))

        # Efficiency row
        row_w = QWidget(); row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(8)
        if ppm:
            fig3, ax3 = plt.subplots(figsize=(5.5, 2.5), dpi=90); self._track_figure(fig3)
            top_eff = sorted(ppm, key=lambda r: r.get("profit_per_km", 0) or 0, reverse=True)[:8]
            make_bar_chart(fig3, ax3, [d.get("driver_name", "?") for d in top_eff],
                           [d.get("profit_per_km", 0) or 0 for d in top_eff],
                           title=t("analytics.driver_efficiency"), horizontal=True,
                           color=CHART_SECONDARY, highlight_max=True)
            fig3.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig3))
        if tacho:
            fig4, ax4 = plt.subplots(figsize=(5.5, 2.5), dpi=90); self._track_figure(fig4)
            make_bar_chart(fig4, ax4, [d.get("driver", "?") for d in tacho[:8]],
                           [d.get("total_violations", 0) or 0 for d in tacho[:8]],
                           title=t("analytics.driver_tacho"), horizontal=True,
                           color=CHART_WARNING, highlight_max=True)
            fig4.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig4))
        if ppm or tacho:
            self._chart_layout.addWidget(row_w)
