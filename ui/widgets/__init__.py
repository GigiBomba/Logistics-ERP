import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from ui.styles import Theme
from ui.theme import COLORS, FONTS, RADIUS_CARD, S


# --- Monkey-patch CTk widgets for backward compat with tkinter .config() ---
def _patched_config(self, **kwargs):
    if "fg" in kwargs:
        kwargs["text_color"] = kwargs.pop("fg")
    if "bg" in kwargs:
        kwargs["fg_color"] = kwargs.pop("bg")
    return self.configure(**kwargs)
ctk.CTkBaseClass.config = _patched_config

_UNSUPPORTED_KWARGS = frozenset({
    "bg", "fg", "activebackground", "activeforeground", "selectcolor",
    "relief", "bd", "highlightthickness", "highlightbackground", "highlightcolor",
    "disabledbackground", "disabledforeground", "insertbackground",
    "padx", "pady",
})


def _strip_unsupported(kwargs):
    for k in list(kwargs):
        if k in _UNSUPPORTED_KWARGS:
            kwargs.pop(k)


class StyledEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        _strip_unsupported(kwargs)
        kwargs.setdefault("fg_color", COLORS.get("input_bg", COLORS.get("bg_input")))
        kwargs.setdefault("text_color", COLORS["text_primary"])
        kwargs.setdefault("border_color", COLORS["border"])
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("corner_radius", RADIUS_CARD)
        kwargs.setdefault("font", FONTS["body"])
        super().__init__(master, **kwargs)


class StyledText(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        _strip_unsupported(kwargs)
        kwargs.setdefault("fg_color", COLORS["input_bg"])
        kwargs.setdefault("text_color", COLORS["text_primary"])
        kwargs.setdefault("border_color", COLORS["border"])
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("corner_radius", RADIUS_CARD)
        kwargs.setdefault("font", FONTS["body"])
        super().__init__(master, **kwargs)


class ActionButton(ctk.CTkButton):
    def __init__(self, master, text, command, color=None, hover_color=None, width=None, **kwargs):
        _strip_unsupported(kwargs)
        fg = None
        hover = None
        if color:
            fg = color
            hover = COLORS["accent_hover"] if color == COLORS["accent"] else COLORS["bg_elevated"]
        if hover_color:
            hover = hover_color
        kwargs.setdefault("font", FONTS["body_bold"])
        if width is not None:
            kwargs["width"] = width
        if fg:
            kwargs["fg_color"] = fg
        if hover:
            kwargs["hover_color"] = hover
        super().__init__(master, text=text, command=command, **kwargs)


class StyledCheckbutton(ctk.CTkCheckBox):
    def __init__(self, master, **kwargs):
        variable = kwargs.pop("variable", None)
        onvalue = kwargs.pop("onvalue", None)
        offvalue = kwargs.pop("offvalue", None)
        _strip_unsupported(kwargs)
        kwargs.setdefault("font", FONTS["body"])
        super().__init__(master, **kwargs)
        if variable is not None:
            self.configure(variable=variable)
            if onvalue is not None:
                self.configure(onvalue=onvalue)
            if offvalue is not None:
                self.configure(offvalue=offvalue)


class StyledRadioButton(ctk.CTkRadioButton):
    def __init__(self, master, **kwargs):
        _strip_unsupported(kwargs)
        kwargs.setdefault("font", FONTS["body"])
        super().__init__(master, **kwargs)


def style_option_menu(widget) -> None:
    Theme.style_option_menu(widget)


def themed_combobox(master, **kwargs):
    return ctk.CTkComboBox(master, **kwargs)


def section_header(parent, text, _return=False):
    container = ctk.CTkFrame(parent, fg_color=COLORS["bg_base"])
    container.pack(fill="x", pady=(S["5"], S["4"]))
    lbl = ctk.CTkLabel(container, text=text, text_color=COLORS["accent"], font=FONTS["body_bold"])
    lbl.pack(side="left")
    line = ctk.CTkFrame(container, fg_color=COLORS["border"], height=1)
    line.pack(side="left", fill="x", expand=True, padx=S["4"])
    if _return:
        return lbl


def kpi_card(parent, title, value):
    c = ctk.CTkFrame(parent, fg_color=COLORS["bg_surface"], corner_radius=RADIUS_CARD)
    c.pack(side="left", padx=S["2"], fill="y")
    title_lbl = ctk.CTkLabel(c, text=title, text_color=COLORS["text_secondary"], font=FONTS["body"])
    title_lbl.pack(anchor="w", padx=S["4"], pady=(S["2"], 0))
    val_lbl = ctk.CTkLabel(c, text=value, text_color=COLORS["text_primary"], font=FONTS["body_bold"])
    val_lbl.pack(anchor="w", padx=S["4"], pady=(0, S["2"]))
    return val_lbl, title_lbl
