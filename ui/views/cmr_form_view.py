"""PySide6 CMR consignment note form view — UN/CEFACT-aligned, 24-box editor.

Replaces ``ui/views/cmr_form_view.py`` (CustomTkinter).  Renders a clean,
scrollable form organised into sequential section cards that mirror the standard
international road consignment note.  Boxes are presented in order 1 → 24 with
prominent badges, bilingual labels, and modern dark styling.

Supports auto-fill from trip/client selectors with a consignor/consignee role
toggle, ADR dangerous goods, successive carriers, financial split, and
electronic signature pads (via ``QtSignaturePad``).

Usage as embedded widget::

    view = QtCmrFormView(parent_widget, db)
    some_layout.addWidget(view)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme import COLORS, S
from ui.components import Card, CardHeader, Btn, PageTitle, Label, Divider
from services.i18n import t, register_listener, unregister_listener
from ui.widgets import (
    StyledComboBox,
    StyledLineEdit,
    StyledTextEdit,
    ScrollableFormContainer,
    field,
)
from ui.widgets.signature_pad import QtSignaturePad

logger = logging.getLogger(__name__)

PAYMENT_OPTIONS = ["", "Sender", "Consignee"]


class QtCmrFormView(QWidget):
    """CMR consignment note form — UN/CEFACT 24-box editor.

    Wraps a ``ScrollableFormContainer`` with heading, role selector, section
    cards for each CMR box group, and a bottom action bar.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs

        # ── State ──────────────────────────────────────────────────────────────
        self._adr_rows: List[QWidget] = []
        self._successive_carrier_rows: List[QWidget] = []
        self._financial_rows: List[Tuple[str, str]] = []
        self._cmr_entries: Dict[str, Any] = {}

        self._consignor_role_active: bool = True
        self._last_trip_data: Optional[dict] = None

        # i18n
        self._language_callback: Callable[[str], None] = self._on_language_changed

        # ── Build ──────────────────────────────────────────────────────────────
        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # UI Construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable form container holds everything
        self._scroll_container = ScrollableFormContainer(self, max_width=1200)
        self._scroll_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self._scroll_container, 1)

        # Shortcut to the content widget inside the scroll container
        self._content = self._scroll_container.content

        self._build_page_heading()
        self._build_role_selector()
        self._build_parties_card()            # Boxes 1–2
        self._build_route_card()              # Boxes 3–5
        self._build_vehicle_card()            # Vehicle & driver
        self._build_cargo_card()              # Boxes 6–12
        self._build_instructions_card()       # Boxes 13–17
        self._build_carrier_card()            # Boxes 18–19
        self._build_charges_card()            # Box 20
        self._build_issue_signatures_card()   # Boxes 21–24

        # Bottom action bar (inside the scroll so it scrolls with the form)
        self._build_action_bar()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _build_page_heading(self):
        heading = QWidget()
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, S["3"])
        heading_layout.setSpacing(S["1"])

        self._page_title = PageTitle(
            heading, t("cmr.title", "CMR International Consignment Note")
        )
        heading_layout.addWidget(self._page_title)

        self._page_subtitle = Label(
            heading,
            t("cmr.subtitle", "UN/CEFACT 24-Box Layout — Boxes 1 to 24 in order"),
            role="secondary",
        )
        heading_layout.addWidget(self._page_subtitle)

        # Mini box navigator
        nav = QWidget()
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, S["1"], 0, 0)
        nav_layout.setSpacing(2)
        for i in range(1, 25):
            badge = QLabel(str(i))
            badge.setFixedSize(18, 18)
            badge.setAlignment(Qt.AlignCenter)
            badge.setProperty("role", "box-badge")
            badge.setStyleSheet(
                f"background-color: {COLORS['accent_dim']};"
                f"color: {COLORS['accent_text']};"
                f"border-radius: 4px; font-size: 7px; font-weight: bold;"
            )
            nav_layout.addWidget(badge)
        nav_layout.addStretch(1)
        heading_layout.addWidget(nav)

        self._scroll_container.add_widget(heading)

    def _build_role_selector(self):
        card = Card()
        card.layout().setSpacing(S["2"])

        label = Label(card, t("cmr.select_role", "SELECT YOUR ROLE"), role="section-title")
        card.layout().addWidget(label)
        card.layout().addWidget(Divider())

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

        self._role_consignor_btn = Btn(
            row,
            t("cmr.role_consignor", "I am the Consignor (Sender)"),
            command=lambda: self._set_role(True),
            variant="primary",
        )
        self._role_consignor_btn.setFixedHeight(42)
        row_layout.addWidget(self._role_consignor_btn, 1)

        self._role_consignee_btn = Btn(
            row,
            t("cmr.role_consignee", "I am the Consignee (Receiver)"),
            command=lambda: self._set_role(False),
            variant="secondary",
        )
        self._role_consignee_btn.setFixedHeight(42)
        row_layout.addWidget(self._role_consignee_btn, 1)

        card.layout().addWidget(row)
        self._scroll_container.add_widget(card)

    def _make_card(self) -> QFrame:
        """Create a section card using the design system Card()."""
        return Card()

    def _section_card(self, title: str, subtitle: str) -> QWidget:
        """Create a themed card with CardHeader and return the content widget.

        Callers pack form fields into the returned widget's layout.
        """
        card = Card()
        CardHeader(card.layout(), title=title, subtitle=subtitle)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(S["3"])
        card.layout().addWidget(content)

        self._scroll_container.add_widget(card)
        return content

    def _two_col_pane(self, parent: QWidget) -> Tuple[QWidget, QWidget]:
        """Return (left, right) widgets with a vertical divider between them."""
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(S["3"])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(S["3"])
        wrapper_layout.addWidget(left, 1)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setFrameShadow(QFrame.Plain)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"background-color: {COLORS['border']};")
        wrapper_layout.addWidget(vline)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(S["3"])
        wrapper_layout.addWidget(right, 1)

        parent_layout = parent.layout()
        if parent_layout is None:
            parent.setLayout(QVBoxLayout())
            parent_layout = parent.layout()
            parent_layout.setContentsMargins(0, 0, 0, 0)
            parent_layout.setSpacing(0)
        parent_layout.addWidget(wrapper)
        return left, right

    def _box_field(
        self,
        parent: QWidget,
        box_num: Optional[int],
        label_en: str,
        label_ro: str,
        kind: str = "entry",
        **kwargs,
    ) -> QWidget:
        """Themed field with accent badge + bilingual label.

        Parameters
        ----------
        parent : QWidget
            Container to add the field into.
        box_num : int or None
            CMR box number (None for supplementary fields).
        label_en, label_ro : str
            Bilingual field labels.
        kind : str
            ``"entry"`` (single-line), ``"textbox"`` (multi-line),
            ``"combobox"`` (dropdown).
        **kwargs
            Forwarded to the underlying widget constructor.
        """
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(S["1"])

        # Label row with optional badge
        lbl_row = QWidget()
        lbl_layout = QHBoxLayout(lbl_row)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_layout.setSpacing(S["2"])

        if box_num is not None:
            badge = QLabel(str(box_num))
            badge.setFixedSize(30, 20)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"background-color: {COLORS['accent_dim']};"
                f"color: {COLORS['accent_text']};"
                f"border-radius: 4px; font-weight: bold; font-size: 10px;"
            )
            lbl_layout.addWidget(badge)

        label = QLabel(f"{label_en} / {label_ro}")
        label.setProperty("fontRole", "label")
        label.setStyleSheet(f"color: {COLORS['text_muted']};")
        lbl_layout.addWidget(label)
        lbl_layout.addStretch(1)

        container_layout.addWidget(lbl_row)

        # Input widget
        placeholder = kwargs.pop("placeholder", None)
        if kind == "entry":
            w = StyledLineEdit(container, placeholder=placeholder, **kwargs)
        elif kind == "textbox":
            height = kwargs.pop("height", 90)
            w = StyledTextEdit(container, placeholder=placeholder, height=height, **kwargs)
        elif kind == "combobox":
            values = kwargs.pop("values", [])
            w = StyledComboBox(container, values=values, **kwargs)
        else:
            w = StyledLineEdit(container, placeholder=placeholder, **kwargs)

        container_layout.addWidget(w)

        # Add to parent layout
        parent_layout = parent.layout()
        if parent_layout is None:
            parent_layout = QVBoxLayout(parent)
            parent_layout.setContentsMargins(0, 0, 0, 0)
            parent_layout.setSpacing(S["3"])
            parent.setLayout(parent_layout)
        parent_layout.addWidget(container)

        return w

    def _compact_box(
        self, parent: QWidget, box_num: int, label: str, col: int, max_col: int = 3
    ) -> StyledLineEdit:
        """Compact grid cell for the goods table (single-line entry)."""
        # We use a simple vertical layout approach since we can't easily
        # grid inside a horizontal layout. Instead, the caller should use
        # a QGridLayout or QHBoxLayout-based approach.
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(S["1"])

        lbl_row = QWidget()
        lbl_layout = QHBoxLayout(lbl_row)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_layout.setSpacing(S["1"])

        badge = QLabel(str(box_num))
        badge.setFixedSize(26, 18)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {COLORS['accent_dim']};"
            f"color: {COLORS['accent_text']};"
            f"border-radius: 3px; font-weight: bold; font-size: 8px;"
        )
        lbl_layout.addWidget(badge)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
        lbl_layout.addWidget(lbl)
        lbl_layout.addStretch(1)

        container_layout.addWidget(lbl_row)

        e = StyledLineEdit(container, height=32)
        container_layout.addWidget(e)

        # Add to parent layout — assumes parent uses QHBoxLayout or QGridLayout
        parent_layout = parent.layout()
        if parent_layout and isinstance(parent_layout, QHBoxLayout):
            parent_layout.addWidget(container, 1)
        elif parent_layout and hasattr(parent_layout, "addWidget"):
            parent_layout.addWidget(container, col, 0)

        return e

    # ── Section: Parties (Boxes 1, 2) ──────────────────────────────────────

    def _build_parties_card(self):
        content = self._section_card(
            t("cmr.section_parties", "Parties"),
            t("cmr.section_parties_sub",
              "Boxes 1 & 2 — Consignor (Sender) and Consignee (Receiver)"),
        )
        left, right = self._two_col_pane(content)

        self._cmr_entries["consignor_name"] = self._box_field(
            left, 1,
            t("cmr.consignor", "Sender (Consignor)"),
            t("cmr.consignor_ro", "Expeditor"),
            kind="textbox", height=90,
        )
        self._cmr_entries["consignee_name"] = self._box_field(
            right, 2,
            t("cmr.consignee", "Consignee"),
            t("cmr.consignee_ro", "Destinatar"),
            kind="textbox", height=90,
        )

    # ── Section: Route & Documents (Boxes 3, 4, 5) ─────────────────────────

    def _build_route_card(self):
        content = self._section_card(
            t("cmr.section_route", "Route & Documents"),
            t("cmr.section_route_sub",
              "Boxes 3, 4 & 5 — Taking over, delivery and attached documents"),
        )
        left, right = self._two_col_pane(content)

        # Box 3: Place of taking over
        self._cmr_entries["place_of_loading"] = self._box_field(
            left, 3,
            t("cmr.place_of_loading", "Place of Taking Over"),
            t("cmr.place_of_loading_ro", "Locul Predarii"),
            placeholder=t("cmr.locality_country", "Locality, Country"),
        )

        # Box 4: Place of delivery
        self._cmr_entries["destination"] = self._box_field(
            right, 4,
            t("cmr.destination", "Place of Delivery"),
            t("cmr.destination_ro", "Locul Livrarii"),
            placeholder=t("cmr.locality_country", "Locality, Country"),
        )

        # Date row for Box 3
        date_container = QWidget()
        date_layout = QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(S["2"])

        date_label = QLabel(t("cmr.date", "Date:"))
        date_label.setProperty("fontRole", "small")
        date_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        date_layout.addWidget(date_label)

        wld = QDateEdit()
        wld.setDisplayFormat("yyyy-MM-dd")
        wld.setCalendarPopup(True)
        wld.setDate(QDate.currentDate())
        wld.setFixedHeight(32)
        wld.setStyleSheet(
            f"background-color: {COLORS['bg_input']};"
            f"color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']};"
            f"border-radius: 4px; padding: 2px 6px;"
        )
        date_layout.addWidget(wld, 1)

        left.layout().addWidget(date_container)
        self._cmr_entries["place_of_loading_date"] = wld

        # ISO country row for Box 3 / 4
        iso_container = QWidget()
        iso_layout = QHBoxLayout(iso_container)
        iso_layout.setContentsMargins(0, 0, 0, 0)
        iso_layout.setSpacing(S["2"])

        iso_label_a = QLabel(t("cmr.loading_country", "Loading Country ISO:"))
        iso_label_a.setProperty("fontRole", "small")
        iso_label_a.setStyleSheet(f"color: {COLORS['text_muted']};")
        iso_layout.addWidget(iso_label_a)

        wlc = StyledLineEdit(height=32)
        wlc.setFixedWidth(60)
        wlc.setMaxLength(2)
        iso_layout.addWidget(wlc)

        iso_label_b = QLabel(t("cmr.delivery_country", "Delivery Country ISO:"))
        iso_label_b.setProperty("fontRole", "small")
        iso_label_b.setStyleSheet(f"color: {COLORS['text_muted']};")
        iso_layout.addWidget(iso_label_b)

        wdc = StyledLineEdit(height=32)
        wdc.setFixedWidth(60)
        wdc.setMaxLength(2)
        iso_layout.addWidget(wdc)

        left.layout().addWidget(iso_container)
        self._cmr_entries["loading_country"] = wlc
        self._cmr_entries["delivery_country"] = wdc

        # Box 5: Documents attached
        self._cmr_entries["documents_attached"] = self._box_field(
            right, 5,
            t("cmr.documents", "Documents Attached"),
            t("cmr.documents_ro", "Documente Atasate"),
            kind="textbox", height=90,
        )

    # ── Section: Vehicle & Driver ──────────────────────────────────────────

    def _build_vehicle_card(self):
        content = self._section_card(
            t("cmr.section_vehicle", "Vehicle & Driver"),
            t("cmr.section_vehicle_sub", "Transport means and driver information"),
        )
        left, right = self._two_col_pane(content)

        self._cmr_entries["truck_plate"] = field(
            left, t("cmr.truck_plate", "Truck Plate / Numar Camion"),
            StyledLineEdit(left, height=38),
        )
        self._cmr_entries["driver_name"] = field(
            left, t("cmr.driver_name", "Driver / Sofer"),
            StyledLineEdit(left, height=38),
        )
        self._cmr_entries["trailer_plate"] = field(
            right, t("cmr.trailer_plate", "Trailer Plate / Numar Remorca"),
            StyledLineEdit(right, height=38),
        )
        self._cmr_entries["driver_license"] = field(
            right, t("cmr.driver_license", "License / Permis"),
            StyledLineEdit(right, height=38),
        )

    # ── Section: Goods (Boxes 6–12) ────────────────────────────────────────

    def _build_cargo_card(self):
        content = self._section_card(
            t("cmr.section_cargo", "Goods Specifications"),
            t("cmr.section_cargo_sub",
              "Boxes 6 to 12 — Cargo details, weight, volume and HS code"),
        )

        # Row 1: Boxes 6–9
        r1 = QWidget()
        r1_layout = QHBoxLayout(r1)
        r1_layout.setContentsMargins(0, 0, 0, 0)
        r1_layout.setSpacing(S["3"])

        self._cmr_entries["cargo_marks"] = self._compact_box(r1, 6, "Marks & Numbers", 0)
        self._cmr_entries["package_count"] = self._compact_box(r1, 7, "No. of Packages", 1)
        self._cmr_entries["package_type"] = self._compact_box(r1, 8, "Method of Packing", 2)
        self._cmr_entries["cargo_description"] = self._compact_box(r1, 9, "Nature of Goods", 3)

        content.layout().addWidget(r1)

        # Row 2: Boxes 10–12
        r2 = QWidget()
        r2_layout = QHBoxLayout(r2)
        r2_layout.setContentsMargins(0, 0, 0, 0)
        r2_layout.setSpacing(S["3"])

        self._cmr_entries["hs_code"] = self._compact_box(r2, 10, "HS Code", 0, max_col=2)
        self._cmr_entries["gross_weight_kg"] = self._compact_box(r2, 11, "Gross Weight (kg)", 1, max_col=2)
        self._cmr_entries["volume_m3"] = self._compact_box(r2, 12, "Volume (m\u00b3)", 2, max_col=2)

        content.layout().addWidget(r2)

        # ADR section
        self._build_adr_section(content)

    def _build_adr_section(self, parent: QWidget):
        self._adr_toggle = QCheckBox(
            t("cmr.adr_toggle", "Contains DANGEROUS GOODS (ADR)")
        )
        self._adr_toggle.setStyleSheet(
            f"color: {COLORS['text_primary']};"
            f"font-weight: bold;"
            f"spacing: 6px;"
        )
        self._adr_toggle.stateChanged.connect(self._on_adr_toggle)
        parent.layout().addWidget(self._adr_toggle)

        # Wrapper for ADR content (shown/hidden on toggle)
        self._adr_content_wrapper = QWidget()
        self._adr_content_wrapper.setVisible(False)
        adr_wrapper_layout = QVBoxLayout(self._adr_content_wrapper)
        adr_wrapper_layout.setContentsMargins(0, S["2"], 0, 0)
        adr_wrapper_layout.setSpacing(S["2"])

        self._adr_content = QWidget()
        self._adr_content_layout = QVBoxLayout(self._adr_content)
        self._adr_content_layout.setContentsMargins(0, 0, 0, 0)
        self._adr_content_layout.setSpacing(S["2"])
        adr_wrapper_layout.addWidget(self._adr_content)

        self._adr_add_btn = Btn(
            self._adr_content_wrapper,
            t("cmr.add_adr", "+ Add ADR Row"),
            command=self._add_adr_row,
            variant="danger",
        )
        self._adr_add_btn.setFixedHeight(28)
        adr_wrapper_layout.addWidget(self._adr_add_btn)

        parent.layout().addWidget(self._adr_content_wrapper)

    def _on_adr_toggle(self, state: int):
        checked = state == Qt.Checked
        self._adr_content_wrapper.setVisible(checked)
        if checked and not self._adr_rows:
            self._add_adr_row()

    def _add_adr_row(self):
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        row.setStyleSheet(
            f"background-color: {COLORS['bg_elevated']};"
            f"border-radius: 4px;"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])
        row_layout.setSpacing(S["2"])

        labels = ["UN No", "Class", "Pack. Grp", "Tunnel", "Qty", "Net Wt(kg)"]
        for lbl in labels:
            e = StyledLineEdit(row, placeholder=lbl, height=28)
            row_layout.addWidget(e, 1)

        remove_btn = Btn(
            row, "X", variant="danger",
            command=lambda r=row: self._remove_adr_row(r),
        )
        remove_btn.setFixedSize(28, 28)
        row_layout.addWidget(remove_btn)

        self._adr_content_layout.addWidget(row)
        self._adr_rows.append(row)

    def _remove_adr_row(self, frame: QWidget):
        frame.deleteLater()
        if frame in self._adr_rows:
            self._adr_rows.remove(frame)

    # ── Section: Instructions & Agreements (Boxes 13–17) ──────────────────

    def _build_instructions_card(self):
        content = self._section_card(
            t("cmr.section_instructions", "Instructions & Agreements"),
            t("cmr.section_instructions_sub",
              "Boxes 13 to 17 — Instructions, reservations, payment,"
              " COD and special agreements"),
        )
        left, right = self._two_col_pane(content)

        # Box 13: Sender's instructions
        self._cmr_entries["carrier_instructions"] = self._box_field(
            left, 13,
            t("cmr.sender_instructions", "Sender's Instructions"),
            t("cmr.sender_instructions_ro", "Instructiuni Expeditor"),
            kind="textbox", height=80,
        )

        # Box 14: Carrier's reservations
        self._cmr_entries["carrier_reservations"] = self._box_field(
            right, 14,
            t("cmr.carrier_reservations", "Carrier's Reservations"),
            t("cmr.carrier_reservations_ro", "Rezerve Transportator"),
            kind="textbox", height=80,
        )

        # Box 15: Payment instruction
        self._cmr_entries["carriage_payer"] = self._box_field(
            left, 15,
            t("cmr.payment_instruction", "Instruction as to Payment"),
            t("cmr.payment_instruction_ro", "Plata Transport"),
            kind="combobox", values=PAYMENT_OPTIONS,
        )

        # Box 16: Cash on delivery
        self._cmr_entries["cod_amount"] = self._box_field(
            right, 16,
            t("cmr.cod", "Cash on Delivery (COD)"),
            t("cmr.cod_ro", "Ramburs"),
            placeholder=t("cmr.amount_eur", "Amount (EUR)"),
        )

        # Box 17: Special agreements
        self._cmr_entries["special_agreements"] = self._box_field(
            right, 17,
            t("cmr.special_agreements", "Special Agreements"),
            t("cmr.special_agreements_ro", "Acorduri Speciale"),
            kind="textbox", height=80,
        )

        # Distance (supplementary, no box number)
        self._cmr_entries["distance_km"] = self._box_field(
            content, None,
            t("cmr.distance", "Distance (km)"),
            t("cmr.distance_ro", "Distanta (km)"),
            placeholder=t("cmr.distance_placeholder", "Distance in kilometres"),
        )

    # ── Section: Carrier (Boxes 18, 19) ───────────────────────────────────

    def _build_carrier_card(self):
        content = self._section_card(
            t("cmr.section_carrier", "Carrier"),
            t("cmr.section_carrier_sub",
              "Boxes 18 & 19 — Carrier and successive carriers"),
        )
        left, right = self._two_col_pane(content)

        self._cmr_entries["carrier_name"] = self._box_field(
            left, 18,
            t("cmr.carrier", "Carrier"),
            t("cmr.carrier_ro", "Transportator"),
            kind="textbox", height=90,
        )

        # Box 19: Successive carriers
        sc_container = QWidget()
        sc_layout = QVBoxLayout(sc_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(S["2"])

        sc_lbl_row = QWidget()
        sc_lbl_layout = QHBoxLayout(sc_lbl_row)
        sc_lbl_layout.setContentsMargins(0, 0, 0, 0)
        sc_lbl_layout.setSpacing(S["2"])

        badge = QLabel("19")
        badge.setFixedSize(30, 20)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {COLORS['accent_dim']};"
            f"color: {COLORS['accent_text']};"
            f"border-radius: 4px; font-weight: bold; font-size: 10px;"
        )
        sc_lbl_layout.addWidget(badge)

        sc_lbl = QLabel(
            t("cmr.successive_carriers", "Successive Carriers / Transportatori Successivi")
        )
        sc_lbl.setProperty("fontRole", "label")
        sc_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        sc_lbl_layout.addWidget(sc_lbl)
        sc_lbl_layout.addStretch(1)

        sc_layout.addWidget(sc_lbl_row)

        self._succ_container = QWidget()
        self._succ_container_layout = QVBoxLayout(self._succ_container)
        self._succ_container_layout.setContentsMargins(0, 0, 0, 0)
        self._succ_container_layout.setSpacing(S["2"])
        sc_layout.addWidget(self._succ_container)

        self._succ_add_btn = Btn(
            sc_container,
            t("cmr.add_successive_carrier", "+ Add Successive Carrier"),
            command=self._add_successive_carrier_row,
            variant="secondary",
        )
        self._succ_add_btn.setFixedHeight(32)
        sc_layout.addWidget(self._succ_add_btn)

        right.layout().addWidget(sc_container)

    def _add_successive_carrier_row(self):
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        row.setStyleSheet(
            f"background-color: {COLORS['bg_elevated']};"
            f"border-radius: 4px;"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(S["2"], S["1"], S["2"], S["1"])
        row_layout.setSpacing(S["2"])

        for lbl in ["Name", "Address", "Country", "Plate", "Trailer", "Driver", "From", "To"]:
            e = StyledLineEdit(row, placeholder=lbl, height=28)
            row_layout.addWidget(e, 1)

        remove_btn = Btn(
            row, "X", variant="danger",
            command=lambda r=row: self._remove_successive_carrier_row(r),
        )
        remove_btn.setFixedSize(28, 28)
        row_layout.addWidget(remove_btn)

        self._succ_container_layout.addWidget(row)
        self._successive_carrier_rows.append(row)

    def _remove_successive_carrier_row(self, frame: QWidget):
        frame.deleteLater()
        if frame in self._successive_carrier_rows:
            self._successive_carrier_rows.remove(frame)

    # ── Section: Charges (Box 20) ─────────────────────────────────────────

    def _build_charges_card(self):
        content = self._section_card(
            t("cmr.section_charges", "Box 20 — To Be Paid By"),
            t("cmr.section_charges_sub",
              "Charges to be paid by the Sender or the Consignee"),
        )

        # Table header
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(S["3"])

        cost_type_lbl = QLabel(t("cmr.cost_type", "Cost Type"))
        cost_type_lbl.setProperty("fontRole", "label")
        cost_type_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        hdr_layout.addWidget(cost_type_lbl, 2)

        sender_lbl = QLabel(t("cmr.sender", "Sender"))
        sender_lbl.setProperty("fontRole", "label")
        sender_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        sender_lbl.setAlignment(Qt.AlignRight)
        hdr_layout.addWidget(sender_lbl, 1)

        consignee_lbl = QLabel(t("cmr.consignee_short", "Consignee"))
        consignee_lbl.setProperty("fontRole", "label")
        consignee_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        consignee_lbl.setAlignment(Qt.AlignRight)
        hdr_layout.addWidget(consignee_lbl, 1)

        content.layout().addWidget(hdr)

        # Divider
        content.layout().addWidget(Divider())

        # Cost rows
        cost_rows = [
            ("Carriage charges", "carriage_sender", "carriage_consignee"),
            ("Supplementary charges", "supplementary_sender", "supplementary_consignee"),
            ("Customs duties", "customs_sender", "customs_consignee"),
            ("Other costs", "other_sender", "other_consignee"),
        ]
        self._financial_rows.clear()
        for label, sk, ck in cost_rows:
            self._build_financial_row(content, label, sk, ck)

    def _build_financial_row(
        self, parent: QWidget, label: str, sender_key: str, consignee_key: str
    ):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["3"])

        lbl = QLabel(label)
        lbl.setProperty("fontRole", "small")
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        row_layout.addWidget(lbl, 2)

        se = StyledLineEdit(row, placeholder="EUR", height=32)
        row_layout.addWidget(se, 1)
        self._cmr_entries[sender_key] = se

        ce = StyledLineEdit(row, placeholder="EUR", height=32)
        row_layout.addWidget(ce, 1)
        self._cmr_entries[consignee_key] = ce

        self._financial_rows.append((sender_key, consignee_key))
        parent.layout().addWidget(row)

    # ── Section: Issue & Signatures (Boxes 21–24) ─────────────────────────

    def _build_issue_signatures_card(self):
        content = self._section_card(
            t("cmr.section_issue", "Issue & Signatures"),
            t("cmr.section_issue_sub",
              "Boxes 21 to 24 — Place/date of issue and party signatures"),
        )

        # Box 21: Established in
        b21 = QWidget()
        b21_layout = QVBoxLayout(b21)
        b21_layout.setContentsMargins(0, 0, 0, 0)
        b21_layout.setSpacing(S["1"])

        b21_lbl_row = QWidget()
        b21_lbl_layout = QHBoxLayout(b21_lbl_row)
        b21_lbl_layout.setContentsMargins(0, 0, 0, 0)
        b21_lbl_layout.setSpacing(S["2"])

        badge21 = QLabel("21")
        badge21.setFixedSize(30, 20)
        badge21.setAlignment(Qt.AlignCenter)
        badge21.setStyleSheet(
            f"background-color: {COLORS['accent_dim']};"
            f"color: {COLORS['accent_text']};"
            f"border-radius: 4px; font-weight: bold; font-size: 10px;"
        )
        b21_lbl_layout.addWidget(badge21)

        b21_title = QLabel(
            t("cmr.established_in", "Established in / Intocmit in")
        )
        b21_title.setProperty("fontRole", "label")
        b21_title.setStyleSheet(f"color: {COLORS['text_muted']};")
        b21_lbl_layout.addWidget(b21_title)
        b21_lbl_layout.addStretch(1)

        b21_layout.addWidget(b21_lbl_row)

        # Row with place + date
        row21 = QWidget()
        row21_layout = QHBoxLayout(row21)
        row21_layout.setContentsMargins(0, 0, 0, 0)
        row21_layout.setSpacing(S["3"])

        place_col = QWidget()
        place_col_layout = QVBoxLayout(place_col)
        place_col_layout.setContentsMargins(0, 0, 0, 0)
        place_col_layout.setSpacing(S["1"])
        place_label = QLabel(t("cmr.place", "Place:"))
        place_label.setProperty("fontRole", "small")
        place_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        place_col_layout.addWidget(place_label)
        self._cmr_entries["issue_place"] = StyledLineEdit(
            place_col, placeholder=t("cmr.city_country", "City, Country"), height=32,
        )
        place_col_layout.addWidget(self._cmr_entries["issue_place"])
        row21_layout.addWidget(place_col, 1)

        date_col = QWidget()
        date_col_layout = QVBoxLayout(date_col)
        date_col_layout.setContentsMargins(0, 0, 0, 0)
        date_col_layout.setSpacing(S["1"])
        date_label = QLabel(t("cmr.date", "Date:"))
        date_label.setProperty("fontRole", "small")
        date_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        date_col_layout.addWidget(date_label)
        w21d = QDateEdit()
        w21d.setDisplayFormat("yyyy-MM-dd")
        w21d.setCalendarPopup(True)
        w21d.setDate(QDate.currentDate())
        w21d.setFixedHeight(32)
        w21d.setStyleSheet(
            f"background-color: {COLORS['bg_input']};"
            f"color: {COLORS['text_primary']};"
            f"border: 1px solid {COLORS['border']};"
            f"border-radius: 4px; padding: 2px 6px;"
        )
        date_col_layout.addWidget(w21d)
        row21_layout.addWidget(date_col, 1)
        self._cmr_entries["issue_date"] = w21d

        b21_layout.addWidget(row21)
        content.layout().addWidget(b21)

        # Signatures 22-24
        sig_row = QWidget()
        sig_layout = QHBoxLayout(sig_row)
        sig_layout.setContentsMargins(0, 0, 0, 0)
        sig_layout.setSpacing(S["3"])

        sig_specs = [
            (22, t("cmr.sig_sender", "Signature of Sender"), "sender"),
            (23, t("cmr.sig_carrier", "Signature of Carrier"), "carrier"),
            (24, t("cmr.sig_consignee", "Signature of Consignee"), "consignee"),
        ]

        for col_i, (num, label_text, key) in enumerate(sig_specs):
            col = QWidget()
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(S["1"])

            # Badge + label
            sig_lbl_row = QWidget()
            sig_lbl_layout = QHBoxLayout(sig_lbl_row)
            sig_lbl_layout.setContentsMargins(0, 0, 0, 0)
            sig_lbl_layout.setSpacing(S["1"])

            sig_badge = QLabel(str(num))
            sig_badge.setFixedSize(26, 18)
            sig_badge.setAlignment(Qt.AlignCenter)
            sig_badge.setStyleSheet(
                f"background-color: {COLORS['accent_dim']};"
                f"color: {COLORS['accent_text']};"
                f"border-radius: 3px; font-weight: bold; font-size: 8px;"
            )
            sig_lbl_layout.addWidget(sig_badge)

            sig_lbl = QLabel(label_text)
            sig_lbl.setProperty("fontRole", "label")
            sig_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            sig_lbl_layout.addWidget(sig_lbl)
            sig_lbl_layout.addStretch(1)

            col_layout.addWidget(sig_lbl_row)

            pad = QtSignaturePad(col, label="")
            col_layout.addWidget(pad)
            setattr(self, f"sig_{key}_pad", pad)

            sig_layout.addWidget(col, 1)

        content.layout().addWidget(sig_row)

    # ── Bottom action bar ────────────────────────────────────────────────

    def _build_action_bar(self):
        """Action buttons for Generate, Print, Save."""
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, S["4"], 0, 0)
        bar_layout.setSpacing(S["3"])

        self._btn_generate = Btn(
            bar,
            t("cmr.generate", "Generate CMR"),
            variant="primary",
        )
        self._btn_generate.setFixedHeight(38)
        bar_layout.addWidget(self._btn_generate)

        self._btn_print = Btn(
            bar,
            t("cmr.print", "Print"),
            variant="secondary",
        )
        self._btn_print.setFixedHeight(38)
        bar_layout.addWidget(self._btn_print)

        bar_layout.addStretch(1)

        self._btn_save = Btn(
            bar,
            t("cmr.save", "Save"),
            variant="secondary",
        )
        self._btn_save.setFixedHeight(38)
        bar_layout.addWidget(self._btn_save)

        self._bottom_bar = bar
        self._scroll_container.add_widget(bar)

    # ── Role selection ────────────────────────────────────────────────────

    def _set_role(self, is_consignor: bool):
        if self._consignor_role_active == is_consignor:
            return
        self._consignor_role_active = is_consignor
        self._update_role_buttons()
        if self._last_trip_data:
            self.fill_from_trip(**self._last_trip_data)

    def _update_role_buttons(self):
        if self._consignor_role_active:
            self._role_consignor_btn.setProperty("variant", "primary")
            self._role_consignee_btn.setProperty("variant", "secondary")
        else:
            self._role_consignor_btn.setProperty("variant", "secondary")
            self._role_consignee_btn.setProperty("variant", "primary")
        # Force style refresh
        self._role_consignor_btn.style().unpolish(self._role_consignor_btn)
        self._role_consignor_btn.style().polish(self._role_consignor_btn)
        self._role_consignee_btn.style().unpolish(self._role_consignee_btn)
        self._role_consignee_btn.style().polish(self._role_consignee_btn)

    # ══════════════════════════════════════════════════════════════════════
    # Data collection
    # ══════════════════════════════════════════════════════════════════════

    def collect_data(self, trip_base: Optional[dict] = None) -> dict:
        """Collect all form field values into a flat dictionary.

        Mirrors the original ``CMRFormView.collect_data()`` but returns
        Qt widget values instead of tkinter string vars.
        """
        data = dict(trip_base) if trip_base else {}
        data["generating_role"] = "consignor" if self._consignor_role_active else "consignee"

        def _get(key: str, widget_key: str, default: str = "") -> None:
            w = self._cmr_entries.get(widget_key)
            if w is None:
                data.setdefault(key, default)
                return

            if isinstance(w, QPlainTextEdit):
                val = w.toPlainText().strip()
            elif isinstance(w, StyledTextEdit):
                val = w.toPlainText().strip()
            elif isinstance(w, StyledComboBox):
                val = w.currentText().strip()
            elif isinstance(w, QDateEdit):
                qdate = w.date()
                if qdate.isValid():
                    val = qdate.toString("yyyy-MM-dd")
                else:
                    val = default
            elif isinstance(w, StyledLineEdit):
                val = w.text().strip()
            else:
                # Fallback: try text() or currentText()
                try:
                    val = w.text().strip()
                except Exception:
                    val = default

            data[key] = val if val else default

        # Party data
        _get("consignor_name", "consignor_name")
        _get("client_name", "consignee_name")
        _get("carrier_name", "carrier_name")

        # Location data
        _get("destination", "destination")
        _get("delivery_country", "delivery_country")
        _get("place_of_loading", "place_of_loading")
        _get("place_of_loading_date", "place_of_loading_date")
        _get("loading_country", "loading_country")
        _get("documents_attached", "documents_attached")

        # Cargo data
        _get("cargo_marks", "cargo_marks")
        _get("cargo_description", "cargo_description")
        _get("package_count", "package_count")
        _get("package_type", "package_type")
        _get("gross_weight_kg", "gross_weight_kg")
        _get("volume_m3", "volume_m3")
        _get("hs_code", "hs_code")

        # Carrier & Vehicle
        _get("carrier_reservations", "carrier_reservations")
        _get("truck_plate", "truck_plate")
        _get("trailer_plate", "trailer_plate")
        _get("driver_name", "driver_name")
        _get("driver_license", "driver_license")

        # Bottom section
        _get("carrier_instructions", "carrier_instructions")
        _get("carriage_payer", "carriage_payer")
        _get("cod_amount", "cod_amount")
        _get("distance_km", "distance_km")
        _get("special_agreements", "special_agreements")

        # Issue info
        _get("issue_place", "issue_place")
        _get("issue_date", "issue_date")

        # Signature paths
        for k in ["sender", "carrier", "consignee"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None:
                path = pad.get_path()
                if path:
                    data[f"sig_{k}_path"] = path

        # Financial grid
        data["financial_grid"] = self._get_financial_data()

        # ADR
        adr = self._get_adr_data()
        if adr:
            data["adr_info_json"] = json.dumps(adr)

        # Successive carriers
        succ = self._get_successive_carriers()
        if succ:
            data["successive_carriers"] = succ

        # Merge compound textarea fields properly
        if data.get("consignor_name"):
            name_val = data.get("consignor_name", "")
            if not data.get("consignor_address"):
                lines = name_val.split("\n")
                data["consignor_name"] = lines[0] if lines else ""
                data["consignor_address"] = "\n".join(lines[1:]) if len(lines) > 1 else ""

        if data.get("consignee_name") or data.get("client_name"):
            cname = data.get("consignee_name") or data.get("client_name", "")
            if not data.get("client_address"):
                lines = cname.split("\n")
                data["client_name"] = lines[0] if lines else ""
                data["client_address"] = "\n".join(lines[1:]) if len(lines) > 1 else ""
            else:
                data["client_name"] = cname

        if data.get("carrier_name"):
            cname_c = data.get("carrier_name", "")
            if not data.get("carrier_address"):
                lines = cname_c.split("\n")
                data["carrier_name"] = lines[0] if lines else ""
                data["carrier_address"] = "\n".join(lines[1:]) if len(lines) > 1 else ""

        return data

    def _get_adr_data(self) -> Optional[List[dict]]:
        if not self._adr_toggle.isChecked():
            return None
        items = []
        for row in self._adr_rows:
            entries = [
                c for c in row.findChildren(StyledLineEdit)
            ]
            if len(entries) >= 6:
                items.append({
                    "un_no": entries[0].text().strip(),
                    "adr_class": entries[1].text().strip(),
                    "packing_group": entries[2].text().strip(),
                    "tunnel_code": entries[3].text().strip(),
                    "quantity": entries[4].text().strip(),
                    "net_weight": entries[5].text().strip(),
                })
        return items if items else None

    def _get_successive_carriers(self) -> List[dict]:
        result = []
        for frame in self._successive_carrier_rows:
            entries = frame.findChildren(StyledLineEdit)
            if len(entries) >= 6:
                result.append({
                    "carrier_name": entries[0].text().strip(),
                    "carrier_address": entries[1].text().strip(),
                    "carrier_country": entries[2].text().strip(),
                    "vehicle_plate": entries[3].text().strip(),
                    "trailer_plate": entries[4].text().strip(),
                    "driver_name": entries[5].text().strip(),
                    "from_location": entries[6].text().strip()
                    if len(entries) > 6 else "",
                    "to_location": entries[7].text().strip()
                    if len(entries) > 7 else "",
                })
        return result

    def _get_financial_data(self) -> dict:
        result = {}
        for sk, ck in self._financial_rows:
            s_w = self._cmr_entries.get(sk)
            c_w = self._cmr_entries.get(ck)
            result[sk] = s_w.text().strip() if s_w else ""
            result[ck] = c_w.text().strip() if c_w else ""
        return result

    # ══════════════════════════════════════════════════════════════════════
    # Auto-fill
    # ══════════════════════════════════════════════════════════════════════

    def fill_from_trip(
        self,
        trip: Optional[dict] = None,
        company_conf: Optional[dict] = None,
        client_data: Optional[dict] = None,
        truck_data: Optional[dict] = None,
        driver_data: Optional[dict] = None,
    ):
        """Populate form fields from trip, company, and client data."""
        self._last_trip_data = dict(
            trip=trip, company_conf=company_conf,
            client_data=client_data, truck_data=truck_data,
            driver_data=driver_data,
        )
        if not trip:
            return

        conf = company_conf or {}
        client = client_data or {}
        truck = truck_data or {}
        driver = driver_data or {}

        if self._consignor_role_active:
            # Company → Box 1 (Consignor / Sender)
            sender_lines = []
            sender_lines.append(conf.get("company_name", ""))
            sender_lines.append(conf.get("address", ""))
            cui = conf.get("cui", "")
            eori = conf.get("eori_number", "")
            phone = conf.get("phone", "")
            if cui:
                sender_lines.append(f"VAT/CUI: {cui}")
            if eori:
                sender_lines.append(f"EORI: {eori}")
            if phone:
                sender_lines.append(f"Tel: {phone}")
            self._set_entry(
                self._cmr_entries.get("consignor_name"),
                "\n".join(line for line in sender_lines if line),
            )

            # Client → Box 2 (Consignee)
            c_lines = []
            c_lines.append(trip.get("client_name", client.get("name", "")))
            c_lines.append(client.get("address", ""))
            c_vat = client.get("vat_number", "")
            c_eori = client.get("eori_number", "")
            c_contact = client.get("consignee_contact_name", "")
            c_phone = client.get("consignee_contact_phone", client.get("phone", ""))
            if c_vat:
                c_lines.append(f"VAT: {c_vat}")
            if c_eori:
                c_lines.append(f"EORI: {c_eori}")
            if c_contact or c_phone:
                c_lines.append(f"Contact: {c_contact}, {c_phone}".strip(", "))
            self._set_entry(
                self._cmr_entries.get("consignee_name"),
                "\n".join(line for line in c_lines if line),
            )
        else:
            # Client → Box 1 (Consignor)
            sender_lines = []
            sender_lines.append(trip.get("client_name", client.get("name", "")))
            sender_lines.append(client.get("address", ""))
            c_vat = client.get("vat_number", "")
            c_eori = client.get("eori_number", "")
            c_contact = client.get("consignee_contact_name", "")
            c_phone = client.get("consignee_contact_phone", client.get("phone", ""))
            if c_vat:
                sender_lines.append(f"VAT: {c_vat}")
            if c_eori:
                sender_lines.append(f"EORI: {c_eori}")
            if c_contact or c_phone:
                sender_lines.append(f"Contact: {c_contact}, {c_phone}".strip(", "))
            self._set_entry(
                self._cmr_entries.get("consignor_name"),
                "\n".join(line for line in sender_lines if line),
            )

            # Company → Box 2 (Consignee)
            c_lines = []
            c_lines.append(conf.get("company_name", ""))
            c_lines.append(conf.get("address", ""))
            cui = conf.get("cui", "")
            eori = conf.get("eori_number", "")
            phone = conf.get("phone", "")
            if cui:
                c_lines.append(f"VAT/CUI: {cui}")
            if eori:
                c_lines.append(f"EORI: {eori}")
            if phone:
                c_lines.append(f"Tel: {phone}")
            self._set_entry(
                self._cmr_entries.get("consignee_name"),
                "\n".join(line for line in c_lines if line),
            )

        # Carrier — always from company config
        carr_lines = []
        carr_lines.append(conf.get("company_name", ""))
        carr_lines.append(conf.get("address", ""))
        c_phone = conf.get("phone", "")
        c_email = conf.get("email", "")
        c_reg = conf.get("reg_number", "")
        if c_phone:
            carr_lines.append(f"Tel: {c_phone}")
        if c_email:
            carr_lines.append(f"Email: {c_email}")
        if c_reg:
            carr_lines.append(f"Reg No: {c_reg}")
        self._set_entry(
            self._cmr_entries.get("carrier_name"),
            "\n".join(line for line in carr_lines if line),
        )

        # Vehicle plates
        plate = truck.get("plate_number", trip.get("truck_number", ""))
        trailer = truck.get("trailer_plate", trip.get("trailer_plate", ""))
        self._set_entry(self._cmr_entries.get("truck_plate"), plate)
        self._set_entry(self._cmr_entries.get("trailer_plate"), trailer)

        # Driver
        dname = driver.get("name", trip.get("driver_name", ""))
        dlic = driver.get("license_number", trip.get("driver_license", ""))
        self._set_entry(self._cmr_entries.get("driver_name"), dname)
        self._set_entry(self._cmr_entries.get("driver_license"), dlic)

        # Locations
        self._set_entry(
            self._cmr_entries.get("destination"),
            trip.get("destination", trip.get("unloading_address", "")),
        )
        self._set_entry(
            self._cmr_entries.get("delivery_country"),
            trip.get("delivery_country", ""),
        )
        self._set_entry(
            self._cmr_entries.get("place_of_loading"),
            trip.get("place_of_loading",
                     trip.get("loading_address", trip.get("origin", ""))),
        )
        self._set_entry(
            self._cmr_entries.get("place_of_loading_date"),
            trip.get("place_of_loading_date", trip.get("start_date", "")),
        )
        self._set_entry(
            self._cmr_entries.get("loading_country"),
            trip.get("loading_country", ""),
        )
        self._set_entry(
            self._cmr_entries.get("documents_attached"),
            trip.get("documents_attached", ""),
        )

        # Cargo
        self._set_entry(
            self._cmr_entries.get("cargo_marks"),
            trip.get("cargo_marks", ""),
        )
        self._set_entry(
            self._cmr_entries.get("cargo_description"),
            trip.get("cargo_description", ""),
        )
        self._set_entry(
            self._cmr_entries.get("package_count"),
            trip.get("package_count", ""),
        )
        self._set_entry(
            self._cmr_entries.get("package_type"),
            trip.get("package_type", ""),
        )
        self._set_entry(
            self._cmr_entries.get("gross_weight_kg"),
            trip.get("gross_weight_kg", ""),
        )
        self._set_entry(
            self._cmr_entries.get("volume_m3"),
            trip.get("volume_m3", ""),
        )
        self._set_entry(
            self._cmr_entries.get("hs_code"),
            trip.get("hs_code", ""),
        )
        self._set_entry(
            self._cmr_entries.get("carrier_reservations"),
            trip.get("carrier_reservations", ""),
        )
        self._set_entry(
            self._cmr_entries.get("carrier_instructions"),
            trip.get("carrier_instructions", ""),
        )

        # Payment
        payer = trip.get("carriage_payer", "")
        payer_w = self._cmr_entries.get("carriage_payer")
        if payer_w and payer in ["Sender", "Consignee"]:
            idx = payer_w.findText(payer)
            if idx >= 0:
                payer_w.setCurrentIndex(idx)

        # Special agreements
        self._set_entry(
            self._cmr_entries.get("special_agreements"),
            trip.get("special_agreements", ""),
        )

        # COD & Issue
        self._set_entry(
            self._cmr_entries.get("cod_amount"),
            trip.get("cod_amount", ""),
        )
        self._set_entry(
            self._cmr_entries.get("distance_km"),
            trip.get("distance_km", ""),
        )
        self._set_entry(
            self._cmr_entries.get("issue_place"),
            trip.get("issue_place", conf.get("address", "")),
        )
        self._set_entry(
            self._cmr_entries.get("issue_date"),
            trip.get("issue_date", ""),
        )

        # Signature paths from config
        sig_path = conf.get("signature_path", "")
        for k in ["sender", "carrier"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None and sig_path:
                pad.set_path(sig_path)

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def get_bottom_frame(self) -> Optional[QWidget]:
        """Return the bottom action bar for adding additional controls.

        Parent views can pack their controls here so they scroll with the form.
        """
        return getattr(self, "_bottom_bar", None) or self

    def clear(self):
        """Reset all form fields to their default / empty state."""
        for _, widget in self._cmr_entries.items():
            try:
                if isinstance(widget, StyledTextEdit):
                    widget.clear()
                elif isinstance(widget, StyledComboBox):
                    widget.setCurrentIndex(0)
                elif isinstance(widget, StyledLineEdit):
                    widget.clear()
                elif isinstance(widget, QDateEdit):
                    widget.setDate(QDate.currentDate())
            except Exception:
                pass

        for row in self._adr_rows:
            row.deleteLater()
        self._adr_rows.clear()

        for row in self._successive_carrier_rows:
            row.deleteLater()
        self._successive_carrier_rows.clear()

        self._adr_toggle.setChecked(False)
        self._adr_content_wrapper.setVisible(False)

        for k in ["sender", "carrier", "consignee"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None:
                pad._clear()

        self._consignor_role_active = True
        self._update_role_buttons()
        self._last_trip_data = None

    def _set_entry(self, widget: Optional[QWidget], value: Any):
        """Set the value of a form widget, handling different widget types."""
        if widget is None:
            return
        str_val = str(value) if value is not None else ""

        if isinstance(widget, StyledTextEdit):
            widget.clear()
            if str_val:
                widget.setPlainText(str_val)
        elif isinstance(widget, StyledComboBox):
            idx = widget.findText(str_val)
            if idx >= 0:
                widget.setCurrentIndex(idx)
            else:
                widget.setCurrentIndex(0)
        elif isinstance(widget, QDateEdit):
            if str_val:
                try:
                    qd = QDate.fromString(str_val, "yyyy-MM-dd")
                    if qd.isValid():
                        widget.setDate(qd)
                except Exception:
                    pass
        elif isinstance(widget, StyledLineEdit):
            widget.setText(str_val)

    # ══════════════════════════════════════════════════════════════════════
    # Data export
    # ══════════════════════════════════════════════════════════════════════

    def get_data(self) -> Dict[str, Any]:
        """Collect all form fields into a flat dict for the CMR generator.

        Returns a dict compatible with ``CMRGenerator.generate()`` /
        ``generate_all_copies()``.
        """
        data: Dict[str, Any] = {}
        for key, widget in self._cmr_entries.items():
            if isinstance(widget, StyledLineEdit):
                data[key] = widget.text()
            elif isinstance(widget, StyledTextEdit):
                data[key] = widget.toPlainText()
            elif isinstance(widget, QDateEdit):
                data[key] = widget.date().toString("yyyy-MM-dd")
            elif isinstance(widget, QCheckBox):
                data[key] = widget.isChecked()

        data["generating_role"] = "consignor" if self._consignor_role_active else "consignee"

        # Role-based autofill: fill in company name/address based on role
        if self._last_trip_data:
            conf = self._last_trip_data.get("company_conf") or {}
            if self._consignor_role_active and not data.get("consignor_name"):
                data["consignor_name"] = conf.get("company_name", "")
                data["consignor_address"] = conf.get("address", "")
                data["consignor_vat"] = conf.get("cui", "")
                data["consignor_phone"] = conf.get("phone", "")
                data["consignor_eori"] = ""
                data["client_name"] = data.get("consignee_name", "")
                data["client_address"] = data.get("consignee_address", "")
            else:
                data["consignor_name"] = data.get("consignor_name", "")
                data["consignor_address"] = data.get("consignor_address", "")
                data["client_name"] = data.get("consignor_name", "")
                data["client_address"] = data.get("consignor_address", "")
                data["consignee_name"] = conf.get("company_name", "")
                data["consignee_address"] = conf.get("address", "")
                data["consignee_vat"] = conf.get("cui", "")
                data["consignee_phone"] = conf.get("phone", "")

        # Signature pad paths
        sig_pad_keys = [
            ("sig_sender_path", "Sender"),
            ("sig_carrier_path", "Carrier"),
            ("sig_consignee_path", "Consignee"),
        ]
        for data_key, _ in sig_pad_keys:
            if data_key in self._cmr_entries:
                pad = self._cmr_entries[data_key]
                if hasattr(pad, "save_path") and pad.save_path:
                    data[data_key] = pad.save_path
                elif hasattr(pad, "image_path") and pad.image_path:
                    data[data_key] = pad.image_path

        # ADR rows
        adr_entries = []
        try:
            for row_data in self._adr_rows:
                row_dict: Dict[str, Any] = {}
                for k, w in row_data.items():
                    if isinstance(w, StyledLineEdit):
                        row_dict[k] = w.text()
                adr_entries.append(row_dict)
        except AttributeError:
            pass
        if adr_entries:
            data["adr_info_json"] = json.dumps(adr_entries)

        # Successive carriers
        successive = []
        try:
            for row_data in self._successive_rows:
                row_dict = {}
                for k, w in row_data.items():
                    if isinstance(w, StyledLineEdit):
                        row_dict[k] = w.text()
                successive.append(row_dict)
        except AttributeError:
            pass
        if successive:
            data["successive_carriers_json"] = json.dumps(successive)

        # Financial grid (Box 20)
        financial = {}
        for key in ["sender_carriage", "consignee_carriage",
                     "sender_supplementary", "consignee_supplementary",
                     "sender_customs", "consignee_customs",
                     "sender_other", "consignee_other"]:
            w = self._cmr_entries.get(key)
            if w is not None:
                financial[key] = w.text() if hasattr(w, "text") else str(w)
        if financial:
            data["financial_grid"] = financial

        # Truck/driver fields from CMR boxes
        data["truck_plate"] = data.get("truck_plate", "")
        data["driver_name"] = data.get("driver_name", "")

        # Place and country fields
        data["place_of_loading"] = data.get("place_of_loading", "")
        data["destination"] = data.get("destination", "")
        data["loading_country"] = data.get("loading_country", "")
        data["delivery_country"] = data.get("delivery_country", "")
        data["distance_km"] = data.get("distance_km", "")

        return data

    # ══════════════════════════════════════════════════════════════════════
    # i18n
    # ══════════════════════════════════════════════════════════════════════

    def _on_language_changed(self, lang: str) -> None:
        """React to language changes.

        Currently a no-op placeholder — the form is built once with English
        labels.  In a future iteration, translatable labels should be refreshed
        here.
        """
        pass

    # ══════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════════════

    def wakeup(self) -> None:
        """Register i18n listener; called when the view becomes active."""
        if not getattr(self, "_listener_registered", False):
            register_listener(self._language_callback)
            self._listener_registered = True

    def shutdown(self) -> None:
        """Unregister i18n listener; called when the view is discarded."""
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        self._listener_registered = False
