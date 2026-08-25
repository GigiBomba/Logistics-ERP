"""Driver Analytics tab — Comparison table, activity timeline, tacho compliance."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QTableWidgetItem,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_TEXT,
    FONT_FAMILY,
    RADIUS_SM,
    SP,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WARNING_DIM,
    WARNING_TEXT,
)
from ui.plotly_charts import CHART_WARNING, make_bar_chart
from ui.plotly_renderer import PlotlyChartWidget
from ui.views.analytics._tab_base import BaseTab
from ui.widgets import StyledTableWidget


def _profit_km_color(ppm: float) -> str:
    """Return color for Profit/KM cell based on plan thresholds."""
    if ppm > 1.0:
        return COLOR_SUCCESS_DEFAULT
    if ppm >= 0.5:
        return COLOR_WARNING_DEFAULT
    return COLOR_ERROR_DEFAULT


class DriverAnalyticsTab(BaseTab):
    def __init__(self, parent=None, service=None):
        super().__init__(parent, service)
        self._build()

    def _build(self):
        self._add_header("analytics.tab_driver", "analytics.driver_subtitle")
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
        drivers_raw = self._svc.get_driver(from_date, to_date) or []
        comp_data = self._svc.get_driver_comparison(from_date, to_date) or []
        tacho = self._svc.get_driver_tacho_violations()
        monthly_activity = self._svc.get_driver_monthly_activity(
            self._months(), from_date, to_date
        ) or []
        if not drivers_raw and not comp_data:
            self._add_no_data(t("common.no_data"))
            return

        # ── Filter out Unassigned ────────────────────────────────
        drivers = [d for d in drivers_raw if str(d.get("driver", "")).strip().lower() != "unassigned"]
        unassigned_count = sum(
            1 for d in drivers_raw if str(d.get("driver", "")).strip().lower() == "unassigned"
        )
        unassigned_trips = sum(
            int(d.get("trip_count", 0) or 0)
            for d in drivers_raw
            if str(d.get("driver", "")).strip().lower() == "unassigned"
        )

        # ── KPI strip ────────────────────────────────────────────
        active_count = len(drivers)
        avg_trips = sum(d.get("trip_count", 0) or 0 for d in drivers) / max(active_count, 1)
        total_profit = sum(d.get("profit", 0) or 0 for d in drivers)
        avg_profit = total_profit / max(active_count, 1)

        kpi_row = QWidget()
        kpi_l = QHBoxLayout(kpi_row)
        kpi_l.setContentsMargins(0, 0, 0, 0)
        kpi_l.setSpacing(SP["4"])

        kpi_l.addWidget(self._make_driver_kpi(
            t("analytics.kpi_active_drivers", default="Active Drivers"),
            str(active_count),
            TEXT_PRIMARY,
        ))
        kpi_l.addWidget(self._make_driver_kpi(
            t("analytics.kpi_avg_trips_per_driver", default="Avg Trips/Driver"),
            f"{avg_trips:.1f}",
            TEXT_PRIMARY,
        ))
        kpi_l.addWidget(self._make_driver_kpi(
            t("analytics.kpi_avg_profit_per_driver", default="Avg Profit/Driver"),
            f"{avg_profit:,.0f} \u20ac",
            TEXT_PRIMARY,
        ))
        if unassigned_trips > 0:
            warn_card = self._make_driver_kpi(
                t("analytics.kpi_unassigned_trips", default="Unassigned Trips"),
                f"{unassigned_trips} \u26a0",
                WARNING_TEXT,
            )
            warn_card.setStyleSheet(
                f"QFrame#kpi-spark-card {{"
                f" background: {WARNING_DIM};"
                f" border: 1px solid {COLOR_WARNING_DEFAULT};"
                f" border-radius: 8px;"
                f" }}"
            )
            kpi_l.addWidget(warn_card)
        self._chart_layout.addWidget(kpi_row)

        if not drivers and not comp_data:
            self._add_no_data(t("analytics.no_driver_data", default="No assigned driver data for this period."))
            return

        # ── Driver Comparison Table ──────────────────────────────
        if comp_data:
            self._add_section_header(
                t("analytics.section_driver_metrics", default="Driver Metrics"), ""
            )
            table_data = []
            for d in comp_data:
                ppm = d.get("profit_per_km", 0) or 0
                table_data.append({
                    "driver": d.get("driver", "?") or "?",
                    "trips": int(d.get("trip_count", 0) or 0),
                    "km": f"{(d.get('total_km', 0) or 0):,.0f} km",
                    "revenue": d.get("revenue", 0) or 0,
                    "profit": d.get("profit", 0) or 0,
                    "profit_km": ppm,
                    "_profit_km_raw": ppm,
                })

            from ui.design_tokens import FONT_MONO

            def _fmt_cur(v):
                return f"\u20ac {float(v):,.0f}"

            def _fmt_rate(v):
                return f"\u20ac {float(v):.2f}/km"

            driver_table = StyledTableWidget(
                self._chart_widget,
                columns=[
                    ("driver", t("analytics.col_driver", default="Driver"), 130),
                    ("trips", t("analytics.col_trips", default="Trips"), 55),
                    ("km", t("analytics.col_km", default="KM"), 85),
                    ("revenue", t("analytics.revenue_label"), 100),
                    ("profit", t("analytics.profit_label"), 100),
                    ("profit_km", t("analytics.col_profit_km", default="Profit/KM"), 95),
                ],
                formatters={
                    "revenue": _fmt_cur,
                    "profit": _fmt_cur,
                    "profit_km": _fmt_rate,
                },
            )
            driver_table.set_data(table_data)
            driver_table.setMinimumHeight(min(38 * len(table_data) + 38, 320))
            self._chart_layout.addWidget(driver_table)

            # Color Profit/KM cells by threshold
            for r, row in enumerate(table_data):
                ppm = row.get("_profit_km_raw", 0)
                color = _profit_km_color(ppm)
                item = QTableWidgetItem(_fmt_rate(ppm))
                item.setForeground(Qt.GlobalColor.white)
                # Use background tint via stylesheet approach — set a data role
                profit_col = 5  # column index for profit_km
                existing = driver_table.item(r, profit_col)
                if existing:
                    existing.setData(Qt.UserRole, ppm)
                    # Use green/amber/red text color for the formatted value
                    from PySide6.QtGui import QColor
                    existing.setForeground(QColor(color))

            self._chart_layout.addSpacing(SP["2"])

        # ── Tacho Violations ─────────────────────────────────────
        if tacho:
            fig4 = make_bar_chart(
                [d.get("driver", "?") or "?" for d in tacho[:8]],
                [d.get("total_violations", 0) or 0 for d in tacho[:8]],
                title=t("analytics.driver_tacho"), horizontal=True,
                color=CHART_WARNING, highlight_max=True,
            )
            pw4 = PlotlyChartWidget(min_height=180)
            pw4.set_figure(fig4)
            self._chart_layout.addWidget(pw4)

        # ── Driver Activity Timeline ─────────────────────────────
        if monthly_activity:
            self._build_activity_timeline(monthly_activity)

        # ── Unassigned note ──────────────────────────────────────
        if unassigned_trips > 0:
            note = QLabel(
                t("analytics.driver_unassigned_note", default="{count} trips without assigned driver (excluded)")
                .format(count=unassigned_trips)
            )
            note.setStyleSheet(
                f"color: {WARNING_TEXT}; font-size: 11px; font-family: {FONT_FAMILY};"
                f" padding: 4px 8px; background: {WARNING_DIM}; border-radius: 4px;"
            )
            self._chart_layout.addWidget(note)

    # ── Activity Timeline ────────────────────────────────────────────

    def _build_activity_timeline(self, monthly_activity: list) -> None:
        """Build a Gantt-style view: one row per driver, cells per week."""
        from datetime import datetime, timedelta

        self._add_section_header(
            t("analytics.section_driver_activity", default="Driver Activity Timeline"), ""
        )

        # Group activity by driver
        driver_weeks: dict[str, set] = {}
        for row in monthly_activity:
            driver = row.get("driver_name", "?") or "?"
            week = row.get("week_start", "")
            if driver not in driver_weeks:
                driver_weeks[driver] = set()
            if week:
                driver_weeks[driver].add(week)

        if not driver_weeks:
            return

        # Determine the full week range
        all_weeks = sorted({row.get("week_start", "") for row in monthly_activity if row.get("week_start")})
        if not all_weeks:
            return
        if len(all_weeks) > 14:
            all_weeks = all_weeks[-12:]  # Show last 12 weeks max

        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background: {COLOR_BG_ELEVATED};"
            f" border: 1px solid {COLOR_BG_OVERLAY}; border-radius: 6px; }}"
        )
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["2"])
        container_layout.setSpacing(SP["1"])

        # Week header row
        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(100, 0, 0, 0)
        header_layout.setSpacing(2)
        for w in all_weeks:
            try:
                dt = datetime.strptime(w[:10], "%Y-%m-%d")
                wlbl = QLabel(dt.strftime("%d/%m"))
            except (ValueError, TypeError):
                wlbl = QLabel(w[:7] if len(w) >= 7 else w)
            wlbl.setFixedWidth(22)
            wlbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 8px; font-family: '{FONT_FAMILY}';"
                f" text-align: center; background: transparent;"
            )
            wlbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(wlbl)
        header_layout.addStretch()
        container_layout.addWidget(header_row)

        # Driver rows
        for driver_name, active_weeks in sorted(driver_weeks.items()):
            driver_row = QWidget()
            driver_row_layout = QHBoxLayout(driver_row)
            driver_row_layout.setContentsMargins(0, 0, 0, 0)
            driver_row_layout.setSpacing(2)

            driver_lbl = QLabel(driver_name)
            driver_lbl.setFixedWidth(96)
            driver_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 10px; font-weight: 600;"
                f" font-family: '{FONT_FAMILY}'; background: transparent;"
            )
            driver_row_layout.addWidget(driver_lbl)

            active_count = 0
            total_weeks = len(all_weeks)
            for w in all_weeks:
                cell = QFrame()
                cell.setFixedSize(22, 22)
                if w in active_weeks:
                    cell.setStyleSheet(
                        f"QFrame {{ background: {COLOR_ACCENT_PRIMARY};"
                        f" border-radius: {RADIUS_SM}px; }}"
                    )
                    active_count += 1
                else:
                    cell.setStyleSheet(
                        f"QFrame {{ background: {COLOR_BG_OVERLAY};"
                        f" border-radius: {RADIUS_SM}px; }}"
                    )
                driver_row_layout.addWidget(cell)

            # Activity summary
            summary = QLabel(f"  {active_count}/{total_weeks}")
            summary.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 9px;"
                f" font-family: '{FONT_FAMILY}'; background: transparent;"
            )
            driver_row_layout.addWidget(summary)
            driver_row_layout.addStretch()

            container_layout.addWidget(driver_row)

        self._chart_layout.addWidget(container)

    # ── KPI card builder ────────────────────────────────────────────

    @staticmethod
    def _make_driver_kpi(label: str, value: str, value_color: str) -> QWidget:
        from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

        from ui.design_tokens import BG_SURFACE, BORDER_DEFAULT

        card = QFrame()
        card.setObjectName("kpi-spark-card")
        card.setStyleSheet(
            f"QFrame#kpi-spark-card {{"
            f" background: {BG_SURFACE};"
            f" border: 1px solid {BORDER_DEFAULT};"
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
            f"color: {value_color}; font-size: 20px; font-weight: 700;"
            f" font-family: '{FONT_FAMILY}'; background: transparent; padding-top: 2px;"
        )
        card_layout.addWidget(val)
        return card
