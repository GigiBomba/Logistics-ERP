"""Document Analytics tab — Counts by type, upload trends, expiring, CMR trends."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import KPICard
from ui.design_tokens import (
    BORDER_DEFAULT,
    COLOR_BG_ELEVATED,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_TEXT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_TEXT,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_TEXT,
    FONT_FAMILY,
    RADIUS_SM,
    SP,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING_TEXT,
)
from ui.plotly_charts import (
    CHART_ACCENT,
    CHART_SUCCESS,
    CHART_WARNING,
    make_line_chart,
    make_pie_chart,
    make_trend_chart,
)
from ui.plotly_renderer import PlotlyChartWidget
from ui.views.analytics._tab_base import BaseTab


def _days_until_expiry(expiry_date_str: str) -> int:
    """Return days until a date string expires, or 9999 if unparseable."""
    from datetime import date as _date
    try:
        expiry = _date.fromisoformat(expiry_date_str[:10])
        return (expiry - _date.today()).days
    except (ValueError, TypeError):
        return 9999


def _expiry_color(days: int) -> str:
    """Return color for expiry urgency."""
    if days <= 7:
        return COLOR_ERROR_DEFAULT
    if days <= 14:
        return COLOR_WARNING_DEFAULT
    return COLOR_SUCCESS_DEFAULT


def _expiry_text_color(days: int) -> str:
    if days <= 7:
        return COLOR_ERROR_TEXT
    if days <= 14:
        return COLOR_WARNING_TEXT
    return COLOR_SUCCESS_TEXT


class DocumentAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_document", "analytics.document_subtitle")
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
        docs = self._svc.get_document()
        trend = self._svc.get_document_upload_trend(12)
        if docs is None:
            self._add_no_data(t("common.no_data"))
            return

        # KPI strip
        kpi_row = QWidget()
        kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0)
        kpi_l.setSpacing(12)
        kpi_l.addWidget(KPICard(kpi_row, f"\U0001f4c4 {t('analytics.kpi_invoices')}",
                                str(docs.get("invoice_count", 0) or 0)))
        kpi_l.addWidget(KPICard(kpi_row, f"\u2705 {t('analytics.kpi_cmrs')}",
                                str(docs.get("cmr_count", 0) or 0)))
        kpi_l.addWidget(KPICard(kpi_row, f"\U0001f4c1 {t('analytics.kpi_total_docs')}",
                                str(docs.get("total_docs", 0) or 0)))
        expiring = docs.get("expiring") or []
        kpi_l.addWidget(KPICard(kpi_row, f"\u26a0 {t('analytics.kpi_expiring')}",
                                str(len(expiring)),
                                value_color=WARNING_TEXT if expiring else None))
        self._chart_layout.addWidget(kpi_row)

        # Category pie + Upload trend row
        row_w = QWidget()
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(8)
        try:
            inv_n = int(float(docs.get("invoice_count", 0) or 0))
            cmr_n = int(float(docs.get("cmr_count", 0) or 0))
            total = int(float(docs.get("total_docs", 0) or 0))
        except (TypeError, ValueError):
            inv_n = cmr_n = 0
            total = 0
        other_n = max(total - inv_n - cmr_n, 0)
        if inv_n + cmr_n + other_n > 0:
            fig1 = make_pie_chart(
                [inv_n, cmr_n, other_n],
                [t("analytics.doc_invoices"), t("analytics.doc_cmrs"), t("analytics.doc_other")],
                title=t("analytics.doc_distribution"),
            )
            pw1 = PlotlyChartWidget()
            pw1.set_figure(fig1)
            row_l.addWidget(pw1)
        trend_months = [self._fmt_month_label(r.get("month", "")) for r in trend] if trend else []
        if trend:
            fig2 = make_trend_chart(
                trend_months,
                [r.get("doc_count", 0) or 0 for r in trend],
                title=t("analytics.doc_upload_trend"), color=CHART_ACCENT,
            )
            pw2 = PlotlyChartWidget(min_height=180)
            pw2.set_figure(fig2)
            row_l.addWidget(pw2)
        self._chart_layout.addWidget(row_w)

        # CMR generation trend
        if trend:
            fig3 = make_trend_chart(
                trend_months,
                [r.get("cmr_count", 0) or 0 for r in trend],
                title=t("analytics.doc_cmr_trend"), color=CHART_SUCCESS,
            )
            pw3 = PlotlyChartWidget(min_height=180)
            pw3.set_figure(fig3)
            self._chart_layout.addWidget(pw3)

        # ── Document Upload vs Expected (vs Trip Count) ────────
        from_date, to_date = self._date_range()
        trip_vol = self._svc.get_monthly_trip_volume(12, from_date, to_date) or []
        if trend and trip_vol:
            # Join by month key
            trip_by_month = {r.get("month", ""): r.get("trip_count", 0) or 0 for r in trip_vol}
            upload_months = []
            upload_counts = []
            expected_counts = []
            for r in trend:
                m = r.get("month", "")
                upload_months.append(self._fmt_month_label(m))
                upload_counts.append(r.get("doc_count", 0) or 0)
                expected_counts.append(trip_by_month.get(m, 0))

            if any(v > 0 for v in upload_counts) and any(v > 0 for v in expected_counts):
                fig4 = make_line_chart(
                    upload_months,
                    [
                        (upload_counts,
                         t("analytics.doc_actual_uploads", default="Actual Uploads"),
                         CHART_ACCENT),
                        (expected_counts,
                         t("analytics.doc_expected_uploads", default="Expected (Trips)"),
                         CHART_WARNING),
                    ],
                    title=t("analytics.doc_upload_vs_expected",
                           default="Document Uploads vs Expected"),
                    show_title=False,
                )
                pw4 = PlotlyChartWidget(min_height=180)
                pw4.set_figure(fig4)
                self._chart_layout.addWidget(pw4)

        # ── Expiring documents (structured widget) ─────────────────
        if expiring:
            self._build_expiry_list(expiring)
        else:
            self._build_expiry_empty()

    # ── Expiry list widget ──────────────────────────────────────────

    def _build_expiry_list(self, expiring: list) -> None:
        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background: {COLOR_BG_ELEVATED};"
            f" border: 1px solid {BORDER_DEFAULT}; border-radius: {RADIUS_SM}px; }}"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        layout.setSpacing(0)

        header = QLabel(
            "\u26a0  "
            + t("analytics.doc_expiring_header",
                default="{count} documents expiring within 30 days:").format(
                    count=len(expiring))
        )
        header.setStyleSheet(
            f"color: {WARNING_TEXT}; font-size: 13px; font-weight: 600;"
            f" font-family: '{FONT_FAMILY}'; padding-bottom: 8px;"
        )
        layout.addWidget(header)

        shown = min(len(expiring), 5)
        for e in expiring[:shown]:
            title = e.get("title", "?")
            expiry_date = e.get("expiry_date", "?")
            days = _days_until_expiry(expiry_date)
            days_text = f"{days} days" if days >= 0 else "Expired"

            row = QFrame()
            row.setFixedHeight(38)
            row.setStyleSheet(
                f"QFrame:hover {{ background: {COLOR_BG_ELEVATED}; }}"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(SP["2"], 0, SP["2"], 0)
            row_layout.setSpacing(SP["2"])

            name_lbl = QLabel(title)
            name_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 12px;"
                f" font-family: '{FONT_FAMILY}';"
            )
            row_layout.addWidget(name_lbl, 1)

            days_lbl = QLabel(
                f"{t('analytics.doc_expires', default='Expires')}: {expiry_date[:10]}"
            )
            days_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px;"
                f" font-family: '{FONT_FAMILY}';"
            )
            row_layout.addWidget(days_lbl)

            urgency = QLabel(f"  {days_text}  ")
            urgency.setStyleSheet(
                f"color: {_expiry_text_color(days)}; font-size: 11px; font-weight: 600;"
                f" font-family: '{FONT_FAMILY}';"
                f" background: {_expiry_color(days)}22;"
                f" border-radius: 4px; padding: 2px 6px;"
            )
            row_layout.addWidget(urgency)

            layout.addWidget(row)

        if len(expiring) > shown:
            more = QLabel(
                t("analytics.doc_see_all", default="See all ({count})").format(
                    count=len(expiring)
                )
            )
            more.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
                f" font-family: '{FONT_FAMILY}'; padding-top: 8px;"
            )
            layout.addWidget(more)

        self._chart_layout.addWidget(container)

    def _build_expiry_empty(self) -> None:
        note = QLabel(
            "\u2705  "
            + t("analytics.doc_no_expiring",
                default="No documents expiring within 30 days")
        )
        note.setStyleSheet(
            f"color: {COLOR_SUCCESS_TEXT}; font-size: 12px;"
            f" font-family: '{FONT_FAMILY}'; padding: 8px;"
            f" background: {COLOR_BG_ELEVATED}; border-radius: 4px;"
        )
        self._chart_layout.addWidget(note)
