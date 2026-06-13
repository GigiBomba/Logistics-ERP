"""CMR WYSIWYG form view — UN/CEFACT-aligned, 24-box consignment note editor.

Renders a clean, two-column form organised into sequential section cards that
mirror the standard international road consignment note. Boxes are presented
in order 1 → 24 with prominent badges, bilingual labels, and modern styling.

Supports auto-fill from trip/client selectors with a consignor/consignee role
toggle, ADR dangerous goods, successive carriers, financial split, and
electronic signature pads.
"""

import json
import logging
import tkinter as tk
import customtkinter as ctk

from ui.theme import (
    COLORS, FONTS, S,
    RADIUS_CARD, RADIUS_INPUT, RADIUS_BUTTON, RADIUS_CHIP,
    card, card_header, field, two_col_row, btn, divider,
)

logger = logging.getLogger(__name__)

PAYMENT_OPTIONS = ["", "Sender", "Consignee"]


class CMRFormView(ctk.CTkFrame):
    def __init__(self, parent, db, prefs=None, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.db = db
        self.prefs = prefs
        self._adr_rows = []
        self._successive_carrier_rows = []
        self._financial_rows = []
        self._cmr_entries = {}

        self._role_var = tk.StringVar(value="consignor")
        self._last_trip_data = None

        self._build_ui()
        self.clear()

    # ═══════════════════════════════════════════════════════════════
    # UI Construction
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_base"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_hover"],
        )
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.columnconfigure(0, weight=1)

        self._container = ctk.CTkFrame(
            self._scroll, fg_color="transparent"
        )
        self._container.grid(row=0, column=0, sticky="new",
                             padx=S["10"], pady=(S["10"], S["10"]))
        self._container.columnconfigure(0, weight=1)

        self._build_page_heading()
        self._build_role_selector()
        self._build_parties_card()          # Boxes 1–2
        self._build_route_card()            # Boxes 3–5
        self._build_vehicle_card()          # Vehicle & driver (supporting)
        self._build_cargo_card()            # Boxes 6–12
        self._build_instructions_card()     # Boxes 13–17
        self._build_carrier_card()          # Boxes 18–19
        self._build_charges_card()          # Box 20
        self._build_issue_signatures_card() # Boxes 21–24

        self._bottom_frame = ctk.CTkFrame(self._container, fg_color="transparent")
        self._bottom_frame.grid(row=self._container.grid_size()[1], column=0,
                                sticky="ew", pady=(S["6"], 0))
        self._bottom_frame.columnconfigure(0, weight=1)

        self._apply_validation()

    def _build_page_heading(self):
        f = ctk.CTkFrame(self._container, fg_color="transparent")
        f.grid(row=0, column=0, sticky="ew", pady=(0, S["6"]))
        f.columnconfigure(0, weight=1)

        left = ctk.CTkFrame(f, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            left, text="CMR International Consignment Note",
            font=FONTS["h1"], text_color=COLORS["text_primary"], anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="UN/CEFACT 24-Box Layout — Boxes 1 to 24 in order",
            font=FONTS["small"], text_color=COLORS["text_muted"], anchor="w"
        ).pack(anchor="w", pady=(S["1"], 0))

        # Mini box navigator
        nav = ctk.CTkFrame(f, fg_color="transparent")
        nav.grid(row=0, column=1, sticky="e")
        for i in range(1, 25):
            badge = ctk.CTkFrame(
                nav, fg_color=COLORS["accent_dim"],
                corner_radius=RADIUS_CHIP, width=18, height=18
            )
            badge.pack(side="left", padx=(0, 2))
            badge.pack_propagate(False)
            ctk.CTkLabel(
                badge, text=str(i), font=("Segoe UI", 7),
                text_color=COLORS["accent_text"]
            ).place(relx=0.5, rely=0.5, anchor="center")

    def _build_role_selector(self):
        inner = card(self._container)
        inner._outer.grid(row=1, column=0, sticky="ew", pady=(0, S["6"]))

        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.pack(fill="x", padx=S["5"], pady=S["5"])

        ctk.CTkLabel(
            content, text="SELECT YOUR ROLE",
            font=FONTS["label"], text_color=COLORS["text_muted"], anchor="w"
        ).pack(anchor="w", pady=(0, S["2"]))

        row = ctk.CTkFrame(content, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure((0, 1), weight=1)

        self._role_consignor_btn = ctk.CTkButton(
            row, text="I am the Consignor (Sender)",
            font=FONTS["body_bold"], height=42,
            corner_radius=RADIUS_BUTTON,
            command=lambda: self._set_role("consignor")
        )
        self._role_consignor_btn.grid(row=0, column=0, sticky="ew", padx=(0, S["2"]))

        self._role_consignee_btn = ctk.CTkButton(
            row, text="I am the Consignee (Receiver)",
            font=FONTS["body_bold"], height=42,
            corner_radius=RADIUS_BUTTON,
            command=lambda: self._set_role("consignee")
        )
        self._role_consignee_btn.grid(row=0, column=1, sticky="ew")

        self._update_role_buttons()
        self._role_var.trace_add("write", lambda *a: self._update_role_buttons())

    def _set_role(self, role):
        if self._role_var.get() == role:
            return
        self._role_var.set(role)
        if self._last_trip_data:
            self.fill_from_trip(**self._last_trip_data)

    def _update_role_buttons(self):
        active = self._role_var.get()
        active_style = dict(
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#ffffff", border_width=0
        )
        inactive_style = dict(
            fg_color="transparent", hover_color=COLORS["bg_elevated"],
            text_color=COLORS["text_secondary"], border_width=1,
            border_color=COLORS["border"]
        )
        if active == "consignor":
            self._role_consignor_btn.configure(**active_style)
            self._role_consignee_btn.configure(**inactive_style)
        else:
            self._role_consignor_btn.configure(**inactive_style)
            self._role_consignee_btn.configure(**active_style)

    # ── Shared helpers ───────────────────────────────────────────

    def _section_card(self, title, subtitle):
        """Create a themed card with header and return the content frame."""
        inner = card(self._container)
        inner._outer.grid(row=self._container.grid_size()[1], column=0,
                          sticky="ew", pady=(0, S["6"]))
        card_header(inner, title, subtitle)
        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.pack(fill="x", padx=S["5"], pady=(0, S["5"]))
        return content

    def _two_col_pane(self, parent):
        """Return (left, right) frames with a vertical divider between them."""
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", expand=True)
        wrapper.columnconfigure(0, weight=1, uniform="twocol")
        wrapper.columnconfigure(1, weight=0)   # divider
        wrapper.columnconfigure(2, weight=1, uniform="twocol")

        left = ctk.CTkFrame(wrapper, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, S["4"]))

        vline = ctk.CTkFrame(wrapper, fg_color=COLORS["border"], width=1)
        vline.grid(row=0, column=1, sticky="ns", padx=S["1"])

        right = ctk.CTkFrame(wrapper, fg_color="transparent")
        right.grid(row=0, column=2, sticky="nsew", padx=(S["4"], 0))

        return left, right

    def _box_badge(self, parent, box_num):
        """Create a prominent box-number badge."""
        badge = ctk.CTkFrame(
            parent, fg_color=COLORS["accent_dim"],
            corner_radius=RADIUS_CHIP, width=30, height=20
        )
        badge.pack(side="left", padx=(0, S["2"]))
        badge.pack_propagate(False)
        ctk.CTkLabel(
            badge, text=f"{box_num}", font=("Segoe UI", 10, "bold"),
            text_color=COLORS["accent_text"]
        ).place(relx=0.5, rely=0.5, anchor="center")
        return badge

    def _box_field(self, parent, box_num, label_en, label_ro,
                   kind="entry", **kwargs):
        """Themed field with accent badge + bilingual label.

        Pass box_num=None to omit the numbered badge (for supplementary fields
        that don't belong to a standard CMR box).
        """
        # Map shorthand 'placeholder' → CTkEntry's 'placeholder_text'
        _placeholder = kwargs.pop("placeholder", None)
        if kind == "entry" and _placeholder is not None:
            kwargs["placeholder_text"] = _placeholder

        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, S["4"]))

        lbl_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
        lbl_frame.pack(anchor="w", fill="x", pady=(0, S["1"]))

        if box_num is not None:
            self._box_badge(lbl_frame, box_num)

        ctk.CTkLabel(
            lbl_frame, text=f"{label_en} / {label_ro}",
            font=FONTS["label"], text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")

        base = dict(
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            font=FONTS["body"],
            height=38,
            corner_radius=RADIUS_INPUT,
        )

        if kind == "entry":
            base["placeholder_text_color"] = COLORS["text_muted"]
            w = ctk.CTkEntry(wrapper, **{**base, **kwargs})
        elif kind == "textbox":
            h = kwargs.pop("height", 90)
            base_no_height = {k: v for k, v in base.items() if k != "height"}
            w = ctk.CTkTextbox(wrapper, height=h, **{**base_no_height, **kwargs})
        elif kind == "combobox":
            base.update(dict(
                button_color=COLORS["bg_elevated"],
                button_hover_color=COLORS["border_hover"],
                dropdown_fg_color=COLORS["bg_surface"],
                dropdown_text_color=COLORS["text_primary"],
                dropdown_hover_color=COLORS["bg_elevated"],
            ))
            w = ctk.CTkComboBox(wrapper, **{**base, **kwargs})
        else:
            w = ctk.CTkEntry(wrapper, **{**base, **kwargs})

        w.pack(fill="x")
        return w

    def _compact_box(self, parent, box_num, label, col, max_col=3):
        """Compact grid cell for the goods table."""
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=col, sticky="ew",
                  padx=(0, S["3"]) if col < max_col else (0, 0))
        cell.columnconfigure(0, weight=1)

        lbl_frame = ctk.CTkFrame(cell, fg_color="transparent")
        lbl_frame.pack(anchor="w", fill="x", pady=(0, S["1"]))
        self._box_badge(lbl_frame, box_num)
        ctk.CTkLabel(
            lbl_frame, text=label, font=("Segoe UI", 10),
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")

        e = ctk.CTkEntry(
            cell, height=32,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"],
            corner_radius=RADIUS_INPUT
        )
        e.pack(fill="x")
        return e

    # ── Section: Parties (Boxes 1, 2) ────────────────────────────

    def _build_parties_card(self):
        content = self._section_card(
            "Parties", "Boxes 1 & 2 — Consignor (Sender) and Consignee (Receiver)")
        left, right = self._two_col_pane(content)

        self._cmr_entries["consignor_name"] = self._box_field(
            left, 1, "Sender (Consignor)", "Expeditor",
            kind="textbox", height=90)
        self._cmr_entries["consignee_name"] = self._box_field(
            right, 2, "Consignee", "Destinatar",
            kind="textbox", height=90)

    # ── Section: Route & Documents (Boxes 3, 4, 5) ───────────────

    def _build_route_card(self):
        content = self._section_card(
            "Route & Documents", "Boxes 3, 4 & 5 — Taking over, delivery and attached documents")
        left, right = self._two_col_pane(content)

        self._cmr_entries["place_of_loading"] = self._box_field(
            left, 3, "Place of Taking Over", "Locul Predarii",
            placeholder="Locality, Country")

        self._cmr_entries["destination"] = self._box_field(
            right, 4, "Place of Delivery", "Locul Livrarii",
            placeholder="Locality, Country")

        # Date row for Box 3
        date_row = ctk.CTkFrame(left, fg_color="transparent")
        date_row.pack(fill="x", pady=(0, S["4"]))
        ctk.CTkLabel(
            date_row, text="Date:", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")
        from ui.widgets.date_picker import make_date_entry
        wld = make_date_entry(
            date_row, date_pattern="y-mm-dd",
            placeholder="YYYY-MM-DD", height=32)
        wld.pack(side="left", fill="x", expand=True, padx=(S["2"], 0))
        self._cmr_entries["place_of_loading_date"] = wld

        # ISO country row for Box 3 / 4
        iso_row = ctk.CTkFrame(left, fg_color="transparent")
        iso_row.pack(fill="x", pady=(0, S["4"]))
        ctk.CTkLabel(
            iso_row, text="Loading Country ISO:", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")
        wlc = ctk.CTkEntry(
            iso_row, height=32, width=60,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"],
            corner_radius=RADIUS_INPUT)
        wlc.pack(side="left", padx=(S["2"], 0))
        self._cmr_entries["loading_country"] = wlc

        ctk.CTkLabel(
            iso_row, text="Delivery Country ISO:", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left", padx=(S["4"], 0))
        wdc = ctk.CTkEntry(
            iso_row, height=32, width=60,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"],
            corner_radius=RADIUS_INPUT)
        wdc.pack(side="left", padx=(S["2"], 0))
        self._cmr_entries["delivery_country"] = wdc

        self._cmr_entries["documents_attached"] = self._box_field(
            right, 5, "Documents Attached", "Documente Atasate",
            kind="textbox", height=90)

    # ── Section: Vehicle & Driver (supporting, no box number) ─────

    def _build_vehicle_card(self):
        content = self._section_card(
            "Vehicle & Driver", "Transport means and driver information")
        left, right = self._two_col_pane(content)

        self._cmr_entries["truck_plate"] = field(
            left, "Truck Plate / Numar Camion")
        self._cmr_entries["driver_name"] = field(
            left, "Driver / Sofer")

        self._cmr_entries["trailer_plate"] = field(
            right, "Trailer Plate / Numar Remorca")
        self._cmr_entries["driver_license"] = field(
            right, "License / Permis")

    # ── Section: Goods (Boxes 6–12) ───────────────────────────────

    def _build_cargo_card(self):
        content = self._section_card(
            "Goods Specifications", "Boxes 6 to 12 — Cargo details, weight, volume and HS code")

        # Row 1: Boxes 6–9
        r1 = ctk.CTkFrame(content, fg_color="transparent")
        r1.pack(fill="x", pady=(0, S["3"]))
        r1.columnconfigure((0, 1, 2, 3), weight=1)

        self._cmr_entries["cargo_marks"] = self._compact_box(r1, 6, "Marks & Numbers", 0)
        self._cmr_entries["package_count"] = self._compact_box(r1, 7, "No. of Packages", 1)
        self._cmr_entries["package_type"] = self._compact_box(r1, 8, "Method of Packing", 2)
        self._cmr_entries["cargo_description"] = self._compact_box(r1, 9, "Nature of Goods", 3)

        # Row 2: Boxes 10–12
        r2 = ctk.CTkFrame(content, fg_color="transparent")
        r2.pack(fill="x", pady=(0, S["3"]))
        r2.columnconfigure((0, 1, 2), weight=1)

        self._cmr_entries["hs_code"] = self._compact_box(r2, 10, "HS Code", 0, max_col=2)
        self._cmr_entries["gross_weight_kg"] = self._compact_box(r2, 11, "Gross Weight (kg)", 1, max_col=2)
        self._cmr_entries["volume_m3"] = self._compact_box(r2, 12, "Volume (m\u00b3)", 2, max_col=2)

        # ADR section
        self._build_adr_section(content)

    def _build_adr_section(self, parent):
        adr_frame = ctk.CTkFrame(parent, fg_color="transparent")
        adr_frame.pack(fill="x", pady=(S["3"], 0))

        self._adr_toggle_var = tk.BooleanVar(value=False)
        self._adr_toggle = ctk.CTkCheckBox(
            adr_frame,
            text="Contains DANGEROUS GOODS (ADR)",
            variable=self._adr_toggle_var,
            command=self._on_adr_toggle,
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            fg_color=COLORS["danger"],
            hover_color=COLORS.get("danger_hover", COLORS["danger"]),
            border_color=COLORS["border"],
            checkbox_width=22, checkbox_height=22
        )
        self._adr_toggle.pack(anchor="w")

        self._adr_content_wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        self._adr_content = ctk.CTkFrame(
            self._adr_content_wrapper, fg_color="transparent")
        self._adr_content.pack(fill="x")

        self._adr_add_btn = btn(
            self._adr_content_wrapper, "+ Add ADR Row",
            variant="danger", height=28,
            command=self._add_adr_row)
        self._adr_add_btn.pack(anchor="w", pady=(S["2"], 0))

    def _on_adr_toggle(self):
        if self._adr_toggle_var.get():
            self._adr_content_wrapper.pack(fill="x", pady=(S["2"], 0))
            if not self._adr_rows:
                self._add_adr_row()
            self._adr_toggle.configure(text_color=COLORS["text_danger"])
        else:
            self._adr_content_wrapper.pack_forget()
            for f in self._adr_rows:
                f.destroy()
            self._adr_rows.clear()
            self._adr_toggle.configure(text_color=COLORS["text_primary"])

    def _add_adr_row(self):
        row = ctk.CTkFrame(
            self._adr_content, fg_color=COLORS["bg_elevated"],
            corner_radius=RADIUS_INPUT)
        row.pack(fill="x", pady=(0, S["2"]))
        labels = ["UN No", "Class", "Pack. Grp", "Tunnel", "Qty", "Net Wt(kg)"]
        for i, lbl in enumerate(labels):
            e = ctk.CTkEntry(
                row, width=70, height=28, placeholder_text=lbl,
                fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                text_color=COLORS["text_primary"], font=FONTS["body"],
                corner_radius=RADIUS_INPUT)
            e.pack(side="left", fill="x", expand=True,
                   padx=(0, S["2"]) if i < len(labels) - 1 else 0)
        btn(
            row, "X", variant="danger", width=28, height=28,
            command=lambda f=row: self._remove_adr_row(f)
        ).pack(side="left")
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
            children = [c for c in row.winfo_children()
                        if isinstance(c, ctk.CTkEntry)]
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

    # ── Section: Instructions & Agreements (Boxes 13–17) ─────────

    def _build_instructions_card(self):
        content = self._section_card(
            "Instructions & Agreements",
            "Boxes 13 to 17 — Instructions, reservations, payment, COD and special agreements")
        left, right = self._two_col_pane(content)

        # Box 13: Sender's instructions
        self._cmr_entries["carrier_instructions"] = self._box_field(
            left, 13, "Sender's Instructions", "Instructiuni Expeditor",
            kind="textbox", height=80)

        # Box 14: Carrier's reservations
        self._cmr_entries["carrier_reservations"] = self._box_field(
            right, 14, "Carrier's Reservations", "Rezerve Transportator",
            kind="textbox", height=80)

        # Box 15: Payment instruction
        self._cmr_entries["carriage_payer"] = self._box_field(
            left, 15, "Instruction as to Payment", "Plata Transport",
            kind="combobox", values=PAYMENT_OPTIONS)
        if PAYMENT_OPTIONS:
            self._cmr_entries["carriage_payer"].set(PAYMENT_OPTIONS[0])

        # Box 16: Cash on delivery
        self._cmr_entries["cod_amount"] = self._box_field(
            right, 16, "Cash on Delivery (COD)", "Ramburs",
            placeholder="Amount (EUR)")

        # Box 17: Special agreements
        self._cmr_entries["special_agreements"] = self._box_field(
            right, 17, "Special Agreements", "Acorduri Speciale",
            kind="textbox", height=80)

        # Distance is supporting info, not a numbered box; keep it below the numbered boxes
        self._cmr_entries["distance_km"] = self._box_field(
            content, None, "Distance (km)", "Distanta (km)",
            placeholder="Distance in kilometres")

    # ── Section: Carrier (Boxes 18, 19) ──────────────────────────

    def _build_carrier_card(self):
        content = self._section_card(
            "Carrier", "Boxes 18 & 19 — Carrier and successive carriers")
        left, right = self._two_col_pane(content)

        self._cmr_entries["carrier_name"] = self._box_field(
            left, 18, "Carrier", "Transportator",
            kind="textbox", height=90)

        # Box 19: Successive carriers
        sc_frame = ctk.CTkFrame(right, fg_color="transparent")
        sc_frame.pack(fill="x")

        lbl_frame = ctk.CTkFrame(sc_frame, fg_color="transparent")
        lbl_frame.pack(anchor="w", fill="x", pady=(0, S["1"]))
        self._box_badge(lbl_frame, 19)
        ctk.CTkLabel(
            lbl_frame, text="Successive Carriers / Transportatori Successivi",
            font=FONTS["label"], text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")

        self._succ_container = ctk.CTkFrame(sc_frame, fg_color="transparent")
        self._succ_container.pack(fill="x", pady=(0, S["2"]))

        btn(
            sc_frame, "+ Add Successive Carrier",
            variant="secondary", height=32,
            command=self._add_successive_carrier_row
        ).pack(anchor="w")

    def _add_successive_carrier_row(self):
        row = ctk.CTkFrame(
            self._succ_container, fg_color=COLORS["bg_elevated"],
            corner_radius=RADIUS_INPUT
        )
        row.pack(fill="x", pady=(0, S["2"]))
        for i, lbl in enumerate(
            ["Name", "Address", "Country", "Plate", "Trailer", "Driver", "From", "To"]
        ):
            e = ctk.CTkEntry(
                row, height=28, placeholder_text=lbl,
                fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                text_color=COLORS["text_primary"], font=FONTS["small"],
                corner_radius=RADIUS_INPUT
            )
            e.pack(side="left", fill="x", expand=True,
                   padx=(0, S["2"]) if i < 7 else 0)
        btn(
            row, "X", variant="danger", width=28, height=28,
            command=lambda r=row: self._remove_successive_carrier_row(r)
        ).pack(side="left")
        self._successive_carrier_rows.append(row)

    def _remove_successive_carrier_row(self, frame):
        frame.destroy()
        if frame in self._successive_carrier_rows:
            self._successive_carrier_rows.remove(frame)

    def _get_successive_carriers(self):
        result = []
        for frame in self._successive_carrier_rows:
            entries = [c for c in frame.winfo_children()
                       if isinstance(c, ctk.CTkEntry)]
            if len(entries) >= 6:
                result.append({
                    "carrier_name": entries[0].get().strip(),
                    "carrier_address": entries[1].get().strip(),
                    "carrier_country": entries[2].get().strip(),
                    "vehicle_plate": entries[3].get().strip(),
                    "trailer_plate": entries[4].get().strip(),
                    "driver_name": entries[5].get().strip(),
                    "from_location": entries[6].get().strip()
                    if len(entries) > 6 else "",
                    "to_location": entries[7].get().strip()
                    if len(entries) > 7 else "",
                })
        return result

    # ── Section: Charges (Box 20) ────────────────────────────────

    def _build_charges_card(self):
        content = self._section_card(
            "Box 20 — To Be Paid By",
            "Charges to be paid by the Sender or the Consignee")

        # Table header
        hdr = ctk.CTkFrame(content, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, S["3"]))
        hdr.columnconfigure(0, weight=2)
        hdr.columnconfigure(1, weight=1)
        hdr.columnconfigure(2, weight=1)

        ctk.CTkLabel(
            hdr, text="Cost Type", font=FONTS["label"],
            text_color=COLORS["text_muted"]
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            hdr, text="Sender", font=FONTS["label"],
            text_color=COLORS["text_muted"]
        ).grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            hdr, text="Consignee", font=FONTS["label"],
            text_color=COLORS["text_muted"]
        ).grid(row=0, column=2, sticky="e")

        divider(content)

        cost_rows = [
            ("Carriage charges", "carriage_sender", "carriage_consignee"),
            ("Supplementary charges", "supplementary_sender", "supplementary_consignee"),
            ("Customs duties", "customs_sender", "customs_consignee"),
            ("Other costs", "other_sender", "other_consignee"),
        ]
        self._financial_rows = []
        for label, sk, ck in cost_rows:
            self._build_financial_row(content, label, sk, ck)

    def _build_financial_row(self, parent, label, sender_key, consignee_key):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(S["2"], 0))
        row.columnconfigure(0, weight=2)
        row.columnconfigure(1, weight=1)
        row.columnconfigure(2, weight=1)

        ctk.CTkLabel(
            row, text=label, font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        ).grid(row=0, column=0, sticky="w")

        se = ctk.CTkEntry(
            row, height=32, placeholder_text="EUR",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["small"],
            corner_radius=RADIUS_INPUT)
        se.grid(row=0, column=1, sticky="ew", padx=(0, S["3"]))
        self._cmr_entries[sender_key] = se

        ce = ctk.CTkEntry(
            row, height=32, placeholder_text="EUR",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["small"],
            corner_radius=RADIUS_INPUT)
        ce.grid(row=0, column=2, sticky="ew")
        self._cmr_entries[consignee_key] = ce

        self._financial_rows.append((sender_key, consignee_key))

    def _get_financial_data(self):
        result = {}
        for sk, ck in self._financial_rows:
            s_val = self._cmr_entries.get(sk)
            c_val = self._cmr_entries.get(ck)
            result[sk] = s_val.get().strip() if s_val and s_val.winfo_exists() else ""
            result[ck] = c_val.get().strip() if c_val and c_val.winfo_exists() else ""
        return result

    # ── Section: Issue & Signatures (Boxes 21–24) ─────────────────

    def _build_issue_signatures_card(self):
        content = self._section_card(
            "Issue & Signatures", "Boxes 21 to 24 — Place/date of issue and party signatures")

        # Box 21
        b21 = ctk.CTkFrame(content, fg_color="transparent")
        b21.pack(fill="x", pady=(0, S["4"]))

        lbl_frame = ctk.CTkFrame(b21, fg_color="transparent")
        lbl_frame.pack(anchor="w", fill="x", pady=(0, S["1"]))
        self._box_badge(lbl_frame, 21)
        ctk.CTkLabel(
            lbl_frame, text="Established in / Intocmit in",
            font=FONTS["label"], text_color=COLORS["text_muted"], anchor="w"
        ).pack(side="left")

        row21 = ctk.CTkFrame(b21, fg_color="transparent")
        row21.pack(fill="x")
        row21.columnconfigure((0, 1), weight=1)

        place_frame = ctk.CTkFrame(row21, fg_color="transparent")
        place_frame.grid(row=0, column=0, sticky="ew", padx=(0, S["3"]))
        ctk.CTkLabel(
            place_frame, text="Place:", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(anchor="w")
        self._cmr_entries["issue_place"] = ctk.CTkEntry(
            place_frame, height=32, placeholder_text="City, Country",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"],
            corner_radius=RADIUS_INPUT)
        self._cmr_entries["issue_place"].pack(fill="x")

        date_frame = ctk.CTkFrame(row21, fg_color="transparent")
        date_frame.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(
            date_frame, text="Date:", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="w"
        ).pack(anchor="w")
        from ui.widgets.date_picker import make_date_entry
        w21d = make_date_entry(
            date_frame, date_pattern="y-mm-dd",
            placeholder="YYYY-MM-DD", height=32)
        w21d.pack(fill="x")
        self._cmr_entries["issue_date"] = w21d

        # Signatures 22-24
        sig_frame = ctk.CTkFrame(content, fg_color="transparent")
        sig_frame.pack(fill="x", pady=(S["4"], 0))
        sig_frame.columnconfigure((0, 1, 2), weight=1)

        sig_labels = [
            (22, "Signature of Sender", "sender"),
            (23, "Signature of Carrier", "carrier"),
            (24, "Signature of Consignee", "consignee"),
        ]
        for col_i, (num, label, key) in enumerate(sig_labels):
            col = ctk.CTkFrame(
                sig_frame, fg_color="transparent")
            col.grid(row=0, column=col_i, sticky="nsew",
                     padx=(0, S["3"]) if col_i < 2 else (0, 0))
            col.columnconfigure(0, weight=1)

            lbl_frame = ctk.CTkFrame(col, fg_color="transparent")
            lbl_frame.pack(anchor="w", fill="x", pady=(0, S["1"]))
            self._box_badge(lbl_frame, num)
            ctk.CTkLabel(
                lbl_frame, text=label, font=FONTS["label"],
                text_color=COLORS["text_muted"], anchor="w"
            ).pack(side="left")

            from ui.widgets.signature_pad import SignaturePad
            pad = SignaturePad(col, label="")
            pad.pack(fill="x", pady=(0, S["1"]))
            setattr(self, f"sig_{key}_pad", pad)

    # ═══════════════════════════════════════════════════════════════
    # Validation
    # ═══════════════════════════════════════════════════════════════

    def _apply_validation(self):
        from services.invoicing.cmr_validator import FieldValidator
        self._field_validator = FieldValidator()
        self._error_labels = {}

        vcmd_numeric = self.register(
            lambda field_key, proposed:
            self._field_validator.validate_keystroke(field_key, proposed)
        )

        for widget_key in self._cmr_entries:
            if not self._field_validator.field_has_numeric_rule(widget_key) and \
               not self._field_validator.field_has_blur_rule(widget_key):
                continue

            w = self._cmr_entries.get(widget_key)
            if w is None or not w.winfo_exists():
                continue

            if isinstance(w, ctk.CTkEntry):
                if self._field_validator.field_has_numeric_rule(widget_key):
                    w.configure(
                        validate="key",
                        validatecommand=(vcmd_numeric, widget_key, "%P"),
                    )
                if self._field_validator.field_has_blur_rule(widget_key):
                    w.bind("<FocusOut>",
                           lambda e, key=widget_key, widget=w:
                           self._on_field_blur(key, widget))
                    w.bind("<FocusIn>",
                           lambda e, key=widget_key, widget=w:
                           self._on_field_focus(key, widget))

    def _on_field_blur(self, field_key, widget):
        err = self._field_validator.validate_blur(field_key, widget.get())
        if err:
            widget.configure(border_color=COLORS["danger"])
            self._show_error_label(field_key, widget, err)
        else:
            widget.configure(border_color=COLORS["border"])
            self._hide_error_label(field_key)

    def _on_field_focus(self, field_key, widget):
        widget.configure(border_color=COLORS["border_focus"])
        self._hide_error_label(field_key)

    def _show_error_label(self, field_key, widget, message):
        if field_key in self._error_labels:
            self._error_labels[field_key].configure(text=message)
            return
        lbl = ctk.CTkLabel(
            widget.master, text=message,
            font=("Segoe UI", 9),
            text_color=COLORS["danger"],
            anchor="w")
        pack_info = widget.pack_info()
        if "side" in pack_info:
            pack_order = [c for c in widget.master.pack_slaves()
                          if c is widget]
            if pack_order:
                lbl.pack(after=widget, fill="x", padx=(S["1"], 0))
                self._error_labels[field_key] = lbl
                return
        lbl.pack(fill="x")
        self._error_labels[field_key] = lbl

    def _hide_error_label(self, field_key):
        if field_key in self._error_labels:
            self._error_labels[field_key].destroy()
            del self._error_labels[field_key]

    # ═══════════════════════════════════════════════════════════════
    # Data collection
    # ═══════════════════════════════════════════════════════════════

    def collect_data(self, trip_base=None):
        data = dict(trip_base) if trip_base else {}
        data["generating_role"] = self._role_var.get()

        def _get(key, widget_key, default=""):
            if widget_key in self._cmr_entries:
                w = self._cmr_entries[widget_key]
                if w.winfo_exists():
                    import datetime as _dt
                    if isinstance(w, ctk.CTkTextbox):
                        val = w.get("1.0", "end-1c").strip()
                    elif isinstance(w, ctk.CTkComboBox):
                        val = w.get().strip()
                    elif isinstance(w, _dt.date):
                        val = w.isoformat()
                    elif hasattr(w, "get_date"):
                        v = w.get_date()
                        val = v.isoformat() if isinstance(v, _dt.date) else str(v)
                    else:
                        raw = w.get()
                        if isinstance(raw, _dt.date):
                            val = raw.isoformat()
                        else:
                            val = str(raw).strip()
                    data[key] = val if val else default
                    return
            data.setdefault(key, default)

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

    # ═══════════════════════════════════════════════════════════════
    # Auto-fill
    # ═══════════════════════════════════════════════════════════════

    def fill_from_trip(self, trip, company_conf=None, client_data=None,
                       truck_data=None, driver_data=None):
        self._last_trip_data = dict(
            trip=trip, company_conf=company_conf,
            client_data=client_data, truck_data=truck_data,
            driver_data=driver_data)
        if not trip:
            return

        conf = company_conf or {}
        client = client_data or {}
        truck = truck_data or {}
        driver = driver_data or {}
        role = self._role_var.get()

        if role == "consignor":
            # Company -> Box 1 (Consignor)
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
                "\n".join(line for line in sender_lines if line))

            # Client -> Box 2 (Consignee)
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
                "\n".join(line for line in c_lines if line))
        else:
            # Client -> Box 1 (Consignor)
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
                "\n".join(line for line in sender_lines if line))

            # Company -> Box 2 (Consignee)
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
                "\n".join(line for line in c_lines if line))

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
            "\n".join(line for line in carr_lines if line))

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
            trip.get("destination", trip.get("unloading_address", "")))
        self._set_entry(
            self._cmr_entries.get("delivery_country"),
            trip.get("delivery_country", ""))
        self._set_entry(
            self._cmr_entries.get("place_of_loading"),
            trip.get("place_of_loading",
                     trip.get("loading_address", trip.get("origin", ""))))
        self._set_entry(
            self._cmr_entries.get("place_of_loading_date"),
            trip.get("place_of_loading_date", trip.get("start_date", "")))
        self._set_entry(
            self._cmr_entries.get("loading_country"),
            trip.get("loading_country", ""))
        self._set_entry(
            self._cmr_entries.get("documents_attached"),
            trip.get("documents_attached", ""))

        # Cargo
        self._set_entry(
            self._cmr_entries.get("cargo_marks"),
            trip.get("cargo_marks", ""))
        self._set_entry(
            self._cmr_entries.get("cargo_description"),
            trip.get("cargo_description", ""))
        self._set_entry(
            self._cmr_entries.get("package_count"),
            trip.get("package_count", ""))
        self._set_entry(
            self._cmr_entries.get("package_type"),
            trip.get("package_type", ""))
        self._set_entry(
            self._cmr_entries.get("gross_weight_kg"),
            trip.get("gross_weight_kg", ""))
        self._set_entry(
            self._cmr_entries.get("volume_m3"),
            trip.get("volume_m3", ""))
        self._set_entry(
            self._cmr_entries.get("hs_code"),
            trip.get("hs_code", ""))
        self._set_entry(
            self._cmr_entries.get("carrier_reservations"),
            trip.get("carrier_reservations", ""))
        self._set_entry(
            self._cmr_entries.get("carrier_instructions"),
            trip.get("carrier_instructions", ""))

        # Payment
        payer = trip.get("carriage_payer", "")
        payer_entry = self._cmr_entries.get("carriage_payer")
        if payer_entry and payer_entry.winfo_exists() and payer in ["Sender", "Consignee"]:
            payer_entry.set(payer)

        # Special agreements
        self._set_entry(
            self._cmr_entries.get("special_agreements"),
            trip.get("special_agreements", ""))

        # COD & Issue
        self._set_entry(
            self._cmr_entries.get("cod_amount"),
            trip.get("cod_amount", ""))
        self._set_entry(
            self._cmr_entries.get("distance_km"),
            trip.get("distance_km", ""))
        self._set_entry(
            self._cmr_entries.get("issue_place"),
            trip.get("issue_place", conf.get("address", "")))
        self._set_entry(
            self._cmr_entries.get("issue_date"),
            trip.get("issue_date", ""))

        # Signature paths from config
        sig_path = conf.get("signature_path", "")
        for k in ["sender", "carrier"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None and sig_path:
                pad.set_path(sig_path)

    # ═══════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════

    def get_bottom_frame(self):
        """Return the frame at the bottom of the scrollable container.

        Parent views can pack their controls (generate buttons, language
        selectors, status) here so they scroll with the form instead of
        being pinned outside.
        """
        return self._bottom_frame

    def clear(self):
        for _, widget in self._cmr_entries.items():
            try:
                if not widget.winfo_exists():
                    continue
                if isinstance(widget, ctk.CTkTextbox):
                    widget.delete("1.0", "end")
                elif isinstance(widget, ctk.CTkComboBox):
                    try:
                        widget.set("")
                    except Exception:
                        pass
                elif isinstance(widget, ctk.CTkEntry):
                    widget.delete(0, "end")
            except Exception:
                pass

        for row in self._adr_rows:
            row.destroy()
        self._adr_rows.clear()

        for row in self._successive_carrier_rows:
            row.destroy()
        self._successive_carrier_rows.clear()

        if hasattr(self, "_adr_toggle_var"):
            self._adr_toggle_var.set(False)
            self._on_adr_toggle()

        for k in ["sender", "carrier", "consignee"]:
            pad = getattr(self, f"sig_{k}_pad", None)
            if pad is not None:
                pad._clear()

        self._role_var.set("consignor")
        self._last_trip_data = None

    def _set_entry(self, widget, value):
        if widget is None:
            return
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        if hasattr(widget, "set_date_str") and value:
            try:
                widget.set_date_str(str(value))
                return
            except Exception:
                pass
        if isinstance(widget, ctk.CTkComboBox):
            try:
                widget.set(str(value) if value else "")
            except Exception:
                pass
            return
        try:
            widget.delete("1.0", "end")
            if value:
                widget.insert("1.0", str(value))
        except Exception:
            try:
                widget.delete(0, "end")
                if value:
                    widget.insert(0, str(value))
            except Exception:
                pass
