"""PySide6 maintenance analytics view — charts and table.

Replaces ``ui/views/maintenance_analytics_view.py``. Uses
``FleetMaintenanceService`` and ``FleetRepository`` for data,
Matplotlib via ``FigureCanvasQTAgg`` for charts.

Usage as embedded widget::

    view = QtMaintenanceAnalyticsView(parent_widget, db)

Usage as standalone dialog (windowed mode)::

    from ui.views.maintenance_analytics_view import MaintenanceAnalyticsDialog

    dlg = MaintenanceAnalyticsDialog(db, parent=parent_widget)
    dlg.exec_()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
)

from repositories.fleet_repository import FleetRepository
from services.fleet_maintenance_service import (
    FleetMaintenanceService,
    MAINT_DISPLAY,
    MaintType,
)
from services.i18n import register_listener, t, unregister_listener
from ui.icons import iconed
from ui.theme import CHART_PALETTE, CHART_PRIMARY, CHART_SECONDARY, COLORS, S
from ui.widgets import ActionButton, StyledTableWidget

logger = logging.getLogger(__name__)

_MONTH_KEYS = [
    "maint_analytics.month_jan", "maint_analytics.month_feb",
    "maint_analytics.month_mar", "maint_analytics.month_apr",
    "maint_analytics.month_may", "maint_analytics.month_jun",
    "maint_analytics.month_jul", "maint_analytics.month_aug",
    "maint_analytics.month_sep", "maint_analytics.month_oct",
    "maint_analytics.month_nov", "maint_analytics.month_dec",
]
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _label_month(ym: str) -> str:
    """Format a ``YYYY-MM`` string as a localized month label (e.g. ``Jan 24``)."""
    try:
        parts = ym.split("-")
        m = int(parts[1])
        return f"{t(_MONTH_KEYS[m - 1], default=_MONTH_NAMES[m - 1])} {parts[0][2:]}"
    except Exception:
        return ym


class QtMaintenanceAnalyticsView(QWidget):
    """Maintenance analytics view with two charts and a summary table.

    Charts show cost-per-truck-month (grouped bar) and fleet cost trend
    (line with fill). The table shows YTD cost, average cost, service
    count, and top category per truck.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
    ):
        super().__init__(parent)
        self.db = db
        self.repo = FleetRepository(db) if db else None
        self.service = FleetMaintenanceService(db) if db else None

        self._fig = None
        self._canvas = None
        self._table_ref = None
        self._i18n_widgets: List[tuple] = []
        self._chart_texts: List[tuple] = []
        self._shutting_down = False

        # Data stores populated by _load_data()
        self._truck_map: Dict[int, str] = {}
        self._cost_by_truck_month: List[Dict[str, Any]] = []
        self._cost_by_month: List[Dict[str, Any]] = []
        self._truck_summary: List[Dict[str, Any]] = []
        self._top_categories: List[Dict[str, Any]] = []

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        QTimer.singleShot(0, self._load_data)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["6"], S["4"], S["6"], S["4"])
        layout.setSpacing(S["4"])

        self._build_header(layout)
        self._build_chart_area(layout)
        self._build_table_area(layout)

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setProperty("role", "section-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self._title_lbl = QLabel(iconed("maint_analytics.title"))
        self._title_lbl.setProperty("fontRole", "h2")
        header_layout.addWidget(self._title_lbl)
        self._i18n_widgets.append((self._title_lbl, "maint_analytics.title", ""))

        header_layout.addStretch(1)

        self._refresh_btn = ActionButton(
            header,
            iconed("maint.refresh"),
            self._load_data,
            variant="primary",
        )
        header_layout.addWidget(self._refresh_btn)
        self._i18n_widgets.append((self._refresh_btn, "maint.refresh", ""))

        layout.addWidget(header)

    def _build_chart_area(self, layout: QVBoxLayout) -> None:
        self._chart_frame = QFrame()
        self._chart_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chart_frame.setMinimumHeight(350)
        self._chart_layout = QVBoxLayout(self._chart_frame)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._chart_frame, 3)

    def _build_table_area(self, layout: QVBoxLayout) -> None:
        self._table_frame = QFrame()
        self._table_frame.setMinimumHeight(200)
        table_layout = QVBoxLayout(self._table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table_frame, 2)

    # ── Data loading ───────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload data and re-render all charts and the table."""
        self._load_data()

    def _load_data(self) -> None:
        if getattr(self, "_shutting_down", False):
            return
        try:
            self.isVisible()
        except RuntimeError:
            return
        if self.repo is None or self.service is None:
            return

        now = datetime.now()
        twelve_ago = now - timedelta(days=365)
        ytd_start = datetime(now.year, 1, 1)

        since_charts = twelve_ago.strftime("%Y-%m-%d")
        since_ytd = ytd_start.strftime("%Y-%m-%d")

        self._truck_map: Dict[int, str] = {}
        for rec in self.repo.get_all():
            self._truck_map[rec["id"]] = rec.get(
                "plate_number",
                iconed("maint_analytics.truck_fallback", rec["id"]),
            )

        self._cost_by_truck_month = self.repo.get_maintenance_cost_truck_monthly(
            since_charts
        )
        self._cost_by_month = self.repo.get_maintenance_cost_monthly(since_charts)
        self._truck_summary = self.repo.get_maintenance_truck_summary(since_ytd)
        self._top_categories = self.repo.get_maintenance_most_expensive_category(
            since_ytd
        )

        self._render_charts()
        self._render_table()

    # ── Chart rendering ────────────────────────────────────────────────────────

    def _render_charts(self) -> None:
        """Clear existing chart widgets and re-render both charts."""
        # Close previous figure to free memory
        if self._fig is not None:
            plt.close(self._fig)
            self._fig = None
            self._canvas = None
        self._clear_layout(self._chart_layout)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
        fig.patch.set_facecolor(COLORS["bg_base"])
        for ax in (ax1, ax2):
            ax.set_facecolor(COLORS["bg_base"])
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=9)
            ax.xaxis.label.set_color(COLORS["text_secondary"])
            ax.yaxis.label.set_color(COLORS["text_secondary"])
            ax.title.set_color(COLORS["text_primary"])
            for spine in ax.spines.values():
                spine.set_edgecolor(COLORS["border"])

        self._chart_texts = []
        self._draw_cost_by_truck_month(ax1)
        self._draw_fleet_trend(ax2)

        fig.tight_layout(pad=3)
        canvas = FigureCanvas(fig)
        self._chart_layout.addWidget(canvas)
        self._fig = fig
        self._canvas = canvas

    def _draw_cost_by_truck_month(self, ax) -> None:
        """Grouped bar chart: cost per truck, per month (12-month view)."""
        title = ax.set_title(
            iconed("maint_analytics.chart_cost_per_truck"),
            color=COLORS["text_primary"],
            fontsize=10,
        )
        self._chart_texts.append((title, "maint_analytics.chart_cost_per_truck"))

        if not self._cost_by_truck_month:
            ax.text(
                0.5, 0.5, iconed("maint_analytics.no_records"),
                color=COLORS["text_muted"],
                ha="center", va="center", transform=ax.transAxes,
            )
            return

        months = sorted(set(r["ym"] for r in self._cost_by_truck_month))
        truck_ids = sorted(set(r["truck_id"] for r in self._cost_by_truck_month))

        lookup: Dict[tuple, float] = {}
        for r in self._cost_by_truck_month:
            lookup[(r["truck_id"], r["ym"])] = r["total"]

        x = list(range(len(months)))
        n = len(truck_ids)
        w = 0.8 / n

        for i, tid in enumerate(truck_ids):
            vals = [lookup.get((tid, m), 0) for m in months]
            color = CHART_PALETTE[i % len(CHART_PALETTE)]
            label = self._truck_map.get(
                tid, iconed("maint_analytics.truck_fallback", tid)
            )
            ax.bar(
                [xi + i * w - 0.4 + w / 2 for xi in x],
                vals,
                w,
                label=label,
                color=color,
                edgecolor=COLORS["bg_base"],
                linewidth=0.5,
            )

        ax.set_xticks(x)
        ax.set_xticklabels(
            [_label_month(m) for m in months],
            rotation=45, ha="right", fontsize=7,
        )
        ax.set_ylabel(
            iconed("maint_analytics.cost_label"),
            color=COLORS["text_muted"],
            fontsize=8,
        )
        ax.legend(
            fontsize=6,
            facecolor=COLORS["bg_surface"],
            labelcolor=COLORS["text_primary"],
            edgecolor=COLORS["border"],
        )

    def _draw_fleet_trend(self, ax) -> None:
        """Line chart: total fleet maintenance cost per month (12-month trend)."""
        title = ax.set_title(
            iconed("maint_analytics.chart_fleet_trend"),
            color=COLORS["text_primary"],
            fontsize=10,
        )
        self._chart_texts.append((title, "maint_analytics.chart_fleet_trend"))

        if not self._cost_by_month:
            ax.text(
                0.5, 0.5, iconed("maint_analytics.no_data_12mo"),
                color=COLORS["text_muted"],
                ha="center", va="center", transform=ax.transAxes,
            )
            return

        months = [r["ym"] for r in self._cost_by_month]
        totals = [r["total"] for r in self._cost_by_month]

        ax.plot(
            range(len(months)),
            totals,
            marker="o",
            color=CHART_PRIMARY,
            linewidth=2,
            markersize=5,
            markerfacecolor=CHART_SECONDARY,
            markeredgecolor="none",
        )
        ax.fill_between(
            range(len(months)),
            totals,
            alpha=0.12,
            color=CHART_PRIMARY,
        )

        ax.set_xticks(range(len(months)))
        ax.set_xticklabels(
            [_label_month(m) for m in months],
            rotation=45, ha="right", fontsize=7,
        )
        ax.set_ylabel(
            iconed("maint_analytics.total_cost_label"),
            color=COLORS["text_muted"],
            fontsize=8,
        )
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"\u20AC{v:,.0f}")
        )

    # ── Table rendering ────────────────────────────────────────────────────────

    def _render_table(self) -> None:
        """Build or rebuild the StyledTableWidget with truck summary data."""
        self._clear_layout(self._table_frame.layout())
        self._table_ref = None

        top_cat_map: Dict[int, str] = {}
        for r in self._top_categories:
            raw = r.get("maintenance_type", "")
            try:
                disp = MAINT_DISPLAY.get(
                    MaintType(raw), raw.replace("_", " ").title()
                )
            except ValueError:
                disp = raw.replace("_", " ").title()
            top_cat_map[r["truck_id"]] = disp

        columns = [
            ("truck", t("maint_analytics.col_truck", default="Truck"), 120),
            ("ytd_cost", t("maint_analytics.col_ytd_cost", default="YTD Cost"), 140),
            ("avg_cost", t("maint_analytics.col_avg_cost", default="Avg. Cost"), 140),
            ("count", t("maint_analytics.col_count", default="Services"), 100),
            (
                "top_category",
                t("maint_analytics.col_top_category", default="Top Category"),
                180,
            ),
        ]

        table = StyledTableWidget(self._table_frame, columns)
        table.setMinimumHeight(200)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        if not self._truck_summary:
            table.set_data(
                [
                    {
                        "truck": iconed("maint_analytics.no_data"),
                        "ytd_cost": "",
                        "avg_cost": "",
                        "count": "",
                        "top_category": "",
                    }
                ]
            )
        else:
            rows = []
            for r in self._truck_summary:
                tid = r["truck_id"]
                plate = self._truck_map.get(
                    tid, iconed("maint_analytics.truck_fallback", tid)
                )
                rows.append(
                    {
                        "truck": plate,
                        "ytd_cost": f"\u20AC{r['total_ytd']:,.2f}",
                        "avg_cost": f"\u20AC{r['avg_cost']:,.2f}",
                        "count": str(r["service_count"]),
                        "top_category": top_cat_map.get(tid, "\u2014"),
                    }
                )
            table.set_data(rows)

        self._table_frame.layout().addWidget(table)
        self._table_ref = table

    # ── i18n ───────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        """Schedule a translation refresh on the next event-loop tick."""
        QTimer.singleShot(0, self._refresh_translations)

    def _refresh_translations(self) -> None:
        """Update widget text and reload data after a language change."""
        self._title_lbl.setText(iconed("maint_analytics.title"))
        self._refresh_btn.setText(iconed("maint.refresh"))

        for text_obj, key in self._chart_texts:
            try:
                text_obj.set_text(
                    iconed(key)
                    if key.startswith("maint")
                    else t(key)
                )
            except Exception:
                pass

        self._load_data()

    # ── Helpers ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _clear_layout(layout) -> None:
        """Remove and schedule deletion of every widget in *layout*."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Re-fetch data when the view becomes visible again."""
        self._load_data()

    def shutdown(self) -> None:
        """Clean up i18n listener and matplotlib figure."""
        self._shutting_down = True
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass

        if self._fig is not None:
            try:
                plt.close(self._fig)
            except Exception:
                pass
            self._fig = None
            self._canvas = None


class MaintenanceAnalyticsDialog(QDialog):
    """Standalone windowed mode for maintenance analytics."""

    def __init__(
        self,
        db=None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(iconed("maint_analytics.title"))
        self.setMinimumSize(1400, 850)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = QtMaintenanceAnalyticsView(self, db)
        layout.addWidget(self._view)

    def wakeup(self) -> None:
        self._view.wakeup()

    def shutdown(self) -> None:
        self._view.shutdown()
