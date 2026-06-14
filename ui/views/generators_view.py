"""Generators workspace — unified Invoice + CMR document generation UI.

The view is organised around a single, persistent trip selector at the top.
Below it the user picks the document type (Invoice or CMR waybill) via small
segmented-tab buttons. The active editor fills the content area. For CMR a
control bar with language, generate actions and copy status sits at the bottom.
"""

import json
import logging
import os
import threading
from tkinter import messagebox

import customtkinter as ctk

from ui.theme import COLORS, FONTS, S, RADIUS_CARD, btn
from services.i18n import t
from services.trip_service import TripService

logger = logging.getLogger(__name__)

_COPY_META = {
    "Sender":        {"color": COLORS["text_danger"],  "bg": COLORS["danger_dim"],  "icon": "\U0001F4E4"},
    "Consignee":     {"color": COLORS["info"],         "bg": COLORS["info_dim"],     "icon": "\U0001F4E5"},
    "Carrier":       {"color": COLORS["text_success"], "bg": COLORS["success_dim"],  "icon": "\U0001F69B"},
    "Administrative":{"color": COLORS["text_secondary"],"bg": COLORS["bg_elevated"], "icon": "\U0001F4C1"},
}


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
        self._cmr_last_paths = {}
        self._cmr_filled_trip_id = None

        self._invoice_editor = None
        self._cmr_form = None
        self._cmr_content_frame = None
        self._copy_labels = {}
        self._cmr_status_lbl = None
        self._cmr_lang1 = None
        self._cmr_lang2 = None

        self._current_doc = None
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
        self._refresh_trip_lists()
        if self._invoice_editor is not None and hasattr(self._invoice_editor, "lazy_load"):
            try:
                self._invoice_editor.lazy_load()
            except Exception as e:
                logger.warning("Could not refresh invoice editor: %s", e)

    def _lazy_cmr_doc_service(self):
        if self._cmr_doc_service is None:
            from services.document_service import DocumentService
            self._cmr_doc_service = DocumentService(self.db)
        return self._cmr_doc_service

    # ═══════════════════════════════════════════════════════════════════
    # Main layout
    # ═══════════════════════════════════════════════════════════════════

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build_header()
        self._build_document_tabs()

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=2, column=0, sticky="nsew",
                           padx=S["8"], pady=(S["4"], S["8"]))
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

        self._switch_document("invoice")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew",
                    padx=S["8"], pady=(S["8"], S["4"]))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_block, text=t("generators.title"),
            font=FONTS["h1"], text_color=COLORS["text_primary"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_block, text=t("generators.subtitle"),
            font=FONTS["small"], text_color=COLORS["text_muted"], anchor="w",
        ).pack(anchor="w", pady=(S["1"], 0))

        trip_block = ctk.CTkFrame(header, fg_color="transparent")
        trip_block.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            trip_block, text=t("generators.trip_label"),
            font=FONTS["small"], text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(0, S["2"]))
        self._trip_combo = ctk.CTkComboBox(
            trip_block, values=[], state="readonly", width=340,
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_surface"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["bg_elevated"],
            command=self._on_global_trip_selected,
        )
        self._trip_combo.pack(side="left", padx=(0, S["2"]))
        btn(trip_block, text="\u21BB", variant="secondary", width=36, height=36,
            font=FONTS["body_bold"], command=self._refresh_trip_lists,
        ).pack(side="left")

    # ── Document tabs ──────────────────────────────────────────────

    def _build_document_tabs(self):
        tab_bar = ctk.CTkFrame(self, fg_color="transparent")
        tab_bar.grid(row=1, column=0, sticky="w",
                     padx=S["8"], pady=(0, S["3"]))

        self._tab_btns = {}
        for col, (key, icon, label_key) in enumerate([
            ("invoice", "\U0001F5B9", "generators.doc_invoice_title"),
            ("cmr", "\U0001F4C4", "generators.doc_cmr_title"),
        ]):
            b = ctk.CTkButton(
                tab_bar,
                text=f" {icon}  {t(label_key)} ",
                font=FONTS["body"],
                height=32,
                corner_radius=RADIUS_CARD,
                cursor="hand2",
                command=lambda k=key: self._switch_document(k),
            )
            b.grid(row=0, column=col, sticky="w",
                   padx=(0, S["2"] if col == 0 else 0))
            self._tab_btns[key] = b

    def _switch_document(self, doc_type: str):
        if self._current_doc == doc_type:
            return
        self._current_doc = doc_type

        for widget in self._content.winfo_children():
            widget.destroy()
        self._invoice_editor = None
        self._cmr_form = None
        self._cmr_content_frame = None

        if doc_type == "invoice":
            self._build_invoice_content()
        else:
            self._build_cmr_content()

        self._update_tab_state()

    def _update_tab_state(self):
        for key, btn_widget in self._tab_btns.items():
            active = key == self._current_doc
            btn_widget.configure(
                fg_color=COLORS["accent"] if active else COLORS["bg_elevated"],
                text_color="#ffffff" if active else COLORS["text_secondary"],
                hover_color=COLORS["accent_hover"] if active else COLORS["border_hover"],
            )

    # ═══════════════════════════════════════════════════════════════════
    # Invoice content
    # ═══════════════════════════════════════════════════════════════════

    def _build_invoice_content(self):
        from ui.invoice_editor import InvoiceEditor
        self._invoice_editor = InvoiceEditor(self._content, self.db, prefs=self.prefs)
        self._invoice_editor.frame.pack(fill="both", expand=True)
        self._invoice_editor.lazy_load()
        self._invoice_built = True

    # ═══════════════════════════════════════════════════════════════════
    # CMR content — controls scroll with the form at the bottom
    # ═══════════════════════════════════════════════════════════════════

    def _build_cmr_content(self):
        self._cmr_content_frame = ctk.CTkFrame(
            self._content, fg_color="transparent")
        self._cmr_content_frame.pack(fill="both", expand=True)

        from ui.views.cmr_form_view import CMRFormView
        self._cmr_form = CMRFormView(
            self._cmr_content_frame, self.db, prefs=self.prefs)
        self._cmr_form.pack(fill="both", expand=True)

        bottom = self._build_cmr_bottom_bar(self._cmr_form.get_bottom_frame())
        bottom.pack(fill="x")

        self._cmr_built = True

        current = self._trip_combo.get()
        if current and current in self._trip_map:
            self._on_global_trip_selected(current)

    def _build_cmr_bottom_bar(self, parent):
        bar = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"],
                           corner_radius=RADIUS_CARD)
        bar.columnconfigure((0, 1, 2), weight=1)

        # ── Languages ──
        lang_col = ctk.CTkFrame(bar, fg_color="transparent")
        lang_col.grid(row=0, column=0, sticky="nsew",
                      padx=(S["5"], S["4"]), pady=S["4"])
        ctk.CTkLabel(lang_col, text=t("generators.cmr_options_title").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["2"]))

        lang_codes = self.prefs.get_available_languages() if self.prefs else ["en", "ro"]
        lang_display = []
        for c in lang_codes:
            try:
                dn = self.prefs.get_language_display_name(c) if self.prefs else c
                lang_display.append(f"{dn} ({c})")
            except Exception:
                lang_display.append(c)

        self._cmr_lang1 = self._lang_field(
            lang_col, t("generators.cmr_primary_language"), lang_display, 0)
        self._cmr_lang2 = self._lang_field(
            lang_col, t("generators.cmr_secondary_language"), lang_display,
            1 if len(lang_display) > 1 else 0)

        # ── Actions ──
        actions_col = ctk.CTkFrame(bar, fg_color="transparent")
        actions_col.grid(row=0, column=1, sticky="nsew",
                         padx=S["4"], pady=S["4"])
        ctk.CTkLabel(actions_col, text=t("generators.cmr_actions_title").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["2"]))

        btn(actions_col,
            text=f"\U0001F4E4  {t('generators.cmr_generate_single')}",
            variant="secondary", height=38,
            command=self._generate_cmr,
        ).pack(fill="x", pady=(0, S["2"]))
        btn(actions_col,
            text=f"\U0001F680  {t('generators.cmr_generate_all')}",
            variant="primary", height=42,
            command=self._generate_all_copies,
        ).pack(fill="x")

        # ── Copies status ──
        copies_col = ctk.CTkFrame(bar, fg_color="transparent")
        copies_col.grid(row=0, column=2, sticky="nsew",
                        padx=(S["4"], S["5"]), pady=S["4"])
        ctk.CTkLabel(copies_col, text=t("generators.cmr_copies_title").upper(),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(0, S["2"]))

        self._cmr_status_lbl = ctk.CTkLabel(
            copies_col, text=t("generators.cmr_status_ready"),
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
        )
        self._cmr_status_lbl.pack(fill="x", pady=(0, S["2"]))

        copies_grid = ctk.CTkFrame(copies_col, fg_color="transparent")
        copies_grid.pack(fill="x")
        self._copy_labels = {}

        for suffix in ["Sender", "Consignee", "Carrier", "Administrative"]:
            meta = self._copy_meta(suffix)
            row = ctk.CTkFrame(copies_grid, fg_color=meta["bg"],
                               corner_radius=RADIUS_CARD)
            row.pack(fill="x", pady=(0, S["1"]))
            row.columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row, text=meta["icon"], font=("Segoe UI", 12),
                text_color=meta["color"], width=22,
            ).pack(side="left", padx=(S["2"], 0))

            lbl = ctk.CTkLabel(
                row, text=f"{suffix}: {t('generators.cmr_not_generated')}",
                font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True, padx=(S["2"], 0))

            open_btn = btn(
                row, text=t("generators.open_pdf"), variant="ghost",
                height=22, width=46, font=FONTS["small"],
                state="disabled",
                command=lambda s=suffix: self._open_copy(s),
            )
            open_btn.pack(side="right", padx=S["2"])
            self._copy_labels[suffix] = (lbl, open_btn)

        return bar

    def _lang_field(self, parent, label, values, default_index):
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, S["2"]))
        ctk.CTkLabel(wrapper, text=label, font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w",
        ).pack(anchor="w", pady=(0, S["1"]))
        combo = ctk.CTkComboBox(
            wrapper, values=values, state="readonly",
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["border_hover"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_surface"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["bg_elevated"],
        )
        combo.pack(fill="x")
        if values:
            combo.set(values[default_index])
        return combo

    @staticmethod
    def _copy_meta(suffix: str):
        return _COPY_META.get(suffix, {"color": COLORS["text_secondary"],
                                       "bg": COLORS["bg_surface"],
                                       "icon": "\U0001F4C4"})

    # ═══════════════════════════════════════════════════════════════════
    # Trip handling
    # ═══════════════════════════════════════════════════════════════════

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

            current = self._trip_combo.get() if self._trip_combo.winfo_exists() else ""
            self._trip_combo.configure(values=labels)

            if labels:
                if current not in labels:
                    self._trip_combo.set(labels[0])
                    self._on_global_trip_selected(labels[0])
            else:
                self._trip_combo.set("")

            if self._invoice_editor is not None and hasattr(self._invoice_editor, "_load_trips"):
                try:
                    self._invoice_editor._load_trips()
                except Exception as e:
                    logger.warning("Could not refresh invoice editor trips: %s", e)

        except Exception as e:
            logger.warning("Could not refresh trip lists: %s", e)

    def _on_global_trip_selected(self, choice: str):
        if not choice or choice not in self._trip_map:
            return
        trip_id = self._trip_map[choice]
        trip = self._trip_svc.get_by_id(trip_id)
        if not trip:
            return
        if self._cmr_built and self._cmr_form is not None:
            if trip.get("id") != self._cmr_filled_trip_id:
                self._cmr_filled_trip_id = None
            self._auto_fill_cmr(trip)

    def _auto_fill_cmr(self, trip):
        if self._cmr_form is None:
            return
        trip_id = trip.get("id")
        if trip_id is not None and trip_id == self._cmr_filled_trip_id:
            return
        self._cmr_filled_trip_id = trip_id

        from services.invoicing.config_manager import load_company_config
        conf = load_company_config()

        client_data, truck_data, driver_data = {}, {}, {}
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

        if trip.get("route_history_v2_id"):
            self._fill_stops_from_route(trip["route_history_v2_id"])

    def _fill_stops_from_route(self, route_id: int) -> None:
        if self._cmr_form is None:
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
            entries = getattr(self._cmr_form, "_cmr_entries", {})
            if origin and "place_of_loading" in entries:
                self._cmr_form._set_entry(entries["place_of_loading"], origin)
            if destination and "destination" in entries:
                self._cmr_form._set_entry(entries["destination"], destination)
        except Exception as e:
            logger.debug("Could not fill stops from route %d: %s", route_id, e)

    # ═══════════════════════════════════════════════════════════════════
    # CMR generation
    # ═══════════════════════════════════════════════════════════════════

    def _collect_cmr_data(self):
        if self._cmr_form is None:
            return None
        sel = self._trip_combo.get()
        if not sel or sel not in self._trip_map:
            return None
        trip_id = self._trip_map[sel]
        trip = self._trip_svc.get_by_id(trip_id)
        if not trip:
            return None
        trip_data = dict(trip)
        trip_data["trip_id"] = trip_id
        form_data = self._cmr_form.collect_data(trip_data)

        def _extract_lang(combo):
            if combo is None:
                return None
            val = combo.get()
            if not val:
                return None
            parts = val.split("(")
            if len(parts) > 1:
                return parts[-1].rstrip(")").strip()
            return val.strip()

        lang1 = _extract_lang(self._cmr_lang1)
        lang2 = _extract_lang(self._cmr_lang2)
        if lang1:
            form_data["cmr_language"] = lang1
        if lang2:
            form_data["cmr_language_secondary"] = lang2

        return form_data

    def _generate_cmr(self):
        if self._cmr_form is None or self._cmr_status_lbl is None:
            return
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
                filepath, title=f"CMR Trip #{trip_id}", category="trips",
                entity_type="trip", entity_id=trip_id,
                tags=["cmr", "generated"],
            )
        except Exception:
            logger.warning("CMR registration in Document Center skipped", exc_info=True)

        self._cmr_last_paths["Sender"] = filepath
        self._cmr_status_lbl.configure(
            text=t("generators.cmr_generated").format(path=os.path.basename(filepath)),
            text_color=COLORS["text_success"],
        )
        self._update_copy_status("Sender", filepath)
        logger.info("CMR generated for trip %d: %s", trip_id, filepath)

    def _generate_all_copies(self):
        if self._cmr_form is None or self._cmr_status_lbl is None:
            return
        trip_data = self._collect_cmr_data()
        if trip_data is None:
            messagebox.showwarning(t("generators.cmr_generate"),
                                   t("generators.cmr_select_trip"))
            return
        trip_id = trip_data["trip_id"]

        self._cmr_status_lbl.configure(
            text=t("generators.cmr_status_generating"),
            text_color=COLORS["text_warning"],
        )
        self._cmr_status_lbl.update_idletasks()

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
                    if self._cmr_status_lbl is not None and self._cmr_status_lbl.winfo_exists():
                        self._cmr_status_lbl.configure(
                            text=t("generators.cmr_error").format(error=str(e)),
                            text_color=COLORS["danger"],
                        )
                self.after(0, _err)
                logger.error("CMR generation failed: %s", e)
                return

            def _register():
                if self._cmr_status_lbl is None:
                    return
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
                                category="trips", entity_type="trip",
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
                        text=t("generators.cmr_all_generated").format(path=base),
                        text_color=COLORS["text_success"],
                    )
                    for suffix, path in registered_paths.items():
                        self._update_copy_status(suffix, path)

            self.after(0, _register)

        threading.Thread(target=_run, daemon=True, name=f"cmr-gen-{trip_id}").start()

    def _update_copy_status(self, suffix, path):
        if suffix in self._copy_labels:
            lbl, btn = self._copy_labels[suffix]
            lbl.configure(text=f"{suffix}: {os.path.basename(path)}")
            btn.configure(state="normal")
            btn.configure(command=lambda p=path: self._open_path(p))

    def _open_copy(self, suffix):
        if suffix in self._cmr_last_paths:
            path = self._cmr_last_paths[suffix]
            self._open_path(path)

    def _open_path(self, path: str):
        if path and os.path.isfile(path):
            try:
                os.startfile(os.path.abspath(path))
            except Exception as e:
                logger.warning("Could not open %s: %s", path, e)
