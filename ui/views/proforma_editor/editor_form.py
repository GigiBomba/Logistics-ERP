"""PySide6 proforma invoice editor.

Provides a form-based proforma editor with client selection, line items,
auto-calculated totals, branding controls, PDF generation, document linking,
and draft save/load.

Usage as embedded widget::

    editor = QtProformaEditor(parent_widget, db, prefs=prefs)
    editor.wakeup()
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from repositories.client_repository import ClientRepository
from repositories.document_repository import DocumentRepository
from repositories.proforma_repository import PROFORMA_NUMBER_FORMATS, DEFAULT_PROFORMA_FORMAT_KEY as PROF_DEFAULT_FMT
from services.i18n import t
from ui.base_view import BaseView
from utils.editor_toolkit import DebouncedTask, export_editor_data, mark_field_invalid, register_shortcuts
from services.invoicing.config_manager import load_company_config
from services.invoicing.proforma_service import ProformaService
from services.operations.event_bus import SETTINGS_UPDATED, EventBus
from services.preferences import PreferencesManager
from ui.components import Btn, Card, Label, PageTitle, SectionTitle
from ui.theme import COLORS, S
from ui.views.proforma_editor.line_items import LineItemsMixin
from ui.widgets import (
    ScrollableFormContainer,
    StyledCheckBox,
    StyledComboBox,
    StyledLineEdit,
    StyledTextEdit,
)

_logger = logging.getLogger(__name__)


class QtProformaEditor(BaseView, LineItemsMixin):
    """Professional proforma invoice editor.

    This is a QWidget for embedding in tab views. It uses ``ScrollableFormContainer``
    for the main form area and provides section cards for client info, proforma details,
    line items, and totals.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: PreferencesManager | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs or (PreferencesManager(db) if db else None)
        self._client_repo = ClientRepository(db) if db else None
        self._doc_repo = DocumentRepository(db) if db else None
        self._proforma_service: ProformaService | None = None


        # ── Data state ────────────────────────────────────────────────────────
        self._clients: list[dict[str, Any]] = []
        self._client_map: dict[str, dict[str, Any]] = {}

        # Proforma data
        self._proforma_number: str = ""
        self._issue_date: str = datetime.now().strftime("%Y-%m-%d")
        self._valid_until: str = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self._payment_terms: str = "Net 30"
        self._notes: str = ""
        self._tax_rate: str = "19"
        self._discount_type: str = ""
        self._discount_value: str = "0"
        self._currency: str = self.prefs.get_currency() if self.prefs else "EUR"

        # Line items
        self._addon_items: list[dict[str, Any]] = []

        # Mode
        self._is_client_mode: bool = True
        self._is_internal_mode: bool = False

        # Description
        self._description: str = ""

        # Branding
        self._logo_path: str = ""
        self._signature_path: str = ""
        self._stamp_path: str = ""
        self._company_color: str = COLORS["accent"]

        # Client info
        self._client_name: str = ""
        self._client_vat: str = ""
        self._client_vat_raw: str = ""
        self._client_address: str = ""
        self._client_phone: str = ""
        self._client_phone_raw: str = ""
        self._client_email: str = ""
        self._client_email_raw: str = ""
        self._selected_client_id: int | None = None

        # Company info
        self._company_name: str = ""
        self._company_cui: str = ""
        self._company_cui_raw: str = ""
        self._company_reg: str = ""
        self._company_reg_raw: str = ""
        self._company_address: str = ""
        self._company_phone: str = ""
        self._company_phone_raw: str = ""
        self._company_email: str = ""
        self._company_email_raw: str = ""

        # Linked documents
        self._linked_docs: list[dict[str, Any]] = []

        # i18n
        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        self._data_loaded: bool = False

        # Branch / Office
        self._branch: str = ""
        self._format_key: str = PROF_DEFAULT_FMT

        # ── Build UI ─────────────────────────────────────────────────────────
        self._build_ui()
        self._load_company_config()
        self._add_default_item()

        self._subscribe(SETTINGS_UPDATED, self._on_settings_updated)

        # Debounced recalculation
        self._recalc_task = DebouncedTask(self._recalc_all, interval_ms=300)

        # Keyboard shortcuts
        self._shortcuts = register_shortcuts(self, {
            "generate": self._generate_pdf,
            "save_draft": self._save_draft,
            "load_draft": self._load_draft,
            "export_json": self._on_export_json,
            "print": self._print_pdf,
        })

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Load DB-dependent data. Called when the tab becomes visible."""
        if not self._data_loaded:
            self._load_clients()
            self._data_loaded = True
        self._recalc_all()

    def shutdown(self) -> None:
        """Clean up resources."""
        super().shutdown()

    def _on_language_changed(self, _lang: str) -> None:
        """Refresh UI text when language changes."""
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        """Update all translatable labels and headers."""
        self._page_title.setText(t("proforma_editor.title"))
        self._page_subtitle.setText(t("proforma_editor.subtitle", ""))

        # Top bar
        self._client_label.setText(t("proforma_editor.select_client"))
        self._cb_client.setText(t("proforma_editor.mode_client"))
        self._cb_internal.setText(t("proforma_editor.mode_internal"))

        # Details section
        self._details_header.setText(t("proforma_editor.proforma_details").upper())
        self._proforma_number_label.setText(t("proforma_editor.proforma_number"))
        self._issue_date_label.setText(t("proforma_editor.issue_date"))
        self._valid_until_label.setText(t("proforma_editor.valid_until"))
        self._payment_terms_label.setText(t("proforma_editor.payment_terms"))

        # Line items
        self._lit_header_label.setText(t("proforma_editor.line_items").upper())
        self._add_row_btn.setText("+ " + t("proforma_editor.add_row"))
        self._desc_label.setText(t("proforma_editor.description"))

        # Financial panel
        self._financial_header.setText(t("proforma_editor.financial_controls").upper())
        self._tax_label.setText(t("proforma_editor.tax_rate"))
        self._discount_label.setText(t("proforma_editor.discount"))
        self._currency_label.setText(t("proforma_editor.currency"))
        self._subtotal_title.setText(t("proforma_editor.subtotal"))
        self._tax_title.setText(t("proforma_editor.tax"))
        self._discount_title.setText(t("proforma_editor.discount"))
        self._grand_title.setText(t("proforma_editor.grand_total"))

        # Branding panel
        self._branding_header.setText(t("proforma_editor.branding").upper())
        self._logo_label.setText(t("proforma_editor.logo"))
        self._color_label.setText(t("proforma_editor.company_color"))
        self._color_btn.setText(t("proforma_editor.pick_color"))
        self._sig_label.setText(t("proforma_editor.signature"))
        self._stamp_label.setText(t("proforma_editor.stamp"))
        self._browse_logo_btn.setText(t("proforma_editor.browse"))
        self._browse_sig_btn.setText(t("proforma_editor.browse"))
        self._browse_stamp_btn.setText(t("proforma_editor.browse"))

        # Canvas / preview section headers
        self._from_header.setText(t("proforma_editor.from").upper())
        self._bill_to_header.setText(t("proforma_editor.bill_to").upper())

        # Notes
        self._notes_label.setText(t("proforma_editor.notes"))

        # Linked documents
        self._linked_docs_header.setText(t("proforma_editor.linked_documents").upper())

        # Bottom bar
        self._preview_btn.setText("\U0001F50D " + t("proforma_editor.preview_pdf"))
        self._generate_btn.setText("\U0001F4C4 " + t("proforma_editor.generate_pdf"))
        self._print_btn.setText("\U0001F5A8 " + t("proforma_editor.print"))
        self._email_btn.setText("\U0001F4E7 " + t("proforma_editor.email"))
        self._save_draft_btn.setText("\U0001F4BE " + t("proforma_editor.save_draft"))
        self._load_draft_btn.setText("\U0001F4C2 " + t("proforma_editor.load_draft"))

        # Canvas totals
        self._canvas_subtotal_label.setText(t("proforma_editor.subtotal"))
        self._canvas_tax_label.setText(t("proforma_editor.tax"))
        self._canvas_discount_label.setText(t("proforma_editor.discount"))
        self._canvas_grand_label.setText(t("proforma_editor.grand_total"))

        # Discount combo
        idx = self._disc_type_combo.currentIndex()
        self._disc_type_combo.clear()
        self._disc_type_combo.addItems([
            t("proforma_editor.discount_percentage"),
            t("proforma_editor.discount_fixed"),
        ])
        if idx >= 0:
            self._disc_type_combo.setCurrentIndex(idx)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_proforma_service(self) -> ProformaService:
        if self._proforma_service is None:
            self._proforma_service = ProformaService(self.db, prefs=self.prefs)
        return self._proforma_service

    def _on_settings_updated(self, ev: Any) -> None:
        data = ev.get("data", {}) if isinstance(ev, dict) else {}
        if data.get("key") == "company_config":
            QTimer.singleShot(0, self._load_company_config)

    # ══════════════════════════════════════════════════════════════════════════
    # UI BUILDING
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """Build the complete UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        self._build_top_bar()
        main_layout.addWidget(self._top_bar)

        # Scrollable form container
        self._scroll = ScrollableFormContainer(self, max_width=1400)
        main_layout.addWidget(self._scroll, 1)

        # View header
        self._build_view_header()

        # Sections
        self._build_client_section()
        self._build_details_section()
        self._build_line_items_section()
        self._build_totals_section()
        self._build_branding_section()
        self._build_notes_section()
        self._build_linked_docs_section()

        # Bottom bar
        self._build_bottom_bar()
        main_layout.addWidget(self._bottom_bar)

    # ── Top Bar ──────────────────────────────────────────────────────────────

    def _build_top_bar(self) -> None:
        self._top_bar = QFrame(self)
        self._top_bar.setProperty("role", "top-bar")
        self._top_bar.setFixedHeight(56)

        layout = QHBoxLayout(self._top_bar)
        layout.setContentsMargins(S["4"], S["2"], S["4"], S["2"])
        layout.setSpacing(S["3"])

        # Client selector
        self._client_label = Label(self._top_bar, t("proforma_editor.select_client"), role="field-label")
        layout.addWidget(self._client_label)

        self._client_combo = StyledComboBox()
        self._client_combo.currentTextChanged.connect(self._on_client_selected)
        self._client_combo.setMinimumWidth(200)
        layout.addWidget(self._client_combo)

        # Mode checkboxes
        self._cb_client = StyledCheckBox(text=t("proforma_editor.mode_client"))
        self._cb_client.setChecked(True)
        self._cb_client.toggled.connect(lambda checked: self._on_mode_changed("client", checked))
        layout.addWidget(self._cb_client)

        self._cb_internal = StyledCheckBox(text=t("proforma_editor.mode_internal"))
        self._cb_internal.toggled.connect(lambda checked: self._on_mode_changed("internal", checked))
        layout.addWidget(self._cb_internal)

        layout.addStretch()

    # ── View Header ──────────────────────────────────────────────────────────

    def _build_view_header(self) -> None:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, S["3"])
        layout.setSpacing(S["1"])

        self._page_title = PageTitle(header, t("proforma_editor.title"))
        layout.addWidget(self._page_title)

        self._page_subtitle = Label(
            header,
            t("proforma_editor.subtitle", "Create and manage proforma invoices"),
            role="secondary",
        )
        layout.addWidget(self._page_subtitle)

        self._scroll.add_widget(header)

    # ── Client Section (From / Bill To) ──────────────────────────────────────

    def _build_client_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionTitle(container, t("proforma_editor.client_info"))
        layout.addWidget(header)

        cols = QWidget()
        cols_layout = QHBoxLayout(cols)
        cols_layout.setContentsMargins(0, 0, 0, 0)
        cols_layout.setSpacing(S["4"])

        # From (Company)
        from_card = self._make_card()
        from_layout = from_card.layout()
        from_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        from_layout.setSpacing(S["2"])

        self._from_header = QLabel(t("proforma_editor.from").upper())
        self._from_header.setProperty("fontRole", "section")
        from_layout.addWidget(self._from_header)

        self._c_company_name = self._make_canvas_label(from_card, "", bold=True)
        from_layout.addWidget(self._c_company_name)
        self._c_company_cui = self._make_canvas_label(from_card, "")
        from_layout.addWidget(self._c_company_cui)
        self._c_company_reg = self._make_canvas_label(from_card, "")
        from_layout.addWidget(self._c_company_reg)
        self._c_company_addr = self._make_canvas_label(from_card, "")
        from_layout.addWidget(self._c_company_addr)
        self._c_company_phone = self._make_canvas_label(from_card, "")
        from_layout.addWidget(self._c_company_phone)
        self._c_company_email = self._make_canvas_label(from_card, "")
        from_layout.addWidget(self._c_company_email)

        edit_company_btn = Btn(from_card, "\u270F", variant="ghost")
        edit_company_btn.setFixedSize(28, 28)
        edit_company_btn.clicked.connect(self._open_company_editor)
        from_layout.addWidget(edit_company_btn)
        from_layout.addStretch()

        cols_layout.addWidget(from_card)

        # Bill To (Client)
        to_card = self._make_card()
        to_layout = to_card.layout()
        to_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        to_layout.setSpacing(S["2"])

        self._bill_to_header = QLabel(t("proforma_editor.bill_to").upper())
        self._bill_to_header.setProperty("fontRole", "section")
        to_layout.addWidget(self._bill_to_header)

        self._c_client_name = self._make_canvas_label(to_card, "", bold=True)
        to_layout.addWidget(self._c_client_name)
        self._c_client_vat = self._make_canvas_label(to_card, "")
        to_layout.addWidget(self._c_client_vat)
        self._c_client_addr = self._make_canvas_label(to_card, "")
        to_layout.addWidget(self._c_client_addr)
        self._c_client_phone = self._make_canvas_label(to_card, "")
        to_layout.addWidget(self._c_client_phone)
        self._c_client_email = self._make_canvas_label(to_card, "")
        to_layout.addWidget(self._c_client_email)
        to_layout.addStretch()

        cols_layout.addWidget(to_card)
        layout.addWidget(cols)
        self._scroll.add_widget(container)

    def _make_card(self) -> QFrame:
        return Card()

    def _make_canvas_label(self, parent: QWidget, text: str, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        if bold:
            lbl.setProperty("fontRole", "body-bold")
        else:
            lbl.setProperty("fontRole", "body")
        return lbl

    def _update_canvas_labels(self) -> None:
        self._c_company_name.setText(self._company_name)
        self._c_company_cui.setText(self._company_cui)
        self._c_company_reg.setText(self._company_reg)
        self._c_company_addr.setText(self._company_address)
        self._c_company_phone.setText(self._company_phone)
        self._c_company_email.setText(self._company_email)

        self._c_client_name.setText(self._client_name)
        self._c_client_vat.setText(self._client_vat)
        self._c_client_addr.setText(self._client_address)
        self._c_client_phone.setText(self._client_phone)
        self._c_client_email.setText(self._client_email)

    # ── Details Section ─────────────────────────────────────────────────────

    def _build_details_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        self._details_header = SectionTitle(container, t("proforma_editor.proforma_details"))
        layout.addWidget(self._details_header)

        form = QFrame()
        form_layout = QHBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(S["4"])

        # Proforma number (read-only)
        pf_col = QWidget()
        pf_layout = QVBoxLayout(pf_col)
        pf_layout.setContentsMargins(0, 0, 0, 0)
        pf_layout.setSpacing(S["1"])
        self._proforma_number_label = QLabel(t("proforma_editor.proforma_number"))
        self._proforma_number_label.setProperty("fontRole", "label")
        pf_layout.addWidget(self._proforma_number_label)
        self._pf_number_value = QLabel(t("proforma.auto_label", default="(auto)"))
        self._pf_number_value.setProperty("fontRole", "body")
        pf_layout.addWidget(self._pf_number_value)
        form_layout.addWidget(pf_col)

        # Issue date
        date_col = QWidget()
        date_layout = QVBoxLayout(date_col)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(S["1"])
        self._issue_date_label = QLabel(t("proforma_editor.issue_date"))
        self._issue_date_label.setProperty("fontRole", "label")
        date_layout.addWidget(self._issue_date_label)
        self._issue_date_input = StyledLineEdit(self._issue_date)
        self._issue_date_input.textChanged.connect(self._on_issue_date_changed)
        date_layout.addWidget(self._issue_date_input)
        form_layout.addWidget(date_col)

        # Valid until
        vu_col = QWidget()
        vu_layout = QVBoxLayout(vu_col)
        vu_layout.setContentsMargins(0, 0, 0, 0)
        vu_layout.setSpacing(S["1"])
        self._valid_until_label = QLabel(t("proforma_editor.valid_until"))
        self._valid_until_label.setProperty("fontRole", "label")
        vu_layout.addWidget(self._valid_until_label)
        self._valid_until_input = StyledLineEdit(self._valid_until)
        self._valid_until_input.textChanged.connect(self._on_valid_until_changed)
        vu_layout.addWidget(self._valid_until_input)
        form_layout.addWidget(vu_col)

        # Payment terms
        pt_col = QWidget()
        pt_layout = QVBoxLayout(pt_col)
        pt_layout.setContentsMargins(0, 0, 0, 0)
        pt_layout.setSpacing(S["1"])
        self._payment_terms_label = QLabel(t("proforma_editor.payment_terms"))
        self._payment_terms_label.setProperty("fontRole", "label")
        pt_layout.addWidget(self._payment_terms_label)
        self._payment_terms_combo = StyledComboBox()
        self._payment_terms_combo.addItems(["Net 30", "Net 15", "Net 60", "Due on Receipt"])
        self._payment_terms_combo.setCurrentText(self._payment_terms)
        self._payment_terms_combo.currentTextChanged.connect(self._on_payment_terms_changed)
        pt_layout.addWidget(self._payment_terms_combo)
        form_layout.addWidget(pt_col)

        # Branch / Office
        br_col = QWidget()
        br_layout = QVBoxLayout(br_col)
        br_layout.setContentsMargins(0, 0, 0, 0)
        br_layout.setSpacing(S["1"])
        self._branch_label = QLabel(t("proforma_editor.branch", "Branch / Office"))
        self._branch_label.setProperty("fontRole", "label")
        br_layout.addWidget(self._branch_label)
        self._branch_entry = StyledLineEdit(text=self._branch,
                                            placeholder=t("receipt.branch_placeholder"))
        self._branch_entry.textChanged.connect(self._on_branch_changed)
        br_layout.addWidget(self._branch_entry)
        form_layout.addWidget(br_col)

        # Number format
        nf_col = QWidget()
        nf_layout = QVBoxLayout(nf_col)
        nf_layout.setContentsMargins(0, 0, 0, 0)
        nf_layout.setSpacing(S["1"])
        nf_label = QLabel(t("proforma_editor.number_format", "Number Format"))
        nf_label.setProperty("fontRole", "label")
        nf_layout.addWidget(nf_label)
        fmt_display = [f"{key} ({ex})" for key, (_, ex) in PROFORMA_NUMBER_FORMATS.items()]
        self._format_combo = StyledComboBox(nf_col, values=fmt_display)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        nf_layout.addWidget(self._format_combo)
        form_layout.addWidget(nf_col)

        form_layout.addStretch()
        layout.addWidget(form)
        self._scroll.add_widget(container)

    # ── Branding Section ──────────────────────────────────────────────────────

    def _build_branding_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        self._branding_header = SectionTitle(container, t("proforma_editor.branding"))
        layout.addWidget(self._branding_header)

        branding_card = self._make_card()
        b_layout = branding_card.layout()
        b_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        b_layout.setSpacing(S["2"])

        # Logo
        logo_row = QWidget()
        logo_layout = QHBoxLayout(logo_row)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        self._logo_label = QLabel(t("proforma_editor.logo"))
        self._logo_label.setProperty("fontRole", "label")
        logo_layout.addWidget(self._logo_label)
        self._logo_entry = StyledLineEdit(self._logo_path)
        self._logo_entry.setReadOnly(True)
        logo_layout.addWidget(self._logo_entry, 1)
        self._browse_logo_btn = Btn(logo_row, t("proforma_editor.browse"), variant="ghost")
        self._browse_logo_btn.clicked.connect(lambda: self._browse_file("logo"))
        logo_layout.addWidget(self._browse_logo_btn)
        b_layout.addWidget(logo_row)

        # Color
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        self._color_label = QLabel(t("proforma_editor.company_color"))
        self._color_label.setProperty("fontRole", "label")
        color_layout.addWidget(self._color_label)
        self._color_swatch = QFrame(color_row)
        self._color_swatch.setFixedSize(24, 24)
        self._color_swatch.setStyleSheet(f"background-color: {self._company_color}; border-radius: 4px;")
        color_layout.addWidget(self._color_swatch)
        self._color_btn = Btn(color_row, t("proforma_editor.pick_color"), variant="ghost")
        self._color_btn.clicked.connect(self._pick_color)
        color_layout.addWidget(self._color_btn)
        color_layout.addStretch()
        b_layout.addWidget(color_row)

        # Signature
        sig_row = QWidget()
        sig_layout = QHBoxLayout(sig_row)
        sig_layout.setContentsMargins(0, 0, 0, 0)
        self._sig_label = QLabel(t("proforma_editor.signature"))
        self._sig_label.setProperty("fontRole", "label")
        sig_layout.addWidget(self._sig_label)
        self._sig_entry = StyledLineEdit(self._signature_path)
        self._sig_entry.setReadOnly(True)
        sig_layout.addWidget(self._sig_entry, 1)
        self._browse_sig_btn = Btn(sig_row, t("proforma_editor.browse"), variant="ghost")
        self._browse_sig_btn.clicked.connect(lambda: self._browse_file("signature"))
        sig_layout.addWidget(self._browse_sig_btn)
        b_layout.addWidget(sig_row)

        # Stamp
        stamp_row = QWidget()
        stamp_layout = QHBoxLayout(stamp_row)
        stamp_layout.setContentsMargins(0, 0, 0, 0)
        self._stamp_label = QLabel(t("proforma_editor.stamp"))
        self._stamp_label.setProperty("fontRole", "label")
        stamp_layout.addWidget(self._stamp_label)
        self._stamp_entry = StyledLineEdit(self._stamp_path)
        self._stamp_entry.setReadOnly(True)
        stamp_layout.addWidget(self._stamp_entry, 1)
        self._browse_stamp_btn = Btn(stamp_row, t("proforma_editor.browse"), variant="ghost")
        self._browse_stamp_btn.clicked.connect(lambda: self._browse_file("stamp"))
        stamp_layout.addWidget(self._browse_stamp_btn)
        b_layout.addWidget(stamp_row)

        layout.addWidget(branding_card)
        self._scroll.add_widget(container)

    # ── Notes Section ─────────────────────────────────────────────────────────

    def _build_notes_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["2"])

        self._notes_label = QLabel(t("proforma_editor.notes"))
        self._notes_label.setProperty("fontRole", "label")
        layout.addWidget(self._notes_label)

        self._notes_edit = StyledTextEdit()
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        self._notes_edit.setMaximumHeight(120)
        layout.addWidget(self._notes_edit)

        self._scroll.add_widget(container)

    # ── Linked Documents Section ──────────────────────────────────────────────

    def _build_linked_docs_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["2"])

        self._linked_docs_header = SectionTitle(container, t("proforma_editor.linked_documents"))
        layout.addWidget(self._linked_docs_header)

        # Linked documents list
        self._linked_docs_list = QListWidget()
        self._linked_docs_list.setMinimumHeight(80)
        self._linked_docs_list.setMaximumHeight(150)
        layout.addWidget(self._linked_docs_list)

        # Buttons
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(S["2"])

        self._link_doc_btn = Btn(btn_row, t("proforma_editor.link_document"), variant="ghost")
        self._link_doc_btn.clicked.connect(self._link_document)
        btn_layout.addWidget(self._link_doc_btn)

        self._unlink_doc_btn = Btn(btn_row, t("proforma_editor.unlink_document"), variant="ghost")
        self._unlink_doc_btn.clicked.connect(self._unlink_document)
        self._unlink_doc_btn.setEnabled(False)
        btn_layout.addWidget(self._unlink_doc_btn)

        self._autofill_from_doc_btn = Btn(btn_row, t("proforma_editor.autofill_from_doc"), variant="ghost")
        self._autofill_from_doc_btn.clicked.connect(self._autofill_from_linked_document)
        self._autofill_from_doc_btn.setEnabled(False)
        btn_layout.addWidget(self._autofill_from_doc_btn)

        btn_layout.addStretch()
        layout.addWidget(btn_row)

        self._linked_docs_list.currentRowChanged.connect(self._on_linked_doc_selected)

        self._scroll.add_widget(container)

    # ── Bottom Bar ────────────────────────────────────────────────────────────

    def _build_bottom_bar(self) -> None:
        self._bottom_bar = QFrame(self)
        self._bottom_bar.setProperty("role", "bottom-bar")
        self._bottom_bar.setFixedHeight(56)

        layout = QHBoxLayout(self._bottom_bar)
        layout.setContentsMargins(S["4"], S["2"], S["4"], S["2"])
        layout.setSpacing(S["3"])

        self._preview_btn = Btn(self._bottom_bar, "\U0001F50D " + t("proforma_editor.preview_pdf"),
                                variant="ghost")
        self._preview_btn.clicked.connect(self._preview_pdf)
        layout.addWidget(self._preview_btn)

        self._generate_btn = Btn(self._bottom_bar, "\U0001F4C4 " + t("proforma_editor.generate_pdf"),
                                 variant="primary")
        self._generate_btn.clicked.connect(self._generate_pdf)
        layout.addWidget(self._generate_btn)

        self._print_btn = Btn(self._bottom_bar, "\U0001F5A8 " + t("proforma_editor.print"),
                              variant="ghost")
        self._print_btn.clicked.connect(self._print_pdf)
        layout.addWidget(self._print_btn)

        self._email_btn = Btn(self._bottom_bar, "\U0001F4E7 " + t("proforma_editor.email"),
                              variant="ghost")
        self._email_btn.clicked.connect(self._email_pdf)
        layout.addWidget(self._email_btn)

        self._save_draft_btn = Btn(self._bottom_bar, "\U0001F4BE " + t("proforma_editor.save_draft"),
                                   variant="ghost")
        self._save_draft_btn.clicked.connect(self._save_draft)
        layout.addWidget(self._save_draft_btn)

        self._load_draft_btn = Btn(self._bottom_bar, "\U0001F4C2 " + t("proforma_editor.load_draft"),
                                   variant="ghost")
        self._load_draft_btn.clicked.connect(self._load_draft)
        layout.addWidget(self._load_draft_btn)

        self._export_json_btn = Btn(self._bottom_bar, "\U0001F4C4 " + t("proforma_editor.export_json"),
                                    variant="ghost")
        self._export_json_btn.clicked.connect(self._on_export_json)
        layout.addWidget(self._export_json_btn)

        layout.addStretch()

    # ══════════════════════════════════════════════════════════════════════════
    # EXPORT / VALIDATION HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _all_inputs(self) -> list[QWidget]:
        """Return all form input widgets for validation highlighting."""
        result: list[QWidget] = []
        for attr in [
            "_client_combo", "_issue_date_input", "_valid_until_input",
            "_payment_terms_combo", "_desc_text_edit",
            "_tax_combo", "_disc_type_combo", "_disc_entry", "_curr_combo",
            "_notes_edit",
        ]:
            w = getattr(self, attr, None)
            if w is not None:
                result.append(w)
        return result

    def _on_export_json(self) -> None:
        """Export proforma data as JSON."""
        data = self._collect_proforma_data()
        default_name = f"proforma_{data.get('proforma_number', 'draft')}.json"
        export_editor_data(
            self,
            data,
            t("proforma_editor.export_json"),
            default_name,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # DATA LOADING
    # ══════════════════════════════════════════════════════════════════════════

    def _load_company_config(self) -> None:
        conf = load_company_config()
        self._company_name = conf.get("company_name", "")
        self._company_cui_raw = conf.get("cui", "")
        self._company_cui = f"CUI: {self._company_cui_raw}" if self._company_cui_raw else ""
        self._company_reg_raw = conf.get("reg_number", "")
        self._company_reg = f"Reg: {self._company_reg_raw}" if self._company_reg_raw else ""
        self._company_address = conf.get("address", "")
        self._company_phone_raw = conf.get("phone", "")
        self._company_phone = f"Tel: {self._company_phone_raw}" if self._company_phone_raw else ""
        self._company_email_raw = conf.get("email", "")
        self._company_email = f"Email: {self._company_email_raw}" if self._company_email_raw else ""
        self._logo_path = conf.get("logo_path", "")
        self._signature_path = conf.get("signature_path", "")
        self._stamp_path = conf.get("stamp_path", "")
        self._company_color = conf.get("company_color", COLORS["accent"])
        self._update_canvas_labels()

    def _load_clients(self) -> None:
        if not self._client_repo:
            return
        try:
            clients = self._client_repo.get_all()
        except Exception:
            clients = []
        self._clients = clients or []
        self._client_map = {}
        current = self._client_combo.currentText()
        self._client_combo.blockSignals(True)
        self._client_combo.clear()
        self._client_combo.addItem("")
        for c in self._clients:
            display = c.get("name", "")
            self._client_combo.addItem(display)
            self._client_map[display] = c
        idx = self._client_combo.findText(current)
        if idx >= 0:
            self._client_combo.setCurrentIndex(idx)
        self._client_combo.blockSignals(False)

    # ── Event Handlers ────────────────────────────────────────────────────────

    def _on_client_selected(self, text: str) -> None:
        client = self._client_map.get(text)
        if client:
            self._selected_client_id = client.get("id")
            self._client_name = client.get("name", "")
            self._client_vat_raw = client.get("vat_number", "")
            self._client_vat = f"VAT: {self._client_vat_raw}" if self._client_vat_raw else ""
            self._client_address = client.get("address", "")
            self._client_phone_raw = client.get("phone", "")
            self._client_phone = f"Tel: {self._client_phone_raw}" if self._client_phone_raw else ""
            self._client_email_raw = client.get("email", "")
            self._client_email = f"Email: {self._client_email_raw}" if self._client_email_raw else ""
            self._update_canvas_labels()

    def _on_mode_changed(self, mode: str, checked: bool) -> None:
        if mode == "client":
            self._is_client_mode = checked
            if checked:
                self._cb_internal.blockSignals(True)
                self._cb_internal.setChecked(False)
                self._cb_internal.blockSignals(False)
        else:
            self._is_internal_mode = checked
            if checked:
                self._cb_client.blockSignals(True)
                self._cb_client.setChecked(False)
                self._cb_client.blockSignals(False)

    def _on_issue_date_changed(self, text: str) -> None:
        self._issue_date = text

    def _on_valid_until_changed(self, text: str) -> None:
        self._valid_until = text

    def _on_payment_terms_changed(self, text: str) -> None:
        self._payment_terms = text

    def _on_branch_changed(self, text: str) -> None:
        self._branch = text.strip()
        self._recalc_all()

    def _on_format_changed(self, text: str) -> None:
        if not text:
            return
        for key in PROFORMA_NUMBER_FORMATS:
            if text.startswith(key):
                self._format_key = key
                break
        svc = self._get_proforma_service()
        svc.set_format_key(self._format_key)
        self._gen_proforma_number()

    def _on_notes_changed(self) -> None:
        self._notes = self._notes_edit.toPlainText()

    # ── Branding Helpers ──────────────────────────────────────────────────────

    def _browse_file(self, field_type: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("proforma_editor.select_logo"), "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        if field_type == "logo":
            self._logo_entry.setText(path)
            self._logo_path = path
        elif field_type == "signature":
            self._sig_entry.setText(path)
            self._signature_path = path
        elif field_type == "stamp":
            self._stamp_entry.setText(path)
            self._stamp_path = path

    def _pick_color(self) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self._company_color = color.name()
            self._color_swatch.setStyleSheet(
                f"background-color: {self._company_color}; border-radius: 4px;")

    def _open_company_editor(self) -> None:
        dlg = CompanyEditorQtDialog(self, db=self.db, prefs=self.prefs)
        dlg.exec_()

    # ── Linked Documents ──────────────────────────────────────────────────────

    def _link_document(self) -> None:
        try:
            from services.document_service import DocumentService
            ds = DocumentService(self.db)
            result = ds.advanced_search(page_size=200)
            docs = result.get("docs", []) if isinstance(result, dict) else []
        except Exception:
            docs = []
        if not docs:
            QMessageBox.information(self, t("proforma_editor.no_docs_available"),
                                    t("proforma_editor.no_docs_available"))
            return

        # Create a simple dialog to pick a document
        dlg = QDialog(self)
        dlg.setWindowTitle(t("proforma_editor.select_document"))
        dlg.setMinimumSize(500, 400)
        dlg_layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        for d in docs:
            title = d.get("title", d.get("file_name", "Unknown"))
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, d.get("id"))
            list_widget.addItem(item)
        dlg_layout.addWidget(list_widget)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        select_btn = Btn(btn_row, t("proforma_editor.select"), variant="primary")
        cancel_btn = Btn(btn_row, t("proforma_editor.cancel"), variant="ghost")

        def do_select():
            selected = list_widget.currentItem()
            if selected:
                doc_id = selected.data(Qt.UserRole)
                title = selected.text()
                # Link remotely first, then update local state only on success
                if self._link_doc_to_proforma(doc_id):
                    self._linked_docs.append({"id": doc_id, "title": title})
                    self._refresh_linked_docs_list()
            dlg.accept()

        select_btn.clicked.connect(do_select)
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        dlg_layout.addWidget(btn_row)

        dlg.exec_()

    def _link_doc_to_proforma(self, doc_id: int) -> bool:
        """Link a document to this proforma with a placeholder entity_id.

        The entity_id is updated to the real proforma id after
        :meth:`_generate_pdf` or :meth:`_email_pdf` persists the record.
        """
        try:
            from services.document_service import DocumentService
            ds = DocumentService(self.db)
            result = ds.link_document(doc_id, "proforma", 0, relation_type="attached")
            return bool(result)
        except Exception as exc:
            _logger.warning("Failed to link document %s: %s", doc_id, exc)
            return False

    def _update_linked_entity_ids(self, pf_id: int) -> None:
        """Backfill the real proforma id on document links that were created
        with the placeholder entity_id (0)."""
        if pf_id <= 0 or not self._doc_repo:
            return
        for doc_info in self._linked_docs:
            doc_id = doc_info.get("id")
            if doc_id:
                try:
                    self._doc_repo.update_link_entity_id(
                        doc_id, old_entity_id=0, new_entity_id=pf_id, entity_type="proforma",
                    )
                except Exception as exc:
                    _logger.warning("Failed to update link entity_id for doc %s: %s", doc_id, exc)
        try:
            self._doc_repo.commit_transaction()
        except Exception:
            pass

    def _unlink_document(self) -> None:
        idx = self._linked_docs_list.currentRow()
        if idx < 0 or idx >= len(self._linked_docs):
            return
        removed = self._linked_docs.pop(idx)
        self._refresh_linked_docs_list()
        try:
            from services.document_service import DocumentService
            ds = DocumentService(self.db)
            # Find the link record for this document
            links = self._doc_repo.get_links(removed["id"]) if self._doc_repo else []
            for link in links:
                if link.get("linked_entity_type") == "proforma":
                    link_id = link.get("id")
                    if link_id:
                        ds.unlink_document(link_id)
                        break
        except Exception as exc:
            _logger.warning("Failed to unlink document %s: %s", removed.get("id"), exc)

    def _on_linked_doc_selected(self, row: int) -> None:
        has_selection = row >= 0 and row < len(self._linked_docs)
        self._unlink_doc_btn.setEnabled(has_selection)
        self._autofill_from_doc_btn.setEnabled(has_selection)

    def _autofill_from_linked_document(self) -> None:
        """Autofill proforma fields from the OCR text of a linked document."""
        idx = self._linked_docs_list.currentRow()
        if idx < 0 or idx >= len(self._linked_docs):
            return
        doc_info = self._linked_docs[idx]
        doc_id = doc_info.get("id")
        if not doc_id or not self._doc_repo:
            return
        try:
            doc = self._doc_repo.get_by_id(doc_id)
        except Exception:
            doc = None
        if not doc:
            return

        text = doc.get("text_content") or doc.get("ocr_text") or ""
        extracted = doc.get("extracted_data_json") or "{}"
        try:
            extracted_data = json.loads(extracted)
        except (json.JSONDecodeError, TypeError):
            extracted_data = {}

        if not text and not extracted_data:
            QMessageBox.warning(self, t("proforma_editor.autofill_empty"),
                                t("proforma_editor.autofill_empty"))
            return

        # Attempt to pre-fill from extracted data
        if extracted_data:
            client_name = extracted_data.get("client_name", "")
            client_address = extracted_data.get("client_address", "")
            client_vat = extracted_data.get("vat_number", "")
            total_amount = extracted_data.get("total_amount", extracted_data.get("amount", ""))

            if client_name:
                self._client_name = client_name
                self._c_client_name.setText(self._client_name)
            if client_address:
                self._client_address = client_address
                self._c_client_addr.setText(self._client_address)
            if client_vat:
                self._client_vat_raw = client_vat
                self._client_vat = f"VAT: {client_vat}"
                self._c_client_vat.setText(self._client_vat)
            if total_amount:
                try:
                    amt = float(total_amount)
                    if self._items_table.rowCount() > 0:
                        self._items_table.blockSignals(True)
                        price_item = self._items_table.item(0, 2)
                        if price_item:
                            price_item.setText(f"{amt:.2f}")
                        self._items_table.blockSignals(False)
                        self._recalc_all()
                except (ValueError, TypeError):
                    pass

            QMessageBox.information(self, t("proforma_editor.autofill_done"),
                                    t("proforma_editor.autofill_done"))
        elif text:
            QMessageBox.information(self, t("proforma_editor.autofill_partial"),
                                    t("proforma_editor.autofill_partial"))

    def _refresh_linked_docs_list(self) -> None:
        self._linked_docs_list.blockSignals(True)
        self._linked_docs_list.clear()
        for doc in self._linked_docs:
            self._linked_docs_list.addItem(doc.get("title", "Unknown"))
        self._linked_docs_list.blockSignals(False)
        if not self._linked_docs:
            self._unlink_doc_btn.setEnabled(False)
            self._autofill_from_doc_btn.setEnabled(False)

    # ══════════════════════════════════════════════════════════════════════════
    # PDF OPERATIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _collect_proforma_data(self) -> dict[str, Any]:
        """Collect all form data for PDF generation."""
        mode = "internal" if self._is_internal_mode else "client"
        is_client_mode = mode == "client"

        # Auto-generate number if not set
        pf_number = self._proforma_number
        if not pf_number:
            try:
                repo = self._get_proforma_service()._proforma_repo
                pf_number = repo.get_next_number()
            except Exception:
                pf_number = f"PROF-{datetime.now().year}-{datetime.now().strftime('%m%d')}-001"
            self._proforma_number = pf_number
            self._pf_number_value.setText(pf_number)

        subtotal = sum(item.get("amount", 0) for item in self._addon_items)

        try:
            disc_val = float(self._discount_value or "0")
        except ValueError:
            disc_val = 0
        if self._discount_type == "percentage" and disc_val > 0:
            discount_amount = subtotal * (disc_val / 100)
        else:
            discount_amount = disc_val if self._discount_type == "fixed" else 0
        if discount_amount > subtotal:
            discount_amount = subtotal
        after_discount = subtotal - discount_amount

        try:
            tax_rate = float(self._tax_rate or "0")
        except ValueError:
            tax_rate = 0
        tax_amount = after_discount * (tax_rate / 100)
        grand_total = after_discount + tax_amount

        discount_type_display = ""
        if self._discount_type == "percentage":
            discount_type_display = "Discount %"
        elif self._discount_type == "fixed":
            discount_type_display = "Discount Fixed"

        return {
            "proforma_number": pf_number,
            "invoice_number": pf_number,
            "issue_date": self._issue_date,
            "valid_until": self._valid_until,
            "due_date": self._valid_until,
            "payment_terms": self._payment_terms,
            "currency": self._currency,
            "branch": self._branch,
            "_format_key": self._format_key,
            "company": {
                "company_name": self._company_name,
                "cui": self._company_cui_raw,
                "reg_number": self._company_reg_raw,
                "address": self._company_address,
                "phone": self._company_phone_raw,
                "email": self._company_email_raw,
            },
            "client": {
                "name": self._client_name,
                "vat_number": self._client_vat_raw,
                "address": self._client_address,
                "phone": self._client_phone_raw,
                "email": self._client_email_raw,
            },
            "addon_items": self._addon_items,
            "line_items": self._addon_items,
            "description": self._description,
            "subtotal": subtotal,
            "total_tax": tax_amount,
            "discount_type": discount_type_display,
            "discount_value": disc_val,
            "discount": discount_amount,
            "grand_total": grand_total,
            "notes": self._notes,
            "logo_path": self._logo_path,
            "signature_path": self._signature_path,
            "stamp_path": self._stamp_path,
            "company_color": self._company_color,
            "mode": mode,
            # Proforma-specific
            "document_type": "proforma",
        }

    def _preview_pdf(self) -> None:
        """Generate and open the PDF in the system viewer silently."""
        data = self._collect_proforma_data()
        try:
            path = self._get_proforma_service().generate(data, mode=data.get("mode", "client"))
            if path and os.path.isfile(path):
                import subprocess
                subprocess.Popen([path], shell=True)
        except Exception as exc:
            _logger.exception("Preview failed")
            QMessageBox.warning(self, t("proforma_editor.error"),
                                str(exc))

    def _generate_pdf(self) -> None:
        """Generate the proforma PDF and persist it."""
        data = self._collect_proforma_data()
        if not data.get("addon_items"):
            QMessageBox.warning(self, t("proforma_editor.error"),
                                t("proforma_editor.no_items"))
            return
        try:
            path = self._get_proforma_service().generate_and_record(data)
            # Backfill the real proforma id on any linked documents
            pf_id = data.get("_record_id", 0)
            if pf_id:
                self._update_linked_entity_ids(pf_id)
            QMessageBox.information(
                self,
                t("proforma_editor.success"),
                t("proforma_editor.proforma_generated").format(os.path.basename(path)),
            )
        except Exception as exc:
            _logger.exception("Generate failed")
            QMessageBox.warning(self, t("proforma_editor.error"),
                                str(exc))

    def _print_pdf(self) -> None:
        """Generate and send to printer."""
        data = self._collect_proforma_data()
        try:
            path = self._get_proforma_service().generate(data, mode=data.get("mode", "client"))
            if path and os.path.isfile(path):
                import subprocess
                subprocess.Popen(["print", path], shell=True)
        except Exception as exc:
            _logger.exception("Print failed")
            QMessageBox.warning(self, t("proforma_editor.error"),
                                str(exc))

    def _email_pdf(self) -> None:
        """Email the proforma PDF with optional linked documents."""
        from PySide6.QtWidgets import QCheckBox as QCheckBoxWidget
        data = self._collect_proforma_data()
        if not data.get("addon_items"):
            QMessageBox.warning(self, t("proforma_editor.error"),
                                t("proforma_editor.no_items"))
            return

        # Ask for recipient first (don't generate PDF until user confirms)
        email, ok = QInputDialog.getText(
            self,
            t("proforma_editor.email_to"),
            t("proforma_editor.enter_email"),
        )
        if not ok or not email:
            return

        # Ask whether to include linked docs
        include_linked = False
        if self._linked_docs:
            cb = QCheckBoxWidget(t("proforma_editor.include_linked_docs"))
            cb.setChecked(False)
            msg = QMessageBox(self)
            msg.setWindowTitle(t("proforma_editor.email"))
            msg.setText(t("proforma_editor.email_confirm"))
            msg.setCheckBox(cb)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            result = msg.exec_()
            if result != QMessageBox.Yes:
                return
            include_linked = cb.isChecked()

        # Now generate and record
        try:
            path = self._get_proforma_service().generate_and_record(data)
            data["_generated_path"] = path
        except Exception as exc:
            _logger.exception("Generate failed before email")
            QMessageBox.warning(self, t("proforma_editor.error"), str(exc))
            return

        # Get the record id and backfill linked document entity_ids
        pf_number = data.get("proforma_number", "")
        pf_id = data.get("_record_id", 0)
        if not pf_id and pf_number:
            try:
                record = self._get_proforma_service()._proforma_repo.get_by_number(pf_number)
                if record:
                    pf_id = record["id"]
                    data["_record_id"] = pf_id
            except Exception:
                pass
        if pf_id:
            self._update_linked_entity_ids(pf_id)

        try:
            success = self._get_proforma_service().send_email(
                proforma_id=pf_id,
                recipient=email,
                proforma_data=data,
                include_linked_docs=include_linked,
                skip_generate=True,
            )
            if success:
                QMessageBox.information(self, t("proforma_editor.email_sent"),
                                        t("proforma_editor.email_sent"))
            else:
                QMessageBox.warning(self, t("proforma_editor.email_failed"),
                                    t("proforma_editor.email_failed"))
        except Exception as exc:
            _logger.exception("Email failed")
            QMessageBox.warning(self, t("proforma_editor.email_failed"),
                                str(exc))

    # ── Draft Management ──────────────────────────────────────────────────────

    def _save_draft(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            t("proforma_editor.draft_name"),
            t("proforma_editor.draft_name"),
        )
        if not ok or not name:
            return
        data = self._collect_proforma_data()
        svc = self._get_proforma_service()
        if svc.save_draft(data, name):
            QMessageBox.information(
                self,
                t("proforma_editor.draft_saved"),
                t("proforma_editor.draft_saved_msg").format(name),
            )
        else:
            QMessageBox.warning(self, t("proforma_editor.error"),
                                t("proforma_editor.draft_save_failed"))

    def _load_draft(self) -> None:
        svc = self._get_proforma_service()
        drafts = svc.list_drafts()
        if not drafts:
            QMessageBox.information(self, t("proforma_editor.no_drafts"),
                                    t("proforma_editor.no_drafts"))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(t("proforma_editor.load_draft"))
        dlg.setMinimumSize(300, 400)
        dlg_layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        for name in drafts:
            list_widget.addItem(name)
        dlg_layout.addWidget(list_widget)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        load_btn = Btn(btn_row, t("proforma_editor.load"), variant="primary")
        cancel_btn = Btn(btn_row, t("proforma_editor.cancel"), variant="ghost")

        def do_load():
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
        company = draft.get("company") or {}
        client = draft.get("client") or {}

        self._company_name = str(company.get("company_name", ""))
        self._company_cui_raw = company.get("cui", "")
        self._company_cui = f"CUI: {self._company_cui_raw}" if self._company_cui_raw else ""
        self._company_reg_raw = company.get("reg_number", "")
        self._company_reg = f"Reg: {self._company_reg_raw}" if self._company_reg_raw else ""
        self._company_address = str(company.get("address", ""))
        self._company_phone_raw = company.get("phone", "")
        self._company_phone = f"Tel: {self._company_phone_raw}" if self._company_phone_raw else ""
        self._company_email_raw = company.get("email", "")
        self._company_email = f"Email: {self._company_email_raw}" if self._company_email_raw else ""

        self._client_name = str(client.get("name", ""))
        self._client_vat_raw = client.get("vat_number", "")
        self._client_vat = f"VAT: {self._client_vat_raw}" if self._client_vat_raw else ""
        self._client_address = str(client.get("address", ""))
        self._client_phone_raw = client.get("phone", "")
        self._client_phone = f"Tel: {self._client_phone_raw}" if self._client_phone_raw else ""
        self._client_email_raw = client.get("email", "")
        self._client_email = f"Email: {self._client_email_raw}" if self._client_email_raw else ""
        self._issue_date = str(draft.get("issue_date", self._issue_date) or self._issue_date)
        self._valid_until = str(draft.get("valid_until", draft.get("due_date", self._valid_until)) or self._valid_until)
        self._payment_terms = str(draft.get("payment_terms", self._payment_terms) or self._payment_terms)
        self._branch = draft.get("branch", "")
        self._format_key = draft.get("_format_key", PROF_DEFAULT_FMT)
        self._notes = str(draft.get("notes", ""))
        self._description = str(draft.get("description", ""))
        self._tax_rate = str(draft.get("tax_rate", 19) or 19)
        self._discount_type = "percentage" if "Percentage" in (draft.get("discount_type") or "") else "fixed"
        if self._discount_type == "percentage":
            self._disc_type_combo.setCurrentIndex(0)
        else:
            self._disc_type_combo.setCurrentIndex(1)
        self._discount_value = str(draft.get("discount_value", 0) or 0)
        self._currency = str(draft.get("currency", "EUR") or "EUR")
        self._logo_path = str(draft.get("logo_path", "") or "")
        self._signature_path = str(draft.get("signature_path", "") or "")
        self._stamp_path = str(draft.get("stamp_path", "") or "")
        self._company_color = str(draft.get("company_color", COLORS["accent"]) or COLORS["accent"])
        mode = draft.get("mode", "client")
        self._is_client_mode = mode == "client"
        self._is_internal_mode = mode == "internal"
        self._proforma_number = str(draft.get("proforma_number", "") or "")

        # Restore line items
        items = draft.get("addon_items") or draft.get("line_items") or []
        self._items_table.blockSignals(True)
        self._items_table.setRowCount(0)
        self._addon_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = self._items_table.rowCount()
            self._items_table.insertRow(row)
            self._items_table.setItem(row, 0, QTableWidgetItem(str(item.get("description", ""))))
            try:
                qty = float(item.get("quantity", 1) or 1)
            except (ValueError, TypeError):
                qty = 1
            try:
                unit_price = float(item.get("unit_price", 0) or 0)
            except (ValueError, TypeError):
                unit_price = 0
            try:
                amount = float(item.get("amount", 0) or 0)
            except (ValueError, TypeError):
                amount = 0
            self._items_table.setItem(row, 1, QTableWidgetItem(str(qty)))
            self._items_table.setItem(row, 2, QTableWidgetItem(f"{unit_price:.2f}"))
            total_item = QTableWidgetItem(f"{amount:.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            self._items_table.setItem(row, 3, total_item)
            self._addon_items.append({"description": item.get("description", ""), "quantity": qty, "unit_price": unit_price, "amount": amount})
        self._items_table.blockSignals(False)

        # Update UI
        self._issue_date_input.setText(self._issue_date)
        self._valid_until_input.setText(self._valid_until)
        self._payment_terms_combo.setCurrentText(self._payment_terms)
        self._branch_entry.setText(self._branch)
        self._notes_edit.blockSignals(True)
        self._notes_edit.setText(self._notes)
        self._notes_edit.blockSignals(False)
        self._desc_text_edit.blockSignals(True)
        self._desc_text_edit.setText(self._description)
        self._desc_text_edit.blockSignals(False)
        self._tax_combo.setCurrentText(self._tax_rate)
        self._logo_entry.setText(self._logo_path)
        self._sig_entry.setText(self._signature_path)
        self._stamp_entry.setText(self._stamp_path)
        self._pf_number_value.setText(self._proforma_number or "(auto)")

        self._update_canvas_labels()
        self._recalc_all()

    # ── Utility Methods ───────────────────────────────────────────────────────

    def _log(self, msg: str, *args) -> None:
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("ProformaEditor: " + msg, *args)


# ══════════════════════════════════════════════════════════════════════════════
# Company Editor Dialog
# ══════════════════════════════════════════════════════════════════════════════


class CompanyEditorQtDialog(QDialog):
    """Qt dialog for editing company info."""

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self._on_save = None
        self.setWindowTitle(t("proforma_editor.company_editor"))
        self.resize(480, 440)
        self.setMinimumSize(400, 380)

        conf = load_company_config()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["6"], S["6"], S["6"], S["6"])
        layout.setSpacing(S["4"])

        header = QLabel(t("proforma_editor.company_editor"))
        header.setProperty("fontRole", "h2")
        layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(S["2"])

        fields = [
            ("Company Name", "name", conf.get("company_name", "")),
            ("CUI", "cui", conf.get("cui", "")),
            ("Reg. Number", "reg", conf.get("reg_number", "")),
            ("Address", "addr", conf.get("address", "")),
            ("Phone", "phone", conf.get("phone", "")),
            ("Email", "email", conf.get("email", "")),
        ]

        self._entries: dict[str, StyledLineEdit] = {}
        for label_text, key, default in fields:
            lbl = QLabel(label_text)
            lbl.setProperty("fontRole", "label")
            content_layout.addWidget(lbl)
            entry = StyledLineEdit(text=default)
            content_layout.addWidget(entry)
            self._entries[key] = entry

        layout.addWidget(content, 1)

        btn_frame = QWidget()
        btn_frame_layout = QHBoxLayout(btn_frame)
        btn_frame_layout.setContentsMargins(0, 0, 0, 0)
        btn_frame_layout.setSpacing(S["2"])

        save_btn = Btn(btn_frame, t("proforma_editor.save"), variant="primary")
        save_btn.clicked.connect(self._save_and_close)
        btn_frame_layout.addWidget(save_btn)

        cancel_btn = Btn(btn_frame, t("proforma_editor.cancel"), variant="ghost")
        cancel_btn.clicked.connect(self.reject)
        btn_frame_layout.addWidget(cancel_btn)
        btn_frame_layout.addStretch()
        layout.addWidget(btn_frame)

    def _save_and_close(self) -> None:
        data = {
            "company_name": self._entries["name"].text(),
            "cui": self._entries["cui"].text(),
            "reg_number": self._entries["reg"].text(),
            "address": self._entries["addr"].text(),
            "phone": self._entries["phone"].text(),
            "email": self._entries["email"].text(),
        }
        from services.invoicing.config_manager import save_company_config as _save
        _save(data)
        bus = EventBus()
        bus.publish(SETTINGS_UPDATED, {"data": {"key": "company_config", "value": data}})
        self.accept()
