"""PySide6 driver management view.

Replaces ``ui/driver_manager.py``. Displays KPI cards, a searchable
driver table, and CRUD operations via a form dialog. Embeds in a
``QStackedWidget`` via the ``wakeup`` / ``shutdown`` lifecycle.
"""

from __future__ import annotations

import contextlib
import csv
import json
import logging
from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from repositories.driver_repository import DriverRepository
from services.driver_truck_service import DriverTruckService
from services.i18n import t

if TYPE_CHECKING:
    from repositories.driver_repository import DriverRepository
from ui.mode_guard import ConnectionMode, detect_mode, guard_local_access
from services.operations.event_bus import (
    DRIVER_CREATED,
    DRIVER_DELETED,
    DRIVER_UPDATED,
    EventBus,
    TRUCK_UPDATED,
)
from ui.base_view import BaseView
from ui.components import (
    Btn,
    Card,
    IconButton,
    KPICard,
    MonoLabel,
    PageTitle,
    SectionTitle,
)
from ui.design_tokens import (
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    RADIUS_SM,
    SP,
)
from ui.widgets import (
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    field,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit

from ui.performance_timer import PerfTimer

logger = logging.getLogger(__name__)


# ── Column definitions ─────────────────────────────────────────────────────────
# (column_id,  i18n_key_or_raw_label,  width_px,  translate)

_COLUMNS: list[tuple] = [
    ("id",             "driver_manager.col_id",              50,  True),
    ("name",           "driver_manager.col_name",           150,  True),
    ("phone",          "driver_manager.col_phone",          110,  True),
    ("license",        "driver_manager.col_license",         90,  True),
    ("license_expiry", "driver_manager.col_license_expiry", 100,  True),
    ("medical_expiry", "driver_manager.col_medical_expiry", 100,  True),
    ("hire_date",      "driver_manager.col_hire_date",      100,  True),
    ("salary",         "driver_manager.col_salary",          90,  True),
    ("active",         "driver_manager.col_active",          70,  True),
    ("truck",          "driver_manager.col_truck",          120,  True),
]


def _resolve_column_labels() -> list[str]:
    """Return translated header labels for the current language."""
    return [t(key) if translate else key for _, key, _, translate in _COLUMNS]


def _columns_for_table() -> list[tuple]:
    """Return ``(cid, label, width)`` tuples for ``StyledTableWidget``."""
    labels = _resolve_column_labels()
    return [(cid, labels[i], width) for i, (cid, _, width, _) in enumerate(_COLUMNS)]


# ── Driver form dialog (add / edit) ────────────────────────────────────────────


class QtDriverFormDialog(QDialog):
    """Add / edit driver dialog.

    Mirrors ``ui/dialogs/driver_form.py`` using PySide6 widgets.
    """

    FIELDS: list[tuple] = [
        ("name",             "driver_manager.field_name",             True),
        ("phone",            "driver_manager.field_phone",            False),
        ("email",            "driver_manager.field_email",            False),
        ("license_number",   "driver_manager.field_license_number",   False),
        ("license_category", "driver_manager.field_license_category", False),
        ("license_expiry",   "driver_manager.field_license_expiry",   False),
        ("medical_expiry",   "driver_manager.field_medical_expiry",   False),
        ("hire_date",        "driver_manager.field_hire_date",        False),
        ("monthly_salary",   "driver_manager.field_monthly_salary",   False),
        ("notes",            "driver_manager.field_notes",            False),
    ]

    def __init__(
        self,
        parent: QWidget | None,
        driver_repo: DriverRepository,
        driver: dict[str, Any] | None = None,
        on_save=None,
        dta_service: DriverTruckService | None = None,
    ):
        super().__init__(parent)
        self._repo = driver_repo
        self._driver = driver
        self._on_save = on_save
        self._dta_service = dta_service

        self._editing = driver is not None
        self.setWindowTitle(
            t("driver_manager.edit_driver") if self._editing else t("driver_manager.add_driver"),
        )
        self.setMinimumSize(480, 600)
        self.setModal(True)

        self._entries: dict[str, StyledLineEdit] = {}
        self._truck_combo: StyledComboBox | None = None
        self._truck_ids: list[str] = []
        self._truck_names: list[str] = []
        self._active_values: list[str] = []

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from ui.widgets import ScrollableFormContainer

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=480)
        layout.addWidget(scroll, 1)

        d = self._driver or {}

        for key, i18n_key, _required in self.FIELDS:
            entry = StyledLineEdit()
            val = d.get(key, "")
            if val is not None:
                entry.setText(str(val))
            self._entries[key] = entry
            fw = field(scroll.content, t(i18n_key), entry)
            scroll.add_widget(fw)

        # ── Truck assignment dropdown ──────────────────────────────────────
        if self._dta_service:
            self._truck_names = [""]
            self._truck_ids = [""]
            try:
                # Prefer the injected driver/truck service's own truck list in
                # remote mode; fall back to the local FleetRepository when a DB
                # is available.  The guard only blocks the remote + no-DB case
                # where no truck-list source exists.
                repo_db = getattr(self._repo, "db", None)
                if repo_db is not None:
                    from repositories.fleet_repository import FleetRepository

                    # Guard: local-only operation (FleetRepository instantiation)
                    mode = detect_mode(repo_db, None)
                    if mode == ConnectionMode.REMOTE:
                        guard_local_access(mode, "Driver form — truck assignment dropdown")

                    fleet_repo = FleetRepository(repo_db)
                    for tr in fleet_repo.get_active_trucks():
                        self._truck_ids.append(str(tr["id"]))
                        self._truck_names.append(tr["plate_number"])
                elif hasattr(self._repo, "get_active_trucks"):
                    for tr in self._repo.get_active_trucks():
                        self._truck_ids.append(str(tr["id"]))
                        self._truck_names.append(tr["plate_number"])
            except Exception:
                pass

            self._truck_combo = StyledComboBox(
                self,
                values=self._truck_names,
                state="readonly",
            )

            if d and self._dta_service:
                assigned_plate = self._dta_service.get_truck_plate_for_driver(
                    d.get("id", 0)
                )
                if assigned_plate and assigned_plate in self._truck_names:
                    idx = self._truck_names.index(assigned_plate)
                    self._truck_combo.setCurrentIndex(idx)

            fw = field(scroll.content, t("driver_manager.col_truck"), self._truck_combo)
            scroll.add_widget(fw)

        # ── Active checkbox ────────────────────────────────────────────────
        from ui.widgets import StyledCheckBox

        self._active_cb = StyledCheckBox(self, text=t("driver_manager.field_active"))
        is_active = d.get("is_active", 1)
        self._active_cb.setChecked(bool(is_active))
        scroll.add_widget(self._active_cb)

        scroll.add_stretch()

        # ── Button bar ─────────────────────────────────────────────────────
        btn_bar = QFrame()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(SP["5"], SP["3"], SP["5"], SP["4"])

        cancel_btn = Btn(
            btn_bar,
            t("driver_manager.cancel"),
            variant="secondary",
            command=self.reject,
        )
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        save_btn = Btn(
            btn_bar,
            t("driver_manager.save"),
            variant="primary",
            command=self._save,
        )
        btn_layout.addWidget(save_btn)

        layout.addWidget(btn_bar)

    # ── Save logic ─────────────────────────────────────────────────────────

    def _save(self) -> None:
        name = self._entries["name"].text().strip()
        if not name:
            QMessageBox.warning(
                self,
                t("common.warning"),
                t("driver_manager.field_name"),
            )
            return

        salary_text = self._entries["monthly_salary"].text().strip()
        try:
            salary = float(salary_text) if salary_text else 0.0
        except ValueError:
            QMessageBox.warning(
                self,
                t("common.warning"),
                t("driver_manager.field_monthly_salary"),
            )
            return

        data: dict[str, Any] = {
            k: v.text().strip() for k, v in self._entries.items()
        }
        data["monthly_salary"] = salary
        data["is_active"] = 1 if self._active_cb.isChecked() else 0

        try:
            if self._editing and self._driver is not None:
                driver_id = self._driver["id"]
                self._repo.update(driver_id, data)
            else:
                driver_id = self._repo.create(data)

            # Truck assignment
            if self._dta_service and self._truck_combo is not None:
                selected_label = self._truck_combo.currentText()
                try:
                    selected_idx = self._truck_names.index(selected_label)
                except ValueError:
                    selected_idx = -1
                if selected_idx >= 0:
                    truck_id_str = self._truck_ids[selected_idx]
                    if truck_id_str:
                        self._dta_service.assign_driver_to_truck(
                            driver_id, int(truck_id_str)
                        )
                    else:
                        self._dta_service.unassign_driver(driver_id)

            # Publish event
            bus = EventBus()
            if self._editing:
                bus.publish(DRIVER_UPDATED, {"driver_id": driver_id})
            else:
                bus.publish(DRIVER_CREATED, {"driver_id": driver_id})

            if self._on_save is not None:
                self._on_save()

            self.accept()
        except Exception as ex:
            logger.exception("Save driver failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )


# ── Main view ──────────────────────────────────────────────────────────────────


class QtDriverManager(BaseView):
    """Driver management view for embedding in ``QStackedWidget``.

    Provides KPI cards, a searchable driver table, CRUD operations,
    CSV import/export, and a tachograph detail panel on row selection.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: dict | None = None,
        driver_svc=None,
        trip_svc=None,
        dta_svc=None,
        tacho_repo=None,
    ):
        super().__init__(parent)
        self.db = db
        self._prefs = prefs or {}
        self._event_bus = EventBus()
        self._driver_repo = driver_svc
        self._trip_repo = trip_svc
        self._dta_service = dta_svc
        self._tacho_activity_repo = tacho_repo

        # Mode guard — conditional: remote mode is only blocked when no driver
        # service was injected.  With a ``RemoteDriverService`` the view is
        # remote-capable.  When a remote-capable service is injected the mode
        # is REMOTE outright — skip ``detect_mode(db, None)`` so it cannot log
        # the spurious "degraded mode" warning (db is None in remote mode).
        if db is None and self._driver_repo is not None:
            self._mode = ConnectionMode.REMOTE
        else:
            self._mode = detect_mode(db, None)
        if self._mode == ConnectionMode.REMOTE and self._driver_repo is None:
            guard_local_access(self._mode, "Driver manager")

        self._kpi_value_labels: dict[str, MonoLabel] = {}
        self._kpi_strip_layout: QHBoxLayout | None = None


        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        self._build_ui()
        self._subscribe_events()
        self.refresh()

        self.destroyed.connect(self._cleanup)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Called when this view becomes active in a QStackedWidget."""
        self.refresh()

    def shutdown(self) -> None:
        """Called when this view is hidden / removed from the stack."""
        if hasattr(self, "_search_timer") and self._search_timer is not None:
            self._search_timer.stop()
        super().shutdown()

    def _cleanup(self) -> None:
        self.shutdown()

    # ── EventBus subscriptions ─────────────────────────────────────────────

    def _subscribe_events(self) -> None:
        for evt in (DRIVER_CREATED, DRIVER_UPDATED, DRIVER_DELETED, TRUCK_UPDATED):
            self._subscribe(evt, self._on_bus_event)

    def _on_bus_event(self, ev: dict) -> None:
        """Schedule a refresh on the UI thread after any relevant event."""
        with contextlib.suppress(Exception):
            QTimer.singleShot(0, self.refresh)

    # ── i18n ───────────────────────────────────────────────────────────────

    def _on_language_changed(self, _lang: str) -> None:
        self.refresh_translations()

    def refresh_translations(self) -> None:
        """Update all translatable UI strings."""
        labels = _resolve_column_labels()
        self.table.setHorizontalHeaderLabels(labels)

        self._search_entry.setPlaceholderText(t("driver_manager.search_placeholder"))
        self._title_label.setText(t("driver_manager.title"))

        self._add_btn.setText("+ " + t("driver_manager.add_driver"))
        self._edit_btn.setText(t("driver_manager.edit_driver"))
        self._delete_btn.setText(t("driver_manager.delete_driver"))
        self._documents_btn.setText(t("driver_manager.documents_button"))
        self._import_btn.setText(t("driver_manager.import_csv"))

        # KPIs are rebuilt on full refresh; title is set at construction time

        self.refresh()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setAccessibleName("Driver manager")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["4"])

        self._kpi_title_refs: list[tuple] = []

        self._build_header(layout)
        self._build_kpi_row(layout)
        self._build_search_bar(layout)
        self._build_table(layout)
        self._build_action_bar(layout)
        self._build_tacho_detail(layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        header_layout.setSpacing(SP["3"])

        self._title_label = PageTitle(None, t("driver_manager.title"))
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        self._import_btn = Btn(
            self,
            t("driver_manager.import_csv"),
            variant="secondary",
            command=self._import_csv,
        )
        header_layout.addWidget(self._import_btn)

        parent_layout.addWidget(header)

    def _build_kpi_row(self, parent_layout: QVBoxLayout) -> None:
        kpi_row = QFrame()
        self._kpi_strip_layout = QHBoxLayout(kpi_row)
        self._kpi_strip_layout.setContentsMargins(0, 0, 0, 0)
        self._kpi_strip_layout.setSpacing(SP["3"])

        self._kpi_value_labels = {}
        self._kpi_title_refs = []

        kpi_configs = [
            ("driver_manager.kpi_total",      "0"),
            ("driver_manager.kpi_expiring",    "0"),
            ("driver_manager.kpi_on_trip",     "0"),
            ("driver_manager.kpi_unassigned",  "0"),
        ]

        for title_key, initial_value in kpi_configs:
            card = KPICard(kpi_row, t(title_key), initial_value)
            val_lbl = card.findChild(QLabel, "kpi-value")
            if val_lbl is not None:
                self._kpi_value_labels[title_key] = val_lbl
            self._kpi_title_refs.append((title_key, card))
            self._kpi_strip_layout.addWidget(card)

        parent_layout.addWidget(kpi_row)

    def _build_search_bar(self, parent_layout: QVBoxLayout) -> None:
        search_row = QFrame()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self._search_entry = DebouncedLineEdit(
            placeholder=t("driver_manager.search_placeholder"),
        )
        self._search_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._search_entry.debouncedTextChanged.connect(self._filter_table)

        search_layout.addWidget(self._search_entry, 1)

        parent_layout.addWidget(search_row)

    def _build_table(self, parent_layout: QVBoxLayout) -> None:
        columns = _columns_for_table()
        card = Card(None)
        title = SectionTitle(None, t("driver_manager.title"))
        card.layout().addWidget(title)
        self.table = StyledTableWidget(
            self, columns=columns, prefs_key="driver_manager",
        )
        self.table.setAccessibleName("Drivers table")
        self.table.setAccessibleDescription("Use arrow keys to navigate. Press Enter to select.")
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        # Add an extra column for inline action buttons
        extra_col = self.table.columnCount()
        self.table.setColumnCount(extra_col + 1)
        self.table.setHorizontalHeaderItem(extra_col, QTableWidgetItem(""))
        self.table.setColumnWidth(extra_col, 70)
        self.table.rowSelected.connect(self._on_row_selected)
        self.table.rowDoubleClicked.connect(self._on_row_double_clicked)
        card.layout().addWidget(self.table, 1)
        parent_layout.addWidget(card, 1)

    def _build_action_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)

        self._add_btn = Btn(
            self,
            "+ " + t("driver_manager.add_driver"),
            variant="primary",
            command=self._add_driver,
        )
        bar_layout.addWidget(self._add_btn)

        self._edit_btn = Btn(
            self,
            t("driver_manager.edit_driver"),
            variant="secondary",
            command=self._edit_selected,
        )
        bar_layout.addWidget(self._edit_btn)

        bar_layout.addStretch()

        # Density toggle
        density_btn = IconButton(
            self,
            icon_name="fa5s.table",
            tooltip=t("driver_manager.density_toggle", default="Row density"),
            variant="ghost",
            size=32,
        )
        density_menu = self.table._build_density_menu(density_btn)
        density_btn.setMenu(density_menu)
        bar_layout.addWidget(density_btn)

        self._documents_btn = Btn(
            self,
            t("driver_manager.documents_button"),
            variant="secondary",
            icon_name="fa5s.folder-open",
            command=self._open_driver_documents,
        )
        bar_layout.addWidget(self._documents_btn)

        self._delete_btn = Btn(
            self,
            t("driver_manager.delete_driver"),
            variant="danger",
            command=self._delete_selected,
        )
        bar_layout.addWidget(self._delete_btn)

        parent_layout.addWidget(bar)

    def _build_tacho_detail(self, parent_layout: QVBoxLayout) -> None:
        """Collapsible tachograph detail panel shown on driver selection."""
        self._tacho_container = QFrame()
        self._tacho_container.setProperty("role", "tacho-detail")
        self._tacho_layout = QVBoxLayout(self._tacho_container)
        self._tacho_layout.setContentsMargins(0, 0, 0, 0)
        self._tacho_layout.setSpacing(SP["2"])
        self._tacho_container.hide()
        parent_layout.addWidget(self._tacho_container)

    # ── Selection handlers ─────────────────────────────────────────────────

    def _on_row_selected(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._show_driver_tacho_detail()

    def _on_row_double_clicked(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._edit_selected()

    def _get_selected_id(self) -> int | None:
        row = self.table.selected_row_data()
        if row is None:
            QMessageBox.information(
                self,
                t("driver_manager.title"),
                t("driver_manager.no_driver_selected"),
            )
            return None
        return row.get("id")

    # ── Data loading ───────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload driver data from the database and update the UI.

        Shows a skeleton table placeholder immediately, then schedules
        the actual data load on the next event loop iteration.
        """
        if self._driver_repo is None or self._trip_repo is None:
            return

        self._show_table_skeleton()
        QTimer.singleShot(0, self._load_data)

    def _show_table_skeleton(self) -> None:
        """Replace the real table with a skeleton table placeholder."""
        from ui.skeleton_widgets import SkeletonTable

        # Hide real table
        self.table.hide()

        # Remove old skeleton if present
        if hasattr(self, '_table_skel') and self._table_skel is not None:
            self._table_skel.deleteLater()
            self._table_skel = None

        # Find the card that contains the table and insert skeleton
        parent_card = self.table.parent()
        if parent_card is not None and parent_card.layout() is not None:
            skel = SkeletonTable(parent_card, rows=5, columns=7)
            skel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # Insert before the table in the card's layout
            idx = parent_card.layout().indexOf(self.table)
            parent_card.layout().insertWidget(idx, skel, 1)
            self._table_skel = skel

    def _hide_table_skeleton(self) -> None:
        """Remove skeleton table and show the real table."""
        if hasattr(self, '_table_skel') and self._table_skel is not None:
            self._table_skel.deleteLater()
            self._table_skel = None
        self.table.show()

    def _load_data(self) -> None:
        """Fetch driver data and populate the real table."""
        with PerfTimer("driver_manager.refresh"):
            try:
                drivers = self._driver_repo.get_all(limit=500)
                active_trips = self._trip_repo.get_by_statuses(["Loading", "In Transit"])

                driver_trip_ids: set = set()
                for trip in active_trips:
                    did = trip.get("driver_id")
                    if did:
                        driver_trip_ids.add(did)

                rows: list[dict[str, Any]] = []
                unassigned_count = 0

                # Single batched lookup for every driver's truck plate instead
                # of N sequential JOIN queries (``get_truck_plate_for_driver``).
                # Falls back to "all unassigned" if the batch call is unavailable
                # or fails — identical to the legacy per-row empty result.
                plates_by_driver: dict[int, str] = {}
                if self._dta_service:
                    try:
                        result = self._dta_service.get_plates_by_driver_ids(
                            [d["id"] for d in drivers]
                        )
                        plates_by_driver = result if isinstance(result, dict) else {}
                    except Exception:
                        logger.warning(
                            "Batched driver-truck plate lookup failed; treating all as unassigned",
                            exc_info=True,
                        )
                        plates_by_driver = {}

                for d in drivers:
                    did = d["id"]
                    truck_plate = plates_by_driver.get(did, "") if self._dta_service else ""
                    is_unassigned = not truck_plate
                    if is_unassigned:
                        unassigned_count += 1
                    truck_text = truck_plate or t("driver_manager.unassigned")

                    salary = float(d.get("monthly_salary") or 0)
                    is_active = d.get("is_active", 1)

                    rows.append({
                        "id":             did,
                        "name":           d.get("name", ""),
                        "phone":          d.get("phone", ""),
                        "license":        d.get("license_category", ""),
                        "license_expiry": d.get("license_expiry", ""),
                        "medical_expiry": d.get("medical_expiry", ""),
                        "hire_date":      d.get("hire_date", ""),
                        "salary":         f"{salary:.2f}",
                        "active":         t("common.yes") if is_active else t("common.no"),
                        "truck":          truck_text,
                    })

                # Hide skeleton before populating real data
                self._hide_table_skeleton()

                self.table.set_data(rows)
                self.table.restore_column_widths()

                # ── Inline action buttons ─────────────────────────────────────
                actions_col = self.table.columnCount() - 1
                for r in range(self.table.rowCount()):
                    container = QWidget()
                    container.setContentsMargins(0, 0, 0, 0)
                    row_layout = QHBoxLayout(container)
                    row_layout.setContentsMargins(4, 0, 4, 0)
                    row_layout.setSpacing(2)

                    edit_btn = QPushButton("\u270E")  # pencil
                    edit_btn.setFixedSize(28, 28)
                    edit_btn.setToolTip(t("driver_manager.edit_driver"))
                    edit_btn.setCursor(Qt.PointingHandCursor)
                    edit_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent; border: none;
                            color: {COLOR_TEXT_TERTIARY};
                            font-size: 13px;
                            border-radius: {RADIUS_SM}px;
                        }}
                        QPushButton:hover {{
                            color: {COLOR_TEXT_PRIMARY};
                            background: {COLOR_BG_HOVER};
                        }}
                    """)
                    driver_id = rows[r].get("id") if r < len(rows) else None
                    if driver_id is not None:
                        edit_btn.clicked.connect(
                            lambda checked, did=driver_id: self._edit_driver_by_id(did)
                        )
                    row_layout.addWidget(edit_btn)

                    docs_btn = QPushButton("\U0001F4C2")  # folder-open
                    docs_btn.setFixedSize(28, 28)
                    docs_btn.setToolTip(t("driver_manager.documents_button"))
                    docs_btn.setCursor(Qt.PointingHandCursor)
                    docs_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent; border: none;
                            color: {COLOR_TEXT_TERTIARY};
                            font-size: 13px;
                            border-radius: {RADIUS_SM}px;
                        }}
                        QPushButton:hover {{
                            color: {COLOR_TEXT_PRIMARY};
                            background: {COLOR_BG_HOVER};
                        }}
                    """)
                    if driver_id is not None:
                        docs_btn.clicked.connect(
                            lambda checked, did=driver_id: self._open_driver_documents_by_id(did)
                        )
                    row_layout.addWidget(docs_btn)

                    # Assign Truck button
                    assign_btn = QPushButton("\U0001F69A")  # truck-moving
                    assign_btn.setFixedSize(28, 28)
                    assign_btn.setToolTip(t("driver_manager.assign_truck", default="Assign Truck"))
                    assign_btn.setCursor(Qt.PointingHandCursor)
                    assign_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent; border: none;
                            color: {COLOR_TEXT_TERTIARY};
                            font-size: 13px;
                            border-radius: {RADIUS_SM}px;
                        }}
                        QPushButton:hover {{
                            color: {COLOR_TEXT_PRIMARY};
                            background: {COLOR_BG_HOVER};
                        }}
                    """)
                    if driver_id is not None:
                        assign_btn.clicked.connect(
                            lambda checked, did=driver_id: self._assign_truck(did)
                        )
                    row_layout.addWidget(assign_btn)

                    self.table.setCellWidget(r, actions_col, container)

                # ── KPI updates ───────────────────────────────────────────────
                total = len(drivers)
                active_count = sum(1 for d in drivers if d.get("is_active", 1))

                if "driver_manager.kpi_total" in self._kpi_value_labels:
                    self._kpi_value_labels["driver_manager.kpi_total"].setText(str(total))
                if "driver_manager.kpi_on_trip" in self._kpi_value_labels:
                    self._kpi_value_labels["driver_manager.kpi_on_trip"].setText(str(len(driver_trip_ids)))

                cutoff = datetime.now() + timedelta(days=30)
                expiring = 0
                for d in drivers:
                    if d.get("is_active", 1):
                        for field_name in ("license_expiry", "medical_expiry"):
                            val = d.get(field_name, "")
                            if val:
                                try:
                                    dt_val = datetime.strptime(val, "%Y-%m-%d")
                                    if dt_val <= cutoff:
                                        expiring += 1
                                        break
                                except ValueError:
                                    pass
                if "driver_manager.kpi_expiring" in self._kpi_value_labels:
                    self._kpi_value_labels["driver_manager.kpi_expiring"].setText(str(expiring))
                if "driver_manager.kpi_unassigned" in self._kpi_value_labels:
                    self._kpi_value_labels["driver_manager.kpi_unassigned"].setText(str(unassigned_count))

                # ── Grey out inactive rows ────────────────────────────────────
                muted = QColor(COLOR_TEXT_TERTIARY)
                for r, row in enumerate(rows):
                    if row.get("active") == t("common.no"):
                        for c in range(self.table.columnCount()):
                            item = self.table.item(r, c)
                            if item is not None:
                                item.setForeground(muted)

                self._filter_table()

            except Exception as ex:
                logger.exception("refresh drivers failed")
                self._hide_table_skeleton()
                QMessageBox.critical(
                    self,
                    t("main.error_title"),
                    str(ex),
                )

    def _filter_table(self) -> None:
        """Filter visible rows based on search text."""
        query = self._search_entry.text().strip().lower()
        for r in range(self.table.rowCount()):
            visible = False
            if not query:
                visible = True
            else:
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    if item is not None and query in item.text().lower():
                        visible = True
                        break
            self.table.setRowHidden(r, not visible)

    # ── CRUD actions ───────────────────────────────────────────────────────

    def _add_driver(self) -> None:
        if self._driver_repo is None:
            return
        dialog = QtDriverFormDialog(
            self,
            self._driver_repo,
            driver=None,
            on_save=self.refresh,
            dta_service=self._dta_service,
        )
        dialog.exec()

    def _edit_selected(self) -> None:
        if self._driver_repo is None:
            return
        driver_id = self._get_selected_id()
        if driver_id is None:
            return
        self._edit_driver_by_id(driver_id)

    def _edit_driver_by_id(self, driver_id: int) -> None:
        """Open the edit dialog for a specific driver ID."""
        if self._driver_repo is None:
            return
        row = self._driver_repo.get_by_id(driver_id)
        if row is None:
            QMessageBox.information(
                self,
                t("driver_manager.title"),
                t("driver_manager.no_driver_selected"),
            )
            return
        dialog = QtDriverFormDialog(
            self,
            self._driver_repo,
            driver=row,
            on_save=self.refresh,
            dta_service=self._dta_service,
        )
        dialog.exec()

    def _delete_selected(self) -> None:
        driver_id = self._get_selected_id()
        if driver_id is None:
            return

        reply = QMessageBox.question(
            self,
            t("driver_manager.delete_driver"),
            t("driver_manager.confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if self._dta_service is not None:
                self._dta_service.unassign_driver(driver_id)
            self._driver_repo.delete(driver_id)
            self._event_bus.publish(DRIVER_DELETED, {"driver_id": driver_id})
            self.refresh()
        except Exception as ex:
            logger.exception("Delete driver failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    def _toggle_active(self) -> None:
        """Toggle the active state of the selected driver."""
        if self._driver_repo is None:
            return
        driver_id = self._get_selected_id()
        if driver_id is None:
            return
        row = self._driver_repo.get_by_id(driver_id)
        if row is None:
            return
        new_active = 0 if row.get("is_active", 1) else 1
        self._driver_repo.update(driver_id, {"is_active": new_active})
        self._event_bus.publish(
            DRIVER_UPDATED,
            {"driver_id": driver_id, "is_active": new_active},
        )
        self.refresh()

    # ── Assign Truck ───────────────────────────────────────────────────────

    def _assign_truck(self, driver_id: int) -> None:
        """Show a truck selection dialog and assign the chosen truck to the driver."""
        if self._dta_service is None:
            QMessageBox.information(
                self,
                t("driver_manager.assign_truck", default="Assign Truck"),
                t("driver_manager.no_dta_service", default="Truck assignment is not available."),
            )
            return
        try:
            trucks = []
            # Prefer the injected driver service's own truck list in remote
            # mode (a ``RemoteDriverService`` may expose ``get_active_trucks``);
            # fall back to the local ``FleetRepository`` when a DB is present.
            if getattr(self._driver_repo, "get_active_trucks", None) is not None:
                trucks = self._driver_repo.get_active_trucks()
            elif self.db is not None:
                from repositories.fleet_repository import FleetRepository
                fleet_repo = FleetRepository(self.db)
                trucks = fleet_repo.get_active_trucks()
            else:
                QMessageBox.information(
                    self,
                    t("driver_manager.assign_truck", default="Assign Truck"),
                    t("driver_manager.no_trucks_available", default="No active trucks available."),
                )
                return
        except Exception as ex:
            logger.exception("Failed to load trucks")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )
            return

        if not trucks:
            QMessageBox.information(
                self,
                t("driver_manager.assign_truck", default="Assign Truck"),
                t("driver_manager.no_trucks_available", default="No active trucks available."),
            )
            return

        # Build a list of truck display strings
        truck_names = []
        truck_ids = []
        for t in trucks:
            label = t.get("plate_number", f"Truck #{t['id']}")
            truck_names.append(label)
            truck_ids.append(t["id"])

        # Pre-select current assignment
        current_plate = self._dta_service.get_truck_plate_for_driver(driver_id)
        default_idx = 0
        if current_plate:
            try:
                default_idx = truck_names.index(current_plate) + 1  # +1 for empty option
            except ValueError:
                default_idx = 0

        # Add an "Unassign" option at the top
        unassign_label = t("driver_manager.unassign_truck", default="— Unassign —")
        truck_names.insert(0, unassign_label)
        truck_ids.insert(0, None)

        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel
        from ui.widgets import StyledComboBox

        dlg = QDialog(self)
        dlg.setWindowTitle(t("driver_manager.assign_truck", default="Assign Truck"))
        dlg.setMinimumWidth(320)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(SP["3"])
        layout.setContentsMargins(SP["5"], SP["4"], SP["5"], SP["4"])

        lbl = QLabel(
            t("driver_manager.select_truck", default="Select a truck to assign:")
        )
        layout.addWidget(lbl)

        combo = StyledComboBox(dlg, values=truck_names)
        combo.setCurrentIndex(default_idx)
        layout.addWidget(combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.Accepted:
            idx = combo.currentIndex()
            if 0 <= idx < len(truck_ids):
                selected_id = truck_ids[idx]
                try:
                    if selected_id is None:
                        self._dta_service.unassign_driver(driver_id)
                    else:
                        self._dta_service.assign_driver_to_truck(
                            driver_id, int(selected_id)
                        )
                    from services.operations.event_bus import (
                        DRIVER_UPDATED,
                        EventBus,
                    )
                    EventBus().publish(DRIVER_UPDATED, {"driver_id": driver_id})
                    self.refresh()
                except Exception as ex:
                    logger.exception("Failed to assign truck")
                    QMessageBox.critical(
                        self,
                        t("main.error_title"),
                        str(ex),
                    )

    # ── CSV import / export ────────────────────────────────────────────────

    def _import_csv(self) -> None:
        """Import drivers from a CSV file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("driver_manager.import_csv"),
            "",
            f"{t('common.csv_filter')} (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    name = row.get("name", "").strip()
                    if not name:
                        continue
                    data: dict[str, Any] = {
                        "name": name,
                        "phone": row.get("phone", "").strip(),
                        "email": row.get("email", "").strip(),
                        "license_number": row.get("license_number", "").strip(),
                        "license_category": row.get("license_category", "").strip(),
                        "license_expiry": row.get("license_expiry", "").strip(),
                        "medical_expiry": row.get("medical_expiry", "").strip(),
                        "hire_date": row.get("hire_date", "").strip(),
                        "notes": row.get("notes", "").strip(),
                    }
                    try:
                        salary = float(row.get("monthly_salary", 0) or 0)
                    except ValueError:
                        salary = 0.0
                    data["monthly_salary"] = salary
                    data["is_active"] = 1

                    self._driver_repo.create(data)
                    count += 1

            QMessageBox.information(
                self,
                t("driver_manager.import_csv"),
                t("driver_manager.import_success").format(count=count),
            )
            self.refresh()
        except Exception as ex:
            logger.exception("CSV import failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    def _export_csv(self) -> None:
        """Export driver list to a CSV file."""
        if self._driver_repo is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("driver_manager.export_csv"),
            "",
            f"{t('common.csv_filter')} (*.csv)",
        )
        if not path:
            return

        try:
            drivers = self._driver_repo.get_all(limit=10000)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow([
                    t("common.id"),
                    t("driver_manager.col_name"),
                    t("driver_manager.col_phone"),
                    t("driver_manager.col_license"),
                    t("driver_manager.col_license_expiry"),
                    t("driver_manager.col_medical_expiry"),
                    t("driver_manager.col_hire_date"),
                    t("driver_manager.col_salary"),
                    t("driver_manager.col_active"),
                ])
                for d in drivers:
                    w.writerow([
                        d.get("id"),
                        d.get("name"),
                        d.get("phone"),
                        d.get("license_category"),
                        d.get("license_expiry"),
                        d.get("medical_expiry"),
                        d.get("hire_date"),
                        d.get("monthly_salary"),
                        d.get("is_active"),
                    ])

            QMessageBox.information(
                self,
                t("driver_manager.export_csv"),
                t("driver_manager.export_success"),
            )
        except Exception as ex:
            logger.exception("CSV export failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    # ── Documents ──────────────────────────────────────────────────────────

    def _open_driver_documents_by_id(self, driver_id: int) -> None:
        """Open the document centre for a specific driver ID."""
        if self._driver_repo is None:
            return
        try:
            from ui.views.document_center_view import open_entity_documents

            driver = self._driver_repo.get_by_id(driver_id)
            name = driver.get("name", "Unknown") if driver else "Unknown"
            open_entity_documents(
                self,
                self.db,
                "driver",
                driver_id,
                t("driver_manager.driver_title", default="Driver {}").format(name),
            )
        except Exception as ex:
            logger.exception("Open driver documents failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    def _open_driver_documents(self) -> None:
        """Open the document centre for the selected driver."""
        driver_id = self._get_selected_id()
        if driver_id is None:
            QMessageBox.information(
                self,
                t("driver_manager.documents_button"),
                t("driver_manager.select_driver_first"),
            )
            return
        try:
            from ui.views.document_center_view import open_entity_documents

            driver = self._driver_repo.get_by_id(driver_id)
            name = driver.get("name", "Unknown") if driver else "Unknown"
            open_entity_documents(
                self,
                self.db,
                "driver",
                driver_id,
                t("driver_manager.driver_title", default="Driver {}").format(name),
            )
        except Exception as ex:
            logger.exception("Open driver documents failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    # ── Tachograph detail panel ────────────────────────────────────────────

    def _show_driver_tacho_detail(self) -> None:
        """Display a tachograph activity summary for the selected driver."""
        # Clear previous content — use takeAt to properly remove layout items
        while self._tacho_layout.count():
            item = self._tacho_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()

        if self._selected_id is None:
            self._tacho_container.hide()
            return

        driver_id = self._selected_id

        # Title
        title_lbl = QLabel(t("tacho.driver_activity_title"))
        title_lbl.setProperty("fontRole", "h3")
        self._tacho_layout.addWidget(title_lbl)

        try:
            from_date = datetime.now().date() - timedelta(days=28)
            records = self._tacho_activity_repo.get_by_driver(driver_id, from_date)
        except Exception:
            records = []

        if not records:
            no_data_lbl = QLabel(t("tacho.no_activity"))
            no_data_lbl.setProperty("fontRole", "small")
            self._tacho_layout.addWidget(no_data_lbl)
            self._tacho_container.show()
            return

        # ── Summary row ───────────────────────────────────────────────────
        total_driving = sum(
            r.get("driving_minutes", 0) or 0 for r in records
        )
        avg_daily = total_driving / 60 / len(records) if records else 0
        total_violations = sum(
            len(json.loads(r.get("violations") or "[]")) for r in records
        )

        summary_frame = QFrame()
        summary_frame.setProperty("role", "tacho-summary")
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["2"])
        summary_layout.setSpacing(SP["3"])

        summary_items = [
            (t("tacho.total_hours"), f"{total_driving / 60:.1f}h",
             None),
            (t("tacho.avg_daily"), f"{avg_daily:.1f}h",
             None),
            (t("tacho.violations"), str(total_violations),
             COLOR_ERROR_DEFAULT if total_violations > 0 else COLOR_SUCCESS_DEFAULT),
        ]
        for label_text, value_text, color in summary_items:
            chip = self._summary_chip(summary_frame, label_text, value_text, color)
            summary_layout.addWidget(chip)

        self._tacho_layout.addWidget(summary_frame)

        # ── Mini activity chart (last 14 days) ────────────────────────────
        chart_label = QLabel(t("tacho.last_14_days"))
        chart_label.setProperty("fontRole", "small")
        self._tacho_layout.addWidget(chart_label)

        # Delete old scene and view before creating new ones to prevent
        # memory leak (each driver selection previously leaked a scene).
        if hasattr(self, "_tacho_scene") and self._tacho_scene is not None:
            self._tacho_scene.deleteLater()
        if hasattr(self, "_tacho_chart_view") and self._tacho_chart_view is not None:
            self._tacho_chart_view.deleteLater()

        last_14 = records[:14] if len(records) >= 14 else records
        scene = QGraphicsScene(self)
        self._tacho_scene = scene
        bar_width = 18
        spacing = 2
        chart_height = 60

        for i, r in enumerate(reversed(last_14)):
            driving_h = (r.get("driving_minutes", 0) or 0) / 60
            if driving_h <= 9:
                bar_color = COLOR_SUCCESS_DEFAULT
            elif driving_h <= 10:
                bar_color = COLOR_WARNING_DEFAULT
            else:
                bar_color = COLOR_ERROR_DEFAULT

            bar_h = min(int(driving_h * 6), chart_height)
            x = i * (bar_width + spacing)

            rect = QGraphicsRectItem(x, chart_height - bar_h, bar_width, bar_h)
            rect.setBrush(QColor(bar_color))
            rect.setPen(Qt.NoPen)
            scene.addItem(rect)

            date_str = str(r.get("activity_date", ""))[5:]  # mm-dd
            text_item = scene.addText(date_str)
            text_item.setDefaultTextColor(QColor(COLOR_TEXT_TERTIARY))
            text_item.setPos(x, chart_height + 2)

        view = QGraphicsView(scene)
        self._tacho_chart_view = view
        view.setFixedHeight(chart_height + 24)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet("background: transparent; border: none;")
        self._tacho_layout.addWidget(view)

        # ── Last 5 violations ────────────────────────────────────────────
        violations: list[tuple] = []
        for r in records:
            vlist = json.loads(r.get("violations") or "[]")
            for v in vlist:
                violations.append((r.get("activity_date", ""), v))

        if violations:
            viol_label = QLabel(t("tacho.recent_violations"))
            viol_label.setProperty("fontRole", "small")
            self._tacho_layout.addWidget(viol_label)

            for date_str, v in violations[:5]:
                row_frame = QFrame()
                row_frame.setProperty("role", "tacho-violation-row")
                row_layout = QHBoxLayout(row_frame)
                row_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])

                date_lbl = QLabel(str(date_str))
                date_lbl.setProperty("fontRole", "small")
                date_lbl.setFixedWidth(90)
                row_layout.addWidget(date_lbl)

                viol_lbl = QLabel(v)
                viol_lbl.setProperty("fontRole", "small")
                viol_lbl.setStyleSheet(f"color: {COLOR_ERROR_DEFAULT};")
                viol_lbl.setWordWrap(True)
                row_layout.addWidget(viol_lbl, 1)

                self._tacho_layout.addWidget(row_frame)

        self._tacho_container.show()

    def _summary_chip(
        self,
        parent: QWidget,
        label_text: str,
        value_text: str,
        color: str | None = None,
    ) -> QFrame:
        """Create a summary chip label-value pair."""
        chip = QFrame(parent)
        chip.setProperty("role", "tacho-chip")
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])
        chip_layout.setSpacing(0)

        lbl = QLabel(label_text.upper())
        lbl.setProperty("fontRole", "label")
        chip_layout.addWidget(lbl)

        val = QLabel(value_text)
        val.setProperty("fontRole", "body-bold")
        if color:
            val.setStyleSheet(f"color: {color};")
        chip_layout.addWidget(val)

        return chip

    # ── Context menu (right-click) ─────────────────────────────────────────

    def contextMenuEvent(self, event) -> None:
        """Show a context menu on right-click over the table."""
        row_data = self.table.selected_row_data()
        if row_data is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLOR_BG_ELEVATED};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
            }}
            QMenu::item:selected {{
                background-color: {COLOR_ACCENT_SUBTLE};
            }}
        """)

        edit_action = QAction(t("driver_manager.edit_driver"), self)
        edit_action.triggered.connect(self._edit_selected)
        menu.addAction(edit_action)

        toggle_action = QAction(t("driver_manager.toggle_active"), self)
        toggle_action.triggered.connect(self._toggle_active)
        menu.addAction(toggle_action)

        menu.addSeparator()

        delete_action = QAction(t("driver_manager.delete_driver"), self)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)

        menu.exec(event.globalPos())
