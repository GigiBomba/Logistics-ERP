"""Tab switching container for the Dispatch Board redesign."""
import customtkinter as ctk
from ui.theme import COLORS, FONTS
from services.i18n import t


class DispatchTabs(ctk.CTkFrame):
    """A horizontal tab bar that switches between panels."""

    TAB_BG = COLORS["bg_surface"]
    TAB_ACTIVE = COLORS["accent"]
    TAB_INACTIVE = COLORS["bg_elevated"]
    TAB_HOVER = COLORS["border_hover"]

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_surface"], corner_radius=0, **kwargs)
        self._tabs = {}
        self._buttons = {}
        self._active_tab = None
        self._on_switch_callback = None
        self._btn_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_surface"], corner_radius=0)
        self._btn_frame.pack(fill="x")

    def add_tab(self, tab_id: str, label: str, panel: ctk.CTkFrame):
        self._tabs[tab_id] = panel
        btn = ctk.CTkButton(
            self._btn_frame, text=label,
            fg_color=self.TAB_INACTIVE, text_color=COLORS["text_secondary"],
            font=FONTS["body_bold"], corner_radius=0, height=36,
            cursor="hand2",
            command=lambda tid=tab_id: self.switch_to(tid),
        )
        btn.pack(side="left")
        self._buttons[tab_id] = btn

    def switch_to(self, tab_id: str):
        if tab_id == self._active_tab:
            return
        if self._active_tab:
            old_panel = self._tabs.get(self._active_tab)
            if old_panel:
                old_panel.pack_forget()
            old_btn = self._buttons.get(self._active_tab)
            if old_btn:
                old_btn.configure(fg_color=self.TAB_INACTIVE, text_color=COLORS["text_secondary"])

        panel = self._tabs.get(tab_id)
        if panel:
            panel.pack(fill="both", expand=True)
        btn = self._buttons.get(tab_id)
        if btn:
            btn.configure(fg_color=self.TAB_ACTIVE, text_color="#ffffff")

        self._active_tab = tab_id
        if self._on_switch_callback:
            self._on_switch_callback(tab_id)

    def on_switch(self, callback):
        self._on_switch_callback = callback

    def refresh_translations(self, labels: dict):
        for tab_id, lbl in labels.items():
            btn = self._buttons.get(tab_id)
            if btn:
                btn.configure(text=lbl)

    def get_active_tab(self):
        return self._active_tab
