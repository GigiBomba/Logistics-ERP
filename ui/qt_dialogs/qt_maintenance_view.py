"""PySide6 maintenance dialog with tabs for records, schedules, and health.

Replaces ``ui/maintenance_view.py`` (CTkToplevel) with a modal QDialog that
uses a QTabWidget and widget toolkit from ``ui.qt_widgets``.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.fleet_maintenance_service import FleetMaintenanceService
from services.i18n import t, register_listener, unregister_listener
from ui.icons import iconed
from ui.qt_widgets import ActionButton, KpiCard, StyledTableWidget


class QtMaintenanceView(QDialog):
    """PySide6 maintenance dialog with three tab pages.

    Args:
        parent: Parent widget (may be None).
        db: Database connection / session object.
        truck_id: Identifier of the truck whose maintenance is displayed.
        truck_plate: Licence plate string used in window title / header.
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        db,
        truck_id: int,
        truck_plate: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(iconed("maint.title", truck_plate))
        self.resize(1200, 750)
        self.setWindowModality(Qt.ApplicationModal)

        self.db = db
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.service = FleetMaintenanceService(db)

        # -- i18n listener --
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        # Tracks (widget, i18n_key, prefix) for live translation refreshes.
        self._i18n_widgets: List[Tuple[QWidget, str, str]] = []

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header area -----------------------------------------------------------
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)

        self._title_lbl = QLabel(iconed("maint.header", self.truck_plate))
        self._title_lbl.setProperty("fontRole", "h2")
        header_layout.addWidget(self._title_lbl)

        header_layout.addStretch(1)

        self._close_btn = ActionButton(
            header, iconed("maint.close"), self.close, variant="ghost",
        )
        header_layout.addWidget(self._close_btn)
        self._i18n_tag(self._close_btn, "maint.close")

        layout.addWidget(header)

        # Tab widget ------------------------------------------------------------
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget, 1)

        # Tab 1 — Maintenance history
        self._record_tab = QWidget()
        self._record_tab_layout = QVBoxLayout(self._record_tab)
        self._record_table = StyledTableWidget(
            self._record_tab,
            columns=[
                ("id", "ID", 50),
                ("type", t("maint.col_type"), 120),
                ("date", t("maint.col_date"), 110),
                ("description", t("maint.col_description"), 200),
                ("cost", t("maint.col_cost"), 80),
                ("mileage", t("maint.col_mileage"), 90),
            ],
        )
        self._record_table.rowDoubleClicked.connect(self._on_record_double_clicked)
        self._record_tab_layout.addWidget(self._record_table)
        self._tab_widget.addTab(self._record_tab, iconed("maint.tab_history"))

        # Tab 2 — Maintenance schedules
        self._schedule_tab = QWidget()
        self._schedule_tab_layout = QVBoxLayout(self._schedule_tab)
        self._schedule_table = StyledTableWidget(
            self._schedule_tab,
            columns=[
                ("id", "ID", 50),
                ("type", t("maint.col_type"), 120),
                ("next_date", t("maint.col_next_date"), 110),
                ("next_mileage", t("maint.col_next_mileage"), 110),
                ("interval_km", t("maint.col_interval_km"), 100),
                ("interval_days", t("maint.col_interval_days"), 100),
            ],
        )
        self._schedule_tab_layout.addWidget(self._schedule_table)
        self._tab_widget.addTab(self._schedule_tab, iconed("maint.tab_schedules"))

        # Tab 3 — Health overview
        self._health_tab = QWidget()
        self._health_tab_layout = QVBoxLayout(self._health_tab)

        self._health_cards_layout = QHBoxLayout()
        self._overall_card = KpiCard(self._health_tab, t("maint.health_overall"), "--")
        self._engine_card = KpiCard(self._health_tab, t("maint.health_compliance"), "--")
        self._brakes_card = KpiCard(self._health_tab, t("maint.health_overdue"), "--")
        self._tires_card = KpiCard(self._health_tab, t("maint.health_recurring"), "--")
        self._health_cards_layout.addWidget(self._overall_card)
        self._health_cards_layout.addWidget(self._engine_card)
        self._health_cards_layout.addWidget(self._brakes_card)
        self._health_cards_layout.addWidget(self._tires_card)
        self._health_tab_layout.addLayout(self._health_cards_layout)

        self._health_detail = QLabel(t("maint.health_no_data", "No health data available"))
        self._health_detail.setProperty("fontRole", "muted")
        self._health_detail.setWordWrap(True)
        self._health_tab_layout.addWidget(self._health_detail, 1)

        self._tab_widget.addTab(self._health_tab, iconed("maint.tab_health"))

        # Load data
        self._load_records()
        self._load_schedules()
        self._load_health()

    # ── Data loading ────────────────────────────────────────────────────────────

    def _load_records(self) -> None:
        """Load maintenance records for this truck into the table."""
        try:
            records = self.service.get_records(truck_id=self.truck_id)
            rows = []
            for r in records:
                if isinstance(r, dict):
                    # Map DB column names to table column IDs
                    row = dict(r)
                    row["type"] = row.get("maintenance_type", "")
                    row["description"] = row.get("notes", "")
                    row["mileage"] = row.get("km", "")
                    rows.append(row)
                else:
                    display = r.display_type() if hasattr(r, "display_type") and callable(r.display_type) else getattr(r, "maintenance_type", "")
                    rows.append({
                        "id": getattr(r, "id", ""),
                        "type": display,
                        "date": getattr(r, "date", ""),
                        "description": getattr(r, "notes", ""),
                        "cost": getattr(r, "cost", ""),
                        "mileage": getattr(r, "km", ""),
                    })
            self._record_table.set_data(rows)
        except Exception:
            self._record_table.set_data([])

    def _load_schedules(self) -> None:
        """Load maintenance schedules for this truck into the table."""
        try:
            schedules = self.service.get_schedules(truck_id=self.truck_id)
            rows = []
            for s in schedules:
                if isinstance(s, dict):
                    # Map DB column names to table column IDs
                    row = dict(s)
                    row["type"] = row.get("maintenance_type", "")
                    # Compute next_date and next_mileage from predictions
                    pred = self.service.predict_next_service(
                        self.truck_id, s.get("maintenance_type", "")
                    )
                    if pred:
                        row["next_date"] = pred.get("due_by_date", "")
                        row["next_mileage"] = pred.get("due_by_km", pred.get("remaining_km", ""))
                    else:
                        row["next_date"] = row.get("fixed_expiry_date", "")
                        row["next_mileage"] = ""
                    row["interval_days"] = row.get("interval_months", "")
                    rows.append(row)
                else:
                    display = s.display_type() if hasattr(s, "display_type") and callable(s.display_type) else getattr(s, "maintenance_type", "")
                    rows.append({
                        "id": getattr(s, "id", ""),
                        "type": display,
                        "next_date": getattr(s, "next_date", ""),
                        "next_mileage": getattr(s, "next_mileage", ""),
                        "interval_km": getattr(s, "interval_km", ""),
                        "interval_days": getattr(s, "interval_months", ""),
                    })
            self._schedule_table.set_data(rows)
        except Exception:
            self._schedule_table.set_data([])

    def _load_health(self) -> None:
        """Load truck health KPIs.

        TruckHealth has: score, compliance_pct, overdue_count,
        recurring_issues, downtime_days, last_updated.
        We map these to the 4 KPI cards.
        """
        try:
            health = self.service.compute_health(truck_id=self.truck_id)
            self._overall_card.set_value(str(health.score))
            self._engine_card.set_value(f"{health.compliance_pct:.0f}%")
            self._brakes_card.set_value(str(health.overdue_count))
            self._tires_card.set_value(str(health.recurring_issues))

            parts = []
            if health.overdue_count:
                parts.append(t("maint.health_overdue", f"{health.overdue_count} overdue"))
            if health.downtime_days:
                parts.append(t("maint.health_downtime", f"{health.downtime_days} days downtime"))
            if health.recurring_issues:
                parts.append(t("maint.health_recurring", f"{health.recurring_issues} recurring"))
            detail = " | ".join(parts) if parts else t("maint.health_ok", "All systems nominal")
            self._health_detail.setText(detail)
        except Exception:
            self._overall_card.set_value("--")
            self._engine_card.set_value("--")
            self._brakes_card.set_value("--")
            self._tires_card.set_value("--")

    def _on_record_double_clicked(self, row_data: dict) -> None:
        """Handle double-click on a maintenance record row."""
        # Future: open record detail/edit dialog
        pass

    # ── i18n helpers ───────────────────────────────────────────────────────────

    def _i18n_tag(self, widget: QWidget, key: str, prefix: str = "") -> None:
        """Register *widget* for live translation of its text by *key*."""
        self._i18n_widgets.append((widget, key, prefix))

    def _on_language_changed(self, lang: str) -> None:
        """Refresh all translatable text when the active language changes."""
        self.setWindowTitle(iconed("maint.title", self.truck_plate))
        self._title_lbl.setText(iconed("maint.header", self.truck_plate))

        for widget, key, prefix in self._i18n_widgets:
            try:
                resolved = iconed(key) if key.startswith("maint.") else t(key)
                widget.setText(f"{prefix}{resolved}")
            except Exception:
                pass

        # Refresh tab labels
        self._tab_widget.setTabText(0, iconed("maint.tab_history"))
        self._tab_widget.setTabText(1, iconed("maint.tab_schedules"))
        self._tab_widget.setTabText(2, iconed("maint.tab_health"))

        # Refresh table headers
        self._record_table.setHorizontalHeaderLabels([
            "ID", t("maint.col_type"), t("maint.col_date"),
            t("maint.col_description"), t("maint.col_cost"), t("maint.col_mileage"),
        ])
        self._schedule_table.setHorizontalHeaderLabels([
            "ID", t("maint.col_type"), t("maint.col_next_date"),
            t("maint.col_next_mileage"), t("maint.col_interval_km"),
            t("maint.col_interval_days"),
        ])

        # Refresh KPI card titles
        self._overall_card.set_title(t("maint.health_overall"))
        self._engine_card.set_title(t("maint.health_compliance"))
        self._brakes_card.set_title(t("maint.health_overdue"))
        self._tires_card.set_title(t("maint.health_recurring"))

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Unregister the i18n listener before closing."""
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        super().closeEvent(event)
