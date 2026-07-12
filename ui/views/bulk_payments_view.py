"""PySide6 bulk payments view.

Main Bulk Payments module for the Operion ERP desktop application.
Provides a recipient selector, payment batch management, CSV export,
and CRUD for custom payment profiles.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.client_service import ClientService
from services.csv_service import CsvService
from services.driver_truck_service import DriverTruckService
from services.payment_batch_service import PaymentBatchService
from services.payment_profile_service import PaymentProfileService
from services.i18n import t, register_listener
from ui.base_view import BaseView
from ui.components import Btn, Card, PageTitle, SectionTitle
from ui.design_tokens import SP
from ui.theme import COLORS
from ui.widgets import (
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    StyledTextEdit,
    field,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit

logger = logging.getLogger(__name__)

# ── Column definitions ─────────────────────────────────────────────────────────

_RECIPIENT_COLUMNS: list[tuple] = [
    ("name",         "bulk_payments.col_name",         150),
    ("type",         "bulk_payments.col_type",         100),
    ("bank_account", "bulk_payments.col_bank_account", 150),
    ("bank_code",    "bulk_payments.col_bank_code",    100),
    ("iban",         "bulk_payments.col_iban",         180),
]

_BATCH_COLUMNS: list[tuple] = [
    ("recipient_name",   "bulk_payments.col_name",        150),
    ("recipient_type",   "bulk_payments.col_type",        100),
    ("bank_account",     "bulk_payments.col_bank_account", 150),
    ("iban",             "bulk_payments.col_iban",        180),
    ("amount",           "bulk_payments.col_amount",      100),
    ("currency",         "bulk_payments.col_currency",     80),
    ("payment_reference","bulk_payments.col_reference",   150),
]


def _resolve_recipient_labels() -> list[str]:
    """Return translated header labels for the recipient table."""
    return [t(key) for _, key, _ in _RECIPIENT_COLUMNS]


def _resolve_batch_labels() -> list[str]:
    """Return translated header labels for the batch table."""
    return [t(key) for _, key, _ in _BATCH_COLUMNS]


def _recipient_columns_for_table() -> list[tuple]:
    """Return ``(cid, label, width)`` tuples for ``StyledTableWidget``."""
    labels = _resolve_recipient_labels()
    return [(cid, labels[i], width) for i, (cid, _, width) in enumerate(_RECIPIENT_COLUMNS)]


def _batch_columns_for_table() -> list[tuple]:
    """Return ``(cid, label, width)`` tuples for ``StyledTableWidget``."""
    labels = _resolve_batch_labels()
    return [(cid, labels[i], width) for i, (cid, _, width) in enumerate(_BATCH_COLUMNS)]


# ── Payment profile form dialog ────────────────────────────────────────────────


class QtPaymentProfileDialog(QDialog):
    """Add / edit custom payment profile dialog."""

    FIELDS: list[tuple] = [
        ("profile_name",      "bulk_payments.profile_name",            True),
        ("bank_name",         "bulk_payments.profile_bank_name",       False),
        ("bank_account",      "bulk_payments.profile_bank_account",    False),
        ("bank_code",         "bulk_payments.profile_bank_code",       False),
        ("bank_bic",          "bulk_payments.profile_bank_bic",        False),
        ("iban",              "bulk_payments.profile_iban",            False),
        ("payment_reference", "bulk_payments.profile_payment_reference", False),
        ("contact_name",      "bulk_payments.profile_contact_name",    False),
        ("contact_email",     "bulk_payments.profile_contact_email",   False),
        ("contact_phone",     "bulk_payments.profile_contact_phone",   False),
    ]

    def __init__(
        self,
        parent: QWidget | None,
        profile_service: PaymentProfileService,
        profile: dict[str, Any] | None = None,
        on_save: Any = None,
    ):
        super().__init__(parent)
        # Use PaymentProfileService instead of raw repository
        self._service = profile_service
        self._profile = profile
        self._on_save = on_save
        self._editing = profile is not None

        self.setWindowTitle(
            t("bulk_payments.edit_profile") if self._editing else t("bulk_payments.new_profile"),
        )
        self.setMinimumSize(480, 640)
        self.setModal(True)

        self._entries: dict[str, StyledLineEdit] = {}
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from ui.widgets import ScrollableFormContainer

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=480)
        layout.addWidget(scroll, 1)

        d = self._profile or {}

        # Text fields
        for key, i18n_key, _required in self.FIELDS:
            entry = StyledLineEdit()
            val = d.get(key, "")
            if val is not None:
                entry.setText(str(val))
            self._entries[key] = entry
            fw = field(scroll.content, t(i18n_key), entry)
            scroll.add_widget(fw)

        # Recipient type dropdown
        self._type_combo = StyledComboBox(
            self,
            values=["custom", "government", "supplier", "contractor", "other"],
            state="readonly",
        )
        current_type = d.get("recipient_type", "custom")
        idx = self._type_combo.findText(current_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
        fw = field(scroll.content, t("bulk_payments.profile_type"), self._type_combo)
        scroll.add_widget(fw)

        # Notes
        self._notes_edit = StyledTextEdit(height=80)
        notes_val = d.get("notes", "")
        if notes_val is not None:
            self._notes_edit.setPlainText(str(notes_val))
        fw = field(scroll.content, t("bulk_payments.profile_notes"), self._notes_edit)
        scroll.add_widget(fw)

        scroll.add_stretch()

        # Button bar
        btn_bar = QFrame()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(SP["5"], SP["3"], SP["5"], SP["4"])

        cancel_btn = Btn(
            btn_bar,
            t("common.cancel"),
            variant="secondary",
            command=self.reject,
        )
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        save_btn = Btn(
            btn_bar,
            t("bulk_payments.save_profile"),
            variant="primary",
            command=self._save,
        )
        btn_layout.addWidget(save_btn)

        layout.addWidget(btn_bar)

    # ── Save logic ─────────────────────────────────────────────────────────

    def _save(self) -> None:
        name = self._entries["profile_name"].text().strip()
        if not name:
            QMessageBox.warning(
                self,
                t("common.warning"),
                t("bulk_payments.profile_name_required"),
            )
            return

        data: dict[str, Any] = {
            k: v.text().strip() for k, v in self._entries.items()
        }
        data["recipient_type"] = self._type_combo.currentText()
        data["notes"] = self._notes_edit.toPlainText().strip()
        data["is_active"] = 1

        try:
            if self._editing and self._profile is not None:
                profile_id = self._profile["id"]
                self._service.update(profile_id, data)  # Delegated to service layer
            else:
                profile_id = self._service.create(data)  # Delegated to service layer

            if self._on_save is not None:
                self._on_save(data)

            self.accept()
        except Exception as ex:
            logger.exception("Save payment profile failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )


# ── Main view ──────────────────────────────────────────────────────────────────


class QtBulkPaymentsView(BaseView):
    """Bulk payments view for embedding in a ``QStackedWidget``.

    Provides recipient selection, payment batch assembly, CSV export,
    and CRUD for custom payment profiles.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: dict | None = None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self._prefs = prefs or {}
        self._api_client = api_client

        self._batch_items: list[dict[str, Any]] = []
        self._all_recipients: list[dict[str, Any]] = []

        # Service-layer access instead of direct repository instantiation
        self._client_service = ClientService(db) if db else None
        self._driver_truck_service = DriverTruckService(db) if db else None
        self._profile_service = PaymentProfileService(db) if db else None
        self._batch_service = PaymentBatchService(db) if db else None

        self._language_callback = self._refresh_i18n
        self._register_i18n(self._language_callback)

        self._build_ui()
        self.destroyed.connect(self._cleanup)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Called when this view becomes active in a QStackedWidget."""
        self._load_data()
        self._refresh_batch_table()

    def shutdown(self) -> None:
        """Called when this view is hidden / removed from the stack."""
        super().shutdown()

    def _cleanup(self) -> None:
        self.shutdown()

    # ── i18n ───────────────────────────────────────────────────────────────

    def _refresh_i18n(self, _lang: str = "") -> None:
        """Update all translatable UI strings."""
        self._title_label.setText(t("bulk_payments.title"))
        self._export_btn.setText(t("bulk_payments.export_csv"))
        self._new_profile_btn.setText(t("bulk_payments.new_profile"))
        self._remove_selected_btn.setText(t("bulk_payments.remove_selected"))
        self._search_entry.setPlaceholderText(t("bulk_payments.search_recipients"))
        self._add_selected_btn.setText(t("bulk_payments.add_selected"))
        self._batch_title.setText(t("bulk_payments.batch_title", default="Payment Batch"))
        self._batch_empty_label.setText(t("bulk_payments.batch_empty"))

        self._recipient_table.setHorizontalHeaderLabels(_resolve_recipient_labels())
        self._batch_table.setHorizontalHeaderLabels(_resolve_batch_labels())

        self._refresh_batch_table()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["4"])

        self._build_header(layout)
        self._build_toolbar(layout)
        self._build_recipient_panel(layout)
        self._build_batch_panel(layout)
        layout.addStretch()

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        header_layout.setSpacing(SP["3"])

        self._title_label = PageTitle(None, t("bulk_payments.title"))
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        parent_layout.addWidget(header)

    def _build_toolbar(self, parent_layout: QVBoxLayout) -> None:
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(SP["10"], 0, SP["10"], 0)
        toolbar_layout.setSpacing(SP["3"])

        self._export_btn = Btn(
            self,
            t("bulk_payments.export_csv"),
            variant="primary",
            command=self._export_csv,
        )
        toolbar_layout.addWidget(self._export_btn)

        self._new_profile_btn = Btn(
            self,
            t("bulk_payments.new_profile"),
            variant="secondary",
            command=self._new_payment_profile,
        )
        toolbar_layout.addWidget(self._new_profile_btn)

        toolbar_layout.addStretch()

        self._remove_selected_btn = Btn(
            self,
            t("bulk_payments.remove_selected"),
            variant="danger",
            command=self._remove_from_batch,
        )
        toolbar_layout.addWidget(self._remove_selected_btn)

        parent_layout.addWidget(toolbar)

    def _build_recipient_panel(self, parent_layout: QVBoxLayout) -> None:
        card = Card(None)
        card_layout = card.layout()

        # Search bar
        search_row = QFrame()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self._search_entry = DebouncedLineEdit(
            placeholder=t("bulk_payments.search_recipients"),
        )
        self._search_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._search_entry.debouncedTextChanged.connect(self._search_recipients)
        search_layout.addWidget(self._search_entry, 1)

        card_layout.addWidget(search_row)

        # Recipient table
        columns = _recipient_columns_for_table()
        self._recipient_table = StyledTableWidget(self, columns=columns)
        self._recipient_table.cellDoubleClicked.connect(self._add_to_batch)
        self._recipient_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._recipient_table.customContextMenuRequested.connect(
            self._show_recipient_context_menu
        )
        card_layout.addWidget(self._recipient_table, 1)

        # Add selected button
        btn_row = QFrame()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()

        self._add_selected_btn = Btn(
            btn_row,
            t("bulk_payments.add_selected"),
            variant="secondary",
            command=self._add_selected_to_batch,
        )
        btn_layout.addWidget(self._add_selected_btn)

        card_layout.addWidget(btn_row)
        parent_layout.addWidget(card)

    def _build_batch_panel(self, parent_layout: QVBoxLayout) -> None:
        card = Card(None)
        card_layout = card.layout()

        self._batch_title = SectionTitle(None, t("bulk_payments.batch_title", default="Payment Batch"))
        card_layout.addWidget(self._batch_title)

        # Empty state
        self._batch_empty_label = QLabel(t("bulk_payments.batch_empty"))
        self._batch_empty_label.setAlignment(Qt.AlignCenter)
        self._batch_empty_label.setWordWrap(True)
        self._batch_empty_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; padding: {SP['8']}px; font-size: 14px;"
        )
        card_layout.addWidget(self._batch_empty_label)

        # Batch table
        columns = _batch_columns_for_table()
        self._batch_table = StyledTableWidget(self, columns=columns)
        self._batch_table.set_column_alignment("amount", Qt.AlignRight | Qt.AlignVCenter)
        self._batch_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._batch_table.customContextMenuRequested.connect(
            self._show_batch_context_menu
        )
        card_layout.addWidget(self._batch_table, 1)

        parent_layout.addWidget(card, 1)

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_data(self) -> None:
        """Load recipients from the database via the service layer."""
        if self.db is None:
            return

        try:
            # Fetch via services (typed Pydantic results → dict for backward compat)
            clients: list[dict[str, Any]] = []
            if self._client_service:
                result = self._client_service.list_all()
                clients = [c.model_dump() for c in (result.data or [])]

            drivers: list[dict[str, Any]] = []
            if self._driver_truck_service:
                result = self._driver_truck_service.list_drivers()
                drivers = [d.model_dump() for d in (result.data or [])]

            profiles: list[dict[str, Any]] = []
            if self._batch_service:
                result = self._batch_service.list_profiles()
                profiles = [p.model_dump() for p in (result.data or [])]

            recipients: list[dict[str, Any]] = []

            # NOTE: Service methods return only active entities by default,
            # so the is_active check is implicit.

            for c in clients:
                recipients.append({
                    "id": c["id"],
                    "name": c.get("name", ""),
                    "type": "client",
                    "bank_account": c.get("bank_account", ""),
                    "bank_code": c.get("bank_code", ""),
                    "iban": c.get("iban", ""),
                    "source": "client",
                    "source_data": c,
                })

            for d in drivers:
                recipients.append({
                    "id": d["id"],
                    "name": d.get("name", ""),
                    "type": "driver",
                    "bank_account": d.get("bank_account", ""),
                    "bank_code": d.get("bank_code", ""),
                    "iban": d.get("iban", ""),
                    "source": "driver",
                    "source_data": d,
                })

            for p in profiles:
                recipients.append({
                    "id": p["id"],
                    "name": p.get("name", ""),
                    "type": p.get("recipient_type", "custom"),
                    "bank_account": p.get("bank_account", ""),
                    "bank_code": p.get("bank_code", ""),
                    "iban": p.get("iban", ""),
                    "source": "profile",
                    "source_data": p,
                })

            self._all_recipients = recipients
            self._search_recipients(self._search_entry.text())

        except Exception as ex:
            logger.exception("Load recipients failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    def _search_recipients(self, text: str) -> None:
        """Filter recipients based on debounced search text."""
        query = (text or "").strip().lower()
        if not query:
            filtered = self._all_recipients
        else:
            filtered = [
                r for r in self._all_recipients
                if query in r.get("name", "").lower()
                or query in r.get("bank_account", "").lower()
                or query in r.get("iban", "").lower()
                or query in r.get("bank_code", "").lower()
            ]

        rows: list[dict[str, Any]] = []
        for r in filtered:
            rows.append({
                "name": r["name"],
                "type": r["type"],
                "bank_account": r["bank_account"],
                "bank_code": r["bank_code"],
                "iban": r["iban"],
                "_source": r,
            })

        self._recipient_table.set_data(rows)

    # ── Batch operations ───────────────────────────────────────────────────

    def _add_to_batch(self, row_idx: int, _col_idx: int = 0) -> None:
        """Add recipient at *row_idx* to the payment batch (double-click)."""
        if not (0 <= row_idx < len(self._recipient_table._data)):
            return
        row_data = self._recipient_table._data[row_idx]
        source = row_data.get("_source")
        if source is None:
            return
        self._prompt_and_add(source)

    def _add_selected_to_batch(self) -> None:
        """Add the currently selected recipient to the batch."""
        row_data = self._recipient_table.selected_row_data()
        if row_data is None:
            QMessageBox.information(
                self,
                t("bulk_payments.title"),
                t("bulk_payments.select_recipient_first"),
            )
            return
        source = row_data.get("_source")
        if source is None:
            return
        self._prompt_and_add(source)

    def _prompt_and_add(self, source: dict[str, Any]) -> None:
        """Prompt for amount and append the recipient to the batch."""
        amount, ok = QInputDialog.getDouble(
            self,
            t("bulk_payments.add_amount_title", default="Payment Amount"),
            t("bulk_payments.add_amount_prompt", default="Enter amount for {}:").format(
                source["name"]
            ),
            0.0,
            0.0,
            999_999_999.99,
            2,
        )
        if not ok:
            return

        currency = self._prefs.get("default_currency", "EUR")

        batch_item: dict[str, Any] = {
            "recipient_id": source["id"],
            "recipient_type": source["type"],
            "recipient_name": source["name"],
            "bank_account": source["bank_account"],
            "bank_code": source["bank_code"],
            "bank_bic": source.get("source_data", {}).get("bank_bic", ""),
            "iban": source["iban"],
            "amount": amount,
            "currency": currency,
            "payment_reference": source.get("source_data", {}).get("payment_reference", ""),
        }
        self._batch_items.append(batch_item)
        self._refresh_batch_table()

    def _remove_from_batch(self) -> None:
        """Remove the selected batch item."""
        row_data = self._batch_table.selected_row_data()
        if row_data is None:
            QMessageBox.information(
                self,
                t("bulk_payments.title"),
                t("bulk_payments.no_batch_selection"),
            )
            return

        rid = row_data.get("recipient_id")
        rtype = row_data.get("recipient_type")
        ramt = row_data.get("amount")

        for i, item in enumerate(self._batch_items):
            if (
                item.get("recipient_id") == rid
                and item.get("recipient_type") == rtype
                and abs(float(item.get("amount", 0) or 0) - float(ramt or 0)) < 0.001
            ):
                self._batch_items.pop(i)
                break

        self._refresh_batch_table()

    def _edit_amount(self) -> None:
        """Edit the amount of the selected batch item."""
        row_data = self._batch_table.selected_row_data()
        if row_data is None:
            return

        current = float(row_data.get("amount", 0) or 0)
        amount, ok = QInputDialog.getDouble(
            self,
            t("bulk_payments.edit_amount_title", default="Edit Amount"),
            t("bulk_payments.edit_amount_prompt", default="New amount:"),
            current,
            0.0,
            999_999_999.99,
            2,
        )
        if not ok:
            return

        rid = row_data.get("recipient_id")
        rtype = row_data.get("recipient_type")

        for item in self._batch_items:
            if (
                item.get("recipient_id") == rid
                and item.get("recipient_type") == rtype
                and abs(float(item.get("amount", 0) or 0) - current) < 0.001
            ):
                item["amount"] = amount
                break

        self._refresh_batch_table()

    def _refresh_batch_table(self) -> None:
        """Refresh the batch table display and empty state."""
        has_items = bool(self._batch_items)
        self._batch_table.setVisible(has_items)
        self._batch_empty_label.setVisible(not has_items)

        if not has_items:
            self._batch_table.setRowCount(0)
            self._batch_table._data = []
            return

        table = self._batch_table
        table.setSortingEnabled(False)
        table.setRowCount(0)
        table._data = list(self._batch_items)

        # Populate data rows
        table.setRowCount(len(self._batch_items) + 1)
        for r, item in enumerate(self._batch_items):
            for c, cid in enumerate(table._column_ids):
                value = item.get(cid, "")
                display = str(value) if value is not None else ""
                twi = QTableWidgetItem(display)
                twi.setData(Qt.UserRole, value)
                table.setItem(r, c, twi)

        # Total row (last row)
        total_row = len(self._batch_items)
        # Delegate financial sum to service layer
        total_amount = PaymentBatchService.calculate_total(self._batch_items)

        total_label = QTableWidgetItem(t("bulk_payments.total"))
        font = total_label.font()
        font.setBold(True)
        total_label.setFont(font)
        total_label.setFlags(total_label.flags() & ~Qt.ItemIsSelectable)
        table.setItem(total_row, 0, total_label)

        # Middle columns (empty, non-selectable, bold)
        for c in range(1, 4):
            twi = QTableWidgetItem("")
            font = twi.font()
            font.setBold(True)
            twi.setFont(font)
            twi.setFlags(twi.flags() & ~Qt.ItemIsSelectable)
            table.setItem(total_row, c, twi)

        amount_item = QTableWidgetItem(f"{total_amount:.2f}")
        font = amount_item.font()
        font.setBold(True)
        amount_item.setFont(font)
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsSelectable)
        table.setItem(total_row, 4, amount_item)

        for c in (5, 6):
            twi = QTableWidgetItem("")
            font = twi.font()
            font.setBold(True)
            twi.setFont(font)
            twi.setFlags(twi.flags() & ~Qt.ItemIsSelectable)
            table.setItem(total_row, c, twi)

        self._update_total()

    def _update_total(self) -> None:
        """Recalculate and log the batch total via the service layer."""
        # Delegate financial sum to PaymentBatchService
        total = PaymentBatchService.calculate_total(self._batch_items)
        logger.debug("Batch total updated: %.2f", total)

    # ── Payment profile CRUD ───────────────────────────────────────────────

    def _new_payment_profile(self) -> None:
        """Open the dialog to create a new payment profile."""
        if self._profile_service is None:
            return
        dialog = QtPaymentProfileDialog(
            self,
            self._profile_service,  # Use service instead of raw repo
            profile=None,
            on_save=self._on_save_profile,
        )
        dialog.exec()

    def _edit_payment_profile(self, profile_id: int | None = None) -> None:
        """Open the dialog to edit an existing payment profile."""
        if self._profile_service is None:
            return

        if profile_id is None:
            row_data = self._recipient_table.selected_row_data()
            if row_data is None:
                return
            source = row_data.get("_source")
            if source is None or source.get("source") != "profile":
                QMessageBox.information(
                    self,
                    t("bulk_payments.title"),
                    t("bulk_payments.select_profile_first"),
                )
                return
            profile_id = source["id"]

        if profile_id is None:
            return
        # Use service layer for DB access
        profile = self._profile_service.get_by_id(profile_id)
        if profile is None:
            return

        dialog = QtPaymentProfileDialog(
            self,
            self._profile_service,  # Use service instead of raw repo
            profile=profile,
            on_save=self._on_save_profile,
        )
        dialog.exec()

    def _delete_payment_profile(self, profile_id: int | None = None) -> None:
        """Delete a payment profile after confirmation."""
        if self._profile_service is None:
            return

        if profile_id is None:
            row_data = self._recipient_table.selected_row_data()
            if row_data is None:
                return
            source = row_data.get("_source")
            if source is None or source.get("source") != "profile":
                return
            profile_id = source["id"]

        if profile_id is None:
            return

        reply = QMessageBox.question(
            self,
            t("bulk_payments.delete_profile"),
            t("bulk_payments.confirm_delete_profile"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._profile_service.delete(profile_id)  # Delegated to service layer
            self._load_data()
        except Exception as ex:
            logger.exception("Delete payment profile failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    def _on_save_profile(self, data: dict[str, Any]) -> None:
        """Callback after a profile is saved via the dialog.

        Optionally syncs to the API client if one is configured.
        """
        if self._api_client is not None and hasattr(self._api_client, "save_payment_profile"):
            try:
                self._api_client.save_payment_profile(data)
            except Exception:
                logger.exception("API client save payment profile failed")
        self._load_data()

    # ── CSV export ─────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        """Export the current payment batch to a CSV file."""
        if not self._batch_items:
            QMessageBox.information(
                self,
                t("bulk_payments.title"),
                t("bulk_payments.nothing_to_export"),
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("bulk_payments.export_csv"),
            "",
            f"{t('common.csv_filter')} (*.csv)",
        )
        if not path:
            return

        try:
            # Delegate CSV generation to CsvService (no raw file I/O in the view)
            fieldnames = [
                "recipient_name", "recipient_type", "bank_account",
                "iban", "amount", "currency", "payment_reference",
            ]
            CsvService.export(self._batch_items, path, fieldnames=fieldnames)

            QMessageBox.information(
                self,
                t("bulk_payments.export_csv"),
                t("bulk_payments.export_success"),
            )
        except Exception as ex:
            logger.exception("CSV export failed")
            QMessageBox.critical(
                self,
                t("main.error_title"),
                str(ex),
            )

    # ── Context menus ──────────────────────────────────────────────────────

    def _show_recipient_context_menu(self, position) -> None:
        """Show context menu for the recipient table."""
        row_data = self._recipient_table.selected_row_data()
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

        add_action = QAction(t("bulk_payments.add_to_batch"), self)
        add_action.triggered.connect(self._add_selected_to_batch)
        menu.addAction(add_action)

        source = row_data.get("_source", {})
        if source.get("source") == "profile":
            menu.addSeparator()

            edit_action = QAction(t("bulk_payments.edit_profile"), self)
            edit_action.triggered.connect(
                lambda: self._edit_payment_profile(source.get("id"))
            )
            menu.addAction(edit_action)

            delete_action = QAction(t("bulk_payments.delete_profile"), self)
            delete_action.triggered.connect(
                lambda: self._delete_payment_profile(source.get("id"))
            )
            menu.addAction(delete_action)

        menu.exec(self._recipient_table.viewport().mapToGlobal(position))

    def _show_batch_context_menu(self, position) -> None:
        """Show context menu for the batch table."""
        row_data = self._batch_table.selected_row_data()
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

        edit_action = QAction(t("bulk_payments.edit_amount"), self)
        edit_action.triggered.connect(self._edit_amount)
        menu.addAction(edit_action)

        menu.addSeparator()

        remove_action = QAction(t("bulk_payments.remove_from_batch"), self)
        remove_action.triggered.connect(self._remove_from_batch)
        menu.addAction(remove_action)

        menu.exec(self._batch_table.viewport().mapToGlobal(position))
