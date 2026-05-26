import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import os
from services.i18n import t, register_listener, unregister_listener
from services.invoicing.config_manager import load_company_config, save_company_config
from services.invoicing.generator import InvoiceGenerator
from ui.styles import Theme
from ui.widgets import StyledEntry, ActionButton, StyledRadioButton

_logger = logging.getLogger(__name__)

class InvoiceTab:
    def __init__(self, parent, db, prefs=None):
        self.frame = tk.Frame(parent, bg=Theme.BG)
        self.db = db
        self.generator = InvoiceGenerator()
        from services.preferences import PreferencesManager
        self.prefs = prefs or PreferencesManager(db)
        self._i18n_widgets = []
        self._radio_buttons = []
        
        self._setup_ui()
        
        self.frame.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.frame:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        for rb in self._radio_buttons:
            try:
                rb.refresh_translations()
            except Exception:
                pass

    def _setup_ui(self):
        config_f = tk.LabelFrame(self.frame, text=f" 🏢 {t('invoice.section_company')} ", 
                                  bg=Theme.BG, fg=Theme.ACCENT, font=Theme.FONT_BOLD, padx=20, pady=20)
        config_f.pack(fill="x", padx=30, pady=20)
        self._i18n_tag(config_f, "invoice.section_company", " 🏢 ")

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
            lbl = tk.Label(config_f, text=label, bg=Theme.BG, fg=Theme.TEXT, font=("Segoe UI", 9))
            lbl.grid(row=row*2, column=col, sticky="w", pady=(8,0), padx=5)
            self._i18n_tag(lbl, f"invoice.field_{key}")
            
            entry = StyledEntry(config_f)
            entry.insert(0, conf.get(key, ""))
            entry.grid(row=row*2+1, column=col, sticky="ew", padx=5, pady=(0,5))
            self.inputs[key] = entry
        
        config_f.columnconfigure((0,1), weight=1)
        
        btn = ActionButton(config_f, f"💾 {t('invoice.save_company')}", self._save_settings, 
                     color=Theme.ACCENT_SUCCESS)
        btn.grid(row=6, column=0, columnspan=2, pady=15)
        self._i18n_tag(btn, "invoice.save_company", "💾 ")

        gen_f = tk.LabelFrame(self.frame, text=f" 🧾 {t('invoice.section_generator')} ", 
                                bg=Theme.BG, fg=Theme.ACCENT, font=Theme.FONT_BOLD, padx=20, pady=20)
        gen_f.pack(fill="both", expand=True, padx=30, pady=(0,30))
        self._i18n_tag(gen_f, "invoice.section_generator", " 🧾 ")

        lbl = tk.Label(gen_f, text=f"1. {t('invoice.select_trip')}", bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "invoice.select_trip", "1. ")
        
        trip_sel_f = tk.Frame(gen_f, bg=Theme.BG)
        trip_sel_f.pack(fill="x", pady=10)
        
        self.c_trips = ttk.Combobox(trip_sel_f, state="readonly", font=("Segoe UI", 10))
        self.c_trips.pack(side="left", fill="x", expand=True, padx=(0,10))
        
        ActionButton(trip_sel_f, "🔄", self._refresh_trip_list, color=Theme.SURFACE2, width=3).pack(side="right")
        
        lbl = tk.Label(gen_f, text=f"2. {t('invoice.doc_type_label')}", bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_BOLD)
        lbl.pack(anchor="w", pady=(15, 5))
        self._i18n_tag(lbl, "invoice.doc_type_label", "2. ")
        
        self.invoice_mode = tk.StringVar(value="client")
        
        radio_f = tk.Frame(gen_f, bg=Theme.BG)
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

        btn = ActionButton(gen_f, f"🚀 {t('invoice.generate_button')}", self._generate, 
                     color=Theme.ACCENT)
        btn.pack(fill="x", side="bottom", pady=10)
        self._i18n_tag(btn, "invoice.generate_button", "🚀 ")

        self._refresh_trip_list()

    def _refresh_trip_list(self):
        try:
            trips = self.db.get_all_trips()
            self.trip_map = {
                f"ID {t['id']} | {t['truck_number']} | Client: {t['client_name']} | Data: {t['created_at'][:10]}": t['id'] 
                for t in trips
            }
            self.c_trips['values'] = list(self.trip_map.keys())
            if self.c_trips['values']:
                self.c_trips.current(0)
        except Exception as e:
            print(f"Eroare la încărcarea curselor: {e}")

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
            trip_data = self.db.get_trip_by_id(trip_id)
            mode = self.invoice_mode.get()
            _logger.info("Generating invoice for trip_id=%s mode=%s", trip_id, mode)

            path = self.generator.generate(trip_data, mode=mode)

            if mode == "client":
                due_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
                inv_number = f"INV-{datetime.now().year}-{trip_data['id']:04d}"
                self.db.create_invoice_record(
                    trip_id=trip_id,
                    inv_number=inv_number,
                    amount=trip_data['total_price_eur'],
                    due_date=due_date,
                )
                _logger.info("Invoice record created: %s", inv_number)

            if os.path.exists(path):
                os.startfile(path)
                self._refresh_trip_list()
            else:
                raise FileNotFoundError(f"Invoice PDF not found: {path}")

        except Exception as e:
            _logger.error("Invoice generation failed for trip_id=%s: %s", selection, e, exc_info=True)
            messagebox.showerror(t("invoice.error_generate").format(''), str(e))
