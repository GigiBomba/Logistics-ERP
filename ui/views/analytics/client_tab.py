"""Client Analytics tab — Top clients by revenue/profit, payment delay, concentration, growth."""

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
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_ERROR_DEFAULT,
    COLOR_INFO_DEFAULT,
    COLOR_INFO_SUBTLE,
    COLOR_INFO_TEXT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    FONT_FAMILY,
    SP,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING,
)
from ui.plotly_charts import (
    CHART_ACCENT,
    _value_colors,
    make_bar_chart,
    make_pie_chart,
    make_trend_chart,
)
from ui.plotly_renderer import PlotlyChartWidget
from ui.views.analytics._tab_base import BaseTab


class ClientAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_client", "analytics.client_subtitle")
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
        rev = self._svc.get_revenue_by_client(from_date, to_date) or []
        clients = self._svc.get_client_analytics(from_date, to_date) or []
        growth = self._svc.get_client_growth(12, from_date, to_date)
        conc = self._svc.get_revenue_concentration()
        if not rev and not clients:
            self._add_no_data(t("common.no_data"))
            return

        # ── KPI strip ────────────────────────────────────────────
        total_clients = len(rev) if rev else len(clients)
        top_client_name = rev[0].get("client", "?") if rev else "?"
        top_client_rev = rev[0].get("revenue", 0) if rev else 0
        avg_delay = sum(
            c.get("avg_payment_delay_days", 0) or 0 for c in clients
        ) / max(len(clients), 1)
        new_in_period = sum(g.get("new_clients", 0) or 0 for g in growth) if growth else 0

        kpi_row = QWidget()
        kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0)
        kpi_l.setSpacing(SP["4"])
        kpi_l.addWidget(self._make_client_kpi(
            t("analytics.kpi_total_clients", default="Total Clients"),
            str(total_clients),
        ))
        kpi_l.addWidget(self._make_client_kpi(
            t("analytics.kpi_top_client_rev", default="Top Client"),
            f"{top_client_name}\n\u20ac {top_client_rev:,.0f}",
            multiline=True,
        ))
        kpi_l.addWidget(self._make_client_kpi(
            t("analytics.kpi_avg_payment_delay", default="Avg Payment Delay"),
            f"{avg_delay:.0f} days",
            value_color=COLOR_WARNING_DEFAULT if avg_delay > 30 else COLOR_SUCCESS_DEFAULT,
        ))
        kpi_l.addWidget(self._make_client_kpi(
            t("analytics.kpi_new_clients", default="New Clients"),
            str(int(new_in_period)),
        ))
        self._chart_layout.addWidget(kpi_row)

        # ── Revenue + Profit side by side ────────────────────────
        row_w = QWidget()
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(8)
        if rev:
            rev_labels = [r.get("client", "?") or "?" for r in rev[:8]]
            rev_revenues = [r.get("revenue", 0) or 0 for r in rev[:8]]
            fig1 = make_bar_chart(
                rev_labels, rev_revenues,
                title=t("analytics.client_revenue"), horizontal=True,
                color=CHART_ACCENT, highlight_max=True, is_currency=True,
            )
            pw1 = PlotlyChartWidget(min_height=180)
            pw1.set_figure(fig1)
            row_l.addWidget(pw1)
        if clients:
            top_profit = sorted(clients, key=lambda r: r.get("profit", 0) or 0, reverse=True)[:8]
            client_labels_p = [c.get("client", "?") or "?" for c in top_profit]
            client_profits = [c.get("profit", 0) or 0 for c in top_profit]
            fig2 = make_bar_chart(
                client_labels_p, client_profits,
                title=t("analytics.client_profit"), horizontal=True,
                color=_value_colors(client_profits), highlight_max=True,
                is_currency=True,
            )
            pw2 = PlotlyChartWidget(min_height=180)
            pw2.set_figure(fig2)
            row_l.addWidget(pw2)
        self._chart_layout.addWidget(row_w)

        # ── Payment delay ────────────────────────────────────────
        if clients:
            delay_data = [c for c in clients if (c.get("avg_payment_delay_days") or 0) > 0]
            if delay_data:
                delay_labels = [c.get("client", "?") or "?" for c in delay_data[:8]]
                delay_vals = [c.get("avg_payment_delay_days", 0) or 0 for c in delay_data[:8]]
                delay_colors = []
                for d in delay_vals:
                    if d <= 30:
                        delay_colors.append(COLOR_SUCCESS_DEFAULT)
                    elif d <= 45:
                        delay_colors.append(COLOR_WARNING_DEFAULT)
                    else:
                        delay_colors.append(COLOR_WARNING_TEXT)
                fig3 = make_bar_chart(
                    delay_labels, delay_vals,
                    title=t("analytics.client_payment_delay"), horizontal=True,
                    color=delay_colors, highlight_max=True,
                )
                fig3.add_vline(x=30, line={"color": COLOR_WARNING_DEFAULT, "width": 1.5, "dash": "dash"},
                               annotation_text=t("analytics.payment_target", default="Target 30d"),
                               annotation_position="top")
                pw3 = PlotlyChartWidget(min_height=180)
                pw3.set_figure(fig3)
                self._chart_layout.addWidget(pw3)

        # ── Revenue concentration + Growth row ───────────────────
        row2 = QWidget()
        row2_l = QHBoxLayout(row2)
        row2_l.setContentsMargins(0, 0, 0, 0)
        row2_l.setSpacing(8)
        if conc and len(conc) > 3:
            top3_rev = sum(c.get("revenue", 0) or 0 for c in conc[:3])
            rest_rev = sum(c.get("revenue", 0) or 0 for c in conc[3:])
            if top3_rev > 0 or rest_rev > 0:
                top_names = ", ".join(c.get("client", "") for c in conc[:3])
                top_names_display = top_names if len(top_names) <= 30 else top_names[:27] + "..."
                fig4 = make_pie_chart(
                    [top3_rev, rest_rev],
                    [f"{t('analytics.group_top3')}\n({top_names_display})",
                     t("analytics.client_rest")],
                    title=t("analytics.client_concentration"),
                )
                pw4 = PlotlyChartWidget()
                pw4.set_figure(fig4)
                row2_l.addWidget(pw4)
        if growth:
            growth_months = [self._fmt_month_label(g.get("month", "")) for g in growth]
            fig5 = make_trend_chart(
                growth_months,
                [g.get("new_clients", 0) or 0 for g in growth],
                title=t("analytics.client_growth"), color=CHART_ACCENT,
            )
            pw5 = PlotlyChartWidget(min_height=180)
            pw5.set_figure(fig5)
            row2_l.addWidget(pw5)
        if (conc and len(conc) > 3) or growth:
            self._chart_layout.addWidget(row2)

        # ── Styled Insight ───────────────────────────────────────
        if conc and len(conc) > 1:
            total_rev = sum(c.get("revenue", 0) or 0 for c in conc)
            total_profit_con = sum(c.get("profit", 0) or 0 for c in conc)
            if total_rev > 0:
                for c in conc[:5]:
                    rev_pct = ((c.get("revenue", 0) or 0) / total_rev) * 100
                    profit_pct = ((c.get("profit", 0) or 0) / max(total_profit_con, 1)) * 100
                    gap = abs(rev_pct - profit_pct)
                    if gap > 15:
                        client_name = c.get("client", "?")
                        insight_text = t("analytics.client_insight").format(
                            client=client_name,
                            rev_pct=f"{rev_pct:.0f}",
                            profit_pct=f"{profit_pct:.0f}",
                        )
                        is_negative = profit_pct < 0 or (profit_pct < rev_pct * 0.5)
                        self._build_insight_banner(insight_text, warning=is_negative)
                        break

        # ── Payment Behavior Timeline ───────────────────────────
        if clients:
            self._build_payment_timeline(clients)

    # ── KPI card builder ────────────────────────────────────────────

    @staticmethod
    def _make_client_kpi(
        label: str, value: str, value_color: str | None = None,
        multiline: bool = False,
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
        if multiline:
            val.setStyleSheet(val.styleSheet() + " line-height: 1.3;")
        card_layout.addWidget(val)
        return card

    # ── Insight banner ──────────────────────────────────────────────

    def _build_insight_banner(self, text: str, warning: bool = False) -> None:
        bg = COLOR_WARNING_SUBTLE if warning else COLOR_INFO_SUBTLE
        border = COLOR_WARNING_DEFAULT if warning else COLOR_INFO_DEFAULT
        icon_color = COLOR_WARNING_TEXT if warning else COLOR_INFO_TEXT

        banner = QFrame()
        banner.setStyleSheet(
            f"QFrame {{ background: {bg};"
            f" border-left: 3px solid {border};"
            f" border-radius: 4px; padding: 0px; }}"
        )
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        banner_layout.setSpacing(SP["2"])

        icon_lbl = QLabel("\U0001f4a1")
        icon_lbl.setStyleSheet(
            f"font-size: 14px; color: {icon_color}; background: transparent;"
        )
        banner_layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)

        text_lbl = QLabel(text)
        text_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;"
            f" font-family: '{FONT_FAMILY}'; background: transparent;"
            f" line-height: 1.4;"
        )
        text_lbl.setWordWrap(True)
        banner_layout.addWidget(text_lbl, 1)

        self._chart_layout.addWidget(banner)

    # ── Payment Behavior Timeline ──────────────────────────────────

    def _build_payment_timeline(self, clients: list) -> None:
        """Build a compact payment delay bar per client.

        Shows top 4 clients by payment delay with a colored bar
        proportional to their average delay (max 60 days).
        """

        self._chart_layout.addSpacing(SP["2"])
        self._add_section_header(
            t("analytics.section_payment_timeline", default="Payment Behavior"), ""
        )

        delay_clients = sorted(
            [c for c in clients if (c.get("avg_payment_delay_days") or 0) > 0],
            key=lambda c: c.get("avg_payment_delay_days", 0) or 0,
            reverse=True,
        )[:4]

        if not delay_clients:
            return

        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background: {COLOR_BG_ELEVATED};"
            f" border: 1px solid {COLOR_BG_OVERLAY}; border-radius: 6px; }}"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["2"])
        container_layout.setSpacing(SP["1"])

        max_delay = max(
            (c.get("avg_payment_delay_days", 0) or 0) for c in delay_clients
        )
        max_delay = max(max_delay, 1)

        for c in delay_clients:
            name = c.get("client", "?") or "?"
            days = c.get("avg_payment_delay_days", 0) or 0
            pct = min(days / max(max_delay, 1), 1.0)
            bar_width = int(pct * 160)

            if days <= 15:
                bar_color = COLOR_SUCCESS_DEFAULT
                icon = "\u2713"
            elif days <= 30:
                bar_color = COLOR_WARNING_DEFAULT
                icon = "\u26a0"
            else:
                bar_color = COLOR_ERROR_DEFAULT
                icon = "\u26d4"

            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SP["2"])

            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(110)
            name_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600;"
                f" font-family: '{FONT_FAMILY}'; background: transparent;"
            )
            row_layout.addWidget(name_lbl)

            bar = QFrame()
            bar.setFixedSize(bar_width, 16)
            bar.setStyleSheet(
                f"QFrame {{ background: {bar_color}; border-radius: 3px; }}"
            )
            row_layout.addWidget(bar)

            if bar_width < 160:
                row_layout.addStretch()

            icon_lbl = QLabel(f"{icon} {days:.0f}d")
            icon_lbl.setStyleSheet(
                f"color: {bar_color}; font-size: 11px; font-weight: 600;"
                f" font-family: '{FONT_FAMILY}'; background: transparent;"
            )
            row_layout.addWidget(icon_lbl)

            container_layout.addWidget(row)

        self._chart_layout.addWidget(container)
