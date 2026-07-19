"""PySide6 invoice editor.

Replaces ``ui/invoice_editor.py``. Provides a form-based invoice editor with
client/trip selection, line items, auto-calculated totals, branding controls,
PDF generation, and draft save/load.

Usage as embedded widget::

    editor = QtInvoiceEditor(parent_widget, db, prefs=prefs)
    editor.wakeup()

Usage as standalone window (QDialog)::

    dlg = InvoiceEditorDialog(db, prefs=prefs, parent=parent_widget)
    if dlg.exec_():
        ...
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.app_state import AppState
from services.client_service import ClientService
from services.numbering_service import NumberingService
from repositories.invoice_repository import INVOICE_NUMBER_FORMATS, DEFAULT_INVOICE_FORMAT_KEY as INV_DEFAULT_FMT  # model constants, not data access
from services.i18n import t
from ui.base_view import BaseView
from utils.editor_toolkit import DebouncedTask, export_editor_data, register_shortcuts, validate_and_highlight
from services.invoicing.config_manager import load_company_config, save_company_config
from services.invoicing.service import InvoiceService
from services.operations.event_bus import SETTINGS_UPDATED
from services.preferences import PreferencesManager
from services.trip_service import TripService
from ui.components import Btn, Card, Divider, Label, PageTitle, SectionTitle
from ui.views.invoice_editor.line_items import LineItemsMixin
from ui.theme import COLORS, S
from ui.widgets import (
    ScrollableFormContainer,
    StyledCheckBox,
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    StyledTextEdit,
    field,
)

_logger = logging.getLogger(__name__)

DRAFTS_DIR = os.path.join("data", "invoice_drafts")


# ──────────────────────────────────────────────────────────────────────────────
# QtInvoiceEditor
# ──────────────────────────────────────────────────────────────────────────────


class QtInvoiceEditor(BaseView, LineItemsMixin):
    """Professional invoice editor with live preview.

    This is a QWidget for embedding in tab views. It uses ``ScrollableFormContainer``
    for the main form area and provides section cards for client info, invoice details,
    line items, and totals.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: PreferencesManager | None = None,
        invoice_repo=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs or (PreferencesManager(db) if db else None)
        self._trip_service = TripService(db) if db else None
        # Use ClientService instead of direct ClientRepository access
        self._client_service = ClientService(db) if db else None
        # NumberingService handles invoice/proforma/receipt number generation
        self._numbering_service = NumberingService(db) if db else None
        # InvoiceService is lazy-init to avoid circular dependency at import time
        self._invoice_service: InvoiceService | None = None  # lazy
        # invoice_repo parameter kept for backward compatibility
        _ = invoice_repo  # no longer used directly
        self._app_state = AppState()


        # ── Data state ────────────────────────────────────────────────────────
        self._clients: list[dict[str, Any]] = []
        self._client_map: dict[str, dict[str, Any]] = {}
        self._trips: list[dict[str, Any]] = []
        self._trip_map: dict[str, dict[str, Any]] = {}

        # Invoice data (replaces tk.StringVar with plain attributes)
        self._invoice_number: str = self._gen_invoice_number()
        self._issue_date: str = datetime.now().strftime("%Y-%m-%d")
        self._due_date: str = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self._payment_terms: str = "Net 30"
        self._notes: str = ""
        self._tax_rate: str = "19"
        self._discount_type: str = ""  # "percentage" or "fixed"
        self._discount_value: str = "0"
        self._currency: str = self.prefs.get_currency() if self.prefs else "EUR"

        # Additional line items
        self._addon_items: list[dict[str, Any]] = []

        # Invoice mode
        self._is_client_invoice: bool = True
        self._is_internal_invoice: bool = False

        # Trip prices
        self._trip_base_price: str = "0.00"
        self._trip_price_pre_vat: str = ""
        self._trip_vat_percent: str = ""

        # Trip details
        self._truck_plate: str = ""
        self._driver_name: str = ""
        self._distance: str = ""

        # Dynamic stops
        self._loading_stops: list[dict[str, str]] = [{"value": ""}]
        self._unloading_stops: list[dict[str, str]] = [{"value": ""}]

        # Free-text description
        self._description: str = ""

        # Branding
        self._logo_path: str = ""
        self._signature_path: str = ""
        self._stamp_path: str = ""
        self._company_color: str = COLORS["accent"]

        # Client info (editable, auto-filled)
        self._client_name: str = ""
        self._client_vat: str = ""
        self._client_address: str = ""
        self._client_phone: str = ""
        self._client_email: str = ""
        self._selected_client_id: int | None = None

        # Company info
        self._company_name: str = ""
        self._company_cui: str = ""
        self._company_reg: str = ""
        self._company_address: str = ""
        self._company_phone: str = ""
        self._company_email: str = ""

        # Selected trip
        self._selected_trip_id: int | None = None
        self._selected_trip_data: dict[str, Any] | None = None

        # i18n
        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

        # Branch / Office
        self._branch: str = ""
        self._format_key: str = INV_DEFAULT_FMT

        # Debounced recalculation
        self._recalc_task = DebouncedTask(self._refresh_totals_display)

        # Keyboard shortcuts
        self._shortcuts = register_shortcuts(self, {
            "generate": self._generate_pdf,
            "save_draft": self._save_draft,
            "load_draft": self._load_draft,
            "export_json": self._on_export_json,
            "print": self._print_invoice,
        })

        # ── Build UI ─────────────────────────────────────────────────────────
        self._build_ui()
        self._load_company_config()
        self._add_default_addon_item()

        self._data_loaded: bool = False
        self._subscribe(SETTINGS_UPDATED, self._on_settings_updated)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Load DB-dependent data. Called when the tab becomes visible."""
        if not self._data_loaded:
            self._load_clients()
            self._load_trips()
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
        # Page header
        self._page_title.setText(t("invoice_editor.title"))
        self._page_subtitle.setText(t("invoice_editor.subtitle", ""))

        # Top bar
        self._client_label.setText(t("invoice_editor.select_client"))
        self._trip_label.setText(t("invoice_editor.select_trip"))
        self._auto_btn.setText(t("invoice_editor.auto_fill"))
        self._cb_client.setText(t("invoice.radio_client_invoice"))
        self._cb_internal.setText(t("invoice.radio_internal_invoice"))
        self._refresh_btn.setText("\U0001F504")

        # Financial panel
        self._financial_header.setText(t("invoice_editor.financial_controls").upper())
        self._tax_label.setText(t("invoice_editor.tax_rate"))
        self._discount_label.setText(t("invoice_editor.discount"))
        self._currency_label.setText(t("invoice_editor.currency"))
        self._subtotal_title.setText(t("invoice_editor.subtotal"))
        self._tax_title.setText(t("invoice_editor.tax"))
        self._discount_title.setText(t("invoice_editor.discount"))
        self._grand_title.setText(t("invoice_editor.grand_total"))

        # Branding panel
        self._branding_header.setText(t("invoice_editor.branding").upper())
        self._logo_label.setText(t("invoice_editor.logo"))
        self._color_label.setText(t("invoice_editor.company_color"))
        self._color_btn.setText(t("invoice_editor.pick_color"))
        self._sig_label.setText(t("invoice_editor.signature"))
        self._stamp_label.setText(t("invoice_editor.stamp"))
        self._browse_logo_btn.setText(t("invoice_editor.browse"))
        self._browse_sig_btn.setText(t("invoice_editor.browse"))
        self._browse_stamp_btn.setText(t("invoice_editor.browse"))

        # Canvas / preview section headers
        self._from_header.setText(t("invoice_editor.from").upper())
        self._bill_to_header.setText(t("invoice_editor.bill_to").upper())
        self._trip_header.setText(t("invoice_editor.trip_details").upper())
        self._inv_meta_header.setText(t("invoice_editor.invoice_metadata").upper())
        self._desc_label.setText(t("invoice_editor.description"))
        self._notes_label.setText(t("invoice_editor.notes"))
        self._lit_header_label.setText(t("invoice_editor.line_items").upper())
        self._add_row_btn.setText("+ " + t("invoice_editor.add_row"))

        # Bottom bar
        self._preview_btn.setText("\U0001F50D " + t("invoice_editor.preview_pdf"))
        self._generate_btn.setText("\U0001F4C4 " + t("invoice_editor.generate_pdf"))
        self._print_btn.setText("\U0001F5A8 " + t("invoice_editor.print"))
        self._email_btn.setText("\U0001F4E7 " + t("invoice_editor.email"))
        self._save_draft_btn.setText("\U0001F4BE " + t("invoice_editor.save_draft"))
        self._load_draft_btn.setText("\U0001F4C2 " + t("invoice_editor.load_draft"))

        # Canvas totals
        self._canvas_subtotal_label.setText(t("invoice_editor.subtotal"))
        self._canvas_tax_label.setText(t("invoice_editor.tax"))
        self._canvas_discount_label.setText(t("invoice_editor.discount"))
        self._canvas_grand_label.setText(t("invoice_editor.grand_total"))

        # Update discount combo values
        idx = self._disc_type_combo.currentIndex()
        self._disc_type_combo.clear()
        self._disc_type_combo.addItems([
            t("invoice_editor.discount_percentage"),
            t("invoice_editor.discount_fixed"),
        ])
        if idx >= 0:
            self._disc_type_combo.setCurrentIndex(idx)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_invoice_service(self) -> InvoiceService:
        if self._invoice_service is None:
            self._invoice_service = InvoiceService(self.db, prefs=self.prefs)
        return self._invoice_service

    def _gen_invoice_number(self) -> str:
        """Generate an invoice number via NumberingService."""
        if self._numbering_service:
            try:
                return self._numbering_service.next_invoice_number(format_key=self._format_key)
            except Exception:
                pass
        # Fallback if numbering service is unavailable
        year = datetime.now().year
        return f"INV-{year}-{datetime.now().strftime('%m%d')}-001"

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

        # View header (PageTitle + secondary label)
        self._build_view_header()

        # Build sections inside the scrollable content
        self._build_client_section()       # From / Bill To
        self._build_invoice_details_section()
        self._build_trip_details_section()
        self._build_line_items_section()
        self._build_totals_section()
        self._build_branding_section()
        self._build_notes_section()

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
        self._client_label = Label(self._top_bar, t("invoice_editor.select_client"), role="field-label")
        layout.addWidget(self._client_label)

        self._client_combo = StyledComboBox()
        self._client_combo.currentTextChanged.connect(self._on_client_selected)
        self._client_combo.setMinimumWidth(200)
        layout.addWidget(self._client_combo)

        # Trip selector
        self._trip_label = QLabel(t("invoice_editor.select_trip"))
        self._trip_label.setProperty("fontRole", "label")
        layout.addWidget(self._trip_label)

        self._trip_combo = StyledComboBox()
        self._trip_combo.currentTextChanged.connect(self._on_trip_selected)
        self._trip_combo.setMinimumWidth(240)
        layout.addWidget(self._trip_combo)

        # Auto-fill button
        self._auto_btn = Btn(self._top_bar, t("invoice_editor.auto_fill"),
                              variant="primary")
        self._auto_btn.setFixedWidth(90)
        self._auto_btn.clicked.connect(self._auto_fill_all)
        layout.addWidget(self._auto_btn)

        # Mode checkboxes
        self._cb_client = StyledCheckBox(text=t("invoice.radio_client_invoice"))
        self._cb_client.setChecked(True)
        self._cb_client.toggled.connect(lambda checked: self._on_mode_changed("client", checked))
        layout.addWidget(self._cb_client)

        self._cb_internal = StyledCheckBox(text=t("invoice.radio_internal_invoice"))
        self._cb_internal.toggled.connect(lambda checked: self._on_mode_changed("internal", checked))
        layout.addWidget(self._cb_internal)

        # Refresh button
        self._refresh_btn = Btn(self._top_bar, "\U0001F504",
                                 variant="ghost")
        self._refresh_btn.setFixedWidth(34)
        self._refresh_btn.clicked.connect(self._refresh_all)
        layout.addWidget(self._refresh_btn)

        layout.addStretch()

    # ── View Header ──────────────────────────────────────────────────────────

    def _build_view_header(self) -> None:
        """Build the page header with title and description."""
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, S["3"])
        layout.setSpacing(S["1"])

        self._page_title = PageTitle(header, t("invoice_editor.title"))
        layout.addWidget(self._page_title)

        self._page_subtitle = Label(
            header,
            t("invoice_editor.subtitle", "Create and manage invoices"),
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

        # Section header
        header = SectionTitle(container, t("invoice_editor.client_info"))
        layout.addWidget(header)

        # Two-column: From / Bill To
        cols = QWidget()
        cols_layout = QHBoxLayout(cols)
        cols_layout.setContentsMargins(0, 0, 0, 0)
        cols_layout.setSpacing(S["4"])

        # ── From (Company) ────────────────────────────────────────────────
        from_card = self._make_card()
        from_layout = from_card.layout()
        from_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        from_layout.setSpacing(S["2"])

        self._from_header = QLabel(t("invoice_editor.from").upper())
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

        # ── Bill To (Client) ──────────────────────────────────────────────
        to_card = self._make_card()
        to_layout = to_card.layout()
        to_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        to_layout.setSpacing(S["2"])

        self._bill_to_header = QLabel(t("invoice_editor.bill_to").upper())
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
        """Refresh the canvas/preview labels from current data."""
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

        self._truck_plate_label.setText(self._truck_plate)
        self._driver_name_label.setText(self._driver_name)
        self._distance_label.setText(self._distance)

        self._inv_num_label.setText(self._invoice_number)
        self._issue_date_label.setText(self._issue_date)
        self._due_date_label.setText(self._due_date)
        self._payment_terms_label.setText(self._payment_terms)

        # Description (block signals to prevent textChanged cascades)
        self._desc_text_edit.blockSignals(True)
        self._desc_text_edit.setPlainText(self._description)
        self._desc_text_edit.blockSignals(False)

        # Notes
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(self._notes)
        self._notes_edit.blockSignals(False)

    # ── Invoice Details Section ──────────────────────────────────────────────

    def _build_invoice_details_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionTitle(container, t("invoice_editor.invoice_details"))
        layout.addWidget(header)

        card = self._make_card()
        card_layout = card.layout()
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["3"])

        # Two-row grid for invoice metadata
        grid = QWidget()
        grid_layout = QGridLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(S["3"])

        # Row 0: Invoice Number, Issue Date
        self._inv_num_edit = StyledLineEdit(text=self._invoice_number)
        self._inv_num_edit.textChanged.connect(self._on_inv_num_changed)
        inv_num_widget = field(grid, t("invoice_editor.invoice_number"),
                                self._inv_num_edit)
        grid_layout.addWidget(inv_num_widget, 0, 0)

        self._issue_date_edit = StyledLineEdit(text=self._issue_date,
                                                 placeholder="YYYY-MM-DD")
        self._issue_date_edit.textChanged.connect(self._on_issue_date_changed)
        issue_widget = field(grid, t("invoice_editor.issue_date"),
                              self._issue_date_edit)
        grid_layout.addWidget(issue_widget, 0, 1)

        # Row 1: Due Date, Payment Terms
        self._due_date_edit = StyledLineEdit(text=self._due_date,
                                               placeholder="YYYY-MM-DD")
        self._due_date_edit.textChanged.connect(self._on_due_date_changed)
        due_widget = field(grid, t("invoice_editor.due_date"),
                            self._due_date_edit)
        grid_layout.addWidget(due_widget, 1, 0)

        self._payment_terms_edit = StyledLineEdit(text=self._payment_terms)
        self._payment_terms_edit.textChanged.connect(self._on_payment_terms_changed)
        terms_widget = field(grid, t("invoice_editor.payment_terms"),
                              self._payment_terms_edit)
        grid_layout.addWidget(terms_widget, 1, 1)

        # Row 2: Branch / Office
        self._branch_entry = StyledLineEdit(text=self._branch,
                                             placeholder=t("receipt.branch_placeholder"))
        self._branch_entry.textChanged.connect(self._on_branch_changed)
        branch_widget = field(grid, t("invoice_editor.branch"), self._branch_entry)
        grid_layout.addWidget(branch_widget, 2, 0)

        # Number format (row 2, col 1)
        fmt_display = [f"{key} ({ex})" for key, (_, ex) in INVOICE_NUMBER_FORMATS.items()]
        self._format_combo = StyledComboBox(grid, values=fmt_display)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        fmt_widget = field(grid, t("invoice_editor.number_format"), self._format_combo)
        grid_layout.addWidget(fmt_widget, 2, 1)

        card_layout.addWidget(grid)

        # Invoice metadata preview row
        meta_card = QFrame()
        meta_card.setProperty("role", "card-inner")
        meta_layout = QHBoxLayout(meta_card)
        meta_layout.setContentsMargins(S["3"], S["3"], S["3"], S["3"])

        self._inv_meta_header = QLabel(t("invoice_editor.invoice_metadata").upper())
        self._inv_meta_header.setProperty("fontRole", "section")
        meta_layout.addWidget(self._inv_meta_header)

        self._inv_num_label = QLabel(self._invoice_number)
        self._inv_num_label.setProperty("fontRole", "body")
        meta_layout.addWidget(self._inv_num_label)

        self._issue_date_label = QLabel(self._issue_date)
        self._issue_date_label.setProperty("fontRole", "body")
        meta_layout.addWidget(self._issue_date_label)

        self._due_date_label = QLabel(self._due_date)
        self._due_date_label.setProperty("fontRole", "body")
        meta_layout.addWidget(self._due_date_label)

        self._payment_terms_label = QLabel(self._payment_terms)
        self._payment_terms_label.setProperty("fontRole", "body")
        meta_layout.addWidget(self._payment_terms_label)

        meta_layout.addStretch()
        card_layout.addWidget(meta_card)

        # Description
        self._desc_label = QLabel(t("invoice_editor.description"))
        self._desc_label.setProperty("fontRole", "label")
        card_layout.addWidget(self._desc_label)

        self._desc_text_edit = StyledTextEdit(height=60)
        self._desc_text_edit.textChanged.connect(self._on_description_changed)
        card_layout.addWidget(self._desc_text_edit)

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _set_text(self, edit, text: str) -> None:
        """Update a ``QLineEdit`` *and* its internal state attribute
        without re-entering the ``textChanged`` handler that already
        keeps the attribute in sync (which would re-emit and could
        swallow keystrokes).  ``blockSignals`` is the safe Qt idiom.
        """
        if edit is None:
            return
        edit.blockSignals(True)
        edit.setText(text)
        edit.blockSignals(False)

    def _set_plain_text(self, edit, text: str) -> None:
        """Same as ``_set_text`` but for ``QPlainTextEdit``."""
        if edit is None:
            return
        edit.blockSignals(True)
        edit.setPlainText(text)
        edit.blockSignals(False)

    def _on_inv_num_changed(self, text: str) -> None:
        self._invoice_number = text
        self._inv_num_label.setText(text)
        self._recalc_all()

    def _on_issue_date_changed(self, text: str) -> None:
        self._issue_date = text
        self._issue_date_label.setText(text)
        self._recalc_all()

    def _on_due_date_changed(self, text: str) -> None:
        self._due_date = text
        self._due_date_label.setText(text)
        self._recalc_all()

    def _on_payment_terms_changed(self, text: str) -> None:
        self._payment_terms = text
        self._payment_terms_label.setText(text)

    def _on_branch_changed(self, text: str) -> None:
        self._branch = text.strip()
        self._recalc_all()

    def _on_format_changed(self, text: str) -> None:
        """Update invoice number when format changes."""
        if not text:
            return
        for key in INVOICE_NUMBER_FORMATS:
            if text.startswith(key):
                self._format_key = key
                break
        svc = self._get_invoice_service()
        if svc and hasattr(svc, "set_format_key"):
            svc.set_format_key(self._format_key)
        self._inv_num_edit.setText(self._gen_invoice_number())

    def _on_description_changed(self) -> None:
        self._description = self._desc_text_edit.toPlainText()

    # ── Trip Details Section ────────────────────────────────────────────────

    def _build_trip_details_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionTitle(container, t("invoice_editor.trip_details"))
        layout.addWidget(header)

        card = self._make_card()
        card_layout = card.layout()
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["3"])

        # Vehicle info row
        trip_grid = QWidget()
        trip_grid_layout = QHBoxLayout(trip_grid)
        trip_grid_layout.setContentsMargins(0, 0, 0, 0)
        trip_grid_layout.setSpacing(S["4"])

        # Truck plate
        self._truck_plate_edit = StyledLineEdit(
            text=self._truck_plate,
            placeholder=t("invoice_editor.truck_plate"),
        )
        self._truck_plate_edit.textChanged.connect(self._on_truck_plate_changed)
        plate_w = field(trip_grid, t("invoice_editor.truck_plate"),
                         self._truck_plate_edit)
        trip_grid_layout.addWidget(plate_w)

        # Driver
        self._driver_name_edit = StyledLineEdit(
            text=self._driver_name,
            placeholder=t("invoice_editor.driver"),
        )
        self._driver_name_edit.textChanged.connect(self._on_driver_name_changed)
        driver_w = field(trip_grid, t("invoice_editor.driver"),
                          self._driver_name_edit)
        trip_grid_layout.addWidget(driver_w)

        # Distance
        self._distance_edit = StyledLineEdit(
            text=self._distance,
            placeholder=t("invoice_editor.distance"),
        )
        self._distance_edit.textChanged.connect(self._on_distance_changed)
        dist_w = field(trip_grid, t("invoice_editor.distance"),
                        self._distance_edit)
        trip_grid_layout.addWidget(dist_w)

        card_layout.addWidget(trip_grid)

        # Preview labels for trip details
        self._truck_plate_label = QLabel(self._truck_plate)
        self._truck_plate_label.setProperty("fontRole", "body")
        card_layout.addWidget(self._truck_plate_label)

        self._driver_name_label = QLabel(self._driver_name)
        self._driver_name_label.setProperty("fontRole", "body")
        card_layout.addWidget(self._driver_name_label)

        self._distance_label = QLabel(self._distance)
        self._distance_label.setProperty("fontRole", "body")
        card_layout.addWidget(self._distance_label)

        # Stops section
        self._stops_container = QWidget()
        self._stops_layout = QVBoxLayout(self._stops_container)
        self._stops_layout.setContentsMargins(0, S["2"], 0, 0)
        self._stops_layout.setSpacing(S["2"])
        card_layout.addWidget(self._stops_container)
        self._rebuild_stops_ui()

        layout.addWidget(card)
        self._scroll.add_widget(container)



    def _on_truck_plate_changed(self, text: str) -> None:
        self._truck_plate = text
        self._truck_plate_label.setText(text)

    def _on_driver_name_changed(self, text: str) -> None:
        self._driver_name = text
        self._driver_name_label.setText(text)

    def _on_distance_changed(self, text: str) -> None:
        self._distance = text
        self._distance_label.setText(text)

    def _rebuild_stops_ui(self) -> None:
        """Rebuild the stops section in the trip details card."""
        for i in reversed(range(self._stops_layout.count())):
            w = self._stops_layout.itemAt(i).widget()
            if w is not None:
                w.deleteLater()

        # Loading stops
        load_label = QLabel(t("invoice_editor.loading_stops"))
        load_label.setProperty("fontRole", "label")
        self._stops_layout.addWidget(load_label)

        for i, _stop in enumerate(self._loading_stops):
            self._build_stop_row(i, "loading")

        add_load_btn = Btn(
            self._stops_container,
            "+ " + t("invoice_editor.add_loading_stop"),
            variant="ghost",
        )
        add_load_btn.clicked.connect(self._add_loading_stop)
        self._stops_layout.addWidget(add_load_btn)

        # Divider
        self._stops_layout.addWidget(Divider())

        # Unloading stops
        unload_label = QLabel(t("invoice_editor.unloading_stops"))
        unload_label.setProperty("fontRole", "label")
        self._stops_layout.addWidget(unload_label)

        for i, _stop in enumerate(self._unloading_stops):
            self._build_stop_row(i, "unloading")

        add_unload_btn = Btn(
            self._stops_container,
            "+ " + t("invoice_editor.add_unloading_stop"),
            variant="ghost",
        )
        add_unload_btn.clicked.connect(self._add_unloading_stop)
        self._stops_layout.addWidget(add_unload_btn)

    def _build_stop_row(self, idx: int, stop_type: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

        label_text = f"{t('invoice_editor.loading_label') if stop_type == 'loading' else t('invoice_editor.unloading_label')} {idx + 1}"
        label = QLabel(label_text)
        label.setProperty("fontRole", "label")
        label.setFixedWidth(70)
        row_layout.addWidget(label)

        stops_list = self._loading_stops if stop_type == "loading" else self._unloading_stops
        entry = StyledLineEdit(text=stops_list[idx]["value"],
                               placeholder=label_text)
        entry.textChanged.connect(
            lambda text, i=idx, t=stop_type: self._on_stop_text_changed(i, t, text)
        )
        row_layout.addWidget(entry, 1)

        if len(stops_list) > 1:
            remove_btn = Btn(row, "\u2716", variant="ghost")
            remove_btn.setFixedSize(22, 22)
            remove_btn.clicked.connect(
                lambda checked, i=idx, t=stop_type: self._remove_stop(i, t)
            )
            row_layout.addWidget(remove_btn)

        self._stops_layout.addWidget(row)

    def _on_stop_text_changed(self, idx: int, stop_type: str, text: str) -> None:
        stops = self._loading_stops if stop_type == "loading" else self._unloading_stops
        if 0 <= idx < len(stops):
            stops[idx]["value"] = text

    def _add_loading_stop(self) -> None:
        self._loading_stops.append({"value": ""})
        self._rebuild_stops_ui()

    def _add_unloading_stop(self) -> None:
        self._unloading_stops.append({"value": ""})
        self._rebuild_stops_ui()

    def _remove_stop(self, idx: int, stop_type: str) -> None:
        stops = self._loading_stops if stop_type == "loading" else self._unloading_stops
        if len(stops) > 1:
            del stops[idx]
            self._rebuild_stops_ui()

    # ── Branding Section ────────────────────────────────────────────────────

    def _build_branding_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        self._branding_header = SectionTitle(container, t("invoice_editor.branding"))
        layout.addWidget(self._branding_header)

        card = self._make_card()
        card_layout = card.layout()
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["3"])

        # Logo
        self._brand_row(card_layout, t("invoice_editor.logo"), self._logo_path,
                         self._browse_logo, "logo")

        # Company color
        color_row = QWidget()
        color_row_layout = QHBoxLayout(color_row)
        color_row_layout.setContentsMargins(0, 0, 0, 0)
        color_row_layout.setSpacing(S["2"])

        self._color_label = QLabel(t("invoice_editor.company_color"))
        self._color_label.setProperty("fontRole", "label")
        color_row_layout.addWidget(self._color_label)

        self._color_swatch = QFrame()
        self._color_swatch.setFixedSize(24, 24)
        self._color_swatch.setProperty("role", "color-swatch")
        self._color_swatch.setStyleSheet(f"background-color: {self._company_color};")
        color_row_layout.addWidget(self._color_swatch)

        self._color_btn = Btn(color_row, t("invoice_editor.pick_color"),
                                        variant="secondary")
        self._color_btn.setFixedWidth(80)
        self._color_btn.clicked.connect(self._pick_color)
        color_row_layout.addWidget(self._color_btn)
        color_row_layout.addStretch()

        card_layout.addWidget(color_row)

        # Signature
        self._brand_row(card_layout, t("invoice_editor.signature"), self._signature_path,
                         self._browse_signature, "sig")

        # Stamp
        self._brand_row(card_layout, t("invoice_editor.stamp"), self._stamp_path,
                         self._browse_stamp, "stamp")

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _brand_row(self, parent_layout: QVBoxLayout, label: str,
                   path_value: str, browse_cmd, tag: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

        lbl = QLabel(label)
        lbl.setProperty("fontRole", "label")
        lbl.setFixedWidth(70)
        if tag == "logo":
            self._logo_label = lbl
        row_layout.addWidget(lbl)

        entry = StyledLineEdit(text=path_value, height=28)
        entry.setReadOnly(True)
        setattr(self, f"_{tag}_entry", entry)
        row_layout.addWidget(entry, 1)

        btn = Btn(row, t("invoice_editor.browse"), variant="ghost")
        btn.setFixedWidth(80)
        btn.clicked.connect(browse_cmd)
        setattr(self, f"_browse_{tag}_btn", btn)
        row_layout.addWidget(btn)

        parent_layout.addWidget(row)

    def _browse_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("invoice_editor.select_logo"),
            "",
            t("file_filter.images") + " (*.png *.jpg *.jpeg *.bmp *.gif);;" +
            t("file_filter.all") + " (*.*)",
        )
        if path:
            self._logo_path = path
            self._logo_entry.setText(path)
            self._update_logo_preview(path)

    def _browse_signature(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("invoice_editor.select_signature"),
            "",
            t("file_filter.images") + " (*.png *.jpg *.jpeg *.bmp);;" +
            t("file_filter.all") + " (*.*)",
        )
        if path:
            self._signature_path = path
            self._sig_entry.setText(path)

    def _browse_stamp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("invoice_editor.select_stamp"),
            "",
            t("file_filter.images") + " (*.png *.jpg *.jpeg *.bmp);;" +
            t("file_filter.all") + " (*.*)",
        )
        if path:
            self._stamp_path = path
            self._stamp_entry.setText(path)

    def _update_logo_preview(self, path: str) -> None:
        """Update the canvas logo area to show the selected logo filename."""
        pass  # Preview is handled by the canvas label system

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(
            initial=self._company_color if hasattr(self, '_company_color') else COLORS["accent"],
            parent=self,
            title=t("invoice_editor.pick_color_title"),
        )
        if color and color.isValid():
            hex_color = color.name()
            self._company_color = hex_color
            self._color_swatch.setStyleSheet(f"background-color: {hex_color};")

    # ── Notes Section ───────────────────────────────────────────────────────

    def _build_notes_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionTitle(container, t("invoice_editor.notes_section"))
        layout.addWidget(header)

        card = self._make_card()
        card_layout = card.layout()
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["2"])

        self._notes_label = QLabel(t("invoice_editor.notes"))
        self._notes_label.setProperty("fontRole", "label")
        card_layout.addWidget(self._notes_label)

        self._notes_edit = StyledTextEdit(height=80)
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        card_layout.addWidget(self._notes_edit)

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _on_notes_changed(self) -> None:
        self._notes = self._notes_edit.toPlainText()

    # ── Bottom Bar ──────────────────────────────────────────────────────────

    def _build_bottom_bar(self) -> None:
        self._bottom_bar = QFrame(self)
        self._bottom_bar.setProperty("role", "bottom-bar")
        self._bottom_bar.setFixedHeight(52)

        layout = QHBoxLayout(self._bottom_bar)
        layout.setContentsMargins(S["4"], S["2"], S["4"], S["2"])
        layout.setSpacing(S["2"])

        actions = [
            ("\U0001F50D " + t("invoice_editor.preview_pdf"), self._preview_pdf, "secondary"),
            ("\U0001F4C4 " + t("invoice_editor.generate_pdf"), self._generate_pdf, "primary"),
            ("\U0001F5A8 " + t("invoice_editor.print"), self._print_invoice, "secondary"),
            ("\U0001F4E7 " + t("invoice_editor.email"), self._email_invoice, "primary"),
            ("\U0001F4BE " + t("invoice_editor.save_draft"), self._save_draft, "secondary"),
            ("\U0001F4C2 " + t("invoice_editor.load_draft"), self._load_draft, "secondary"),
            ("\U0001F4C4 " + t("invoice_editor.export_json"), self._on_export_json, "ghost"),
        ]

        self._preview_btn = Btn(self._bottom_bar, actions[0][0],
                                          command=actions[0][1], variant=actions[0][2])
        layout.addWidget(self._preview_btn)

        self._generate_btn = Btn(self._bottom_bar, actions[1][0],
                                           command=actions[1][1], variant=actions[1][2])
        layout.addWidget(self._generate_btn)

        self._print_btn = Btn(self._bottom_bar, actions[2][0],
                                        command=actions[2][1], variant=actions[2][2])
        layout.addWidget(self._print_btn)

        self._email_btn = Btn(self._bottom_bar, actions[3][0],
                                        command=actions[3][1], variant=actions[3][2])
        layout.addWidget(self._email_btn)

        self._save_draft_btn = Btn(self._bottom_bar, actions[4][0],
                                             command=actions[4][1], variant=actions[4][2])
        layout.addWidget(self._save_draft_btn)

        self._load_draft_btn = Btn(self._bottom_bar, actions[5][0],
                                             command=actions[5][1], variant=actions[5][2])
        layout.addWidget(self._load_draft_btn)

        self._export_json_btn = Btn(self._bottom_bar, actions[6][0],
                                             command=actions[6][1], variant=actions[6][2])
        layout.addWidget(self._export_json_btn)

        layout.addStretch()

    # ══════════════════════════════════════════════════════════════════════════
    # DATA LOADING
    # ══════════════════════════════════════════════════════════════════════════

    def _load_company_config(self) -> None:
        conf = load_company_config()
        self._company_name = conf.get("company_name", "")
        self._company_cui = conf.get("cui", "")
        self._company_reg = conf.get("reg_number", "")
        self._company_address = conf.get("address", "")
        self._company_phone = conf.get("phone", "")
        self._company_email = conf.get("email", "")
        # Branding defaults
        logo = conf.get("logo_path", "")
        if logo:
            self._logo_path = logo
            if hasattr(self, '_logo_entry'):
                self._logo_entry.setText(logo)
        color = conf.get("company_color", COLORS["accent"])
        if color:
            self._company_color = color
            if hasattr(self, '_color_swatch'):
                self._color_swatch.setStyleSheet(f"background-color: {color};")
        sig = conf.get("signature_path", "")
        if sig:
            self._signature_path = sig
            if hasattr(self, '_sig_entry'):
                self._sig_entry.setText(sig)
        stamp = conf.get("stamp_path", "")
        if stamp:
            self._stamp_path = stamp
            if hasattr(self, '_stamp_entry'):
                self._stamp_entry.setText(stamp)
        self._update_canvas_labels()

    def _load_clients(self) -> None:
        """Load clients via ClientService (delegates to repository internally)."""
        if not self._client_service:
            return
        try:
            self._clients = self._client_service.get_all()
            self._client_map = {c["name"]: c for c in self._clients}
            names = list(self._client_map.keys())
            self._client_combo.blockSignals(True)
            self._client_combo.clear()
            self._client_combo.addItems(names)
            self._client_combo.blockSignals(False)
        except Exception as e:
            _logger.warning("Could not load clients: %s", e)

    def _load_trips(self) -> None:
        if not self._trip_service:
            return
        try:
            trips = self._trip_service.get_all()
            self._trips = trips
            self._trip_map = {}
            labels = []
            for trip in trips:
                label = t("invoice.trip_list_format").format(
                    id=trip["id"],
                    truck_number=trip.get("truck_number", ""),
                    client_name=trip.get("client_name", ""),
                    created_at=trip.get("created_at", "")[:10] if trip.get("created_at") else "",
                )
                self._trip_map[label] = trip
                labels.append(label)
            self._trip_combo.blockSignals(True)
            self._trip_combo.clear()
            self._trip_combo.addItems(labels)
            self._trip_combo.blockSignals(False)
        except Exception as e:
            _logger.warning("Could not load trips: %s", e)

    def _refresh_all(self) -> None:
        self._load_clients()
        self._load_trips()

    # ══════════════════════════════════════════════════════════════════════════
    # CLIENT / TRIP SELECTION
    # ══════════════════════════════════════════════════════════════════════════

    def _on_client_selected(self, choice: str) -> None:
        if not choice or choice not in self._client_map:
            self._selected_client_id = None
            return
        client = self._client_map[choice]
        self._selected_client_id = client["id"]
        self._client_name = client.get("name", "")
        self._client_vat = client.get("vat_number", "")
        self._client_address = client.get("address", "")
        self._client_phone = client.get("phone", "")
        self._client_email = client.get("email", "")
        self._update_canvas_labels()

    def _on_trip_selected(self, choice: str) -> None:
        if not choice or choice not in self._trip_map:
            self._selected_trip_id = None
            self._selected_trip_data = None
            return
        trip = self._trip_map[choice]
        self._selected_trip_id = trip["id"]
        self._selected_trip_data = trip
        self._auto_fill_from_trip()

    def _auto_fill_from_trip(self) -> None:
        """Fill invoice fields from selected trip data and route stops.

        Trip data is already sourced through ``TripService`` (see ``_load_trips``)
        so this method operates on service-retrieved data.  The price/VAT fields
        (``total_price_eur``, ``price_pre_vat``, ``vat_percent``) are business
        values managed by the trip domain; extracting them here is a UI-to-state
        mapping rather than a computation.
        """
        trip = self._selected_trip_data
        if not trip:
            return

        # Trip details — update both the internal state and the
        # visible text boxes so the user immediately sees the
        # auto-filled values.  Internal state is updated *before*
        # the widget so the test assertion ``state == widget_text``
        # holds even though we block signals (the textChanged
        # handler is what would normally keep the state in sync).
        truck_plate = trip.get("truck_number", "") or ""
        driver_name = trip.get("driver_name", "") or ""
        dist = trip.get("distance_km", 0) or 0
        distance_text = f"{float(dist):,.1f} km" if dist else ""
        self._truck_plate = truck_plate
        self._driver_name = driver_name
        self._distance = distance_text
        self._set_text(self._truck_plate_edit, truck_plate)
        self._set_text(self._driver_name_edit, driver_name)
        self._set_text(self._distance_edit, distance_text)

        # Fetch route stops
        route_id = trip.get("route_history_v2_id")
        if route_id:
            self._fill_cities_from_route(route_id)

        # Auto-set dates from trip
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        if start:
            self._issue_date = start[:10] if len(start) >= 10 else start
            self._set_text(self._issue_date_edit, self._issue_date)
        if end:
            try:
                dt = datetime.strptime(end[:10], "%Y-%m-%d")
                self._due_date = (dt + timedelta(days=30)).strftime("%Y-%m-%d")
            except ValueError:
                pass
            self._set_text(self._due_date_edit, self._due_date)

        # Auto-fill description from trip.  Use the rendered template
        # even when ``dist`` is 0 so the user gets a sensible default
        # (the prior implementation skipped this branch when
        # ``dist <= 0`` which left the description empty for trips
        # without a recorded distance).
        current_desc = self._description.strip()
        if not current_desc:
            self._description = t("invoice_pdf.service_desc").format(float(dist))
            self._set_plain_text(self._desc_text_edit, self._description)

        # Set trip base price
        price = round(float(trip.get("total_price_eur", 0) or 0), 2)
        self._trip_base_price = f"{price:.2f}"

        # Handle VAT if present on trip
        pre_vat = trip.get("price_pre_vat")
        vat_pct = trip.get("vat_percent")
        if pre_vat is not None and vat_pct is not None:
            self._trip_price_pre_vat = str(pre_vat)
            self._trip_vat_percent = str(vat_pct)

        # Only reset addon items if all are empty/default to avoid losing custom entries
        if all(
            not item.get("description", "").strip() and float(item.get("amount", 0) or 0) == 0
            for item in self._addon_items
        ):
            self._addon_items = [{"description": "", "amount": 0.0}]
        self._sync_table_to_items()

        # Auto-select client — always update to match the current trip's client
        client_name = trip.get("client_name", "")
        if client_name and client_name in self._client_map:
            self._selected_client_id = None
            self._client_combo.setCurrentText(client_name)
            # on_client_selected is triggered by setCurrentText via signal

        self._update_canvas_labels()
        self._recalc_all()

    def _fill_cities_from_route(self, route_id: int) -> None:
        """Extract loading/unloading cities from route stops JSON."""
        if not self.db:
            return
        try:
            stops_json = self._trip_service.get_route_stops_json(route_id) if self._trip_service else None
            if not stops_json:
                return
            stops = json.loads(stops_json)
            if not isinstance(stops, list) or len(stops) < 2:
                return
            origin = stops[0].get("address", "")
            destination = stops[-1].get("address", "")
            if origin and self._loading_stops:
                self._loading_stops[0]["value"] = origin
            if destination and self._unloading_stops:
                self._unloading_stops[0]["value"] = destination
            self._rebuild_stops_ui()
        except Exception:
            pass

    def _auto_fill_all(self) -> None:
        """Manual auto-fill trigger."""
        choice = self._client_combo.currentText()
        if choice and choice in self._client_map:
            self._on_client_selected(choice)
        choice = self._trip_combo.currentText()
        if choice and choice in self._trip_map:
            self._on_trip_selected(choice)

    def _on_mode_changed(self, mode: str, checked: bool) -> None:
        if mode == "client":
            if checked:
                self._is_client_invoice = True
                self._is_internal_invoice = False
                self._cb_internal.blockSignals(True)
                self._cb_internal.setChecked(False)
                self._cb_internal.blockSignals(False)
        else:
            if checked:
                self._is_internal_invoice = True
                self._is_client_invoice = False
                self._cb_client.blockSignals(True)
                self._cb_client.setChecked(False)
                self._cb_client.blockSignals(False)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPANY EDITOR
    # ══════════════════════════════════════════════════════════════════════════

    def _open_company_editor(self) -> None:
        dlg = CompanyEditorQtDialog(
            self,
            company_name=self._company_name,
            cui=self._company_cui,
            reg=self._company_reg,
            address=self._company_address,
            phone=self._company_phone,
            email=self._company_email,
            on_save=self._save_company_data,
        )
        dlg.exec_()

    def _save_company_data(self, data: dict[str, str]) -> None:
        self._company_name = data["company_name"]
        self._company_cui = data["cui"]
        self._company_reg = data["reg_number"]
        self._company_address = data["address"]
        self._company_phone = data["phone"]
        self._company_email = data["email"]
        save_company_config(data)
        self._update_canvas_labels()
        QMessageBox.information(self, t("invoice.success_save_company"),
                                t("invoice.success_save_company"))

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS — PDF / Email / Draft
    # ══════════════════════════════════════════════════════════════════════════

    def _collect_invoice_data(self) -> dict[str, Any]:
        """Collect all invoice data into a dict for PDF generation."""
        conf = {
            "company_name": self._company_name,
            "cui": self._company_cui,
            "reg_number": self._company_reg,
            "address": self._company_address,
            "phone": self._company_phone,
            "email": self._company_email,
        }

        client = {
            "name": self._client_name,
            "vat_number": self._client_vat,
            "address": self._client_address,
            "phone": self._client_phone,
            "email": self._client_email,
        }

        addon_items = []
        for item in self._addon_items:
            addon_items.append({
                "description": item.get("description", ""),
                "amount": item.get("amount", 0),
            })

        # Delegate arithmetic to shared _calculate_totals()
        calc = self._calculate_totals()
        subtotal = calc["subtotal"]
        total_tax = calc["total_tax"]
        discount = calc["discount"]
        grand_total = calc["grand_total"]
        tax_rate = calc["tax_rate"]
        disc_val = calc["disc_value"]
        trip_price = calc["trip_price"]
        addon_total = round(subtotal - trip_price, 2)  # reverse-compute for the data dict

        mode = "internal" if self._is_internal_invoice else "client"

        description = self._description

        # Pre/post VAT from trip if available
        price_pre_vat = self._trip_price_pre_vat if self._trip_price_pre_vat else None
        vat_percent = self._trip_vat_percent if self._trip_vat_percent else None

        return {
            "invoice_number": self._invoice_number,
            "issue_date": self._issue_date,
            "due_date": self._due_date,
            "payment_terms": self._payment_terms,
            "currency": self._currency,
            "branch": self._branch,
            "_format_key": self._format_key,
            "company": conf,
            "client": client,
            "addon_items": addon_items,
            "trip_price": trip_price,
            "addon_total": addon_total,
            "description": description,
            "loading_stops": [s["value"] for s in self._loading_stops if s["value"].strip()],
            "unloading_stops": [s["value"] for s in self._unloading_stops if s["value"].strip()],
            "truck_plate": self._truck_plate,
            "driver_name": self._driver_name,
            "distance": self._distance,
            "tax_rate": tax_rate,
            "discount_type": self._discount_type,
            "discount_value": disc_val,
            "subtotal": subtotal,
            "total_tax": total_tax,
            "discount": discount,
            "grand_total": grand_total,
            "notes": self._notes,
            "logo_path": self._logo_path,
            "signature_path": self._signature_path,
            "stamp_path": self._stamp_path,
            "company_color": self._company_color,
            "trip_id": self._selected_trip_id,
            "trip_data": self._selected_trip_data,
            "mode": mode,
            "client_id": self._selected_client_id,
            "price_pre_vat": price_pre_vat,
            "vat_percent": vat_percent,
            "trip_label": self._trip_combo.currentText() if hasattr(self, "_trip_combo") else "",
        }

    def _preview_pdf(self) -> None:
        """Generate PDF silently and open for preview."""
        data = self._collect_invoice_data()
        try:
            path = self._generate_rich_pdf(data, open_after=True, record=False)
            if path and os.path.exists(path):
                os.startfile(path)
        except Exception as e:
            _logger.error("Preview failed: %s", e, exc_info=True)
            QMessageBox.critical(self, t("invoice.error_generate").format(""), str(e))

    def _generate_pdf(self) -> None:
        """Generate PDF invoice and record it."""
        data = self._collect_invoice_data()

        # Inline validation
        all_widgets = self._all_inputs() if hasattr(self, "_all_inputs") else []
        errors: list[str] = []
        invalid_fields: list[QWidget] = []

        if not data["company"]["company_name"] or not data["company"]["cui"]:
            errors.append(t("invoice.warning_fields_msg"))
            if hasattr(self, "_company_name_label"):
                invalid_fields.append(self._company_name_label)

        if errors:
            if all_widgets:
                from utils.editor_toolkit import highlight_invalid_fields, mark_field_invalid
                highlight_invalid_fields(all_widgets)
                for w in invalid_fields:
                    mark_field_invalid(w)
            QMessageBox.warning(self, t("invoice.warning_fields_title"),
                                "\n".join(errors))
            return

        try:
            path = self._generate_rich_pdf(data, open_after=True, record=True)
            if path and os.path.exists(path):
                QMessageBox.information(self, t("invoice.success_save_company"),
                                        t("invoice_editor.invoice_generated").format(path))
            else:
                raise FileNotFoundError(f"Invoice PDF not found: {path}")
        except Exception as e:
            _logger.error("Generation failed: %s", e, exc_info=True)
            QMessageBox.critical(self, t("invoice.error_generate").format(""), str(e))

    def _generate_rich_pdf(self, data: dict[str, Any], open_after: bool = False,
                           record: bool = True) -> str | None:
        """Generate a rich PDF via InvoiceService (delegates to InvoiceGenerator internally)."""
        svc = self._get_invoice_service()
        path = svc.generator.generate_rich(data)

        if record and path and os.path.exists(path):
            trip_data = data.get("trip_data") or {}
            trip_id = data.get("trip_id") or trip_data.get("id", 0)
            if trip_id:
                self._get_invoice_service().create_record(
                    trip_id=trip_id,
                    inv_number=data["invoice_number"],
                    amount=data["grand_total"],
                    due_date=data["due_date"],
                )
                from services.operations.event_bus import INVOICE_CREATED
                self._event_bus.publish(INVOICE_CREATED, {
                    "trip_id": trip_id,
                    "invoice_number": data["invoice_number"],
                    "amount": data["grand_total"],
                    "due_date": data["due_date"],
                })
            # Register in Document Center
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ent_id = trip_id if trip_id else 0
                ds.register_existing(
                    file_path=path,
                    title=f"Invoice {os.path.basename(path)}",
                    category="invoices",
                    entity_type="trip",
                    entity_id=ent_id,
                    tags=["invoice", "generated"],
                )
            except Exception:
                _logger.warning("Document Center registration skipped", exc_info=True)

        return path

    def _print_invoice(self) -> None:
        """Print the invoice PDF."""
        data = self._collect_invoice_data()
        try:
            path = self._generate_rich_pdf(data, record=False)
            if path and os.path.exists(path):
                os.startfile(path, "print")
        except Exception as e:
            _logger.error("Print failed: %s", e, exc_info=True)
            QMessageBox.critical(self, t("invoice.error_generate").format(""), str(e))

    def _email_invoice(self) -> None:
        """Email the invoice using configured SMTP."""
        data = self._collect_invoice_data()
        recipient = data["client"].get("email", "") or self._company_email

        if not recipient:
            result, ok = QInputDialog.getText(
                self,
                t("invoice_editor.email_to"),
                t("invoice_editor.enter_email"),
            )
            if not ok or not result:
                return
            recipient = result

        try:
            path = self._generate_rich_pdf(data, record=True)
            if not path or not os.path.exists(path):
                raise FileNotFoundError(f"Invoice PDF not found: {path}")

            smtp_config = self.prefs.get_smtp_config() if self.prefs else {}
            if not smtp_config or not smtp_config.get("smtp_server"):
                QMessageBox.warning(self, t("email.config_missing"),
                                    t("email.config_missing"))
                return

            from services.operations.notification_center import NotificationCenter
            nc = NotificationCenter(self.db)
            nc.configure_smtp(
                smtp_config.get("smtp_server", ""),
                int(smtp_config.get("smtp_port", "587")),
                smtp_config.get("smtp_user", ""),
                smtp_config.get("smtp_password", ""),
            )

            filename = os.path.basename(path)
            subject = t("email.invoice_subject").format(
                filename=filename,
                client=data["client"].get("name", t("invoice.default_client")),
            )
            body = t("email.invoice_body").format(
                trip_id=data.get("trip_id", 0),
                company=data["company"].get("company_name", ""),
            )

            if nc.send_email(recipient, subject, body, attachments=[path]):
                from services.operations.event_bus import INVOICE_EMAILED
                self._event_bus.publish(INVOICE_EMAILED, {
                    "trip_id": data.get("trip_id", 0),
                    "invoice_number": filename.replace(".pdf", ""),
                    "recipient": recipient,
                })
                QMessageBox.information(self, t("invoice.button_email"),
                                        t("invoice.email_success").format(recipient))
            else:
                QMessageBox.critical(self, t("invoice.email_failed"),
                                     t("invoice.email_failed").format(data.get("trip_id", 0)))
        except Exception as e:
            _logger.error("Email failed: %s", e, exc_info=True)
            QMessageBox.critical(self, t("invoice.error_generate").format(""), str(e))

    # ══════════════════════════════════════════════════════════════════════════
    # EXPORT / JSON
    # ══════════════════════════════════════════════════════════════════════════

    def _all_inputs(self) -> list[QWidget]:
        """Return all form input widgets for validation highlighting."""
        result: list[QWidget] = []
        for attr in [
            "_client_combo", "_trip_combo",
            "_inv_num_edit", "_issue_date_edit", "_due_date_edit",
            "_payment_terms_edit", "_desc_text_edit",
            "_truck_plate_edit", "_driver_name_edit", "_distance_edit",
            "_tax_combo", "_disc_type_combo", "_disc_entry", "_curr_combo",
            "_notes_edit",
        ]:
            w = getattr(self, attr, None)
            if w is not None:
                result.append(w)
        return result

    def _on_export_json(self) -> None:
        """Export invoice data as JSON."""
        data = self._collect_invoice_data()
        default_name = f"invoice_{data.get('invoice_number', 'draft')}.json"
        export_editor_data(
            self,
            data,
            t("invoice_editor.export_json"),
            default_name,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # DRAFT SYSTEM
    # ══════════════════════════════════════════════════════════════════════════

    def _save_draft(self) -> None:
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        data = self._collect_invoice_data()
        data.pop("trip_data", None)
        data["saved_at"] = datetime.now().isoformat()

        name, ok = QInputDialog.getText(
            self,
            t("invoice_editor.save_draft"),
            t("invoice_editor.draft_name"),
        )
        if not ok or not name:
            return

        safe_name = "".join(c for c in name if c.isalnum() or c in " _-")
        if not safe_name:
            safe_name = f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        filepath = os.path.join(DRAFTS_DIR, f"{safe_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        QMessageBox.information(self, t("invoice_editor.draft_saved"),
                                t("invoice_editor.draft_saved_msg").format(name))

    def _load_draft(self) -> None:
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        drafts = [f for f in os.listdir(DRAFTS_DIR) if f.endswith(".json")]
        if not drafts:
            QMessageBox.information(self, t("invoice_editor.load_draft"),
                                    t("invoice_editor.no_drafts"))
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            t("invoice_editor.load_draft"),
            DRAFTS_DIR,
            "JSON (*.json)",
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            self._invoice_number = data.get("invoice_number", self._gen_invoice_number())
            self._issue_date = data.get("issue_date", datetime.now().strftime("%Y-%m-%d"))
            self._due_date = data.get("due_date", "")
            self._payment_terms = data.get("payment_terms", "Net 30")
            self._currency = data.get("currency", "EUR")
            self._tax_rate = str(data.get("tax_rate", 19))
            self._discount_type = data.get("discount_type", t("invoice_editor.discount_percentage"))
            self._discount_value = str(data.get("discount_value", 0))
            self._branch = data.get("branch", "")

            # Company
            c = data.get("company", {})
            self._company_name = c.get("company_name", "")
            self._company_cui = c.get("cui", "")
            self._company_reg = c.get("reg_number", "")
            self._company_address = c.get("address", "")
            self._company_phone = c.get("phone", "")
            self._company_email = c.get("email", "")

            # Client
            cl = data.get("client", {})
            self._client_name = cl.get("name", "")
            self._client_vat = cl.get("vat_number", "")
            self._client_address = cl.get("address", "")
            self._client_phone = cl.get("phone", "")
            self._client_email = cl.get("email", "")

            # Addon items
            self._addon_items = []
            addons = data.get("addon_items") or []
            if not addons:
                for li in data.get("line_items", []):
                    self._addon_items.append({
                        "description": li.get("description", ""),
                        "amount": li.get("total", li.get("amount", 0)),
                    })
            else:
                for ai in addons:
                    self._addon_items.append({
                        "description": ai.get("description", ""),
                        "amount": ai.get("amount", 0),
                    })
            if not self._addon_items:
                self._addon_items = [{"description": "", "amount": 0.0}]
            self._sync_table_to_items()

            # Trip base price
            self._trip_base_price = data.get("trip_price", "0.00")
            if data.get("price_pre_vat"):
                self._trip_price_pre_vat = str(data["price_pre_vat"])
            if data.get("vat_percent"):
                self._trip_vat_percent = str(data["vat_percent"])

            # Mode
            mode = data.get("mode", "client")
            if mode == "internal":
                self._is_internal_invoice = True
                self._is_client_invoice = False
                self._cb_internal.setChecked(True)
                self._cb_client.setChecked(False)
            else:
                self._is_client_invoice = True
                self._is_internal_invoice = False
                self._cb_client.setChecked(True)
                self._cb_internal.setChecked(False)

            # Description
            self._description = data.get("description", "")
            self._desc_text_edit.setPlainText(self._description)

            # Trip details
            self._truck_plate = data.get("truck_plate", "")
            self._driver_name = data.get("driver_name", "")
            self._distance = data.get("distance", "")

            # Stops
            load_stops = data.get("loading_stops") or []
            if not load_stops and data.get("loading_city"):
                load_stops = [data["loading_city"]]
            if load_stops:
                self._loading_stops = [{"value": v} for v in load_stops]

            unload_stops = data.get("unloading_stops") or []
            if not unload_stops and data.get("unloading_city"):
                unload_stops = [data["unloading_city"]]
            if unload_stops:
                self._unloading_stops = [{"value": v} for v in unload_stops]

            if not self._loading_stops:
                self._loading_stops = [{"value": ""}]
            if not self._unloading_stops:
                self._unloading_stops = [{"value": ""}]
            self._rebuild_stops_ui()

            # Notes
            self._notes = data.get("notes", "")
            self._notes_edit.setPlainText(self._notes)

            # Branding
            self._logo_path = data.get("logo_path", "")
            if hasattr(self, '_logo_entry'):
                self._logo_entry.setText(self._logo_path)
            self._signature_path = data.get("signature_path", "")
            if hasattr(self, '_sig_entry'):
                self._sig_entry.setText(self._signature_path)
            self._stamp_path = data.get("stamp_path", "")
            if hasattr(self, '_stamp_entry'):
                self._stamp_entry.setText(self._stamp_path)
            self._company_color = data.get("company_color", COLORS["accent"])
            if hasattr(self, '_color_swatch'):
                self._color_swatch.setStyleSheet(f"background-color: {self._company_color};")

            # Sync combo boxes and preview labels
            self._tax_combo.setCurrentText(self._tax_rate)
            self._curr_combo.setCurrentText(self._currency)
            self._disc_entry.setText(self._discount_value)
            self._branch_entry.setText(self._branch)

            # Try to re-select client/trip
            client_name = cl.get("name", "")
            if client_name and client_name in self._client_map:
                self._client_combo.setCurrentText(client_name)
                # Signal will fire _on_client_selected

            # Restore selected trip ID from loaded data
            loaded_trip_id = data.get("trip_id")
            if loaded_trip_id is not None:
                self._selected_trip_id = int(loaded_trip_id)
                self._selected_trip_data = data.get("trip_data")
            # Also try to match by trip combo text if trip data has client context
            trip_label = data.get("trip_label", "")
            if trip_label and trip_label in self._trip_map:
                self._trip_combo.setCurrentText(trip_label)
                # Signal will fire _on_trip_selected

            self._update_canvas_labels()
            self._recalc_all()

            QMessageBox.information(self, t("invoice_editor.draft_loaded"),
                                    t("invoice_editor.draft_loaded_msg").format(
                                        os.path.basename(path)))
        except Exception as e:
            _logger.error("Failed to load draft: %s", e, exc_info=True)
            QMessageBox.critical(self, t("invoice.error_generate").format(""), str(e))


# ──────────────────────────────────────────────────────────────────────────────
# CompanyEditorQtDialog
# ──────────────────────────────────────────────────────────────────────────────


class CompanyEditorQtDialog(QDialog):
    """Qt dialog for editing company info."""

    def __init__(
        self,
        parent: QWidget | None = None,
        company_name: str = "",
        cui: str = "",
        reg: str = "",
        address: str = "",
        phone: str = "",
        email: str = "",
        on_save=None,
    ):
        super().__init__(parent)
        self._on_save = on_save
        self.setWindowTitle(t("invoice.section_company"))
        self.resize(480, 440)
        self.setMinimumSize(400, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["6"], S["6"], S["6"], S["6"])
        layout.setSpacing(S["4"])

        header = QLabel(t("invoice.section_company"))
        header.setProperty("fontRole", "h2")
        layout.addWidget(header)

        # Content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(S["2"])

        fields = [
            (t("invoice.field_company_name"), "name", company_name),
            (t("invoice.field_cui"), "cui", cui),
            (t("invoice.field_reg_number"), "reg", reg),
            (t("invoice.field_address"), "addr", address),
            (t("invoice.field_phone"), "phone", phone),
            (t("invoice.field_email"), "email", email),
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

        # Buttons
        btn_frame = QWidget()
        btn_frame_layout = QHBoxLayout(btn_frame)
        btn_frame_layout.setContentsMargins(0, 0, 0, 0)
        btn_frame_layout.setSpacing(S["2"])

        save_btn = Btn(btn_frame, t("invoice.save_company"),
                                 variant="primary")
        save_btn.clicked.connect(self._save_and_close)
        btn_frame_layout.addWidget(save_btn)

        cancel_btn = Btn(btn_frame, t("invoice_editor.cancel"),
                                   variant="ghost")
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
        if self._on_save:
            self._on_save(data)
        self.accept()


# ──────────────────────────────────────────────────────────────────────────────
# InvoiceEditorDialog (standalone QDialog wrapper)
# ──────────────────────────────────────────────────────────────────────────────


class InvoiceEditorDialog(QDialog):
    """Standalone QDialog that wraps a QtInvoiceEditor.

    Usage::

        dlg = InvoiceEditorDialog(db, prefs=prefs, parent=parent_widget)
        if dlg.exec_():
            ...
    """

    def __init__(
        self,
        db=None,
        prefs: PreferencesManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(t("invoice_editor.title"))
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._editor = QtInvoiceEditor(self, db=db, prefs=prefs)
        layout.addWidget(self._editor)

        self._editor.wakeup()

    def closeEvent(self, event) -> None:
        self._editor.shutdown()
        super().closeEvent(event)
