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

from services.fleet_maintenance_service import MAINT_DISPLAY, MaintType
from services.i18n import register_listener, t, unregister_listener
from ui.components import Btn, Card, EmptyState, IconButton, Label, PageTitle
from ui.mode_guard import ConnectionMode, detect_mode, guard_local_access
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

    def __init__(self, parent=None, db=None, repo=None):
        super().__init__(parent)
        self.db = db
        self.repo = repo
        if self.repo is None and self.db is not None:
            from repositories.fleet_repository import FleetRepository
            self.repo = FleetRepository(db=self.db)
        elif self.repo is None and self.db is None:
            logger.warning("MaintenanceAnalyticsView: no local database - repository operations disabled in remote mode")

        # ── Mode guard ───────────────────────────────────────────────────────
        self._mode = detect_mode(db, None)  # no api_client — local-only view
        guard_local_access(self._mode, "Maintenance analytics")

        # ── Grid toggle state ────────────────────────────────────────────────
        self._grid_visible = True

        # Chart widgets (created once, re-used)
        self._chart_widget_a = None
        self._chart_widget_b = None
        self._chart_placeholder_a = None
        self._chart_placeholder_b = None
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
        self._empty_state_shown = False
        self._vm.data_changed.connect(self._on_data_changed)

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        QTimer.singleShot(0, self, self._load_data)

    # ── UI Build ─────────────────────────────────────────────────

    def _build_ui(self):
        self.setAccessibleName("Maintenance analytics")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["6"])

        self._build_view_header(layout)

        self._empty_state = EmptyState(
            self,
            icon_name="fa5s.wrench",
            title=t("maint_analytics.empty_title", default="No maintenance records"),
            subtitle=t("maint_analytics.empty_desc", default="Schedule your first service to see maintenance analytics."),
            cta_button=Btn(
                self,
                text=t("maint_analytics.schedule_service", default="Schedule Your First Service"),
                variant="primary",
            ),
        )
        self._empty_state.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._empty_state.hide()
        layout.addWidget(self._empty_state)

        self._chart_card = None
        self._table_card_area = None

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

        self._refresh_btn = Btn(header, iconed("maint.refresh"), variant="primary", command=self.refresh)
        hl.addWidget(self._refresh_btn)
        self._i18n_widgets.append((self._refresh_btn, "maint.refresh", ""))

        # ── Grid toggle button ──────────────────────────────────────
        self._grid_btn = IconButton(
            header,
            icon_name="fa5s.th",
            tooltip=t("chart.toggle_grid", "Toggle grid"),
            variant="ghost",
            command=self._toggle_grid,
        )
        hl.addWidget(self._grid_btn)

        layout.addWidget(header)

    def _build_chart_area(self, layout):
        chart_card = Card()
        chart_card.setMinimumHeight(350)
        frame = QFrame()
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QHBoxLayout(frame)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(SP["3"])

        # Placeholder frames — real PlotlyChartWidget created lazily in _render_charts
        self._chart_placeholder_a = QFrame()
        self._chart_placeholder_a.setMinimumHeight(300)
        self._chart_placeholder_a.setStyleSheet("background: #1C1C1F; border-radius: 6px;")
        self._chart_placeholder_b = QFrame()
        self._chart_placeholder_b.setMinimumHeight(300)
        self._chart_placeholder_b.setStyleSheet("background: #1C1C1F; border-radius: 6px;")
        cl.addWidget(self._chart_placeholder_a, 1)
        cl.addWidget(self._chart_placeholder_b, 1)

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
        self._data_loaded = False  # Force re-load on explicit refresh
        self._load_data()

    def _load_data(self):
        if self._shutting_down:
            return
        if self.repo is None:
            return
        if self._data_loaded:
            logger.debug("MaintenanceAnalyticsView: data already loaded, skipping re-load")
            return

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

        # Show empty state when no maintenance data exists
        has_data = bool(self._cost_by_truck_month or self._cost_by_month or self._truck_summary)
        if has_data and self._empty_state_shown:
            self._empty_state.hide()
            if self._chart_card:
                self._chart_card.show()
            if self._table_card_area:
                self._table_card_area.show()
            self._empty_state_shown = False
        elif not has_data and not self._empty_state_shown:
            self._empty_state.show()
            if self._chart_card:
                self._chart_card.hide()
            if self._table_card_area:
                self._table_card_area.hide()
            self._empty_state_shown = True
        elif has_data:
            self._empty_state.hide()
            if self._chart_card:
                self._chart_card.show()
            if self._table_card_area:
                self._table_card_area.show()

    def _on_data_changed(self):
        """ViewModel signals data change — re-render charts and table."""
        if self._shutting_down:
            return
        self._render_charts()
        self._render_table()

    # ── Chart rendering (reuses existing widgets) ────────────────

    def _render_charts(self):
        # Lazy creation: replace placeholders with real PlotlyChartWidget on first render
        if self._chart_widget_a is None and self._chart_placeholder_a is not None:
            from ui.plotly_renderer import PlotlyChartWidget
            self._chart_widget_a = PlotlyChartWidget(min_height=300)
            layout = self._chart_placeholder_a.parent().layout()
            idx = layout.indexOf(self._chart_placeholder_a)
            layout.insertWidget(idx, self._chart_widget_a)
            self._chart_placeholder_a.deleteLater()
            self._chart_placeholder_a = None
            self._i18n_widgets.append((self._chart_widget_a, "maint_analytics.chart_cost_per_truck", "cost_per_truck"))

        if self._chart_widget_b is None and self._chart_placeholder_b is not None:
            from ui.plotly_renderer import PlotlyChartWidget
            self._chart_widget_b = PlotlyChartWidget(min_height=300)
            layout = self._chart_placeholder_b.parent().layout()
            idx = layout.indexOf(self._chart_placeholder_b)
            layout.insertWidget(idx, self._chart_widget_b)
            self._chart_placeholder_b.deleteLater()
            self._chart_placeholder_b = None
            self._i18n_widgets.append((self._chart_widget_b, "maint_analytics.chart_fleet_trend", "fleet_trend"))

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
        if self._table_container is None:
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
        # Re-render charts and table so translated labels are picked up.
        # Data reload is not needed — the ViewModel already has fresh data.
        self._render_charts()
        self._render_table()

    # ── Grid toggle ────────────────────────────────────────────

    def _toggle_grid(self) -> None:
        """Toggle grid lines on all charts in this view."""
        self._grid_visible = not self._grid_visible
        for chart in self.findChildren(PlotlyChartWidget):
            try:
                chart.fig.update_xaxes(showgrid=self._grid_visible)
                chart.fig.update_yaxes(showgrid=self._grid_visible)
                chart.render()
            except Exception:
                logger.exception("Failed to toggle grid on chart widget")

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
