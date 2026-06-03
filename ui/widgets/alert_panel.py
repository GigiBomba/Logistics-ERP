"""AlertPanel — dropdown notification panel for the top bar bell icon."""
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from ui.theme import COLORS, FONTS, S
from services.i18n import t


class AlertPanel(ctk.CTkToplevel):
    """Popup panel showing alerts. Anchored below the bell button."""

    def __init__(self, parent, alerts, on_navigate):
        super().__init__(parent)
        self.on_navigate = on_navigate
        self.overrideredirect(True)
        self.configure(fg_color=COLORS["bg_elevated"])
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self._build(alerts)
        self.after(80, lambda: self.focus_set())
        self.bind("<FocusOut>", self._on_focus_out)

    def _build(self, alerts):
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_elevated"], corner_radius=0, height=42)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text=t("alerts.panel_title"),
                     font=FONTS["h3"], text_color=COLORS["text_primary"]).pack(
            side="left", padx=16, pady=10)

        # Scrollable list
        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_elevated"],
                                         scrollbar_button_color=COLORS["border"])
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        if not alerts:
            ctk.CTkLabel(scroll, text=t("alerts.none_active"),
                         font=FONTS["body"], text_color=COLORS["text_muted"]).pack(pady=40)
            return

        sorted_alerts = sorted(alerts, key=lambda a: a.created_at or "", reverse=True)[:20]
        for alert in sorted_alerts:
            self._build_row(scroll, alert)

        # Resize after building
        self.update_idletasks()
        h = min(self.winfo_reqheight(), 420)
        self.geometry(f"340x{h}")

    def _build_row(self, parent, alert):
        row = ctk.CTkFrame(parent, fg_color=COLORS["bg_elevated"], corner_radius=4, cursor="hand2")
        row.pack(fill="x", padx=8, pady=2)

        row.bind("<Enter>", lambda e: row.configure(fg_color=COLORS["bg_elevated"]))
        row.bind("<Leave>", lambda e: row.configure(fg_color=COLORS["bg_elevated"]))

        # Severity chip
        sev = str(getattr(alert.severity, "value", alert.severity)).upper()
        sev_color = {"CRITICAL": COLORS["danger"], "WARNING": COLORS["warning"]}.get(
            sev, COLORS["info"])
        sev_translation_key = f"alerts.severity_{sev.lower()}"
        chip = ctk.CTkLabel(row, text=t(sev_translation_key), fg_color=sev_color, text_color="white",
                            font=FONTS["label"], corner_radius=4, width=64, height=22)
        chip.pack(side="left", padx=(10, 0), pady=10)

        # Text
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", padx=10, pady=8, fill="x", expand=True)
        ctk.CTkLabel(text_frame, text=alert.title or alert.message,
                     font=FONTS["body"], text_color=COLORS["text_primary"],
                     anchor="w", wraplength=210).pack(anchor="w")
        ctk.CTkLabel(text_frame, text=self._time_ago(alert.created_at),
                     font=FONTS["small"], text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(2, 0))

        # Chevron
        ctk.CTkLabel(row, text="\u203a", font=FONTS["h2"],
                     text_color=COLORS["text_muted"]).pack(side="right", padx=12)

        # Click binds
        for w in (row, chip, text_frame):
            w.bind("<Button-1>", lambda e, a=alert: self._go(a))

    def _go(self, alert):
        self._close()
        alert_type = str(getattr(alert.type, "value", alert.type))
        destination = {
            "trip_delay": "dispatch_board",
            "maintenance": "maintenance_control",
            "inspection": "maintenance_control",
            "insurance": "fleet",
            "overdue_invoice": "invoices",
            "inactive_truck": "fleet",
            "route_issue": "route_planner",
            "compliance_warning": "maintenance",
        }.get(alert_type, "overview")
        if self.on_navigate:
            self.on_navigate(destination)

    def _on_focus_out(self, event):
        # Only close if focus moved outside this panel
        try:
            if event.widget != self and not str(event.widget).startswith(str(self)):
                self._close()
        except Exception:
            self._close()

    def _close(self):
        try:
            self.destroy()
        except Exception:
            pass

    def _time_ago(self, dt_str):
        if not dt_str:
            return ""
        try:
            dt = datetime.fromisoformat(dt_str)
        except Exception:
            return ""
        now = datetime.now()
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return t("time.just_now")
        if secs < 3600:
            return t("time.minutes_ago").format(n=secs // 60)
        if secs < 86400:
            return t("time.hours_ago").format(n=secs // 3600)
        return t("time.days_ago").format(n=delta.days)
