"""PySide6 client management view.

Replaces ``ui/client_manager.py``.  Displays a searchable client table
with CRUD operations via a form dialog.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

import contextlib

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.client_service import ClientService
from services.i18n import register_listener, t, unregister_listener
from services.operations.event_bus import (
    CLIENT_CREATED,
    CLIENT_UPDATED,
    EventBus,
)
from ui.components import (
    Btn,
    PageTitle,
)
from ui.design_tokens import (
    SP,
)
from ui.theme import COLORS
from ui.widgets import (
    ScrollableFormContainer,
    StyledLineEdit,
    StyledTableWidget,
    field,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit

# ── Column definition ──────────────────────────────────────────────────────────
# (column_id,  label_or_i18n_key,  width_px,  translate)
_COLUMNS: list[tuple] = [
    ("id",      "ID",                   40,  False),
    ("name",    "client.table_name",    180, True),
    ("contact", "client.table_contact", 130, True),
    ("phone",   "client.table_phone",   110, True),
    ("email",   "client.table_email",   150, True),
    ("trips",   "client.table_trips",    60, True),
]


def _resolve_column_labels() -> list[str]:
    """Return translated header labels for the current language."""
    return [t(key) if translate else key for _, key, _, translate in _COLUMNS]


def _columns_for_table() -> list[tuple]:
    """Return ``(cid, label, width)`` tuples suitable for ``StyledTableWidget``."""
    labels = _resolve_column_labels()
    return [(cid, labels[i], width) for i, (cid, _, width, _) in enumerate(_COLUMNS)]


# ── Main view ──────────────────────────────────────────────────────────────────

class QtClientManager(QWidget):
    """Client management table view for embedding in ``QStackedWidget``.

    Provides search, add, edit, and deactivate operations via
    ``ClientService``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: dict | None = None,
        client_service=None,
    ):
        super().__init__(parent)
        self.db = db
        self.service = client_service
        self._selected_id: int | None = None

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()
        self._load_data()

        self.destroyed.connect(self._cleanup)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)

    def wakeup(self) -> None:
        if not getattr(self, "_listener_registered", False):
            register_listener(self._language_callback)
            self._listener_registered = True
        self._load_data()

    def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        self._listener_registered = False

    # ── i18n ───────────────────────────────────────────────────────────────

    def _on_language_changed(self, _lang: str) -> None:
        self._update_translations()
        self._load_data()

    def _update_translations(self) -> None:
        labels = _resolve_column_labels()
        self.table.setHorizontalHeaderLabels(labels)

        self._search_entry.setPlaceholderText(t("common.search"))

        self._title_label.setText(t("client.title"))
        self._new_btn.setText("+ " + t("client.new_button"))
        self._edit_btn.setText(t("client.edit_button"))
        self._deact_btn.setText(t("client.deactivate_button"))

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["4"])

        self._build_top_bar(layout)
        self._build_table(layout)
        self._build_action_bar(layout)

    def _build_top_bar(self, parent_layout: QVBoxLayout) -> None:
        top = QFrame()
        top.setFixedHeight(72)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        top_layout.setSpacing(SP["3"])

        self._title_label = PageTitle(None, t("client.title"))
        top_layout.addWidget(self._title_label)

        top_layout.addSpacing(SP["3"])

        self._search_entry = DebouncedLineEdit(
            placeholder=t("common.search"),
        )
        self._search_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._search_entry.debouncedTextChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_entry, 1)

        top_layout.addStretch()

        self._new_btn = Btn(
            self,
            text="+ " + t("client.new_button"),
            command=self._open_form_new,
        )
        top_layout.addWidget(self._new_btn)

        parent_layout.addWidget(top)

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

        self._edit_btn = Btn(
            self,
            text=t("client.edit_button"),
            command=self._open_form_edit,
        )
        bar_layout.addWidget(self._edit_btn)

        self._deact_btn = Btn(
            self,
            text=t("client.deactivate_button"),
            command=self._deactivate,
            variant="danger",
        )
        bar_layout.addWidget(self._deact_btn)

        bar_layout.addStretch()
        parent_layout.addWidget(bar)

    # ── Search ─────────────────────────────────────────────────────────────

    def _on_search_changed(self) -> None:
        self._load_data()

    # ── Data loading ───────────────────────────────────────────────────────

    def _load_data(self) -> None:
        if self.service is None:
            return

        query = self._search_entry.text().strip()
        clients = self.service.search(query, limit=200) if query else self.service.get_all()

        rows: list[dict[str, Any]] = []
        for c in clients:
            trip_count = self.service.get_trip_count(c["id"])
            rows.append({
                "id":      c["id"],
                "name":    c.get("name", ""),
                "contact": c.get("contact_person") or "",
                "phone":   c.get("phone") or "",
                "email":   c.get("email") or "",
                "trips":   trip_count,
                "_is_active": c.get("is_active", 1),
            })

        self.table.set_data(rows)

        # Gray out inactive rows.
        muted = QColor(COLORS["text_muted"])
        for r, row in enumerate(rows):
            if not row.get("_is_active", 1):
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    if item is not None:
                        item.setForeground(muted)

    # ── Selection ──────────────────────────────────────────────────────────

    def _on_row_selected(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")

    def _on_row_double_clicked(self, row_data: dict) -> None:
        self._selected_id = row_data.get("id")
        self._open_form_edit()

    # ── CRUD actions ───────────────────────────────────────────────────────

    def _open_form_new(self) -> None:
        if self.service is None:
            return
        dialog = QtClientFormDialog(
            self, self.service, client_data=None, on_save=self._load_data,
        )
        dialog.exec()

    def _open_form_edit(self) -> None:
        if self._selected_id is None or self.service is None:
            return
        client = self.service.get_by_id(self._selected_id)
        if client is None:
            return
        dialog = QtClientFormDialog(
            self, self.service, client_data=client, on_save=self._load_data,
        )
        dialog.exec()

    def _deactivate(self) -> None:
        if self._selected_id is None or self.service is None:
            return
        client = self.service.get_by_id(self._selected_id)
        if client is None:
            return
        count = self.service.get_trip_count(self._selected_id)
        msg = t("client.deactivate_confirm").format(name=client.get("name", ""))
        if count > 0:
            msg += t("client.deactivate_trips_warning").format(count=count)

        reply = QMessageBox.question(
            self,
            t("common.confirm"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.service.deactivate(self._selected_id)
            # Soft-delete: a deactivation changes the client's state
            # and any other view that holds a client combo needs to
            # refresh.  We use ``CLIENT_UPDATED`` (not a separate
            # event) so subscribers only need one handler.
            try:
                EventBus().publish(CLIENT_UPDATED, {
                    "client_id": int(self._selected_id),
                    "name": client.get("name", ""),
                    "is_active": 0,
                })
            except Exception:
                logger.exception(
                    "Failed to publish CLIENT_UPDATED for deactivation"
                )
            self._load_data()


# ── Form dialog ────────────────────────────────────────────────────────────────

class QtClientFormDialog(QDialog):
    """Add / edit client dialog."""

    FIELDS: list[tuple] = [
        ("name",           "client.field_name",    True),
        ("contact_person", "client.field_contact",  False),
        ("phone",          "client.field_phone",    False),
        ("email",          "client.field_email",    False),
        ("address",        "client.field_address",  False),
        ("vat_number",     "client.field_vat",      False),
        ("notes",          "client.field_notes",    False),
    ]

    def __init__(
        self,
        parent: QWidget | None,
        service: ClientService,
        client_data: dict[str, Any] | None = None,
        on_save=None,
    ):
        super().__init__(parent)
        self.service = service
        self.client_data = client_data
        self.on_save = on_save
        self._editing = client_data is not None

        self.setWindowTitle(
            t("client.edit_title") if self._editing else t("client.new_title"),
        )
        self.setMinimumSize(450, 480)
        self.setModal(True)

        self._entries: dict[str, StyledLineEdit] = {}

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=450)
        layout.addWidget(scroll, 1)

        for key, i18n_key, _required in self.FIELDS:
            entry = StyledLineEdit()
            if self.client_data is not None:
                val = self.client_data.get(key) or ""
                entry.setText(str(val))
            self._entries[key] = entry
            fw = field(scroll.content, t(i18n_key), entry)
            scroll.add_widget(fw)

        scroll.add_stretch()

        # Bottom button bar.
        btn_bar = QFrame()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(SP["5"], 0, SP["5"], SP["4"])

        btn_layout.addStretch()
        save_btn = Btn(
            btn_bar,
            text=t("client.save_button"),
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
                self, t("common.warning"), t("client.name_required"),
            )
            return

        data: dict[str, str] = {
            k: v.text().strip() for k, v in self._entries.items()
        }

        if self._editing and self.client_data is not None:
            self.service.update(self.client_data["id"], **data)
            event_type = CLIENT_UPDATED
            entity_id = int(self.client_data["id"])
        else:
            existing = self.service._repo.get_by_name(name)
            if existing:
                QMessageBox.warning(
                    self,
                    t("common.warning"),
                    t("client.already_exists").format(name=name),
                )
                return
            new_id = self.service.create(**data)
            event_type = CLIENT_CREATED
            entity_id = int(new_id) if new_id is not None else 0

        # Notify other views (route planner, calculator, dispatch
        # assignment) so the change shows up without a restart.
        try:
            EventBus().publish(event_type, {
                "client_id": entity_id,
                "name": name,
            })
        except Exception:
            logger.exception(
                "Failed to publish client %s event", event_type
            )

        if self.on_save is not None:
            self.on_save()

        self.accept()
