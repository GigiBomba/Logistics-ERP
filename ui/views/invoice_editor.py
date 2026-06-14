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
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QColorDialog,
    QFileDialog,
    QInputDialog,
    QAbstractItemView,
)

from services.i18n import t, register_listener, unregister_listener
from services.app_state import AppState
from services.invoicing.config_manager import load_company_config, save_company_config
from services.invoicing.service import InvoiceService
from services.trip_service import TripService
from repositories.client_repository import ClientRepository
from services.operations.event_bus import EventBus, SETTINGS_UPDATED
from services.preferences import PreferencesManager
from ui.theme import COLORS, S
from ui.widgets import (
    ActionButton,
    StyledLineEdit,
    StyledComboBox,
    StyledTextEdit,
    StyledCheckBox,
    StyledTableWidget,
    ScrollableFormContainer,
    SectionHeader,
    field,
)

_logger = logging.getLogger(__name__)

DRAFTS_DIR = os.path.join("data", "invoice_drafts")


# ──────────────────────────────────────────────────────────────────────────────
# QtInvoiceEditor
# ──────────────────────────────────────────────────────────────────────────────


class QtInvoiceEditor(QWidget):
    """Professional invoice editor with live preview.

    This is a QWidget for embedding in tab views. It uses ``ScrollableFormContainer``
    for the main form area and provides section cards for client info, invoice details,
    line items, and totals.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs: Optional[PreferencesManager] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs or (PreferencesManager(db) if db else None)
        self._trip_service = TripService(db) if db else None
        self._client_repo = ClientRepository(db) if db else None
        self._invoice_service: Optional[InvoiceService] = None  # lazy
        self._app_state = AppState()
        self._event_bus = EventBus()

        # ── Data state ────────────────────────────────────────────────────────
        self._clients: List[Dict[str, Any]] = []
        self._client_map: Dict[str, Dict[str, Any]] = {}
        self._trips: List[Dict[str, Any]] = []
        self._trip_map: Dict[str, Dict[str, Any]] = {}

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
        self._addon_items: List[Dict[str, Any]] = []

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
        self._loading_stops: List[Dict[str, str]] = [{"value": ""}]
        self._unloading_stops: List[Dict[str, str]] = [{"value": ""}]

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
        self._selected_client_id: Optional[int] = None

        # Company info
        self._company_name: str = ""
        self._company_cui: str = ""
        self._company_reg: str = ""
        self._company_address: str = ""
        self._company_phone: str = ""
        self._company_email: str = ""

        # Selected trip
        self._selected_trip_id: Optional[int] = None
        self._selected_trip_data: Optional[Dict[str, Any]] = None

        # i18n
        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        # ── Build UI ─────────────────────────────────────────────────────────
        self._build_ui()
        self._load_company_config()
        self._add_default_addon_item()

        self._data_loaded: bool = False
        self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)

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
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        try:
            self._event_bus.unsubscribe(SETTINGS_UPDATED, self._on_settings_updated)
        except Exception:
            pass

    def _on_language_changed(self, _lang: str) -> None:
        """Refresh UI text when language changes."""
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        """Update all translatable labels and headers."""
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
        self._scroll = ScrollableFormContainer(self, max_width=1000)
        main_layout.addWidget(self._scroll, 1)

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
        self._client_label = QLabel(t("invoice_editor.select_client"))
        self._client_label.setProperty("fontRole", "label")
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
        self._auto_btn = ActionButton(self._top_bar, t("invoice_editor.auto_fill"),
                                       variant="primary", width=90)
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
        self._refresh_btn = ActionButton(self._top_bar, "\U0001F504",
                                          variant="ghost", width=34)
        self._refresh_btn.clicked.connect(self._refresh_all)
        layout.addWidget(self._refresh_btn)

        layout.addStretch()

    # ── Client Section (From / Bill To) ──────────────────────────────────────

    def _build_client_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        # Section header
        header = SectionHeader(container, t("invoice_editor.client_info").upper())
        layout.addWidget(header)

        # Two-column: From / Bill To
        cols = QWidget()
        cols_layout = QHBoxLayout(cols)
        cols_layout.setContentsMargins(0, 0, 0, 0)
        cols_layout.setSpacing(S["4"])

        # ── From (Company) ────────────────────────────────────────────────
        from_card = self._make_card()
        from_layout = QVBoxLayout(from_card)
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

        edit_company_btn = QPushButton("\u270F")
        edit_company_btn.setFixedSize(28, 28)
        edit_company_btn.setProperty("variant", "ghost")
        edit_company_btn.clicked.connect(self._open_company_editor)
        from_layout.addWidget(edit_company_btn)
        from_layout.addStretch()

        cols_layout.addWidget(from_card)

        # ── Bill To (Client) ──────────────────────────────────────────────
        to_card = self._make_card()
        to_layout = QVBoxLayout(to_card)
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
        card = QFrame()
        card.setProperty("role", "card")
        card.setFrameShape(QFrame.StyledPanel)
        return card

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

        # Description
        self._desc_text_edit.setPlainText(self._description)

        # Notes
        self._notes_edit.setPlainText(self._notes)

    # ── Invoice Details Section ──────────────────────────────────────────────

    def _build_invoice_details_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionHeader(container, t("invoice_editor.invoice_details").upper())
        layout.addWidget(header)

        card = self._make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["3"])

        # Two-row grid for invoice metadata
        grid = QWidget()
        grid_layout = QGridLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(S["3"])

        # Row 0: Invoice Number, Issue Date
        inv_num_widget = field(grid, t("invoice_editor.invoice_number"),
                                StyledLineEdit(text=self._invoice_number))
        inv_num_widget.findChild(StyledLineEdit).textChanged.connect(self._on_inv_num_changed)
        grid_layout.addWidget(inv_num_widget, 0, 0)

        issue_widget = field(grid, t("invoice_editor.issue_date"),
                              StyledLineEdit(text=self._issue_date,
                                             placeholder="YYYY-MM-DD"))
        issue_widget.findChild(StyledLineEdit).textChanged.connect(self._on_issue_date_changed)
        grid_layout.addWidget(issue_widget, 0, 1)

        # Row 1: Due Date, Payment Terms
        due_widget = field(grid, t("invoice_editor.due_date"),
                            StyledLineEdit(text=self._due_date,
                                           placeholder="YYYY-MM-DD"))
        due_widget.findChild(StyledLineEdit).textChanged.connect(self._on_due_date_changed)
        grid_layout.addWidget(due_widget, 1, 0)

        terms_widget = field(grid, t("invoice_editor.payment_terms"),
                              StyledLineEdit(text=self._payment_terms))
        terms_widget.findChild(StyledLineEdit).textChanged.connect(self._on_payment_terms_changed)
        grid_layout.addWidget(terms_widget, 1, 1)

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

    def _on_description_changed(self) -> None:
        self._description = self._desc_text_edit.toPlainText()

    # ── Trip Details Section ────────────────────────────────────────────────

    def _build_trip_details_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionHeader(container, t("invoice_editor.trip_details").upper())
        layout.addWidget(header)

        card = self._make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["3"])

        # Vehicle info row
        trip_grid = QWidget()
        trip_grid_layout = QHBoxLayout(trip_grid)
        trip_grid_layout.setContentsMargins(0, 0, 0, 0)
        trip_grid_layout.setSpacing(S["4"])

        # Truck plate
        plate_w = field(trip_grid, t("invoice_editor.truck_plate"),
                         StyledLineEdit(text=self._truck_plate,
                                        placeholder=t("invoice_editor.truck_plate")))
        plate_w.findChild(StyledLineEdit).textChanged.connect(self._on_truck_plate_changed)
        trip_grid_layout.addWidget(plate_w)

        # Driver
        driver_w = field(trip_grid, t("invoice_editor.driver"),
                          StyledLineEdit(text=self._driver_name,
                                         placeholder=t("invoice_editor.driver")))
        driver_w.findChild(StyledLineEdit).textChanged.connect(self._on_driver_name_changed)
        trip_grid_layout.addWidget(driver_w)

        # Distance
        dist_w = field(trip_grid, t("invoice_editor.distance"),
                        StyledLineEdit(text=self._distance,
                                       placeholder=t("invoice_editor.distance")))
        dist_w.findChild(StyledLineEdit).textChanged.connect(self._on_distance_changed)
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

        for i, stop in enumerate(self._loading_stops):
            self._build_stop_row(i, "loading")

        add_load_btn = ActionButton(
            self._stops_container,
            "+ " + t("invoice_editor.add_loading_stop"),
            variant="ghost",
        )
        add_load_btn.clicked.connect(self._add_loading_stop)
        self._stops_layout.addWidget(add_load_btn)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setProperty("role", "divider")
        sep.setFixedHeight(1)
        self._stops_layout.addWidget(sep)

        # Unloading stops
        unload_label = QLabel(t("invoice_editor.unloading_stops"))
        unload_label.setProperty("fontRole", "label")
        self._stops_layout.addWidget(unload_label)

        for i, stop in enumerate(self._unloading_stops):
            self._build_stop_row(i, "unloading")

        add_unload_btn = ActionButton(
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
            remove_btn = QPushButton("\u2716")
            remove_btn.setFixedSize(22, 22)
            remove_btn.setProperty("variant", "ghost")
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

    # ── Line Items Section ──────────────────────────────────────────────────

    def _build_line_items_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        self._lit_header_label = SectionHeader(container, t("invoice_editor.line_items").upper())
        layout.addWidget(self._lit_header_label)

        card = self._make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["2"])

        # Line items table
        self._items_table = StyledTableWidget(
            parent=card,
            columns=[
                ("idx", "#", 30),
                ("description", t("invoice_editor.description"), 300),
                ("amount", t("invoice_editor.amount"), 100),
            ],
        )
        self._items_table.setMinimumHeight(150)
        self._items_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._items_table.cellChanged.connect(self._on_table_cell_changed)
        card_layout.addWidget(self._items_table)

        # Button row
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(S["2"])

        self._add_row_btn = ActionButton(
            btn_row, "+ " + t("invoice_editor.add_row"), variant="secondary"
        )
        self._add_row_btn.clicked.connect(self._add_addon_row)
        btn_row_layout.addWidget(self._add_row_btn)

        remove_btn = ActionButton(
            btn_row, "\u2716 " + t("invoice_editor.remove_row"), variant="ghost"
        )
        remove_btn.clicked.connect(self._remove_selected_addon)
        btn_row_layout.addWidget(remove_btn)

        btn_row_layout.addStretch()
        card_layout.addWidget(btn_row)

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _sync_table_to_items(self) -> None:
        """Refresh the table widget from ``_addon_items``."""
        self._items_table.blockSignals(True)
        self._items_table.setRowCount(len(self._addon_items))
        for r, item in enumerate(self._addon_items):
            # Index
            idx_item = QTableWidgetItem(str(r + 1))
            idx_item.setFlags(idx_item.flags() & ~Qt.ItemIsEditable)
            self._items_table.setItem(r, 0, idx_item)

            # Description
            desc = item.get("description", "")
            desc_item = QTableWidgetItem(desc)
            self._items_table.setItem(r, 1, desc_item)

            # Amount
            amt = item.get("amount", 0)
            amt_item = QTableWidgetItem(f"{amt:.2f}")
            self._items_table.setItem(r, 2, amt_item)

        self._items_table.blockSignals(False)
        self._recalc_all()

    def _on_table_cell_changed(self, row: int, col: int) -> None:
        if row >= len(self._addon_items):
            return
        item = self._addon_items[row]
        widget_item = self._items_table.item(row, col)
        if widget_item is None:
            return
        text = widget_item.text()
        if col == 1:
            item["description"] = text
        elif col == 2:
            try:
                item["amount"] = round(float(text or "0"), 2)
            except ValueError:
                item["amount"] = 0.0
            # Reformat amount
            self._items_table.blockSignals(True)
            self._items_table.item(row, 2).setText(f"{item['amount']:.2f}")
            self._items_table.blockSignals(False)
        self._recalc_all()

    def _add_addon_row(self, data: Optional[dict] = None) -> None:
        if data is None:
            data = {"description": "", "amount": 0.0}
        self._addon_items.append(data)
        self._sync_table_to_items()

    def _remove_selected_addon(self) -> None:
        row = self._items_table.currentRow()
        if row < 0 or len(self._addon_items) <= 1:
            return
        del self._addon_items[row]
        self._sync_table_to_items()

    def _add_default_addon_item(self) -> None:
        if not self._addon_items:
            self._addon_items = [{"description": "", "amount": 0.0}]
        self._sync_table_to_items()

    # ── Totals Section ──────────────────────────────────────────────────────

    def _build_totals_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        header = SectionHeader(container, t("invoice_editor.totals").upper())
        layout.addWidget(header)

        card = self._make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])
        card_layout.setSpacing(S["3"])

        # Financial controls
        self._financial_header = QLabel(t("invoice_editor.financial_controls").upper())
        self._financial_header.setProperty("fontRole", "section")
        card_layout.addWidget(self._financial_header)

        # Tax rate
        tax_row = QWidget()
        tax_row_layout = QHBoxLayout(tax_row)
        tax_row_layout.setContentsMargins(0, 0, 0, 0)
        tax_row_layout.setSpacing(S["2"])

        self._tax_label = QLabel(t("invoice_editor.tax_rate"))
        self._tax_label.setProperty("fontRole", "label")
        tax_row_layout.addWidget(self._tax_label)

        self._tax_combo = StyledComboBox(values=["0", "5", "9", "19", "20", "21", "24", "25"])
        self._tax_combo.setCurrentText(self._tax_rate)
        self._tax_combo.currentTextChanged.connect(self._on_tax_rate_changed)
        self._tax_combo.setFixedWidth(80)
        tax_row_layout.addWidget(self._tax_combo)

        pct_label = QLabel("%")
        pct_label.setProperty("fontRole", "label")
        tax_row_layout.addWidget(pct_label)
        tax_row_layout.addStretch()

        card_layout.addWidget(tax_row)

        # Discount
        disc_row = QWidget()
        disc_row_layout = QHBoxLayout(disc_row)
        disc_row_layout.setContentsMargins(0, 0, 0, 0)
        disc_row_layout.setSpacing(S["2"])

        self._discount_label = QLabel(t("invoice_editor.discount"))
        self._discount_label.setProperty("fontRole", "label")
        disc_row_layout.addWidget(self._discount_label)

        disc_values = [
            t("invoice_editor.discount_percentage"),
            t("invoice_editor.discount_fixed"),
        ]
        self._disc_type_combo = StyledComboBox(values=disc_values)
        self._disc_type_combo.setCurrentText(disc_values[0])
        self._discount_type = disc_values[0]
        self._disc_type_combo.currentTextChanged.connect(self._on_discount_type_changed)
        self._disc_type_combo.setFixedWidth(100)
        disc_row_layout.addWidget(self._disc_type_combo)

        self._disc_entry = StyledLineEdit(text=self._discount_value, height=32)
        self._disc_entry.setFixedWidth(70)
        self._disc_entry.textChanged.connect(self._on_discount_value_changed)
        disc_row_layout.addWidget(self._disc_entry)

        self._disc_symbol_lbl = QLabel("%")
        self._disc_symbol_lbl.setProperty("fontRole", "label")
        disc_row_layout.addWidget(self._disc_symbol_lbl)
        disc_row_layout.addStretch()

        card_layout.addWidget(disc_row)

        # Currency
        curr_row = QWidget()
        curr_row_layout = QHBoxLayout(curr_row)
        curr_row_layout.setContentsMargins(0, 0, 0, 0)
        curr_row_layout.setSpacing(S["2"])

        self._currency_label = QLabel(t("invoice_editor.currency"))
        self._currency_label.setProperty("fontRole", "label")
        curr_row_layout.addWidget(self._currency_label)

        self._curr_combo = StyledComboBox(values=["EUR", "RON", "USD", "GBP"])
        self._curr_combo.setCurrentText(self._currency)
        self._curr_combo.currentTextChanged.connect(self._on_currency_changed)
        self._curr_combo.setFixedWidth(80)
        curr_row_layout.addWidget(self._curr_combo)
        curr_row_layout.addStretch()

        card_layout.addWidget(curr_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setProperty("role", "divider")
        sep.setFixedHeight(1)
        card_layout.addWidget(sep)

        # Totals display
        self._subtotal_title = QLabel(t("invoice_editor.subtotal"))
        self._subtotal_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._subtotal_title)
        self._subtotal_lbl = QLabel("0.00")
        self._subtotal_lbl.setProperty("fontRole", "body")
        self._subtotal_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._subtotal_lbl)

        self._tax_title = QLabel(t("invoice_editor.tax"))
        self._tax_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._tax_title)
        self._tax_lbl = QLabel("0.00")
        self._tax_lbl.setProperty("fontRole", "body")
        self._tax_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._tax_lbl)

        self._discount_title = QLabel(t("invoice_editor.discount"))
        self._discount_title.setProperty("fontRole", "label")
        card_layout.addWidget(self._discount_title)
        self._discount_lbl = QLabel("0.00")
        self._discount_lbl.setProperty("fontRole", "body")
        self._discount_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._discount_lbl)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setProperty("role", "divider")
        sep2.setFixedHeight(1)
        card_layout.addWidget(sep2)

        self._grand_title = QLabel(t("invoice_editor.grand_total"))
        self._grand_title.setProperty("fontRole", "body-bold")
        card_layout.addWidget(self._grand_title)
        self._grand_lbl = QLabel("0.00")
        self._grand_lbl.setProperty("fontRole", "body-bold")
        self._grand_lbl.setAlignment(Qt.AlignRight)
        card_layout.addWidget(self._grand_lbl)

        # Canvas totals (also shown in preview area)
        canvas_totals_card = QFrame()
        canvas_totals_card.setProperty("role", "card-inner")
        canvas_totals_layout = QVBoxLayout(canvas_totals_card)
        canvas_totals_layout.setContentsMargins(S["3"], S["3"], S["3"], S["3"])
        canvas_totals_layout.setSpacing(S["1"])

        self._canvas_subtotal_label = QLabel(t("invoice_editor.subtotal"))
        self._canvas_subtotal_label.setProperty("fontRole", "label")
        canvas_totals_layout.addWidget(self._canvas_subtotal_label)
        self._canvas_subtotal = QLabel("0.00")
        self._canvas_subtotal.setProperty("fontRole", "body")
        self._canvas_subtotal.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_subtotal)

        self._canvas_tax_label = QLabel(t("invoice_editor.tax"))
        self._canvas_tax_label.setProperty("fontRole", "label")
        canvas_totals_layout.addWidget(self._canvas_tax_label)
        self._canvas_tax = QLabel("0.00")
        self._canvas_tax.setProperty("fontRole", "body")
        self._canvas_tax.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_tax)

        self._canvas_discount_label = QLabel(t("invoice_editor.discount"))
        self._canvas_discount_label.setProperty("fontRole", "label")
        canvas_totals_layout.addWidget(self._canvas_discount_label)
        self._canvas_discount = QLabel("0.00")
        self._canvas_discount.setProperty("fontRole", "body")
        self._canvas_discount.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_discount)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setProperty("role", "divider")
        sep3.setFixedHeight(1)
        canvas_totals_layout.addWidget(sep3)

        self._canvas_grand_label = QLabel(t("invoice_editor.grand_total"))
        self._canvas_grand_label.setProperty("fontRole", "body-bold")
        canvas_totals_layout.addWidget(self._canvas_grand_label)
        self._canvas_grand = QLabel("0.00")
        self._canvas_grand.setProperty("fontRole", "body-bold")
        self._canvas_grand.setAlignment(Qt.AlignRight)
        canvas_totals_layout.addWidget(self._canvas_grand)

        card_layout.addWidget(canvas_totals_card)

        layout.addWidget(card)
        self._scroll.add_widget(container)

    def _on_tax_rate_changed(self, text: str) -> None:
        self._tax_rate = text
        self._recalc_all()

    def _on_discount_type_changed(self, text: str) -> None:
        self._discount_type = text
        is_percent = text == t("invoice_editor.discount_percentage")
        self._disc_symbol_lbl.setText("%" if is_percent else self._get_currency_symbol(self._currency))
        self._recalc_all()

    def _on_discount_value_changed(self, text: str) -> None:
        self._discount_value = text
        self._recalc_all()

    def _on_currency_changed(self, text: str) -> None:
        self._currency = text
        self._recalc_all()

    # ── Branding Section ────────────────────────────────────────────────────

    def _build_branding_section(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        self._branding_header = SectionHeader(container, t("invoice_editor.branding").upper())
        layout.addWidget(self._branding_header)

        card = self._make_card()
        card_layout = QVBoxLayout(card)
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

        self._color_btn = ActionButton(color_row, t("invoice_editor.pick_color"),
                                        variant="secondary", width=80)
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
        row_layout.addWidget(lbl)

        entry = StyledLineEdit(text=path_value, height=28)
        entry.setReadOnly(True)
        setattr(self, f"_{tag}_entry", entry)
        row_layout.addWidget(entry, 1)

        btn = ActionButton(row, t("invoice_editor.browse"), variant="ghost", width=50)
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

        header = SectionHeader(container, t("invoice_editor.notes_section").upper())
        layout.addWidget(header)

        card = self._make_card()
        card_layout = QVBoxLayout(card)
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
        ]

        self._preview_btn = ActionButton(self._bottom_bar, actions[0][0],
                                          command=actions[0][1], variant=actions[0][2])
        layout.addWidget(self._preview_btn)

        self._generate_btn = ActionButton(self._bottom_bar, actions[1][0],
                                           command=actions[1][1], variant=actions[1][2])
        layout.addWidget(self._generate_btn)

        self._print_btn = ActionButton(self._bottom_bar, actions[2][0],
                                        command=actions[2][1], variant=actions[2][2])
        layout.addWidget(self._print_btn)

        self._email_btn = ActionButton(self._bottom_bar, actions[3][0],
                                        command=actions[3][1], variant=actions[3][2])
        layout.addWidget(self._email_btn)

        self._save_draft_btn = ActionButton(self._bottom_bar, actions[4][0],
                                             command=actions[4][1], variant=actions[4][2])
        layout.addWidget(self._save_draft_btn)

        self._load_draft_btn = ActionButton(self._bottom_bar, actions[5][0],
                                             command=actions[5][1], variant=actions[5][2])
        layout.addWidget(self._load_draft_btn)

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
        if not self._client_repo:
            return
        try:
            self._clients = self._client_repo.get_all()
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
        """Fill invoice fields from selected trip data and route stops."""
        trip = self._selected_trip_data
        if not trip:
            return

        # Trip details
        self._truck_plate = trip.get("truck_number", "")
        self._driver_name = trip.get("driver_name", "")
        dist = trip.get("distance_km", 0) or 0
        self._distance = f"{dist:,.1f} km" if dist else ""

        # Fetch route stops
        route_id = trip.get("route_history_v2_id")
        if route_id:
            self._fill_cities_from_route(route_id)

        # Auto-set dates from trip
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        if start:
            self._issue_date = start[:10] if len(start) >= 10 else start
        if end:
            try:
                dt = datetime.strptime(end[:10], "%Y-%m-%d")
                self._due_date = (dt + timedelta(days=30)).strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Auto-fill description from trip
        if dist > 0:
            current_desc = self._description.strip()
            if not current_desc:
                self._description = t("invoice_pdf.service_desc").format(dist)
                self._desc_text_edit.setPlainText(self._description)

        # Set trip base price
        price = round(float(trip.get("total_price_eur", 0) or 0), 2)
        self._trip_base_price = f"{price:.2f}"

        # Handle VAT if present on trip
        pre_vat = trip.get("price_pre_vat")
        vat_pct = trip.get("vat_percent")
        if pre_vat is not None and vat_pct is not None:
            self._trip_price_pre_vat = str(pre_vat)
            self._trip_vat_percent = str(vat_pct)

        # Clear existing addon items and add empty one
        self._addon_items = [{"description": "", "amount": 0.0}]
        self._sync_table_to_items()

        # Auto-select client
        client_name = trip.get("client_name", "")
        if client_name and not self._selected_client_id and client_name in self._client_map:
            self._client_combo.setCurrentText(client_name)
            # on_client_selected is triggered by setCurrentText via signal

        self._update_canvas_labels()
        self._recalc_all()

    def _fill_cities_from_route(self, route_id: int) -> None:
        """Extract loading/unloading cities from route stops JSON."""
        if not self.db:
            return
        try:
            row = self.db.conn.execute(
                "SELECT stops_json FROM route_history_v2 WHERE id = ?",
                (route_id,),
            ).fetchone()
            if not row or not row["stops_json"]:
                return
            stops = json.loads(row["stops_json"])
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
    # CALCULATIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _recalc_all(self) -> None:
        self._refresh_totals_display()

    def _refresh_totals_display(self) -> None:
        """Update all totals displays based on addon items and settings."""
        try:
            tax_rate = float(self._tax_rate or 0)
            disc_val = float(self._discount_value or 0)
            trip_price = float(self._trip_base_price or 0)
        except ValueError:
            tax_rate = 0
            disc_val = 0
            trip_price = 0

        disc_type = self._discount_type
        currency = self._currency

        # Trip base price + addon items
        subtotal = round(trip_price, 2)
        for item in self._addon_items:
            try:
                amt = round(float(item.get("amount", 0) or 0), 2)
            except ValueError:
                amt = 0.0
            item["amount"] = amt
            subtotal = round(subtotal + amt, 2)

        total_tax = round(subtotal * (tax_rate / 100), 2)

        # Discount
        is_percent = disc_type == t("invoice_editor.discount_percentage")
        if is_percent:
            discount = round(subtotal * (disc_val / 100), 2)
        else:
            discount = round(disc_val, 2)

        grand_total = round(subtotal + total_tax - discount, 2)

        sym = self._get_currency_symbol(currency)

        # Update side panel totals
        self._subtotal_lbl.setText(f"{sym}{subtotal:,.2f}")
        self._tax_lbl.setText(f"{sym}{total_tax:,.2f}")
        self._discount_lbl.setText(f"-{sym}{discount:,.2f}")
        self._grand_lbl.setText(f"{sym}{grand_total:,.2f}")

        # Update canvas totals
        self._canvas_subtotal.setText(f"{sym}{subtotal:,.2f}")
        self._canvas_tax.setText(f"{sym}{total_tax:,.2f}")
        self._canvas_discount.setText(f"-{sym}{discount:,.2f}")
        self._canvas_grand.setText(f"{sym}{grand_total:,.2f}")

        # Update discount symbol
        if is_percent:
            self._disc_symbol_lbl.setText("%")
        else:
            self._disc_symbol_lbl.setText(sym)

    def _get_currency_symbol(self, code: str) -> str:
        symbols = {"EUR": "\u20AC", "RON": "lei", "USD": "$", "GBP": "\u00A3"}
        return symbols.get(code, code)

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

    def _save_company_data(self, data: Dict[str, str]) -> None:
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

    def _collect_invoice_data(self) -> Dict[str, Any]:
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

        trip_price = round(float(self._trip_base_price or "0"), 2)
        addon_total = round(sum(li["amount"] for li in addon_items), 2)
        subtotal = round(trip_price + addon_total, 2)
        tax_rate = float(self._tax_rate or 0)
        total_tax = round(subtotal * (tax_rate / 100), 2)
        disc_val = round(float(self._discount_value or "0"), 2)
        is_percent = self._discount_type == t("invoice_editor.discount_percentage")
        discount = round(subtotal * (disc_val / 100), 2) if is_percent else disc_val
        grand_total = round(subtotal + total_tax - discount, 2)

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
        if not data["company"]["company_name"] or not data["company"]["cui"]:
            QMessageBox.warning(self, t("invoice.warning_fields_title"),
                                t("invoice.warning_fields_msg"))
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

    def _generate_rich_pdf(self, data: Dict[str, Any], open_after: bool = False,
                           record: bool = True) -> Optional[str]:
        """Generate a rich PDF using the enhanced InvoiceGenerator."""
        from services.invoicing.generator import InvoiceGenerator
        gen = InvoiceGenerator()
        path = gen.generate_rich(data)

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
                    entity_type="invoice",
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
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._invoice_number = data.get("invoice_number", self._gen_invoice_number())
            self._issue_date = data.get("issue_date", datetime.now().strftime("%Y-%m-%d"))
            self._due_date = data.get("due_date", "")
            self._payment_terms = data.get("payment_terms", "Net 30")
            self._currency = data.get("currency", "EUR")
            self._tax_rate = str(data.get("tax_rate", 19))
            self._discount_type = data.get("discount_type", t("invoice_editor.discount_percentage"))
            self._discount_value = str(data.get("discount_value", 0))

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

            # Try to re-select client/trip
            client_name = cl.get("name", "")
            if client_name and client_name in self._client_map:
                self._client_combo.setCurrentText(client_name)
                # Signal will fire _on_client_selected

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
        parent: Optional[QWidget] = None,
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

        self._entries: Dict[str, StyledLineEdit] = {}
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

        save_btn = ActionButton(btn_frame, t("invoice.save_company"),
                                 variant="primary")
        save_btn.clicked.connect(self._save_and_close)
        btn_frame_layout.addWidget(save_btn)

        cancel_btn = ActionButton(btn_frame, t("invoice_editor.cancel"),
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
        prefs: Optional[PreferencesManager] = None,
        parent: Optional[QWidget] = None,
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
