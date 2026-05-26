import tkinter as tk
from tkinter import ttk, messagebox
from services.i18n import t, register_listener, unregister_listener
from services.invoicing.config_manager import load_company_config, save_company_config
from services.preferences import PreferencesManager
from ui.styles import Theme
from ui.widgets import StyledEntry, ActionButton


class SettingsView:
    def __init__(self, parent, db, prefs=None):
        self.win = tk.Toplevel(parent)
        self.win.title(f"⚙️ {t('settings.title')}")
        self.win.geometry("600x850")
        Theme.apply(self.win)
        self.db = db
        self.prefs = prefs or PreferencesManager(db)
        self._i18n_widgets = []
        self._setup_ui()
        self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_destroy(self, event=None):
        if event is not None and event.widget != self.win:
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        self.win.title(f"⚙️ {t('settings.title')}")
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.config(text=f"{prefix}{t(key)}")
            except Exception:
                pass

    def _setup_ui(self):
        container = tk.Frame(self.win, bg=Theme.BG, padx=30, pady=20)
        container.pack(fill="both", expand=True)

        f1 = tk.LabelFrame(container, text=f" 🏢 {t('settings.section_company')} ", bg=Theme.BG, fg=Theme.ACCENT, padx=15, pady=15)
        f1.pack(fill="x", pady=10)
        self._i18n_tag(f1, "settings.section_company", " 🏢 ")

        conf = load_company_config()
        self.company_inputs = {}
        fields = [
            ("company_name", t("settings.field_company_name")),
            ("cui", t("settings.field_cui")),
            ("reg_number", t("settings.field_reg_number")),
            ("address", t("settings.field_address")),
            ("phone", t("settings.field_phone")),
            ("email", t("settings.field_email"))
        ]

        for key, label in fields:
            lbl = tk.Label(f1, text=label, bg=Theme.BG, fg=Theme.TEXT)
            lbl.pack(anchor="w")
            self._i18n_tag(lbl, f"settings.field_{key}")
            e = StyledEntry(f1)
            e.insert(0, conf.get(key, ""))
            e.pack(fill="x", pady=(0, 10))
            self.company_inputs[key] = e

        fp = tk.LabelFrame(container, text=f" 🎯 {t('settings.section_preferences')} ", bg=Theme.BG, fg=Theme.ACCENT, padx=15, pady=15)
        fp.pack(fill="x", pady=10)
        self._i18n_tag(fp, "settings.section_preferences", " 🎯 ")

        lbl = tk.Label(fp, text=t("settings.language_label"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "settings.language_label")
        self._lang_var = tk.StringVar(value=self.prefs.get_language())
        lang_codes = self.prefs.get_available_languages()
        lang_display = [f"{self.prefs.get_language_display_name(c)} ({c})" for c in lang_codes]
        lang_menu = ttk.Combobox(fp, values=lang_display, textvariable=tk.StringVar(), state="readonly")
        lang_menu.pack(fill="x", pady=(0, 10))
        current_idx = next((i for i, c in enumerate(lang_codes) if c == self.prefs.get_language()), 0)
        lang_menu.current(current_idx)
        self._lang_menu = lang_menu
        self._lang_codes = lang_codes
        self._lang_menu.bind("<<ComboboxSelected>>", self._on_lang_changed)

        lbl = tk.Label(fp, text=t("settings.currency_label"), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, "settings.currency_label")
        self._currency_var = tk.StringVar(value=self.prefs.get_currency())
        currency_menu = ttk.Combobox(fp, textvariable=self._currency_var, values=self.prefs.get_supported_currencies(), state="readonly")
        currency_menu.pack(fill="x", pady=(0, 5))
        self._currency_menu = currency_menu

        f2 = tk.LabelFrame(container, text=f" 📧 {t('settings.section_smtp')} ", bg=Theme.BG, fg=Theme.ACCENT, padx=15, pady=15)
        f2.pack(fill="x", pady=10)
        self._i18n_tag(f2, "settings.section_smtp", " 📧 ")

        smtp_conf = {}
        try:
            rows = self.db.conn.execute("SELECT key, value FROM settings").fetchall()
            smtp_conf = {row['key']: row['value'] for row in rows}
        except: pass

        self.smtp_srv = self._add_smtp_field(f2, "settings.smtp_server", smtp_conf.get('smtp_server', ''))
        self.smtp_port = self._add_smtp_field(f2, "settings.smtp_port", smtp_conf.get('smtp_port', '587'))
        self.smtp_user = self._add_smtp_field(f2, "settings.smtp_user", smtp_conf.get('smtp_user', ''))
        self.smtp_pwd = self._add_smtp_field(f2, "settings.smtp_password", smtp_conf.get('smtp_password', ''), show="*")

        btn = ActionButton(container, f"💾 {t('settings.save_all')}", self._save_all, color=Theme.ACCENT_SUCCESS)
        btn.pack(fill="x", pady=20)
        self._i18n_tag(btn, "settings.save_all", "💾 ")

    def _add_smtp_field(self, p, key, val, show=""):
        lbl = tk.Label(p, text=t(key), bg=Theme.BG, fg=Theme.TEXT)
        lbl.pack(anchor="w")
        self._i18n_tag(lbl, key)
        e = StyledEntry(p, show=show); e.insert(0, val); e.pack(fill="x", pady=(0,5)); return e

    def _on_lang_changed(self, event=None):
        idx = self._lang_menu.current()
        if 0 <= idx < len(self._lang_codes):
            self.prefs.set_language(self._lang_codes[idx])

    def _on_currency_changed(self, event=None):
        self.prefs.set_currency(self._currency_var.get())

    def _save_all(self):
        company_data = {k: v.get() for k, v in self.company_inputs.items()}
        save_company_config(company_data)

        self._on_lang_changed()
        self._on_currency_changed()

        try:
            self.db.update_smtp_setting(self.smtp_srv.get(), self.smtp_port.get(), self.smtp_user.get(), self.smtp_pwd.get())
            messagebox.showinfo(t("settings.success_save"), t("settings.success_save"))
            self.win.destroy()
        except Exception as e:
            messagebox.showerror(t("settings.error_save_smtp").format(''), t("settings.error_save_smtp").format(e))
