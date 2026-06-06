"""Generators workspace — unified Invoice + CMR document generation UI."""
import logging
import os
import tkinter as tk
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
        self._trip_service = TripService(db)
        self._cmr_doc_service = None
        self._trips_list = []
        self._trip_map = {}
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

    # ── Invoice Tab ─────────────────────────────────────────────────

    def _build_invoice_tab(self):
        tab = self._tabview.tab(t("generators.tab_invoice"))
        from ui.invoice_editor import InvoiceEditor
        self._invoice_tab = InvoiceEditor(tab, self.db, prefs=self.prefs)
        self._invoice_tab.frame.pack(fill="both", expand=True)

    # ── CMR Tab ─────────────────────────────────────────────────────

    def _build_cmr_tab(self):
        tab = self._tabview.tab(t("generators.tab_cmr"))
        tab.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(tab, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(S["4"], S["3"]))
        ctk.CTkLabel(hdr, text=f"\U0001F4C4 {t('generators.cmr_title')}",
                     font=FONTS["h2"], text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(hdr, text=t("generators.cmr_subtitle"),
                     font=FONTS["small"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w")

        trip_f = ctk.CTkFrame(tab, fg_color=COLORS["bg_surface"],
                              corner_radius=8)
        trip_f.grid(row=1, column=0, sticky="ew", pady=(0, S["3"]))
        trip_f.columnconfigure(0, weight=1)

        ctk.CTkLabel(trip_f, text=t("generators.cmr_trip_select"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", padx=S["4"], pady=(S["4"], 0))

        trip_sel = ctk.CTkFrame(trip_f, fg_color="transparent")
        trip_sel.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))

        self._cmr_trip_combo = ctk.CTkComboBox(
            trip_sel, values=[], state="readonly",
            font=FONTS["body"],
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            command=self._on_cmr_trip_selected,
        )
        self._cmr_trip_combo.pack(side="left", fill="x", expand=True, padx=(0, S["2"]))
        ctk.CTkButton(trip_sel, text="\U0001F504", width=36, height=36,
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      font=FONTS["body"],
                      command=self._refresh_trip_lists).pack(side="right")

        opts_f = ctk.CTkFrame(tab, fg_color=COLORS["bg_surface"],
                              corner_radius=8)
        opts_f.grid(row=2, column=0, sticky="ew", pady=(0, S["3"]))

        ctk.CTkLabel(opts_f, text=t("generators.cmr_options"),
                     font=FONTS["label"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", padx=S["4"], pady=(S["4"], 0))

        fields_frame = ctk.CTkFrame(opts_f, fg_color="transparent")
        fields_frame.pack(fill="x", padx=S["4"], pady=(S["1"], S["4"]))

        for label_key, var_name in [
            ("generators.cmr_loading", "cmr_loading"),
            ("generators.cmr_unloading", "cmr_unloading"),
            ("generators.cmr_driver", "cmr_driver"),
        ]:
            row_f = ctk.CTkFrame(fields_frame, fg_color="transparent")
            row_f.pack(fill="x", pady=(0, S["2"]))
            ctk.CTkLabel(row_f, text=t(label_key), font=FONTS["body"],
                         text_color=COLORS["text_secondary"],
                         anchor="w", width=140).pack(side="left")
            entry = ctk.CTkEntry(
                row_f,
                placeholder_text=t(label_key),
                fg_color=COLORS["bg_input"],
                border_color=COLORS["border"],
                text_color=COLORS["text_primary"],
                font=FONTS["body"],
                height=34,
            )
            entry.pack(side="left", fill="x", expand=True)
            setattr(self, f"_{var_name}_entry", entry)

        btn_f = ctk.CTkFrame(tab, fg_color="transparent")
        btn_f.grid(row=3, column=0, sticky="ew")
        btn_f.columnconfigure(0, weight=1)

        ctk.CTkButton(btn_f, text=f"\U0001F680 {t('generators.cmr_generate')}",
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      text_color="#ffffff", font=FONTS["body_bold"],
                      height=40,
                      command=self._generate_cmr).grid(
            row=0, column=0, sticky="ew", padx=(0, S["2"]))

        self._cmr_open_btn = ctk.CTkButton(
            btn_f, text=f"\U0001F4C2 {t('generators.cmr_open')}",
            fg_color=COLORS["info"],
            hover_color=COLORS["info_dim"],
            text_color="#ffffff", font=FONTS["body_bold"],
            height=40, state="disabled",
            command=self._open_generated_cmr)
        self._cmr_open_btn.grid(row=0, column=1, sticky="ew")

        self._cmr_result_lbl = ctk.CTkLabel(
            tab, text="", font=FONTS["small"],
            text_color=COLORS["text_success"], anchor="w")
        self._cmr_result_lbl.grid(row=4, column=0, sticky="ew",
                                  pady=(S["3"], 0))

        self._cmr_last_path = None

        self._refresh_trip_lists()

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

        driver_entry = getattr(self, "_cmr_driver_entry", None)
        if driver_entry and driver_entry.winfo_exists():
            driver_entry.delete(0, "end")
            driver = trip.get("driver_name", "")
            if driver:
                driver_entry.insert(0, driver)

        route_id = trip.get("route_history_v2_id")
        if route_id:
            self._fill_stops_from_route(route_id)

    def _fill_stops_from_route(self, route_id: int) -> None:
        import json
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

            loading_entry = getattr(self, "_cmr_loading_entry", None)
            if loading_entry and loading_entry.winfo_exists():
                loading_entry.delete(0, "end")
                if origin:
                    loading_entry.insert(0, origin)

            unloading_entry = getattr(self, "_cmr_unloading_entry", None)
            if unloading_entry and unloading_entry.winfo_exists():
                unloading_entry.delete(0, "end")
                if destination:
                    unloading_entry.insert(0, destination)
        except Exception as e:
            logger.debug("Could not fill stops from route %d: %s", route_id, e)

    # ── CMR Generation ─────────────────────────────────────────────

    def _generate_cmr(self):
        sel = self._cmr_trip_combo.get()
        if not sel or sel not in self._trip_map:
            messagebox.showwarning(t("generators.cmr_generate"),
                                   t("generators.cmr_select_trip"))
            return

        trip_id = self._trip_map[sel]
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if not trip:
                raise ValueError(f"Trip {trip_id} not found")
        except Exception as e:
            messagebox.showerror(t("generators.cmr_generate"), str(e))
            return

        loading = getattr(self, "_cmr_loading_entry", None)
        unloading = getattr(self, "_cmr_unloading_entry", None)
        driver = getattr(self, "_cmr_driver_entry", None)

        trip_data = dict(trip)
        trip_data["trip_id"] = trip_id
        trip_data["truck_plate"] = trip.get("truck_number", "")
        if loading and loading.get().strip():
            trip_data["loading_address"] = loading.get().strip()
            trip_data["origin"] = loading.get().strip()
        if unloading and unloading.get().strip():
            trip_data["unloading_address"] = unloading.get().strip()
            trip_data["destination"] = unloading.get().strip()
        if driver and driver.get().strip():
            trip_data["driver_name"] = driver.get().strip()

        try:
            from services.invoicing.cmr_generator import CMRGenerator
            gen = CMRGenerator()
            import os as _os
            output_dir = _os.path.join("data", "documents", "trips", str(trip_id))
            _os.makedirs(output_dir, exist_ok=True)
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

        self._cmr_last_path = filepath
        self._cmr_result_lbl.configure(
            text=t("generators.cmr_generated").format(path=os.path.basename(filepath)))
        self._cmr_open_btn.configure(state="normal")
        logger.info("CMR generated for trip %d: %s", trip_id, filepath)

    def _open_generated_cmr(self):
        if self._cmr_last_path and os.path.isfile(self._cmr_last_path):
            os.startfile(os.path.abspath(self._cmr_last_path))
