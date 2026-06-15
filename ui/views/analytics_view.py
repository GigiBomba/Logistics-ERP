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
from ui.charts import (
    apply_dark_style, apply_global_empty, apply_empty_state,
    make_bar_chart, make_line_chart, make_pie_chart,
    CHART_ACCENT, CHART_SECONDARY,
)

logger = logging.getLogger(__name__)


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

        # data is a 3-tuple from db.get_analytics_data():
        #   data[0] = per_truck:  [{"truck_number": str, "p": float}, ...]
        #   data[1] = per_driver: [{"driver_name": str, "p": float}, ...]
        #   data[2] = rev_exp:    [{"month": str, "rev": float, "exp": float}, ...]
        per_truck = data[0] if len(data) > 0 else []
        per_driver = data[1] if len(data) > 1 else []
        rev_exp_data = data[2] if len(data) > 2 else []

        fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=90)
        fig.subplots_adjust(hspace=0.45, wspace=0.35)

        if not data or len(data) == 0:
            apply_global_empty(fig, t("common.no_data"))
            return

        self._chart_texts = []

        # Chart 1: Top Trucks (bar)
        names = []
        profits = []
        if per_truck:
            top = sorted(per_truck, key=lambda t: t.get("p", 0), reverse=True)[:8]
            names = [t.get("truck_number", "?") for t in top]
            profits = [t.get("p", 0) for t in top]
        make_bar_chart(
            fig, axes[0, 0], names, profits,
            title=t("analytics.top_trucks_title"),
            color=CHART_ACCENT, highlight_max=True,
            empty_message=t("common.no_data"),
        )
        self._chart_texts.append((axes[0, 0], "analytics.top_trucks_title"))

        # Chart 2: Revenue vs Expenses (line)
        months = [r["month"] for r in rev_exp_data] if rev_exp_data else []
        revenue = [r["rev"] for r in rev_exp_data] if rev_exp_data else []
        expenses = [r["exp"] for r in rev_exp_data] if rev_exp_data else []
        # Reverse to chronological order (DB returns DESC, we reversed already, so this is ascending)
        if months and len(months) > 1 and months[0] > months[-1]:
            months.reverse()
            revenue.reverse()
            expenses.reverse()
        make_line_chart(
            fig, axes[0, 1], months,
            [(revenue, t("analytics.revenue_label"), CHART_ACCENT),
             (expenses, t("analytics.expenses_label"), CHART_SECONDARY)],
            title=t("analytics.revenue_expenses_title"),
            empty_message=t("common.no_data"),
        )
        self._chart_texts.append((axes[0, 1], "analytics.revenue_expenses_title"))

        # Chart 3: Profit per Driver (bar)
        dnames = []
        dprofits = []
        if per_driver:
            top_d = sorted(per_driver, key=lambda d: d.get("p", 0), reverse=True)[:8]
            dnames = [d.get("driver_name", "?") for d in top_d]
            dprofits = [d.get("p", 0) for d in top_d]
        make_bar_chart(
            fig, axes[1, 0], dnames, dprofits,
            title=t("analytics.driver_profit_title"),
            color=CHART_ACCENT, horizontal=False, highlight_max=True,
            empty_message=t("common.no_data"),
        )
        self._chart_texts.append((axes[1, 0], "analytics.driver_profit_title"))

        # Chart 4: Profit/Expenses Ratio (pie)
        total_profit = sum(abs(t.get("p", 0)) for t in per_truck) if per_truck else 0
        total_exp = sum(expenses) if expenses else 0
        make_pie_chart(
            fig, axes[1, 1],
            [total_profit, total_exp],
            [t("analytics.profit_label"), t("analytics.expenses_label")],
            title=t("analytics.profit_ratio_title"),
            empty_message=t("common.no_data"),
        )
        self._chart_texts.append((axes[1, 1], "analytics.profit_ratio_title"))

        fig.tight_layout(pad=2.0)

        canvas = FigureCanvas(fig)
        self._chart_container.layout().addWidget(canvas)

        self._fig = fig
        self._axes = axes

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self._refresh_translations)

    def _refresh_translations(self) -> None:
        from ui.design_tokens import TEXT_SECONDARY
        for ax, key in self._chart_texts:
            try:
                ax.set_title(t(key), color=TEXT_SECONDARY, fontsize=10)
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
