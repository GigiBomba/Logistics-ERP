"""Generators workspace — unified Invoice + CMR document generation UI."""
import json
import logging
import os
import threading
from tkinter import messagebox
import customtkinter as ctk

from ui.theme import COLORS, FONTS, S
from services.i18n import t
from services.trip_service import TripService

logger = logging.getLogger(__name__)


class GeneratorsView(ctk.CTkFrame):
    def __init__(self, parent, db, prefs=None, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.db = db
        self.prefs = prefs
        self._frame = self
        self._trip_svc_instance = None
        self._cmr_doc_service = None
        self._trips_list = []
        self._trip_map = {}
        self._cmr_copies = {}
        self._cmr_last_paths = {}
        self._cmr_filled_trip_id = None
        self._invoice_built = False
        self._cmr_built = False
        self._build()

    @property
    def _trip_svc(self):
        if self._trip_svc_instance is None:
            self._trip_svc_instance = TripService(self.db)
        return self._trip_svc_instance

    @property
    def frame(self):
        return self._frame

    def wakeup(self):
        if self._cmr_built:
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
            command=self._on_tab_changed,
        )
        self._tabview.grid(row=0, column=0, sticky="nsew", padx=S["4"], pady=S["4"])

        self._tab_invoice_name = t("generators.tab_invoice")
        self._tab_cmr_name = t("generators.tab_cmr")
        self._tabview.add(self._tab_invoice_name)
        self._tabview.add(self._tab_cmr_name)

        # Build the initial tab immediately so something is visible
        self._build_invoice_tab()

    def _on_tab_changed(self):
        selected = self._tabview.get()
        if selected == self._tab_invoice_name and not self._invoice_built:
            self._build_invoice_tab()
        elif selected == self._tab_cmr_name and not self._cmr_built:
            self._build_cmr_tab()

    def _build_invoice_tab(self):
        if self._invoice_built:
            return
        tab = self._tabview.tab(self._tab_invoice_name)
        from ui.invoice_editor import InvoiceEditor
        self._invoice_tab = InvoiceEditor(tab, self.db, prefs=self.prefs)
        self._invoice_tab.frame.pack(fill="both", expand=True)
        self._invoice_tab.lazy_load()
        self._invoice_built = True

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # CMR Tab â€” Professional logistics-grade CMR generator
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _build_cmr_tab(self):
        if self._cmr_built:
            return
        tab = self._tabview.tab(self._tab_cmr_name)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=0)
        tab.rowconfigure(1, weight=1)

        # ── Row 0: Header — title + trip selector ──
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

        # ── Row 1: WYSIWYG CMR Form (scrollable, main content) ──
        from ui.views.cmr_form_view import CMRFormView
        self._cmr_form = CMRFormView(tab, self.db, prefs=self.prefs)
        self._cmr_form.grid(row=1, column=0, sticky="nsew")

        # ── Controls live inside the scrollable bottom of the CMR form ──
        bottom = self._cmr_form.get_bottom_frame()
        controls = ctk.CTkFrame(bottom, fg_color=COLORS["bg_surface"], corner_radius=8)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)

        # Language row
        lang_row = ctk.CTkFrame(controls, fg_color="transparent")
        lang_row.grid(row=0, column=0, sticky="ew", padx=S["4"], pady=(S["2"], S["1"]))
        ctk.CTkLabel(lang_row, text="CMR Languages:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        lang_codes = self.prefs.get_available_languages() if self.prefs else ["en", "ro"]
        lang_display = []
        for c in lang_codes:
            try:
                dn = self.prefs.get_language_display_name(c) if self.prefs else c
                lang_display.append(f"{dn} ({c})")
            except Exception:
                lang_display.append(c)
        ctk.CTkLabel(lang_row, text="Primary:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(S["4"], 0))
        self._cmr_lang1 = ctk.CTkComboBox(lang_row, values=lang_display, state="readonly",
                                          width=140, font=FONTS["body"],
                                          fg_color=COLORS["bg_input"],
                                          border_color=COLORS["border"],
                                          button_color=COLORS["bg_elevated"],
                                          text_color=COLORS["text_primary"])
        self._cmr_lang1.pack(side="left", padx=(S["1"], S["3"]))
        if lang_display:
            self._cmr_lang1.set(lang_display[0])
        ctk.CTkLabel(lang_row, text="Secondary:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._cmr_lang2 = ctk.CTkComboBox(lang_row, values=lang_display, state="readonly",
                                          width=140, font=FONTS["body"],
                                          fg_color=COLORS["bg_input"],
                                          border_color=COLORS["border"],
                                          button_color=COLORS["bg_elevated"],
                                          text_color=COLORS["text_primary"])
        self._cmr_lang2.pack(side="left", padx=(S["1"], 0))
        if len(lang_display) > 1:
            self._cmr_lang2.set(lang_display[1])

        # Generate buttons row
        btn_row = ctk.CTkFrame(controls, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=S["4"], pady=(S["1"], S["2"]))
        btn_row.columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btn_row, text="\U0001F680 Generate All 4 Copies",
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["body_bold"],
                      height=40, corner_radius=8,
                      command=self._generate_all_copies).grid(
            row=0, column=0, sticky="ew", padx=(0, S["2"]))
        ctk.CTkButton(btn_row, text="\U0001F4C4 Generate Single Copy",
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      font=FONTS["body_bold"], height=40, corner_radius=8,
                      command=self._generate_cmr).grid(
            row=0, column=1, sticky="ew")

        # Status label
        self._cmr_status_lbl = ctk.CTkLabel(controls, text="", font=FONTS["small"],
            text_color=COLORS["text_success"], anchor="w")
        self._cmr_status_lbl.grid(row=2, column=0, sticky="w", padx=S["4"], pady=(0, S["1"]))

        # Copies status section
        self._copies_frame = ctk.CTkFrame(controls, fg_color="transparent")
        self._copies_frame.grid(row=3, column=0, sticky="ew", padx=S["4"], pady=(0, S["4"]))
        self._copy_labels = {}
        colors_map = {"Sender": "#D32F2F", "Consignee": "#1565C0",
                       "Carrier": "#2E7D32", "Administrative": "#212121"}
        bg_map = {"Sender": "#FFEBEE", "Consignee": "#E3F2FD",
                  "Carrier": "#E8F5E9", "Administrative": "#F5F5F5"}
        for suffix, color in colors_map.items():
            row_frame = ctk.CTkFrame(self._copies_frame, fg_color=bg_map.get(suffix, COLORS["bg_surface"]),
                                     corner_radius=6)
            row_frame.pack(fill="x", pady=(0, S["1"]))
            dot = ctk.CTkLabel(row_frame, text="\u25CF", font=("Segoe UI", 10),
                               text_color=color, width=20)
            dot.pack(side="left", padx=(S["2"], 0))
            lbl = ctk.CTkLabel(row_frame, text=f"{suffix} Copy: not generated",
                               font=FONTS["small"], text_color=COLORS["text_secondary"])
            lbl.pack(side="left", fill="x", expand=True)
            open_btn = ctk.CTkButton(row_frame, text="Open", font=FONTS["small"],
                fg_color=COLORS["bg_elevated"],
                hover_color=COLORS["border_hover"],
                text_color=COLORS["text_primary"], height=24, width=50,
                state="disabled", corner_radius=4,
                command=lambda s=suffix: self._open_copy(s))
            open_btn.pack(side="right", padx=S["2"])
            self._copy_labels[suffix] = (lbl, open_btn)

        self._refresh_trip_lists()

    # -- Trip Lists --

    def _refresh_trip_lists(self):
        try:
            trips = self._trip_svc.get_all()
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
        trip = self._trip_svc.get_by_id(trip_id)
        if not trip:
            return
        # Reset fill tracker when user manually changes trip
        if trip.get("id") != self._cmr_filled_trip_id:
            self._cmr_filled_trip_id = None
        self._auto_fill_from_trip(trip)

    def _auto_fill_from_trip(self, trip):
        trip_id = trip.get("id")
        if trip_id is not None and trip_id == self._cmr_filled_trip_id:
            return
        self._cmr_filled_trip_id = trip_id
        from services.invoicing.config_manager import load_company_config
        conf = load_company_config()

        # Gather related data for the form
        client_data = {}
        truck_data = {}
        driver_data = {}
        if trip.get("client_id"):
            try:
                row = self.db.conn.execute(
                    "SELECT * FROM clients WHERE id = ?", (trip["client_id"],)
                ).fetchone()
                if row:
                    client_data = dict(row)
            except Exception:
                pass
        if trip.get("truck_id"):
            try:
                row = self.db.conn.execute(
                    "SELECT * FROM trucks WHERE id = ?", (trip["truck_id"],)
                ).fetchone()
                if row:
                    truck_data = dict(row)
            except Exception:
                pass
        if trip.get("driver_id"):
            try:
                row = self.db.conn.execute(
                    "SELECT * FROM drivers WHERE id = ?", (trip["driver_id"],)
                ).fetchone()
                if row:
                    driver_data = dict(row)
            except Exception:
                pass

        self._cmr_form.fill_from_trip(trip, conf, client_data, truck_data, driver_data)

        # Fill stops from route if available
        if trip.get("route_history_v2_id"):
            self._fill_stops_from_route(trip["route_history_v2_id"])

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
            entries = getattr(self._cmr_form, "_cmr_entries", {})
            if origin and "place_of_loading" in entries:
                self._cmr_form._set_entry(entries["place_of_loading"], origin)
            if destination and "destination" in entries:
                self._cmr_form._set_entry(entries["destination"], destination)
        except Exception as e:
            logger.debug("Could not fill stops from route %d: %s", route_id, e)

    # â”€â”€ CMR Generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _collect_cmr_data(self):
        sel = self._cmr_trip_combo.get()
        if not sel or sel not in self._trip_map:
            return None
        trip_id = self._trip_map[sel]
        trip = self._trip_svc.get_by_id(trip_id)
        if not trip:
            return None
        trip_data = dict(trip)
        trip_data["trip_id"] = trip_id
        form_data = self._cmr_form.collect_data(trip_data)
        return form_data

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

        # Pre-generate CMR number on main thread (DB access must be thread-safe)
        from services.invoicing.cmr_generator import CMRGenerator
        gen = CMRGenerator(db=self.db, prefs=self.prefs)
        cmr_number, cmr_seq = gen._next_cmr_number()
        trip_data["cmr_number"] = cmr_number
        trip_data["cmr_sequence"] = cmr_seq

        def _run():
            registered_paths = {}
            try:
                output_dir = os.path.join("data", "documents", "trips", str(trip_id))
                os.makedirs(output_dir, exist_ok=True)
                copies = gen.generate_all_copies(trip_data, output_dir, skip_db_update=True)
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
                # Update trip status (moved from background thread)
                try:
                    self.db.conn.execute(
                        "UPDATE trips SET cmr_number = ?, cmr_sequence = ?, cmr_status = 'generated' WHERE id = ?",
                        (cmr_number, cmr_seq, trip_id),
                    )
                    self.db.conn.commit()
                except Exception:
                    pass
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
