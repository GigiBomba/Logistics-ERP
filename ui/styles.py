import tkinter as tk
from tkinter import ttk
from ui.theme import COLORS, FONTS, S


class Theme:
    BG = COLORS["bg_base"]
    SURFACE = COLORS["bg_surface"]
    SURFACE2 = COLORS["bg_elevated"]
    SURFACE3 = COLORS["bg_elevated"]
    INPUT_BG = COLORS["bg_input"]
    INPUT_HOVER = COLORS["bg_elevated"]
    TEXT = COLORS["text_primary"]
    MUTED = COLORS["text_secondary"]
    ACCENT = COLORS["accent"]
    ACCENT_HOVER = COLORS["accent_hover"]
    ACCENT_SUCCESS = COLORS["success"]
    HOVER = ACCENT_HOVER
    BORDER = COLORS["border"]
    BORDER_FOCUS = COLORS["border_focus"]
    DANGER = COLORS["danger"]
    WARNING = COLORS["warning"]
    SUCCESS = COLORS["success"]
    GREEN = COLORS["success"]
    BLUE = COLORS["info"]
    INFO = BLUE
    ORANGE = COLORS["warning"]
    YELLOW = COLORS["warning"]
    PURPLE_SOFT = COLORS["accent_dim"]
    EXCEL = COLORS["success"]

    CARD_BG = COLORS["bg_surface"]
    CARD_ACCENT = COLORS["accent"]
    GLOW = COLORS["accent"]

    FONT_MAIN = FONTS["body"]
    FONT_BOLD = FONTS["body_bold"]
    FONT_TITLE = FONTS["h1"]

    PAD_X = S["4"]
    PAD_Y = S["2"]

    ACCENT_PRIMARY = ACCENT
    ACCENT_SECONDARY = ACCENT_HOVER

    _applied = False

    @classmethod
    def apply(cls, root=None) -> None:
        """Apply the global dark theme to Tk and ttk widgets."""
        try:
            if root is None:
                root = tk._default_root
            if root is not None:
                root.configure(bg=cls.BG)
                cls._apply_option_database(root)

            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass

            style.configure(".", background=cls.BG, foreground=cls.TEXT, font=cls.FONT_MAIN)
            style.configure("TFrame", background=cls.BG)
            style.configure("Surface.TFrame", background=cls.SURFACE)
            style.configure("TLabel", background=cls.BG, foreground=cls.TEXT)
            style.configure("Muted.TLabel", background=cls.BG, foreground=cls.MUTED)
            style.configure("TButton", background=cls.SURFACE2, foreground=cls.TEXT, borderwidth=0, padding=(12, 7))
            style.map("TButton", background=[("active", cls.SURFACE3), ("pressed", cls.ACCENT)])

            style.configure(
                "TEntry",
                fieldbackground=cls.INPUT_BG,
                background=cls.INPUT_BG,
                foreground=cls.TEXT,
                insertcolor=cls.ACCENT,
                bordercolor=cls.BORDER,
                lightcolor=cls.BORDER,
                darkcolor=cls.BORDER,
                padding=6
            )
            style.map(
                "TEntry",
                fieldbackground=[("focus", cls.INPUT_BG), ("disabled", cls.SURFACE)],
                bordercolor=[("focus", cls.ACCENT)]
            )

            style.configure(
                "TCombobox",
                fieldbackground=cls.INPUT_BG,
                background=cls.INPUT_BG,
                foreground=cls.TEXT,
                arrowcolor=cls.TEXT,
                bordercolor=cls.BORDER,
                lightcolor=cls.BORDER,
                darkcolor=cls.BORDER,
                padding=6
            )
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", cls.INPUT_BG), ("focus", cls.INPUT_BG)],
                foreground=[("readonly", cls.TEXT), ("disabled", cls.MUTED)],
                background=[("active", cls.INPUT_HOVER), ("readonly", cls.INPUT_BG)],
                bordercolor=[("focus", cls.ACCENT)]
            )

            style.configure(
                "Treeview",
                background=cls.INPUT_BG,
                fieldbackground=cls.INPUT_BG,
                foreground=cls.TEXT,
                rowheight=34,
                bordercolor=cls.BORDER,
                borderwidth=0
            )
            style.map(
                "Treeview",
                background=[("selected", COLORS["accent_dim"])],
                foreground=[("selected", COLORS["text_primary"])]
            )
            style.configure(
                "Treeview.Heading",
                background=cls.SURFACE2,
                foreground=cls.TEXT,
                relief="flat",
                padding=(8, 7),
                font=cls.FONT_BOLD
            )
            style.map("Treeview.Heading", background=[("active", cls.SURFACE3)])

            style.configure("Vertical.TScrollbar", background=cls.SURFACE2, troughcolor=cls.BG, arrowcolor=cls.TEXT, bordercolor=cls.BORDER)
            style.configure("Horizontal.TScrollbar", background=cls.SURFACE2, troughcolor=cls.BG, arrowcolor=cls.TEXT, bordercolor=cls.BORDER)
            style.map("TScrollbar", background=[("active", cls.SURFACE3)])

            style.configure("TNotebook", background=cls.BG, borderwidth=0)
            style.configure("TNotebook.Tab", background=cls.SURFACE2, foreground=cls.MUTED, padding=(12, 7), borderwidth=0)
            style.map("TNotebook.Tab", background=[("selected", cls.ACCENT), ("active", cls.SURFACE3)], foreground=[("selected", cls.TEXT)])

            style.configure("TCheckbutton", background=cls.BG, foreground=cls.TEXT, indicatorcolor=cls.INPUT_BG, padding=4)
            style.map(
                "TCheckbutton",
                background=[("active", cls.BG)],
                foreground=[("active", cls.TEXT)],
                indicatorcolor=[("selected", cls.ACCENT), ("active", cls.SURFACE3)]
            )
            style.configure("TRadiobutton", background=cls.BG, foreground=cls.TEXT, indicatorcolor=cls.INPUT_BG, padding=4)
            style.map("TRadiobutton", indicatorcolor=[("selected", cls.ACCENT), ("active", cls.SURFACE3)])

            cls._applied = True
        except Exception:
            # Styling must never stop business workflows from opening.
            pass

    @classmethod
    def _apply_option_database(cls, root) -> None:
        options = {
            "*Background": cls.BG,
            "*Foreground": cls.TEXT,
            "*activeBackground": cls.SURFACE3,
            "*activeForeground": cls.TEXT,
            "*selectBackground": cls.ACCENT,
            "*selectForeground": cls.TEXT,
            "*insertBackground": cls.ACCENT,
            "*highlightBackground": cls.BORDER,
            "*highlightColor": cls.ACCENT,
            "*Entry.Background": cls.INPUT_BG,
            "*Entry.Foreground": cls.TEXT,
            "*Text.Background": cls.INPUT_BG,
            "*Text.Foreground": cls.TEXT,
            "*Listbox.Background": cls.INPUT_BG,
            "*Listbox.Foreground": cls.TEXT,
            "*Listbox.selectBackground": cls.ACCENT,
            "*Listbox.selectForeground": cls.TEXT,
            "*Checkbutton.Background": cls.BG,
            "*Checkbutton.Foreground": cls.TEXT,
            "*Checkbutton.activeBackground": cls.BG,
            "*Checkbutton.activeForeground": cls.TEXT,
            "*Checkbutton.selectColor": cls.ACCENT,
            "*Radiobutton.Background": cls.BG,
            "*Radiobutton.Foreground": cls.TEXT,
            "*Radiobutton.activeBackground": cls.BG,
            "*Radiobutton.activeForeground": cls.TEXT,
            "*Radiobutton.selectColor": cls.ACCENT,
            "*Menu.Background": cls.SURFACE2,
            "*Menu.Foreground": cls.TEXT,
            "*Menu.activeBackground": cls.ACCENT,
            "*Menu.activeForeground": cls.TEXT,
            "*TCombobox*Listbox.background": cls.INPUT_BG,
            "*TCombobox*Listbox.foreground": cls.TEXT,
            "*TCombobox*Listbox.selectBackground": cls.ACCENT,
            "*TCombobox*Listbox.selectForeground": cls.TEXT,
        }
        for key, value in options.items():
            root.option_add(key, value)

    @classmethod
    def style_option_menu(cls, widget) -> None:
        widget.configure(
            bg=cls.INPUT_BG,
            fg=cls.TEXT,
            activebackground=cls.INPUT_HOVER,
            activeforeground=cls.TEXT,
            highlightthickness=1,
            highlightbackground=cls.BORDER,
            relief="flat",
            bd=0,
            font=cls.FONT_MAIN
        )
        try:
            widget["menu"].configure(
                bg=cls.SURFACE2,
                fg=cls.TEXT,
                activebackground=cls.ACCENT,
                activeforeground=cls.TEXT,
                bd=0
            )
        except Exception:
            pass
