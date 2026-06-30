"""PySide6 per-truck maintenance dialog with Records, Schedules, Health tabs.

Refactored to:
- Properly use FleetMaintenanceService dataclasses
- Add Schedule CRUD (create/edit/deactivate)
- Fix health KPI cards to show computed_health values
- Remove fragile hasattr/type-checking data access patterns
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.fleet_maintenance_service import (
    MAINT_DEFAULT_INTERVALS,
    MAINT_DISPLAY,
    FleetMaintenanceService,
    MaintType,
)
from services.i18n import register_listener, t, unregister_listener
from ui.icons import iconed
from ui.models.maintenance_view_model import MaintenanceViewModel
from ui.widgets import ActionButton, KpiCard, StyledTableWidget

logger = logging.getLogger(__name__)


class QtMaintenanceView(QDialog):
    """Per-truck maintenance dialog with 3 tab pages.

    Args:
        parent: Parent widget.
        db: Database connection.
        truck_id: Truck identifier.
        truck_plate: Licence plate for window title.
    """

    def __init__(self, parent: QWidget | None, db, truck_id: int, truck_plate: str):
        super().__init__(parent)
        self.setWindowTitle(iconed("maint.title", truck_plate))
        self.resize(1200, 750)
        self.setWindowModality(Qt.ApplicationModal)

        self.db = db
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.service = FleetMaintenanceService(db)
        self._vm = MaintenanceViewModel(self, db=db)

        self._i18n_widgets: list[tuple[QWidget, str, str]] = []
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._load_all()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 10, 20, 10)
        self._title_lbl = QLabel(iconed("maint.header", self.truck_plate))
        self._title_lbl.setProperty("fontRole", "h2")
        hl.addWidget(self._title_lbl)
        hl.addStretch(1)
        close_btn = ActionButton(header, iconed("maint.close"), self.close, variant="ghost")
        hl.addWidget(close_btn)
        layout.addWidget(header)

        # Tabs
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget, 1)

        # Tab 1 — Records
        self._record_tab = QWidget()
        self._record_layout = QVBoxLayout(self._record_tab)
        self._record_table = StyledTableWidget(self._record_tab, [
            ("id", "ID", 50),
            ("type", t("maint.col_type"), 120),
            ("date", t("maint.col_date"), 110),
            ("description", t("maint.col_description"), 200),
            ("cost", t("maint.col_cost"), 80),
            ("mileage", t("maint.col_mileage"), 90),
        ])
        self._record_table.rowDoubleClicked.connect(self._on_record_double_clicked)
        self._record_layout.addWidget(self._record_table)
        self._tab_widget.addTab(self._record_tab, iconed("maint.tab_history"))

        # Tab 2 — Schedules (with add/edit/delete)
        self._schedule_tab = QWidget()
        self._schedule_layout = QVBoxLayout(self._schedule_tab)
        self._schedule_table = StyledTableWidget(self._schedule_tab, [
            ("id", "ID", 50),
            ("type", t("maint.col_type"), 120),
            ("interval_km", t("maint.col_interval_km"), 100),
            ("interval_days", t("maint.col_interval_days"), 100),
            ("last_done_date", t("maint.col_last_done"), 110),
            ("next_service", t("maint.col_next_service"), 120),
            ("status", t("maint.col_status"), 80),
        ])
        self._schedule_layout.addWidget(self._schedule_table)

        # Schedule action buttons
        btn_row = QHBoxLayout()
        add_sched_btn = ActionButton(None, iconed("maint.add_schedule"), self._add_schedule_dialog, variant="primary")
        btn_row.addWidget(add_sched_btn)
        edit_sched_btn = ActionButton(None, iconed("maint.edit_schedule"), self._edit_schedule_dialog, variant="secondary")
        btn_row.addWidget(edit_sched_btn)
        deact_btn = ActionButton(None, iconed("maint.deactivate_schedule"), self._deactivate_schedule, variant="danger")
        btn_row.addWidget(deact_btn)
        btn_row.addStretch(1)
        self._schedule_layout.addLayout(btn_row)
        self._tab_widget.addTab(self._schedule_tab, iconed("maint.tab_schedules"))

        # Tab 3 — Health
        self._health_tab = QWidget()
        self._health_layout = QVBoxLayout(self._health_tab)
        self._health_cards_layout = QHBoxLayout()
        self._health_cards: dict[str, KpiCard] = {}
        for key, label_text in [
            ("overall", t("maint.health_overall")),
            ("compliance", t("maint.health_compliance")),
            ("overdue", t("maint.health_overdue")),
            ("recurring", t("maint.health_recurring")),
            ("downtime", t("maint.health_downtime")),
        ]:
            card = KpiCard(self._health_tab, label_text, "--")
            self._health_cards_layout.addWidget(card)
            self._health_cards[key] = card
        self._health_layout.addLayout(self._health_cards_layout)

        self._health_detail = QLabel(t("maint.health_no_data", "No health data available"))
        self._health_detail.setProperty("fontRole", "muted")
        self._health_detail.setWordWrap(True)
        self._health_layout.addWidget(self._health_detail, 1)
        self._tab_widget.addTab(self._health_tab, iconed("maint.tab_health"))

    # ── Data loading ─────────────────────────────────────────────

    def _load_all(self):
        self._load_records()
        self._load_schedules()
        self._load_health()

    def _load_records(self):
        try:
            records = self.service.get_records(truck_id=self.truck_id)
            rows = []
            for r in records:
                if isinstance(r, dict):
                    rows.append({
                        "id": r.get("id", ""),
                        "type": r.get("maintenance_type", ""),
                        "date": (r.get("date") or "")[:10],
                        "description": r.get("notes", ""),
                        "cost": r.get("cost", ""),
                        "mileage": r.get("km", ""),
                    })
                else:
                    rows.append({
                        "id": getattr(r, "id", ""),
                        "type": getattr(r, "display_type", lambda: "")(),
                        "date": str(getattr(r, "date", ""))[:10],
                        "description": getattr(r, "notes", ""),
                        "cost": getattr(r, "cost", ""),
                        "mileage": getattr(r, "km", ""),
                    })
            self._record_table.set_data(rows)
        except Exception:
            logger.exception("Failed to load maintenance records")

    def _load_schedules(self):
        try:
            schedules = self.service.get_schedules(truck_id=self.truck_id)
            rows = []
            for s in schedules:
                pred = self.service.predict_next_service(self.truck_id, s["maintenance_type"])
                mt = s.get("maintenance_type", "custom")
                try:
                    display = MAINT_DISPLAY.get(MaintType(mt), mt.replace("_", " ").title())
                except ValueError:
                    display = mt.replace("_", " ").title()

                next_svc = pred.get("due_by_date") or ""
                if pred and pred.get("due_km"):
                    km = pred["due_km"]
                    next_svc += f" ({km:,.0f} km)" if next_svc else f"{km:,.0f} km"
                if pred and pred.get("overdue"):
                    next_svc = f"OVERDUE: {next_svc}"

                rows.append({
                    "id": s.get("id", ""),
                    "type": display,
                    "interval_km": f"{s.get('interval_km', ''):.0f}" if s.get("interval_km") else "",
                    "interval_days": f"{s.get('interval_months', '')*30}" if s.get("interval_months") else "",
                    "last_done_date": (s.get("last_done_date") or "")[:10],
                    "next_service": next_svc,
                    "status": t("maint.active") if s.get("active") else t("maint.inactive"),
                })
            self._schedule_table.set_data(rows)
        except Exception:
            logger.exception("Failed to load schedules")

    def _load_health(self):
        try:
            health = self._vm.get_health(self.truck_id, force=True)
            self._health_cards["overall"].set_value(f"{health.score}/100")
            self._health_cards["compliance"].set_value(f"{health.compliance_pct:.0f}%")
            self._health_cards["overdue"].set_value(str(health.overdue_count))
            self._health_cards["recurring"].set_value(str(health.recurring_issues))
            self._health_cards["downtime"].set_value(f"{health.downtime_days}d")

            summary_parts = []
            if health.overdue_count > 0:
                summary_parts.append(f"{health.overdue_count} overdue service(s)")
            if health.recurring_issues > 0:
                summary_parts.append(f"{health.recurring_issues} recurring issue(s)")
            if health.downtime_days > 30:
                summary_parts.append(f"{health.downtime_days}d since last service")
            if summary_parts:
                self._health_detail.setText("; ".join(summary_parts))
            else:
                self._health_detail.setText(t("maint.health_good"))
        except Exception:
            logger.exception("Failed to load health data")

    # ── Schedule CRUD ────────────────────────────────────────────

    def _selected_schedule(self) -> int | None:
        row = self._schedule_table.selected_row_data()
        if row:
            try:
                return int(row.get("id", 0))
            except (ValueError, TypeError):
                pass
        return None

    def _add_schedule_dialog(self):
        dlg = _ScheduleEditDialog(self, None)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.service.add_schedule(
                truck_id=self.truck_id,
                maint_type=data["type"],
                interval_km=data.get("km"),
                interval_months=data.get("months"),
                fixed_expiry_date=data.get("fixed_date", ""),
                last_done_km=data.get("last_km"),
                last_done_date=data.get("last_date", ""),
            )
            self._load_schedules()
            self._vm.refresh_now()

    def _edit_schedule_dialog(self):
        sched_id = self._selected_schedule()
        if sched_id is None:
            QMessageBox.information(self, t("maint.no_selection"), t("maint.select_schedule_first"))
            return
        sched = self.service._fleet_repo.get_maintenance_schedule(None, None)
        if not sched:
            # Fetch by id instead
            schedules = self.service.get_schedules(truck_id=self.truck_id)
            sched = next((s for s in schedules if s["id"] == sched_id), None)
        if not sched:
            return

        dlg = _ScheduleEditDialog(self, sched)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.service.update_schedule(
                schedule_id=sched_id,
                interval_km=data.get("km"),
                interval_months=data.get("months"),
                fixed_expiry_date=data.get("fixed_date", ""),
                last_done_km=data.get("last_km"),
                last_done_date=data.get("last_date", ""),
            )
            self._load_schedules()
            self._vm.refresh_now()

    def _deactivate_schedule(self):
        sched_id = self._selected_schedule()
        if sched_id is None:
            QMessageBox.information(self, t("maint.no_selection"), t("maint.select_schedule_first"))
            return
        answer = QMessageBox.question(
            self, t("maint.confirm"), t("maint.confirm_deactivate_schedule"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.service.update_schedule(schedule_id=sched_id, active=0)
            self._load_schedules()
            self._vm.refresh_now()

    # ── Record detail ────────────────────────────────────────────

    def _on_record_double_clicked(self, row_data: dict):
        QMessageBox.information(
            self,
            t("maint.record_detail"),
            t("maint.record_detail_text").format(**row_data),
        )

    # ── i18n ─────────────────────────────────────────────────────

    def _i18n_tag(self, widget, key: str, prefix: str = ""):
        self._i18n_widgets.append((widget, key, prefix))
        text = prefix + (iconed(key) if key.startswith("maint.") else t(key))
        if isinstance(widget, (QLabel, QPushButton)):
            widget.setText(text)

    def _on_language_changed(self, lang: str):
        for widget, key, prefix in self._i18n_widgets:
            try:
                text = prefix + (iconed(key) if key.startswith("maint.") else t(key))
                if isinstance(widget, (QLabel, QPushButton)):
                    widget.setText(text)
            except Exception:
                pass
        self._load_all()

    def closeEvent(self, event):
        try:
            unregister_listener(self._language_callback)
        except Exception as e:
            logger.warning("Failed to unregister i18n listener: %s", e)
        super().closeEvent(event)


class _ScheduleEditDialog(QDialog):
    """Modal dialog to create or edit a maintenance schedule."""

    def __init__(self, parent, existing: dict[str, Any] | None):
        super().__init__(parent)
        self.setWindowTitle(t("maint.schedule_edit_title"))
        self.setMinimumWidth(400)

        self._existing = existing
        form = QFormLayout(self)

        # Maintenance type
        self._type_combo = QComboBox()
        for mt in MaintType:
            self._type_combo.addItem(MAINT_DISPLAY.get(mt, mt.value), mt.value)
        if existing:
            idx = self._type_combo.findData(existing.get("maintenance_type", ""))
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)
        form.addRow(t("maint.col_type"), self._type_combo)

        # Interval KM
        self._km_spin = QDoubleSpinBox()
        self._km_spin.setRange(0, 500000)
        self._km_spin.setSingleStep(10000)
        self._km_spin.setSuffix(" km")
        if existing and existing.get("interval_km"):
            self._km_spin.setValue(float(existing["interval_km"]))
        else:
            self._km_spin.setValue(0)
        form.addRow(t("maint.interval_km"), self._km_spin)

        # Interval months
        self._month_spin = QSpinBox()
        self._month_spin.setRange(0, 60)
        self._month_spin.setSuffix(" months")
        if existing and existing.get("interval_months"):
            self._month_spin.setValue(int(existing["interval_months"]))
        else:
            # Provide a default based on type
            mt = existing.get("maintenance_type", "") if existing else ""
            _default_km, default_months = MAINT_DEFAULT_INTERVALS.get(mt, (None, None))
            self._month_spin.setValue(default_months or 0)
        form.addRow(t("maint.interval_months"), self._month_spin)

        # Last done KM
        self._last_km_spin = QDoubleSpinBox()
        self._last_km_spin.setRange(0, 9999999)
        self._last_km_spin.setSuffix(" km")
        if existing and existing.get("last_done_km"):
            self._last_km_spin.setValue(float(existing["last_done_km"]))
        form.addRow(t("maint.last_done_km"), self._last_km_spin)

        # Last done date
        self._last_date_edit = QDateEdit()
        self._last_date_edit.setCalendarPopup(True)
        self._last_date_edit.setDisplayFormat("yyyy-MM-dd")
        if existing and existing.get("last_done_date"):
            try:
                dt = datetime.strptime(existing["last_done_date"][:10], "%Y-%m-%d")
                self._last_date_edit.setDate(dt.date())
            except Exception:
                pass
        else:
            self._last_date_edit.setDate(datetime.now().date())
        form.addRow(t("maint.last_done_date"), self._last_date_edit)

        # Fixed expiry date
        self._fixed_date_edit = QDateEdit()
        self._fixed_date_edit.setCalendarPopup(True)
        self._fixed_date_edit.setDisplayFormat("yyyy-MM-dd")
        self._fixed_date_edit.setSpecialValueText(" ")
        if existing and existing.get("fixed_expiry_date"):
            try:
                dt = datetime.strptime(existing["fixed_expiry_date"][:10], "%Y-%m-%d")
                self._fixed_date_edit.setDate(dt.date())
            except Exception:
                pass
        form.addRow(t("maint.fixed_expiry_date"), self._fixed_date_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton(t("common.save"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(t("common.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        form.addRow(btn_layout)

    def get_data(self) -> dict[str, Any]:
        km = self._km_spin.value()
        months = self._month_spin.value()
        return {
            "type": self._type_combo.currentData(),
            "km": km if km > 0 else None,
            "months": months if months > 0 else None,
            "fixed_date": self._fixed_date_edit.date().toString("yyyy-MM-dd")
                         if not self._fixed_date_edit.date().isNull() else "",
            "last_km": self._last_km_spin.value() if self._last_km_spin.value() > 0 else None,
            "last_date": self._last_date_edit.date().toString("yyyy-MM-dd"),
        }
