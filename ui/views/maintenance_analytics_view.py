"""PySide6 maintenance analytics view — charts and table.

Refactored to:
- Check dirty flag before reloading (skips redundant queries)
- Use setData() on existing StyledTableWidget instead of rebuild
- Share MaintenanceViewModel for data access
"""
from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from repositories.fleet_repository import FleetRepository
from services.fleet_maintenance_service import MAINT_DISPLAY, MaintType
from services.i18n import register_listener, t, unregister_listener
from ui.components import Btn, Card, Label, PageTitle
from ui.design_tokens import SP
from ui.icons import iconed
from ui.models.maintenance_view_model import MaintenanceViewModel
from ui.plotly_charts import CHART_ACCENT, make_grouped_bar_chart, make_trend_chart
from ui.plotly_renderer import PlotlyChartWidget, empty_figure
from ui.widgets import StyledTableWidget
from ui.widgets.layout_utils import clear_layout

_TRUCK_PALETTE = (
    "#6366f1", "#22c55e", "#f59e0b", "#ef4444",
    "#3b82f6", "#a855f7", "#06b6d4", "#ec4899",
)

logger = logging.getLogger(__name__)

_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _label_month(ym: str) -> str:
    try:
        parts = ym.split("-")
        m = int(parts[1])
        return f"{_MONTH_NAMES[m - 1]} {parts[0][2:]}"
    except Exception:
        return ym


class QtMaintenanceAnalyticsView(QWidget):
    """Maintenance analytics with charts and summary table.

    Re-renders only when the ViewModel signals data_changed.
    Chart/table widgets persist across refreshes (no rebuild).
    """

    def __init__(self, parent=None, db=None, api_client=None):
        super().__init__(parent)
        self.db = db
        self._api_client = api_client
        if self._api_client is not None:
            from client.remote_maintenance import RemoteMaintenanceService
            self.repo = RemoteMaintenanceService(self._api_client)
        else:
            self.repo = FleetRepository(db) if db else None

        # Chart widgets (created once, re-used)
        self._chart_widget_a: PlotlyChartWidget | None = None
        self._chart_widget_b: PlotlyChartWidget | None = None
        self._table_ref: StyledTableWidget | None = None
        self._table_container: QFrame | None = None
        self._i18n_widgets: list[tuple] = []
        self._shutting_down = False

        # Data stores
        self._truck_map: dict[int, str] = {}
        self._cost_by_truck_month: list[dict[str, Any]] = []
        self._cost_by_month: list[dict[str, Any]] = []
        self._truck_summary: list[dict[str, Any]] = []
        self._top_categories: list[dict[str, Any]] = []
        self._data_loaded = False

        # ViewModel
        self._vm = MaintenanceViewModel(self, db=db)

        self._build_ui()
        self._vm.data_changed.connect(self._on_data_changed)

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        QTimer.singleShot(0, self._load_data)

    # ── UI Build ─────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["6"])

        self._build_view_header(layout)
        self._build_chart_area(layout)
        self._build_table_area(layout)

    def _build_view_header(self, layout):
        header = QWidget()
        header.setFixedHeight(72)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(SP["10"], 0, SP["10"], 0)

        self._title_lbl = PageTitle(header, iconed("maint_analytics.title"))
        hl.addWidget(self._title_lbl)
        self._i18n_widgets.append((self._title_lbl, "maint_analytics.title", ""))

        subtitle = Label(header, t("maint_analytics.subtitle", default=""), role="secondary")
        hl.addWidget(subtitle)
        hl.addStretch(1)

        self._refresh_btn = Btn(header, iconed("maint.refresh"), variant="primary", command=self._load_data)
        hl.addWidget(self._refresh_btn)
        self._i18n_widgets.append((self._refresh_btn, "maint.refresh", ""))

        layout.addWidget(header)

    def _build_chart_area(self, layout):
        chart_card = Card()
        chart_card.setMinimumHeight(350)
        frame = QFrame()
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QHBoxLayout(frame)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(SP["3"])

        self._chart_widget_a = PlotlyChartWidget(min_height=300)
        self._chart_widget_b = PlotlyChartWidget(min_height=300)
        cl.addWidget(self._chart_widget_a, 1)
        cl.addWidget(self._chart_widget_b, 1)
        self._i18n_widgets.append((self._chart_widget_a, "maint_analytics.chart_cost_per_truck", "cost_per_truck"))
        self._i18n_widgets.append((self._chart_widget_b, "maint_analytics.chart_fleet_trend", "fleet_trend"))

        chart_card.layout().addWidget(frame)
        layout.addWidget(chart_card, 3)

    def _build_table_area(self, layout):
        table_card = Card()
        self._table_container = QFrame()
        self._table_container.setMinimumHeight(200)
        tl = QVBoxLayout(self._table_container)
        tl.setContentsMargins(0, 0, 0, 0)
        table_card.layout().addWidget(self._table_container)
        layout.addWidget(table_card, 2)

    # ── Data loading (dirty-flag aware) ──────────────────────────

    def refresh(self):
        self._load_data()

    def _load_data(self):
        if self._shutting_down:
            return
        if self.repo is None:
            return

        if self._data_loaded:
            return  # Already loaded — ViewModel drives updates

        now = datetime.now()
        twelve_ago = now - timedelta(days=365)
        ytd_start = datetime(now.year, 1, 1)
        since_charts = twelve_ago.strftime("%Y-%m-%d")
        since_ytd = ytd_start.strftime("%Y-%m-%d")

        try:
            self._truck_map = {
                rec["id"]: rec.get("plate_number", iconed("maint_analytics.truck_fallback", rec["id"]))
                for rec in self.repo.get_all()
            }

            self._cost_by_truck_month = self.repo.get_maintenance_cost_truck_monthly(since_charts)
            self._cost_by_month = self.repo.get_maintenance_cost_monthly(since_charts)
            self._truck_summary = self.repo.get_maintenance_truck_summary(since_ytd)
            self._top_categories = self.repo.get_maintenance_most_expensive_category(since_ytd)
            self._data_loaded = True
        except Exception:
            logger.exception("Failed to load analytics data")

        self._render_charts()
        self._render_table()

    def _on_data_changed(self):
        """ViewModel signals data change — re-render charts and table."""
        if self._shutting_down:
            return
        self._render_charts()
        self._render_table()

    # ── Chart rendering (reuses existing widgets) ────────────────

    def _render_charts(self):
        if self._chart_widget_a is None or self._chart_widget_b is None:
            return
        try:
            self._chart_widget_a.set_figure(self._build_cost_by_truck_month_fig())
        except Exception:
            logger.exception("Cost-by-truck-month chart render failed")
            self._chart_widget_a.set_figure(empty_figure(t("maint_analytics.no_records")))

        try:
            self._chart_widget_b.set_figure(self._build_fleet_trend_fig())
        except Exception:
            logger.exception("Fleet trend chart render failed")
            self._chart_widget_b.set_figure(empty_figure(t("maint_analytics.no_data_12mo")))

    def _build_cost_by_truck_month_fig(self):
        if not self._cost_by_truck_month:
            return empty_figure(t("maint_analytics.no_records"))

        months = sorted({r["ym"] for r in self._cost_by_truck_month})
        truck_ids = sorted({r["truck_id"] for r in self._cost_by_truck_month})
        lookup = {(r["truck_id"], r["ym"]): r["total"] for r in self._cost_by_truck_month}
        x_labels = [_label_month(m) for m in months]

        groups = []
        for i, tid in enumerate(truck_ids):
            color = _TRUCK_PALETTE[i % len(_TRUCK_PALETTE)]
            label = self._truck_map.get(tid, str(tid))
            groups.append((label, [lookup.get((tid, m), 0) for m in months], color))

        fig = make_grouped_bar_chart(x_labels, groups,
                                     title=t("maint_analytics.chart_cost_per_truck"),
                                     horizontal=False, is_currency=True, show_title=True)
        fig.update_xaxes(tickangle=-45, tickfont={"size": 9})
        return fig

    def _build_fleet_trend_fig(self):
        if not self._cost_by_month:
            return empty_figure(t("maint_analytics.no_data_12mo"))

        months = [r["ym"] for r in self._cost_by_month]
        totals = [r["total"] for r in self._cost_by_month]

        fig = make_trend_chart([_label_month(m) for m in months], totals,
                               title=t("maint_analytics.chart_fleet_trend"),
                               color=CHART_ACCENT, is_currency=True, show_title=True)
        fig.update_xaxes(tickangle=-45, tickfont={"size": 9})
        return fig

    # ── Table rendering (setData on existing widget) ─────────────

    def _render_table(self):
        if self._table_container is None or self.repo is None:
            return

        top_cat_map: dict[int, str] = {}
        for r in self._top_categories:
            raw = r.get("maintenance_type", "")
            try:
                disp = MAINT_DISPLAY.get(MaintType(raw), raw.replace("_", " ").title())
            except ValueError:
                disp = raw.replace("_", " ").title()
            top_cat_map[r["truck_id"]] = disp

        columns = [
            ("truck", t("maint_analytics.col_truck", default="Truck"), 120),
            ("ytd_cost", t("maint_analytics.col_ytd_cost", default="YTD Cost"), 140),
            ("avg_cost", t("maint_analytics.col_avg_cost", default="Avg. Cost"), 140),
            ("count", t("maint_analytics.col_count", default="Services"), 100),
            ("top_category", t("maint_analytics.col_top_category", default="Top Category"), 180),
        ]

        if self._table_ref is None:
            # Create once
            clear_layout(self._table_container.layout())
            self._table_ref = StyledTableWidget(self._table_container, columns)
            self._table_ref.setMinimumHeight(200)
            self._table_ref.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._table_container.layout().addWidget(self._table_ref)

        if not self._truck_summary:
            self._table_ref.set_data([{
                "truck": iconed("maint_analytics.no_data"),
                "ytd_cost": "", "avg_cost": "", "count": "", "top_category": "",
            }])
        else:
            rows = []
            for r in self._truck_summary:
                tid = r["truck_id"]
                plate = self._truck_map.get(tid, str(tid))
                rows.append({
                    "truck": plate,
                    "ytd_cost": f"\u20ac{r['total_ytd']:,.2f}",
                    "avg_cost": f"\u20ac{r['avg_cost']:,.2f}",
                    "count": str(r["service_count"]),
                    "top_category": top_cat_map.get(tid, "\u2014"),
                })
            self._table_ref.set_data(rows)

    # ── i18n ─────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str):
        QTimer.singleShot(0, self._load_data)

    # ── Helpers ──────────────────────────────────────────────────

    def wakeup(self):
        self._load_data()

    def shutdown(self):
        self._shutting_down = True
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)


class MaintenanceAnalyticsDialog(QDialog):
    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(iconed("maint_analytics.title"))
        self.setMinimumSize(1400, 850)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._view = QtMaintenanceAnalyticsView(self, db)
        layout.addWidget(self._view)

    def wakeup(self):
        self._view.wakeup()

    def shutdown(self):
        self._view.shutdown()
