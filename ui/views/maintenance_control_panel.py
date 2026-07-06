"""PySide6 maintenance control panel.

Refactored to use Model/View architecture:
- AlertListModel + AlertFilterProxy + QListView + AlertCardDelegate
- TachoStatusModel + QTableView
- MaintenanceViewModel as centralized service facade
"""
from __future__ import annotations

import contextlib
import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from services.i18n import register_listener, t, unregister_listener
from services.operations.alert_manager import AlertType, Severity
from services.operations.operations_engine import OperationsEngine
from ui.components import (
    Btn,
    Card,
    CardHeader,
    CompactKPICard,
    FieldLabel,
    Label,
    PageTitle,
)
from ui.delegates.alert_card_delegate import AlertCardDelegate
from ui.design_tokens import (
    COLOR_BG_OVERLAY,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_WARNING_DEFAULT,
    INFO,
    SP,
)
from ui.icons import iconed
from ui.models.alert_list_model import AlertFilterProxy
from ui.models.maintenance_view_model import MaintenanceViewModel
from ui.widgets.fuel_panel import QtFuelPricePanel
from utils.formatters import fmt_currency

logger = logging.getLogger(__name__)


class QtMaintenanceControlPanel(QWidget):
    """Maintenance control panel with KPIs, tachograph table, alert list.

    Embedded widget (QStackedWidget) or standalone dialog via open_dialog().
    """

    REFRESH_INTERVAL_MS = 60_000

    def __init__(self, parent=None, db=None, prefs=None, ops=None, dialog_mode=False, api_client=None):
        super().__init__(parent)
        self._dialog_mode = dialog_mode
        self.db = db
        self._api_client = api_client
        if hasattr(self, '_api_client') and self._api_client is not None:
            from client.remote_ops_stub import RemoteOpsStub
            self.ops = RemoteOpsStub(api_client=self._api_client)
        else:
            self.ops = ops or (OperationsEngine(db) if db is not None else None)
        self._closed = False
        self._i18n_tags: list = []

        # ViewModel (shared data source)
        self._vm = MaintenanceViewModel(self, db=db, ops=self.ops) if db is not None else None

        # ── KPI widgets ────────────────────────────────────────────
        self._kpi_widgets: dict[str, QFrame] = {}
        self._kpi_value_labels: dict[str, QLabel] = {}

        # ── Filter state ───────────────────────────────────────────
        self._filter_severities: list[Severity] | None = None
        self._cb_critical: QCheckBox | None = None
        self._cb_warning: QCheckBox | None = None
        self._cb_info: QCheckBox | None = None
        self._c_type: QComboBox | None = None
        self._e_truck: QLineEdit | None = None
        self._e_trip: QLineEdit | None = None
        self._cb_show_resolved: QCheckBox | None = None
        self._summary_lbl: QLabel | None = None
        self._alert_count_lbl: QLabel | None = None

        # Alert filter proxy
        self._alert_proxy = AlertFilterProxy(self)

        self._build_ui()
        if self._vm is not None:
            self._vm.data_changed.connect(self._on_data_changed)
            self._vm.refresh_now()

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        # Auto-refresh
        self._refresh_timer = QTimer(self)
        if self._vm is not None:
            self._refresh_timer.timeout.connect(self._vm.refresh)
            self._refresh_timer.start(self.REFRESH_INTERVAL_MS)

    # ── Public API ───────────────────────────────────────────────

    @classmethod
    def open_dialog(cls, parent=None, db=None, prefs=None, ops=None):
        dialog = QDialog(parent)
        dialog.setWindowTitle(iconed("maint.control_panel_title"))
        dialog.resize(1450, 950)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        panel = cls(dialog, db=db, prefs=prefs, ops=ops, dialog_mode=True)
        layout.addWidget(panel)
        dialog.exec()
        return panel

    def wakeup(self):
        if self._vm is not None:
            self._vm.refresh_now()

    def shutdown(self):
        self._closed = True
        self._refresh_timer.stop()
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)

    # ── UI Build ─────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout)
        self._build_kpi_row(layout)
        self._build_tacho_table(layout)
        self._build_filter_bar(layout)
        self._build_alert_list(layout)
        self._build_fuel_panel(layout)

    def _build_header(self, layout):
        header = QWidget()
        header.setFixedHeight(72)
        hdr = QHBoxLayout(header)
        hdr.setContentsMargins(SP["10"], 0, SP["10"], 0)

        self._title_lbl = PageTitle(header, iconed("maint.control_panel_title"))
        hdr.addWidget(self._title_lbl)

        subtitle = Label(header, t("maint.control_panel_subtitle", default=""), role="secondary")
        hdr.addWidget(subtitle)
        hdr.addStretch(1)

        self._alert_count_lbl = Label(header, "", role="muted")
        hdr.addWidget(self._alert_count_lbl)

        if self._vm is not None:
            refresh_btn = Btn(header, t("maint.refresh"), variant="secondary", command=self._vm.refresh_now)
            hdr.addWidget(refresh_btn)

        layout.addWidget(header)

    def _build_kpi_row(self, layout):
        row = QFrame()
        row.setProperty("role", "card")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(SP["10"], SP["4"], SP["10"], SP["4"])
        rl.setSpacing(SP["3"])

        kpi_defs = [
            ("avg_health", "maint.avg_health"),
            ("trucks_needing_service", "maint.due_service"),
            ("overdue_schedules", "maint.overdue"),
            ("cost_30d", "maint.cost_30d"),
            ("total_cost", "maint.total_cost_kpi"),
        ]
        for key, title_key in kpi_defs:
            card = CompactKPICard(row, label=t(title_key), value="\u2026")
            rl.addWidget(card, 1)
            self._kpi_widgets[key] = card
            self._kpi_value_labels[key] = card.value_label
            if key == "avg_health":
                from PySide6.QtWidgets import QProgressBar
                pb = QProgressBar(card)
                pb.setMaximum(100)
                pb.setTextVisible(False)
                pb.setFixedHeight(4)
                pb.setStyleSheet(f"""
                    QProgressBar {{ background: {COLOR_BG_OVERLAY}; border: none; border-radius: 2px; }}
                    QProgressBar::chunk {{ background: {COLOR_SUCCESS_DEFAULT}; border-radius: 2px; }}
                """)
                card.layout().addWidget(pb)
                self._health_progress = pb

        layout.addWidget(row)

    def _build_tacho_table(self, layout):
        card = Card()
        CardHeader(
            card.layout(),
            title=t("tacho.section_status_title"),
            right_widget=Btn(None, t("tacho.import_now"), variant="secondary", size="sm"),
        )

        if self._vm is not None:
            self._tacho_table = QTableView()
            self._tacho_table.setModel(self._vm.tacho_model)
            self._tacho_table.setSelectionBehavior(QTableView.SelectRows)
            self._tacho_table.setSelectionMode(QTableView.SingleSelection)
            self._tacho_table.verticalHeader().setVisible(False)
            self._tacho_table.setShowGrid(False)
            self._tacho_table.setAlternatingRowColors(True)
            self._tacho_table.setMinimumHeight(160)

            hdr = self._tacho_table.horizontalHeader()
            hdr.setStretchLastSection(True)
            for c in range(self._vm.tacho_model.columnCount()):
                hdr.setSectionResizeMode(c, QHeaderView.Fixed)
                w = self._vm.tacho_model.header_width(c)
                self._tacho_table.setColumnWidth(c, w)

            card.layout().addWidget(self._tacho_table)
        layout.addWidget(card)

    def _build_filter_bar(self, layout):
        fb = Card()
        fbl = QHBoxLayout()
        fb.layout().addLayout(fbl)

        sev_lbl = FieldLabel(None, t("maint.filter_severity"))
        fbl.addWidget(sev_lbl)

        self._cb_critical = QCheckBox(t("maint.severity_critical"))
        self._cb_critical.setChecked(True)
        self._cb_critical.stateChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._cb_critical)

        self._cb_warning = QCheckBox(t("maint.severity_warning"))
        self._cb_warning.setChecked(True)
        self._cb_warning.stateChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._cb_warning)

        self._cb_info = QCheckBox(t("maint.severity_info"))
        self._cb_info.setChecked(True)
        self._cb_info.stateChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._cb_info)

        type_lbl = FieldLabel(None, t("maint.filter_type"))
        fbl.addWidget(type_lbl)

        self._c_type = QComboBox()
        self._c_type.addItem(t("common.all"))
        for at in AlertType:
            self._c_type.addItem(at.value)
        self._c_type.currentTextChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._c_type)

        truck_lbl = FieldLabel(None, t("maint.filter_truck"))
        fbl.addWidget(truck_lbl)
        self._e_truck = QLineEdit()
        self._e_truck.setPlaceholderText("Filter...")
        self._e_truck.textChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._e_truck)

        trip_lbl = FieldLabel(None, t("maint.filter_trip"))
        fbl.addWidget(trip_lbl)
        self._e_trip = QLineEdit()
        self._e_trip.setPlaceholderText("Filter...")
        self._e_trip.textChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._e_trip)

        self._cb_show_resolved = QCheckBox(t("maint.show_resolved"))
        self._cb_show_resolved.stateChanged.connect(self._on_filter_changed)
        fbl.addWidget(self._cb_show_resolved)

        fbl.addStretch(1)
        self._summary_lbl = Label(None, "", role="muted")
        fbl.addWidget(self._summary_lbl)

        layout.addWidget(fb)

    def _build_alert_list(self, layout):
        if self._vm is None:
            return
        container = Card()
        cl = container.layout()
        cl.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])

        # Wire proxy: source = ViewModel alert model → proxy → QListView
        self._alert_proxy.setSourceModel(self._vm.alert_model)

        self._alert_list = QListView()
        self._alert_list.setModel(self._alert_proxy)
        self._alert_list.setItemDelegate(AlertCardDelegate(self._alert_list))
        self._alert_list.setSelectionMode(QListView.NoSelection)
        self._alert_list.setVerticalScrollMode(QListView.ScrollPerPixel)
        self._alert_list.setSpacing(4)
        self._alert_list.setFrameShape(QFrame.NoFrame)

        cl.addWidget(self._alert_list)
        layout.addWidget(container, 1)

    def _build_fuel_panel(self, layout):
        self._fuel_panel = QtFuelPricePanel(self)
        layout.addWidget(self._fuel_panel)

    # ── Data callbacks ───────────────────────────────────────────

    def _on_data_changed(self):
        """Reactively update KPIs and summary when ViewModel emits data_changed."""
        self._update_kpis()
        self._update_summary()
        self._on_filter_changed()

    def _update_kpis(self):
        summary = self._vm.get_summary() if self._vm is not None else {}
        for key, val_lbl in self._kpi_value_labels.items():
            val = summary.get(key, t("common.na"))
            if key == "avg_health":
                color = COLOR_SUCCESS_DEFAULT if val >= 80 else COLOR_WARNING_DEFAULT if val >= 50 else COLOR_ERROR_DEFAULT
                val_lbl.setText(f"{val}/100")
                val_lbl.setStyleSheet(f"color: {color};")
                if hasattr(self, "_health_progress"):
                    self._health_progress.setValue(int(val))
                    self._health_progress.setStyleSheet(f"""
                        QProgressBar {{ background: {COLOR_BG_OVERLAY}; border: none; border-radius: 2px; }}
                        QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}
                    """)
            elif key == "overdue_schedules":
                color = COLOR_ERROR_DEFAULT if val > 0 else COLOR_SUCCESS_DEFAULT
                val_lbl.setText(str(val))
                val_lbl.setStyleSheet(f"color: {color};")
            elif key in ("cost_30d", "total_cost"):
                val_lbl.setText(fmt_currency(float(val), decimals=0))
                val_lbl.setStyleSheet(f"color: {INFO};")
            elif key == "trucks_needing_service":
                color = COLOR_WARNING_DEFAULT if int(val) > 0 else COLOR_SUCCESS_DEFAULT
                val_lbl.setText(str(val))
                val_lbl.setStyleSheet(f"color: {color};")
            else:
                val_lbl.setText(str(val))
                val_lbl.setStyleSheet("")

    def _update_summary(self):
        total = self._vm.alert_model.rowCount()
        alert_word = iconed("maint.alert_s") if total == 1 else iconed("maint.alert_plural")
        self._alert_count_lbl.setText(f"{total} {alert_word}")

    # ── Filter ───────────────────────────────────────────────────

    def _on_filter_changed(self, *args):
        # Determine which severities are enabled (None = all enabled)
        sevs = []
        if self._cb_critical and self._cb_critical.isChecked():
            sevs.append(Severity.CRITICAL)
        if self._cb_warning and self._cb_warning.isChecked():
            sevs.append(Severity.WARNING)
        if self._cb_info and self._cb_info.isChecked():
            sevs.append(Severity.INFO)
        self._filter_severities = sevs if len(sevs) < 3 else None

        # Apply filters to the proxy model
        self._alert_proxy.set_severity_filter(self._filter_severities)

        type_text = self._c_type.currentText() if self._c_type else ""
        all_label = t("common.all")
        type_filter = None if type_text in ("", all_label) else type_text
        self._alert_proxy.set_type_filter(type_filter)

        truck_text = self._e_truck.text().strip().lower() if self._e_truck else ""
        self._alert_proxy.set_truck_filter(truck_text)

        trip_text = self._e_trip.text().strip().lower() if self._e_trip else ""
        self._alert_proxy.set_trip_filter(trip_text)

        # Update summary counts from source model
        source_alerts = getattr(self._vm.alert_model, "_alerts", [])
        parts = []
        c_count = sum(1 for a in source_alerts if a.severity == Severity.CRITICAL)
        w_count = sum(1 for a in source_alerts if a.severity == Severity.WARNING)
        i_count = sum(1 for a in source_alerts if a.severity == Severity.INFO)
        if self._filter_severities is None or Severity.CRITICAL in self._filter_severities:
            parts.append(f"C:{c_count}")
        if self._filter_severities is None or Severity.WARNING in self._filter_severities:
            parts.append(f"W:{w_count}")
        if self._filter_severities is None or Severity.INFO in self._filter_severities:
            parts.append(f"I:{i_count}")
        if self._summary_lbl:
            self._summary_lbl.setText(" | ".join(parts))

    # ── i18n ─────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str):
        if self._vm is not None:
            QTimer.singleShot(0, self._vm.refresh_now)
