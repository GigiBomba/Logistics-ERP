"""PySide6 receipt editor with QWebEngineView live preview.

Provides a two-column layout: left scrollable form, right live HTML preview.
Modeled after ``QtProformaEditor`` per the Operion pattern.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.base_view import BaseView
from utils.editor_toolkit import DebouncedTask, export_editor_data, mark_field_invalid, register_shortcuts, validate_and_highlight
from services.invoicing.config_manager import load_company_config
from repositories.receipt_repository import RECEIPT_NUMBER_FORMATS, DEFAULT_FORMAT_KEY
from services.invoicing.receipt_service import ReceiptService
from services.operations.event_bus import SETTINGS_UPDATED
from services.preferences import PreferencesManager
from ui.components import Btn, Card, CardHeader, Divider, Label, PageTitle, SectionTitle
from ui.theme import COLORS, S
from ui.widgets import (
    ScrollableFormContainer,
    StyledCheckBox,
    StyledComboBox,
    StyledLineEdit,
    StyledTextEdit,
)
from ui.widgets.layout_utils import clear_layout

from ui.views.receipt_editor.line_items import LineItemsMixin

logger = logging.getLogger(__name__)


RECEIPT_TYPES = [
    ("customer_payment", "receipt.type_customer_payment"),
    ("cash_receipt", "receipt.type_cash_receipt"),
    ("driver_reimbursement", "receipt.type_driver_reimbursement"),
    ("employee_expense", "receipt.type_employee_expense"),
    ("fuel_reimbursement", "receipt.type_fuel_reimbursement"),
    ("toll_reimbursement", "receipt.type_toll_reimbursement"),
    ("miscellaneous", "receipt.type_miscellaneous"),
    ("refund", "receipt.type_refund"),
    ("deposit", "receipt.type_deposit"),
    ("advance_payment", "receipt.type_advance_payment"),
    ("other", "receipt.type_other"),
]

PAYMENT_METHODS = [
    "Cash", "Bank Transfer", "Card", "Mobile Payment", "Other",
]

CURRENCIES = ["EUR", "RON", "USD"]
LANGUAGES = ["en", "ro"]

ATTACHMENT_TYPES = [
    ("receipt_photo", "receipt.attach_type_photo"),
    ("fuel_receipt", "receipt.attach_type_fuel"),
    ("invoice_doc", "receipt.attach_type_invoice"),
    ("cmr_doc", "receipt.attach_type_cmr"),
    ("pod_doc", "receipt.attach_type_pod"),
    ("document", "receipt.attach_type_document"),
    ("image", "receipt.attach_type_image"),
    ("other", "receipt.attach_type_other"),
]


class QtReceiptEditor(BaseView, LineItemsMixin):
    """Professional receipt editor.

    Provides a scrollable form on the left and a QWebEngineView
    live preview on the right. Modeled after ``QtProformaEditor``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: PreferencesManager | None = None,
        client_repo=None,
        fleet_repo=None,
        invoice_repo=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs or (PreferencesManager(db) if db else None)
        self._receipt_service: ReceiptService | None = None
        self._trip_svc_instance: Any | None = None
        self._client_repo_instance = client_repo
        self._fleet_repo_instance = fleet_repo
        self._invoice_repo_instance = invoice_repo


        # ── State ────────────────────────────────────────────────────
        self._receipt_number: str = ""
        self._receipt_type: str = "customer_payment"
        self._issue_date: str = datetime.now().strftime("%Y-%m-%d")
        self._payment_date: str = ""
        self._currency: str = self.prefs.get_currency() if self.prefs else "EUR"
        self._language: str = "en"
        self._branch: str = ""
        self._format_key: str = DEFAULT_FORMAT_KEY

        # Parties
        self._received_from_name: str = ""
        self._received_from_address: str = ""
        self._received_from_vat: str = ""
        self._received_from_reg: str = ""
        self._received_from_contact: str = ""
        self._received_by_name: str = ""
        self._received_by_address: str = ""
        self._received_by_vat: str = ""
        self._received_by_reg: str = ""
        self._received_by_contact: str = ""

        # Payment
        self._payment_method: str = ""
        self._reference_number: str = ""
        self._transaction_id: str = ""
        self._bank_reference: str = ""
        self._invoice_reference: str = ""

        # Logistics
        self._related_trip: str = ""
        self._customer: str = ""
        self._vehicle: str = ""
        self._trailer: str = ""
        self._pickup_location: str = ""
        self._delivery_location: str = ""
        self._route: str = ""
        self._dispatcher: str = ""

        # Financial
        self._amount: float = 0
        self._vat_rate: float = 0
        self._vat_amount: float = 0
        self._total: float = 0
        self._amount_words: str = ""
        self._purpose: str = ""

        # Employee
        self._employee_name: str = ""
        self._department: str = ""
        self._expense_category: str = ""
        self._mileage: float = 0
        self._fuel: float = 0
        self._accommodation: float = 0
        self._meals: float = 0
        self._parking: float = 0
        self._tolls: float = 0
        self._other_expense: float = 0

        # Branding
        self._logo_path: str = ""
        self._signature_path: str = ""
        self._stamp_path: str = ""

        # Attachments
        self._attachments: list[dict[str, Any]] = []

        # Notes
        self._notes: str = ""

        # Combo maps (display text → entity data)
        self._trip_combo_map: dict[str, int] = {}
        self._client_map: dict[str, dict] = {}
        self._vehicle_map: dict[str, dict] = {}
        self._trailer_map: dict[str, dict] = {}
        self._invoice_map: dict[str, int] = {}

        # i18n
        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        # Debounced preview refresh
        self._refresh_task = DebouncedTask(self._refresh_preview)

        # Keyboard shortcuts
        self._shortcuts = register_shortcuts(self, {
            "generate": self._on_generate,
            "save_draft": self._save_draft,
            "load_draft": self._load_draft,
            "duplicate": self._on_duplicate,
            "export_json": self._on_export_json,
            "print": self._on_print,
        })

        # Build UI
        self._build_ui()
        self._load_company_config()
        self._update_receipt_number()

        self._subscribe(SETTINGS_UPDATED, self._on_settings_updated)

    # ── Lifecycle ────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Called when the tab becomes visible."""
        self._load_all_db_combos()
        self._refresh_preview()

    def shutdown(self) -> None:
        """Clean up resources."""
        super().shutdown()

    def _on_language_changed(self, _lang: str) -> None:
        self._retranslate_ui()

    def _on_settings_updated(self, ev: Any) -> None:
        data = ev.get("data", {}) if isinstance(ev, dict) else {}
        if data.get("key") == "company_config":
            QTimer.singleShot(0, self._load_company_config)

    # ── Service ─────────────────────────────────────────────────────

    def _get_receipt_service(self) -> ReceiptService:
        if self._receipt_service is None:
            self._receipt_service = ReceiptService(self.db, prefs=self.prefs)
        return self._receipt_service

    @property
    def _trip_svc(self):
        if self._trip_svc_instance is None and self.db is not None:
            from services.trip_service import TripService
            self._trip_svc_instance = TripService(self.db)
        return self._trip_svc_instance

    @property
    def _client_repo(self):
        return self._client_repo_instance

    @property
    def _fleet_repo(self):
        return self._fleet_repo_instance

    @property
    def _invoice_repo(self):
        return self._invoice_repo_instance

    # ── DB combo data loading ────────────────────────────────────────

    def _load_trip_combo(self) -> None:
        """Populate the Related Trip combo from TripService."""
        if not self._trip_svc or not hasattr(self, "_related_trip_combo"):
            return
        try:
            trips = self._trip_svc.get_all()
        except Exception:
            trips = []
        self._trip_combo_map = {}
        current = self._related_trip_combo.currentText()
        self._related_trip_combo.blockSignals(True)
        self._related_trip_combo.clear()
        self._related_trip_combo.addItem("")
        for t in trips:
            # NOTE: Reusing invoice key "invoice.trip_list_format" because no
            # receipt-specific key exists in translations yet.
            label = t("invoice.trip_list_format").format(
                id=t["id"],
                truck_number=t.get("truck_number", ""),
                client_name=t.get("client_name", ""),
                created_at=((t.get("created_at") or "")[:10]),
            )
            self._related_trip_combo.addItem(label)
            self._trip_combo_map[label] = t["id"]
        idx = self._related_trip_combo.findText(current)
        if idx >= 0:
            self._related_trip_combo.setCurrentIndex(idx)
        self._related_trip_combo.blockSignals(False)

    def _load_client_combo(self) -> None:
        """Populate the Customer combo from ClientRepository."""
        if not self._client_repo or not hasattr(self, "_customer_combo"):
            return
        try:
            clients = self._client_repo.get_all()
        except Exception:
            clients = []
        self._client_map = {}
        current = self._customer_combo.currentText()
        self._customer_combo.blockSignals(True)
        self._customer_combo.clear()
        self._customer_combo.addItem("")
        for c in clients:
            name = c.get("name", "")
            self._customer_combo.addItem(name)
            self._client_map[name] = c
        idx = self._customer_combo.findText(current)
        if idx >= 0:
            self._customer_combo.setCurrentIndex(idx)
        self._customer_combo.blockSignals(False)

    def _load_vehicle_combo(self) -> None:
        """Populate the Vehicle combo from FleetRepository."""
        if not self._fleet_repo or not hasattr(self, "_vehicle_combo"):
            return
        try:
            trucks = self._fleet_repo.get_active_trucks()
        except Exception:
            trucks = []
        self._vehicle_map = {}
        current = self._vehicle_combo.currentText()
        self._vehicle_combo.blockSignals(True)
        self._vehicle_combo.clear()
        self._vehicle_combo.addItem("")
        for t in trucks:
            plate = t.get("plate_number", "")
            if plate:
                self._vehicle_combo.addItem(plate)
                self._vehicle_map[plate] = t
        idx = self._vehicle_combo.findText(current)
        if idx >= 0:
            self._vehicle_combo.setCurrentIndex(idx)
        self._vehicle_combo.blockSignals(False)

    def _load_trailer_combo(self) -> None:
        """Populate the Trailer combo from trucks with trailers."""
        if not self._fleet_repo or not hasattr(self, "_trailer_combo"):
            return
        try:
            trucks = self._fleet_repo.get_active_trucks()
        except Exception:
            trucks = []
        self._trailer_map = {}
        current = self._trailer_combo.currentText()
        self._trailer_combo.blockSignals(True)
        self._trailer_combo.clear()
        self._trailer_combo.addItem("")
        for t in trucks:
            tplate = t.get("trailer_plate", "")
            if tplate:
                self._trailer_combo.addItem(tplate)
                self._trailer_map[tplate] = t
        idx = self._trailer_combo.findText(current)
        if idx >= 0:
            self._trailer_combo.setCurrentIndex(idx)
        self._trailer_combo.blockSignals(False)

    def _load_invoice_combo(self) -> None:
        """Populate the Invoice auto-fill combo from InvoiceRepository."""
        if not self._invoice_repo or not hasattr(self, "_invoice_combo"):
            return
        try:
            invoices = self._invoice_repo.get_all(limit=200)
        except Exception:
            invoices = []
        self._invoice_map = {}
        current = self._invoice_combo.currentText()
        self._invoice_combo.blockSignals(True)
        self._invoice_combo.clear()
        self._invoice_combo.addItem("")
        for inv in invoices:
            label = f"{inv.get('invoice_number', '')} — {inv.get('total_amount', 0):.2f} {inv.get('currency', 'EUR')}"
            self._invoice_combo.addItem(label)
            self._invoice_map[label] = inv["id"]
        idx = self._invoice_combo.findText(current)
        if idx >= 0:
            self._invoice_combo.setCurrentIndex(idx)
        self._invoice_combo.blockSignals(False)

    def _load_all_db_combos(self) -> None:
        """Load all DB-backed combos. Called on wakeup."""
        self._load_trip_combo()
        self._load_client_combo()
        self._load_vehicle_combo()
        self._load_trailer_combo()
        self._load_invoice_combo()
        # Restore number format from settings
        if hasattr(self, "_format_combo"):
            svc = self._get_receipt_service()
            saved_key = svc.get_format_key()
            for i, key in enumerate(RECEIPT_NUMBER_FORMATS):
                if key == saved_key:
                    self._format_combo.setCurrentIndex(i)
                    self._format_key = saved_key
                    break

    # ══════════════════════════════════════════════════════════════════
    # UI BUILDING
    # ══════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        self._build_toolbar()
        main_layout.addWidget(self._toolbar)

        # Splitter: left form + right preview
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        # Left: scrollable form
        self._scroll = ScrollableFormContainer(self, max_width=900)
        splitter.addWidget(self._scroll)

        # Right: QWebEngineView preview
        self._preview_view = QWebEngineView()
        self._preview_view.setMinimumWidth(420)
        self._preview_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            self._preview_view.page().setBackgroundColor(QColor("#f5f5f0"))
        except Exception:
            pass
        splitter.addWidget(self._preview_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # Build form sections
        self._build_view_header()
        self._build_type_section()
        self._build_invoice_autofill_section()
        self._build_info_section()
        self._build_parties_section()
        self._build_payment_section()
        self._build_logistics_section()
        self._build_purpose_section()
        self._build_financial_section()
        self._build_employee_section()
        self._build_attachments_section()
        self._build_notes_section()
        self._build_branding_section()

        # Initial preview
        QTimer.singleShot(200, self._refresh_preview)

    # ── Toolbar ─────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        self._toolbar = QFrame(self)
        self._toolbar.setProperty("role", "top-bar")
        self._toolbar.setFixedHeight(52)

        layout = QHBoxLayout(self._toolbar)
        layout.setContentsMargins(S["4"], S["2"], S["4"], S["2"])
        layout.setSpacing(S["3"])

        self._generate_btn = Btn(
            self._toolbar,
            f"\U0001F4C4  {t('receipt.editor.generate_pdf')}",
            command=self._on_generate,
            variant="primary",
        )
        layout.addWidget(self._generate_btn)

        layout.addWidget(Divider(self._toolbar, vertical=True))

        self._print_btn = Btn(
            self._toolbar,
            f"\U0001F5A8  {t('receipt.editor.print')}",
            command=self._on_print,
            variant="secondary",
        )
        layout.addWidget(self._print_btn)

        self._save_draft_btn = Btn(
            self._toolbar,
            f"\U0001F4BE  {t('receipt.editor.save_draft')}",
            command=self._save_draft,
            variant="secondary",
        )
        layout.addWidget(self._save_draft_btn)

        self._load_draft_btn = Btn(
            self._toolbar,
            f"\U0001F4C2  {t('receipt.editor.load_draft')}",
            command=self._load_draft,
            variant="secondary",
        )
        layout.addWidget(self._load_draft_btn)

        self._duplicate_btn = Btn(
            self._toolbar,
            f"\U0001F4CB  {t('receipt.editor.duplicate')}",
            command=self._on_duplicate,
            variant="secondary",
        )
        layout.addWidget(self._duplicate_btn)

        self._export_json_btn = Btn(
            self._toolbar,
            f"\U0001F4C4  {t('receipt.editor.export_json')}",
            command=self._on_export_json,
            variant="secondary",
        )
        layout.addWidget(self._export_json_btn)

        self._email_btn = Btn(
            self._toolbar,
            f"\U0001F4E7  {t('receipt.editor.email')}",
            command=self._on_email,
            variant="secondary",
        )
        layout.addWidget(self._email_btn)

        layout.addStretch()

    # ── View Header ─────────────────────────────────────────────────

    def _build_view_header(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._page_title = PageTitle(card, t("receipt.editor.title"))
        card_layout.addWidget(self._page_title)

        self._page_subtitle = Label(
            card,
            t("receipt.editor.subtitle", "Create professional receipts"),
            role="secondary",
        )
        card_layout.addWidget(self._page_subtitle)

        self._scroll.add_widget(card)

    # ── Receipt Type Section ────────────────────────────────────────

    def _build_type_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._type_header = SectionTitle(card, t("receipt.section_type").upper())
        card_layout.addWidget(self._type_header)
        card_layout.addWidget(Divider(card))

        type_values = [t(key) for _, key in RECEIPT_TYPES]
        self._type_combo = StyledComboBox(card, values=type_values)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        card_layout.addWidget(self._type_combo)

        self._scroll.add_widget(card)

        # Map type key → display text for reverse lookup
        self._type_display_map = dict(RECEIPT_TYPES)
        self._type_reverse_map = {t(key): key for _, key in RECEIPT_TYPES}

    # ── Invoice Auto-Fill Section ──────────────────────────────────────

    def _build_invoice_autofill_section(self) -> None:
        """A compact card with an invoice selector that auto-fills the receipt."""
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._invoice_header = SectionTitle(card, t("receipt.section_invoice_autofill").upper())
        card_layout.addWidget(self._invoice_header)
        card_layout.addWidget(Divider(card))

        from ui.widgets import field
        self._invoice_combo = StyledComboBox(card, state="readonly")
        self._invoice_combo.currentTextChanged.connect(self._on_invoice_selected)
        card_layout.addWidget(field(
            card,
            t("receipt.invoice_autofill_label"),
            self._invoice_combo,
            helper_text=t("receipt.invoice_autofill_helper"),
        ))

        self._scroll.add_widget(card)

    # ── Receipt Info Section ────────────────────────────────────────

    def _build_info_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._info_header = SectionTitle(card, t("receipt.section_info").upper())
        card_layout.addWidget(self._info_header)
        card_layout.addWidget(Divider(card))

        # Two-column row
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["3"])

        # Left column
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["2"])

        from ui.widgets import field
        self._receipt_number_entry = StyledLineEdit(
            left, placeholder=t("receipt.number_placeholder"),
        )
        self._receipt_number_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.number_label"), self._receipt_number_entry))

        self._issue_date_entry = StyledLineEdit(
            left, placeholder=t("receipt.issue_date_placeholder"),
        )
        self._issue_date_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.issue_date_label"), self._issue_date_entry))

        row_layout.addWidget(left)

        # Right column
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["2"])

        self._payment_date_entry = StyledLineEdit(
            right, placeholder=t("receipt.payment_date_placeholder"),
        )
        self._payment_date_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.payment_date_label"), self._payment_date_entry))

        self._currency_combo = StyledComboBox(right, values=CURRENCIES)
        self._currency_combo.setCurrentText(self._currency)
        self._currency_combo.currentTextChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.currency_label"), self._currency_combo))

        self._language_combo = StyledComboBox(right, values=["English", "Română"])
        self._language_combo.currentTextChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.language_label"), self._language_combo))

        self._branch_entry = StyledLineEdit(right, placeholder=t("receipt.branch_placeholder"))
        self._branch_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.branch_label"), self._branch_entry))

        # Number format combo
        format_display = [f"{key} ({example})" for key, (_, example) in RECEIPT_NUMBER_FORMATS.items()]
        self._format_combo = StyledComboBox(right, values=format_display)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        right_layout.addWidget(field(right, t("receipt.number_format_label"), self._format_combo))

        row_layout.addWidget(right)
        card_layout.addWidget(row)
        self._scroll.add_widget(card)

    # ── Parties Section ─────────────────────────────────────────────

    def _build_parties_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._parties_header = SectionTitle(card, t("receipt.section_parties").upper())
        card_layout.addWidget(self._parties_header)
        card_layout.addWidget(Divider(card))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["3"])

        # Received From
        from_card = Card(row)
        from_layout = from_card.layout()
        self._from_title = Label(from_card, t("receipt.received_from"), role="bold")
        from_layout.addWidget(self._from_title)

        self._rf_name = StyledLineEdit(from_card)
        self._rf_name.textChanged.connect(self._on_field_changed)
        from_layout.addWidget(self._rf_name)

        self._rf_address = StyledLineEdit(from_card)
        self._rf_address.textChanged.connect(self._on_field_changed)
        from_layout.addWidget(self._rf_address)

        self._rf_vat = StyledLineEdit(from_card)
        self._rf_vat.textChanged.connect(self._on_field_changed)
        from_layout.addWidget(self._rf_vat)

        self._rf_reg = StyledLineEdit(from_card)
        self._rf_reg.textChanged.connect(self._on_field_changed)
        from_layout.addWidget(self._rf_reg)

        self._rf_contact = StyledLineEdit(from_card)
        self._rf_contact.textChanged.connect(self._on_field_changed)
        from_layout.addWidget(self._rf_contact)

        row_layout.addWidget(from_card)

        # Received By
        by_card = Card(row)
        by_layout = by_card.layout()
        self._by_title = Label(by_card, t("receipt.received_by"), role="bold")
        by_layout.addWidget(self._by_title)

        self._rb_name = StyledLineEdit(by_card)
        self._rb_name.textChanged.connect(self._on_field_changed)
        by_layout.addWidget(self._rb_name)

        self._rb_address = StyledLineEdit(by_card)
        self._rb_address.textChanged.connect(self._on_field_changed)
        by_layout.addWidget(self._rb_address)

        self._rb_vat = StyledLineEdit(by_card)
        self._rb_vat.textChanged.connect(self._on_field_changed)
        by_layout.addWidget(self._rb_vat)

        self._rb_reg = StyledLineEdit(by_card)
        self._rb_reg.textChanged.connect(self._on_field_changed)
        by_layout.addWidget(self._rb_reg)

        self._rb_contact = StyledLineEdit(by_card)
        self._rb_contact.textChanged.connect(self._on_field_changed)
        by_layout.addWidget(self._rb_contact)

        row_layout.addWidget(by_card)
        card_layout.addWidget(row)
        self._scroll.add_widget(card)

    # ── Payment Details Section ─────────────────────────────────────

    def _build_payment_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._payment_header = SectionTitle(card, t("receipt.section_payment").upper())
        card_layout.addWidget(self._payment_header)
        card_layout.addWidget(Divider(card))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["3"])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["2"])

        from ui.widgets import field
        self._payment_method_combo = StyledComboBox(left, values=PAYMENT_METHODS)
        self._payment_method_combo.currentTextChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.payment_method_label"), self._payment_method_combo))

        self._reference_number_entry = StyledLineEdit(left)
        self._reference_number_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.reference_number_label"), self._reference_number_entry))

        self._transaction_id_entry = StyledLineEdit(left)
        self._transaction_id_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.transaction_id_label"), self._transaction_id_entry))

        row_layout.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["2"])

        self._bank_reference_entry = StyledLineEdit(right)
        self._bank_reference_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.bank_reference_label"), self._bank_reference_entry))

        self._invoice_reference_entry = StyledLineEdit(right)
        self._invoice_reference_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.invoice_reference_label"), self._invoice_reference_entry))

        row_layout.addWidget(right)
        card_layout.addWidget(row)
        self._scroll.add_widget(card)

    # ── Logistics Section ───────────────────────────────────────────

    def _build_logistics_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._logistics_header = SectionTitle(card, t("receipt.section_logistics").upper())
        card_layout.addWidget(self._logistics_header)
        card_layout.addWidget(Divider(card))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["3"])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["2"])

        from ui.widgets import field
        # Trip combo
        self._related_trip_combo = StyledComboBox(left, state="readonly")
        self._related_trip_combo.currentTextChanged.connect(self._on_trip_combo_changed)
        left_layout.addWidget(field(left, t("receipt.related_trip_label"), self._related_trip_combo))

        # Customer combo
        self._customer_combo = StyledComboBox(left, state="readonly")
        self._customer_combo.currentTextChanged.connect(self._on_customer_combo_changed)
        left_layout.addWidget(field(left, t("receipt.customer_label"), self._customer_combo))

        # Vehicle combo
        self._vehicle_combo = StyledComboBox(left, state="readonly")
        left_layout.addWidget(field(left, t("receipt.vehicle_label"), self._vehicle_combo))

        self._pickup_location_entry = StyledLineEdit(left)
        self._pickup_location_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.pickup_label"), self._pickup_location_entry))

        self._delivery_location_entry = StyledLineEdit(left)
        self._delivery_location_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.delivery_label"), self._delivery_location_entry))

        row_layout.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["2"])

        # Trailer combo
        self._trailer_combo = StyledComboBox(right, state="readonly")
        right_layout.addWidget(field(right, t("receipt.trailer_label"), self._trailer_combo))

        self._route_entry = StyledLineEdit(right)
        self._route_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.route_label"), self._route_entry))

        self._dispatcher_entry = StyledLineEdit(right)
        self._dispatcher_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.dispatcher_label"), self._dispatcher_entry))

        row_layout.addWidget(right)
        card_layout.addWidget(row)
        self._scroll.add_widget(card)

    # ── Purpose Section ─────────────────────────────────────────────

    def _build_purpose_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._purpose_header = SectionTitle(card, t("receipt.section_purpose").upper())
        card_layout.addWidget(self._purpose_header)
        card_layout.addWidget(Divider(card))

        self._purpose_edit = StyledTextEdit(card, height=80)
        self._purpose_edit.textChanged.connect(self._on_field_changed)
        card_layout.addWidget(self._purpose_edit)

        self._scroll.add_widget(card)

    # ── Financial Section ───────────────────────────────────────────

    def _build_financial_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._financial_header = SectionTitle(card, t("receipt.section_financial").upper())
        card_layout.addWidget(self._financial_header)
        card_layout.addWidget(Divider(card))

        from ui.widgets import field
        grid = QWidget()
        grid_layout = QVBoxLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(S["2"])

        # Amount
        self._amount_entry = StyledLineEdit(grid, placeholder=t("receipt.amount_placeholder"))
        self._amount_entry.textChanged.connect(self._on_amount_changed)
        grid_layout.addWidget(field(grid, t("receipt.amount_label"), self._amount_entry,
                                    helper_text=t("receipt.amount_helper")))

        # VAT Rate
        self._vat_rate_entry = StyledLineEdit(grid, placeholder=t("receipt.vat_placeholder"))
        self._vat_rate_entry.textChanged.connect(self._on_amount_changed)
        grid_layout.addWidget(field(grid, t("receipt.vat_rate_label"), self._vat_rate_entry,
                                    helper_text=t("receipt.vat_helper")))

        # VAT Amount (read-only)
        self._vat_amount_entry = StyledLineEdit(grid, placeholder="0.00")
        self._vat_amount_entry.setReadOnly(True)
        grid_layout.addWidget(field(grid, t("receipt.vat_amount_label"), self._vat_amount_entry))

        # Total (read-only)
        self._total_entry = StyledLineEdit(grid, placeholder="0.00")
        self._total_entry.setReadOnly(True)
        grid_layout.addWidget(field(grid, t("receipt.total_label"), self._total_entry))

        # Amount in Words (read-only)
        self._amount_words_entry = StyledLineEdit(grid, placeholder=t("receipt.words_placeholder"))
        self._amount_words_entry.setReadOnly(True)
        grid_layout.addWidget(field(grid, t("receipt.amount_words_label"), self._amount_words_entry))

        card_layout.addWidget(grid)
        self._scroll.add_widget(card)

    # ── Employee Section (conditional) ──────────────────────────────

    def _build_employee_section(self) -> None:
        self._employee_card = Card(self._scroll.content)
        card_layout = self._employee_card.layout()

        self._employee_header = SectionTitle(self._employee_card, t("receipt.section_employee").upper())
        card_layout.addWidget(self._employee_header)
        card_layout.addWidget(Divider(self._employee_card))

        grid = QWidget()
        grid_layout = QHBoxLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(S["3"])

        from ui.widgets import field
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["2"])

        self._employee_name_entry = StyledLineEdit(left)
        self._employee_name_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.employee_name_label"), self._employee_name_entry))

        self._department_entry = StyledLineEdit(left)
        self._department_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.department_label"), self._department_entry))

        self._expense_category_entry = StyledLineEdit(left)
        self._expense_category_entry.textChanged.connect(self._on_field_changed)
        left_layout.addWidget(field(left, t("receipt.expense_category_label"), self._expense_category_entry))

        grid_layout.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["2"])

        self._mileage_entry = StyledLineEdit(right, placeholder="0")
        self._mileage_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.mileage_label"), self._mileage_entry))

        self._fuel_entry = StyledLineEdit(right, placeholder="0")
        self._fuel_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.fuel_label"), self._fuel_entry))

        self._accommodation_entry = StyledLineEdit(right, placeholder="0")
        self._accommodation_entry.textChanged.connect(self._on_field_changed)
        right_layout.addWidget(field(right, t("receipt.accommodation_label"), self._accommodation_entry))

        grid_layout.addWidget(right)

        right2 = QWidget()
        right2_layout = QVBoxLayout(right2)
        right2_layout.setContentsMargins(0, 0, 0, 0)
        right2_layout.setSpacing(S["2"])

        self._meals_entry = StyledLineEdit(right2, placeholder="0")
        self._meals_entry.textChanged.connect(self._on_field_changed)
        right2_layout.addWidget(field(right2, t("receipt.meals_label"), self._meals_entry))

        self._parking_entry = StyledLineEdit(right2, placeholder="0")
        self._parking_entry.textChanged.connect(self._on_field_changed)
        right2_layout.addWidget(field(right2, t("receipt.parking_label"), self._parking_entry))

        self._tolls_entry = StyledLineEdit(right2, placeholder="0")
        self._tolls_entry.textChanged.connect(self._on_field_changed)
        right2_layout.addWidget(field(right2, t("receipt.tolls_label"), self._tolls_entry))

        self._other_expense_entry = StyledLineEdit(right2, placeholder="0")
        self._other_expense_entry.textChanged.connect(self._on_field_changed)
        right2_layout.addWidget(field(right2, t("receipt.other_label"), self._other_expense_entry))

        grid_layout.addWidget(right2)

        card_layout.addWidget(grid)
        self._scroll.add_widget(self._employee_card)
        self._employee_card.setVisible(False)

    # ── Attachments Section ─────────────────────────────────────────

    def _build_attachments_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._attachments_header = SectionTitle(card, t("receipt.section_attachments").upper())
        card_layout.addWidget(self._attachments_header)
        card_layout.addWidget(Divider(card))

        from ui.widgets import field
        # Attachment type selector
        type_values = [t(key) for _, key in ATTACHMENT_TYPES]
        self._attach_type_combo = StyledComboBox(card, values=type_values)
        self._attach_type_combo.setCurrentIndex(len(type_values) - 1)  # default: "Other"
        card_layout.addWidget(field(card, t("receipt.attach_type_label"), self._attach_type_combo))

        # Type display map
        self._attach_type_display_map = {t(key): key_val for key_val, key in ATTACHMENT_TYPES}

        # Attach button
        self._attach_btn = Btn(
            card,
            f"  {t('receipt.editor.attach_files')}",
            command=self._on_attach_files,
            variant="secondary",
        )
        card_layout.addWidget(self._attach_btn)

        # Attachment list (scrollable with remove buttons)
        self._attachment_scroll = QScrollArea(card)
        self._attachment_scroll.setWidgetResizable(True)
        self._attachment_scroll.setFrameShape(QFrame.NoFrame)
        self._attachment_scroll.setMaximumHeight(150)
        self._attachment_list_widget = QWidget()
        self._attachment_list_layout = QVBoxLayout(self._attachment_list_widget)
        self._attachment_list_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_list_layout.setSpacing(2)
        self._attachment_list_layout.setAlignment(Qt.AlignTop)
        self._attachment_scroll.setWidget(self._attachment_list_widget)
        card_layout.addWidget(self._attachment_scroll)

        self._scroll.add_widget(card)

    # ── Notes Section ───────────────────────────────────────────────

    def _build_notes_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._notes_header = SectionTitle(card, t("receipt.section_notes").upper())
        card_layout.addWidget(self._notes_header)
        card_layout.addWidget(Divider(card))

        self._notes_edit = StyledTextEdit(card, height=100)
        self._notes_edit.textChanged.connect(self._on_field_changed)
        card_layout.addWidget(self._notes_edit)

        self._scroll.add_widget(card)

    # ── Branding Section ────────────────────────────────────────────

    def _build_branding_section(self) -> None:
        card = Card(self._scroll.content)
        card_layout = card.layout()

        self._branding_header = SectionTitle(card, t("receipt.section_branding").upper())
        card_layout.addWidget(self._branding_header)
        card_layout.addWidget(Divider(card))

        from ui.widgets import field
        # Logo
        logo_row = QWidget()
        logo_layout = QHBoxLayout(logo_row)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(S["2"])

        self._logo_entry = StyledLineEdit(card, placeholder=t("receipt.logo_placeholder"))
        logo_layout.addWidget(self._logo_entry, 1)

        self._browse_logo_btn = Btn(
            card, t("receipt.editor.browse"), command=lambda: self._browse_file("logo"),
            variant="ghost",
        )
        logo_layout.addWidget(self._browse_logo_btn)
        card_layout.addWidget(field(card, t("receipt.logo_label"), logo_row))

        # Signature
        sig_row = QWidget()
        sig_layout = QHBoxLayout(sig_row)
        sig_layout.setContentsMargins(0, 0, 0, 0)
        sig_layout.setSpacing(S["2"])

        self._signature_entry = StyledLineEdit(card, placeholder=t("receipt.signature_placeholder"))
        sig_layout.addWidget(self._signature_entry, 1)

        self._browse_sig_btn = Btn(
            card, t("receipt.editor.browse"), command=lambda: self._browse_file("signature"),
            variant="ghost",
        )
        sig_layout.addWidget(self._browse_sig_btn)
        card_layout.addWidget(field(card, t("receipt.signature_label"), sig_row))

        # Stamp
        stamp_row = QWidget()
        stamp_layout = QHBoxLayout(stamp_row)
        stamp_layout.setContentsMargins(0, 0, 0, 0)
        stamp_layout.setSpacing(S["2"])

        self._stamp_entry = StyledLineEdit(card, placeholder=t("receipt.stamp_placeholder"))
        stamp_layout.addWidget(self._stamp_entry, 1)

        self._browse_stamp_btn = Btn(
            card, t("receipt.editor.browse"), command=lambda: self._browse_file("stamp"),
            variant="ghost",
        )
        stamp_layout.addWidget(self._browse_stamp_btn)
        card_layout.addWidget(field(card, t("receipt.stamp_label"), stamp_row))

        self._scroll.add_widget(card)

    # ── File browse helper ──────────────────────────────────────────

    def _browse_file(self, field_name: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("receipt.editor.select_file"),
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*.*)",
        )
        if not path:
            return
        if field_name == "logo":
            self._logo_entry.setText(path)
            self._logo_path = path
        elif field_name == "signature":
            self._signature_entry.setText(path)
            self._signature_path = path
        elif field_name == "stamp":
            self._stamp_entry.setText(path)
            self._stamp_path = path
        self._on_field_changed()

    # ══════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ══════════════════════════════════════════════════════════════════

    def _on_type_changed(self, text: str) -> None:
        """Show/hide employee section based on receipt type."""
        self._receipt_type = self._type_reverse_map.get(text, "other")
        is_employee = self._receipt_type in (
            "driver_reimbursement", "employee_expense",
            "fuel_reimbursement", "toll_reimbursement",
        )
        self._employee_card.setVisible(is_employee)
        self._on_field_changed()

    def _on_amount_changed(self) -> None:
        """Recalculate VAT, total, amount in words."""
        self._recalculate()
        self._schedule_preview_refresh()

    def _on_field_changed(self) -> None:
        """Mark state changed and schedule preview refresh."""
        self._sync_state()
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self) -> None:
        """Debounce preview updates (300ms)."""
        self._refresh_task.schedule()

    # ── Combo change handlers ─────────────────────────────────────────

    def _on_trip_combo_changed(self, text: str) -> None:
        """Auto-fill pickup/delivery from selected trip's route stops."""
        if not text or text not in self._trip_combo_map:
            return
        trip_id = self._trip_combo_map[text]
        if self._trip_svc:
            trip = self._trip_svc.get_by_id(trip_id)
            if trip:
                # Fill pickup/delivery from route stops
                if trip.get("route_history_v2_id") and self._trip_svc:
                    try:
                        stops_json = self._trip_svc.get_route_stops_json(trip["route_history_v2_id"])
                        if stops_json:
                            import json as _json
                            stops = _json.loads(stops_json)
                            if isinstance(stops, list) and len(stops) >= 2:
                                self._pickup_location_entry.setText(stops[0].get("address", ""))
                                self._delivery_location_entry.setText(stops[-1].get("address", ""))
                    except Exception:
                        pass
                # Try to match customer in client combo
                client_name = trip.get("client_name", "")
                if client_name:
                    idx = self._customer_combo.findText(client_name)
                    if idx >= 0:
                        self._customer_combo.setCurrentIndex(idx)
        self._schedule_preview_refresh()

    def _on_customer_combo_changed(self, text: str) -> None:
        """Auto-fill Received From section from selected client."""
        if not text or text not in self._client_map:
            return
        client = self._client_map[text]
        self._rf_name.setText(client.get("name", ""))
        self._rf_address.setText(client.get("address", ""))
        self._rf_vat.setText(client.get("vat_number", ""))
        self._rf_contact.setText(client.get("phone", ""))
        self._schedule_preview_refresh()

    def _on_format_changed(self, text: str) -> None:
        """Update receipt number when format changes."""
        if not text:
            return
        # Extract format key from "key (example)" display
        for key in RECEIPT_NUMBER_FORMATS:
            if text.startswith(key):
                self._format_key = key
                break
        svc = self._get_receipt_service()
        svc.set_format_key(self._format_key)
        self._update_receipt_number()
        self._schedule_preview_refresh()

    def _on_invoice_selected(self, text: str) -> None:
        """Auto-fill receipt fields from the selected invoice."""
        if not text or text not in self._invoice_map or not self._invoice_repo:
            return
        invoice = self._invoice_repo.get_by_id(self._invoice_map[text])
        if not invoice:
            return
        # Look up the associated trip for client info
        trip_data = {}
        if invoice.get("trip_id") and self._trip_svc:
            trip_data = self._trip_svc.get_by_id(invoice["trip_id"]) or {}
        # Fill customer from trip's client
        client_name = trip_data.get("client_name", "")
        if client_name and hasattr(self, "_customer_combo"):
            idx = self._customer_combo.findText(client_name)
            if idx >= 0:
                self._customer_combo.setCurrentIndex(idx)
        # Fill amount
        total_amt = invoice.get("total_amount", 0)
        if total_amt:
            self._amount_entry.setText(str(total_amt))
        # Fill currency
        inv_currency = invoice.get("currency", "") or trip_data.get("currency", "")
        if inv_currency:
            self._currency_combo.setCurrentText(inv_currency)
        # Fill invoice reference
        self._invoice_reference_entry.setText(invoice.get("invoice_number", ""))
        # Fill related trip
        if trip_data.get("id"):
            trip_label = ""
            for lbl, tid in self._trip_combo_map.items():
                if tid == trip_data["id"]:
                    trip_label = lbl
                    break
            if trip_label and hasattr(self, "_related_trip_combo"):
                idx = self._related_trip_combo.findText(trip_label)
                if idx >= 0:
                    self._related_trip_combo.setCurrentIndex(idx)
        # Recalculate financials
        self._recalculate()
        self._schedule_preview_refresh()

    # ══════════════════════════════════════════════════════════════════
    # STATE MANAGEMENT
    # ══════════════════════════════════════════════════════════════════

    def _sync_state(self) -> None:
        """Read all form fields into instance variables."""
        # Info
        self._receipt_number = self._receipt_number_entry.text().strip()
        self._issue_date = self._issue_date_entry.text().strip()
        self._payment_date = self._payment_date_entry.text().strip()
        self._currency = self._currency_combo.currentText()
        lang_text = self._language_combo.currentText()
        self._language = "ro" if "Română" in lang_text else "en"
        self._branch = self._branch_entry.text().strip()
        fmt_text = self._format_combo.currentText() if hasattr(self, "_format_combo") else ""
        for key in RECEIPT_NUMBER_FORMATS:
            if fmt_text.startswith(key):
                self._format_key = key
                break

        # Receipt type
        type_text = self._type_combo.currentText()
        self._receipt_type = self._type_reverse_map.get(type_text, "other")

        # Parties
        self._received_from_name = self._rf_name.text().strip()
        self._received_from_address = self._rf_address.text().strip()
        self._received_from_vat = self._rf_vat.text().strip()
        self._received_from_reg = self._rf_reg.text().strip()
        self._received_from_contact = self._rf_contact.text().strip()

        self._received_by_name = self._rb_name.text().strip()
        self._received_by_address = self._rb_address.text().strip()
        self._received_by_vat = self._rb_vat.text().strip()
        self._received_by_reg = self._rb_reg.text().strip()
        self._received_by_contact = self._rb_contact.text().strip()

        # Payment
        self._payment_method = self._payment_method_combo.currentText()
        self._reference_number = self._reference_number_entry.text().strip()
        self._transaction_id = self._transaction_id_entry.text().strip()
        self._bank_reference = self._bank_reference_entry.text().strip()
        self._invoice_reference = self._invoice_reference_entry.text().strip()

        # Logistics
        self._related_trip = self._related_trip_combo.currentText() if hasattr(self, "_related_trip_combo") else ""
        self._customer = self._customer_combo.currentText() if hasattr(self, "_customer_combo") else ""
        self._vehicle = self._vehicle_combo.currentText() if hasattr(self, "_vehicle_combo") else ""
        self._trailer = self._trailer_combo.currentText() if hasattr(self, "_trailer_combo") else ""
        self._pickup_location = self._pickup_location_entry.text().strip()
        self._delivery_location = self._delivery_location_entry.text().strip()
        self._route = self._route_entry.text().strip()
        self._dispatcher = self._dispatcher_entry.text().strip()

        # Purpose (from QPlainTextEdit)
        self._purpose = self._purpose_edit.toPlainText().strip()

        # Employee
        self._employee_name = self._employee_name_entry.text().strip()
        self._department = self._department_entry.text().strip()
        self._expense_category = self._expense_category_entry.text().strip()
        self._mileage = self._safe_float(self._mileage_entry.text())
        self._fuel = self._safe_float(self._fuel_entry.text())
        self._accommodation = self._safe_float(self._accommodation_entry.text())
        self._meals = self._safe_float(self._meals_entry.text())
        self._parking = self._safe_float(self._parking_entry.text())
        self._tolls = self._safe_float(self._tolls_entry.text())
        self._other_expense = self._safe_float(self._other_expense_entry.text())

        # Branding
        self._logo_path = self._logo_entry.text().strip()
        self._signature_path = self._signature_entry.text().strip()
        self._stamp_path = self._stamp_entry.text().strip()

        # Notes
        self._notes = self._notes_edit.toPlainText().strip()

    def _all_inputs(self) -> list[QWidget]:
        """Return all form input widgets for validation highlighting."""
        result = [
            self._amount_entry, self._vat_rate_entry,
            self._receipt_number_entry, self._issue_date_entry, self._payment_date_entry,
            self._rf_name, self._rf_address, self._rf_vat, self._rf_reg, self._rf_contact,
            self._rb_name, self._rb_address, self._rb_vat, self._rb_reg, self._rb_contact,
            self._reference_number_entry, self._transaction_id_entry,
            self._bank_reference_entry, self._invoice_reference_entry,
            self._pickup_location_entry, self._delivery_location_entry,
            self._route_entry, self._dispatcher_entry,
            self._employee_name_entry, self._department_entry, self._expense_category_entry,
            self._mileage_entry, self._fuel_entry, self._accommodation_entry,
            self._meals_entry, self._parking_entry, self._tolls_entry, self._other_expense_entry,
            self._logo_entry, self._signature_entry, self._stamp_entry,
        ]
        if hasattr(self, "_related_trip_combo"):
            result.append(self._related_trip_combo)
        if hasattr(self, "_customer_combo"):
            result.append(self._customer_combo)
        if hasattr(self, "_vehicle_combo"):
            result.append(self._vehicle_combo)
        if hasattr(self, "_trailer_combo"):
            result.append(self._trailer_combo)
        return result

    @staticmethod
    def _safe_float(val: str) -> float:
        try:
            return float(val.replace(",", ".")) if val.strip() else 0
        except (ValueError, AttributeError):
            return 0

    def _recalculate(self) -> None:
        """Calculate VAT amount, total, and amount-in-words."""
        amount = self._safe_float(self._amount_entry.text())
        vat_rate = self._safe_float(self._vat_rate_entry.text())
        vat_amount = round(amount * vat_rate / 100, 2)
        total = amount + vat_amount

        self._vat_amount_entry.setText(f"{vat_amount:.2f}")
        self._total_entry.setText(f"{total:.2f}")

        self._amount = amount
        self._vat_rate = vat_rate
        self._vat_amount = vat_amount
        self._total = total

        # Amount in words
        if total > 0:
            try:
                from utils.number_to_words import number_to_words
                words = number_to_words(total, self._currency, self._language)
                self._amount_words_entry.setText(words)
                self._amount_words = words
            except Exception:
                self._amount_words_entry.setText("")
                self._amount_words = ""
        else:
            self._amount_words_entry.setText("")
            self._amount_words = ""

    # ══════════════════════════════════════════════════════════════════
    # LIVE PREVIEW (QWebEngineView HTML)
    # ══════════════════════════════════════════════════════════════════

    def _refresh_preview(self) -> None:
        """Re-render the live preview in QWebEngineView."""
        self._sync_state()
        self._recalculate()
        html = self._build_preview_html()
        self._preview_view.setHtml(html)

    def _build_preview_html(self) -> str:
        """Build the receipt preview HTML string."""
        conf = load_company_config()
        company_name = conf.get("company_name", "")
        company_address = conf.get("address", "")
        company_vat = conf.get("cui", "")
        company_reg = conf.get("reg_number", "")
        company_phone = conf.get("phone", "")
        company_email = conf.get("email", "")

        # Use self._received_by_* if not set, fallback to company config
        by_name = self._received_by_name or company_name
        by_address = self._received_by_address or company_address
        by_vat = self._received_by_vat or company_vat
        by_reg = self._received_by_reg or company_reg
        by_contact = self._received_by_contact or company_phone

        # Determine receipt type label
        type_key = self._type_display_map.get(self._receipt_type, "receipt.type_other")
        type_label = t(type_key)

        logo_html = ""
        if self._logo_path and os.path.isfile(self._logo_path):
            logo_html = f'<div style="text-align:left;margin-bottom:6px"><img src="file:///{os.path.abspath(self._logo_path).replace(chr(92), "/")}" style="max-height:50px;max-width:160px"></div>'

        stamp_html = ""
        if self._stamp_path and os.path.isfile(self._stamp_path):
            stamp_html = f'<div style="text-align:right"><img src="file:///{os.path.abspath(self._stamp_path).replace(chr(92), "/")}" style="max-height:50px;max-width:120px"></div>'

        # Build HTML
        return f"""<!DOCTYPE html>
<html lang="{self._language}">
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 12px;
    color: #222;
    background: #f5f5f0;
    margin: 0; padding: 16px;
  }}
  .page {{
    max-width: 680px; margin: 0 auto;
    background: #fff; padding: 32px 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12);
    border-radius: 4px;
  }}
  .accent-bar {{
    height: 3px; background: #6366f1; margin: 8px 0 16px 0;
  }}
  h1 {{
    font-size: 20px; color: #6366f1; text-align: center;
    margin: 0 0 4px 0;
  }}
  .subtitle {{
    font-size: 10px; color: #888; text-align: center;
    margin: 0 0 12px 0;
  }}
  .meta {{ font-size: 10px; margin-bottom: 8px; }}
  .meta b {{ color: #444; }}
  .section {{ margin: 10px 0; }}
  .section-title {{ font-size: 10px; color: #6366f1; font-weight: bold; margin: 0 0 4px 0; }}
  .parties {{ display: flex; gap: 12px; margin: 8px 0; }}
  .party {{ flex: 1; border: 1px solid #ddd; border-radius: 4px; padding: 8px; }}
  .party b {{ font-size: 10px; color: #6366f1; }}
  .party p {{ margin: 2px 0; font-size: 10px; line-height: 1.4; }}
  table.financial {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
  table.financial td {{ padding: 4px 8px; font-size: 11px; }}
  table.financial td:last-child {{ text-align: right; }}
  table.financial .total {{ font-weight: bold; font-size: 13px; color: #6366f1; }}
  table.financial .total-line {{ border-top: 2px solid #6366f1; }}
  .words {{ font-style: italic; color: #555; font-size: 10px; margin: 6px 0; }}
  .logistics {{ font-size: 10px; margin: 8px 0; }}
  .logistics td {{ padding: 2px 8px 2px 0; }}
  .signatures {{ display: flex; justify-content: space-between; margin: 16px 0; }}
  .sig-block {{ font-size: 9px; }}
  .sig-block .line {{ border-top: 1px solid #333; width: 140px; margin: 4px 0; }}
  .footer {{ font-size: 8px; color: #999; text-align: center; border-top: 1px solid #ddd; padding-top: 6px; margin-top: 12px; }}
</style>
</head>
<body>
<div class="page">
  {logo_html}

  <div class="meta">
    <b>{t('receipt.number_label')}:</b> {self._receipt_number}
    {f'&nbsp;&nbsp;|&nbsp;&nbsp;<b>{t("receipt.branch_label")}:</b> {self._branch}' if self._branch else ''}
  </div>
  <h1>{t('receipt.title')}</h1>
  <div class="subtitle">{type_label} &mdash; {self._receipt_number}</div>
  <div class="accent-bar"></div>

  <div class="meta">
    <b>{t('receipt.issue_date_label')}:</b> {self._issue_date}
    &nbsp;&nbsp; <b>{t('receipt.payment_date_label')}:</b> {self._payment_date}
    &nbsp;&nbsp; <b>{t('receipt.currency_label')}:</b> {self._currency}
  </div>

  <div class="parties">
    <div class="party">
      <b>{t('receipt.received_from')}</b>
      {'<p style="color:#bbb;font-size:9px">' + t("receipt.received_from_placeholder", "—") + '</p>' if not (self._received_from_name or self._received_from_address or self._received_from_vat or self._received_from_reg) else ''}
      {'<p>' + self._received_from_name + '</p>' if self._received_from_name else ''}
      {'<p>' + self._received_from_address + '</p>' if self._received_from_address else ''}
      {'<p>VAT: ' + self._received_from_vat + '</p>' if self._received_from_vat else ''}
      {'<p>Reg: ' + self._received_from_reg + '</p>' if self._received_from_reg else ''}
    </div>
    <div class="party">
      <b>{t('receipt.received_by')}</b>
      <p>{by_name}</p>
      <p>{by_address}</p>
      <p>{'VAT: ' + by_vat if by_vat else ''}</p>
      <p>{'Reg: ' + by_reg if by_reg else ''}</p>
    </div>
  </div>

  {self._preview_purpose_html()}
  {self._preview_payment_html()}
  {self._preview_logistics_html()}
  {self._preview_employee_html()}

  <div class="section section-title">{t('receipt.section_financial').upper()}</div>
  <table class="financial">
    <tr><td>{t('receipt.amount_label')}</td><td>{self._amount:.2f} {self._currency}</td></tr>
    {f'<tr><td>{t("receipt.vat_rate_label")}</td><td>{self._vat_rate:.1f}%</td></tr>' if self._vat_rate > 0 else ''}
    {f'<tr><td>{t("receipt.vat_amount_label")}</td><td>{self._vat_amount:.2f} {self._currency}</td></tr>' if self._vat_rate > 0 else ''}
    <tr class="total-line"><td class="total">{t('receipt.total_label')}</td><td class="total">{self._total:.2f} {self._currency}</td></tr>
    {'<tr><td colspan="2" style="color:#999;font-size:9px;text-align:center;padding-top:4px">' + t("receipt.amount_hint", "Introduceti suma mai jos") + '</td></tr>' if self._amount == 0 and self._total == 0 else ''}
  </table>

  {f'<div class="words">{self._amount_words}</div>' if self._amount_words else ''}

  {self._preview_notes_html()}

  <div class="signatures">
    <div class="sig-block">
      <b>{t('receipt.company_signature_label')}</b>
      <div class="line"></div>
      <span style="font-size:8px">{company_name}</span>
    </div>
    <div class="sig-block">
      <b>{t('receipt.recipient_signature_label')}</b>
      <div class="line"></div>
      <span style="font-size:8px">{self._received_from_name}</span>
    </div>
  </div>

  {stamp_html}

  <div class="footer">{t('receipt.generated_by')} &mdash; {company_name}</div>
</div>
</body>
</html>"""

    def _preview_purpose_html(self) -> str:
        if not self._purpose:
            return ""
        return f'<div class="section"><div class="section-title">{t("receipt.purpose_label")}</div><p style="font-size:10px">{self._purpose}</p></div>'

    def _preview_payment_html(self) -> str:
        parts = []
        if self._payment_method:
            parts.append(f"<b>{t('receipt.payment_method_label')}:</b> {self._payment_method}")
        if self._reference_number:
            parts.append(f"<b>{t('receipt.reference_number_label')}:</b> {self._reference_number}")
        if self._transaction_id:
            parts.append(f"<b>{t('receipt.transaction_id_label')}:</b> {self._transaction_id}")
        if self._bank_reference:
            parts.append(f"<b>{t('receipt.bank_reference_label')}:</b> {self._bank_reference}")
        if self._invoice_reference:
            parts.append(f"<b>{t('receipt.invoice_reference_label')}:</b> {self._invoice_reference}")
        if not parts:
            return ""
        return f'<div class="section"><div class="section-title">{t("receipt.section_payment").upper()}</div><p style="font-size:10px">{"<br>".join(parts)}</p></div>'

    def _preview_logistics_html(self) -> str:
        parts = []
        if self._related_trip:
            parts.append(f"<b>{t('receipt.related_trip_label')}:</b> {self._related_trip}")
        if self._customer:
            parts.append(f"<b>{t('receipt.customer_label')}:</b> {self._customer}")
        if self._vehicle:
            parts.append(f"<b>{t('receipt.vehicle_label')}:</b> {self._vehicle}")
        if self._trailer:
            parts.append(f"<b>{t('receipt.trailer_label')}:</b> {self._trailer}")
        if self._pickup_location:
            parts.append(f"<b>{t('receipt.pickup_label')}:</b> {self._pickup_location}")
        if self._delivery_location:
            parts.append(f"<b>{t('receipt.delivery_label')}:</b> {self._delivery_location}")
        if self._route:
            parts.append(f"<b>{t('receipt.route_label')}:</b> {self._route}")
        if self._dispatcher:
            parts.append(f"<b>{t('receipt.dispatcher_label')}:</b> {self._dispatcher}")
        if not parts:
            return ""
        return f'<div class="section"><div class="section-title">{t("receipt.section_logistics").upper()}</div><table class="logistics">{"".join(f"<tr><td>{p}</td></tr>" for p in parts)}</table></div>'

    def _preview_employee_html(self) -> str:
        has_employee = self._employee_name or self._department or self._expense_category
        has_amounts = any([self._mileage, self._fuel, self._accommodation,
                           self._meals, self._parking, self._tolls, self._other_expense])
        if not (has_employee or has_amounts):
            return ""
        parts = []
        if self._employee_name:
            parts.append(f"<b>{t('receipt.employee_name_label')}:</b> {self._employee_name}")
        if self._department:
            parts.append(f"<b>{t('receipt.department_label')}:</b> {self._department}")
        if self._expense_category:
            parts.append(f"<b>{t('receipt.expense_category_label')}:</b> {self._expense_category}")
        if self._mileage:
            parts.append(f"<b>{t('receipt.mileage_label')}:</b> {self._mileage}")
        if self._fuel:
            parts.append(f"<b>{t('receipt.fuel_label')}:</b> {self._fuel:.2f}")
        if self._accommodation:
            parts.append(f"<b>{t('receipt.accommodation_label')}:</b> {self._accommodation:.2f}")
        if self._meals:
            parts.append(f"<b>{t('receipt.meals_label')}:</b> {self._meals:.2f}")
        if self._parking:
            parts.append(f"<b>{t('receipt.parking_label')}:</b> {self._parking:.2f}")
        if self._tolls:
            parts.append(f"<b>{t('receipt.tolls_label')}:</b> {self._tolls:.2f}")
        if self._other_expense:
            parts.append(f"<b>{t('receipt.other_label')}:</b> {self._other_expense:.2f}")
        return f'<div class="section"><div class="section-title">{t("receipt.section_employee").upper()}</div><table class="logistics">{"".join(f"<tr><td>{p}</td></tr>" for p in parts)}</table></div>'

    def _preview_notes_html(self) -> str:
        if not self._notes:
            return ""
        return f'<div class="section"><div class="section-title">{t("receipt.section_notes").upper()}</div><p style="font-size:10px">{self._notes}</p></div>'

    # ══════════════════════════════════════════════════════════════════
    # COMPANY CONFIG
    # ══════════════════════════════════════════════════════════════════

    def _load_company_config(self) -> None:
        try:
            conf = load_company_config()
            self._received_by_name = conf.get("company_name", "")
            self._received_by_address = conf.get("address", "")
            self._received_by_vat = conf.get("cui", "")
            self._received_by_reg = conf.get("reg_number", "")
            self._received_by_contact = conf.get("phone", "")
            self._logo_path = conf.get("logo_path", "")
            self._signature_path = conf.get("signature_path", "")
            self._stamp_path = conf.get("stamp_path", "")

            # Update form fields
            self._rb_name.setText(self._received_by_name)
            self._rb_address.setText(self._received_by_address)
            self._rb_vat.setText(self._received_by_vat)
            self._rb_reg.setText(self._received_by_reg)
            self._rb_contact.setText(self._received_by_contact)
            self._logo_entry.setText(self._logo_path)
            self._signature_entry.setText(self._signature_path)
            self._stamp_entry.setText(self._stamp_path)
        except Exception as exc:
            logger.warning("Failed to load company config: %s", exc)

    def _update_receipt_number(self) -> None:
        """Auto-generate and display the next receipt number."""
        try:
            svc = self._get_receipt_service()
            if svc and svc._receipt_repo:
                num = svc._receipt_repo.get_next_number(format_key=self._format_key)
                self._receipt_number_entry.setText(num)
                self._receipt_number = num
        except Exception as exc:
            logger.warning("Failed to generate receipt number: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # VALIDATION
    # ══════════════════════════════════════════════════════════════════

    def _validate(self) -> list[str]:
        """Return list of validation error messages. Empty list = valid.

        Also highlights invalid fields via ``mark_field_invalid()``
        (handled by global QSS ``[invalid=\"true\"]`` selector).
        """
        # Collect all input widgets once
        all_inputs = self._all_inputs()

        # Clear previous highlights
        from utils.editor_toolkit import highlight_invalid_fields
        highlight_invalid_fields(all_inputs)

        errors: list[str] = []
        invalid_fields: list[QWidget] = []

        # Amount — check total as well when VAT is present
        if (not self._amount or self._amount <= 0) and (not self._total or self._total <= 0):
            errors.append(t("receipt.validation.amount_required"))
            invalid_fields.append(self._amount_entry)

        # Recipient name
        if not self._received_from_name:
            errors.append(t("receipt.validation.recipient_required"))
            invalid_fields.append(self._rf_name)

        # Receipt number
        if not self._receipt_number:
            errors.append(t("receipt.validation.number_required"))
            invalid_fields.append(self._receipt_number_entry)

        # Issue date
        if not self._issue_date:
            errors.append(t("receipt.validation.date_required"))
            invalid_fields.append(self._issue_date_entry)

        # VAT sanity check
        vat_val = self._safe_float(self._vat_rate_entry.text())
        if vat_val < 0 or vat_val > 100:
            errors.append(t("receipt.validation.vat_invalid"))
            invalid_fields.append(self._vat_rate_entry)

        # Date format validation
        for date_field, label in [
            (self._issue_date_entry.text().strip(), "Issue Date"),
            (self._payment_date_entry.text().strip(), "Payment Date"),
        ]:
            if date_field and not re.match(r"^\d{4}-\d{2}-\d{2}$", date_field):
                errors.append(t("receipt.validation.date_format").format(field=label))
                if date_field == self._issue_date_entry.text().strip():
                    invalid_fields.append(self._issue_date_entry)
                else:
                    invalid_fields.append(self._payment_date_entry)

        # Apply highlights via shared utility
        for w in invalid_fields:
            mark_field_invalid(w)

        return errors

    # ══════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════

    def _on_generate(self) -> None:
        """Validate, collect data, generate PDF, persist."""
        self._sync_state()
        self._recalculate()
        errors = self._validate()
        if errors:
            QMessageBox.warning(
                self,
                t("receipt.editor.validation_error"),
                "\n".join(errors),
            )
            return

        data = self._collect_receipt_data()
        try:
            svc = self._get_receipt_service()
            path = svc.generate_and_record(data)
            QMessageBox.information(
                self,
                t("receipt.editor.pdf_generated"),
                t("receipt.editor.pdf_generated_msg").format(path=path),
            )
            # Open the PDF
            if os.path.isfile(path):
                os.startfile(os.path.abspath(path))
        except Exception as exc:
            logger.exception("Receipt generation failed")
            QMessageBox.critical(
                self,
                t("receipt.editor.error"),
                str(exc),
            )

    def _on_print(self) -> None:
        """Print the generated receipt."""
        self._sync_state()
        if not self._receipt_number:
            QMessageBox.warning(self, t("receipt.editor.error"),
                                t("receipt.editor.print_no_number"))
            return
        pdf_path = os.path.join("data", "documents", "receipts", f"{self._receipt_number}.pdf")
        if os.path.isfile(pdf_path):
            os.startfile(os.path.abspath(pdf_path))
        else:
            QMessageBox.warning(self, t("receipt.editor.error"),
                                t("receipt.editor.print_no_file"))

    def _on_duplicate(self) -> None:
        """Duplicate current receipt with new number and restore all fields."""
        data = self._collect_receipt_data()
        data.pop("receipt_number", None)
        data["_record_id"] = None
        svc = self._get_receipt_service()
        if svc and svc._receipt_repo:
            new_num = svc._receipt_repo.get_next_number()
            data["receipt_number"] = new_num
            self._receipt_number_entry.setText(new_num)
            self._restore_from_draft(data)
        QMessageBox.information(
            self,
            t("receipt.editor.duplicated"),
            t("receipt.editor.duplicated_msg"),
        )

    def _on_export_json(self) -> None:
        """Export current receipt data as JSON."""
        data = self._collect_receipt_data()
        default_name = f"receipt_{self._receipt_number or 'draft'}.json"
        export_editor_data(
            self,
            data,
            t("receipt.editor.export_json"),
            default_name,
        )

    def _on_email(self) -> None:
        """Placeholder for email action."""
        QMessageBox.information(
            self,
            t("receipt.editor.email"),
            t("receipt.editor.email_placeholder"),
        )

    def _on_attach_files(self) -> None:
        """Open file dialog and attach files with type categorization."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            t("receipt.editor.attach_files"),
            "",
            "All Files (*.*)",
        )
        if not paths:
            return
        # Get selected attachment type
        type_display = self._attach_type_combo.currentText()
        attach_type = self._attach_type_display_map.get(type_display, "other")
        for p in paths:
            if os.path.isfile(p):
                self._attachments.append({
                    "path": p,
                    "name": os.path.basename(p),
                    "size": os.path.getsize(p),
                    "type": attach_type,
                })
        self._update_attachment_list()
        self._on_field_changed()

    def _update_attachment_list(self) -> None:
        """Rebuild the styled attachment list with type badges and remove buttons."""
        from ui.widgets import clear_layout
        clear_layout(self._attachment_list_layout)

        if not self._attachments:
            lbl = QLabel(t("receipt.editor.no_attachments"), self._attachment_list_widget)
            lbl.setProperty("fontRole", "small")
            lbl.setAlignment(Qt.AlignCenter)
            self._attachment_list_layout.addWidget(lbl)
            return

        type_labels = dict(ATTACHMENT_TYPES)
        for idx, a in enumerate(self._attachments):
            row = QFrame(self._attachment_list_widget)
            row.setProperty("role", "card")
            row.setFixedHeight(32)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(S["2"], 0, S["2"], 0)
            row_layout.setSpacing(S["2"])

            # Type badge
            atype = a.get("type", "other")
            type_display = t(type_labels.get(atype, "receipt.attach_type_other"))
            badge = QLabel(f"[{type_display}]", row)
            badge.setProperty("role", "tag-chip")
            row_layout.addWidget(badge)

            # Filename + size
            size_kb = a["size"] / 1024
            info = QLabel(f"{a['name']}  ({size_kb:.1f} KB)", row)
            info.setProperty("fontRole", "small")
            row_layout.addWidget(info, 1)

            # Remove button
            rm_btn = Btn(row, "✕", command=lambda i=idx: self._remove_attachment(i), variant="ghost")
            rm_btn.setFixedWidth(20)
            rm_btn.setFixedHeight(20)
            row_layout.addWidget(rm_btn)

            self._attachment_list_layout.addWidget(row)

    def _remove_attachment(self, idx: int) -> None:
        """Remove an attachment by index."""
        if 0 <= idx < len(self._attachments):
            del self._attachments[idx]
            self._update_attachment_list()
            self._on_field_changed()

    # ══════════════════════════════════════════════════════════════════
    # DATA COLLECTION
    # ══════════════════════════════════════════════════════════════════

    def _collect_receipt_data(self) -> dict:
        """Collect all form data into a dict for PDF generation / DB."""
        conf = load_company_config()
        return {
            "receipt_number": self._receipt_number,
            "receipt_type": self._receipt_type,
            "issue_date": self._issue_date,
            "payment_date": self._payment_date,
            "currency": self._currency,
            "language": self._language,
            "branch": self._branch,
            "_format_key": self._format_key,
            # Company info (for DB)
            "company_name": conf.get("company_name", ""),
            "company_address": conf.get("address", ""),
            "company_vat": conf.get("cui", ""),
            "company_reg": conf.get("reg_number", ""),
            "company_phone": conf.get("phone", ""),
            "company_email": conf.get("email", ""),
            # Received From
            "received_from_name": self._received_from_name,
            "received_from_address": self._received_from_address,
            "received_from_vat": self._received_from_vat,
            "received_from_reg": self._received_from_reg,
            "received_from_contact": self._received_from_contact,
            # Received By
            "received_by_name": self._received_by_name or conf.get("company_name", ""),
            "received_by_address": self._received_by_address or conf.get("address", ""),
            "received_by_vat": self._received_by_vat or conf.get("cui", ""),
            "received_by_reg": self._received_by_reg or conf.get("reg_number", ""),
            "received_by_contact": self._received_by_contact or conf.get("phone", ""),
            # Payment
            "payment_method": self._payment_method,
            "reference_number": self._reference_number,
            "transaction_id": self._transaction_id,
            "bank_reference": self._bank_reference,
            "invoice_reference": self._invoice_reference,
            # Logistics
            "related_trip": self._related_trip,
            "customer": self._customer,
            "vehicle": self._vehicle,
            "trailer": self._trailer,
            "pickup_location": self._pickup_location,
            "delivery_location": self._delivery_location,
            "route": self._route,
            "dispatcher": self._dispatcher,
            # Purpose
            "purpose": self._purpose,
            # Financial
            "amount": self._amount,
            "vat_rate": self._vat_rate,
            "vat_amount": self._vat_amount,
            "total": self._total,
            "amount_words": self._amount_words,
            # Employee
            "employee_name": self._employee_name,
            "department": self._department,
            "expense_category": self._expense_category,
            "mileage": self._mileage,
            "fuel": self._fuel,
            "accommodation": self._accommodation,
            "meals": self._meals,
            "parking": self._parking,
            "tolls": self._tolls,
            "other_expense": self._other_expense,
            # Branding
            "logo_path": self._logo_path,
            "signature_path": self._signature_path,
            "stamp_path": self._stamp_path,
            # Attachments
            "attachments": self._attachments,
            # Notes
            "notes": self._notes,
        }

    # ══════════════════════════════════════════════════════════════════
    # DRAFT SYSTEM
    # ══════════════════════════════════════════════════════════════════

    def _save_draft(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            t("receipt.editor.draft_name"),
            t("receipt.editor.draft_name"),
        )
        if not ok or not name:
            return
        data = self._collect_receipt_data()
        svc = self._get_receipt_service()
        if svc.save_draft(data, name):
            QMessageBox.information(
                self,
                t("receipt.editor.draft_saved"),
                t("receipt.editor.draft_saved_msg").format(name=name),
            )
        else:
            QMessageBox.warning(
                self, t("receipt.editor.error"),
                t("receipt.editor.draft_save_failed"),
            )

    def _load_draft(self) -> None:
        svc = self._get_receipt_service()
        drafts = svc.list_drafts()
        if not drafts:
            QMessageBox.information(
                self, t("receipt.editor.no_drafts"),
                t("receipt.editor.no_drafts"),
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(t("receipt.editor.load_draft"))
        dlg.setMinimumSize(300, 400)
        dlg_layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        for name in drafts:
            list_widget.addItem(name)
        dlg_layout.addWidget(list_widget)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        load_btn = Btn(btn_row, t("receipt.editor.load"), variant="primary")
        cancel_btn = Btn(btn_row, t("receipt.editor.cancel"), variant="ghost")

        def do_load() -> None:
            selected = list_widget.currentItem()
            if selected:
                draft = svc.load_draft(selected.text())
                if draft:
                    self._restore_from_draft(draft)
            dlg.accept()

        load_btn.clicked.connect(do_load)
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        dlg_layout.addWidget(btn_row)

        dlg.exec_()

    def _restore_from_draft(self, draft: dict[str, Any]) -> None:
        """Restore all form fields from a loaded draft."""
        if not isinstance(draft, dict):
            return

        # Receipt type
        rtype = draft.get("receipt_type", "customer_payment")
        display_type = t(self._type_display_map.get(rtype, "receipt.type_other"))
        idx = self._type_combo.findText(display_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)

        # Info
        self._receipt_number_entry.setText(draft.get("receipt_number", ""))
        self._issue_date_entry.setText(draft.get("issue_date", ""))
        self._payment_date_entry.setText(draft.get("payment_date", ""))
        self._currency_combo.setCurrentText(draft.get("currency", "EUR"))
        self._branch_entry.setText(draft.get("branch", ""))
        lang_display = "Română" if draft.get("language") == "ro" else "English"
        lang_idx = self._language_combo.findText(lang_display)
        if lang_idx >= 0:
            self._language_combo.setCurrentIndex(lang_idx)

        # Parties
        self._rf_name.setText(draft.get("received_from_name", ""))
        self._rf_address.setText(draft.get("received_from_address", ""))
        self._rf_vat.setText(draft.get("received_from_vat", ""))
        self._rf_reg.setText(draft.get("received_from_reg", ""))
        self._rf_contact.setText(draft.get("received_from_contact", ""))

        self._rb_name.setText(draft.get("received_by_name", ""))
        self._rb_address.setText(draft.get("received_by_address", ""))
        self._rb_vat.setText(draft.get("received_by_vat", ""))
        self._rb_reg.setText(draft.get("received_by_reg", ""))
        self._rb_contact.setText(draft.get("received_by_contact", ""))

        # Payment
        self._payment_method_combo.setCurrentText(draft.get("payment_method", ""))
        self._reference_number_entry.setText(draft.get("reference_number", ""))
        self._transaction_id_entry.setText(draft.get("transaction_id", ""))
        self._bank_reference_entry.setText(draft.get("bank_reference", ""))
        self._invoice_reference_entry.setText(draft.get("invoice_reference", ""))

        # Logistics
        trip_text = draft.get("related_trip", "")
        if hasattr(self, "_related_trip_combo"):
            idx = self._related_trip_combo.findText(trip_text)
            self._related_trip_combo.setCurrentIndex(idx if idx >= 0 else 0)
        cust_text = draft.get("customer", "")
        if hasattr(self, "_customer_combo"):
            idx = self._customer_combo.findText(cust_text)
            self._customer_combo.setCurrentIndex(idx if idx >= 0 else 0)
        veh_text = draft.get("vehicle", "")
        if hasattr(self, "_vehicle_combo"):
            idx = self._vehicle_combo.findText(veh_text)
            self._vehicle_combo.setCurrentIndex(idx if idx >= 0 else 0)
        trl_text = draft.get("trailer", "")
        if hasattr(self, "_trailer_combo"):
            idx = self._trailer_combo.findText(trl_text)
            self._trailer_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._pickup_location_entry.setText(draft.get("pickup_location", ""))
        self._delivery_location_entry.setText(draft.get("delivery_location", ""))
        self._route_entry.setText(draft.get("route", ""))
        self._dispatcher_entry.setText(draft.get("dispatcher", ""))

        # Purpose
        self._purpose_edit.setPlainText(draft.get("purpose", ""))

        # Financial
        self._amount_entry.setText(str(draft.get("amount", 0)))
        self._vat_rate_entry.setText(str(draft.get("vat_rate", 0)))
        self._recalculate()

        # Employee
        self._employee_name_entry.setText(draft.get("employee_name", ""))
        self._department_entry.setText(draft.get("department", ""))
        self._expense_category_entry.setText(draft.get("expense_category", ""))
        self._mileage_entry.setText(str(draft.get("mileage", 0)))
        self._fuel_entry.setText(str(draft.get("fuel", 0)))
        self._accommodation_entry.setText(str(draft.get("accommodation", 0)))
        self._meals_entry.setText(str(draft.get("meals", 0)))
        self._parking_entry.setText(str(draft.get("parking", 0)))
        self._tolls_entry.setText(str(draft.get("tolls", 0)))
        self._other_expense_entry.setText(str(draft.get("other_expense", 0)))

        # Branding
        self._logo_entry.setText(draft.get("logo_path", ""))
        self._signature_entry.setText(draft.get("signature_path", ""))
        self._stamp_entry.setText(draft.get("stamp_path", ""))

        # Attachments
        self._attachments = draft.get("attachments", [])
        self._update_attachment_list()

        # Notes
        self._notes_edit.setPlainText(draft.get("notes", ""))

        # Refresh
        self._on_field_changed()

    # ══════════════════════════════════════════════════════════════════
    # I18N
    # ══════════════════════════════════════════════════════════════════

    def _retranslate_ui(self) -> None:
        """Update all translatable labels and headers."""
        self._page_title.setText(t("receipt.editor.title"))
        self._page_subtitle.setText(t("receipt.editor.subtitle", ""))

        # Section headers
        self._type_header.setText(t("receipt.section_type").upper())
        if hasattr(self, "_invoice_header"):
            self._invoice_header.setText(t("receipt.section_invoice_autofill").upper())
        self._info_header.setText(t("receipt.section_info").upper())
        self._parties_header.setText(t("receipt.section_parties").upper())
        self._payment_header.setText(t("receipt.section_payment").upper())
        self._logistics_header.setText(t("receipt.section_logistics").upper())
        self._purpose_header.setText(t("receipt.section_purpose").upper())
        self._financial_header.setText(t("receipt.section_financial").upper())
        self._employee_header.setText(t("receipt.section_employee").upper())
        self._attachments_header.setText(t("receipt.section_attachments").upper())
        self._notes_header.setText(t("receipt.section_notes").upper())
        self._branding_header.setText(t("receipt.section_branding").upper())

        # Party titles
        self._from_title.setText(t("receipt.received_from"))
        self._by_title.setText(t("receipt.received_by"))

        # Receipt type combo
        current_type = self._type_reverse_map.get(self._type_combo.currentText(), "other")
        self._type_combo.blockSignals(True)
        self._type_combo.clear()
        new_type_values = [t(key) for _, key in RECEIPT_TYPES]
        self._type_combo.addItems(new_type_values)
        self._type_reverse_map = {t(key): key for _, key in RECEIPT_TYPES}
        # Restore selection
        restore_text = t(self._type_display_map.get(current_type, "receipt.type_other"))
        idx = self._type_combo.findText(restore_text)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
        self._type_combo.blockSignals(False)

        # Toolbar
        self._generate_btn.setText(f"\U0001F4C4  {t('receipt.editor.generate_pdf')}")
        self._print_btn.setText(f"\U0001F5A8  {t('receipt.editor.print')}")
        self._save_draft_btn.setText(f"\U0001F4BE  {t('receipt.editor.save_draft')}")
        self._load_draft_btn.setText(f"\U0001F4C2  {t('receipt.editor.load_draft')}")
        self._duplicate_btn.setText(f"\U0001F4CB  {t('receipt.editor.duplicate')}")
        self._export_json_btn.setText(f"\U0001F4C4  {t('receipt.editor.export_json')}")
        self._email_btn.setText(f"\U0001F4E7  {t('receipt.editor.email')}")

        # Attachment button
        self._attach_btn.setText(f"  {t('receipt.editor.attach_files')}")

        # Browse buttons
        self._browse_logo_btn.setText(t("receipt.editor.browse"))
        self._browse_sig_btn.setText(t("receipt.editor.browse"))
        self._browse_stamp_btn.setText(t("receipt.editor.browse"))

        # Refresh preview
        self._refresh_preview()
