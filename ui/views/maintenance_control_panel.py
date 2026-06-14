"""PySide6 maintenance control panel.

Replaces ``ui/maintenance_control_panel.py``. Displays KPI cards, tachograph
status, a filter bar, fuel prices, and a severity-grouped alert centre.

Can be embedded directly in a ``QStackedWidget`` or opened as a standalone
modal dialog via :meth:`open_dialog`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QSizePolicy,
    QDialog,
)

from ui.theme import COLORS, S
from ui.styles import Theme
from services.i18n import t, register_listener, unregister_listener
from ui.icons import iconed
from services.operations.alert_manager import AlertType, Severity, Alert
from services.operations.operations_engine import OperationsEngine
from services.operations.event_bus import (
    EventBus,
    ALERT_CREATED,
    ALERT_RESOLVED,
    MAINTENANCE_ADDED,
    MAINTENANCE_DELETED,
)
from services.fleet_maintenance_service import FleetMaintenanceService
from ui.widgets import ActionButton, KpiCard
from ui.widgets.fuel_panel import QtFuelPricePanel

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Mapping constants (mirror the original ui/maintenance_control_panel.py)
# ──────────────────────────────────────────────────────────────────────────────

ALERT_ICONS: Dict[AlertType, str] = {
    AlertType.MAINTENANCE: "\u2699",          # ⚙
    AlertType.INSPECTION: "\u2611",           # ☑
    AlertType.INSURANCE: "\u26E8",            # ⛨
    AlertType.OVERDUE_INVOICE: "\u20AC",      # €
    AlertType.TRIP_DELAY: "\u23F1",           # ⏱
    AlertType.INACTIVE_TRUCK: "\u25CB",       # ○
    AlertType.ROUTE_ISSUE: "\u26A0",          # ⚠
    AlertType.COMPLIANCE_WARNING: "\u2696",   # ⚖
    AlertType.TACHOGRAPH_EXPIRY: "\U0001f4be",  # 💾
    AlertType.DRIVER_HOURS_WEEKLY: "\u23F1",  # ⏱
    AlertType.DRIVER_HOURS_DAILY: "\u23F1",   # ⏱
}

SEVERITY_ICONS: Dict[Severity, str] = {
    Severity.CRITICAL: "\u26A0",              # ⚠
    Severity.WARNING: "\u26A0",               # ⚠
    Severity.INFO: "\u2139",                  # ℹ
}

SEVERITY_COLORS: Dict[Severity, str] = {
    Severity.CRITICAL: Theme.DANGER,
    Severity.WARNING: Theme.WARNING,
    Severity.INFO: Theme.INFO,
}

SEVERITY_LABELS: Dict[Severity, str] = {
    Severity.CRITICAL: "maint.section_critical",
    Severity.WARNING: "maint.section_warnings",
    Severity.INFO: "maint.section_info",
}


# ──────────────────────────────────────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────────────────────────────────────


class QtMaintenanceControlPanel(QWidget):
    """Maintenance control panel with KPIs, tachograph status, fuel prices,
    and a severity-grouped alert centre.

    Use as a plain widget (embedded in a ``QStackedWidget``) or open as a
    standalone modal dialog via :meth:`open_dialog`.
    """

    REFRESH_INTERVAL_MS = 60_000

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
        ops=None,
        dialog_mode: bool = False,
    ):
        super().__init__(parent)
        self._dialog_mode = dialog_mode
        self.db = db
        self.ops = ops or OperationsEngine()
        self._event_bus = EventBus()
        self._alerts: List[Alert] = []
        self._filtered_alerts: List[Alert] = []
        self._closed = False
        self._i18n_tags: list = []          # (widget, key, prefix)
        self._handlers: Dict[str, Any] = {}  # event_type → callable

        # ── Severity checkbox state (populated after _build_filter_bar) ──
        self._cb_critical: Optional[QCheckBox] = None
        self._cb_warning: Optional[QCheckBox] = None
        self._cb_info: Optional[QCheckBox] = None

        self._build_ui()
        self._subscribe_events()

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._refresh()

        # ── Auto-refresh timer ──────────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

    # ── Public API ───────────────────────────────────────────────────────────

    @classmethod
    def open_dialog(
        cls,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
        ops=None,
    ) -> QtMaintenanceControlPanel:
        """Open the maintenance control panel as a standalone modal dialog."""
        dialog = QDialog(parent)
        dialog.setWindowTitle(iconed("maint.control_panel_title"))
        dialog.resize(1450, 950)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        panel = cls(dialog, db=db, prefs=prefs, ops=ops, dialog_mode=True)
        layout.addWidget(panel)
        dialog.exec()
        return panel

    def wakeup(self) -> None:
        """Re-subscribe events and force a refresh when the view becomes visible."""
        self._subscribe_events()
        self._refresh()

    def shutdown(self) -> None:
        """Unsubscribe events, stop timers, and clean up i18n listeners."""
        self._closed = True
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        self._unsubscribe_events()

    # ── UI Build ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout)
        self._build_kpi_row(layout)
        self._build_tachograph_status(layout)
        self._build_filter_bar(layout)
        self._build_fuel_panel(layout)
        self._build_alert_centre(layout)

    # ── Header ───────────────────────────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setProperty("role", "top-bar")
        header.setFixedHeight(56)
        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(S["5"], 0, S["5"], 0)

        self._title_lbl = QLabel()
        self._title_lbl.setProperty("fontRole", "h2")
        self._i18n_tag(self._title_lbl, "maint.control_panel_title")
        hdr_layout.addWidget(self._title_lbl)

        hdr_layout.addStretch(1)

        self._alert_count_lbl = QLabel()
        self._alert_count_lbl.setProperty("fontRole", "muted")
        hdr_layout.addWidget(self._alert_count_lbl)

        self._refresh_btn = QPushButton()
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._refresh)
        self._i18n_tag(self._refresh_btn, "maint.refresh")
        hdr_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

    # ── KPI cards ────────────────────────────────────────────────────────────

    def _build_kpi_row(self, layout: QVBoxLayout) -> None:
        row = QFrame()
        row.setProperty("role", "card")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])
        row_layout.setSpacing(S["3"])

        self._kpi_widgets: Dict[str, KpiCard] = {}
        kpi_defs = [
            ("avg_health",            "maint.avg_health"),
            ("trucks_needing_service", "maint.due_service"),
            ("overdue_schedules",      "maint.overdue"),
            ("cost_30d",               "maint.cost_30d"),
            ("total_cost",             "maint.total_cost_kpi"),
        ]
        for key, title_key in kpi_defs:
            card = KpiCard(row, iconed(title_key), "\u2026")
            row_layout.addWidget(card, 1)
            self._kpi_widgets[key] = card

        layout.addWidget(row)

    # ── Tachograph status ────────────────────────────────────────────────────

    def _build_tachograph_status(self, layout: QVBoxLayout) -> None:
        section = QFrame()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(S["5"], S["3"], S["5"], S["2"])
        section_layout.setSpacing(S["2"])

        # ── Header row ───────────────────────────────────────────────────
        hdr = QFrame()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)

        tacho_title = QLabel(t("tacho.section_status_title"))
        tacho_title.setProperty("fontRole", "section")
        hdr_layout.addWidget(tacho_title)

        hdr_layout.addStretch(1)

        import_btn = QPushButton(t("tacho.import_now"))
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setFixedSize(100, 24)
        import_btn.clicked.connect(self._navigate_to_tachograph)
        hdr_layout.addWidget(import_btn)

        section_layout.addWidget(hdr)

        # ── Scrollable table ─────────────────────────────────────────────
        self._tacho_scroll = QScrollArea()
        self._tacho_scroll.setWidgetResizable(True)
        self._tacho_scroll.setFrameShape(QFrame.NoFrame)
        self._tacho_scroll.setFixedHeight(160)

        self._tacho_content = QWidget()
        self._tacho_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tacho_layout = QVBoxLayout(self._tacho_content)
        self._tacho_layout.setContentsMargins(0, 0, 0, 0)
        self._tacho_layout.setSpacing(1)
        self._tacho_layout.setAlignment(Qt.AlignTop)

        self._tacho_scroll.setWidget(self._tacho_content)
        section_layout.addWidget(self._tacho_scroll)

        layout.addWidget(section)

    # ── Filter bar ───────────────────────────────────────────────────────────

    def _build_filter_bar(self, layout: QVBoxLayout) -> None:
        fb = QFrame()
        fb.setProperty("role", "card")
        fb_layout = QHBoxLayout(fb)
        fb_layout.setContentsMargins(S["5"], S["2"], S["5"], S["2"])
        fb_layout.setSpacing(S["3"])

        # -- Severity checkboxes ------------------------------------------
        sev_lbl = QLabel(t("maint.filter_severity"))
        sev_lbl.setProperty("fontRole", "label")
        fb_layout.addWidget(sev_lbl)

        self._cb_critical = QCheckBox(t("maint.severity_critical"))
        self._cb_critical.setChecked(True)
        self._cb_critical.stateChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._cb_critical)

        self._cb_warning = QCheckBox(t("maint.severity_warning"))
        self._cb_warning.setChecked(True)
        self._cb_warning.stateChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._cb_warning)

        self._cb_info = QCheckBox(t("maint.severity_info"))
        self._cb_info.setChecked(True)
        self._cb_info.stateChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._cb_info)

        # -- Type combobox ------------------------------------------------
        type_lbl = QLabel(t("maint.filter_type"))
        type_lbl.setProperty("fontRole", "label")
        fb_layout.addWidget(type_lbl)

        self._c_type = QComboBox()
        self._c_type.addItem(t("common.all"))
        for at in AlertType:
            self._c_type.addItem(at.value)
        self._c_type.currentTextChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._c_type)

        # -- Truck filter -------------------------------------------------
        truck_lbl = QLabel(t("maint.filter_truck"))
        truck_lbl.setProperty("fontRole", "label")
        fb_layout.addWidget(truck_lbl)

        self._e_truck = QLineEdit()
        self._e_truck.textChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._e_truck)

        # -- Trip filter --------------------------------------------------
        trip_lbl = QLabel(t("maint.filter_trip"))
        trip_lbl.setProperty("fontRole", "label")
        fb_layout.addWidget(trip_lbl)

        self._e_trip = QLineEdit()
        self._e_trip.textChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._e_trip)

        # -- Show resolved ------------------------------------------------
        self._cb_show_resolved = QCheckBox(t("maint.show_resolved"))
        self._cb_show_resolved.stateChanged.connect(self._on_filter_changed)
        fb_layout.addWidget(self._cb_show_resolved)

        fb_layout.addStretch(1)

        self._summary_lbl = QLabel()
        self._summary_lbl.setProperty("fontRole", "muted")
        fb_layout.addWidget(self._summary_lbl)

        layout.addWidget(fb)

    # ── Fuel price panel ─────────────────────────────────────────────────────

    def _build_fuel_panel(self, layout: QVBoxLayout) -> None:
        self._fuel_panel = QtFuelPricePanel(self)
        layout.addWidget(self._fuel_panel)

    # ── Alert centre (scrollable) ────────────────────────────────────────────

    def _build_alert_centre(self, layout: QVBoxLayout) -> None:
        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(S["5"], S["2"], S["5"], S["5"])

        self._alert_scroll = QScrollArea()
        self._alert_scroll.setWidgetResizable(True)
        self._alert_scroll.setFrameShape(QFrame.NoFrame)

        self._alert_content = QWidget()
        self._alert_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._alert_layout = QVBoxLayout(self._alert_content)
        self._alert_layout.setContentsMargins(0, 0, 0, 0)
        self._alert_layout.setSpacing(S["4"])
        self._alert_layout.setAlignment(Qt.AlignTop)

        self._alert_scroll.setWidget(self._alert_content)
        container_layout.addWidget(self._alert_scroll)

        layout.addWidget(container, 1)  # stretch = 1 → fills remaining space

    # ── i18n helpers ─────────────────────────────────────────────────────────

    def _i18n_tag(self, widget, key: str, prefix: str = "") -> None:
        """Register a widget for language updates and set its initial text."""
        self._i18n_tags.append((widget, key, prefix))
        text = prefix + (iconed(key) if key.startswith("maint.") else t(key))
        if isinstance(widget, (QLabel, QPushButton)):
            widget.setText(text)

    def _on_language_changed(self, lang: str) -> None:
        """Update all registered i18n widgets on language change."""
        for widget, key, prefix in self._i18n_tags:
            try:
                text = prefix + (iconed(key) if key.startswith("maint.") else t(key))
                if isinstance(widget, (QLabel, QPushButton)):
                    widget.setText(text)
            except Exception:
                pass
        # Rebuild dynamic content that depends on translations
        self._refresh()

    # ── Event subscriptions ──────────────────────────────────────────────────

    def _subscribe_events(self) -> None:
        events = {
            ALERT_CREATED: self._schedule_refresh,
            ALERT_RESOLVED: self._schedule_refresh,
            MAINTENANCE_ADDED: self._schedule_maintenance_refresh,
            MAINTENANCE_DELETED: self._schedule_maintenance_refresh,
        }
        for ev_type, handler in events.items():
            if ev_type not in self._handlers:
                self._event_bus.subscribe(ev_type, handler)
                self._handlers[ev_type] = handler

    def _unsubscribe_events(self) -> None:
        for ev_type, handler in list(self._handlers.items()):
            try:
                self._event_bus.unsubscribe(ev_type, handler)
            except Exception:
                pass
        self._handlers.clear()

    def _schedule_refresh(self, event=None) -> None:
        if self._closed:
            return
        QTimer.singleShot(300, self._do_refresh)

    def _schedule_maintenance_refresh(self, event=None) -> None:
        if self._closed:
            return
        QTimer.singleShot(200, self._refresh_kpis)

    def _do_refresh(self) -> None:
        if not self._closed:
            self._refresh()

    # ── KPI refresh ──────────────────────────────────────────────────────────

    def _refresh_kpis(self) -> None:
        try:
            svc = FleetMaintenanceService(self.db)
            summary = svc.get_summary()
            for key, card in self._kpi_widgets.items():
                val = summary.get(key, t("common.na"))
                if key == "avg_health":
                    color = (
                        Theme.SUCCESS if val >= 80
                        else Theme.WARNING if val >= 50
                        else Theme.DANGER
                    )
                    card.set_value(f"{val}/100")
                    card.value_label.setStyleSheet(f"color: {color};")
                elif key == "overdue_schedules":
                    color = Theme.DANGER if val > 0 else Theme.SUCCESS
                    card.set_value(str(val))
                    card.value_label.setStyleSheet(f"color: {color};")
                elif key in ("cost_30d", "total_cost"):
                    card.set_value(f"{float(val):,.0f}\u20AC")
                    card.value_label.setStyleSheet(f"color: {Theme.INFO};")
                elif key == "trucks_needing_service":
                    color = Theme.WARNING if int(val) > 0 else Theme.SUCCESS
                    card.set_value(str(val))
                    card.value_label.setStyleSheet(f"color: {color};")
                else:
                    card.set_value(str(val))
                    card.value_label.setStyleSheet("")
        except Exception as e:
            logger.debug("Maintenance KPIs unavailable: %s", e)
            for card in self._kpi_widgets.values():
                card.set_value(t("common.na"))
                card.value_label.setStyleSheet("")

    # ── Tachograph status ────────────────────────────────────────────────────

    def _refresh_tachograph_status(self) -> None:
        # Remove stale rows
        while self._tacho_layout.count():
            item = self._tacho_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        try:
            from repositories.tacho_vehicle_data_repository import (
                TachoVehicleDataRepository,
            )
            from repositories.fleet_repository import FleetRepository
            tvd_repo = TachoVehicleDataRepository(self.db)
            fleet_repo = FleetRepository(self.db)
            trucks = fleet_repo.get_active_trucks()
        except Exception:
            lbl = QLabel(t("tacho.no_data"))
            lbl.setProperty("fontRole", "muted")
            lbl.setAlignment(Qt.AlignCenter)
            self._tacho_layout.addWidget(lbl)
            return

        if not trucks:
            lbl = QLabel(t("tacho.no_trucks"))
            lbl.setProperty("fontRole", "muted")
            lbl.setAlignment(Qt.AlignCenter)
            self._tacho_layout.addWidget(lbl)
            return

        # ── Header row ───────────────────────────────────────────────────
        header_row = QFrame()
        header_row.setProperty("role", "input")
        header_row.setFixedHeight(24)
        hdr_layout = QHBoxLayout(header_row)
        hdr_layout.setContentsMargins(S["2"], 0, S["2"], 0)
        hdr_layout.setSpacing(S["3"])

        for col_key, width in [
            ("fleet.table_plate", 120),
            ("tacho.last_import", 120),
            ("tacho.calibration_date", 120),
            ("tacho.expiry", 120),
            ("common.status", 80),
        ]:
            lbl = QLabel(t(col_key))
            lbl.setProperty("fontRole", "label")
            lbl.setFixedWidth(width)
            hdr_layout.addWidget(lbl)
        hdr_layout.addStretch(1)
        self._tacho_layout.addWidget(header_row)

        # ── Truck data rows ──────────────────────────────────────────────
        for truck in trucks:
            latest = tvd_repo.get_latest_by_truck(truck["id"])
            self._build_tacho_row(truck, latest)

    def _build_tacho_row(self, truck: dict, latest: Optional[dict]) -> None:
        row = QFrame()
        row.setProperty("role", "card")
        row.setFixedHeight(28)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["2"], 0, S["2"], 0)
        row_layout.setSpacing(S["3"])

        plate = truck.get("plate_number", "\u2014")
        plate_lbl = QLabel(plate)
        plate_lbl.setFixedWidth(120)
        row_layout.addWidget(plate_lbl)

        if not latest or not latest.get("calibration_expiry"):
            for _ in range(3):
                dash = QLabel("\u2014")
                dash.setProperty("fontRole", "muted")
                dash.setFixedWidth(120)
                row_layout.addWidget(dash)
            chip = QLabel(t("tacho.status_no_data"))
            chip.setProperty("fontRole", "label")
            chip.setFixedWidth(80)
            chip.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(chip)
            row_layout.addStretch(1)
            self._tacho_layout.addWidget(row)
            return

        # Last import date
        import_at = "\u2014"
        try:
            from repositories.tacho_import_repository import TachoImportRepository
            ti_repo = TachoImportRepository(self.db)
            imp = ti_repo.get_by_id(latest.get("import_id"))
            if imp and imp.get("imported_at"):
                import_at = str(imp["imported_at"])[:10]
        except Exception:
            pass
        import_lbl = QLabel(import_at)
        import_lbl.setFixedWidth(120)
        row_layout.addWidget(import_lbl)

        # Calibration date
        calib_date = latest.get("calibration_date") or "\u2014"
        calib_text = (
            str(calib_date)[:10]
            if isinstance(calib_date, str)
            else str(calib_date)[:10]
        )
        calib_lbl = QLabel(calib_text)
        calib_lbl.setFixedWidth(120)
        row_layout.addWidget(calib_lbl)

        # Expiry
        expiry_str = latest.get("calibration_expiry") or "\u2014"
        expiry_text = (
            str(expiry_str)[:10]
            if isinstance(expiry_str, str)
            else str(expiry_str)[:10]
        )
        expiry_lbl = QLabel(expiry_text)
        expiry_lbl.setFixedWidth(120)
        row_layout.addWidget(expiry_lbl)

        # Status chip
        days_left: Optional[int] = None
        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
            days_left = (expiry_dt - datetime.now()).days
        except Exception:
            pass

        if days_left is None:
            chip_text = t("tacho.status_no_data")
            chip_color = COLORS["border"]
        elif days_left < 0:
            chip_text = t("tacho.status_expired")
            chip_color = COLORS["danger"]
        elif days_left <= 7:
            chip_text = f"{days_left}d"
            chip_color = COLORS["danger"]
        elif days_left <= 30:
            chip_text = f"{days_left}d"
            chip_color = COLORS["warning"]
        else:
            chip_text = t("tacho.status_valid")
            chip_color = COLORS["success"]

        chip = QLabel(chip_text)
        chip.setProperty("fontRole", "label")
        chip.setFixedWidth(80)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background-color: {chip_color};"
            f"color: {COLORS['text_primary']};"
            f"border-radius: 4px; padding: 2px 6px;"
        )
        row_layout.addWidget(chip)
        row_layout.addStretch(1)

        self._tacho_layout.addWidget(row)

    def _navigate_to_tachograph(self) -> None:
        """Try to navigate to the tachograph view via parent hierarchy."""
        parent = self.parent()
        for _ in range(5):
            if parent is None:
                break
            if hasattr(parent, "_switch_module"):
                parent._switch_module("tachograph")
                return
            parent = parent.parent()
        # Fallback: open as standalone view
        try:
            from ui.views.tacho_import_view import QtTachoImportView
            view = QtTachoImportView(self, db=self.db)
            view.show()
        except Exception:
            pass

    # ── Alert filtering ──────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if self._closed:
            return
        self._alerts = self.ops.get_active_alerts(limit=200)
        if self._cb_show_resolved.isChecked():
            resolved = self.ops.get_alerts(resolved=True, limit=200)
            self._alerts.extend(resolved)
        self._apply_filters()
        self._refresh_kpis()
        self._refresh_tachograph_status()

    def _on_filter_changed(self, *args) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        sev_critical = self._cb_critical.isChecked()
        sev_warning = self._cb_warning.isChecked()
        sev_info = self._cb_info.isChecked()
        type_text = self._c_type.currentText()
        truck_text = self._e_truck.text().strip().lower()
        trip_text = self._e_trip.text().strip().lower()

        raw = self._alerts

        # ── Severity (checkbox-based) ────────────────────────────────────
        def _passes_severity(a: Alert) -> bool:
            if a.severity == Severity.CRITICAL and not sev_critical:
                return False
            if a.severity == Severity.WARNING and not sev_warning:
                return False
            if a.severity == Severity.INFO and not sev_info:
                return False
            return True

        raw = [a for a in raw if _passes_severity(a)]

        # ── Type ─────────────────────────────────────────────────────────
        all_label = t("common.all")
        if type_text and type_text != all_label:
            raw = [a for a in raw if a.type.value == type_text]

        # ── Truck / Trip free-text ───────────────────────────────────────
        if truck_text:
            raw = [
                a for a in raw
                if a.truck_id and truck_text in a.truck_id.lower()
            ]
        if trip_text:
            raw = [
                a for a in raw
                if a.trip_id and trip_text in a.trip_id.lower()
            ]

        # ── Sort: severity (critical first), then age ────────────────────
        raw.sort(
            key=lambda a: (
                0 if a.severity == Severity.CRITICAL else
                1 if a.severity == Severity.WARNING else 2,
                a.created_at or "",
            ),
        )

        self._filtered_alerts = raw
        self._render_alerts()

    # ── Alert rendering ──────────────────────────────────────────────────────

    def _render_alerts(self) -> None:
        # Clear existing alert content
        while self._alert_layout.count():
            item = self._alert_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        critical = [a for a in self._filtered_alerts if a.severity == Severity.CRITICAL]
        warnings = [a for a in self._filtered_alerts if a.severity == Severity.WARNING]
        info = [a for a in self._filtered_alerts if a.severity == Severity.INFO]

        total = len(self._filtered_alerts)
        alert_word = iconed("maint.alert_s") if total == 1 else iconed("maint.alert_plural")
        self._alert_count_lbl.setText(f"{total} {alert_word}")

        counts = []
        if critical:
            counts.append(iconed("maint.critical_count").format(len(critical)))
        if warnings:
            counts.append(iconed("maint.warning_count").format(len(warnings)))
        if info:
            counts.append(iconed("maint.info_count").format(len(info)))
        self._summary_lbl.setText(" | ".join(counts))

        if not self._filtered_alerts:
            empty = QLabel(iconed("maint.no_alerts_filter"))
            empty.setProperty("fontRole", "muted")
            empty.setAlignment(Qt.AlignCenter)
            self._alert_layout.addWidget(empty)
            return

        for severity, group in [
            (Severity.CRITICAL, critical),
            (Severity.WARNING, warnings),
            (Severity.INFO, info),
        ]:
            if not group:
                continue
            self._build_alert_section(severity, group)

    def _build_alert_section(self, severity: Severity, alerts: List[Alert]) -> None:
        colour = SEVERITY_COLORS[severity]
        icon = SEVERITY_ICONS[severity]
        label = t(SEVERITY_LABELS[severity])
        count = len(alerts)

        section = QFrame()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(S["2"])

        # ── Section header ───────────────────────────────────────────────
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(S["2"])

        strip = QFrame()
        strip.setFixedWidth(4)
        strip.setFixedHeight(20)
        strip.setStyleSheet(f"background-color: {colour}; border-radius: 2px;")
        header_layout.addWidget(strip)

        title_lbl = QLabel(f"{icon}  {label} ({count})")
        title_lbl.setProperty("fontRole", "h3")
        title_lbl.setStyleSheet(f"color: {colour};")
        header_layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            f"background-color: {COLORS['border']}; max-height: 1px;"
        )
        sep.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(sep)

        section_layout.addWidget(header)

        # ── Alert cards ──────────────────────────────────────────────────
        for alert in alerts:
            self._build_alert_card(section, alert)

        self._alert_layout.addWidget(section)

    def _build_alert_card(self, parent: QFrame, alert: Alert) -> None:
        sev_colour = SEVERITY_COLORS.get(alert.severity, COLORS["text_muted"])
        icon = ALERT_ICONS.get(alert.type, "\u2753")

        card = QFrame()
        card.setProperty("role", "card")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── Colour strip ────────────────────────────────────────────────
        strip = QFrame()
        strip.setFixedWidth(4)
        strip.setStyleSheet(f"background-color: {sev_colour}; border-radius: 2px;")
        strip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        card_layout.addWidget(strip)

        # ── Inner content ───────────────────────────────────────────────
        inner = QFrame()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        inner_layout.setSpacing(S["1"])

        # Row 1: icon + title + timestamp
        row1 = QFrame()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(S["2"])

        icon_lbl = QLabel(icon)
        row1_layout.addWidget(icon_lbl)

        title_lbl = QLabel(alert.title)
        title_lbl.setProperty("fontRole", "small")
        title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row1_layout.addWidget(title_lbl)

        ts = alert.created_at
        if ts and len(ts) > 16:
            ts = ts[:16].replace("T", " ")
        ts_lbl = QLabel(ts or "")
        ts_lbl.setProperty("fontRole", "muted")
        row1_layout.addWidget(ts_lbl)

        inner_layout.addWidget(row1)

        # Row 2: message
        msg_lbl = QLabel(alert.message)
        msg_lbl.setProperty("fontRole", "muted")
        msg_lbl.setWordWrap(True)
        inner_layout.addWidget(msg_lbl)

        # Row 3: references (truck / trip)
        refs = []
        if alert.truck_id:
            refs.append(iconed("maint.label_truck", truck_id=alert.truck_id))
        if alert.trip_id:
            refs.append(iconed("maint.label_trip", trip_id=alert.trip_id))
        if refs:
            ref_lbl = QLabel("  \u2022  ".join(refs))
            ref_lbl.setProperty("fontRole", "small")
            ref_lbl.setStyleSheet(f"color: {COLORS['info']};")
            inner_layout.addWidget(ref_lbl)

        # Row 4: action buttons
        actions = QFrame()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(S["2"])

        self._action_btn(
            actions,
            iconed("maint.action_resolve"),
            "success",
            lambda aid=alert.id: self._resolve_alert(aid),
        )
        if alert.truck_id:
            self._action_btn(
                actions,
                iconed("maint.action_truck"),
                "primary",
                lambda tid=alert.truck_id: self._open_truck(tid),
            )
        if alert.trip_id:
            self._action_btn(
                actions,
                iconed("maint.action_trip"),
                "primary",
                lambda tip=alert.trip_id: self._open_trip(tip),
            )
        if alert.truck_id and alert.severity in (Severity.CRITICAL, Severity.WARNING):
            self._action_btn(
                actions,
                iconed("maint.action_maint"),
                "danger",
                lambda tid=alert.truck_id: self._schedule_maint(tid),
            )
        self._action_btn(
            actions,
            iconed("maint.action_remind"),
            "ghost",
            lambda a=alert: self._generate_reminder(a),
        )

        actions_layout.addStretch(1)
        inner_layout.addWidget(actions)

        card_layout.addWidget(inner, 1)

        # Add card to the parent (section) layout
        parent.layout().addWidget(card)

    def _action_btn(
        self,
        parent: QFrame,
        text: str,
        variant: str,
        command,
    ) -> None:
        """Add a small action button to the given parent layout."""
        btn = ActionButton(
            parent,
            text=text,
            command=command,
            variant=variant,
        )
        parent.layout().addWidget(btn)

    # ── Alert actions ────────────────────────────────────────────────────────

    def _resolve_alert(self, alert_id: str) -> None:
        self.ops.resolve_alert(alert_id)
        self._refresh()

    def _open_truck(self, truck_id: str) -> None:
        if hasattr(self.parent(), "_open_fleet"):
            self.parent()._open_fleet()
        self._flash_msg(iconed("maint.flash_truck_copied").format(truck_id))

    def _open_trip(self, trip_id: str) -> None:
        self._flash_msg(iconed("maint.flash_trip_copied").format(trip_id))

    def _schedule_maint(self, truck_id: str) -> None:
        self._flash_msg(iconed("maint.flash_maint_scheduled").format(truck_id))

    def _generate_reminder(self, alert: Alert) -> None:
        self._flash_msg(iconed("maint.flash_reminder").format(alert.title))

    def _flash_msg(self, msg: str) -> None:
        self._alert_count_lbl.setText(msg)
        self._alert_count_lbl.setStyleSheet(f"color: {Theme.WARNING};")
        total = len(self._filtered_alerts)
        alert_word = iconed("maint.alert_s") if total == 1 else iconed("maint.alert_plural")
        QTimer.singleShot(2500, lambda: self._restore_alert_count(total, alert_word))

    def _restore_alert_count(self, total: int, alert_word: str) -> None:
        self._alert_count_lbl.setText(f"{total} {alert_word}")
        self._alert_count_lbl.setStyleSheet("")
