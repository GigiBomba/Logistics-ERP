"""Modern Invoice Editor with live preview.

Replaces the old InvoiceTab form with a professional invoice-building
experience inspired by Invoice Simple and similar tools.
"""

import json
import logging
import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from services.i18n import t
from services.app_state import AppState
from services.invoicing.config_manager import load_company_config, save_company_config
from services.invoicing.service import InvoiceService
from services.trip_service import TripService
from repositories.client_repository import ClientRepository
from services.operations.event_bus import EventBus, SETTINGS_UPDATED
from services.preferences import PreferencesManager
from ui.theme import COLORS, FONTS, S, RADIUS_CARD, RADIUS_INPUT
from ui.i18n_mixin import I18nMixin

_logger = logging.getLogger(__name__)

DRAFTS_DIR = os.path.join("data", "invoice_drafts")


class InvoiceEditor(I18nMixin):
    """Professional invoice editor with live canvas preview."""

    def __init__(self, parent, db, prefs=None):
        I18nMixin.__init__(self)
        self.db = db
        self.prefs = prefs or PreferencesManager(db)
        self._trip_service = TripService(db)
        self._client_repo = ClientRepository(db)
        self._invoice_service = InvoiceService(db, prefs=self.prefs)
        self._app_state = AppState()
        self._event_bus = EventBus()

        self._clients = []
        self._client_map = {}
        self._trips = []
        self._trip_map = {}

        # Invoice data model
        self._invoice_number = tk.StringVar(value=self._gen_invoice_number())
        self._issue_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self._due_date = tk.StringVar(value=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
        self._payment_terms = tk.StringVar(value="Net 30")
        self._notes = tk.StringVar()
        self._tax_rate = tk.StringVar(value="19")
        self._discount_type = tk.StringVar()
        self._discount_value = tk.StringVar(value="0")
        self._currency = tk.StringVar(value=self.prefs.get_currency())

        # Additional items: list of dicts with description + amount
        self._addon_items = []

        # Invoice mode
        self._is_client_invoice = tk.BooleanVar(value=True)
        self._is_internal_invoice = tk.BooleanVar(value=False)

        # Trip base price (loaded from trip)
        self._trip_base_price = tk.StringVar(value="0.00")
        self._trip_price_pre_vat = tk.StringVar()
        self._trip_vat_percent = tk.StringVar()

        # Trip details (auto-filled from trip + route)
        self._truck_plate = tk.StringVar()
        self._driver_name = tk.StringVar()
        self._distance = tk.StringVar()

        # Dynamic stops: separate lists for loading and unloading locations
        self._loading_stops = []    # list of {"var": StringVar}
        self._unloading_stops = []  # list of {"var": StringVar}
        self._stops_frame = None

        # Free-text description (separate from line items)
        self._description = tk.StringVar()

        # Branding
        self._logo_path = tk.StringVar()
        self._signature_path = tk.StringVar()
        self._stamp_path = tk.StringVar()
        self._company_color = tk.StringVar(value=COLORS["accent"])

        # Client info (editable, auto-filled from client selection)
        self._client_name = tk.StringVar()
        self._client_vat = tk.StringVar()
        self._client_address = tk.StringVar()
        self._client_phone = tk.StringVar()
        self._client_email = tk.StringVar()
        self._selected_client_id = None

        # Company info (editable, loaded from config)
        self._company_name = tk.StringVar()
        self._company_cui = tk.StringVar()
        self._company_reg = tk.StringVar()
        self._company_address = tk.StringVar()
        self._company_phone = tk.StringVar()
        self._company_email = tk.StringVar()

        # Selected trip
        self._selected_trip_id = None
        self._selected_trip_data = None

        # The main frame (for embedding in tab views)
        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_base"])

        self._build_layout()
        self._load_company_config()
        self._load_clients()
        self._load_trips()
        self._add_default_addon_item()

        self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)
        self.frame.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.frame:
            return
        self._event_bus.unsubscribe(SETTINGS_UPDATED, self._on_settings_updated)
        self.i18n_cleanup()

    def _on_settings_updated(self, ev):
        data = ev.get("data", {})
        if data.get("key") == "company_config":
            try:
                self.frame.after(0, self._load_company_config)
            except Exception:
                pass

    def refresh_translations(self):
        pass

    def _gen_invoice_number(self):
        year = datetime.now().year
        return f"INV-{year}-{datetime.now().strftime('%m%d')}-001"

    # ═══════════════════════════════════════════════════════════════
    # LAYOUT BUILDING
    # ═══════════════════════════════════════════════════════════════

    def _build_layout(self):
        self.frame.rowconfigure(0, weight=0)   # top bar
        self.frame.rowconfigure(1, weight=1)   # main area
        self.frame.rowconfigure(2, weight=0)   # bottom bar
        self.frame.columnconfigure(0, weight=1)

        self._build_top_bar(self.frame)
        self._build_main_area(self.frame)
        self._build_bottom_bar(self.frame)

    def _build_top_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"], height=56, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        bar.columnconfigure(0, weight=0)
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(2, weight=0)
        bar.columnconfigure(3, weight=1)
        bar.columnconfigure(4, weight=0)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.grid(row=0, column=0, columnspan=5, sticky="ew", padx=S["4"], pady=S["2"])

        # Client selector
        ctk.CTkLabel(inner, text=t("invoice_editor.select_client"),
                     font=FONTS["label"], text_color=COLORS["text_muted"]).grid(
            row=0, column=0, sticky="w", padx=(0, S["2"]))
        self._client_combo = ctk.CTkComboBox(
            inner, values=[], state="readonly", width=220,
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"], dropdown_fg_color=COLORS["bg_surface"],
            command=self._on_client_selected)
        self._client_combo.grid(row=0, column=1, sticky="w", padx=(0, S["4"]))

        # Trip selector
        ctk.CTkLabel(inner, text=t("invoice_editor.select_trip"),
                     font=FONTS["label"], text_color=COLORS["text_muted"]).grid(
            row=0, column=2, sticky="w", padx=(0, S["2"]))
        self._trip_combo = ctk.CTkComboBox(
            inner, values=[], state="readonly", width=240,
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"], dropdown_fg_color=COLORS["bg_surface"],
            command=self._on_trip_selected)
        self._trip_combo.grid(row=0, column=3, sticky="w", padx=(0, S["3"]))

        # Auto-fill button
        self._auto_btn = ctk.CTkButton(
            inner, text=t("invoice_editor.auto_fill"), width=90, height=34,
            font=FONTS["body_bold"], fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], text_color="#ffffff",
            command=self._auto_fill_all)
        self._auto_btn.grid(row=0, column=4, sticky="e")

        # Mode checkboxes
        mode_frame = ctk.CTkFrame(inner, fg_color="transparent")
        mode_frame.grid(row=0, column=5, sticky="e", padx=(S["3"], 0))
        self._cb_client = ctk.CTkCheckBox(mode_frame, text=t("invoice.radio_client_invoice"),
                                          variable=self._is_client_invoice,
                                          command=lambda: self._on_mode_changed("client"),
                                          font=FONTS["small"], text_color=COLORS["text_secondary"],
                                          fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])
        self._cb_client.pack(side="left", padx=(0, S["2"]))
        self._cb_internal = ctk.CTkCheckBox(mode_frame, text=t("invoice.radio_internal_invoice"),
                                            variable=self._is_internal_invoice,
                                            command=lambda: self._on_mode_changed("internal"),
                                            font=FONTS["small"], text_color=COLORS["text_secondary"],
                                            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])
        self._cb_internal.pack(side="left")

        # Refresh buttons
        ctk.CTkButton(inner, text="\U0001F504", width=34, height=34,
                      font=FONTS["body"], fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      command=self._refresh_all).grid(
            row=0, column=5, sticky="e", padx=(S["2"], 0))

    def _build_main_area(self, parent):
        main = ctk.CTkFrame(parent, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)   # canvas
        main.columnconfigure(1, weight=0)   # right panels
        main.rowconfigure(0, weight=1)

        self._build_invoice_canvas(main)
        self._build_right_panels(main)

    # ── RIGHT PANELS ──────────────────────────────────────────────

    def _build_right_panels(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent", width=300)
        right.grid(row=0, column=1, sticky="nsew", padx=(S["4"], S["4"]))
        right.grid_propagate(False)
        right.rowconfigure(2, weight=1)

        self._build_financial_panel(right)
        self._build_branding_panel(right)

    def _build_financial_panel(self, parent):
        outer = ctk.CTkFrame(parent, fg_color=COLORS["border"], corner_radius=RADIUS_CARD + 1)
        outer.grid(row=0, column=0, sticky="ew", pady=(S["2"], S["3"]))
        card = ctk.CTkFrame(outer, fg_color=COLORS["bg_surface"], corner_radius=RADIUS_CARD)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        ctk.CTkLabel(card, text=t("invoice_editor.financial_controls").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", padx=S["4"], pady=(S["4"], S["2"]))

        # Tax rate
        tax_f = ctk.CTkFrame(card, fg_color="transparent")
        tax_f.pack(fill="x", padx=S["4"], pady=(0, S["2"]))
        ctk.CTkLabel(tax_f, text=t("invoice_editor.tax_rate"),
                     font=FONTS["small"], text_color=COLORS["text_secondary"],
                     width=50, anchor="w").pack(side="left")
        self._tax_combo = ctk.CTkComboBox(
            tax_f, values=["0", "5", "9", "19", "20", "21", "24", "25"],
            variable=self._tax_rate, width=80, font=FONTS["body"],
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"], text_color=COLORS["text_primary"])
        self._tax_combo.pack(side="left", padx=(S["2"], 0))
        ctk.CTkLabel(tax_f, text="%", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(S["1"], 0))
        self._tax_combo.bind("<<ComboboxSelected>>", lambda e: self._recalc_all())
        self._tax_combo.bind("<KeyRelease>", lambda e: self._recalc_all())

        # Discount type
        disc_row = ctk.CTkFrame(card, fg_color="transparent")
        disc_row.pack(fill="x", padx=S["4"], pady=(0, S["2"]))
        ctk.CTkLabel(disc_row, text=t("invoice_editor.discount"),
                     font=FONTS["small"], text_color=COLORS["text_secondary"],
                     width=50, anchor="w").pack(side="left")
        disc_values = [t("invoice_editor.discount_percentage"),
                       t("invoice_editor.discount_fixed")]
        self._disc_type_combo = ctk.CTkComboBox(
            disc_row, values=disc_values,
            command=self._on_discount_type_changed, width=90, font=FONTS["body"],
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"], text_color=COLORS["text_primary"])
        self._disc_type_combo.pack(side="left", padx=(S["2"], 0))
        self._disc_type_combo.set(disc_values[0])
        self._discount_type.set(disc_values[0])

        self._disc_entry = ctk.CTkEntry(
            disc_row, textvariable=self._discount_value, width=70, height=32,
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self._disc_entry.pack(side="left", padx=(S["2"], 0))
        self._disc_entry.bind("<KeyRelease>", lambda e: self._recalc_all())

        self._disc_symbol_lbl = ctk.CTkLabel(disc_row, text="%", font=FONTS["small"],
                                              text_color=COLORS["text_muted"])
        self._disc_symbol_lbl.pack(side="left", padx=(S["1"], 0))

        # Currency
        curr_row = ctk.CTkFrame(card, fg_color="transparent")
        curr_row.pack(fill="x", padx=S["4"], pady=(0, S["3"]))
        ctk.CTkLabel(curr_row, text=t("invoice_editor.currency"),
                     font=FONTS["small"], text_color=COLORS["text_secondary"],
                     width=50, anchor="w").pack(side="left")
        self._curr_combo = ctk.CTkComboBox(
            curr_row, values=["EUR", "RON", "USD", "GBP"],
            variable=self._currency, width=80, font=FONTS["body"],
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"], text_color=COLORS["text_primary"],
            command=lambda e: self._recalc_all())
        self._curr_combo.pack(side="left", padx=(S["2"], 0))
        self._curr_combo.configure(state="readonly")

        # Totals display
        sep = ctk.CTkFrame(card, fg_color=COLORS["border"], height=1, corner_radius=0)
        sep.pack(fill="x", padx=S["4"], pady=(0, S["3"]))

        self._totals_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._totals_frame.pack(fill="x", padx=S["4"], pady=(0, S["4"]))
        self._build_totals_labels()

    def _build_totals_labels(self):
        for w in self._totals_frame.winfo_children():
            w.destroy()

        self._subtotal_lbl = self._totals_row(t("invoice_editor.subtotal"), "0.00")
        self._tax_lbl = self._totals_row(t("invoice_editor.tax"), "0.00")
        self._discount_lbl = self._totals_row(t("invoice_editor.discount"), "0.00")

        sep = ctk.CTkFrame(self._totals_frame, fg_color=COLORS["border"], height=1, corner_radius=0)
        sep.pack(fill="x", pady=(S["2"], S["2"]))

        self._grand_lbl = self._totals_row(t("invoice_editor.grand_total"), "0.00", bold=True)

    def _totals_row(self, label, value, bold=False):
        row = ctk.CTkFrame(self._totals_frame, fg_color="transparent")
        row.pack(fill="x", pady=(0, S["1"]))
        f = FONTS["body_bold"] if bold else FONTS["small"]
        c = COLORS["text_primary"] if bold else COLORS["text_secondary"]
        ctk.CTkLabel(row, text=label, font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w").pack(side="left")
        lbl = ctk.CTkLabel(row, text=value, font=f, text_color=c, anchor="e")
        lbl.pack(side="right")
        return lbl

    def _build_branding_panel(self, parent):
        outer = ctk.CTkFrame(parent, fg_color=COLORS["border"], corner_radius=RADIUS_CARD + 1)
        outer.grid(row=1, column=0, sticky="ew")
        card = ctk.CTkFrame(outer, fg_color=COLORS["bg_surface"], corner_radius=RADIUS_CARD)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        ctk.CTkLabel(card, text=t("invoice_editor.branding").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", padx=S["4"], pady=(S["4"], S["2"]))

        # Logo
        self._brand_row(card, t("invoice_editor.logo"), self._logo_path, self._browse_logo)

        # Company color
        color_row = ctk.CTkFrame(card, fg_color="transparent")
        color_row.pack(fill="x", padx=S["4"], pady=(0, S["2"]))
        ctk.CTkLabel(color_row, text=t("invoice_editor.company_color"),
                     font=FONTS["small"], text_color=COLORS["text_secondary"],
                     width=70, anchor="w").pack(side="left")
        self._color_swatch = ctk.CTkFrame(color_row, width=24, height=24,
                                           fg_color=self._company_color.get(),
                                           corner_radius=4)
        self._color_swatch.pack(side="left", padx=(S["2"], 0))
        self._color_swatch.bind("<Button-1>", lambda e: self._pick_color())
        ctk.CTkButton(color_row, text=t("invoice_editor.pick_color"), width=60, height=28,
                      font=FONTS["small"], fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      command=self._pick_color).pack(side="left", padx=(S["2"], 0))

        # Signature
        self._brand_row(card, t("invoice_editor.signature"), self._signature_path, self._browse_signature)

        # Stamp
        self._brand_row(card, t("invoice_editor.stamp"), self._stamp_path, self._browse_stamp)

    def _brand_row(self, parent, label, var, cmd):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=S["4"], pady=(0, S["2"]))
        ctk.CTkLabel(row, text=label, font=FONTS["small"],
                     text_color=COLORS["text_secondary"],
                     width=70, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(row, textvariable=var, height=28, font=FONTS["small"],
                             fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                             text_color=COLORS["text_muted"], state="readonly")
        entry.pack(side="left", fill="x", expand=True, padx=(S["2"], 0))
        btn = ctk.CTkButton(row, text=t("invoice_editor.browse"), width=50, height=28,
                            font=FONTS["small"], fg_color=COLORS["bg_elevated"],
                            hover_color=COLORS["border_hover"],
                            text_color=COLORS["text_primary"], command=cmd)
        btn.pack(side="left", padx=(S["1"], 0))

    # ═══════════════════════════════════════════════════════════════
    # INVOICE CANVAS (live preview)
    # ═══════════════════════════════════════════════════════════════

    def _build_invoice_canvas(self, parent):
        outer = ctk.CTkFrame(parent, fg_color=COLORS["border"], corner_radius=RADIUS_CARD + 1)
        outer.grid(row=0, column=0, sticky="nsew", padx=(S["4"], 0), pady=S["2"])
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        self._canvas_scroll = ctk.CTkScrollableFrame(
            outer, fg_color=COLORS["bg_surface"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_hover"])
        self._canvas_scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        self._canvas_inner = ctk.CTkFrame(self._canvas_scroll, fg_color=COLORS["bg_surface"])
        self._canvas_inner.pack(fill="both", expand=True, padx=S["8"], pady=S["6"])

        # Invoice header (logo + title)
        self._build_canvas_header()

        # From / Bill To
        self._build_canvas_from_bill_to()

        # Trip details
        self._build_canvas_trip_details()

        # Invoice metadata
        self._build_canvas_metadata()

        # Description (free text)
        self._build_canvas_description()

        # Line items table
        self._build_canvas_line_items()

        # Notes
        self._build_canvas_notes()

        # Totals
        self._build_canvas_totals()

    def _build_canvas_header(self):
        hdr = ctk.CTkFrame(self._canvas_inner, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, S["6"]))

        # Logo placeholder
        logo_frame = ctk.CTkFrame(hdr, fg_color=COLORS["bg_elevated"],
                                  width=100, height=60, corner_radius=4)
        logo_frame.pack(side="left")
        logo_frame.pack_propagate(False)
        self._canvas_logo_lbl = ctk.CTkLabel(
            logo_frame, text="LOGO", font=FONTS["label"],
            text_color=COLORS["text_muted"])
        self._canvas_logo_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.pack(side="right", anchor="e")
        self._canvas_title_lbl = ctk.CTkLabel(
            title_frame, text="INVOICE", font=FONTS["display"],
            text_color=COLORS["accent"])
        self._canvas_title_lbl.pack(anchor="e")
        self._canvas_inv_num_lbl = ctk.CTkLabel(
            title_frame, text="", font=FONTS["h3"],
            text_color=COLORS["text_secondary"])
        self._canvas_inv_num_lbl.pack(anchor="e")

        sep = ctk.CTkFrame(self._canvas_inner, fg_color=COLORS["border"],
                           height=2, corner_radius=0)
        sep.pack(fill="x", pady=(0, S["6"]))

    def _build_canvas_from_bill_to(self):
        row = ctk.CTkFrame(self._canvas_inner, fg_color="transparent")
        row.pack(fill="x", pady=(0, S["6"]))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        # From (Company)
        from_frame = ctk.CTkFrame(row, fg_color="transparent")
        from_frame.grid(row=0, column=0, sticky="nsew", padx=(0, S["4"]))
        ctk.CTkLabel(from_frame, text=t("invoice_editor.from").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["2"]))

        self._c_company_name = self._canvas_label(from_frame, self._company_name, bold=True)
        self._c_company_cui = self._canvas_label(from_frame, self._company_cui)
        self._c_company_reg = self._canvas_label(from_frame, self._company_reg)
        self._c_company_addr = self._canvas_label(from_frame, self._company_address)
        self._c_company_phone = self._canvas_label(from_frame, self._company_phone)
        self._c_company_email = self._canvas_label(from_frame, self._company_email)

        # Edit company btn
        ctk.CTkButton(from_frame, text="\u270F", width=28, height=28,
                      font=FONTS["small"], fg_color="transparent",
                      hover_color=COLORS["bg_elevated"],
                      text_color=COLORS["text_muted"],
                      command=self._open_company_editor).pack(anchor="w")

        # Bill To (Client)
        to_frame = ctk.CTkFrame(row, fg_color="transparent")
        to_frame.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(to_frame, text=t("invoice_editor.bill_to").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["2"]))

        self._c_client_name = self._canvas_label(to_frame, self._client_name, bold=True)
        self._c_client_vat = self._canvas_label(to_frame, self._client_vat)
        self._c_client_addr = self._canvas_label(to_frame, self._client_address)
        self._c_client_phone = self._canvas_label(to_frame, self._client_phone)
        self._c_client_email = self._canvas_label(to_frame, self._client_email)

    def _canvas_label(self, parent, var, bold=False):
        f = FONTS["body_bold"] if bold else FONTS["body"]
        lbl = ctk.CTkLabel(parent, textvariable=var, font=f,
                           text_color=COLORS["text_primary"], anchor="w")
        lbl.pack(anchor="w")
        return lbl

    def _build_canvas_trip_details(self):
        trip_frame = ctk.CTkFrame(self._canvas_inner, fg_color=COLORS["bg_elevated"],
                                  corner_radius=6)
        trip_frame.pack(fill="x", pady=(0, S["4"]))

        ctk.CTkLabel(trip_frame, text=t("invoice_editor.trip_details").upper(),
                     font=FONTS["label"], text_color=COLORS["accent"],
                     anchor="w").pack(anchor="w", padx=S["3"], pady=(S["3"], S["2"]))

        # Vehicle info row
        info_row = ctk.CTkFrame(trip_frame, fg_color="transparent")
        info_row.pack(fill="x", padx=S["3"], pady=(0, S["2"]))
        info_row.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        fields = [
            (t("invoice_editor.truck_plate"), self._truck_plate, 0, 1),
            (t("invoice_editor.driver"), self._driver_name, 2, 3),
            (t("invoice_editor.distance"), self._distance, 4, 5),
        ]
        for label_text, var, lbl_col, val_col in fields:
            ctk.CTkLabel(info_row, text=label_text, font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         anchor="w").grid(row=0, column=lbl_col, sticky="w",
                                          padx=S["2"], pady=(0, S["1"]))
            entry = ctk.CTkEntry(info_row, textvariable=var, height=28, font=FONTS["body"],
                                 fg_color=COLORS["bg_surface"],
                                 border_color=COLORS["border"],
                                 text_color=COLORS["text_primary"])
            entry.grid(row=1, column=val_col, sticky="ew", padx=S["2"], pady=(0, S["1"]))

        # Stops section
        self._stops_frame = ctk.CTkFrame(trip_frame, fg_color="transparent")
        self._stops_frame.pack(fill="x", padx=S["3"], pady=(0, S["3"]))

        # Initialize with one loading and one unloading stop
        if not self._loading_stops:
            self._loading_stops = [{"var": tk.StringVar()}]
        if not self._unloading_stops:
            self._unloading_stops = [{"var": tk.StringVar()}]
        self._rebuild_stops()

    def _rebuild_stops(self):
        """Rebuild the dynamic stops section."""
        if not self._stops_frame:
            return
        for w in self._stops_frame.winfo_children():
            w.destroy()

        # Loading stops
        ctk.CTkLabel(self._stops_frame, text=t("invoice_editor.loading_stops"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(S["1"], S["1"]))

        for i, stop in enumerate(self._loading_stops):
            self._build_stop_row(self._stops_frame, stop, i, "loading")

        # Add loading stop button
        add_load = ctk.CTkFrame(self._stops_frame, fg_color="transparent")
        add_load.pack(fill="x", pady=(0, S["2"]))
        ctk.CTkButton(add_load, text="+ " + t("invoice_editor.add_loading_stop"),
                      font=FONTS["small"], height=24,
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_secondary"],
                      command=self._add_loading_stop).pack(side="left")

        # Divider
        sep = ctk.CTkFrame(self._stops_frame, fg_color=COLORS["border"],
                           height=1, corner_radius=0)
        sep.pack(fill="x", pady=S["2"])

        # Unloading stops
        ctk.CTkLabel(self._stops_frame, text=t("invoice_editor.unloading_stops"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(S["1"], S["1"]))

        for i, stop in enumerate(self._unloading_stops):
            self._build_stop_row(self._stops_frame, stop, i, "unloading")

        # Add unloading stop button
        add_unload = ctk.CTkFrame(self._stops_frame, fg_color="transparent")
        add_unload.pack(fill="x", pady=(0, S["1"]))
        ctk.CTkButton(add_unload, text="+ " + t("invoice_editor.add_unloading_stop"),
                      font=FONTS["small"], height=24,
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_secondary"],
                      command=self._add_unloading_stop).pack(side="left")

    def _build_stop_row(self, parent, stop, idx, stop_type):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, S["1"]))

        label_text = f"{t('invoice_editor.loading_label') if stop_type == 'loading' else t('invoice_editor.unloading_label')} {idx + 1}"
        ctk.CTkLabel(row, text=label_text, font=FONTS["small"],
                     text_color=COLORS["text_muted"], width=70,
                     anchor="w").pack(side="left")

        entry = ctk.CTkEntry(row, textvariable=stop["var"], height=28,
                             font=FONTS["body"], fg_color=COLORS["bg_input"],
                             border_color=COLORS["border"],
                             text_color=COLORS["text_primary"])
        entry.pack(side="left", fill="x", expand=True, padx=(S["2"], 0))

        # Remove button (only if more than 1 stop of this type)
        stops_list = self._loading_stops if stop_type == "loading" else self._unloading_stops
        if len(stops_list) > 1:
            ctk.CTkButton(row, text="\u2716", width=22, height=22,
                          font=("Segoe UI", 9), fg_color="transparent",
                          hover_color=COLORS["danger_dim"],
                          text_color=COLORS["text_danger"],
                          command=lambda t=stop_type, i=idx: self._remove_stop(t, i)).pack(
                side="left", padx=(S["1"], 0))

    def _add_loading_stop(self):
        self._loading_stops.append({"var": tk.StringVar()})
        self._rebuild_stops()

    def _add_unloading_stop(self):
        self._unloading_stops.append({"var": tk.StringVar()})
        self._rebuild_stops()

    def _remove_stop(self, stop_type, idx):
        stops = self._loading_stops if stop_type == "loading" else self._unloading_stops
        if len(stops) > 1:
            del stops[idx]
            self._rebuild_stops()

    def _build_canvas_description(self):
        desc_frame = ctk.CTkFrame(self._canvas_inner, fg_color="transparent")
        desc_frame.pack(fill="x", pady=(0, S["4"]))
        ctk.CTkLabel(desc_frame, text=t("invoice_editor.description"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["1"]))
        self._desc_text = ctk.CTkTextbox(desc_frame, height=60, font=FONTS["body"],
                                         fg_color=COLORS["bg_elevated"],
                                         border_color=COLORS["border"],
                                         border_width=1,
                                         text_color=COLORS["text_primary"],
                                         corner_radius=6)
        self._desc_text.pack(fill="x")

    def _build_canvas_metadata(self):
        meta = ctk.CTkFrame(self._canvas_inner, fg_color=COLORS["bg_elevated"],
                            corner_radius=6)
        meta.pack(fill="x", pady=(0, S["6"]))
        meta.columnconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=1)

        fields = [
            (t("invoice_editor.invoice_number"), self._invoice_number, 0, 1),
            (t("invoice_editor.issue_date"), self._issue_date, 2, 3),
            (t("invoice_editor.due_date"), self._due_date, 4, 5),
            (t("invoice_editor.payment_terms"), self._payment_terms, 6, 7),
        ]

        for label_text, var, lbl_col, val_col in fields:
            ctk.CTkLabel(meta, text=label_text, font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         anchor="w").grid(row=0, column=lbl_col, sticky="w",
                                          padx=S["3"], pady=(S["3"], S["1"]))
            entry = ctk.CTkEntry(meta, textvariable=var, height=30, font=FONTS["body"],
                                 fg_color=COLORS["bg_surface"],
                                 border_color=COLORS["border"],
                                 text_color=COLORS["text_primary"])
            entry.grid(row=1, column=val_col, sticky="ew",
                       padx=S["3"], pady=(0, S["3"]))
            entry.bind("<KeyRelease>", lambda e: self._recalc_all())

    def _build_canvas_line_items(self):
        # Container for the additional items section
        self._lit_container = ctk.CTkFrame(self._canvas_inner, fg_color="transparent")
        self._lit_container.pack(fill="x", pady=(0, S["4"]))

        # Header
        lit_header = ctk.CTkFrame(self._lit_container, fg_color=COLORS["bg_elevated"],
                                  corner_radius=6)
        lit_header.pack(fill="x", pady=(0, S["1"]))
        lit_header.columnconfigure(0, weight=0, minsize=30)   # #
        lit_header.columnconfigure(1, weight=3)                # Description
        lit_header.columnconfigure(2, weight=0, minsize=95)   # Amount
        lit_header.columnconfigure(3, weight=0, minsize=85)   # Actions

        headers = ["#", t("invoice_editor.description"), t("invoice_editor.amount"), ""]
        for i, h in enumerate(headers):
            ctk.CTkLabel(lit_header, text=h, font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         anchor="w" if i == 1 else "center").grid(
                row=0, column=i, sticky="ew", padx=S["2"], pady=(S["2"], S["2"]))

        # Rows container
        self._lit_rows_frame = ctk.CTkFrame(self._lit_container, fg_color="transparent")
        self._lit_rows_frame.pack(fill="x")

        # Add row button
        btn_row = ctk.CTkFrame(self._lit_container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(S["2"], 0))
        ctk.CTkButton(btn_row, text="+ " + t("invoice_editor.add_row"),
                      font=FONTS["body"], height=30,
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_secondary"],
                      command=self._add_addon_row).pack(side="left", padx=(0, S["2"]))

    def _build_canvas_notes(self):
        notes_frame = ctk.CTkFrame(self._canvas_inner, fg_color="transparent")
        notes_frame.pack(fill="x", pady=(0, S["6"]))

        ctk.CTkLabel(notes_frame, text=t("invoice_editor.notes"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["1"]))

        self._notes_entry = ctk.CTkTextbox(notes_frame, height=60, font=FONTS["body"],
                                           fg_color=COLORS["bg_elevated"],
                                           border_color=COLORS["border"],
                                           border_width=1,
                                           text_color=COLORS["text_primary"],
                                           corner_radius=6)
        self._notes_entry.pack(fill="x")

    def _build_canvas_totals(self):
        self._canvas_totals_frame = ctk.CTkFrame(self._canvas_inner, fg_color=COLORS["bg_elevated"],
                                                  corner_radius=6)
        self._canvas_totals_frame.pack(fill="x", pady=(S["4"], 0))
        self._canvas_totals_frame.columnconfigure(0, weight=1)
        self._canvas_totals_frame.columnconfigure(1, weight=0, minsize=140)

        self._canvas_subtotal = self._canvas_total_row(0, t("invoice_editor.subtotal"))
        self._canvas_tax_label = self._canvas_total_row(1, t("invoice_editor.tax"))
        self._canvas_discount_label = self._canvas_total_row(2, t("invoice_editor.discount"))
        sep = ctk.CTkFrame(self._canvas_totals_frame, fg_color=COLORS["border"],
                           height=1, corner_radius=0)
        sep.grid(row=3, column=0, columnspan=2, sticky="ew", padx=S["3"], pady=(S["2"], S["2"]))
        self._canvas_grand = self._canvas_total_row(4, t("invoice_editor.grand_total"), bold=True)

    def _canvas_total_row(self, row_idx, label, bold=False):
        f = FONTS["body_bold"] if bold else FONTS["body"]
        c = COLORS["text_primary"] if bold else COLORS["text_secondary"]
        lbl = ctk.CTkLabel(self._canvas_totals_frame, text=label, font=f,
                           text_color=COLORS["text_muted"], anchor="w")
        lbl.grid(row=row_idx, column=0, sticky="w", padx=S["3"], pady=(S["1"], S["1"]))
        val = ctk.CTkLabel(self._canvas_totals_frame, text="0.00", font=f,
                           text_color=c, anchor="e")
        val.grid(row=row_idx, column=1, sticky="e", padx=S["3"], pady=(S["1"], S["1"]))
        return val

    # ═══════════════════════════════════════════════════════════════
    # BOTTOM BAR
    # ═══════════════════════════════════════════════════════════════

    def _build_bottom_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"], height=52, corner_radius=0)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.grid(row=0, column=0, columnspan=6, sticky="ew", padx=S["4"], pady=S["2"])

        actions = [
            ("\U0001F50D " + t("invoice_editor.preview_pdf"), self._preview_pdf, COLORS["bg_elevated"]),
            ("\U0001F4C4 " + t("invoice_editor.generate_pdf"), self._generate_pdf, COLORS["accent"]),
            ("\U0001F5A8 " + t("invoice_editor.print"), self._print_invoice, COLORS["bg_elevated"]),
            ("\U0001F4E7 " + t("invoice_editor.email"), self._email_invoice, COLORS["info"]),
            ("\U0001F4BE " + t("invoice_editor.save_draft"), self._save_draft, COLORS["bg_elevated"]),
            ("\U0001F4C2 " + t("invoice_editor.load_draft"), self._load_draft, COLORS["bg_elevated"]),
        ]

        for i, (label, cmd, color) in enumerate(actions):
            btn = ctk.CTkButton(inner, text=label, command=cmd, height=36,
                                font=FONTS["body_bold"], fg_color=color,
                                hover_color=COLORS["accent_hover"] if color == COLORS["accent"]
                                else COLORS["border_hover"],
                                text_color="#ffffff" if color in (COLORS["accent"], COLORS["info"])
                                else COLORS["text_secondary"])
            btn.grid(row=0, column=i, sticky="ew", padx=S["1"])

    # ═══════════════════════════════════════════════════════════════
    # DATA LOADING
    # ═══════════════════════════════════════════════════════════════

    def _load_company_config(self):
        conf = load_company_config()
        self._company_name.set(conf.get("company_name", ""))
        self._company_cui.set(conf.get("cui", ""))
        self._company_reg.set(conf.get("reg_number", ""))
        self._company_address.set(conf.get("address", ""))
        self._company_phone.set(conf.get("phone", ""))
        self._company_email.set(conf.get("email", ""))
        # Branding defaults from settings
        logo = conf.get("logo_path", "")
        if logo:
            self._logo_path.set(logo)
            self._update_logo_preview(logo)
        color = conf.get("company_color", COLORS["accent"])
        if color:
            self._company_color.set(color)
        sig = conf.get("signature_path", "")
        if sig:
            self._signature_path.set(sig)
        stamp = conf.get("stamp_path", "")
        if stamp:
            self._stamp_path.set(stamp)

    def _load_clients(self):
        try:
            self._clients = self._client_repo.get_all()
            self._client_map = {c["name"]: c for c in self._clients}
            names = list(self._client_map.keys())
            self._client_combo.configure(values=names)
            if names:
                self._client_combo.set("")
        except Exception as e:
            _logger.warning("Could not load clients: %s", e)

    def _load_trips(self):
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
            self._trip_combo.configure(values=labels)
            if labels:
                self._trip_combo.set("")
        except Exception as e:
            _logger.warning("Could not load trips: %s", e)

    def _refresh_all(self):
        self._load_clients()
        self._load_trips()

    # ═══════════════════════════════════════════════════════════════
    # CLIENT / TRIP SELECTION
    # ═══════════════════════════════════════════════════════════════

    def _on_client_selected(self, choice):
        if not choice or choice not in self._client_map:
            self._selected_client_id = None
            return
        client = self._client_map[choice]
        self._selected_client_id = client["id"]
        self._client_name.set(client.get("name", ""))
        self._client_vat.set(client.get("vat_number", ""))
        self._client_address.set(client.get("address", ""))
        self._client_phone.set(client.get("phone", ""))
        self._client_email.set(client.get("email", ""))

    def _on_trip_selected(self, choice):
        if not choice or choice not in self._trip_map:
            self._selected_trip_id = None
            self._selected_trip_data = None
            return
        trip = self._trip_map[choice]
        self._selected_trip_id = trip["id"]
        self._selected_trip_data = trip
        self._auto_fill_from_trip()

    def _auto_fill_from_trip(self):
        """Fill invoice fields from selected trip data and route stops."""
        trip = self._selected_trip_data
        if not trip:
            return

        # Trip details
        self._truck_plate.set(trip.get("truck_number", ""))
        self._driver_name.set(trip.get("driver_name", ""))
        dist = trip.get("distance_km", 0) or 0
        self._distance.set(f"{dist:,.1f} km" if dist else "")

        # Fetch route stops for loading/unloading cities
        route_id = trip.get("route_history_v2_id")
        if route_id:
            self._fill_cities_from_route(route_id)

        # Auto-set dates from trip
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        if start:
            self._issue_date.set(start[:10] if len(start) >= 10 else start)
        if end:
            try:
                dt = datetime.strptime(end[:10], "%Y-%m-%d")
                self._due_date.set((dt + timedelta(days=30)).strftime("%Y-%m-%d"))
            except ValueError:
                pass

        # Auto-fill description from trip
        if dist > 0:
            current_desc = self._desc_text.get("1.0", "end-1c").strip() if hasattr(self, '_desc_text') else ""
            if not current_desc:
                self._desc_text.delete("1.0", "end")
                self._desc_text.insert("1.0", t("invoice_pdf.service_desc").format(dist))

        # Set trip base price in totals section
        price = round(float(trip.get("total_price_eur", 0) or 0), 2)
        self._trip_base_price.set(f"{price:.2f}")

        # Handle VAT if present on trip
        pre_vat = trip.get("price_pre_vat")
        vat_pct = trip.get("vat_percent")
        if pre_vat is not None and vat_pct is not None:
            self._trip_price_pre_vat.set(str(pre_vat))
            self._trip_vat_percent.set(str(vat_pct))

        # Clear existing addon items and add empty one
        self._addon_items = [self._create_addon_data()]
        self._rebuild_addon_rows()
        self._recalc_all()

        # Auto-select client if not selected
        client_name = trip.get("client_name", "")
        if client_name and not self._selected_client_id and client_name in self._client_map:
            self._client_combo.set(client_name)
            self._on_client_selected(client_name)

    def _fill_cities_from_route(self, route_id):
        """Extract loading/unloading cities from route stops JSON."""
        try:
            import json
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
                self._loading_stops[0]["var"].set(origin)
            if destination and self._unloading_stops:
                self._unloading_stops[0]["var"].set(destination)
        except Exception:
            pass

    def _auto_fill_all(self):
        """Manual auto-fill trigger."""
        choice = self._client_combo.get()
        if choice and choice in self._client_map:
            self._on_client_selected(choice)
        choice = self._trip_combo.get()
        if choice and choice in self._trip_map:
            self._on_trip_selected(choice)

    def _on_mode_changed(self, mode):
        if mode == "client":
            if self._is_client_invoice.get():
                self._is_internal_invoice.set(False)
        else:
            if self._is_internal_invoice.get():
                self._is_client_invoice.set(False)

    # ═══════════════════════════════════════════════════════════════
    # CALCULATIONS
    # ═══════════════════════════════════════════════════════════════
        """Update data model and recalculate when any field changes."""
        if idx >= len(self._addon_items):
            return
        item = self._addon_items[idx]
        try:
            item["description"] = item["desc_var"].get()
            item["amount"] = round(float(item["amt_var"].get() or 0), 2)
        except ValueError:
            item["amount"] = 0.0
        self._recalc_all()

    # ═══════════════════════════════════════════════════════════════
    # CALCULATIONS
    # ═══════════════════════════════════════════════════════════════

    def _recalc_all(self):
        self._refresh_totals_display()

    def _refresh_totals_display(self):
        """Update all totals displays based on addon items and settings."""
        try:
            tax_rate = float(self._tax_rate.get() or 0)
            disc_val = float(self._discount_value.get() or 0)
            trip_price = float(self._trip_base_price.get() or 0)
        except ValueError:
            tax_rate = 0
            disc_val = 0
            trip_price = 0

        disc_type = self._discount_type.get()
        currency = self._currency.get()

        # Trip base price
        subtotal = round(trip_price, 2)

        # Addon items
        for item in self._addon_items:
            try:
                item["amount"] = round(float(item["amt_var"].get() or 0), 2)
            except ValueError:
                item["amount"] = 0.0
            subtotal = round(subtotal + item["amount"], 2)

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
        if hasattr(self, '_subtotal_lbl'):
            self._subtotal_lbl.configure(text=f"{sym}{subtotal:,.2f}")
        if hasattr(self, '_tax_lbl'):
            self._tax_lbl.configure(text=f"{sym}{total_tax:,.2f}")
        if hasattr(self, '_discount_lbl'):
            self._discount_lbl.configure(text=f"-{sym}{discount:,.2f}")
        if hasattr(self, '_grand_lbl'):
            self._grand_lbl.configure(text=f"{sym}{grand_total:,.2f}")

        # Update canvas totals
        if hasattr(self, '_canvas_subtotal'):
            self._canvas_subtotal.configure(text=f"{sym}{subtotal:,.2f}")
        if hasattr(self, '_canvas_tax_label'):
            self._canvas_tax_label.configure(text=f"{sym}{total_tax:,.2f}")
        if hasattr(self, '_canvas_discount_label'):
            self._canvas_discount_label.configure(text=f"-{sym}{discount:,.2f}")
        if hasattr(self, '_canvas_grand'):
            self._canvas_grand.configure(text=f"{sym}{grand_total:,.2f}")

        # Update canvas header
        if hasattr(self, '_canvas_inv_num_lbl'):
            self._canvas_inv_num_lbl.configure(text=self._invoice_number.get())

        # Update discount symbol
        if hasattr(self, '_disc_symbol_lbl'):
            if is_percent:
                self._disc_symbol_lbl.configure(text="%")
            else:
                self._disc_symbol_lbl.configure(text=sym)

    def _get_currency_symbol(self, code):
        symbols = {"EUR": "\u20AC", "RON": "lei", "USD": "$", "GBP": "\u00A3"}
        return symbols.get(code, code)

    def _on_discount_type_changed(self, choice):
        self._discount_type.set(choice)
        self._recalc_all()

    # ═══════════════════════════════════════════════════════════════
    # BRANDING ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def _update_logo_preview(self, path):
        """Update the canvas logo area to show the selected logo filename."""
        if path and os.path.isfile(path):
            fname = os.path.basename(path)
            self._canvas_logo_lbl.configure(text=fname[:20], font=("Segoe UI", 8))
        else:
            self._canvas_logo_lbl.configure(text="LOGO", font=FONTS["label"])

    def _browse_logo(self):
        path = filedialog.askopenfilename(
            title=t("invoice_editor.select_logo"),
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                       ("All files", "*.*")])
        if path:
            self._logo_path.set(path)
            self._update_logo_preview(path)

    def _browse_signature(self):
        path = filedialog.askopenfilename(
            title=t("invoice_editor.select_signature"),
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
                       ("All files", "*.*")])
        if path:
            self._signature_path.set(path)

    def _browse_stamp(self):
        path = filedialog.askopenfilename(
            title=t("invoice_editor.select_stamp"),
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
                       ("All files", "*.*")])
        if path:
            self._stamp_path.set(path)

    def _pick_color(self):
        import tkinter.colorchooser as cc
        result = cc.askcolor(color=self._company_color.get(),
                             title=t("invoice_editor.pick_color_title"))
        if result and result[1]:
            self._company_color.set(result[1])
            self._color_swatch.configure(fg_color=result[1])
            try:
                self._canvas_title_lbl.configure(text_color=result[1])
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════
    # COMPANY EDITOR (inline modal replacement)
    # ═══════════════════════════════════════════════════════════════

    def _open_company_editor(self):
        dialog = CompanyEditorDialog(self.frame, self._company_name.get(),
                                     self._company_cui.get(),
                                     self._company_reg.get(),
                                     self._company_address.get(),
                                     self._company_phone.get(),
                                     self._company_email.get(),
                                     on_save=self._save_company_data)

    def _save_company_data(self, data):
        self._company_name.set(data["company_name"])
        self._company_cui.set(data["cui"])
        self._company_reg.set(data["reg_number"])
        self._company_address.set(data["address"])
        self._company_phone.set(data["phone"])
        self._company_email.set(data["email"])
        save_company_config(data)
        messagebox.showinfo(t("invoice.success_save_company"),
                            t("invoice.success_save_company"))

    # ═══════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def _collect_invoice_data(self):
        """Collect all invoice data into a dict for PDF generation."""
        conf = {
            "company_name": self._company_name.get(),
            "cui": self._company_cui.get(),
            "reg_number": self._company_reg.get(),
            "address": self._company_address.get(),
            "phone": self._company_phone.get(),
            "email": self._company_email.get(),
        }

        client = {
            "name": self._client_name.get(),
            "vat_number": self._client_vat.get(),
            "address": self._client_address.get(),
            "phone": self._client_phone.get(),
            "email": self._client_email.get(),
        }

        addon_items = []
        for item in self._addon_items:
            addon_items.append({
                "description": item["description"],
                "amount": item["amount"],
            })

        trip_price = round(float(self._trip_base_price.get() or 0), 2)
        addon_total = round(sum(li["amount"] for li in addon_items), 2)
        subtotal = round(trip_price + addon_total, 2)
        tax_rate = float(self._tax_rate.get() or 0)
        total_tax = round(subtotal * (tax_rate / 100), 2)
        disc_val = round(float(self._discount_value.get() or 0), 2)
        is_percent = self._discount_type.get() == t("invoice_editor.discount_percentage")
        discount = round(subtotal * (disc_val / 100), 2) if is_percent else disc_val
        grand_total = round(subtotal + total_tax - discount, 2)

        mode = "internal" if self._is_internal_invoice.get() else "client"

        description = self._desc_text.get("1.0", "end-1c") if hasattr(self, '_desc_text') else ""

        # Pre/post VAT from trip if available
        price_pre_vat = self._trip_price_pre_vat.get() if self._trip_price_pre_vat.get() else None
        vat_percent = self._trip_vat_percent.get() if self._trip_vat_percent.get() else None

        return {
            "invoice_number": self._invoice_number.get(),
            "issue_date": self._issue_date.get(),
            "due_date": self._due_date.get(),
            "payment_terms": self._payment_terms.get(),
            "currency": self._currency.get(),
            "company": conf,
            "client": client,
            "addon_items": addon_items,
            "trip_price": trip_price,
            "addon_total": addon_total,
            "description": description,
            "loading_stops": [s["var"].get() for s in self._loading_stops if s["var"].get().strip()],
            "unloading_stops": [s["var"].get() for s in self._unloading_stops if s["var"].get().strip()],
            "truck_plate": self._truck_plate.get(),
            "driver_name": self._driver_name.get(),
            "distance": self._distance.get(),
            "tax_rate": tax_rate,
            "discount_type": self._discount_type.get(),
            "discount_value": disc_val,
            "subtotal": subtotal,
            "total_tax": total_tax,
            "discount": discount,
            "grand_total": grand_total,
            "notes": self._notes_entry.get("1.0", "end-1c"),
            "logo_path": self._logo_path.get(),
            "signature_path": self._signature_path.get(),
            "stamp_path": self._stamp_path.get(),
            "company_color": self._company_color.get(),
            "trip_id": self._selected_trip_id,
            "trip_data": self._selected_trip_data,
            "mode": mode,
            "client_id": self._selected_client_id,
            "price_pre_vat": price_pre_vat,
            "vat_percent": vat_percent,
        }

    def _preview_pdf(self):
        """Generate PDF silently and open for preview."""
        data = self._collect_invoice_data()
        try:
            path = self._generate_rich_pdf(data, open_after=True, record=False)
            if path and os.path.exists(path):
                os.startfile(path)
        except Exception as e:
            _logger.error("Preview failed: %s", e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))

    def _generate_pdf(self):
        """Generate PDF invoice and record it."""
        data = self._collect_invoice_data()
        if not data["company"]["company_name"] or not data["company"]["cui"]:
            messagebox.showwarning(t("invoice.warning_fields_title"),
                                   t("invoice.warning_fields_msg"))
            return

        try:
            path = self._generate_rich_pdf(data, open_after=True, record=True)
            if path and os.path.exists(path):
                messagebox.showinfo(t("invoice.success_save_company"),
                                    t("invoice_editor.invoice_generated").format(path))
            else:
                raise FileNotFoundError(f"Invoice PDF not found: {path}")
        except Exception as e:
            _logger.error("Generation failed: %s", e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))

    def _generate_rich_pdf(self, data, open_after=False, record=True):
        """Generate a rich PDF using the enhanced InvoiceGenerator."""
        from services.invoicing.generator import InvoiceGenerator
        gen = InvoiceGenerator()
        path = gen.generate_rich(data)

        if record and path and os.path.exists(path):
            trip_data = data.get("trip_data") or {}
            trip_id = data.get("trip_id") or trip_data.get("id", 0)
            if trip_id:
                self._invoice_service.create_record(
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

    def _print_invoice(self):
        """Print the invoice PDF."""
        data = self._collect_invoice_data()
        try:
            path = self._generate_rich_pdf(data, record=False)
            if path and os.path.exists(path):
                os.startfile(path, "print")
        except Exception as e:
            _logger.error("Print failed: %s", e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))

    def _email_invoice(self):
        """Email the invoice using configured SMTP."""
        data = self._collect_invoice_data()
        recipient = data["client"].get("email", "") or self._company_email.get()

        if not recipient:
            result = tk.simpledialog.askstring(
                t("invoice_editor.email_to"),
                t("invoice_editor.enter_email"))
            if not result:
                return
            recipient = result

        try:
            path = self._generate_rich_pdf(data, record=True)
            if not path or not os.path.exists(path):
                raise FileNotFoundError(f"Invoice PDF not found: {path}")

            smtp_config = self.prefs.get_smtp_config()
            if not smtp_config or not smtp_config.get("smtp_server"):
                messagebox.showwarning(t("email.config_missing"),
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
                client=data["client"].get("name", t("invoice.default_client")))
            body = t("email.invoice_body").format(
                trip_id=data.get("trip_id", 0),
                company=data["company"].get("company_name", ""))

            if nc.send_email(recipient, subject, body, attachments=[path]):
                from services.operations.event_bus import INVOICE_EMAILED
                self._event_bus.publish(INVOICE_EMAILED, {
                    "trip_id": data.get("trip_id", 0),
                    "invoice_number": filename.replace(".pdf", ""),
                    "recipient": recipient,
                })
                messagebox.showinfo(t("invoice.button_email"),
                                    t("invoice.email_success").format(recipient))
            else:
                messagebox.showerror(t("invoice.email_failed"),
                                     t("invoice.email_failed").format(data.get("trip_id", 0)))
        except Exception as e:
            _logger.error("Email failed: %s", e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))

    # ═══════════════════════════════════════════════════════════════
    # DRAFT SYSTEM
    # ═══════════════════════════════════════════════════════════════

    def _save_draft(self):
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        data = self._collect_invoice_data()
        # Remove non-serializable trip_data
        data.pop("trip_data", None)
        data["saved_at"] = datetime.now().isoformat()

        name = tk.simpledialog.askstring(
            t("invoice_editor.save_draft"),
            t("invoice_editor.draft_name"))
        if not name:
            return

        safe_name = "".join(c for c in name if c.isalnum() or c in " _-")
        if not safe_name:
            safe_name = f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        filepath = os.path.join(DRAFTS_DIR, f"{safe_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        messagebox.showinfo(t("invoice_editor.draft_saved"),
                            t("invoice_editor.draft_saved_msg").format(name))

    def _load_draft(self):
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        drafts = [f for f in os.listdir(DRAFTS_DIR) if f.endswith(".json")]
        if not drafts:
            messagebox.showinfo(t("invoice_editor.load_draft"),
                                t("invoice_editor.no_drafts"))
            return

        path = filedialog.askopenfilename(
            title=t("invoice_editor.load_draft"),
            initialdir=DRAFTS_DIR,
            filetypes=[("JSON", "*.json")])
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._invoice_number.set(data.get("invoice_number", self._gen_invoice_number()))
            self._issue_date.set(data.get("issue_date", datetime.now().strftime("%Y-%m-%d")))
            self._due_date.set(data.get("due_date", ""))
            self._payment_terms.set(data.get("payment_terms", "Net 30"))
            self._currency.set(data.get("currency", "EUR"))
            self._tax_rate.set(str(data.get("tax_rate", 19)))
            self._discount_type.set(data.get("discount_type", "percentage"))
            self._discount_value.set(str(data.get("discount_value", 0)))

            # Company
            c = data.get("company", {})
            self._company_name.set(c.get("company_name", ""))
            self._company_cui.set(c.get("cui", ""))
            self._company_reg.set(c.get("reg_number", ""))
            self._company_address.set(c.get("address", ""))
            self._company_phone.set(c.get("phone", ""))
            self._company_email.set(c.get("email", ""))

            # Client
            cl = data.get("client", {})
            self._client_name.set(cl.get("name", ""))
            self._client_vat.set(cl.get("vat_number", ""))
            self._client_address.set(cl.get("address", ""))
            self._client_phone.set(cl.get("phone", ""))
            self._client_email.set(cl.get("email", ""))

            # Addon items (and backward compat for old line_items)
            self._addon_items = []
            addons = data.get("addon_items") or []
            if not addons:
                # Load from old line_items format
                for li in data.get("line_items", []):
                    self._addon_items.append(self._create_addon_data(
                        description=li.get("description", ""),
                        amount=li.get("total", li.get("amount", 0)),
                    ))
            else:
                for ai in addons:
                    self._addon_items.append(self._create_addon_data(
                        description=ai.get("description", ""),
                        amount=ai.get("amount", 0),
                    ))
            if not self._addon_items:
                self._add_default_addon_item()
            self._rebuild_addon_rows()

            # Trip base price
            self._trip_base_price.set(data.get("trip_price", "0.00"))
            if data.get("price_pre_vat"):
                self._trip_price_pre_vat.set(str(data["price_pre_vat"]))
            if data.get("vat_percent"):
                self._trip_vat_percent.set(str(data["vat_percent"]))

            # Mode
            mode = data.get("mode", "client")
            if mode == "internal":
                self._is_internal_invoice.set(True)
                self._is_client_invoice.set(False)
            else:
                self._is_client_invoice.set(True)
                self._is_internal_invoice.set(False)

            # Description
            self._desc_text.delete("1.0", "end")
            self._desc_text.insert("1.0", data.get("description", ""))

            # Trip details
            self._truck_plate.set(data.get("truck_plate", ""))
            self._driver_name.set(data.get("driver_name", ""))
            self._distance.set(data.get("distance", ""))

            # Stops (support both new list format and old single-value format)
            load_stops = data.get("loading_stops") or []
            if not load_stops and data.get("loading_city"):
                load_stops = [data["loading_city"]]
            if load_stops:
                self._loading_stops = [{"var": tk.StringVar(value=v)} for v in load_stops]

            unload_stops = data.get("unloading_stops") or []
            if not unload_stops and data.get("unloading_city"):
                unload_stops = [data["unloading_city"]]
            if unload_stops:
                self._unloading_stops = [{"var": tk.StringVar(value=v)} for v in unload_stops]

            if not self._loading_stops:
                self._loading_stops = [{"var": tk.StringVar()}]
            if not self._unloading_stops:
                self._unloading_stops = [{"var": tk.StringVar()}]
            self._rebuild_stops()

            # Notes
            self._notes_entry.delete("1.0", "end")
            self._notes_entry.insert("1.0", data.get("notes", ""))

            # Branding
            self._logo_path.set(data.get("logo_path", ""))
            self._signature_path.set(data.get("signature_path", ""))
            self._stamp_path.set(data.get("stamp_path", ""))
            self._company_color.set(data.get("company_color", COLORS["accent"]))
            self._color_swatch.configure(fg_color=self._company_color.get())
            try:
                self._canvas_title_lbl.configure(text_color=self._company_color.get())
            except Exception:
                pass

            # Try to re-select client/trip if they exist in current lists
            client_name = cl.get("name", "")
            if client_name and client_name in self._client_map:
                self._client_combo.set(client_name)
                self._on_client_selected(client_name)

            self._recalc_all()
            messagebox.showinfo(t("invoice_editor.draft_loaded"),
                                t("invoice_editor.draft_loaded_msg").format(
                                    os.path.basename(path)))
        except Exception as e:
            _logger.error("Failed to load draft: %s", e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))


class CompanyEditorDialog:
    """Minimal modal-like dialog for editing company info."""

    def __init__(self, parent, name, cui, reg, addr, phone, email, on_save):
        self._on_save = on_save

        self._top = ctk.CTkToplevel(parent)
        self._top.title(t("invoice.section_company"))
        self._top.geometry("480x440")
        self._top.resizable(False, False)
        self._top.transient(parent)
        self._top.grab_set()

        self._top.configure(fg_color=COLORS["bg_surface"])

        header = ctk.CTkFrame(self._top, fg_color="transparent")
        header.pack(fill="x", padx=S["6"], pady=(S["6"], S["4"]))
        ctk.CTkLabel(header, text=t("invoice.section_company"),
                     font=FONTS["h2"], text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")

        content = ctk.CTkFrame(self._top, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=S["6"])

        fields = [
            (t("invoice.field_company_name"), "name", name),
            (t("invoice.field_cui"), "cui", cui),
            (t("invoice.field_reg_number"), "reg", reg),
            (t("invoice.field_address"), "addr", addr),
            (t("invoice.field_phone"), "phone", phone),
            (t("invoice.field_email"), "email", email),
        ]

        self._entries = {}
        for label_text, key, default in fields:
            ctk.CTkLabel(content, text=label_text, font=FONTS["small"],
                         text_color=COLORS["text_secondary"],
                         anchor="w").pack(anchor="w", pady=(S["2"], S["1"]))
            entry = ctk.CTkEntry(content, height=34, font=FONTS["body"],
                                 fg_color=COLORS["bg_input"],
                                 border_color=COLORS["border"],
                                 text_color=COLORS["text_primary"])
            entry.insert(0, default)
            entry.pack(fill="x", pady=(0, S["2"]))
            self._entries[key] = entry

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(S["4"], 0))
        ctk.CTkButton(btn_frame, text=t("invoice.save_company"),
                      font=FONTS["body_bold"], height=36,
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff",
                      command=self._save_and_close).pack(side="right", padx=(S["2"], 0))
        ctk.CTkButton(btn_frame, text=t("invoice_editor.cancel"),
                      font=FONTS["body"], height=36,
                      fg_color="transparent",
                      hover_color=COLORS["bg_elevated"],
                      text_color=COLORS["text_secondary"],
                      command=self._top.destroy).pack(side="right")

        self._top.after(100, lambda: self._entries["name"].focus_set())

    def _save_and_close(self):
        data = {
            "company_name": self._entries["name"].get(),
            "cui": self._entries["cui"].get(),
            "reg_number": self._entries["reg"].get(),
            "address": self._entries["addr"].get(),
            "phone": self._entries["phone"].get(),
            "email": self._entries["email"].get(),
        }
        self._on_save(data)
        self._top.destroy()
