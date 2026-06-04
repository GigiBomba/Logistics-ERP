import logging
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timedelta
import os
from services.i18n import t
from services.app_state import AppState
from services.invoicing.config_manager import load_company_config, save_company_config
from services.invoicing.service import InvoiceService
from services.trip_service import TripService
from ui.styles import Theme
from ui.theme import FONTS
from ui.widgets import StyledEntry, ActionButton, StyledRadioButton
from services.operations.event_bus import EventBus, SETTINGS_UPDATED

_logger = logging.getLogger(__name__)

from ui.i18n_mixin import I18nMixin

class InvoiceTab(I18nMixin):
    def __init__(self, parent, db, prefs=None):
        I18nMixin.__init__(self)
        self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
        self.db = db
        self.trip_service = TripService(db)
        self.invoice_service = InvoiceService(db, prefs=self.prefs)
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self._radio_buttons = []
        self._app_state = AppState()
        self._event_bus = EventBus()
        self._event_bus.subscribe(SETTINGS_UPDATED, self._on_settings_updated)
        
        self._setup_ui()
        
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
                self.frame.after(0, self._reload_company_fields)
            except Exception:
                pass

    def _reload_company_fields(self):
        conf = load_company_config()
        for key, entry in self.inputs.items():
            try:
                entry.delete(0, "end")
                entry.insert(0, conf.get(key, ""))
            except Exception:
                pass

    def refresh_translations(self):
        for rb in self._radio_buttons:
            try:
                rb.refresh_translations()
            except Exception:
                pass

    def _setup_ui(self):
        config_f = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        config_f.pack(fill="x", padx=30, pady=20)

        config_header = ctk.CTkLabel(config_f, text=f" 🏢 {t('invoice.section_company')}", 
                                      text_color=Theme.ACCENT, font=Theme.FONT_BOLD)
        config_header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(5,10))
        self.i18n_tag(config_header, "invoice.section_company", " 🏢 ")

        conf = load_company_config()
        self.inputs = {}
        
        fields = [
            ("company_name", t("invoice.field_company_name")),
            ("cui", t("invoice.field_cui")),
            ("reg_number", t("invoice.field_reg_number")),
            ("address", t("invoice.field_address")),
            ("phone", t("invoice.field_phone")),
            ("email", t("invoice.field_email"))
        ]

        for i, (key, label) in enumerate(fields):
            row, col = divmod(i, 2)
            lbl = ctk.CTkLabel(config_f, text=label, fg_color=Theme.BG, text_color=Theme.TEXT, font=FONTS["label"])
            lbl.grid(row=row*2+1, column=col, sticky="w", pady=(8,0), padx=5)
            self.i18n_tag(lbl, f"invoice.field_{key}")
            
            entry = StyledEntry(config_f)
            entry.insert(0, conf.get(key, ""))
            entry.grid(row=row*2+2, column=col, sticky="ew", padx=5, pady=(0,5))
            self.inputs[key] = entry
        
        config_f.columnconfigure((0,1), weight=1)
        
        btn = ActionButton(config_f, f"💾 {t('invoice.save_company')}", self._save_settings, 
                     color=Theme.ACCENT_SUCCESS)
        btn.grid(row=7, column=0, columnspan=2, pady=15)
        self.i18n_tag(btn, "invoice.save_company", "💾 ")

        gen_f = ctk.CTkFrame(self.frame, fg_color=Theme.BG)
        gen_f.pack(fill="both", expand=True, padx=30, pady=(0,30))

        gen_header = ctk.CTkLabel(gen_f, text=f" 🧾 {t('invoice.section_generator')}", 
                                   text_color=Theme.ACCENT, font=Theme.FONT_BOLD)
        gen_header.pack(anchor="w", pady=(5,10))
        self.i18n_tag(gen_header, "invoice.section_generator", " 🧾 ")

        lbl = ctk.CTkLabel(gen_f, text=f"1. {t('invoice.select_trip')}", fg_color=Theme.BG, text_color=Theme.TEXT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w")
        self.i18n_tag(lbl, "invoice.select_trip", "1. ")
        
        trip_sel_f = ctk.CTkFrame(gen_f, fg_color=Theme.BG)
        trip_sel_f.pack(fill="x", pady=10)
        
        self.c_trips = ctk.CTkComboBox(trip_sel_f, values=[], state="readonly", font=FONTS["label"])
        self.c_trips.pack(side="left", fill="x", expand=True, padx=(0,10))
        
        ActionButton(trip_sel_f, "🔄", self._refresh_trip_list, color=Theme.SURFACE2, width=3).pack(side="right")
        
        lbl = ctk.CTkLabel(gen_f, text=f"2. {t('invoice.doc_type_label')}", fg_color=Theme.BG, text_color=Theme.TEXT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w", pady=(15, 5))
        self.i18n_tag(lbl, "invoice.doc_type_label", "2. ")
        
        self.invoice_mode = tk.StringVar(value="client")
        
        radio_f = ctk.CTkFrame(gen_f, fg_color=Theme.BG)
        radio_f.pack(fill="x", pady=5)
        
        rb1 = StyledRadioButton(
            radio_f,
            text=t("invoice.radio_client_invoice"),
            variable=self.invoice_mode,
            value="client"
        )
        rb1.pack(side="left", padx=10)
        self._radio_buttons.append(rb1)
        
        rb2 = StyledRadioButton(
            radio_f,
            text=t("invoice.radio_internal_invoice"),
            variable=self.invoice_mode,
            value="internal"
        )
        rb2.pack(side="left", padx=10)
        self._radio_buttons.append(rb2)

        btn_frame = ctk.CTkFrame(gen_f, fg_color=Theme.BG)
        btn_frame.pack(fill="x", side="bottom", pady=10)
        btn = ActionButton(btn_frame, f"\U0001f680 {t('invoice.generate_button')}", self._generate,
                     color=Theme.ACCENT)
        btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.i18n_tag(btn, "invoice.generate_button", "\U0001f680 ")
        btn = ActionButton(btn_frame, f"\U0001f4e7 {t('invoice.button_email')}", self._email_invoice,
                     color=Theme.ACCENT_SUCCESS)
        btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.i18n_tag(btn, "invoice.button_email", "\U0001f4e7 ")

        self._refresh_trip_list()

    def _refresh_trip_list(self):
        try:
            trips = self.trip_service.get_all()
            self.trip_map = {
                t("invoice.trip_list_format").format(id=trip['id'], truck_number=trip['truck_number'], client_name=trip['client_name'], created_at=trip['created_at'][:10]): trip['id'] 
                for trip in trips
            }
            self.c_trips.configure(values=list(self.trip_map.keys()))
            if self.trip_map:
                self.c_trips.set(list(self.trip_map.keys())[0])
        except Exception as e:
            _logger.warning("Could not load trips: %s", e)

    def _save_settings(self):
        data = {k: v.get() for k, v in self.inputs.items()}
        
        if not data["company_name"] or not data["cui"]:
            messagebox.showwarning(t("invoice.warning_fields_title"), t("invoice.warning_fields_msg"))
            return

        save_company_config(data)
        messagebox.showinfo(t("invoice.success_save_company"), t("invoice.success_save_company"))

    def _generate(self):
        selection = self.c_trips.get()
        if not selection:
            messagebox.showwarning(t("invoice.warning_select_trip"), t("invoice.warning_select_trip"))
            return

        try:
            trip_id = self.trip_map[selection]
            trip_data = self.trip_service.get_by_id(trip_id)
            mode = self.invoice_mode.get()
            _logger.info("Generating invoice for trip_id=%s mode=%s", trip_id, mode)

            path = self.invoice_service.generate_and_record(trip_data, mode=mode)

            if os.path.exists(path):
                os.startfile(path)
                self._refresh_trip_list()
            else:
                raise FileNotFoundError(f"Invoice PDF not found: {path}")

        except Exception as e:
            _logger.error("Invoice generation failed for trip_id=%s: %s", selection, e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(''), str(e))

    def _email_invoice(self):
        selection = self.c_trips.get()
        if not selection:
            messagebox.showwarning(t("invoice.warning_select_trip"), t("invoice.warning_select_trip"))
            return

        try:
            trip_id = self.trip_map[selection]
            trip_data = self.trip_service.get_by_id(trip_id)
            mode = self.invoice_mode.get()

            conf = load_company_config()
            recipient = self.inputs.get("email")
            recipient_addr = recipient.get().strip() if recipient else conf.get("email", "")

            if not recipient_addr:
                messagebox.showwarning(t("invoice.warning_fields_title"),
                                       t("settings.field_email"))
                return

            ok = self.invoice_service.send_invoice_email(
                trip_id=trip_id,
                recipient=recipient_addr,
                smtp_config=self.prefs.get_smtp_config(),
                trip_data=trip_data,
                mode=mode,
            )
            if ok:
                _logger.info("Invoice %s emailed to %s", trip_id, recipient_addr)
                messagebox.showinfo(t("invoice.button_email"),
                                    t("invoice.email_success").format(recipient_addr))
                self._refresh_trip_list()
            else:
                messagebox.showerror(t("invoice.email_failed"),
                                     t("invoice.email_failed").format(trip_id))

        except ValueError as e:
            _logger.error("Email invoice failed: %s", e)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))
        except Exception as e:
            _logger.error("Email invoice failed for trip_id=%s: %s", selection, e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(""), str(e))
