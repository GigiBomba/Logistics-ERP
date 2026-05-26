from services.i18n import t


class SettingsTab:
    def __init__(self, parent, db):
        self.frame = tk.Frame(parent, bg=Theme.BG)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        f = tk.LabelFrame(self.frame, text=f" ⚙️ {t('settings.section_smtp_legacy')} ", bg=Theme.BG, fg=Theme.ACCENT, padx=20, pady=20)
        f.pack(padx=40, pady=40, fill="x")

        # Incarca setari existente
        rows = self.db.conn.execute("SELECT key, value FROM settings").fetchall()
        conf = {row['key']: row['value'] for row in rows}

        self.srv = self._add_entry(f, t("settings.smtp_server"), conf.get('smtp_server', ''))
        self.port = self._add_entry(f, t("settings.smtp_port_legacy"), conf.get('smtp_port', '587'))
        self.user = self._add_entry(f, t("settings.smtp_user_legacy"), conf.get('smtp_user', ''))
        self.pwd = self._add_entry(f, t("settings.smtp_password_legacy"), conf.get('smtp_password', ''), show="*")

        ActionButton(f, f"💾 {t('settings.save_smtp')}", self._save, color=Theme.ACCENT_SUCCESS).pack(pady=20, fill="x")

    def _add_entry(self, p, txt, val, show=""):
        tk.Label(p, text=txt, bg=Theme.BG, fg=Theme.TEXT).pack(anchor="w")
        e = StyledEntry(p, show=show); e.insert(0, val); e.pack(fill="x", pady=(0,10)); return e

    def _save(self):
        self.db.update_smtp_setting(self.srv.get(), self.port.get(), self.user.get(), self.pwd.get())
        messagebox.showinfo(t("settings.success_smtp"), t("settings.success_smtp"))
