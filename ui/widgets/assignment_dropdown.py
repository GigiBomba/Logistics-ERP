import tkinter as tk
import customtkinter as ctk
from tkinter import ttk
from ui.styles import Theme
from services.i18n import t
from ui.theme import FONTS


class AssignmentDropdown(ctk.CTkToplevel):

    DROPDOWN_BG = Theme.SURFACE
    ITEM_BG = Theme.SURFACE2
    ITEM_BG_HOVER = Theme.SURFACE3
    ITEM_UNAVAILABLE_FG = Theme.MUTED
    MAX_HEIGHT = 300
    WIDTH = 280

    def __init__(self, parent, anchor_widget, title: str, fetch_func, on_select, on_close=None):
        super().__init__(parent)
        self._anchor = anchor_widget
        self._fetch_func = fetch_func
        self._on_select = on_select
        self._on_close = on_close
        self._items = []

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=Theme.BORDER)

        self._container = ctk.CTkFrame(self, fg_color=self.DROPDOWN_BG)
        self._container.pack(fill="both", expand=True, padx=1, pady=1)

        header = ctk.CTkFrame(self._container, fg_color=self.DROPDOWN_BG)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=title, fg_color=self.DROPDOWN_BG, text_color=Theme.TEXT,
                     font=FONTS["small"]).pack(side="left")

        close_btn = ctk.CTkLabel(header, text="\u2715", fg_color=self.DROPDOWN_BG, text_color=Theme.MUTED,
                                font=FONTS["label"], cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._close())

        self._scroll_frame = ctk.CTkScrollableFrame(self._container, fg_color=self.DROPDOWN_BG, height=self.MAX_HEIGHT)
        self._scroll_frame.pack(fill="both", expand=True)

        self._spinner_lbl = ctk.CTkLabel(self._scroll_frame, text=t("dispatch_board.loading_options"),
                                         fg_color=self.DROPDOWN_BG, text_color=Theme.MUTED,
                                         font=FONTS["label"])
        self._spinner_lbl.pack(pady=20)

        self._position_dropdown()

        self.bind("<FocusOut>", lambda e: self._close())
        self._container.bind("<Button-1>", lambda e: self.focus_set())
        self.focus_set()

        self.after(50, self._load_items)

    def _position_dropdown(self):
        try:
            x = self._anchor.winfo_rootx()
            y = self._anchor.winfo_rooty() + self._anchor.winfo_height() + 2
            screen_h = self.winfo_screenheight()
            if y + self.MAX_HEIGHT > screen_h:
                y = self._anchor.winfo_rooty() - self.MAX_HEIGHT - 2
            self.geometry(f"{self.WIDTH}x{self.MAX_HEIGHT}+{x}+{y}")
        except Exception:
            self.geometry(f"{self.WIDTH}x{self.MAX_HEIGHT}+100+100")

    def _load_items(self):
        try:
            items = self._fetch_func()
            self._spinner_lbl.destroy()
            self._items = items
            self._render_items()
        except Exception as e:
            self._spinner_lbl.configure(text=f"{t('dispatch_board.load_error')}: {e}",
                                        text_color=Theme.DANGER)

    def _render_items(self):
        for widget in self._scroll_frame.winfo_children():
            widget.destroy()

        if not self._items:
            ctk.CTkLabel(self._scroll_frame, text=t("dispatch_board.no_options"),
                         fg_color=self.DROPDOWN_BG, text_color=Theme.MUTED,
                         font=FONTS["label"]).pack(pady=20)
            return

        for item in self._items:
            self._create_item_row(item)

    def _create_item_row(self, item):
        available = item.get("available", True)
        item_id = item.get("id")
        label = item.get("label", "")
        sublabel = item.get("sublabel", "")
        status_text = item.get("status_text", "")

        row = ctk.CTkFrame(self._scroll_frame, fg_color=self.ITEM_BG, cursor="hand2")
        row.pack(fill="x", pady=(0, 1))

        text_frame = ctk.CTkFrame(row, fg_color=self.ITEM_BG)
        text_frame.pack(side="left", fill="x", expand=True)

        fg_color = Theme.TEXT if available else self.ITEM_UNAVAILABLE_FG
        ctk.CTkLabel(text_frame, text=label, fg_color=self.ITEM_BG, text_color=fg_color,
                     font=FONTS["small"]).pack(anchor="w")

        if sublabel:
            ctk.CTkLabel(text_frame, text=sublabel, fg_color=self.ITEM_BG, text_color=Theme.MUTED,
                         font=FONTS["label"]).pack(anchor="w")

        if status_text and not available:
            ctk.CTkLabel(row, text=status_text, fg_color=self.ITEM_BG, text_color=Theme.WARNING,
                          font=FONTS["label"]).pack(side="right")

        if available:
            row.bind("<Enter>", lambda e, r=row: r.configure(fg_color=self.ITEM_BG_HOVER))
            row.bind("<Leave>", lambda e, r=row: r.configure(fg_color=self.ITEM_BG))
            row.bind("<Button-1>", lambda e, iid=item_id: self._select(iid))
            for child in row.winfo_children():
                child.bind("<Enter>", lambda e, r=row: r.configure(fg_color=self.ITEM_BG_HOVER))
                child.bind("<Leave>", lambda e, r=row: r.configure(fg_color=self.ITEM_BG))
                child.bind("<Button-1>", lambda e, iid=item_id: self._select(iid))
                for subchild in child.winfo_children():
                    subchild.bind("<Enter>", lambda e, r=row: r.configure(fg_color=self.ITEM_BG_HOVER))
                    subchild.bind("<Leave>", lambda e, r=row: r.configure(fg_color=self.ITEM_BG))
                    subchild.bind("<Button-1>", lambda e, iid=item_id: self._select(iid))

    def _select(self, item_id):
        if self._on_select:
            self._on_select(item_id)
        self._close()

    def _close(self):
        if self._on_close:
            self._on_close()
        self.destroy()
