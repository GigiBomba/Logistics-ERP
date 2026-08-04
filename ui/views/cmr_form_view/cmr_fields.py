"""PySide6 CMR form view — field group builders (section cards).

Split from ``cmr_form_view.py``.  Provides ``CmrFieldsMixin`` used by
``QtCmrFormView``.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Divider
from ui.design_tokens import (
    ACCENT_TEXT,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    SP,
)
from ui.widgets import StyledLineEdit
from ui.widgets.signature_pad import QtSignaturePad


class CmrFieldsMixin:
    """Mixin providing all ``_build_*_card`` section-building methods.

    Intended for use alongside ``QtCmrFormView``; relies on ``self`` having
    the instance attributes set up in ``QtCmrFormView.__init__``.
    """

    # ── Section: Parties (Boxes 1, 2) ──────────────────────────────────────

    def _build_parties_card(self, content=None):
        if content is None:
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
            kind="textbox", height=90, required=True,
            placeholder=t("cmr.consignor_placeholder", "Nume, adresa, tara"),
        )
        self._cmr_entries["consignee_name"] = self._box_field(
            right, 2,
            t("cmr.consignee", "Consignee"),
            t("cmr.consignee_ro", "Destinatar"),
            kind="textbox", height=90, required=True,
            placeholder=t("cmr.consignee_placeholder", "Nume, adresa, tara"),
        )

    # ── Section: Route & Documents (Boxes 3, 4, 5) ─────────────────────────

    def _build_route_card(self, content=None):
        if content is None:
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
            required=True,
            placeholder=t("cmr.locality_country", "Locality, Country"),
        )

        # Box 4: Place of delivery
        self._cmr_entries["destination"] = self._box_field(
            right, 4,
            t("cmr.destination", "Place of Delivery"),
            t("cmr.destination_ro", "Locul Livrarii"),
            required=True,
            placeholder=t("cmr.locality_country", "Locality, Country"),
        )

        # Date row for Box 3
        date_container = QWidget()
        date_layout = QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(SP["2"])

        date_label = QLabel(t("cmr.date", "Date:"))
        date_label.setProperty("fontRole", "small")
        date_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        date_layout.addWidget(date_label)

        wld = QDateEdit()
        wld.setDisplayFormat("yyyy-MM-dd")
        wld.setCalendarPopup(True)
        wld.setDate(QDate.currentDate())
        wld.setFixedHeight(32)
        wld.setStyleSheet(
            f"background-color: {COLOR_BG_OVERLAY};"
            f"color: {COLOR_TEXT_PRIMARY};"
            f"border: 1px solid {COLOR_BORDER_SUBTLE};"
            f"border-radius: 4px; padding: 2px 6px;"
        )
        date_layout.addWidget(wld, 1)

        left.layout().addWidget(date_container)
        self._cmr_entries["place_of_loading_date"] = wld

        # ISO country fields for Box 3 / 4
        iso_container = QWidget()
        iso_layout = QHBoxLayout(iso_container)
        iso_layout.setContentsMargins(0, 0, 0, 0)
        iso_layout.setSpacing(SP["3"])

        wlc = StyledLineEdit(height=32)
        wlc.setFixedWidth(60)
        wlc.setMaxLength(2)
        iso_layout.addWidget(self._field_widget(
            iso_container,
            t("cmr.loading_country", "Loading Country ISO:"),
            wlc,
        ))

        wdc = StyledLineEdit(height=32)
        wdc.setFixedWidth(60)
        wdc.setMaxLength(2)
        iso_layout.addWidget(self._field_widget(
            iso_container,
            t("cmr.delivery_country", "Delivery Country ISO:"),
            wdc,
        ))

        iso_layout.addStretch()
        left.layout().addWidget(iso_container)
        self._cmr_entries["loading_country"] = wlc
        self._cmr_entries["delivery_country"] = wdc

        # Box 5: Documents attached
        self._cmr_entries["documents_attached"] = self._box_field(
            right, 5,
            t("cmr.documents", "Documents Attached"),
            t("cmr.documents_ro", "Documente Atasate"),
            kind="textbox", height=90,
            placeholder=t("cmr.documents_placeholder", "Listati documentele atasate"),
        )

    # ── Section: Vehicle & Driver ──────────────────────────────────────────

    def _build_vehicle_card(self, content=None):
        if content is None:
            content = self._section_card(
                t("cmr.section_vehicle", "Vehicle & Driver"),
                t("cmr.section_vehicle_sub", "Transport means and driver information"),
            )
        left, right = self._two_col_pane(content)

        self._cmr_entries["truck_plate"] = self._field_widget(
            left, t("cmr.truck_plate", "Truck Plate / Numar Camion"),
            StyledLineEdit(left, height=38),
        )
        self._cmr_entries["driver_name"] = self._field_widget(
            left, t("cmr.driver_name", "Driver / Sofer"),
            StyledLineEdit(left, height=38),
        )
        self._cmr_entries["trailer_plate"] = self._field_widget(
            right, t("cmr.trailer_plate", "Trailer Plate / Numar Remorca"),
            StyledLineEdit(right, height=38),
        )
        self._cmr_entries["driver_license"] = self._field_widget(
            right, t("cmr.driver_license", "License / Permis"),
            StyledLineEdit(right, height=38),
        )

    # ── Section: Goods (Boxes 6–12) ────────────────────────────────────────

    def _build_cargo_card(self, content=None):
        if content is None:
            content = self._section_card(
                t("cmr.section_cargo", "Goods Specifications"),
                t("cmr.section_cargo_sub",
                  "Boxes 6 to 12 — Cargo details, weight, volume and HS code"),
            )

        # Row 1: Boxes 6–9
        r1 = QWidget()
        r1_layout = QHBoxLayout(r1)
        r1_layout.setContentsMargins(0, 0, 0, 0)
        r1_layout.setSpacing(SP["3"])

        self._cmr_entries["cargo_marks"] = self._compact_box(r1, 6, "Marks & Numbers", 0)
        self._cmr_entries["package_count"] = self._compact_box(r1, 7, "No. of Packages", 1)
        self._cmr_entries["package_type"] = self._compact_box(r1, 8, "Method of Packing", 2)
        self._cmr_entries["cargo_description"] = self._compact_box(r1, 9, "Nature of Goods *", 3)

        content.layout().addWidget(r1)

        # Row 2: Boxes 10–12
        r2 = QWidget()
        r2_layout = QHBoxLayout(r2)
        r2_layout.setContentsMargins(0, 0, 0, 0)
        r2_layout.setSpacing(SP["3"])

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
            f"color: {COLOR_TEXT_PRIMARY};"
            f"font-weight: bold;"
            f"spacing: 6px;"
        )
        self._adr_toggle.stateChanged.connect(self._on_adr_toggle)
        parent.layout().addWidget(self._adr_toggle)

        # Wrapper for ADR content (shown/hidden on toggle)
        self._adr_content_wrapper = QWidget()
        self._adr_content_wrapper.setVisible(False)
        adr_wrapper_layout = QVBoxLayout(self._adr_content_wrapper)
        adr_wrapper_layout.setContentsMargins(0, SP["2"], 0, 0)
        adr_wrapper_layout.setSpacing(SP["2"])

        self._adr_content = QWidget()
        self._adr_content_layout = QVBoxLayout(self._adr_content)
        self._adr_content_layout.setContentsMargins(0, 0, 0, 0)
        self._adr_content_layout.setSpacing(SP["2"])
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
        self._update_box_navigator()

    def _add_adr_row(self):
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        row.setStyleSheet(
            f"background-color: {COLOR_BG_OVERLAY};"
            f"border-radius: 4px;"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])
        row_layout.setSpacing(SP["2"])

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

    def _build_instructions_card(self, content=None):
        if content is None:
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
            kind="combobox", values=["", "Sender", "Consignee"],
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

    def _build_carrier_card(self, content=None):
        if content is None:
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
            kind="textbox", height=90, required=True,
        )

        # Box 19: Successive carriers
        sc_container = QWidget()
        sc_layout = QVBoxLayout(sc_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(SP["2"])

        sc_lbl_row = QWidget()
        sc_lbl_layout = QHBoxLayout(sc_lbl_row)
        sc_lbl_layout.setContentsMargins(0, 0, 0, 0)
        sc_lbl_layout.setSpacing(SP["2"])

        badge = QLabel("19")
        badge.setFixedSize(30, 20)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {COLOR_ACCENT_SUBTLE};"
            f"color: {ACCENT_TEXT};"
            f"border-radius: 4px; font-weight: bold; font-size: 10px;"
        )
        sc_lbl_layout.addWidget(badge)

        sc_lbl = QLabel(
            t("cmr.successive_carriers", "Successive Carriers / Transportatori Successivi")
        )
        sc_lbl.setProperty("fontRole", "label")
        sc_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        sc_lbl_layout.addWidget(sc_lbl)
        sc_lbl_layout.addStretch(1)

        sc_layout.addWidget(sc_lbl_row)

        self._succ_container = QWidget()
        self._succ_container_layout = QVBoxLayout(self._succ_container)
        self._succ_container_layout.setContentsMargins(0, 0, 0, 0)
        self._succ_container_layout.setSpacing(SP["2"])
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
            f"background-color: {COLOR_BG_OVERLAY};"
            f"border-radius: 4px;"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(SP["2"], SP["1"], SP["2"], SP["1"])
        row_layout.setSpacing(SP["2"])

        _labels = [
            t("cmr.label_name", default="Name"), t("cmr.label_address", default="Address"),
            t("cmr.label_country", default="Country"), t("cmr.label_plate", default="Plate"),
            t("cmr.label_trailer", default="Trailer"), t("cmr.label_driver", default="Driver"),
            t("cmr.label_from", default="From"), t("cmr.label_to", default="To"),
        ]
        for lbl in _labels:
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

    def _build_charges_card(self, content=None):
        if content is None:
            content = self._section_card(
                t("cmr.section_charges", "Box 20 — To Be Paid By"),
                t("cmr.section_charges_sub",
                  "Charges to be paid by the Sender or the Consignee"),
            )

        # Table header
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(SP["3"])

        cost_type_lbl = QLabel(t("cmr.cost_type", "Cost Type"))
        cost_type_lbl.setProperty("fontRole", "label")
        cost_type_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        hdr_layout.addWidget(cost_type_lbl, 2)

        sender_lbl = QLabel(t("cmr.sender", "Sender"))
        sender_lbl.setProperty("fontRole", "label")
        sender_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        sender_lbl.setAlignment(Qt.AlignRight)
        hdr_layout.addWidget(sender_lbl, 1)

        consignee_lbl = QLabel(t("cmr.consignee_short", "Consignee"))
        consignee_lbl.setProperty("fontRole", "label")
        consignee_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
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
        row_layout.setSpacing(SP["3"])

        lbl = QLabel(label)
        lbl.setProperty("fontRole", "small")
        lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
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

    def _build_issue_signatures_card(self, content=None):
        if content is None:
            content = self._section_card(
                t("cmr.section_issue", "Issue & Signatures"),
                t("cmr.section_issue_sub",
                  "Boxes 21 to 24 — Place/date of issue and party signatures"),
            )

        # Box 21: Established in
        b21 = QWidget()
        b21_layout = QVBoxLayout(b21)
        b21_layout.setContentsMargins(0, 0, 0, 0)
        b21_layout.setSpacing(SP["1"])

        b21_lbl_row = QWidget()
        b21_lbl_layout = QHBoxLayout(b21_lbl_row)
        b21_lbl_layout.setContentsMargins(0, 0, 0, 0)
        b21_lbl_layout.setSpacing(SP["2"])

        badge21 = QLabel("21")
        badge21.setFixedSize(30, 20)
        badge21.setAlignment(Qt.AlignCenter)
        badge21.setStyleSheet(
            f"background-color: {COLOR_ACCENT_SUBTLE};"
            f"color: {ACCENT_TEXT};"
            f"border-radius: 4px; font-weight: bold; font-size: 10px;"
        )
        b21_lbl_layout.addWidget(badge21)

        b21_title = QLabel(
            t("cmr.established_in", "Established in / Intocmit in")
        )
        b21_title.setProperty("fontRole", "label")
        b21_title.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        b21_lbl_layout.addWidget(b21_title)
        b21_lbl_layout.addStretch(1)

        b21_layout.addWidget(b21_lbl_row)

        # Row with place + date
        row21 = QWidget()
        row21_layout = QHBoxLayout(row21)
        row21_layout.setContentsMargins(0, 0, 0, 0)
        row21_layout.setSpacing(SP["3"])

        place_col = QWidget()
        place_col_layout = QVBoxLayout(place_col)
        place_col_layout.setContentsMargins(0, 0, 0, 0)
        place_col_layout.setSpacing(SP["1"])
        place_label = QLabel(t("cmr.place", "Place:"))
        place_label.setProperty("fontRole", "small")
        place_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        place_col_layout.addWidget(place_label)
        self._cmr_entries["issue_place"] = StyledLineEdit(
            place_col, placeholder=t("cmr.city_country", "City, Country"), height=32,
        )
        place_col_layout.addWidget(self._cmr_entries["issue_place"])
        row21_layout.addWidget(place_col, 1)

        date_col = QWidget()
        date_col_layout = QVBoxLayout(date_col)
        date_col_layout.setContentsMargins(0, 0, 0, 0)
        date_col_layout.setSpacing(SP["1"])
        date_label = QLabel(t("cmr.date", "Date:"))
        date_label.setProperty("fontRole", "small")
        date_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        date_col_layout.addWidget(date_label)
        w21d = QDateEdit()
        w21d.setDisplayFormat("yyyy-MM-dd")
        w21d.setCalendarPopup(True)
        w21d.setDate(QDate.currentDate())
        w21d.setFixedHeight(32)
        w21d.setStyleSheet(
            f"background-color: {COLOR_BG_OVERLAY};"
            f"color: {COLOR_TEXT_PRIMARY};"
            f"border: 1px solid {COLOR_BORDER_SUBTLE};"
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
        sig_layout.setSpacing(SP["3"])

        sig_specs = [
            (22, t("cmr.sig_sender", "Signature of Sender"), "sender"),
            (23, t("cmr.sig_carrier", "Signature of Carrier"), "carrier"),
            (24, t("cmr.sig_consignee", "Signature of Consignee"), "consignee"),
        ]

        for _col_i, (num, label_text, key) in enumerate(sig_specs):
            col = QWidget()
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(SP["1"])

            # Badge + label
            sig_lbl_row = QWidget()
            sig_lbl_layout = QHBoxLayout(sig_lbl_row)
            sig_lbl_layout.setContentsMargins(0, 0, 0, 0)
            sig_lbl_layout.setSpacing(SP["1"])

            sig_badge = QLabel(str(num))
            sig_badge.setFixedSize(26, 18)
            sig_badge.setAlignment(Qt.AlignCenter)
            sig_badge.setStyleSheet(
                f"background-color: {COLOR_ACCENT_SUBTLE};"
                f"color: {ACCENT_TEXT};"
                f"border-radius: 3px; font-weight: bold; font-size: 8px;"
            )
            sig_lbl_layout.addWidget(sig_badge)

            sig_lbl = QLabel(label_text)
            sig_lbl.setProperty("fontRole", "label")
            sig_lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
            sig_lbl_layout.addWidget(sig_lbl)
            sig_lbl_layout.addStretch(1)

            col_layout.addWidget(sig_lbl_row)

            pad = QtSignaturePad(col, label="")
            col_layout.addWidget(pad)
            setattr(self, f"sig_{key}_pad", pad)

            sig_layout.addWidget(col, 1)

        content.layout().addWidget(sig_row)

    # ── Internal: field widget helper (replaces ui.widgets.field) ──────────

    def _field_widget(self, parent: QWidget, label_text: str, widget: QWidget) -> QWidget:
        """Build a labelled field row (inline copy of ``ui.widgets.field``)."""
        from ui.widgets import field as _field
        return _field(parent, label_text, widget)
