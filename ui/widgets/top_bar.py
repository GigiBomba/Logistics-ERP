"""Linear-style top bar widget."""
import customtkinter as ctk
from datetime import datetime
from ui.theme import COLORS, FONTS, S


class TopBar(ctk.CTkFrame):
    """48px top bar with breadcrumb, clock, and alert bell."""

    HEIGHT = 48

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        kwargs.setdefault("height", self.HEIGHT)
        super().__init__(parent, **kwargs)
        self.pack_propagate(False)
        self._clock_timer = None
        self._alert_panel = None
        self._on_navigate = None

        self._build()
        self._update_clock()

    def _build(self):
        # Bottom border
        ctk.CTkFrame(
            self, fg_color=COLORS["border"],
            height=1, corner_radius=0
        ).pack(side="bottom", fill="x")

        # Left: breadcrumb
        self._breadcrumb = ctk.CTkLabel(
            self,
            text="",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._breadcrumb.pack(side="left", padx=S["6"], fill="y")

        # Right: clock + bell
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=S["5"], fill="y")

        # Alert bell
        self._bell = ctk.CTkLabel(
            right, text="\U0001f514",
            font=FONTS["h3"],
            text_color=COLORS["text_muted"],
            cursor="hand2",
        )
        self._bell.pack(side="right", padx=(S["4"], 0))
        self._bell.bind("<Button-1>", self._toggle_alerts)

        # Alert count badge
        self._badge = ctk.CTkLabel(
            right, text="",
            font=FONTS["label"],
            fg_color=COLORS["danger"],
            text_color="white",
            corner_radius=99,
            width=18, height=18,
        )

        # Clock
        self._clock = ctk.CTkLabel(
            right, text="",
            font=FONTS["mono"],
            text_color=COLORS["text_muted"],
        )
        self._clock.pack(side="right")

    def set_breadcrumb(self, text: str):
        self._breadcrumb.configure(text=text)

    def set_alert_count(self, count: int):
        if count > 0:
            self._badge.configure(text=str(min(count, 99)))
            self._badge.place(in_=self._bell, relx=0.6, rely=0.0, anchor="nw")
            self._bell.configure(text_color=COLORS["text_danger"])
        else:
            self._badge.place_forget()
            self._bell.configure(text_color=COLORS["text_muted"])

    def set_alert_navigate_callback(self, callback):
        self._on_navigate = callback

    def _update_clock(self):
        try:
            self._clock.configure(text=datetime.now().strftime("%H:%M"))
        except Exception:
            pass
        try:
            self._clock_timer = self.after(30_000, self._update_clock)
        except Exception:
            pass

    def _toggle_alerts(self, event=None):
        if self._alert_panel:
            try:
                self._alert_panel.destroy()
            except Exception:
                pass
            self._alert_panel = None
            return

        from services.operations.alert_manager import AlertManager
        try:
            alerts = AlertManager().get_alerts(resolved=False, limit=20)
        except Exception:
            alerts = []

        x = self._bell.winfo_rootx() - 280
        y = self._bell.winfo_rooty() + self._bell.winfo_height() + 4

        from ui.widgets.alert_panel import AlertPanel
        self._alert_panel = AlertPanel(
            parent=self.winfo_toplevel(),
            alerts=alerts,
            on_navigate=self._on_navigate,
        )
        self._alert_panel.geometry(f"340x420+{x}+{y}")

    def destroy(self):
        if self._clock_timer:
            try:
                self.after_cancel(self._clock_timer)
            except Exception:
                pass
        super().destroy()
