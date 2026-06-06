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

        hdr = ctk.CTkFrame(tab, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(S["4"], S["2"]))
        ctk.CTkLabel(hdr, text="\U0001F4C4 " + t("generators.cmr_title"),
                     font=FONTS["h2"], text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(hdr, text=t("generators.cmr_subtitle"),
                     font=FONTS["small"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")

        self._cmr_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_fg_color=COLORS["bg_surface"],
        )
        self._cmr_scroll.grid(row=1, column=0, sticky="nsew")
        self._cmr_scroll.columnconfigure(0, weight=1)

        self._build_language_section(self._cmr_scroll)
        self._build_trip_section(self._cmr_scroll)
        self._build_consignment_section(self._cmr_scroll)
        self._build_transport_section(self._cmr_scroll)
        self._build_cargo_section(self._cmr_scroll)
        self._build_instructions_section(self._cmr_scroll)
        self._build_adr_section(self._cmr_scroll)
        self._build_successive_section(self._cmr_scroll)
        self._build_signature_section(self._cmr_scroll)
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
        """Section header with optional icon."""
        lbl = ctk.CTkLabel(parent, text=f"{icon}  {text}" if icon else text,
                           font=FONTS["label"],
                           text_color=COLORS["text_primary"],
                           anchor="w")
        lbl.pack(anchor="w", padx=S["4"], pady=(S["4"], S["1"]))

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
        self._section_label(card, "CMR Languages / Limbi CMR", icon="\U0001F310")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        lang_codes = self.prefs.get_available_languages() if self.prefs else ["en", "ro"]
        lang_display = []
        for c in lang_codes:
            try:
                dn = self.prefs.get_language_display_name(c) if self.prefs else c
                lang_display.append(f"{dn} ({c})")
            except Exception:
                lang_display.append(c)

        l1 = ctk.CTkFrame(row, fg_color="transparent")
        l1.grid(row=0, column=0, sticky="ew", padx=(0, S["2"]))
        ctk.CTkLabel(l1, text="Primary:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_lang1 = ctk.CTkComboBox(l1, values=lang_display, state="readonly",
                                          font=FONTS["body"],
                                          fg_color=COLORS["bg_input"],
                                          border_color=COLORS["border"],
                                          button_color=COLORS["bg_elevated"],
                                          text_color=COLORS["text_primary"])
        self._cmr_lang1.pack(fill="x")
        if lang_display:
            self._cmr_lang1.set(lang_display[0])

        l2 = ctk.CTkFrame(row, fg_color="transparent")
        l2.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(l2, text="Secondary:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_lang2 = ctk.CTkComboBox(l2, values=lang_display, state="readonly",
                                          font=FONTS["body"],
                                          fg_color=COLORS["bg_input"],
                                          border_color=COLORS["border"],
                                          button_color=COLORS["bg_elevated"],
                                          text_color=COLORS["text_primary"])
        self._cmr_lang2.pack(fill="x")
        if len(lang_display) > 1:
            self._cmr_lang2.set(lang_display[1])

    # ── Trip Selection ──────────────────────────────────────────────

    def _build_trip_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["warning"])
        self._section_label(card, t("generators.cmr_trip_select"), icon="\U0001F68C")
        sel = ctk.CTkFrame(card, fg_color="transparent")
        sel.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        self._cmr_trip_combo = ctk.CTkComboBox(
            sel, values=[], state="readonly",
            font=FONTS["body"],
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            command=self._on_cmr_trip_selected,
        )
        self._cmr_trip_combo.pack(side="left", fill="x", expand=True, padx=(0, S["2"]))
        ctk.CTkButton(sel, text="\U0001F504", width=36, height=36,
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      font=FONTS["body"],
                      command=self._refresh_trip_lists).pack(side="right")

    # ── Consignment Parties ─────────────────────────────────────────

    def _build_consignment_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["success"])
        self._section_label(card, "Consignment Parties", icon="\U0001F465")

        cols = ctk.CTkFrame(card, fg_color="transparent")
        cols.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        c_left = ctk.CTkFrame(cols, fg_color="transparent")
        c_left.grid(row=0, column=0, sticky="new", padx=(0, S["2"]))
        ctk.CTkLabel(c_left, text="CONSIGNOR", font=FONTS["label"],
                     text_color=COLORS["accent"]).pack(anchor="w")
        self._cmr_consignor_name = ctk.CTkEntry(c_left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignor_name.pack(fill="x", pady=(0, S["1"]))
        self._cmr_consignor_addr = ctk.CTkEntry(c_left, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignor_addr.pack(fill="x", pady=(0, S["1"]))
        vat_row = ctk.CTkFrame(c_left, fg_color="transparent")
        vat_row.pack(fill="x", pady=(0, S["1"]))
        self._cmr_consignor_vat = ctk.CTkEntry(vat_row, width=80, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignor_vat.pack(side="left", padx=(0, S["1"]))
        self._cmr_consignor_eori = ctk.CTkEntry(vat_row, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignor_eori.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(vat_row, text="VAT", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(S["1"], S["2"]))
        ctk.CTkLabel(vat_row, text="EORI", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(S["1"], 0))

        c_right = ctk.CTkFrame(cols, fg_color="transparent")
        c_right.grid(row=0, column=1, sticky="new")
        ctk.CTkLabel(c_right, text="CONSIGNEE", font=FONTS["label"],
                     text_color=COLORS["accent"]).pack(anchor="w")
        self._cmr_consignee_name = ctk.CTkEntry(c_right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_name.pack(fill="x", pady=(0, S["1"]))
        self._cmr_consignee_addr = ctk.CTkEntry(c_right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_addr.pack(fill="x", pady=(0, S["1"]))
        cv_row = ctk.CTkFrame(c_right, fg_color="transparent")
        cv_row.pack(fill="x", pady=(0, S["1"]))
        self._cmr_consignee_vat = ctk.CTkEntry(cv_row, width=80, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_vat.pack(side="left", padx=(0, S["1"]))
        self._cmr_consignee_eori = ctk.CTkEntry(cv_row, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_eori.pack(side="left", fill="x", expand=True)
        self._cmr_consignee_contact = ctk.CTkEntry(c_right, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_consignee_contact.pack(fill="x")

        carr_f = ctk.CTkFrame(card, fg_color="transparent")
        carr_f.pack(fill="x", padx=S["4"], pady=(0, S["4"]))
        ctk.CTkLabel(carr_f, text="CARRIER", font=FONTS["label"],
                     text_color=COLORS["accent"]).pack(anchor="w")
        cr = ctk.CTkFrame(carr_f, fg_color="transparent")
        cr.pack(fill="x")
        self._cmr_carrier_name = ctk.CTkEntry(cr, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_carrier_name.pack(fill="x", pady=(0, S["1"]))

        cd = ctk.CTkFrame(carr_f, fg_color="transparent")
        cd.pack(fill="x")
        cd.columnconfigure(0, weight=1)
        cd.columnconfigure(1, weight=1)
        cd.columnconfigure(2, weight=1)
        vf = ctk.CTkFrame(cd, fg_color="transparent")
        vf.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        ctk.CTkLabel(vf, text="Vehicle Plate", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_vehicle = ctk.CTkEntry(vf, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_vehicle.pack(fill="x")
        tf = ctk.CTkFrame(cd, fg_color="transparent")
        tf.grid(row=0, column=1, sticky="ew", padx=(0, S["1"]))
        ctk.CTkLabel(tf, text="Trailer Plate", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_trailer = ctk.CTkEntry(tf, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_trailer.pack(fill="x")
        df = ctk.CTkFrame(cd, fg_color="transparent")
        df.grid(row=0, column=2, sticky="ew")
        ctk.CTkLabel(df, text="Driver", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_driver_name = ctk.CTkEntry(df, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_driver_name.pack(fill="x")

        dl = ctk.CTkFrame(carr_f, fg_color="transparent")
        dl.pack(fill="x")
        dl.columnconfigure(0, weight=1)
        dl.columnconfigure(1, weight=1)
        self._cmr_driver_license = self._entry(dl, "Driver License", 28)
        self._cmr_driver_license.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._cmr_insurance = self._entry(dl, "CMR Insurance No.", 28)
        self._cmr_insurance.grid(row=0, column=1, sticky="ew")

    # ── Transport Details ───────────────────────────────────────────

    def _build_transport_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(card, "Transport Details", icon="\U0001F6E3")
        cols = ctk.CTkFrame(card, fg_color="transparent")
        cols.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        lf = ctk.CTkFrame(cols, fg_color="transparent")
        lf.grid(row=0, column=0, sticky="ew", padx=(0, S["2"]))
        ctk.CTkLabel(lf, text="Place of Loading", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_loading = ctk.CTkEntry(lf, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_loading.pack(fill="x", pady=(0, S["1"]))
        lrow = ctk.CTkFrame(lf, fg_color="transparent")
        lrow.pack(fill="x")
        self._cmr_loading_date = ctk.CTkEntry(lrow, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_loading_date.pack(side="left", fill="x", expand=True, padx=(0, S["1"]))
        ctk.CTkLabel(lrow, text="Date", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(0, S["2"]))
        self._cmr_loading_country = ctk.CTkEntry(lrow, width=50, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_loading_country.pack(side="left")
        ctk.CTkLabel(lrow, text="ISO", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(S["1"], 0))

        rf = ctk.CTkFrame(cols, fg_color="transparent")
        rf.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(rf, text="Place of Delivery", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")
        self._cmr_unloading = ctk.CTkEntry(rf, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_unloading.pack(fill="x", pady=(0, S["1"]))
        drow = ctk.CTkFrame(rf, fg_color="transparent")
        drow.pack(fill="x")
        self._cmr_delivery_country = ctk.CTkEntry(drow, width=50, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_delivery_country.pack(side="left")
        ctk.CTkLabel(drow, text="ISO", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(S["1"], S["3"]))

        self._cmr_docs_text = ctk.CTkEntry(card, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], font=FONTS["body"])
        self._cmr_docs_text.pack(fill="x", padx=S["4"], pady=(0, S["4"]))
        ctk.CTkLabel(card, text="Documents Attached", font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w").pack(
            anchor="w", padx=S["4"])

    # ── Cargo Details ──────────────────────────────────────────────

    def _build_cargo_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["warning"])
        self._section_label(card, "Cargo Details", icon="\U0001F4E6")
        pf = ctk.CTkFrame(card, fg_color="transparent")
        pf.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))

        self._cmr_cargo_desc = ctk.CTkTextbox(pf, height=60,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"],
            wrap="word")
        self._cmr_cargo_desc.pack(fill="x", pady=(0, S["2"]))
        ctk.CTkLabel(pf, text="Description", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(anchor="w")

        row1 = ctk.CTkFrame(pf, fg_color="transparent")
        row1.pack(fill="x", pady=(S["2"], S["1"]))
        row1.columnconfigure((0, 1, 2, 3), weight=1)
        self._cmr_package_count = self._entry(row1, "Package Count", 28)
        self._cmr_package_count.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._cmr_package_type = ctk.CTkComboBox(row1, values=PACKAGE_TYPES,
            state="readonly", font=FONTS["body"],
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"], height=28)
        self._cmr_package_type.grid(row=0, column=1, sticky="ew", padx=(0, S["1"]))
        self._cmr_package_type.set("Pallet")
        self._cmr_weight = self._entry(row1, "Weight (kg)", 28)
        self._cmr_weight.grid(row=0, column=2, sticky="ew", padx=(0, S["1"]))
        self._cmr_volume = self._entry(row1, "Volume (m\u00b3)", 28)
        self._cmr_volume.grid(row=0, column=3, sticky="ew")

        row2 = ctk.CTkFrame(pf, fg_color="transparent")
        row2.pack(fill="x")
        row2.columnconfigure((0, 1), weight=1)
        self._cmr_hs_code = self._entry(row2, "HS Code", 28)
        self._cmr_hs_code.grid(row=0, column=0, sticky="ew", padx=(0, S["1"]))
        self._cmr_marks = self._entry(row2, "Marks & Numbers", 28)
        self._cmr_marks.grid(row=0, column=1, sticky="ew")

    # ── Instructions & Reservations ─────────────────────────────────

    def _build_instructions_section(self, parent):
        card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(card, "Instructions & Reservations", icon="\U0001F4CB")

        self._cmr_instructions = ctk.CTkTextbox(card, height=40,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_instructions.pack(fill="x", padx=S["4"], pady=(S["1"], 0))
        ctk.CTkLabel(card, text="Sender's Instructions (Customs)",
                     font=FONTS["small"], text_color=COLORS["text_muted"]).pack(
            anchor="w", padx=S["4"])

        self._cmr_reservations = ctk.CTkTextbox(card, height=40,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_reservations.pack(fill="x", padx=S["4"], pady=(S["2"], 0))
        ctk.CTkLabel(card, text="Carrier's Reservations",
                     font=FONTS["small"], text_color=COLORS["text_muted"]).pack(
            anchor="w", padx=S["4"])

        self._cmr_agreements = ctk.CTkTextbox(card, height=40,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"], wrap="word")
        self._cmr_agreements.pack(fill="x", padx=S["4"], pady=(S["2"], 0))
        ctk.CTkLabel(card, text="Special Agreements",
                     font=FONTS["small"], text_color=COLORS["text_muted"]).pack(
            anchor="w", padx=S["4"])

        pr = ctk.CTkFrame(card, fg_color="transparent")
        pr.pack(fill="x", padx=S["4"], pady=(S["2"], S["4"]))
        self._cmr_payer_var = tk.StringVar(value="")
        ctk.CTkLabel(pr, text="Carriage charges:", font=FONTS["body"],
                     text_color=COLORS["text_secondary"]).pack(side="left")
        ctk.CTkRadioButton(pr, text="Sender pays", variable=self._cmr_payer_var,
                           value="sender", font=FONTS["body"],
                           text_color=COLORS["text_primary"],
                           fg_color=COLORS["accent"]).pack(side="left", padx=S["2"])
        ctk.CTkRadioButton(pr, text="Consignee pays", variable=self._cmr_payer_var,
                           value="consignee", font=FONTS["body"],
                           text_color=COLORS["text_primary"],
                           fg_color=COLORS["accent"]).pack(side="left", padx=S["2"])

    # ── ADR Section ────────────────────────────────────────────────

    def _build_adr_section(self, parent):
        self._adr_card = self._section_card(parent, accent_color=COLORS["danger"])
        header = ctk.CTkFrame(self._adr_card, fg_color="transparent")
        header.pack(fill="x", padx=S["4"], pady=(S["4"], 0))
        self._adr_toggle_var = tk.BooleanVar(value=False)
        self._adr_toggle = ctk.CTkCheckBox(
            header, text="\u26A0 This shipment contains DANGEROUS GOODS (ADR)",
            variable=self._adr_toggle_var,
            command=self._on_adr_toggle,
            font=FONTS["body"], text_color=COLORS["text_primary"],
            fg_color=COLORS["danger"],
            hover_color=COLORS.get("danger_hover", COLORS["danger"]),
        )
        self._adr_toggle.pack(side="left")

        self._adr_content = ctk.CTkFrame(self._adr_card, fg_color="transparent")
        self._adr_add_btn = ctk.CTkButton(
            self._adr_card, text="+ Add ADR Row", font=FONTS["body"],
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"], height=28,
            command=self._add_adr_row,
        )

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

    def _build_successive_section(self, parent):
        self._succ_card = self._section_card(parent, accent_color=COLORS["info"])
        self._section_label(self._succ_card, "Successive Carriers (Sub-contracted)", icon="\U0001F69A")
        self._succ_content = ctk.CTkFrame(self._succ_card, fg_color="transparent")
        self._succ_content.pack(fill="x", padx=S["4"], pady=(S["1"], S["2"]))
        self._succ_add_btn = ctk.CTkButton(
            self._succ_card, text="+ Add Successive Carrier", font=FONTS["body"],
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"], height=28,
            command=self._add_successive_carrier,
        )
        self._succ_add_btn.pack(padx=S["4"], pady=(0, S["4"]), anchor="w")

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
        self._section_label(card, "Signature & Stamp Images", icon="\U0000270F")
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
                self._cmr_trip_combo.configure(values=labels)
                if labels:
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
        self._auto_fill_from_trip(trip)

    def _auto_fill_from_trip(self, trip):
        from services.invoicing.config_manager import load_company_config
        conf = load_company_config()
        self._set_entry(self._cmr_consignor_name, conf.get("company_name", ""))
        self._set_entry(self._cmr_consignor_addr, conf.get("address", ""))
        self._set_entry(self._cmr_consignor_vat, conf.get("cui", ""))
        self._set_entry(self._cmr_consignor_eori, conf.get("eori_number", ""))

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

        if trip.get("truck_id"):
            try:
                truck = self.db.conn.execute(
                    "SELECT * FROM trucks WHERE id = ?", (trip["truck_id"],)
                ).fetchone()
                if truck:
                    t = dict(truck)
                    self._set_entry(self._cmr_vehicle, t.get("plate_number", trip.get("truck_number", "")))
                    self._set_entry(self._cmr_trailer, t.get("trailer_plate", ""))
                    self._set_entry(self._cmr_insurance, t.get("cmr_insurance_number", ""))
            except Exception:
                self._set_entry(self._cmr_vehicle, trip.get("truck_number", ""))

        if trip.get("driver_id"):
            try:
                driver = self.db.conn.execute(
                    "SELECT * FROM drivers WHERE id = ?", (trip["driver_id"],)
                ).fetchone()
                if driver:
                    d = dict(driver)
                    self._set_entry(self._cmr_driver_name, d.get("name", trip.get("driver_name", "")))
                    self._set_entry(self._cmr_driver_license, d.get("license_number", ""))
            except Exception:
                self._set_entry(self._cmr_driver_name, trip.get("driver_name", ""))

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
        trip_data["truck_plate"] = self._cmr_vehicle.get()
        trip_data["trailer_plate"] = self._cmr_trailer.get()
        trip_data["driver_name"] = self._cmr_driver_name.get()
        trip_data["driver_license"] = self._cmr_driver_license.get()
        trip_data["cmr_insurance_number"] = self._cmr_insurance.get()
        trip_data["eori_number"] = self._cmr_consignor_eori.get()
        trip_data["consignee_vat"] = self._cmr_consignee_vat.get()
        trip_data["consignee_eori"] = self._cmr_consignee_eori.get()
        trip_data["consignee_contact"] = self._cmr_consignee_contact.get()
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

        adr_data = self._get_adr_data()
        if adr_data:
            trip_data["adr_info_json"] = json.dumps(adr_data)

        trip_data["successive_carriers"] = self._get_successive_carriers()

        if self._cmr_sig_path_var.get():
            trip_data["signature_path"] = self._cmr_sig_path_var.get()
        if self._cmr_stamp_path_var.get():
            trip_data["stamp_path"] = self._cmr_stamp_path_var.get()

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
            messagebox.showwarning("Generate CMR", "Please select a trip first.")
            return
        trip_id = trip_data["trip_id"]
        self._cmr_status_lbl.configure(text="Generating 4 copies...", text_color=COLORS["text_warning"])
        self._cmr_status_lbl.update_idletasks()

        def _run():
            try:
                from services.invoicing.cmr_generator import CMRGenerator
                gen = CMRGenerator(db=self.db, prefs=self.prefs)
                output_dir = os.path.join("data", "documents", "trips", str(trip_id))
                os.makedirs(output_dir, exist_ok=True)
                copies = gen.generate_all_copies(trip_data, output_dir)
            except Exception as e:
                self.after(0, lambda: self._cmr_status_lbl.configure(
                    text=f"Error: {e}", text_color=COLORS["danger"]))
                logger.error("CMR generation failed: %s", e)
                return

            ds = self._lazy_cmr_doc_service()
            for suffix, path in copies.items():
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

            def _update_ui():
                self._cmr_last_paths.update(copies)
                base = os.path.basename(list(copies.values())[0]) if copies else ""
                self._cmr_status_lbl.configure(
                    text=f"All 4 copies generated: {base}",
                    text_color=COLORS["text_success"])
                for suffix, path in copies.items():
                    self._update_copy_status(suffix, path)
            self.after(0, _update_ui)

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
