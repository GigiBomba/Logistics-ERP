"""Generators workspace — unified Invoice + CMR document generation UI."""
import json
import logging
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from ui.theme import COLORS, FONTS, S
from services.i18n import t
from services.trip_service import TripService

logger = logging.getLogger(__name__)

PACKAGE_TYPES = ["Pallet", "Carton", "Drum", "Big Bag", "Bulk", "Other"]
PAYER_OPTIONS = ["sender", "consignee"]


class GeneratorsView(ctk.CTkFrame):
    def __init__(self, parent, db, prefs=None, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.db = db
        self.prefs = prefs
        self._frame = self
        self._trip_service = TripService(db)
        self._cmr_doc_service = None
        self._trips_list = []
        self._trip_map = {}
        self._cmr_copies = {}
        self._cmr_last_paths = {}
        self._adr_rows = []
        self._successive_carrier_frames = []
        self._cmr_filled_trip_id = None
        self._build()

    @property
    def frame(self):
        return self._frame

    def wakeup(self):
        self._refresh_trip_lists()

    def _lazy_cmr_doc_service(self):
        if self._cmr_doc_service is None:
            from services.document_service import DocumentService
            self._cmr_doc_service = DocumentService(self.db)
        return self._cmr_doc_service

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tabview = ctk.CTkTabview(
            self,
            fg_color=COLORS["bg_base"],
            segmented_button_fg_color=COLORS["bg_surface"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_unselected_color=COLORS["bg_surface"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
        )
        self._tabview.grid(row=0, column=0, sticky="nsew", padx=S["4"], pady=S["4"])

        self._tabview.add(t("generators.tab_invoice"))
        self._tabview.add(t("generators.tab_cmr"))

        self._build_invoice_tab()
        self._build_cmr_tab()

    def _build_invoice_tab(self):
        tab = self._tabview.tab(t("generators.tab_invoice"))
        from ui.invoice_editor import InvoiceEditor
        self._invoice_tab = InvoiceEditor(tab, self.db, prefs=self.prefs)
        self._invoice_tab.frame.pack(fill="both", expand=True)

    # ═══════════════════════════════════════════════════════════════
    # CMR Tab — Professional logistics-grade CMR generator
    # ═══════════════════════════════════════════════════════════════

    def _build_cmr_tab(self):
        tab = self._tabview.tab(t("generators.tab_cmr"))
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=0)
        tab.rowconfigure(1, weight=1)

        # ── Header row: title + trip selector ──
        hdr = ctk.CTkFrame(tab, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(S["4"], S["2"]))
        hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="\U0001F4C4 " + t("generators.cmr_title"),
                     font=FONTS["h2"], text_color=COLORS["text_primary"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        trip_f = ctk.CTkFrame(hdr, fg_color="transparent")
        trip_f.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(trip_f, text="Trip:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._cmr_trip_combo = ctk.CTkComboBox(
            trip_f, values=[], state="readonly", width=280,
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            command=self._on_cmr_trip_selected)
        self._cmr_trip_combo.pack(side="left", padx=(S["1"], S["1"]))
        ctk.CTkButton(trip_f, text="\U0001F504", width=32, height=32,
                      fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"], font=FONTS["body"],
                      command=self._refresh_trip_lists).pack(side="left")

        self._cmr_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_fg_color=COLORS["bg_surface"])
        self._cmr_scroll.grid(row=1, column=0, sticky="nsew")
        self._cmr_scroll.columnconfigure(0, weight=1)

        # Sections ordered to match the CMR convention form layout
        self._build_box_1_2(self._cmr_scroll)
        self._build_box_6_12_adr(self._cmr_scroll)
        self._build_box_3_4(self._cmr_scroll)
        self._build_box_5_13(self._cmr_scroll)
        self._build_box_16_18(self._cmr_scroll)
        self._build_box_17_19(self._cmr_scroll)
        self._build_box_14_18_20(self._cmr_scroll)
        self._build_signature_section(self._cmr_scroll)
        self._build_language_section(self._cmr_scroll)
        self._build_generation_section(self._cmr_scroll)
        self._build_copies_section(self._cmr_scroll)

        self._refresh_trip_lists()

    def _section_card(self, parent, accent_color=None):
        """Modern card with optional colored left accent border."""
        accent = accent_color or COLORS["accent"]
        outer = ctk.CTkFrame(parent, fg_color=accent, corner_radius=10)
        outer.pack(fill="x", pady=(0, S["4"]))
        # Inner card with left margin to create accent stripe effect
        card = ctk.CTkFrame(outer, fg_color=COLORS["bg_surface"], corner_radius=0)
        card.pack(fill="both", expand=True, padx=(3, 0))
        return card

    def _section_label(self, parent, text, icon=""):
        """Unified section header with box number and label (matches PDF headers)."""
        lbl = ctk.CTkLabel(parent, text=f"{icon}  {text}" if icon else text,
                           font=FONTS["label"],
                           text_color=COLORS["text_primary"],
                           anchor="w")
        lbl.pack(anchor="w", padx=S["4"], pady=(S["4"], S["1"]))

    def _two_col(self, parent):
        """Create a 2-column layout frame. Returns (cols_frame, left_frame, right_frame)."""
        cols = ctk.CTkFrame(parent, fg_color="transparent")
        cols.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)
        left = ctk.CTkFrame(cols, fg_color="transparent")
        left.grid(row=0, column=0, sticky="new", padx=(0, S["2"]))
        right = ctk.CTkFrame(cols, fg_color="transparent")
        right.grid(row=0, column=1, sticky="new")
        return cols, left, right

    def _lbl(self, parent, text):
        """Small, muted label for field description."""
        ctk.CTkLabel(parent, text=text, font=FONTS["small"],
                     text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")

    def _entry(self, parent, placeholder="", height=32):
        e = ctk.CTkEntry(parent, placeholder_text=placeholder,
                         fg_color=COLORS["bg_input"],
                         border_color=COLORS["border"],
                         text_color=COLORS["text_primary"],
                         font=FONTS["body"], height=height)
        return e

    def _field_row(self, parent, label_text, entry_ref_name=None,
                   width=100, entry_height=32):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=S["4"], pady=(0, S["2"]))
        ctk.CTkLabel(row, text=label_text, font=FONTS["body"],
                     text_color=COLORS["text_secondary"],
                     anchor="w", width=width).pack(side="left")
        entry = ctk.CTkEntry(
            row, fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONTS["body"], height=entry_height,
        )
        entry.pack(side="left", fill="x", expand=True)
        if entry_ref_name:
            setattr(self, entry_ref_name, entry)
        return entry

    # ── Language Selectors ──────────────────────────────────────────

    def _build_language_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(card, "CMR Languages / Limbi CMR")
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        lang_codes = self.prefs.get_available_languages() if self.prefs else ["en", "ro"]
        lang_display = []
        for c in lang_codes:
            try:
                dn = self.prefs.get_language_display_name(c) if self.prefs else c
                lang_display.append(f"{dn} ({c})")
            except Exception:
                lang_display.append(c)
        ctk.CTkLabel(f, text="Primary:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._cmr_lang1 = ctk.CTkComboBox(f, values=lang_display, state="readonly",
                                          width=160, font=FONTS["body"],
                                          fg_color=COLORS["bg_input"],
                                          border_color=COLORS["border"],
                                          button_color=COLORS["bg_elevated"],
                                          text_color=COLORS["text_primary"])
        self._cmr_lang1.pack(side="left", padx=(S["1"], S["3"]))
        if lang_display:
            self._cmr_lang1.set(lang_display[0])
        ctk.CTkLabel(f, text="Secondary:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._cmr_lang2 = ctk.CTkComboBox(f, values=lang_display, state="readonly",
                                          width=160, font=FONTS["body"],
                                          fg_color=COLORS["bg_input"],
                                          border_color=COLORS["border"],
                                          button_color=COLORS["bg_elevated"],
                                          text_color=COLORS["text_primary"])
        self._cmr_lang2.pack(side="left", padx=(S["1"], 0))
        if len(lang_display) > 1:
            self._cmr_lang2.set(lang_display[1])

    # ═══════════════════════════════════════════════════════════════
    # CMR convention form sections (box-number order)
    # ═══════════════════════════════════════════════════════════════

    # ── Box 1: Consignor + Box 2: Consignee ────────────────────────

    def _build_box_1_2(self, parent):
        card = self._section_card(parent, accent_color=COLORS["success"])
        self._section_label(card, "1. CONSIGNOR / EXPEDITOR                   2. CONSIGNEE / DESTINATAR")
        cols, left, right = self._two_col(card)
        self._cmr_consignor_name = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Name")
        self._cmr_consignor_name.pack(fill="x", pady=(0, S["1"]))
        self._cmr_consignor_addr = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Address")
        self._cmr_consignor_addr.pack(fill="x", pady=(0, S["1"]))
        r1 = ctk.CTkFrame(left, fg_color="transparent")
        r1.pack(fill="x", pady=(0, S["1"]))
        self._lbl(r1, "VAT")
        self._cmr_consignor_vat = ctk.CTkEntry(r1, width=80, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignor_vat.pack(side="left", padx=(0, S["1"]))
        self._lbl(r1, "EORI")
        self._cmr_consignor_eori = ctk.CTkEntry(r1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignor_eori.pack(side="left", fill="x", expand=True)
        self._cmr_consignor_phone = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Phone")
        self._cmr_consignor_phone.pack(fill="x")
        self._cmr_consignee_name = ctk.CTkEntry(right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Name")
        self._cmr_consignee_name.pack(fill="x", pady=(0, S["1"]))
        self._cmr_consignee_addr = ctk.CTkEntry(right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Address")
        self._cmr_consignee_addr.pack(fill="x", pady=(0, S["1"]))
        r2 = ctk.CTkFrame(right, fg_color="transparent")
        r2.pack(fill="x", pady=(0, S["1"]))
        self._lbl(r2, "VAT")
        self._cmr_consignee_vat = ctk.CTkEntry(r2, width=80, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_vat.pack(side="left", padx=(0, S["1"]))
        self._lbl(r2, "EORI")
        self._cmr_consignee_eori = ctk.CTkEntry(r2, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_eori.pack(side="left", fill="x", expand=True)
        self._cmr_consignee_contact = ctk.CTkEntry(right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Contact Person")
        self._cmr_consignee_contact.pack(fill="x")

    # ── Boxes 6-12: Cargo + ADR ────────────────────────────────────

    def _build_box_6_12_adr(self, parent):
        card = self._section_card(parent, accent_color=COLORS["warning"])
        self._section_label(card, "6-12. CARGO / MARFA  |  ADR - DANGEROUS GOODS / MARFURI PERICULOASE")
        f = ctk.CTkFrame(card, fg_color="transparent")
        f.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        self._lbl(f, "6. Marks & Numbers")
        self._cmr_marks = ctk.CTkEntry(f, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_marks.pack(fill="x", pady=(0, S["2"]))
        row1 = ctk.CTkFrame(f, fg_color="transparent")
        row1.pack(fill="x", pady=(0, S["1"]))
        row1.columnconfigure((0, 1, 2, 3), weight=1)
        self._cmr_package_count = ctk.CTkEntry(row1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="7. Package Count")
        self._cmr_package_count.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._cmr_package_type = ctk.CTkComboBox(row1, values=PACKAGE_TYPES,
            state="readonly", font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"], height=28)
        self._cmr_package_type.grid(row=0, column=1, sticky="ew", padx=(0, S["1"]))
        self._cmr_package_type.set("Pallet")
        self._cmr_weight = ctk.CTkEntry(row1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="11. Weight (kg)")
        self._cmr_weight.grid(row=0, column=2, sticky="ew", padx=(0, S["1"]))
        self._cmr_volume = ctk.CTkEntry(row1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="12. Volume (m\u00b3)")
        self._cmr_volume.grid(row=0, column=3, sticky="ew")
        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill="x", pady=(0, S["2"]))
        row2.columnconfigure(0, weight=2)
        row2.columnconfigure(1, weight=1)
        d_col = ctk.CTkFrame(row2, fg_color="transparent")
        d_col.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._lbl(d_col, "9. Nature of Goods")
        self._cmr_cargo_desc = ctk.CTkTextbox(d_col, height=50,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_cargo_desc.pack(fill="x")
        h_col = ctk.CTkFrame(row2, fg_color="transparent")
        h_col.grid(row=0, column=1, sticky="nsew")
        self._lbl(h_col, "10. HS Code")
        self._cmr_hs_code = ctk.CTkEntry(h_col, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_hs_code.pack(fill="x")
        self._lbl(f, "8. Kind (Package Type)")
        sep = ctk.CTkFrame(f, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x", pady=(S["2"], S["2"]))
        adr_hdr = ctk.CTkFrame(f, fg_color="transparent")
        adr_hdr.pack(fill="x")
        self._adr_toggle_var = tk.BooleanVar(value=False)
        self._adr_toggle = ctk.CTkCheckBox(
            adr_hdr, text="\u26A0 This shipment contains DANGEROUS GOODS (ADR)",
            variable=self._adr_toggle_var, command=self._on_adr_toggle,
            font=FONTS["body"], text_color=COLORS["text_primary"],
            fg_color=COLORS["danger"],
            hover_color=COLORS.get("danger_hover", COLORS["danger"]))
        self._adr_toggle.pack(side="left")
        self._adr_content = ctk.CTkFrame(f, fg_color="transparent")
        self._adr_add_btn = ctk.CTkButton(
            f, text="+ Add ADR Row", font=FONTS["body"],
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"], height=28, command=self._add_adr_row)

    # ── Box 3: Loading + Box 4: Delivery ───────────────────────────

    def _build_box_3_4(self, parent):
        card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(card, "3. PLACE OF TAKING OVER / LOCUL PREDARII          4. PLACE OF DELIVERY / LOCUL LIVRARII")
        cols, left, right = self._two_col(card)
        self._lbl(left, "Place")
        self._cmr_loading = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_loading.pack(fill="x", pady=(0, S["1"]))
        lr = ctk.CTkFrame(left, fg_color="transparent")
        lr.pack(fill="x")
        self._cmr_loading_date = ctk.CTkEntry(lr, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Date")
        self._cmr_loading_date.pack(side="left", fill="x", expand=True, padx=(0, S["1"]))
        self._cmr_loading_country = ctk.CTkEntry(lr, width=50, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="ISO")
        self._cmr_loading_country.pack(side="left")
        self._lbl(lr, "Date / Country ISO")
        self._lbl(right, "Place")
        self._cmr_unloading = ctk.CTkEntry(right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_unloading.pack(fill="x", pady=(0, S["1"]))
        dr = ctk.CTkFrame(right, fg_color="transparent")
        dr.pack(fill="x")
        self._cmr_delivery_country = ctk.CTkEntry(dr, width=50, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="ISO")
        self._cmr_delivery_country.pack(side="left")
        self._lbl(dr, "Country ISO")

    # ── Box 5: Documents + Box 13: Instructions ────────────────────

    def _build_box_5_13(self, parent):
        card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(card, "5. DOCUMENTS ATTACHED / DOCUMENTE ATASATE          13. SENDER\u2019S INSTRUCTIONS / INSTRUCTIUNI")
        cols, left, right = self._two_col(card)
        self._cmr_docs_text = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"],
            placeholder_text="e.g. Invoice, Packing list, CMR")
        self._cmr_docs_text.pack(fill="x")
        self._cmr_instructions = ctk.CTkTextbox(right, height=60,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_instructions.pack(fill="x")

    # ── Box 16: Carrier + Box 18: Reservations ─────────────────────

    def _build_box_16_18(self, parent):
        card = self._section_card(parent, accent_color=COLORS["accent"])
        self._section_label(card, "16. CARRIER / TRANSPORTATOR          18. CARRIER\u2019S RESERVATIONS / REZERVE")
        cols, left, right = self._two_col(card)
        self._lbl(left, "Company Name")
        self._cmr_carrier_name = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_carrier_name.pack(fill="x", pady=(0, S["1"]))
        self._cmr_carrier_addr = ctk.CTkEntry(left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Address")
        self._cmr_carrier_addr.pack(fill="x", pady=(0, S["1"]))
        c1 = ctk.CTkFrame(left, fg_color="transparent")
        c1.pack(fill="x", pady=(0, S["1"]))
        c1.columnconfigure((0, 1), weight=1)
        self._cmr_carrier_phone = ctk.CTkEntry(c1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Phone")
        self._cmr_carrier_phone.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._cmr_carrier_email = ctk.CTkEntry(c1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Email")
        self._cmr_carrier_email.grid(row=0, column=1, sticky="ew")
        c2 = ctk.CTkFrame(left, fg_color="transparent")
        c2.pack(fill="x")
        c2.columnconfigure((0, 1), weight=1)
        self._cmr_carrier_reg = ctk.CTkEntry(c2, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Reg. Number")
        self._cmr_carrier_reg.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._cmr_insurance = ctk.CTkEntry(c2, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="CMR Insurance No.")
        self._cmr_insurance.grid(row=0, column=1, sticky="ew")
        self._cmr_reservations = ctk.CTkTextbox(right, height=80,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_reservations.pack(fill="x", expand=True)

    # ── Box 17: Successive + Box 19: Agreements ────────────────────

    def _build_box_17_19(self, parent):
        card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(card, "17. SUCCESSIVE CARRIERS / SUCCESIVI          19. SPECIAL AGREEMENTS / ACORDURI SPECIALE")
        cols, left, right = self._two_col(card)
        self._succ_content = ctk.CTkFrame(left, fg_color="transparent")
        self._succ_content.pack(fill="x", pady=(0, S["2"]))
        self._succ_add_btn = ctk.CTkButton(
            left, text="+ Add Successive Carrier", font=FONTS["body"],
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"], height=28,
            command=self._add_successive_carrier)
        self._succ_add_btn.pack(anchor="w")
        self._cmr_agreements = ctk.CTkTextbox(right, height=60,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_agreements.pack(fill="x")

    # ── Box 14: Charges + Box 18-20: Vehicle & Driver ──────────────

    def _build_box_14_18_20(self, parent):
        card = self._section_card(parent, accent_color=COLORS["warning"])
        self._section_label(card, "14. CARRIAGE CHARGES / TAXE DE TRANSPORT          18-20. VEHICLE & DRIVER / VEHICUL SI SOFER")
        cols, left, right = self._two_col(card)
        self._cmr_payer_var = tk.StringVar(value="")
        ctk.CTkLabel(left, text="Carriage charges paid by:",
                     font=FONTS["body"], text_color=COLORS["text_secondary"]).pack(anchor="w")
        pr = ctk.CTkFrame(left, fg_color="transparent")
        pr.pack(fill="x", pady=(S["1"], S["2"]))
        ctk.CTkRadioButton(pr, text="Sender", variable=self._cmr_payer_var,
                           value="sender", font=FONTS["body"],
                           text_color=COLORS["text_primary"],
                           fg_color=COLORS["accent"]).pack(side="left", padx=(0, S["2"]))
        ctk.CTkRadioButton(pr, text="Consignee", variable=self._cmr_payer_var,
                           value="consignee", font=FONTS["body"],
                           text_color=COLORS["text_primary"],
                           fg_color=COLORS["accent"]).pack(side="left")
        self._cmr_distance = ctk.CTkEntry(left, height=28, width=100,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"], placeholder_text="Distance (km)")
        self._cmr_distance.pack(anchor="w")

        v_row1 = ctk.CTkFrame(right, fg_color="transparent")
        v_row1.pack(fill="x")
        v_col1 = ctk.CTkFrame(v_row1, fg_color="transparent")
        v_col1.pack(fill="x")
        ctk.CTkLabel(v_col1, text="Vehicle Plate", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_vehicle = ctk.CTkEntry(v_col1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_vehicle.pack(fill="x")

        v_col2 = ctk.CTkFrame(right, fg_color="transparent")
        v_col2.pack(fill="x", pady=(S["1"], 0))
        ctk.CTkLabel(v_col2, text="Trailer Plate", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_trailer = ctk.CTkEntry(v_col2, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_trailer.pack(fill="x")

        d_row = ctk.CTkFrame(right, fg_color="transparent")
        d_row.pack(fill="x", pady=(S["1"], 0))
        d_col1 = ctk.CTkFrame(d_row, fg_color="transparent")
        d_col1.pack(fill="x")
        ctk.CTkLabel(d_col1, text="Driver Name", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_driver_name = ctk.CTkEntry(d_col1, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_driver_name.pack(fill="x")

        d_col2 = ctk.CTkFrame(right, fg_color="transparent")
        d_col2.pack(fill="x", pady=(S["1"], 0))
        ctk.CTkLabel(d_col2, text="Driver License", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_driver_license = ctk.CTkEntry(d_col2, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_driver_license.pack(fill="x")

    def _on_adr_toggle(self):
        if self._adr_toggle_var.get():
            self._adr_content.pack(fill="x", padx=S["4"], pady=(S["1"], S["2"]))
            self._adr_add_btn.pack(padx=S["4"], pady=(0, S["4"]), anchor="w")
            if not self._adr_rows:
                self._add_adr_row()
        else:
            self._adr_content.pack_forget()
            self._adr_add_btn.pack_forget()
            for f in self._adr_rows:
                f.destroy()
            self._adr_rows.clear()

    def _add_adr_row(self):
        row = ctk.CTkFrame(self._adr_content, fg_color="transparent")
        row.pack(fill="x", pady=(0, S["1"]))
        labels = ["UN No", "Class", "Pack. Grp", "Tunnel", "Qty", "Net Wt(kg)"]
        entries = {}
        for i, lbl in enumerate(labels):
            e = ctk.CTkEntry(row, width=70, height=24,
                placeholder_text=lbl,
                fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                text_color=COLORS["text_primary"], font=FONTS["body"])
            e.pack(side="left", padx=(0, S["1"]))
            entries[lbl] = e
        btn = ctk.CTkButton(row, text="X", width=24, height=24,
            fg_color=COLORS["danger"], hover_color=COLORS["danger"],
            text_color="#ffffff", font=FONTS["body"],
            command=lambda f=row: self._remove_adr_row(f))
        btn.pack(side="left")
        self._adr_rows.append(row)

    def _remove_adr_row(self, frame):
        frame.destroy()
        if frame in self._adr_rows:
            self._adr_rows.remove(frame)

    def _get_adr_data(self):
        if not self._adr_toggle_var.get():
            return None
        items = []
        for row in self._adr_rows:
            children = [c for c in row.winfo_children() if isinstance(c, ctk.CTkEntry)]
            if len(children) >= 6:
                items.append({
                    "un_no": children[0].get().strip(),
                    "adr_class": children[1].get().strip(),
                    "packing_group": children[2].get().strip(),
                    "tunnel_code": children[3].get().strip(),
                    "quantity": children[4].get().strip(),
                    "net_weight": children[5].get().strip(),
                })
        return items if items else None

    # ── Successive Carriers ─────────────────────────────────────────
    def _add_successive_carrier(self):
        row = ctk.CTkFrame(self._succ_content, fg_color=COLORS["bg_base"],
                           corner_radius=4)
        row.pack(fill="x", pady=(0, S["2"]))
        cols_frame = ctk.CTkFrame(row, fg_color="transparent")
        cols_frame.pack(fill="x", padx=S["2"], pady=S["2"])
        fields = {}
        for lbl in ["Name", "Address", "Country", "Plate", "Trailer", "Driver", "From", "To"]:
            e = ctk.CTkEntry(cols_frame, height=24, placeholder_text=lbl,
                fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                text_color=COLORS["text_primary"], font=FONTS["body"])
            e.pack(fill="x", pady=(0, S["1"]))
            fields[lbl] = e
        rm_btn = ctk.CTkButton(row, text="Remove", font=FONTS["small"],
            fg_color=COLORS["danger"], hover_color=COLORS["danger"],
            text_color="#ffffff", height=24,
            command=lambda f=row: self._remove_successive_carrier(f))
        rm_btn.pack(padx=S["2"], pady=(0, S["2"]))
        self._successive_carrier_frames.append(row)

    def _remove_successive_carrier(self, frame):
        frame.destroy()
        if frame in self._successive_carrier_frames:
            self._successive_carrier_frames.remove(frame)

    def _get_successive_carriers(self):
        result = []
        for frame in self._successive_carrier_frames:
            entries = [c for c in frame.winfo_children()[0].winfo_children()
                       if isinstance(c, ctk.CTkEntry)]
            if len(entries) >= 6:
                result.append({
                    "carrier_name": entries[0].get().strip(),
                    "carrier_address": entries[1].get().strip(),
                    "carrier_country": entries[2].get().strip(),
                    "vehicle_plate": entries[3].get().strip(),
                    "trailer_plate": entries[4].get().strip(),
                    "driver_name": entries[5].get().strip(),
                    "from_location": entries[6].get().strip() if len(entries) > 6 else "",
                    "to_location": entries[7].get().strip() if len(entries) > 7 else "",
                })
        return result

    # ── Signature Settings ──────────────────────────────────────────

    def _build_signature_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["accent"])
        self._section_label(card, "SIGNATURES / SEMNATURI  \u2502  Sender  \u2502  Carrier  \u2502  Consignee  \u2502  Stamp")
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=S["4"], pady=(S["1"], S["1"]))
        self._cmr_sig_path_var = tk.StringVar()
        sig_entry = ctk.CTkEntry(row1, textvariable=self._cmr_sig_path_var, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_muted"], state="readonly")
        sig_entry.pack(side="left", fill="x", expand=True, padx=(0, S["1"]))
        ctk.CTkButton(row1, text="Browse Signature", width=100, height=28,
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"], font=FONTS["small"],
            command=self._browse_cmr_signature).pack(side="left")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=S["4"], pady=(0, S["4"]))
        self._cmr_stamp_path_var = tk.StringVar()
        stamp_entry = ctk.CTkEntry(row2, textvariable=self._cmr_stamp_path_var, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_muted"], state="readonly")
        stamp_entry.pack(side="left", fill="x", expand=True, padx=(0, S["1"]))
        ctk.CTkButton(row2, text="Browse Stamp", width=100, height=28,
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"], font=FONTS["small"],
            command=self._browse_cmr_stamp).pack(side="left")

    def _browse_cmr_signature(self):
        path = filedialog.askopenfilename(
            title="Select Signature Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")])
        if path:
            self._cmr_sig_path_var.set(path)

    def _browse_cmr_stamp(self):
        path = filedialog.askopenfilename(
            title="Select Stamp Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")])
        if path:
            self._cmr_stamp_path_var.set(path)

    # ── Generation Section ──────────────────────────────────────────

    def _build_generation_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["accent"])
        self._section_label(card, "Generate CMR", icon="\U0001F680")
        btn_f = ctk.CTkFrame(card, fg_color="transparent")
        btn_f.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        btn_f.columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btn_f, text="\U0001F680 Generate All 4 Copies",
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["body_bold"],
                      height=44, corner_radius=8,
                      command=self._generate_all_copies).grid(
            row=0, column=0, sticky="ew", padx=(0, S["2"]))
        ctk.CTkButton(btn_f, text="\U0001F4C4 Generate Single Copy",
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      font=FONTS["body_bold"], height=44, corner_radius=8,
                      command=self._generate_cmr).grid(
            row=0, column=1, sticky="ew")
        self._cmr_status_lbl = ctk.CTkLabel(card, text="", font=FONTS["small"],
            text_color=COLORS["text_success"], anchor="w")
        self._cmr_status_lbl.pack(anchor="w", padx=S["4"], pady=(0, S["2"]))

    # ── Copies Status Section ───────────────────────────────────────

    def _build_copies_section(self, parent):
        self._copies_card = self._section_card(parent, accent_color=COLORS["text_muted"])
        self._section_label(self._copies_card, "Generated Copies", icon="\U0001F4C1")
        self._copies_frame = ctk.CTkFrame(self._copies_card, fg_color="transparent")
        self._copies_frame.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        self._copy_labels = {}
        colors_map = {"Sender": "#D32F2F", "Consignee": "#1565C0",
                       "Carrier": "#2E7D32", "Administrative": "#212121"}
        bg_map = {"Sender": "#FFEBEE", "Consignee": "#E3F2FD",
                  "Carrier": "#E8F5E9", "Administrative": "#F5F5F5"}
        for suffix, color in colors_map.items():
            row = ctk.CTkFrame(self._copies_frame, fg_color=bg_map.get(suffix, COLORS["bg_surface"]),
                               corner_radius=6)
            row.pack(fill="x", pady=(0, S["2"]), padx=(0, S["1"]))
            dot = ctk.CTkLabel(row, text="\u25CF", font=("Segoe UI", 10),
                              text_color=color, width=20)
            dot.pack(side="left", padx=(S["2"], 0))
            lbl = ctk.CTkLabel(row, text=f"{suffix} Copy: not generated",
                               font=FONTS["small"], text_color=COLORS["text_secondary"])
            lbl.pack(side="left", fill="x", expand=True)
            open_btn = ctk.CTkButton(row, text="Open", font=FONTS["small"],
                fg_color=COLORS["bg_elevated"],
                hover_color=COLORS["border_hover"],
                text_color=COLORS["text_primary"], height=24, width=50,
                state="disabled", corner_radius=4,
                command=lambda s=suffix: self._open_copy(s))
            open_btn.pack(side="right", padx=S["2"])
            self._copy_labels[suffix] = (lbl, open_btn)

    # ── Trip Lists ──────────────────────────────────────────────────

    def _refresh_trip_lists(self):
        try:
            trips = self._trip_service.get_all()
            self._trips_list = trips
            self._trip_map = {}
            labels = []
            for trip in trips:
                label = t("invoice.trip_list_format").format(
                    id=trip["id"],
                    truck_number=trip.get("truck_number", ""),
                    client_name=trip.get("client_name", ""),
                    created_at=trip.get("created_at", "")[:10] if trip.get("created_at") else "",
                )
                self._trip_map[label] = trip["id"]
                labels.append(label)
            if hasattr(self, "_cmr_trip_combo") and self._cmr_trip_combo.winfo_exists():
                current = self._cmr_trip_combo.get()
                self._cmr_trip_combo.configure(values=labels)
                if labels and current not in labels:
                    self._cmr_trip_combo.set(labels[0])
                    self._on_cmr_trip_selected(labels[0])
        except Exception as e:
            logger.warning("Could not refresh trip lists: %s", e)

    def _on_cmr_trip_selected(self, choice: str) -> None:
        if not choice or choice not in self._trip_map:
            return
        trip_id = self._trip_map[choice]
        trip = self._trip_service.get_by_id(trip_id)
        if not trip:
            return
        # Reset fill tracker when user manually changes trip
        if trip.get("id") != self._cmr_filled_trip_id:
            self._cmr_filled_trip_id = None
        self._auto_fill_from_trip(trip)

    def _auto_fill_from_trip(self, trip):
        trip_id = trip.get("id")
        if trip_id is not None and trip_id == self._cmr_filled_trip_id:
            return  # Already filled, preserve user edits
        self._cmr_filled_trip_id = trip_id
        from services.invoicing.config_manager import load_company_config
        conf = load_company_config()
        self._set_entry(self._cmr_consignor_name, conf.get("company_name", ""))
        self._set_entry(self._cmr_consignor_addr, conf.get("address", ""))
        self._set_entry(self._cmr_consignor_vat, conf.get("cui", ""))
        self._set_entry(self._cmr_consignor_eori, conf.get("eori_number", ""))
        self._set_entry(self._cmr_consignor_phone, conf.get("phone", ""))

        self._set_entry(self._cmr_consignee_name, trip.get("client_name", ""))
        if trip.get("client_id"):
            try:
                client = self.db.conn.execute(
                    "SELECT * FROM clients WHERE id = ?", (trip["client_id"],)
                ).fetchone()
                if client:
                    self._set_entry(self._cmr_consignee_addr, dict(client).get("address", ""))
                    self._set_entry(self._cmr_consignee_vat, dict(client).get("vat_number", ""))
                    self._set_entry(self._cmr_consignee_eori, dict(client).get("eori_number", ""))
                    contact = dict(client).get("consignee_contact_name", "")
                    phone = dict(client).get("consignee_contact_phone",
                              dict(client).get("phone", ""))
                    if contact or phone:
                        self._set_entry(self._cmr_consignee_contact,
                                       f"{contact}, {phone}".strip(", "))
            except Exception:
                pass

        self._set_entry(self._cmr_carrier_name, conf.get("company_name", ""))
        self._set_entry(self._cmr_carrier_addr, conf.get("address", ""))
        self._set_entry(self._cmr_carrier_phone, conf.get("phone", ""))
        self._set_entry(self._cmr_carrier_email, conf.get("email", ""))
        self._set_entry(self._cmr_carrier_reg, conf.get("reg_number", ""))
        truck_number = trip.get("truck_number", "")
        self._set_entry(self._cmr_vehicle, truck_number)
        if trip.get("truck_id"):
            try:
                truck = self.db.conn.execute(
                    "SELECT * FROM trucks WHERE id = ?", (trip["truck_id"],)
                ).fetchone()
                if truck:
                    t = dict(truck)
                    self._set_entry(self._cmr_vehicle, t.get("plate_number", truck_number))
                    self._set_entry(self._cmr_trailer, t.get("trailer_plate",
                                     trip.get("trailer_plate", "")))
                    self._set_entry(self._cmr_insurance, t.get("cmr_insurance_number",
                                     trip.get("cmr_insurance_number", "")))
            except Exception:
                self._set_entry(self._cmr_trailer, trip.get("trailer_plate", ""))
                self._set_entry(self._cmr_insurance, trip.get("cmr_insurance_number", ""))
        else:
            self._set_entry(self._cmr_trailer, trip.get("trailer_plate", ""))
            self._set_entry(self._cmr_insurance, trip.get("cmr_insurance_number", ""))

        driver_name = trip.get("driver_name", "")
        self._set_entry(self._cmr_driver_name, driver_name)
        if trip.get("driver_id"):
            try:
                driver = self.db.conn.execute(
                    "SELECT * FROM drivers WHERE id = ?", (trip["driver_id"],)
                ).fetchone()
                if driver:
                    d = dict(driver)
                    self._set_entry(self._cmr_driver_name, d.get("name", driver_name))
                    self._set_entry(self._cmr_driver_license, d.get("license_number",
                                     trip.get("driver_license", "")))
            except Exception:
                self._set_entry(self._cmr_driver_license, trip.get("driver_license", ""))
        else:
            self._set_entry(self._cmr_driver_license, trip.get("driver_license", ""))

        self._set_entry(self._cmr_loading, trip.get("place_of_loading",
                     trip.get("loading_address", trip.get("origin", ""))))
        self._set_entry(self._cmr_unloading, trip.get("destination",
                     trip.get("unloading_address", "")))
        self._set_entry(self._cmr_loading_date, trip.get("place_of_loading_date",
                     trip.get("start_date", "")))
        self._set_entry(self._cmr_loading_country, trip.get("loading_country", ""))
        self._set_entry(self._cmr_delivery_country, trip.get("delivery_country", ""))

        self._set_textbox(self._cmr_cargo_desc, trip.get("cargo_description", ""))
        self._set_entry(self._cmr_package_count, trip.get("package_count", ""))
        if trip.get("package_type"):
            try:
                self._cmr_package_type.set(trip["package_type"])
            except Exception:
                pass
        self._set_entry(self._cmr_weight, trip.get("gross_weight_kg", ""))
        self._set_entry(self._cmr_volume, trip.get("volume_m3", ""))
        self._set_entry(self._cmr_hs_code, trip.get("hs_code", ""))
        self._set_entry(self._cmr_marks, trip.get("cargo_marks", ""))
        self._set_entry(self._cmr_docs_text, trip.get("documents_attached", ""))

        self._set_textbox(self._cmr_instructions, trip.get("carrier_instructions", ""))
        self._set_textbox(self._cmr_reservations, trip.get("carrier_reservations", ""))
        self._set_textbox(self._cmr_agreements, trip.get("special_agreements", ""))
        payer = trip.get("carriage_payer", "")
        if payer in ("sender", "consignee"):
            self._cmr_payer_var.set(payer)
        self._set_entry(self._cmr_distance, trip.get("distance_km", ""))

        self._set_entry(self._cmr_sig_path_var, conf.get("signature_path", ""))
        self._set_entry(self._cmr_stamp_path_var, conf.get("stamp_path", ""))

        if trip.get("route_history_v2_id"):
            self._fill_stops_from_route(trip["route_history_v2_id"])

    def _set_entry(self, widget_or_var, value):
        if widget_or_var is None:
            return
        try:
            if hasattr(widget_or_var, "winfo_exists") and not widget_or_var.winfo_exists():
                return
        except Exception:
            pass
        try:
            if isinstance(widget_or_var, tk.StringVar):
                widget_or_var.set(str(value) if value else "")
                return
        except Exception:
            pass
        try:
            widget_or_var.delete(0, "end")
        except Exception:
            pass
        try:
            if value:
                widget_or_var.insert(0, str(value))
        except Exception:
            pass

    def _set_textbox(self, widget, value):
        if widget is None:
            return
        try:
            if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                return
        except Exception:
            pass
        try:
            widget.delete("1.0", "end")
            if value:
                widget.insert("1.0", str(value))
        except Exception:
            pass

    def _fill_stops_from_route(self, route_id: int) -> None:
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
            if origin:
                self._set_entry(self._cmr_loading, origin)
            if destination:
                self._set_entry(self._cmr_unloading, destination)
        except Exception as e:
            logger.debug("Could not fill stops from route %d: %s", route_id, e)

    # ── CMR Generation ─────────────────────────────────────────────

    def _collect_cmr_data(self):
        sel = self._cmr_trip_combo.get()
        if not sel or sel not in self._trip_map:
            return None
        trip_id = self._trip_map[sel]
        trip = self._trip_service.get_by_id(trip_id)
        if not trip:
            return None
        trip_data = dict(trip)
        trip_data["trip_id"] = trip_id
        trip_data["client_name"] = self._cmr_consignee_name.get()
        trip_data["client_address"] = self._cmr_consignee_addr.get()
        trip_data["consignee_vat"] = self._cmr_consignee_vat.get()
        trip_data["consignee_eori"] = self._cmr_consignee_eori.get()
        trip_data["consignee_contact"] = self._cmr_consignee_contact.get()
        trip_data["consignor_name"] = self._cmr_consignor_name.get()
        trip_data["consignor_address"] = self._cmr_consignor_addr.get()
        trip_data["consignor_vat"] = self._cmr_consignor_vat.get()
        trip_data["consignor_eori"] = self._cmr_consignor_eori.get()
        trip_data["consignor_phone"] = self._cmr_consignor_phone.get()
        trip_data["carrier_name"] = self._cmr_carrier_name.get()
        trip_data["carrier_address"] = self._cmr_carrier_addr.get()
        trip_data["carrier_phone"] = self._cmr_carrier_phone.get()
        trip_data["carrier_email"] = self._cmr_carrier_email.get()
        trip_data["carrier_reg"] = self._cmr_carrier_reg.get()
        trip_data["cmr_insurance_number"] = self._cmr_insurance.get()
        trip_data["truck_plate"] = self._cmr_vehicle.get()
        trip_data["trailer_plate"] = self._cmr_trailer.get()
        trip_data["driver_name"] = self._cmr_driver_name.get()
        trip_data["driver_license"] = self._cmr_driver_license.get()
        trip_data["place_of_loading"] = self._cmr_loading.get()
        trip_data["destination"] = self._cmr_unloading.get()
        trip_data["place_of_loading_date"] = self._cmr_loading_date.get()
        trip_data["loading_country"] = self._cmr_loading_country.get()
        trip_data["delivery_country"] = self._cmr_delivery_country.get()
        trip_data["documents_attached"] = self._cmr_docs_text.get()
        trip_data["cargo_description"] = self._cmr_cargo_desc.get("1.0", "end-1c").strip()
        trip_data["package_count"] = self._cmr_package_count.get()
        trip_data["package_type"] = self._cmr_package_type.get()
        trip_data["gross_weight_kg"] = self._cmr_weight.get()
        trip_data["volume_m3"] = self._cmr_volume.get()
        trip_data["hs_code"] = self._cmr_hs_code.get()
        trip_data["cargo_marks"] = self._cmr_marks.get()
        trip_data["carrier_instructions"] = self._cmr_instructions.get("1.0", "end-1c").strip()
        trip_data["carrier_reservations"] = self._cmr_reservations.get("1.0", "end-1c").strip()
        trip_data["special_agreements"] = self._cmr_agreements.get("1.0", "end-1c").strip()
        trip_data["carriage_payer"] = self._cmr_payer_var.get()
        trip_data["distance_km"] = self._cmr_distance.get()

        adr_data = self._get_adr_data()
        if adr_data:
            trip_data["adr_info_json"] = json.dumps(adr_data)

        trip_data["successive_carriers"] = self._get_successive_carriers()
        trip_data["signature_path"] = self._cmr_sig_path_var.get() or "__NONE__"
        trip_data["stamp_path"] = self._cmr_stamp_path_var.get() or "__NONE__"

        return trip_data

    def _generate_cmr(self):
        trip_data = self._collect_cmr_data()
        if trip_data is None:
            messagebox.showwarning(t("generators.cmr_generate"),
                                   t("generators.cmr_select_trip"))
            return
        trip_id = trip_data["trip_id"]
        try:
            from services.invoicing.cmr_generator import CMRGenerator
            gen = CMRGenerator(db=self.db, prefs=self.prefs)
            output_dir = os.path.join("data", "documents", "trips", str(trip_id))
            os.makedirs(output_dir, exist_ok=True)
            filepath = gen.generate(trip_data, output_dir)
        except Exception as e:
            messagebox.showerror(t("generators.cmr_generate"),
                                 t("generators.cmr_error").format(error=str(e)))
            return

        try:
            ds = self._lazy_cmr_doc_service()
            ds.register_existing(
                filepath,
                title=f"CMR Trip #{trip_id}",
                category="trips",
                entity_type="trip",
                entity_id=trip_id,
                tags=["cmr", "generated"],
            )
        except Exception:
            logger.warning("CMR registration in Document Center skipped", exc_info=True)

        self._cmr_last_paths["Sender"] = filepath
        self._cmr_status_lbl.configure(text=f"CMR generated: {os.path.basename(filepath)}")
        self._update_copy_status("Sender", filepath)
        logger.info("CMR generated for trip %d: %s", trip_id, filepath)

    def _generate_all_copies(self):
        trip_data = self._collect_cmr_data()
        if trip_data is None:
            messagebox.showwarning(t("generators.cmr_generate"),
                                   t("generators.cmr_select_trip"))
            return
        trip_id = trip_data["trip_id"]
        self._cmr_status_lbl.configure(text="Generating 4 copies...", text_color=COLORS["text_warning"])
        self._cmr_status_lbl.update_idletasks()

        def _run():
            registered_paths = {}
            try:
                from services.invoicing.cmr_generator import CMRGenerator
                gen = CMRGenerator(db=self.db, prefs=self.prefs)
                output_dir = os.path.join("data", "documents", "trips", str(trip_id))
                os.makedirs(output_dir, exist_ok=True)
                copies = gen.generate_all_copies(trip_data, output_dir)
                registered_paths = dict(copies)
            except Exception as e:
                def _err():
                    if self._cmr_status_lbl.winfo_exists():
                        self._cmr_status_lbl.configure(
                            text=t("generators.cmr_error").format(error=str(e)),
                            text_color=COLORS["danger"])
                self.after(0, _err)
                logger.error("CMR generation failed: %s", e)
                return

            # DB writes done on main thread via after()
            def _register():
                try:
                    ds = self._lazy_cmr_doc_service()
                    for suffix, path in registered_paths.items():
                        try:
                            ds.register_existing(
                                path,
                                title=f"CMR Trip #{trip_id} - {suffix.upper()} COPY",
                                category="trips",
                                entity_type="trip",
                                entity_id=trip_id,
                                tags=["cmr", suffix.lower(), "generated"],
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
                if self._cmr_status_lbl.winfo_exists():
                    self._cmr_last_paths.update(registered_paths)
                    base = os.path.basename(list(registered_paths.values())[0]) if registered_paths else ""
                    self._cmr_status_lbl.configure(
                        text=f"All 4 copies generated: {base}",
                        text_color=COLORS["text_success"])
                    for suffix, path in registered_paths.items():
                        self._update_copy_status(suffix, path)
            self.after(0, _register)

        threading.Thread(target=_run, daemon=True, name=f"cmr-gen-{trip_id}").start()

    def _update_copy_status(self, suffix, path):
        if suffix in self._copy_labels:
            lbl, btn = self._copy_labels[suffix]
            lbl.configure(text=f"{suffix} Copy: {os.path.basename(path)}")
            btn.configure(state="normal")
            btn.configure(command=lambda p=path: os.startfile(os.path.abspath(p)))

    def _open_copy(self, suffix):
        if suffix in self._cmr_last_paths:
            path = self._cmr_last_paths[suffix]
            if os.path.isfile(path):
                os.startfile(os.path.abspath(path))
