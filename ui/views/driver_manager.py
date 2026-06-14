"""PySide6 driver management view.

Replaces ``ui/driver_manager.py``. Displays KPI cards, a searchable
driver table, and CRUD operations via a form dialog. Embeds in a
``QStackedWidget`` via the ``wakeup`` / ``shutdown`` lifecycle.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPainter
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from repositories.driver_repository import DriverRepository
from repositories.trip_repository import TripRepository
from services.driver_truck_service import DriverTruckService
from services.i18n import t, register_listener, unregister_listener
from services.operations.event_bus import (
    EventBus,
    DRIVER_CREATED,
    DRIVER_UPDATED,
    DRIVER_DELETED,
    TRUCK_UPDATED,
)
from ui.theme import COLORS, S
from ui.widgets import (
    ActionButton,
    KpiCard,
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    field,
)

logger = logging.getLogger(__name__)


# ── Column definitions ─────────────────────────────────────────────────────────
# (column_id,  i18n_key_or_raw_label,  width_px,  translate)

_COLUMNS: List[tuple] = [
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


def _resolve_column_labels() -> List[str]:
    """Return translated header labels for the current language."""
    return [t(key) if translate else key for _, key, _, translate in _COLUMNS]


def _columns_for_table() -> List[tuple]:
    """Return ``(cid, label, width)`` tuples for ``StyledTableWidget``."""
    labels = _resolve_column_labels()
    return [(cid, labels[i], width) for i, (cid, _, width, _) in enumerate(_COLUMNS)]


# ── Search line edit (focus-driven placeholder) ────────────────────────────────


class _SearchLineEdit(StyledLineEdit):
    """Single-line input with focus-driven placeholder behaviour.

    Mirrors the original ``ui/driver_manager.py`` pattern where the
    placeholder is shown as actual text and cleared on focus.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._placeholder: str = ""
        self._user_typed: bool = False

    # ── Public API ─────────────────────────────────────────────────────────

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        if not self._user_typed:
            blocked = self.blockSignals(True)
            self.setText(text)
            self.blockSignals(blocked)

    def search_value(self) -> str:
        if not self._user_typed:
            return ""
        return self.text().strip()

    # ── Event overrides ────────────────────────────────────────────────────

    def focusInEvent(self, event) -> None:
        if not self._user_typed:
            self.clear()
        self._user_typed = True
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if not self.text().strip():
            self._user_typed = False
            blocked = self.blockSignals(True)
            self.setText(self._placeholder)
            self.blockSignals(blocked)
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:
        self._user_typed = True
        super().keyPressEvent(event)


# ── Driver form dialog (add / edit) ────────────────────────────────────────────


class QtDriverFormDialog(QDialog):
    """Add / edit driver dialog.

    Mirrors ``ui/dialogs/driver_form.py`` using PySide6 widgets.
    """

    FIELDS: List[tuple] = [
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
        parent: Optional[QWidget],
        driver_repo: DriverRepository,
        driver: Optional[Dict[str, Any]] = None,
        on_save=None,
        dta_service: Optional[DriverTruckService] = None,
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

        self._entries: Dict[str, StyledLineEdit] = {}
        self._truck_combo: Optional[StyledComboBox] = None
        self._truck_ids: List[str] = []
        self._truck_names: List[str] = []
        self._active_values: List[str] = []

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
                from repositories.fleet_repository import FleetRepository

                fleet_repo = FleetRepository(self._repo.db)
                for tr in fleet_repo.get_active_trucks():
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
        btn_layout.setContentsMargins(S["5"], S["3"], S["5"], S["4"])

        cancel_btn = ActionButton(
            btn_bar,
            text=t("driver_manager.cancel"),
            command=self.reject,
            variant="secondary",
        )
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        save_btn = ActionButton(
            btn_bar,
            text=t("driver_manager.save"),
            command=self._save,
            variant="success",
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

        data: Dict[str, Any] = {
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


class QtDriverManager(QWidget):
    """Driver management view for embedding in ``QStackedWidget``.

    Provides KPI cards, a searchable driver table, CRUD operations,
    CSV import/export, and a tachograph detail panel on row selection.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs: Optional[dict] = None,
    ):
        super().__init__(parent)
        self.db = db
        self._prefs = prefs or {}

        self._event_bus = EventBus()
        self._driver_repo = DriverRepository(db) if db is not None else None
        self._trip_repo = TripRepository(db) if db is not None else None
        self._dta_service = DriverTruckService(db) if db is not None else None

        self._kpi_cards: List[KpiCard] = []
        self._search_timer: Optional[QTimer] = None

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

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
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        self._unsubscribe_events()

    def _cleanup(self) -> None:
        self.shutdown()

    # ── EventBus subscriptions ─────────────────────────────────────────────

    def _subscribe_events(self) -> None:
        for evt in (DRIVER_CREATED, DRIVER_UPDATED, DRIVER_DELETED, TRUCK_UPDATED):
            self._event_bus.subscribe(evt, self._on_bus_event)

    def _unsubscribe_events(self) -> None:
        for evt in (DRIVER_CREATED, DRIVER_UPDATED, DRIVER_DELETED, TRUCK_UPDATED):
            try:
                self._event_bus.unsubscribe(evt, self._on_bus_event)
            except Exception:
                pass

    def _on_bus_event(self, ev: dict) -> None:
        """Schedule a refresh on the UI thread after any relevant event."""
        try:
            QTimer.singleShot(0, self.refresh)
        except Exception:
            pass

    # ── i18n ───────────────────────────────────────────────────────────────

    def _on_language_changed(self, _lang: str) -> None:
        self.refresh_translations()

    def refresh_translations(self) -> None:
        """Update all translatable UI strings."""
        labels = _resolve_column_labels()
        self.table.setHorizontalHeaderLabels(labels)

        self._search_entry.set_placeholder(t("driver_manager.search_placeholder"))
        self._title_label.setText(t("driver_manager.title"))

        self._add_btn.setText("+ " + t("driver_manager.add_driver"))
        self._edit_btn.setText(t("driver_manager.edit_driver"))
        self._delete_btn.setText(t("driver_manager.delete_driver"))
        self._documents_btn.setText("\U0001f4c2 " + t("driver_manager.documents_button"))
        self._import_btn.setText(t("driver_manager.import_csv"))

        for card, key in self._kpi_title_refs:
            card.set_title(t(key))

        self.refresh()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["5"], S["5"], S["5"], S["5"])
        layout.setSpacing(S["3"])

        self._kpi_title_refs: List[tuple] = []

        self._build_header(layout)
        self._build_kpi_row(layout)
        self._build_search_bar(layout)
        self._build_table(layout)
        self._build_action_bar(layout)
        self._build_tacho_detail(layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel(t("driver_manager.title"))
        self._title_label.setProperty("fontRole", "h2")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        self._import_btn = ActionButton(
            self,
            text=t("driver_manager.import_csv"),
            command=self._import_csv,
            variant="secondary",
        )
        header_layout.addWidget(self._import_btn)

        parent_layout.addWidget(header)

    def _build_kpi_row(self, parent_layout: QVBoxLayout) -> None:
        kpi_row = QFrame()
        kpi_layout = QHBoxLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(S["3"])

        kpi_configs = [
            ("driver_manager.kpi_total",      "0"),
            ("driver_manager.kpi_expiring",    "0"),
            ("driver_manager.kpi_on_trip",     "0"),
            ("driver_manager.kpi_unassigned",  "0"),
        ]

        for title_key, initial_value in kpi_configs:
            card = KpiCard(self, t(title_key), initial_value)
            self._kpi_cards.append(card)
            self._kpi_title_refs.append((card, title_key))
            kpi_layout.addWidget(card)

        parent_layout.addWidget(kpi_row)

    def _build_search_bar(self, parent_layout: QVBoxLayout) -> None:
        search_row = QFrame()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self._search_entry = _SearchLineEdit()
        self._search_entry.set_placeholder(t("driver_manager.search_placeholder"))
        self._search_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Debounced search: 200 ms after last keystroke
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._filter_table)
        self._search_entry.textChanged.connect(self._on_search_debounce)

        search_layout.addWidget(self._search_entry, 1)

        parent_layout.addWidget(search_row)

    def _on_search_debounce(self) -> None:
        if self._search_timer is not None:
            self._search_timer.start(200)

    def _build_table(self, parent_layout: QVBoxLayout) -> None:
        columns = _columns_for_table()
        self.table = StyledTableWidget(self, columns=columns)
        self.table.rowSelected.connect(self._on_row_selected)
        self.table.rowDoubleClicked.connect(self._on_row_double_clicked)
        parent_layout.addWidget(self.table, 1)

    def _build_action_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)

        self._add_btn = ActionButton(
            self,
            text="+ " + t("driver_manager.add_driver"),
            command=self._add_driver,
            variant="success",
        )
        bar_layout.addWidget(self._add_btn)

        self._edit_btn = ActionButton(
            self,
            text=t("driver_manager.edit_driver"),
            command=self._edit_selected,
        )
        bar_layout.addWidget(self._edit_btn)

        bar_layout.addStretch()

        self._documents_btn = ActionButton(
            self,
            text="\U0001f4c2 " + t("driver_manager.documents_button"),
            command=self._open_driver_documents,
        )
        bar_layout.addWidget(self._documents_btn)

        self._delete_btn = ActionButton(
            self,
            text=t("driver_manager.delete_driver"),
            command=self._delete_selected,
            variant="danger",
        )
        bar_layout.addWidget(self._delete_btn)

        parent_layout.addWidget(bar)

    def _build_tacho_detail(self, parent_layout: QVBoxLayout) -> None:
        """Collapsible tachograph detail panel shown on driver selection."""
        self._tacho_container = QFrame()
        self._tacho_container.setProperty("role", "tacho-detail")
        self._tacho_layout = QVBoxLayout(self._tacho_container)
        self._tacho_layout.setContentsMargins(0, 0, 0, 0)
        self._tacho_layout.setSpacing(S["2"])
        self._tacho_container.hide()
        parent_layout.addWidget(self._tacho_container)

    # ── Selection handlers ─────────────────────────────────────────────────

    def _on_row_selected(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._show_driver_tacho_detail()

    def _on_row_double_clicked(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._edit_selected()

    def _get_selected_id(self) -> Optional[int]:
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
        """Reload driver data from the database and update the UI."""
        if self._driver_repo is None or self._trip_repo is None:
            return

        try:
            drivers = self._driver_repo.get_all(limit=500)
            active_trips = self._trip_repo.get_by_statuses(["Loading", "In Transit"])

            driver_trip_ids: set = set()
            for trip in active_trips:
                did = trip.get("driver_id")
                if did:
                    driver_trip_ids.add(did)

            rows: List[Dict[str, Any]] = []
            for d in drivers:
                did = d["id"]
                truck_text = (
                    self._dta_service.get_truck_plate_for_driver(did)
                    if self._dta_service
                    else ""
                ) or t("driver_manager.unassigned")

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

            self.table.set_data(rows)

            # ── KPI updates ───────────────────────────────────────────────
            total = len(drivers)
            active_count = sum(1 for d in drivers if d.get("is_active", 1))

            if len(self._kpi_cards) >= 1:
                self._kpi_cards[0].set_value(str(total))
            if len(self._kpi_cards) >= 3:
                self._kpi_cards[2].set_value(str(len(driver_trip_ids)))

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
            if len(self._kpi_cards) >= 2:
                self._kpi_cards[1].set_value(str(expiring))
            if len(self._kpi_cards) >= 4:
                self._kpi_cards[3].set_value(str(total - active_count))

            # ── Grey out inactive rows ────────────────────────────────────
            muted = QColor(COLORS["text_muted"])
            for r, row in enumerate(rows):
                if row.get("active") == t("common.no"):
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        if item is not None:
                            item.setForeground(muted)

            self._filter_table()

        except Exception as ex:
            logger.exception("refresh drivers failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    def _filter_table(self) -> None:
        """Filter visible rows based on search text."""
        query = self._search_entry.search_value().lower()
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
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    name = row.get("name", "").strip()
                    if not name:
                        continue
                    data: Dict[str, Any] = {
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
                f"Driver {name}",
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
        # Clear previous content
        for i in reversed(range(self._tacho_layout.count())):
            item = self._tacho_layout.itemAt(i)
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
            from repositories.tacho_driver_activity_repository import (
                TachoDriverActivityRepository,
            )

            activity_repo = TachoDriverActivityRepository(self.db)
            from_date = datetime.now().date() - timedelta(days=28)
            records = activity_repo.get_by_driver(driver_id, from_date)
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
        summary_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        summary_layout.setSpacing(S["3"])

        summary_items = [
            (t("tacho.total_hours"), f"{total_driving / 60:.1f}h",
             None),
            (t("tacho.avg_daily"), f"{avg_daily:.1f}h",
             None),
            (t("tacho.violations"), str(total_violations),
             COLORS["danger"] if total_violations > 0 else COLORS["success"]),
        ]
        for label_text, value_text, color in summary_items:
            chip = self._summary_chip(summary_frame, label_text, value_text, color)
            summary_layout.addWidget(chip)

        self._tacho_layout.addWidget(summary_frame)

        # ── Mini activity chart (last 14 days) ────────────────────────────
        chart_label = QLabel(t("tacho.last_14_days"))
        chart_label.setProperty("fontRole", "small")
        self._tacho_layout.addWidget(chart_label)

        last_14 = records[:14] if len(records) >= 14 else records
        scene = QGraphicsScene(self)
        bar_width = 18
        spacing = 2
        chart_height = 60

        for i, r in enumerate(reversed(last_14)):
            driving_h = (r.get("driving_minutes", 0) or 0) / 60
            if driving_h <= 9:
                bar_color = COLORS["success"]
            elif driving_h <= 10:
                bar_color = COLORS["warning"]
            else:
                bar_color = COLORS["danger"]

            bar_h = min(int(driving_h * 6), chart_height)
            x = i * (bar_width + spacing)

            rect = QGraphicsRectItem(x, chart_height - bar_h, bar_width, bar_h)
            rect.setBrush(QColor(bar_color))
            rect.setPen(Qt.NoPen)
            scene.addItem(rect)

            date_str = str(r.get("activity_date", ""))[5:]  # mm-dd
            text_item = scene.addText(date_str)
            text_item.setDefaultTextColor(QColor(COLORS["text_muted"]))
            text_item.setPos(x, chart_height + 2)

        view = QGraphicsView(scene)
        view.setFixedHeight(chart_height + 24)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setStyleSheet("background: transparent; border: none;")
        self._tacho_layout.addWidget(view)

        # ── Last 5 violations ────────────────────────────────────────────
        violations: List[tuple] = []
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
                row_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])

                date_lbl = QLabel(str(date_str))
                date_lbl.setProperty("fontRole", "small")
                date_lbl.setFixedWidth(90)
                row_layout.addWidget(date_lbl)

                viol_lbl = QLabel(v)
                viol_lbl.setProperty("fontRole", "small")
                viol_lbl.setStyleSheet(f"color: {COLORS['danger']};")
                viol_lbl.setWordWrap(True)
                row_layout.addWidget(viol_lbl, 1)

                self._tacho_layout.addWidget(row_frame)

        self._tacho_container.show()

    def _summary_chip(
        self,
        parent: QWidget,
        label_text: str,
        value_text: str,
        color: Optional[str] = None,
    ) -> QFrame:
        """Create a summary chip label-value pair."""
        chip = QFrame(parent)
        chip.setProperty("role", "tacho-chip")
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])
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
                background-color: {COLORS['bg_elevated']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
            }}
            QMenu::item:selected {{
                background-color: {COLORS['accent_dim']};
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
