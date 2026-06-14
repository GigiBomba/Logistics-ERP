"""PySide6 analytics view — 4-chart dashboard with period controls.

Replaces ``ui/analytics_view.py``. Uses ``AnalyticsService`` and
``TripRepository`` for data, Matplotlib via ``FigureCanvasQTAgg`` for charts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QDate, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QDateEdit,
    QMessageBox,
    QSizePolicy,
)

from services.analytics_service import AnalyticsService
from services.i18n import t, register_listener, unregister_listener
from repositories.trip_repository import TripRepository
from ui.components import Card, Btn, Label, PageTitle, Divider
from ui.design_tokens import (
    BG_SURFACE, BORDER_DEFAULT, TEXT_MUTED, TEXT_SECONDARY, ACCENT, SP,
)

logger = logging.getLogger(__name__)

CHART_PRIMARY = ACCENT
CHART_SECONDARY = "#818cf8"


class QtAnalyticsView(QScrollArea):
    """Analytics dashboard with period controls and 2×2 chart grid."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs

        self.service = AnalyticsService(db) if db else None
        self._trip_repo = TripRepository(db) if db else None

        self._year = datetime.now().year
        self._month = datetime.now().month
        self._custom_from: Optional[str] = None
        self._custom_to: Optional[str] = None
        self._fig = None
        self._axes = None
        self._chart_texts: List[tuple] = []

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._load_data()

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["6"])

        self._build_view_header(layout)
        self._build_controls(layout)
        self._build_chart_area(layout)

        self.setWidget(container)

    def _build_view_header(self, layout: QVBoxLayout) -> None:
        header = QWidget()
        header.setFixedHeight(72)
        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)

        title = PageTitle(header, t("analytics.title"))
        hdr_layout.addWidget(title)

        subtitle = Label(header, t("analytics.subtitle", default=""), role="secondary")
        hdr_layout.addWidget(subtitle)

        hdr_layout.addStretch()
        layout.addWidget(header)

    def _build_controls(self, layout: QVBoxLayout) -> None:
        card = Card()
        card_layout = card.layout()
        card_layout.setContentsMargins(SP["4"], SP["2"], SP["4"], SP["2"])
        card_layout.setSpacing(SP["2"])

        bar_layout = QHBoxLayout()
        card_layout.addLayout(bar_layout)

        prev_btn = Btn(None, "\u25c0", variant="ghost", command=self._prev_month)
        prev_btn.setFixedSize(28, 28)
        bar_layout.addWidget(prev_btn)

        self._period_lbl = QLabel("")
        self._period_lbl.setProperty("fontRole", "h3")
        bar_layout.addWidget(self._period_lbl)

        next_btn = Btn(None, "\u25b6", variant="ghost", command=self._next_month)
        next_btn.setFixedSize(28, 28)
        bar_layout.addWidget(next_btn)

        sep = QLabel(" | ")
        sep.setStyleSheet(f"color: {TEXT_MUTED};")
        bar_layout.addWidget(sep)

        from_lbl = QLabel(t("analytics.from_label"))
        from_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        bar_layout.addWidget(from_lbl)

        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(QDate.currentDate())
        bar_layout.addWidget(self._from_date)

        to_lbl = QLabel(t("analytics.to_label"))
        to_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        bar_layout.addWidget(to_lbl)

        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(QDate.currentDate())
        bar_layout.addWidget(self._to_date)

        apply_btn = Btn(
            None, t("analytics.apply"), variant="primary", command=self._apply_custom,
        )
        bar_layout.addWidget(apply_btn)

        bar_layout.addStretch(1)
        card_layout.addStretch()
        layout.addWidget(card, 0)

        self._update_period_label()

    def _build_chart_area(self, layout: QVBoxLayout) -> None:
        chart_card = Card()
        chart_card.setMinimumHeight(400)
        chart_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chart_container = QFrame()
        self._chart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        clayout = QVBoxLayout(self._chart_container)
        clayout.setContentsMargins(0, 0, 0, 0)
        chart_card.layout().addWidget(self._chart_container)
        layout.addWidget(chart_card, 1)

    # ── Period navigation ──────────────────────────────────────────────────────

    def _update_period_label(self) -> None:
        month_name = datetime(self._year, self._month, 1).strftime("%B %Y")
        self._period_lbl.setText(month_name)

    def _prev_month(self) -> None:
        self._custom_from = None
        self._custom_to = None
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._update_period_label()
        self._load_data()

    def _next_month(self) -> None:
        self._custom_from = None
        self._custom_to = None
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._update_period_label()
        self._load_data()

    def _apply_custom(self) -> None:
        df = self._from_date.date()
        dt = self._to_date.date()
        if df > dt:
            QMessageBox.warning(self, t("analytics.error"), t("analytics.invalid_date_order"))
            return
        self._custom_from = df.toString("yyyy-MM-dd")
        self._custom_to = dt.toString("yyyy-MM-dd")
        self._period_lbl.setText(f"{self._custom_from} — {self._custom_to}")
        self._load_data()

    # ── Data loading & chart rendering ─────────────────────────────────────────

    def _load_data(self) -> None:
        if self.service is None:
            return

        from_d = self._custom_from or f"{self._year}-{self._month:02d}-01"
        if self._month == 12:
            to_d = self._custom_to or f"{self._year}-12-31"
        else:
            to_d = self._custom_to or f"{self._year}-{self._month + 1:02d}-01"
        data = self.service.get_data(from_d, to_d)

        self._render_charts(data)

    def _render_charts(self, data) -> None:
        import matplotlib
        matplotlib.use("QtAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        # Clear existing
        if self._fig:
            plt.close(self._fig)
        for w in self._chart_container.findChildren(QWidget):
            if w is not self._chart_container:
                w.deleteLater()

        rev_exp = data[3] if len(data) > 3 else ([], [], [])
        trucks = data[4] if len(data) > 4 else []
        drivers = data[5] if len(data) > 5 else []

        fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=90)

        # ── Empty state guard ──
        if not data or len(data) == 0:
            for ax in axes.flat:
                ax.set_visible(False)
                ax.set_axis_off()
            fig.patch.set_facecolor(BG_SURFACE)
            fig.text(0.5, 0.55, '\u2014',
                     ha='center', va='center',
                     fontsize=32, color=BORDER_DEFAULT,
                     fontfamily='Segoe UI')
            fig.text(0.5, 0.42, 'No data for this period',
                     ha='center', va='center',
                     fontsize=11, color=TEXT_MUTED,
                     fontfamily='Segoe UI')
            return

        fig.patch.set_facecolor(BG_SURFACE)

        self._chart_texts = []

        # ── Chart 1: Top Trucks (barh) ──
        ax1 = axes[0, 0]
        ax1.set_facecolor(BG_SURFACE)
        if trucks:
            top_trucks = sorted(trucks, key=lambda x: x[1] if len(x) > 1 else 0, reverse=True)[:8]
            names = [t[0] for t in top_trucks]
            profits = [abs(t[1] if len(t) > 1 else 0) for t in top_trucks]
            colors = [ACCENT] * len(names)
            if profits:
                max_idx = profits.index(max(profits))
                colors[max_idx] = CHART_SECONDARY
            ax1.barh(names, profits, color=colors)
        else:
            ax1.text(0.5, 0.5, t("common.no_data"), ha="center", va="center",
                     transform=ax1.transAxes, color=TEXT_MUTED)

        title1 = ax1.set_title(t("analytics.top_trucks_title"), color=TEXT_SECONDARY, fontsize=10)
        self._chart_texts.append((title1, "analytics.top_trucks_title"))
        ax1.tick_params(colors=TEXT_MUTED, labelsize=8)

        for spine in ax1.spines.values():
            spine.set_edgecolor(BORDER_DEFAULT)

        # ── Chart 2: Revenue vs Expenses (line) ──
        ax2 = axes[0, 1]
        ax2.set_facecolor(BG_SURFACE)
        revenue = rev_exp[1] if len(rev_exp) > 1 else []
        expenses = rev_exp[2] if len(rev_exp) > 2 else []
        months = rev_exp[0] if len(rev_exp) > 0 else []

        if months and revenue and expenses:
            idx = list(range(len(months)))
            ax2.plot(idx, revenue, color=ACCENT, label=t("analytics.revenue_label"), linewidth=2)
            ax2.fill_between(idx, 0, revenue, alpha=0.1, color=ACCENT)
            ax2.plot(idx, expenses, color=CHART_SECONDARY, label=t("analytics.expenses_label"), linewidth=2)
            ax2.fill_between(idx, 0, expenses, alpha=0.1, color=CHART_SECONDARY)
            ax2.set_xticks(idx)
            ax2.set_xticklabels(months, rotation=45, ha="right", fontsize=7)
            ax2.legend(loc="upper left", fontsize=7)
        else:
            ax2.text(0.5, 0.5, t("common.no_data"), ha="center", va="center",
                     transform=ax2.transAxes, color=TEXT_MUTED)

        title2 = ax2.set_title(
            t("analytics.revenue_expenses_title"), color=TEXT_SECONDARY, fontsize=10,
        )
        self._chart_texts.append((title2, "analytics.revenue_expenses_title"))
        ax2.tick_params(colors=TEXT_MUTED, labelsize=8)
        for spine in ax2.spines.values():
            spine.set_edgecolor(BORDER_DEFAULT)

        # ── Chart 3: Profit per Driver (bar) ──
        ax3 = axes[1, 0]
        ax3.set_facecolor(BG_SURFACE)
        if drivers:
            top_drivers = sorted(drivers, key=lambda x: x[1] if len(x) > 1 else 0, reverse=True)[:8]
            dnames = [d[0] for d in top_drivers]
            dprofits = [abs(d[1] if len(d) > 1 else 0) for d in top_drivers]
            colors_d = [ACCENT] * len(dnames)
            if dprofits:
                colors_d[dprofits.index(max(dprofits))] = CHART_SECONDARY
            ax3.bar(dnames, dprofits, color=colors_d)
            ax3.tick_params(axis="x", rotation=45, labelsize=7)
        else:
            ax3.text(0.5, 0.5, t("common.no_data"), ha="center", va="center",
                     transform=ax3.transAxes, color=TEXT_MUTED)

        title3 = ax3.set_title(
            t("analytics.driver_profit_title"), color=TEXT_SECONDARY, fontsize=10,
        )
        self._chart_texts.append((title3, "analytics.driver_profit_title"))
        ax3.tick_params(colors=TEXT_MUTED, labelsize=8)
        for spine in ax3.spines.values():
            spine.set_edgecolor(BORDER_DEFAULT)

        # ── Chart 4: Profit/Expenses Ratio (pie) ──
        ax4 = axes[1, 1]
        ax4.set_facecolor(BG_SURFACE)
        total_profit = sum(abs(t[1] if len(t) > 1 else 0) for t in trucks) if trucks else 0
        total_exp = sum(expenses) if expenses else 0
        if total_profit > 0 or total_exp > 0:
            sizes = [total_profit, total_exp]
            labels_pie = [t("analytics.profit_label"), t("analytics.expenses_label")]
            ax4.pie(sizes, labels=labels_pie, autopct="%1.0f%%",
                    colors=[ACCENT, CHART_SECONDARY],
                    textprops={"color": TEXT_SECONDARY, "fontsize": 8})
        else:
            ax4.text(0.5, 0.5, t("common.no_data"), ha="center", va="center",
                     transform=ax4.transAxes, color=TEXT_MUTED)

        title4 = ax4.set_title(t("analytics.profit_ratio_title"), color=TEXT_SECONDARY, fontsize=10)
        self._chart_texts.append((title4, "analytics.profit_ratio_title"))

        fig.tight_layout(pad=2.0)

        canvas = FigureCanvas(fig)
        self._chart_container.layout().addWidget(canvas)

        self._fig = fig
        self._axes = axes

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self._refresh_translations)

    def _refresh_translations(self) -> None:
        for text_obj, key in self._chart_texts:
            try:
                text_obj.set_text(t(key))
            except Exception:
                pass
        self._load_data()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        self._load_data()

    def shutdown(self) -> None:
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        if self._fig is not None:
            try:
                import matplotlib.pyplot as plt
                plt.close(self._fig)
            except Exception:
                pass
            self._fig = None
