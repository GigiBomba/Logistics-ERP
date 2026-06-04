import logging
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from services.i18n import t, register_listener, unregister_listener
from services.invoicing.config_manager import load_company_config, save_company_config
from services.preferences import PreferencesManager
from services.operations.notification_center import NotificationCenter
from services.operations.event_bus import EventBus, SETTINGS_UPDATED
from ui.styles import Theme
from ui.widgets import StyledEntry, ActionButton
from ui.theme import COLORS, FONTS

logger = logging.getLogger(__name__)


class SettingsView:
    def __init__(self, parent, db, prefs=None, ops=None, embedded=False):
        self.db = db
        self.prefs = prefs or PreferencesManager(db)
        self.ops = ops
        self._embedded = embedded

        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
            self._tk_root = parent.winfo_toplevel()
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.title(f"\u2699\ufe0f {t('settings.title')}")
            self.win.geometry("620x950")
            Theme.apply(self.win)
            self.win.configure(fg_color=Theme.BG)
            self.frame = ctk.CTkFrame(self.win, fg_color=Theme.BG)
            self.frame.pack(fill="both", expand=True)
            self._tk_root = self.win

        self._i18n_widgets = []
        self._section_headings = {}
        self._setup_ui()

        if self.win:
            self.win.protocol("WM_DELETE_WINDOW", self._on_close)
            self.win.bind("<Destroy>", self._on_destroy)
        register_listener(self._on_language_changed)

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _on_close(self):
        if self.win:
            self.win.destroy()

    def _on_destroy(self, event=None):
        if event is not None and event.widget != (self.win or self.frame):
            return
        unregister_listener(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.refresh_translations()

    def refresh_translations(self):
        if self.win:
            self.win.title(f"\u2699\ufe0f {t('settings.title')}")
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{t(key)}")
            except Exception:
                pass
        for text_key, lbl in self._section_headings.items():
            try:
                lbl.configure(text=t(text_key))
            except Exception:
                pass

    def _section_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"], corner_radius=10)
        card.pack(fill="x", pady=(0, 16))
        return card

    def _section_heading(self, card, text_key, emoji=""):
        lbl = ctk.CTkLabel(card, text=emoji + t(text_key), font=FONTS["h3"],
                           text_color=COLORS["text_primary"])
        lbl.pack(anchor="w", padx=20, pady=(16, 4))
        self._section_headings[text_key] = lbl
        ctk.CTkFrame(card, fg_color=COLORS["border"], height=1).pack(fill="x", padx=20, pady=(0, 12))
        return lbl

    def _field_row(self, parent, label_key):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 14))
        lbl = ctk.CTkLabel(row, text=t(label_key), font=FONTS["label"],
                           text_color=COLORS["text_secondary"], anchor="w")
        lbl.pack(anchor="w", pady=(0, 4))
        self._i18n_tag(lbl, label_key)
        return row

    def _setup_ui(self):
        header = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_base"], height=64)
        header.pack(fill="x", padx=24, pady=(20, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(header, text=t("settings.title"), font=FONTS["h1"],
                     text_color=COLORS["text_primary"], anchor="w").pack(anchor="w")
        ctk.CTkLabel(header, text=t("settings.subtitle"), font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w").pack(anchor="w", pady=(2, 0))

        scroll = ctk.CTkScrollableFrame(self.frame, fg_color=COLORS["bg_base"],
                                        scrollbar_button_color=COLORS["border"],
                                        scrollbar_button_hover_color=COLORS["accent"])
        scroll.pack(fill="both", expand=True, padx=24, pady=(16, 0))

        # ── Company ──
        self._build_section_company(scroll)

        # ── Preferences ──
        self._build_section_preferences(scroll)

        # ── Email & SMTP ──
        self._build_section_email(scroll)

        # ── Fleet Tracking ──
        self._build_section_tracking(scroll)

        # ── Maintenance Thresholds ──
        self._build_section_maintenance(scroll)

        # Bottom padding
        ctk.CTkFrame(scroll, fg_color="transparent", height=8).pack()

        # ── Save bar ──
        save_bar = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_surface"],
                                corner_radius=0, height=64)
        save_bar.pack(fill="x", side="bottom")
        save_bar.pack_propagate(False)
        ctk.CTkFrame(save_bar, fg_color=COLORS["border"], height=1).pack(fill="x", side="top")

        save_btn = ctk.CTkButton(save_bar, text=t("settings.save"),
                                 font=FONTS["body_bold"], fg_color=COLORS["accent"],
                                 hover_color=COLORS["accent_hover"], height=38, width=160,
                                 corner_radius=8, command=self._save_all)
        save_btn.pack(side="right", padx=24, pady=12)
        self._i18n_tag(save_btn, "settings.save")

        reset_btn = ctk.CTkButton(save_bar, text=t("settings.reset"),
                                  font=FONTS["body"], fg_color="transparent",
                                  border_width=1, border_color=COLORS["border"],
                                  text_color=COLORS["text_secondary"],
                                  hover_color=COLORS["bg_elevated"],
                                  height=38, width=120, corner_radius=8)
        reset_btn.pack(side="left", padx=24, pady=12)

    def _build_section_company(self, parent):
        card = self._section_card(parent)
        self._section_heading(card, "settings.section_company")

        conf = load_company_config()
        self.company_inputs = {}
        fields = [
            ("company_name", "settings.field_company_name"),
            ("cui", "settings.field_cui"),
            ("reg_number", "settings.field_reg_number"),
            ("address", "settings.field_address"),
            ("phone", "settings.field_phone"),
            ("email", "settings.field_email"),
        ]
        for key, label_key in fields:
            row = self._field_row(card, label_key)
            e = StyledEntry(row)
            e.insert(0, conf.get(key, ""))
            e.pack(fill="x")
            self.company_inputs[key] = e

    def _build_section_preferences(self, parent):
        card = self._section_card(parent)
        self._section_heading(card, "settings.section_preferences")

        row = self._field_row(card, "settings.language_label")
        self._lang_codes = self.prefs.get_available_languages()
        lang_display = [f"{self.prefs.get_language_display_name(c)} ({c})" for c in self._lang_codes]
        current_idx = next((i for i, c in enumerate(self._lang_codes) if c == self.prefs.get_language()), 0)
        self._lang_menu = ctk.CTkComboBox(row, values=lang_display, state="readonly",
                                          command=self._on_lang_changed)
        self._lang_menu.set(lang_display[current_idx])
        self._lang_menu.pack(fill="x")

        row = self._field_row(card, "settings.currency_label")
        self._currency_menu = ctk.CTkComboBox(row, values=self.prefs.get_supported_currencies(),
                                              state="readonly", command=self._on_currency_changed)
        self._currency_menu.set(self.prefs.get_currency())
        self._currency_menu.pack(fill="x")

    def _on_lang_changed(self, event=None):
        val = event if isinstance(event, str) else self._lang_menu.get()
        try:
            idx = self._lang_menu.cget("values").index(val)
            if 0 <= idx < len(self._lang_codes):
                self.prefs.set_language(self._lang_codes[idx])
        except (ValueError, tk.TclError):
            pass

    def _on_currency_changed(self, event=None):
        self.prefs.set_currency(self._currency_menu.get())

    def _build_section_email(self, parent):
        card = self._section_card(parent)
        self._section_heading(card, "settings.section_email")

        smtp_keys = ["smtp_server", "smtp_port", "smtp_user", "smtp_password",
                     "alert_email_recipients"]
        smtp_labels = [
            "settings.field_smtp_server", "settings.field_smtp_port",
            "settings.field_smtp_user", "settings.field_smtp_password",
            "settings.field_alert_recipients",
        ]
        smtp_cfg = self.prefs.get_settings(smtp_keys) if self.prefs else {}

        self.smtp_inputs = {}
        for key, label_key in zip(smtp_keys, smtp_labels):
            row = self._field_row(card, label_key)
            e = StyledEntry(row)
            e.insert(0, smtp_cfg.get(key, ""))
            if key == "smtp_password":
                e.configure(show="*")
            e.pack(fill="x")
            self.smtp_inputs[key] = e

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 20))
        ActionButton(btn_row, t("settings.test_connection"),
                     self._test_smtp, color=COLORS["bg_elevated"]
                     ).pack(side="left", padx=(0, 8))
        ActionButton(btn_row, t("settings.email_logs"),
                     self._view_email_logs, color=COLORS["bg_elevated"]
                     ).pack(side="left")

    def _build_section_tracking(self, parent):
        card = self._section_card(parent)
        self._section_heading(card, "tracking.section_title", emoji="\U0001f4cc ")

        ctk.CTkLabel(card, text=t("tracking.setup_hint"), font=FONTS["small"],
                     text_color=COLORS["text_muted"], anchor="w", wraplength=520
                     ).pack(anchor="w", padx=20, pady=(0, 8))

        row = self._field_row(card, "tracking.platform")
        platform_vals = [
            t("tracking.platform_not_configured"),
            "Wialon / GPS-Trace (Gurtam)", "Frotcom", "Navixy",
            "Traccar (self-hosted)", "Generic REST API",
        ]
        self._tracking_platform_menu = ctk.CTkComboBox(
            row, values=platform_vals, state="readonly",
            command=self._on_tracking_platform_changed)
        saved_platform = (self.db.get_setting("tracking.platform") or "") if self.db else ""
        display_val = saved_platform if saved_platform else platform_vals[0]
        self._tracking_platform_menu.set(display_val)
        self._tracking_platform_menu.pack(fill="x")

        self._tracking_rows = {}

        r = self._field_row(card, "tracking.token")
        e = StyledEntry(r)
        e.insert(0, (self.db.get_setting("tracking.token") or "") if self.db else "")
        e.pack(fill="x")
        self._tracking_rows["token"] = (r, e)

        r = self._field_row(card, "tracking.host")
        e = StyledEntry(r)
        e.insert(0, (self.db.get_setting("tracking.host") or "") if self.db else "")
        e.pack(fill="x")
        self._tracking_rows["host"] = (r, e)

        r = self._field_row(card, "tracking.username")
        e = StyledEntry(r)
        e.insert(0, (self.db.get_setting("tracking.username") or "") if self.db else "")
        e.pack(fill="x")
        self._tracking_rows["username"] = (r, e)

        r = self._field_row(card, "tracking.password")
        e = StyledEntry(r)
        e.configure(show="*")
        e.insert(0, (self.db.get_setting("tracking.password") or "") if self.db else "")
        e.pack(fill="x")
        self._tracking_rows["password"] = (r, e)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 20))
        ActionButton(btn_row, t("tracking.btn_test"),
                     self._test_tracking_connection, color=COLORS["bg_elevated"]
                     ).pack(side="left", padx=(0, 8))
        self._tracking_test_lbl = ctk.CTkLabel(
            btn_row, text="", font=FONTS["small"], text_color=COLORS["text_muted"])
        self._tracking_test_lbl.pack(side="left")

        self._on_tracking_platform_changed(self._tracking_platform_menu.get())

    def _on_tracking_platform_changed(self, event=None):
        val = event if event is not None else self._tracking_platform_menu.get()
        p = val.lower()
        if t("tracking.platform_not_configured").lower() in p or "not configured" in p:
            visible = {k: False for k in self._tracking_rows}
        elif "wialon" in p or "gps-trace" in p or "gurtam" in p:
            visible = {"token": True, "host": True, "username": False, "password": False}
        elif "frotcom" in p:
            visible = {"token": False, "host": False, "username": True, "password": True}
        elif "navixy" in p:
            visible = {"token": True, "host": True, "username": False, "password": False}
        elif "traccar" in p:
            visible = {"token": False, "host": True, "username": True, "password": True}
        elif "generic" in p or "rest" in p:
            visible = {"token": True, "host": True, "username": False, "password": False}
        else:
            visible = {k: False for k in self._tracking_rows}

        for key, (row, _entry) in self._tracking_rows.items():
            if visible.get(key, False):
                row.pack(fill="x", padx=20, pady=(0, 14))
            else:
                row.pack_forget()

    def _test_tracking_connection(self):
        from services.fleet_tracking_service import FleetTrackingService

        platform = self._tracking_platform_menu.get()
        if t("tracking.platform_not_configured").lower() in platform.lower():
            self._tracking_test_lbl.configure(
                text="\u2717 " + t("tracking.test_incomplete"),
                text_color=COLORS["text_danger"])
            return

        all_filled = True
        for key, (row, entry) in self._tracking_rows.items():
            if row.winfo_ismapped():
                if not entry.get().strip():
                    all_filled = False
                    break

        if not all_filled:
            self._tracking_test_lbl.configure(
                text="\u2717 " + t("tracking.test_incomplete"),
                text_color=COLORS["text_danger"])
            return

        settings_map = {"tracking.platform": platform}
        for key, (row, entry) in self._tracking_rows.items():
            settings_map[f"tracking.{key}"] = entry.get().strip()
        if self.prefs:
            for k, v in settings_map.items():
                self.prefs.save_setting(k, v)

        svc = FleetTrackingService()
        svc.initialize(self.db)
        ok, msg = svc.test_connection()

        if not ok:
            logger.error("Tracking connection test failed: %s", msg)
            self._tracking_test_lbl.configure(
                text="\u2717 " + t("tracking.test_incorrect"),
                text_color=COLORS["text_danger"])
        else:
            self._tracking_test_lbl.configure(
                text="\u2713 " + msg,
                text_color=COLORS["text_success"])

    def _build_section_maintenance(self, parent):
        card = self._section_card(parent)
        self._section_heading(card, "settings.section_maintenance")

        for key, label_key in [
            ("alert_days_ahead", "settings.field_alert_days_ahead"),
            ("tacho_warning", "settings.field_tacho_warning"),
            ("tacho_critical", "settings.field_tacho_critical"),
        ]:
            row = self._field_row(card, label_key)
            e = StyledEntry(row)
            smtp_val = self.prefs.get_setting(key, "") if self.prefs else ""
            e.insert(0, smtp_val or "")
            e.pack(fill="x")
            setattr(self, f"_{key}_entry", e)

    def _save_all(self):
        company_data = {k: v.get() for k, v in self.company_inputs.items()}
        save_company_config(company_data)

        self._on_lang_changed()
        self._on_currency_changed()

        smtp_keys = ["smtp_server", "smtp_port", "smtp_user", "smtp_password",
                     "alert_email_recipients"]
        for key in smtp_keys:
            val = self.smtp_inputs.get(key)
            if val:
                self.prefs.save_setting(key, val.get().strip())

        if self.prefs:
            platform = self._tracking_platform_menu.get()
            self.prefs.save_setting("tracking.platform", platform)
            for key, (_row, entry) in self._tracking_rows.items():
                self.prefs.save_setting(f"tracking.{key}", entry.get().strip())

        for key in ["alert_days_ahead", "tacho_warning", "tacho_critical"]:
            entry = getattr(self, f"_{key}_entry", None)
            if entry:
                self.prefs.save_setting(key, entry.get().strip())

        if self.ops:
            try:
                self.ops._configure_smtp_from_db()
            except Exception:
                pass

        EventBus().publish(SETTINGS_UPDATED, {})

        messagebox.showinfo(t("settings.success_save"), t("settings.success_save"))

    def _test_smtp(self):
        nc = NotificationCenter()
        smtp_data = {k: v.get().strip() for k, v in self.smtp_inputs.items()}
        try:
            port = int(smtp_data.get("smtp_port", "587"))
        except ValueError:
            messagebox.showwarning(t("settings.title"),
                                   t("settings.test_failed").format("Invalid port"))
            return
        nc.configure_smtp(smtp_data.get("smtp_server", ""), port,
                         smtp_data.get("smtp_user", ""),
                         smtp_data.get("smtp_password", ""))
        recipients_raw = smtp_data.get("alert_email_recipients", "")
        first_recipient = ((recipients_raw.split(",")[0].strip())
                           if recipients_raw else smtp_data.get("smtp_user", ""))
        if nc.send_test_email(first_recipient):
            messagebox.showinfo(t("settings.test_connection"),
                                t("settings.test_success"))
        else:
            messagebox.showerror(t("settings.test_connection"),
                                 t("settings.test_failed").format("SMTP error"))

    def _view_email_logs(self):
        win = ctk.CTkToplevel(self.win or self.frame)
        win.configure(fg_color=Theme.BG)
        win.title(t("settings.email_logs"))
        win.geometry("700x400")
        Theme.apply(win)

        tree = ttk.Treeview(win,
                            columns=("id", "recipient", "subject", "timestamp", "status"),
                            show="headings")
        tree.heading("id", text="ID"); tree.column("id", width=40, anchor="center")
        tree.heading("recipient", text="Recipient"); tree.column("recipient", width=200)
        tree.heading("subject", text="Subject"); tree.column("subject", width=200)
        tree.heading("timestamp", text="Sent"); tree.column("timestamp", width=150, anchor="center")
        tree.heading("status", text="Status"); tree.column("status", width=60, anchor="center")
        tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        try:
            rows = self.db.conn.execute(
                "SELECT id, recipient, subject, timestamp, status FROM email_logs "
                "ORDER BY id DESC LIMIT 200").fetchall()
            for r in rows:
                tree.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4]))
        except Exception:
            tree.insert("", "end", values=("", "No logs found", "", "", ""))
