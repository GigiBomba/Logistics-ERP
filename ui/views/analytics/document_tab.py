"""Document Analytics tab — Counts by type, upload trends, expiring, CMR trends."""

from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from ui.views.analytics._tab_base import BaseTab
from ui.design_tokens import TEXT_MUTED, DANGER_TEXT, WARNING_TEXT, SP, FONT_FAMILY
from ui.charts import make_pie_chart, make_trend_chart, CHART_ACCENT, CHART_SECONDARY, CHART_SUCCESS, CHART_WARNING, CHART_DANGER
from ui.components import KPICard
from services.i18n import t


class DocumentAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_document", "analytics.document_subtitle")
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
        docs = self._svc.get_document()
        trend = self._svc.get_document_upload_trend(12)
        if docs is None: self._add_no_data(t("common.no_data")); return

        # KPI strip
        kpi_row = QWidget(); kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0); kpi_l.setSpacing(12)
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_invoices"), str(docs.get("invoice_count", 0) or 0)))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_cmrs"), str(docs.get("cmr_count", 0) or 0)))
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_total_docs"), str(docs.get("total_docs", 0) or 0)))
        expiring = docs.get("expiring") or []
        kpi_l.addWidget(KPICard(kpi_row, t("analytics.kpi_expiring"), str(len(expiring)),
                                value_color=WARNING_TEXT if expiring else None))
        self._chart_layout.addWidget(kpi_row)

        # Category pie + Upload trend row
        row_w = QWidget(); row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(8)
        inv_n = docs.get("invoice_count", 0) or 0
        cmr_n = docs.get("cmr_count", 0) or 0
        other_n = max((docs.get("total_docs", 0) or 0) - inv_n - cmr_n, 0)
        if inv_n + cmr_n + other_n > 0:
            fig1, ax1 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig1)
            make_pie_chart(fig1, ax1, [inv_n, cmr_n, other_n],
                           [t("analytics.doc_invoices"), t("analytics.doc_cmrs"), t("analytics.doc_other")],
                           title=t("analytics.doc_distribution"))
            fig1.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig1))
        if trend:
            fig2, ax2 = plt.subplots(figsize=(5.5, 3), dpi=90); self._track_figure(fig2)
            make_trend_chart(fig2, ax2, [r.get("month", "") for r in trend],
                             [r.get("doc_count", 0) or 0 for r in trend],
                             title=t("analytics.doc_upload_trend"), color=CHART_ACCENT)
            fig2.tight_layout(pad=1.0); row_l.addWidget(FigureCanvas(fig2))
        self._chart_layout.addWidget(row_w)

        # CMR generation trend
        if trend:
            fig3, ax3 = plt.subplots(figsize=(12, 2.5), dpi=90); self._track_figure(fig3)
            make_trend_chart(fig3, ax3, [r.get("month", "") for r in trend],
                             [r.get("doc_count", 0) or 0 for r in trend],
                             title=t("analytics.doc_cmr_trend"), color=CHART_SUCCESS)
            fig3.tight_layout(pad=1.0); self._chart_layout.addWidget(FigureCanvas(fig3))

        # Expiring documents warning
        if expiring:
            exp_lbl = QLabel(t("analytics.doc_expiring_header").format(count=len(expiring)))
            exp_text = "\n".join(f"• {e.get('title', '?')} — {e.get('expiry_date', '?')}" for e in expiring[:6])
            exp_lbl.setText(f"{exp_lbl.text()}\n{exp_text}")
            exp_lbl.setStyleSheet(f"color:{WARNING_TEXT};font-size:12px;font-family:{FONT_FAMILY};padding:8px;")
            exp_lbl.setWordWrap(True)
            self._chart_layout.addWidget(exp_lbl)
