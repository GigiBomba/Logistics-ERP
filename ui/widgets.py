import tkinter as tk
from tkinter import ttk
from ui.styles import Theme


class StyledEntry(tk.Entry):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            bg=Theme.INPUT_BG,
            fg=Theme.TEXT,
            insertbackground=Theme.ACCENT,
            disabledbackground=Theme.SURFACE,
            disabledforeground=Theme.MUTED,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
            font=Theme.FONT_MAIN,
            **kwargs
        )


class StyledText(tk.Text):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            bg=Theme.INPUT_BG,
            fg=Theme.TEXT,
            insertbackground=Theme.ACCENT,
            selectbackground=Theme.ACCENT,
            selectforeground=Theme.TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
            font=Theme.FONT_MAIN,
            **kwargs
        )


class StyledCheckbutton(tk.Checkbutton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("bg", Theme.BG)
        kwargs.setdefault("fg", Theme.TEXT)
        kwargs.setdefault("activebackground", Theme.BG)
        kwargs.setdefault("activeforeground", Theme.TEXT)
        kwargs.setdefault("selectcolor", Theme.ACCENT)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("font", Theme.FONT_MAIN)
        kwargs.setdefault("cursor", "hand2")
        super().__init__(master, **kwargs)


class StyledRadioButton(tk.Radiobutton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("bg", Theme.BG)
        kwargs.setdefault("fg", Theme.TEXT)
        kwargs.setdefault("activebackground", Theme.BG)
        kwargs.setdefault("activeforeground", Theme.TEXT)
        kwargs.setdefault("selectcolor", Theme.ACCENT)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("font", Theme.FONT_MAIN)
        kwargs.setdefault("cursor", "hand2")
        super().__init__(master, **kwargs)


class ActionButton(tk.Button):
    def __init__(self, master, text, command, color=Theme.ACCENT, hover_color=None, **kwargs):
        self._base_color = color
        self._hover_color = hover_color or (Theme.ACCENT_HOVER if color == Theme.ACCENT else Theme.SURFACE3)
        super().__init__(
            master,
            text=text,
            command=command,
            bg=color,
            fg=Theme.TEXT,
            activebackground=self._hover_color,
            activeforeground=Theme.TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=Theme.FONT_BOLD,
            padx=Theme.PAD_X,
            pady=Theme.PAD_Y,
            **kwargs
        )
        self.bind("<Enter>", lambda _e: self.configure(bg=self._hover_color))
        self.bind("<Leave>", lambda _e: self.configure(bg=self._base_color))


def style_option_menu(widget) -> None:
    Theme.style_option_menu(widget)


def themed_combobox(master, **kwargs):
    Theme.apply(master.winfo_toplevel())
    return ttk.Combobox(master, **kwargs)


def section_header(parent, text, _return=False):
    container = tk.Frame(parent, bg=Theme.BG)
    container.pack(fill="x", pady=(16, 8))
    lbl = tk.Label(container, text=text, bg=Theme.BG, fg=Theme.ACCENT, font=Theme.FONT_BOLD)
    lbl.pack(side="left")
    tk.Frame(container, bg=Theme.BORDER, height=1).pack(side="left", fill="x", expand=True, padx=10)
    if _return:
        return lbl
