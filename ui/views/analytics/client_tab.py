"""Client Analytics tab — Top clients by revenue/profit, payment delay, concentration, growth."""

from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from ui.views.analytics._tab_base import BaseTab
from ui.design_tokens import TEXT_SECONDARY, ACCENT_TEXT, SP, FONT_FAMILY
from ui.charts import make_bar_chart, make_pie_chart, make_trend_chart, CHART_ACCENT, CHART_SECONDARY, CHART_SUCCESS, CHART_WARNING
from services.i18n import t


class ClientAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_client", "analytics.client_subtitle")
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
        rev = self._svc.get_revenue_by_client()
        clients = self._svc.get_client_analytics()
        growth = self._svc.get_client_growth(12)
        conc = self._svc.get_revenue_concentration()
        if not rev and not clients: self._add_no_data(t("common.no_data")); return

        # Revenue + Profit side by side
        row_w = QWidget(); row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(8)
        if rev:
            fig1, ax1 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig1)
            make_bar_chart(fig1, ax1, [r.get("client", "?") for r in rev[:8]],
                           [r.get("revenue", 0) or 0 for r in rev[:8]],
                           title=t("analytics.client_revenue"), horizontal=True,
                           color=CHART_ACCENT, highlight_max=True)
            fig1.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig1))
        if clients:
            top_profit = sorted(clients, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:8]
            fig2, ax2 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig2)
            make_bar_chart(fig2, ax2, [c.get("client", "?") for c in top_profit],
                           [c.get("profit", 0) or 0 for c in top_profit],
                           title=t("analytics.client_profit"), horizontal=True,
                           color=CHART_SUCCESS, highlight_max=True)
            fig2.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig2))
        self._chart_layout.addWidget(row_w)

        # Payment delay
        if clients:
            delay_data = [c for c in clients if (c.get("avg_payment_delay_days") or 0) > 0]
            if delay_data:
                fig3, ax3 = plt.subplots(figsize=(12, 3), dpi=90); self._track_figure(fig3)
                make_bar_chart(fig3, ax3, [c.get("client", "?") for c in delay_data[:8]],
                               [c.get("avg_payment_delay_days", 0) or 0 for c in delay_data[:8]],
                               title=t("analytics.client_payment_delay"), horizontal=True,
                               color=CHART_WARNING, highlight_max=True)
                fig3.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig3))

        # Revenue concentration + Growth row
        row2 = QWidget(); row2_l = QHBoxLayout(row2)
        row2_l.setContentsMargins(0, 0, 0, 0); row2_l.setSpacing(8)
        if conc and len(conc) > 3:
            top3_rev = sum(c.get("revenue", 0) or 0 for c in conc[:3])
            rest_rev = sum(c.get("revenue", 0) or 0 for c in conc[3:])
            if top3_rev > 0 or rest_rev > 0:
                fig4, ax4 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig4)
                top_names = ", ".join(c.get("client", "") for c in conc[:3])
                make_pie_chart(fig4, ax4, [top3_rev, rest_rev], [f"Top 3\n({top_names[:30]})", t("analytics.client_rest")],
                               title=t("analytics.client_concentration"), empty_message=t("common.no_data"))
                fig4.tight_layout(pad=1.0); row2_l.addWidget(FigureCanvas(fig4))
        if growth:
            fig5, ax5 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig5)
            make_trend_chart(fig5, ax5, [g.get("month", "") for g in growth],
                             [g.get("new_clients", 0) or 0 for g in growth],
                             title=t("analytics.client_growth"), color=CHART_ACCENT)
            fig5.tight_layout(pad=1.0); row2_l.addWidget(FigureCanvas(fig5))
        if conc and len(conc) > 3 or growth:
            self._chart_layout.addWidget(row2)

        # AI Insight
        if conc and len(conc) > 1:
            for c in conc[:5]:
                rev_pct = (c.get("revenue", 0) or 0) / max(sum(x.get("revenue", 0) or 0 for x in conc), 1) * 100
                profit_pct = (c.get("profit", 0) or 0) / max(sum(x.get("profit", 0) or 0 for x in conc), 1) * 100
                if abs(rev_pct - profit_pct) > 15:
                    insight = QLabel(t("analytics.client_insight").format(
                        client=c.get("client", "?"), rev_pct=f"{rev_pct:.0f}", profit_pct=f"{profit_pct:.0f}"))
                    insight.setStyleSheet(f"color:{ACCENT_TEXT};font-size:13px;font-family:{FONT_FAMILY};padding:8px;")
                    insight.setWordWrap(True)
                    self._chart_layout.addWidget(insight)
                    break
