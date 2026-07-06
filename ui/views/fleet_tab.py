"""PySide6 fleet management view.

Replaces ``ui/fleet_tab.py``. Displays truck cards, KPI metrics, a
styled truck table, Plotly-based charts, and CRUD dialogs.

Can be embedded directly in a ``QStackedWidget``.
"""

from __future__ import annotations

import contextlib
import csv
import logging
import time
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from repositories.fleet_repository import FleetRepository
from services.driver_truck_service import DriverTruckService
from services.export_service import ExportService
from services.fleet_service import FleetService
from services.i18n import register_listener, t, unregister_listener
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    TRUCK_CREATED,
    TRUCK_DELETED,
    TRUCK_UPDATED,
    EventBus,
)
from ui.components import (
    Btn,
    KPICard,
    MonoLabel,
    PageTitle,
    SectionTitle,
)
from ui.design_tokens import (
    SP,
)
from ui.plotly_charts import CHART_ACCENT, CHART_INFO, CHART_SECONDARY, make_pie_chart
from ui.plotly_renderer import PlotlyChartWidget
from ui.styles import Theme
from ui.theme import COLORS
from ui.widgets import (
    StyledCheckBox,
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
)
from ui.widgets.layout_utils import clear_layout

logger = logging.getLogger(__name__)


# ===========================================================================
# Add / Edit Truck dialog
# ===========================================================================


class _TruckFormDialog(QDialog):
    """Modal dialog for creating or editing a truck record."""

    def __init__(
        self,
        parent: QWidget | None,
        service: FleetService,
        dta_service: DriverTruckService | None = None,
        truck: dict[str, Any] | None = None,
        on_save=None,
    ):
        super().__init__(parent)
        self._service = service
        self._dta_service = dta_service
        self._truck = truck
        self._on_save = on_save
        self._driver_ids: list[str] = []
        self._driver_names: list[str] = []
        self._fields: dict[str, StyledLineEdit] = {}

        is_edit = truck is not None
        self.setWindowTitle(
            t("fleet.edit_button") if is_edit else t("fleet.truck_form_title")
        )
        self.setMinimumWidth(480)
        self.setModal(True)

        self._build()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        self._form_layout = QVBoxLayout(content)
        self._form_layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])
        self._form_layout.setSpacing(SP["3"])
        self._form_layout.setAlignment(Qt.AlignTop)

        truck = self._truck or {}

        def make_field(label_key: str, default: str = "") -> StyledLineEdit:
            label = QLabel(t(label_key))
            label.setProperty("fontRole", "label")
            self._form_layout.addWidget(label)
            edit = StyledLineEdit()
            edit.setText(default)
            self._form_layout.addWidget(edit)
            return edit

        self._fields = {
            "plate": make_field(
                "fleet.form_plate", truck.get("plate_number", "")
            ),
            "model": make_field(
                "fleet.form_model", truck.get("model", "")
            ),
            "manufacturer": make_field(
                "fleet.form_manufacturer", truck.get("manufacturer", "")
            ),
            "year": make_field(
                "fleet.form_year",
                str(truck["year"]) if truck and truck.get("year") else "",
            ),
            "vin": make_field(
                "fleet.form_vin", truck.get("vin", "")
            ),
            "fuel": make_field(
                "fleet.form_consumption",
                str(truck.get("fuel_consumption", "") or ""),
            ),
            "mileage": make_field(
                "fleet.form_km",
                str(truck.get("mileage", "0") or "0"),
            ),
            "monthly_rate": make_field(
                "fleet.form_rate",
                f"{truck['monthly_rate']:.2f}"
                if truck and truck.get("monthly_rate") is not None
                else "0",
            ),
            "status": make_field(
                "fleet.form_status",
                truck.get("status", t("fleet.status_active")),
            ),
            "tracking_device_id": make_field(
                "fleet.form_tracking_device_id",
                truck.get("tracking_device_id", ""),
            ),
        }

        # -- Driver assignment dropdown --
        if self._dta_service:
            lbl = QLabel(t("fleet.table_driver"))
            lbl.setProperty("fontRole", "label")
            self._form_layout.addWidget(lbl)

            driver_options: list[tuple[str, str]] = [
                ("", t("fleet.table_driver_unassigned"))
            ]
            try:
                from repositories.driver_repository import DriverRepository

                dr_repo = DriverRepository(self._service.db)
                for dr in dr_repo.get_active_drivers():
                    driver_options.append((str(dr["id"]), dr["name"]))
            except Exception:
                pass

            self._driver_ids = [did for did, _ in driver_options]
            self._driver_names = [name for _, name in driver_options]
            self._driver_combo = StyledComboBox(values=self._driver_names, state="readonly")
            self._form_layout.addWidget(self._driver_combo)

            if truck and self._dta_service:
                assigned = self._dta_service.get_driver_name_for_truck(truck["id"])
                if assigned and assigned in self._driver_names:
                    self._driver_combo.setCurrentText(assigned)

        # -- Active checkbox --
        self._active_cb = StyledCheckBox(
            text=t("fleet.form_active"),
        )
        active_val = truck.get("active_status", 1) if truck else 1
        self._active_cb.setChecked(bool(active_val))
        self._form_layout.addWidget(self._active_cb)

        # -- Spacer --
        self._form_layout.addStretch(1)

        # -- Buttons --
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP["3"])

        save_btn = Btn(
            self, t("fleet.save_button"), variant="primary", command=self._save
        )
        cancel_btn = Btn(
            self, t("fleet.cancel_button"), variant="secondary", command=self.reject
        )
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        self._form_layout.addLayout(btn_row)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        scroll.setWidget(content)

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _save(self) -> None:
        f = self._fields
        plate = f["plate"].text().strip().upper()
        if not plate:
            QMessageBox.warning(
                self,
                t("fleet.validation_plate_required"),
                t("fleet.validation_plate_required"),
            )
            return

        year: int | None = None
        if f["year"].text().strip():
            try:
                year = int(f["year"].text().strip())
            except ValueError:
                QMessageBox.warning(
                    self,
                    t("fleet.validation_year_invalid"),
                    t("fleet.validation_year_invalid"),
                )
                return

        fuel: float | None = None
        if f["fuel"].text().strip():
            try:
                fuel = float(f["fuel"].text().strip())
            except ValueError:
                QMessageBox.warning(
                    self,
                    t("fleet.validation_consumption_invalid"),
                    t("fleet.validation_consumption_invalid"),
                )
                return

        try:
            mileage = float(f["mileage"].text() or "0")
            monthly_rate = float(f["monthly_rate"].text() or "0")
        except ValueError:
            QMessageBox.warning(
                self,
                t("fleet.validation_km_rate_service_invalid"),
                t("fleet.validation_km_rate_service_invalid"),
            )
            return

        data: dict[str, Any] = {
            "plate_number": plate,
            "model": f["model"].text(),
            "manufacturer": f["manufacturer"].text(),
            "year": year,
            "vin": f["vin"].text(),
            "fuel_consumption": fuel,
            "mileage": mileage,
            "monthly_rate": monthly_rate,
            "status": f["status"].text(),
            "active_status": 1 if self._active_cb.isChecked() else 0,
            "tracking_device_id": f["tracking_device_id"].text().strip(),
        }

        try:
            if self._truck:
                truck_id = self._truck["id"]
                self._service.update_truck(truck_id, data)
            else:
                truck_id = self._service.add_truck(data)

            # Driver assignment
            if self._dta_service and hasattr(self, "_driver_combo"):
                try:
                    selected_idx = self._driver_names.index(
                        self._driver_combo.currentText()
                    )
                except ValueError:
                    selected_idx = -1
                if selected_idx >= 0:
                    did_str = self._driver_ids[selected_idx]
                    if did_str:
                        self._dta_service.assign_driver_to_truck(
                            int(did_str), truck_id
                        )
                    else:
                        self._dta_service.unassign_truck(truck_id)

            # Publish the change so dropdowns in other views
            # (route planner, calculator, dispatch assignment) refresh
            # without a restart.
            plate = data.get("plate_number", "")
            try:
                bus = EventBus()
                if self._truck:
                    bus.publish(TRUCK_UPDATED, {
                        "truck_id": int(truck_id),
                        "plate": plate,
                    })
                else:
                    bus.publish(TRUCK_CREATED, {
                        "truck_id": int(truck_id),
                        "plate": plate,
                    })
            except Exception:
                logger.exception(
                    "Failed to publish truck %s event", truck_id
                )

            if self._on_save:
                self._on_save()
            self.accept()
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.error_save", default="Save Error"),
                str(ex),
            )


# ===========================================================================
# Fleet Tab
# ===========================================================================


class QtFleetTab(QWidget):
    """Fleet management view — truck table, KPI cards, charts, CRUD.

    Designed for embedding in a ``QStackedWidget``. Call ``wakeup()``
    when the view becomes visible and ``shutdown()`` when hidden.
    """

    # Staleness window for the chart on ``wakeup``.  When the chart
    # was last rendered within this many seconds, the cached pixmap is
    # reused (no render activity).
    CHART_STALENESS_SECONDS = 300

    # Column definition for StyledTableWidget: (id, label, width)
    TABLE_COLUMNS: list[tuple[str, str, int]] = [
        ("id", "fleet.table_id", 60),
        ("plate", "fleet.table_plate", 110),
        ("model", "fleet.table_model", 120),
        ("manufacturer", "fleet.table_manufacturer", 120),
        ("year", "fleet.table_year", 70),
        ("vin", "fleet.table_vin", 140),
        ("mileage", "fleet.table_km", 90),
        ("fuel", "fleet.table_consumption", 80),
        ("monthly_rate", "fleet.table_rate", 100),
        ("status", "fleet.table_status", 90),
        ("active", "fleet.table_active", 70),
        ("driver", "fleet.table_driver", 120),
    ]

    STATUS_KEYS: dict[str, str] = {
        "Active": "fleet.status_active",
        "Inactive": "fleet.status_inactive",
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        ops=None,
        fleet_repo=None,
        fleet_service=None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        self._api_client = api_client
        self.service = fleet_service if fleet_service is not None else (
            FleetService(db) if db is not None else None
        )
        self.exporter = ExportService()
        self._event_bus = EventBus()
        self._dta_service = DriverTruckService(db) if db is not None else None
        self._fleet_repo = fleet_repo if fleet_repo is not None else (FleetRepository(db) if db is not None else None)

        # -- i18n --
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        # -- Event subscriptions --
        self._event_bus.subscribe(TRUCK_UPDATED, self._on_truck_updated_ev)
        self._event_bus.subscribe(ALERT_CREATED, self._on_alert_ev)
        self._event_bus.subscribe(ALERT_RESOLVED, self._on_alert_ev)

        # -- Chart references --
        self._chart_widget: PlotlyChartWidget | None = None
        # Wall-clock timestamp of the most recent successful chart
        # render.  ``wakeup`` uses this to decide whether to re-render
        # the chart (skipping it on re-entry if the data is fresh).
        self._last_chart_ts: float = 0.0
        # Cache of the chart's status-key signature so we can detect a
        # data change without re-querying the DB.
        self._last_chart_signature: tuple | None = None

        # -- Row cache --
        self._rows: list = []

        # -- KPI card references --
        self._kpi_value_labels: dict[str, MonoLabel] = {}

        # -- UI --
        self._build_ui()
        self.refresh()

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def wakeup(self) -> None:
        """Called when the view becomes visible (e.g. tab switch).

        The chart widget and its rendered ``QPixmap`` are kept alive
        across view-switches.  We only re-render the chart if the data
        is older than the staleness window (or has never been
        rendered), so the common case — re-entering the fleet view
        after visiting another module — is instant.
        """
        # If the chart was rendered recently, skip the chart re-render.
        # The KPI / table data is cheap and still refreshes.
        chart_is_fresh = (
            self._chart_widget is not None
            and self._last_chart_ts > 0
            and (time.time() - self._last_chart_ts) < self.CHART_STALENESS_SECONDS
        )
        if chart_is_fresh:
            # Refresh the cheap data (KPIs, table) but not the chart.
            self._refresh_cheap()
        else:
            self.refresh()

    def shutdown(self) -> None:
        """Called when the view is hidden or destroyed."""
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        with contextlib.suppress(Exception):
            self._event_bus.unsubscribe(TRUCK_UPDATED, self._on_truck_updated_ev)
        with contextlib.suppress(Exception):
            self._event_bus.unsubscribe(ALERT_CREATED, self._on_alert_ev)
            self._event_bus.unsubscribe(ALERT_RESOLVED, self._on_alert_ev)
        # The chart widget lifecycle is managed by Qt's parent-child system.

    # ==================================================================
    # Event handlers
    # ==================================================================

    def _on_truck_updated_ev(self, ev: Any) -> None:
        QTimer.singleShot(0, self.refresh)

    def _on_alert_ev(self, ev: Any) -> None:
        QTimer.singleShot(0, self._refresh_alerts)

    def _on_language_changed(self, lang: str) -> None:
        QTimer.singleShot(0, self.refresh)

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout)
        self._build_kpi_strip(layout)

        # Main split: left (table) + right (alerts, charts, quick-add)
        main = QFrame()
        main_layout = QHBoxLayout(main)
        main_layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["3"])
        main_layout.setSpacing(SP["3"])

        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SP["2"])

        right = QFrame()
        right.setMinimumWidth(300)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SP["3"])

        self._build_search_bar(left_layout)
        self._build_table(left_layout)
        self._build_action_buttons(left_layout)

        self._build_alerts_panel(right_layout)
        self._build_chart_area(right_layout)
        self._build_quick_add(right_layout)

        main_layout.addWidget(left, 1)
        main_layout.addWidget(right, 0)
        layout.addWidget(main, 1)

    # -- Header ------------------------------------------------------------

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        header_layout.setSpacing(SP["3"])

        title = PageTitle(None, t("fleet.title"))
        header_layout.addWidget(title)

        header_layout.addStretch(1)

        for label_key, callback in (
            ("fleet.export_csv", self._export_csv),
            ("fleet.export_excel", self._export_excel),
            ("fleet.export_pdf", self._export_pdf),
        ):
            btn = Btn(None, t(label_key), variant="secondary", command=callback)
            header_layout.addWidget(btn)

        layout.addWidget(header)

    # -- KPI strip ---------------------------------------------------------

    def _build_kpi_strip(self, layout: QVBoxLayout) -> None:
        self._kpi_strip = QFrame()
        self._kpi_strip_layout = QHBoxLayout(self._kpi_strip)
        self._kpi_strip_layout.setContentsMargins(SP["3"], 0, SP["3"], SP["2"])
        self._kpi_strip_layout.setSpacing(SP["2"])

        self._kpi_value_labels: dict[str, MonoLabel] = {}
        self._rebuild_kpi_strip()

        layout.addWidget(self._kpi_strip)

    def _rebuild_kpi_strip(self) -> None:
        """Clear and rebuild KPI cards with current translations."""
        while self._kpi_strip_layout.count():
            item = self._kpi_strip_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._kpi_value_labels.clear()

        kpi_defs = [
            ("kpi_total", "fleet.kpi_total_trucks", "0"),
            ("kpi_active", "fleet.kpi_active", "0"),
            ("kpi_leasing", "fleet.kpi_monthly_rate", "0"),
            ("kpi_alerts", "fleet.kpi_alerts", "0"),
        ]
        for key, title_key, default_val in kpi_defs:
            card = KPICard(self._kpi_strip, t(title_key), default_val)
            val_lbl = card.findChild(QLabel, "kpi-value")
            if val_lbl is not None:
                self._kpi_value_labels[key] = val_lbl
            self._kpi_strip_layout.addWidget(card, 1)

    # -- Search bar --------------------------------------------------------

    def _build_search_bar(self, layout: QVBoxLayout) -> None:
        search_row = QFrame()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(SP["2"])

        # General text search
        search_label = QLabel(t("fleet.search_label"))
        search_label.setProperty("fontRole", "label")
        search_layout.addWidget(search_label)

        self._e_search = StyledLineEdit(placeholder=t("fleet.search_label"))
        self._e_search.textChanged.connect(self._filter_table)
        search_layout.addWidget(self._e_search, 1)

        reset_btn = Btn(
            None,
            t("fleet.reset_button"),
            variant="secondary",
            command=lambda: (self._e_search.clear(), self._filter_table()),
        )
        search_layout.addWidget(reset_btn)

        # Plate search
        plate_label = QLabel(t("fleet.plate_label"))
        plate_label.setProperty("fontRole", "label")
        search_layout.addWidget(plate_label)

        self._e_plate_search = StyledLineEdit()
        self._e_plate_search.setFixedWidth(120)
        search_layout.addWidget(self._e_plate_search)

        find_btn = Btn(
            None,
            t("fleet.find_button"),
            variant="secondary",
            command=self._find_plate,
        )
        search_layout.addWidget(find_btn)

        layout.addWidget(search_row)

    # -- Table -------------------------------------------------------------

    def _build_table(self, layout: QVBoxLayout) -> None:
        # Translate column labels at build time.
        columns = [
            (cid, t(lbl_key), w) for cid, lbl_key, w in self.TABLE_COLUMNS
        ]
        self._table = StyledTableWidget(None, columns)
        self._table.setSortingEnabled(True)
        self._table.rowDoubleClicked.connect(self._on_table_double_click)
        layout.addWidget(self._table, 1)

    # -- Action buttons ----------------------------------------------------

    def _build_action_buttons(self, layout: QVBoxLayout) -> None:
        btn_row = QFrame()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(SP["2"])

        add_btn = Btn(
            None, t("fleet.add_truck"), variant="primary", command=self._add_truck_win
        )
        btn_layout.addWidget(add_btn)

        edit_btn = Btn(
            None, t("fleet.edit_button"), variant="secondary", command=self._edit_truck_selected
        )
        btn_layout.addWidget(edit_btn)

        btn_layout.addStretch(1)

        docs_btn = Btn(
            None,
            t("fleet.documents_button"),
            variant="secondary",
            command=self._open_truck_documents,
        )
        btn_layout.addWidget(docs_btn)

        delete_btn = Btn(
            None,
            t("fleet.delete_button"),
            variant="danger",
            command=self._delete_truck,
        )
        btn_layout.addWidget(delete_btn)

        layout.addWidget(btn_row)

    # -- Alerts panel ------------------------------------------------------

    def _build_alerts_panel(self, layout: QVBoxLayout) -> None:
        self._alerts_container = QFrame()
        self._alerts_container_layout = QVBoxLayout(self._alerts_container)
        self._alerts_container_layout.setContentsMargins(0, 0, 0, 0)
        self._alerts_container_layout.setSpacing(2)

        title = SectionTitle(self._alerts_container, t("fleet.section_alerts"))
        self._alerts_container_layout.addWidget(title)

        layout.addWidget(self._alerts_container)

    # -- Chart area --------------------------------------------------------

    def _build_chart_area(self, layout: QVBoxLayout) -> None:
        self._chart_area = QFrame()
        self._chart_area.setMinimumHeight(200)
        self._chart_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._chart_layout = QVBoxLayout(self._chart_area)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)

        title = SectionTitle(self._chart_area, t("fleet.section_charts"))
        self._chart_layout.addWidget(title)

        self._chart_widget = PlotlyChartWidget(min_height=200)
        self._chart_layout.addWidget(self._chart_widget)

        layout.addWidget(self._chart_area, 1)

    # -- Quick add form ----------------------------------------------------

    def _build_quick_add(self, layout: QVBoxLayout) -> None:
        title = SectionTitle(self, t("fleet.section_quick_add"))
        layout.addWidget(title)

        quick_form = QFrame()
        qf_layout = QVBoxLayout(quick_form)
        qf_layout.setContentsMargins(0, 0, 0, 0)
        qf_layout.setSpacing(SP["2"])

        plate_lbl = QLabel(t("fleet.plate_quick"))
        plate_lbl.setProperty("fontRole", "label")
        qf_layout.addWidget(plate_lbl)
        self._q_plate = StyledLineEdit()
        qf_layout.addWidget(self._q_plate)

        model_lbl = QLabel(t("fleet.model_quick"))
        model_lbl.setProperty("fontRole", "label")
        qf_layout.addWidget(model_lbl)
        self._q_model = StyledLineEdit()
        qf_layout.addWidget(self._q_model)

        rate_lbl = QLabel(t("fleet.rate_quick"))
        rate_lbl.setProperty("fontRole", "label")
        qf_layout.addWidget(rate_lbl)
        self._q_rate = StyledLineEdit(text="0")
        qf_layout.addWidget(self._q_rate)

        save_quick_btn = Btn(
            None,
            t("fleet.save_quick"),
            variant="primary",
            command=self._save_quick,
        )
        qf_layout.addWidget(save_quick_btn)

        layout.addWidget(quick_form)

    # ==================================================================
    # Data loading
    # ==================================================================

    def refresh(self) -> None:
        """Reload all truck data, update KPIs, chart, and alerts."""
        try:
            rows = self.service.get_trucks()
        except Exception as ex:
            logger.exception("refresh_fleet failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                t("fleet.error_load", default=str(ex)),
            )
            return

        # Populate table
        table_rows: list[dict[str, Any]] = []
        for r in rows:
            driver_name = (
                self._dta_service.get_driver_name_for_truck(r["id"])
                if self._dta_service is not None else None
            ) or t("fleet.table_driver_unassigned")
            table_rows.append(
                {
                    "id": r["id"],
                    "plate": r["plate_number"],
                    "model": r.get("model", "") or "",
                    "manufacturer": r.get("manufacturer", "") or "",
                    "year": r.get("year", "") or "",
                    "vin": r.get("vin", "") or "",
                    "mileage": f"{(r.get('mileage') or 0):,}",
                    "fuel": (
                        f"{(r.get('fuel_consumption') or 0):.1f}"
                        if r.get("fuel_consumption") is not None
                        else ""
                    ),
                    "monthly_rate": f"{(r.get('monthly_rate') or 0):.2f}",
                    "status": r.get("status") or "",
                    "active": (
                        t("common.yes")
                        if r.get("active_status") in (1, True)
                        else t("common.no")
                    ),
                    "driver": driver_name,
                }
            )
        self._table.set_data(table_rows)

        # KPIs
        total = len(rows)
        active = sum(
            1 for r in rows if r.get("active_status") in (1, True)
        )
        if "kpi_total" in self._kpi_value_labels:
            self._kpi_value_labels["kpi_total"].setText(str(total))
        if "kpi_active" in self._kpi_value_labels:
            self._kpi_value_labels["kpi_active"].setText(str(active))
        if "kpi_leasing" in self._kpi_value_labels:
            self._kpi_value_labels["kpi_leasing"].setText("")

        alert_count = 0
        if self.ops:
            with contextlib.suppress(Exception):
                alert_count = self.ops.get_active_alert_count()
        if "kpi_alerts" in self._kpi_value_labels:
            self._kpi_value_labels["kpi_alerts"].setText(
                str(alert_count) if self.ops else "N/A"
            )

        self._refresh_alerts()
        self._draw_charts(rows)
        self._filter_table()

    # ==================================================================
    # Chart rendering
    # ==================================================================

    def _draw_charts(self, rows: list[dict[str, Any]]) -> None:
        if self._chart_widget is None:
            return

        statuses: dict[str, int] = {}
        for r in rows:
            st_raw = (r.get("status") or "").title()
            key = self.STATUS_KEYS.get(st_raw, "")
            st = t(key) if key else (st_raw or t("fleet.status_unknown"))
            statuses[st] = statuses.get(st, 0) + 1

        labels = list(statuses.keys())
        counts = list(statuses.values())

        if counts:
            fig = make_pie_chart(
                counts,
                labels,
                title=t("fleet.section_charts"),
                colors=[CHART_ACCENT, CHART_SECONDARY, CHART_INFO],
                show_title=True,
            )
        else:
            # No data: render an empty placeholder figure with a message
            from ui.plotly_renderer import empty_figure
            fig = empty_figure(t("fleet.no_data_chart"))

        try:
            self._chart_widget.set_figure(fig)
            # Record render time + signature so ``wakeup`` can skip
            # subsequent re-renders when the data has not changed.
            self._last_chart_ts = time.time()
            self._last_chart_signature = tuple(sorted(statuses.items()))
        except Exception:
            logger.exception("Fleet chart render failed")

    # ==================================================================
    # Alerts panel
    # ==================================================================

    def _refresh_alerts(self) -> None:
        clear_layout(self._alerts_container_layout)

        if not self.ops:
            lbl = QLabel(t("fleet.no_engine"))
            lbl.setProperty("fontRole", "muted")
            self._alerts_container_layout.addWidget(lbl)
            return

        try:
            alerts = self.ops.get_active_alerts(limit=10)
        except Exception:
            alerts = []

        if not alerts:
            lbl = QLabel(t("fleet.no_alerts"))
            lbl.setProperty("fontRole", "muted")
            lbl.setAlignment(Qt.AlignCenter)
            self._alerts_container_layout.addWidget(lbl)
            return

        for a in alerts:
            sev = getattr(a, "severity", None)
            sev_str = getattr(sev, "value", "info") if sev else "info"
            if sev_str == "critical":
                sev_color = COLORS["danger"]
            elif sev_str == "warning":
                sev_color = COLORS["warning"]
            else:
                sev_color = COLORS["info"]

            card = QFrame()
            card.setProperty("role", "card-elevated")
            card.setStyleSheet(
                f"border-left: 3px solid {sev_color};"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])
            card_layout.setSpacing(2)

            title_text = getattr(a, "title", getattr(a, "message", "Alert"))
            title_lbl = QLabel(title_text)
            title_lbl.setProperty("fontRole", "body_bold")
            title_lbl.setWordWrap(True)
            card_layout.addWidget(title_lbl)

            msg_text = getattr(a, "message", "")
            if msg_text:
                msg_lbl = QLabel(msg_text)
                msg_lbl.setProperty("fontRole", "muted")
                msg_lbl.setWordWrap(True)
                card_layout.addWidget(msg_lbl)

            self._alerts_container_layout.addWidget(card)

    # ==================================================================
    # Table filtering
    # ==================================================================

    def _refresh_cheap(self) -> None:
        """Re-fetch the cheap data (KPIs, table, alerts) without re-rendering the chart.

        Called from ``wakeup`` when the chart's cached pixmap is
        still fresh, so re-entering the view does not pay the render
        cost.  The chart's underlying figure is also unchanged in
        this path; only the textual / tabular data is refreshed.
        """
        try:
            rows = self.service.get_trucks()
        except Exception as ex:
            logger.exception("refresh_fleet failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                t("fleet.error_load", default=str(ex)),
            )
            return
        self._rows = rows
        self._update_kpis(rows)
        self._populate_table(rows)
        self._render_alerts(rows)

    def _filter_table(self) -> None:
        query = self._e_search.text().strip().lower()
        for row in range(self._table.rowCount()):
            visible = False
            if not query:
                visible = True
            else:
                for col in range(self._table.columnCount()):
                    item = self._table.item(row, col)
                    if item and query in item.text().lower():
                        visible = True
                        break
            self._table.setRowHidden(row, not visible)

    def _find_plate(self) -> None:
        plate = self._e_plate_search.text().strip().upper()
        if not plate:
            QMessageBox.information(
                self,
                t("fleet.search_info_title"),
                t("fleet.search_info_msg"),
            )
            return

        for row in range(self._table.rowCount()):
            item = self._table.item(row, 1)  # "plate" column
            if item and item.text().upper() == plate:
                self._table.selectRow(row)
                self._table.scrollToItem(item)
                return

        QMessageBox.information(
            self,
            t("fleet.search_info_title"),
            t("fleet.search_not_found", plate),
        )

    def _on_table_double_click(self, row_data: dict[str, Any]) -> None:
        truck_id = row_data.get("id")
        if truck_id is not None:
            self._open_truck_detail(int(truck_id))

    # ==================================================================
    # Selection helpers
    # ==================================================================

    def _get_selected_truck_id(self) -> int | None:
        row = self._table.selected_row_data()
        if row is None:
            QMessageBox.information(
                self,
                t("fleet.select_first"),
                t("fleet.select_first"),
            )
            return None
        return row.get("id")

    # ==================================================================
    # CRUD operations
    # ==================================================================

    def _add_truck_win(self) -> None:
        dlg = _TruckFormDialog(
            self,
            self.service,
            dta_service=self._dta_service,
            on_save=self.refresh,
        )
        dlg.exec_()

    def _edit_truck_selected(self) -> None:
        truck_id = self._get_selected_truck_id()
        if truck_id is None:
            return
        row = self.service.get_truck(truck_id)
        if not row:
            QMessageBox.critical(
                self,
                t("fleet.truck_not_found"),
                t("fleet.truck_not_found"),
            )
            return
        dlg = _TruckFormDialog(
            self,
            self.service,
            dta_service=self._dta_service,
            truck=row,
            on_save=self.refresh,
        )
        dlg.exec_()

    def _save_quick(self) -> None:
        plate = self._q_plate.text().strip().upper()
        if not plate:
            QMessageBox.warning(
                self,
                t("fleet.validation_plate_required"),
                t("fleet.validation_plate_required"),
            )
            return
        try:
            rate = float(self._q_rate.text() or "0")
        except ValueError:
            QMessageBox.warning(
                self,
                t("fleet.validation_rate_invalid"),
                t("fleet.validation_rate_invalid"),
            )
            return
        try:
            new_id = self.service.add_truck(
                {
                    "plate_number": plate,
                    "model": self._q_model.text().strip(),
                    "monthly_rate": rate,
                    "mileage": 0,
                    "status": "Active",
                    "active_status": 1,
                }
            )
            # Notify other views (route planner, calculator, dispatch
            # assignment dropdowns) so the new truck appears
            # without an app restart.
            try:
                EventBus().publish(TRUCK_CREATED, {
                    "truck_id": int(new_id) if new_id is not None else 0,
                    "plate": plate,
                })
            except Exception:
                logger.exception("Failed to publish TRUCK_CREATED for %s", plate)
            self._q_plate.clear()
            self._q_model.clear()
            self._q_rate.setText("0")
            self.refresh()
            QMessageBox.information(
                self,
                t("fleet.success_added"),
                t("fleet.success_added"),
            )
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.error_save", default="Save Error"),
                str(ex),
            )

    def _delete_truck(self) -> None:
        truck_id = self._get_selected_truck_id()
        if truck_id is None:
            return
        confirmed = QMessageBox.question(
            self,
            t("fleet.delete_button"),
            t("fleet.confirm_delete"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmed != QMessageBox.Yes:
            return
        try:
            self.service.delete_truck(truck_id)
            # Notify other views.
            try:
                EventBus().publish(TRUCK_DELETED, {
                    "truck_id": int(truck_id),
                })
            except Exception:
                logger.exception(
                    "Failed to publish TRUCK_DELETED for %s", truck_id
                )
            self.refresh()
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.error_delete", default="Delete Error"),
                str(ex),
            )

    # ==================================================================
    # Truck detail window
    # ==================================================================

    def _open_selected_truck_detail(self) -> None:
        truck_id = self._get_selected_truck_id()
        if truck_id is not None:
            self._open_truck_detail(truck_id)

    def _open_truck_detail(self, truck_id: int) -> None:
        from ui.dialogs.maintenance_view import QtMaintenanceView

        row = self.service.get_truck(truck_id)
        if not row:
            QMessageBox.critical(
                self,
                t("fleet.truck_not_found"),
                t("fleet.truck_not_found"),
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(
            t("fleet.truck_detail_title", row.get("plate_number", ""))
        )
        dlg.resize(900, 650)
        dlg.setModal(True)

        main_layout = QHBoxLayout(dlg)
        main_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        main_layout.setSpacing(SP["3"])

        # Left panel — info
        left = QFrame()
        left.setMinimumWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SP["2"])

        header_lbl = QLabel(
            f"{row.get('plate_number', '')} - {row.get('model', '')}"
        )
        header_lbl.setProperty("fontRole", "h3")
        left_layout.addWidget(header_lbl)

        details = [
            ("fleet.detail_manufacturer", row.get("manufacturer", "")),
            ("fleet.detail_year", str(row.get("year", "") or "")),
            ("fleet.detail_vin", row.get("vin", "") or ""),
            ("fleet.detail_km", f"{(row.get('mileage') or 0):,}"),
            (
                "fleet.detail_rate",
                f"{(row.get('monthly_rate') or 0):.2f} {t('common.currency_eur')}",
            ),
        ]
        for label_key, value in details:
            lbl = QLabel(f"{t(label_key)} {value}")
            lbl.setProperty("fontRole", "body")
            left_layout.addWidget(lbl)

        self._build_maintenance_kpi_strip(left_layout, truck_id, row)

        edit_btn = Btn(
            None,
            t("fleet.detail_edit_button"),
            variant="primary",
            command=lambda: (
                dlg.reject(),
                self._open_edit_from_detail(truck_id),
            ),
        )
        left_layout.addWidget(edit_btn)

        export_btn = Btn(
            None,
            t("fleet.detail_export_button"),
            variant="secondary",
            command=lambda: self._export_truck_csv(row),
        )
        left_layout.addWidget(export_btn)

        left_layout.addStretch(1)
        main_layout.addWidget(left)

        # Right panel — tabs
        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        from PySide6.QtWidgets import QTabWidget

        tabs = QTabWidget()
        right_layout.addWidget(tabs)

        # Maintenance tab
        maint_tab = QWidget()
        maint_tab_layout = QVBoxLayout(maint_tab)
        open_maint = Btn(
            None,
            t("fleet.open_maintenance_manager"),
            variant="primary",
            command=lambda: QtMaintenanceView(
                dlg, self.db, row["id"], row.get("plate_number", "")
            ).exec_(),
        )
        maint_tab_layout.addWidget(open_maint, 0, Qt.AlignCenter)
        maint_desc = QLabel(t("fleet.maint_history_desc"))
        maint_desc.setProperty("fontRole", "muted")
        maint_desc.setAlignment(Qt.AlignCenter)
        maint_tab_layout.addWidget(maint_desc)
        tabs.addTab(maint_tab, t("fleet.tab_maintenance"))

        # Expenses tab (requires local service with expense methods)
        if hasattr(self.service, 'get_expenses'):
            exp_tab = QWidget()
            self._populate_expenses_tab(exp_tab, truck_id)
            tabs.addTab(exp_tab, t("fleet.tab_expenses"))

        main_layout.addWidget(right, 1)
        dlg.exec_()

    def _open_edit_from_detail(self, truck_id: int) -> None:
        row = self.service.get_truck(truck_id)
        if row:
            dlg = _TruckFormDialog(
                self,
                self.service,
                dta_service=self._dta_service,
                truck=row,
                on_save=self.refresh,
            )
            dlg.exec_()

    def _build_maintenance_kpi_strip(
        self, layout: QVBoxLayout, truck_id: int, truck_row: dict[str, Any]
    ) -> None:
        if self.db is None:
            return
        repo = self._fleet_repo

        section_lbl = QLabel(t("fleet.maint_kpi_title"))
        section_lbl.setProperty("fontRole", "section")
        layout.addWidget(section_lbl)

        kpi_frame = QFrame()
        kpi_layout = QHBoxLayout(kpi_frame)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(SP["2"])

        # Odometer
        odometer_km = truck_row.get("mileage", 0) or 0
        odometer_str = f"{odometer_km:,.0f} {t('fleet.unit_km')}"
        self._maint_kpi_card(kpi_layout, t("fleet.maint_kpi_odometer"), odometer_str, Theme.ACCENT)

        # Last service
        last_service = repo.get_maintenance_last_date(truck_id)
        self._maint_kpi_card(
            kpi_layout, t("fleet.maint_kpi_last_service"), last_service or "\u2014", Theme.SUCCESS
        )

        # Next due
        schedules = repo.get_maintenance_schedules(truck_id)
        next_due = None
        for sched in schedules:
            fixed_date = sched.get("fixed_expiry_date")
            if fixed_date:
                try:
                    sched_dt = datetime.strptime(fixed_date, "%Y-%m-%d")
                    if next_due is None or sched_dt < next_due:
                        next_due = sched_dt
                except Exception:
                    pass
        next_due_str = next_due.strftime("%d/%m/%Y") if next_due else "\u2014"
        self._maint_kpi_card(
            kpi_layout, t("fleet.maint_kpi_next_due"), next_due_str, Theme.WARNING
        )

        # Cost month
        month_start = datetime.now().strftime("%Y-%m-01")
        cost_month = repo.sum_maintenance_cost(since_date=month_start)
        self._maint_kpi_card(
            kpi_layout, t("fleet.maint_kpi_cost_month"), f"{cost_month:.0f}", Theme.INFO
        )

        # Alert count
        alert_count = 0
        if self.ops:
            try:
                alerts = self.ops.get_alerts(
                    truck_id=str(truck_id), resolved=False, limit=100
                )
                alert_count = len(alerts)
            except Exception:
                pass
        self._maint_kpi_card(
            kpi_layout, t("fleet.maint_kpi_alerts"), str(alert_count), Theme.DANGER
        )

        # Tachograph expiry
        tacho_expiry = truck_row.get("tachograph_expiry") or ""
        tacho_color = Theme.MUTED
        tacho_display = "\u2014"
        if tacho_expiry:
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    tacho_dt = datetime.strptime(tacho_expiry, fmt)
                    days_left = (tacho_dt - datetime.now()).days
                    tacho_display = tacho_dt.strftime("%d/%m/%Y")
                    if days_left <= 7:
                        tacho_color = Theme.DANGER
                    elif days_left <= 30:
                        tacho_color = Theme.WARNING
                    else:
                        tacho_color = Theme.SUCCESS
                    break
                except Exception:
                    continue
            else:
                tacho_color = Theme.DANGER
                tacho_display = tacho_expiry
        self._maint_kpi_card(
            kpi_layout, t("fleet.maint_kpi_tacho"), tacho_display, tacho_color
        )

        layout.addWidget(kpi_frame)

    @staticmethod
    def _maint_kpi_card(
        layout: QHBoxLayout, title: str, value: str, accent_color: str
    ) -> None:
        card = QFrame()
        card.setProperty("role", "card")
        card.setStyleSheet(f"border-left: 3px solid {accent_color};")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])
        card_layout.setSpacing(1)

        title_lbl = QLabel(title.upper())
        title_lbl.setProperty("fontRole", "label")
        card_layout.addWidget(title_lbl)

        val_lbl = QLabel(str(value))
        val_lbl.setProperty("fontRole", "mono")
        val_lbl.setStyleSheet(f"color: {accent_color};")
        card_layout.addWidget(val_lbl)

        layout.addWidget(card)

    # ==================================================================
    # Expenses tab within detail dialog
    # ==================================================================

    def _populate_expenses_tab(
        self, parent: QWidget, truck_id: int
    ) -> None:
        if not hasattr(self.service, 'ensure_expenses_table'):
            return
        with contextlib.suppress(Exception):
            self.service.ensure_expenses_table()

        layout = QVBoxLayout(parent)
        layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
        layout.setSpacing(SP["2"])

        # Expenses table
        exp_cols: list[tuple[str, str, int]] = [
            ("id", "fleet.expenses_table_id", 60),
            ("date", "fleet.expenses_table_date", 100),
            ("category", "fleet.expenses_table_category", 120),
            ("amount", "fleet.expenses_table_amount", 100),
            ("desc", "fleet.expenses_table_desc", 240),
        ]
        translated_cols = [
            (cid, t(lbl_key), w) for cid, lbl_key, w in exp_cols
        ]
        self._expenses_tree = StyledTableWidget(None, translated_cols)

        def load_expenses() -> None:
            rows = self.service.get_expenses(truck_id)
            data = []
            for r in rows:
                data.append(
                    {
                        "id": r[0],
                        "date": r[1],
                        "category": r[2],
                        "amount": f"{r[3]:.2f}",
                        "desc": r[4] or "",
                    }
                )
            self._expenses_tree.set_data(data)

        load_expenses()
        layout.addWidget(self._expenses_tree, 1)

        # Add expense form
        form = QFrame()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(SP["2"])

        form_title = QLabel(t("fleet.add_expense"))
        form_title.setProperty("fontRole", "section")
        form_layout.addWidget(form_title)

        self._exp_date = StyledLineEdit(
            text=datetime.now().strftime("%Y-%m-%d")
        )
        form_layout.addWidget(self._exp_date)

        self._exp_cat = StyledLineEdit(
            text=t("fleet.expense_default_category")
        )
        form_layout.addWidget(self._exp_cat)

        self._exp_amount = StyledLineEdit(text="0")
        form_layout.addWidget(self._exp_amount)

        self._exp_desc = StyledLineEdit()
        form_layout.addWidget(self._exp_desc)

        def save_expense() -> None:
            try:
                amt = float(self._exp_amount.text() or "0")
            except ValueError:
                QMessageBox.warning(
                    self,
                    t("fleet.validation_amount_invalid"),
                    t("fleet.validation_amount_invalid"),
                )
                return
            try:
                self.service.add_expense(
                    truck_id,
                    self._exp_date.text(),
                    self._exp_cat.text(),
                    self._exp_desc.text(),
                    amt,
                )
                load_expenses()
                self.refresh()
            except Exception as ex:
                QMessageBox.critical(
                    self,
                    t("fleet.error_save_expense", default="Save Error"),
                    str(ex),
                )

        save_exp_btn = Btn(
            None,
            t("fleet.save_expense"),
            variant="primary",
            command=save_expense,
        )
        form_layout.addWidget(save_exp_btn)

        layout.addWidget(form)

    # ==================================================================
    # Export helpers
    # ==================================================================

    def _gather_trucks_for_export(self) -> list[dict[str, Any]]:
        rows = self.service.get_trucks()
        trucks = []
        for r in rows:
            trucks.append(
                {
                    "id": r["id"],
                    "plate_number": r["plate_number"],
                    "model": r.get("model") or "",
                    "manufacturer": r.get("manufacturer") or "",
                    "year": r.get("year") or "",
                    "vin": r.get("vin") or "",
                    "mileage": r.get("mileage") or 0,
                    "fuel_consumption": r.get("fuel_consumption") or 0,
                    "monthly_rate": r.get("monthly_rate") or 0,
                    "status": r.get("status") or "",
                    "active_status": r.get("active_status") or 0,
                }
            )
        return trucks

    def _export_csv(self) -> None:
        trucks = self._gather_trucks_for_export()
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("fleet.save_csv_title"),
            "",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "ID",
                        "Plate",
                        "Model",
                        "Manufacturer",
                        "Year",
                        "VIN",
                        "Mileage",
                        "Fuel L/100",
                        "Monthly Rate EUR",
                        "Status",
                        "Active",
                    ]
                )
                for truck in trucks:
                    writer.writerow(
                        [
                            truck["id"],
                            truck["plate_number"],
                            truck["model"],
                            truck["manufacturer"],
                            truck["year"],
                            truck["vin"],
                            truck["mileage"],
                            truck["fuel_consumption"],
                            truck["monthly_rate"],
                            truck["status"],
                            truck["active_status"],
                        ]
                    )
            QMessageBox.information(
                self,
                t("fleet.export_csv_success", default="Exported"),
                t("fleet.export_csv_success", default="Exported to {path}").format(
                    path=path
                ),
            )
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.export_csv_error", default="Export Error"),
                str(ex),
            )

    def _export_excel(self) -> None:
        trucks = self._gather_trucks_for_export()
        mapped = []
        for truck in trucks:
            mapped.append(
                {
                    "id": truck["id"],
                    "created_at": "",
                    "truck_number": truck["plate_number"],
                    "driver_name": "",
                    "client_name": truck["manufacturer"] or truck["model"],
                    "distance_km": truck["mileage"],
                    "total_price_eur": truck["monthly_rate"],
                    "gross_per_km": 0,
                    "rate_per_km": 0,
                    "net_profit": 0,
                    "status": truck["status"],
                    "fuel_cost": 0,
                    "toll_cost": 0,
                    "salary_cost": 0,
                }
            )
        try:
            path = self.exporter.generate_excel(
                mapped,
                filename=(
                    f"trucks_export_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                ),
            )
            QMessageBox.information(
                self,
                t("fleet.export_excel_success", default="Exported"),
                t(
                    "fleet.export_excel_success",
                    default="Exported to {path}",
                ).format(path=path),
            )
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.export_excel_error", default="Export Error"),
                str(ex),
            )

    def _export_pdf(self) -> None:
        trucks = self._gather_trucks_for_export()
        mapped = []
        for truck in trucks:
            mapped.append(
                {
                    "created_at": "",
                    "truck_number": truck["plate_number"],
                    "driver_name": truck["manufacturer"] or truck["model"],
                    "client_name": "",
                    "distance_km": truck["mileage"],
                    "gross_per_km": 0,
                    "net_profit": truck["monthly_rate"],
                    "status": truck["status"],
                }
            )
        try:
            path = self.exporter.generate_pdf(
                mapped,
                filename=(
                    f"fleet_report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                ),
            )
            QMessageBox.information(
                self,
                t("fleet.export_pdf_success", default="Exported"),
                t(
                    "fleet.export_pdf_success",
                    default="Exported to {path}",
                ).format(path=path),
            )
        except Exception as ex:
            QMessageBox.critical(
                self,
                t("fleet.export_pdf_error", default="Export Error"),
                str(ex),
            )

    def _export_truck_csv(self, truck_row: dict[str, Any]) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("fleet.save_truck_csv_title"),
            "",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Value"])
                writer.writerow(["ID", truck_row["id"]])
                writer.writerow(["Plate", truck_row["plate_number"]])
                writer.writerow(["Model", truck_row.get("model", "")])
                writer.writerow(
                    ["Manufacturer", truck_row.get("manufacturer", "")]
                )
                writer.writerow(["Year", truck_row.get("year", "")])
                writer.writerow(["VIN", truck_row.get("vin", "")])
                writer.writerow(
                    ["Mileage", truck_row.get("mileage", 0)]
                )
                writer.writerow(
                    [
                        "Fuel L/100",
                        truck_row.get("fuel_consumption", ""),
                    ]
                )
                writer.writerow(
                    [
                        "Monthly Rate EUR",
                        truck_row.get("monthly_rate", 0),
                    ]
                )
                writer.writerow(
                    ["Status", truck_row.get("status", "")]
                )
                writer.writerow(
                    [
                        "Active",
                        truck_row.get("active_status", 0),
                    ]
                )
            QMessageBox.information(
                self,
                t(
                    "fleet.export_truck_csv_success",
                    default="Exported",
                ),
                t(
                    "fleet.export_truck_csv_success",
                    default="Exported to {path}",
                ).format(path=path),
            )
        except Exception as ex:
            QMessageBox.critical(
                self,
                t(
                    "fleet.export_truck_csv_error",
                    default="Export Error",
                ),
                str(ex),
            )

    # ==================================================================
    # Document center
    # ==================================================================

    def _open_truck_documents(self) -> None:
        truck_id = self._get_selected_truck_id()
        if truck_id is None:
            QMessageBox.information(
                self,
                t("fleet.documents_button"),
                t("fleet.select_truck_first"),
            )
            return

        from ui.views.document_center_view import open_entity_documents

        truck = self.service._fleet_repo.get_by_id(truck_id)
        plate = (
            truck.get("plate_number", "Unknown") if truck else "Unknown"
        )
        open_entity_documents(
            self, self.db, "truck", truck_id, t("fleet.truck_title", default="Truck {}").format(plate)
        )

    # ==================================================================
    # Maintenance view
    # ==================================================================

    def _jump_to_alerts(self, truck_id: int) -> None:
        row = self.service.get_truck(truck_id)
        if row:
            self._open_maintenance_view(truck_id, row["plate_number"])

    def _open_maintenance_view(
        self, truck_id: int, truck_plate: str
    ) -> None:
        from ui.dialogs.maintenance_view import QtMaintenanceView

        dlg = QtMaintenanceView(
            self, self.db, truck_id, truck_plate
        )
        dlg.exec_()

    # ==================================================================
    # Utility
    # ==================================================================
