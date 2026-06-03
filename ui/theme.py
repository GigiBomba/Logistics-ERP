# ── ui/theme.py ──────────────────────────────────────────────────

import customtkinter as ctk
from typing import Optional

# ─────────────────────────────────────────────────────────────────
# COLOR TOKENS
# Zinc/neutral palette. No blue or purple tint on background
# surfaces. Color appears ONLY on interactive elements as accent.
# ─────────────────────────────────────────────────────────────────
COLORS = {
    # Backgrounds — layered darkness, barely distinguishable
    "bg_base":        "#09090b",  # Root window — near-pure black
    "bg_surface":     "#111113",  # Cards, sidebar — barely lighter
    "bg_elevated":    "#1c1c1f",  # Hover rows, active nav, selected
    "bg_input":       "#18181b",  # Inputs, comboboxes, dropdowns

    # Borders — subtle, just defines edges
    "border":         "#27272a",  # Card outlines, dividers, input borders
    "border_hover":   "#3f3f46",  # Border on interactive hover
    "border_focus":   "#6366f1",  # Input focus ring ONLY

    # Accent — indigo, used sparingly
    "accent":         "#6366f1",  # Buttons, active state, key indicators
    "accent_hover":   "#4f46e5",  # Button hover
    "accent_dim":     "#1e1b4b",  # Subtle accent fill (badges only)
    "accent_text":    "#a5b4fc",  # Indigo text on dark surfaces

    # Semantic
    "success":        "#22c55e",
    "success_dim":    "#052e16",
    "warning":        "#f59e0b",
    "warning_dim":    "#341a00",
    "danger":         "#ef4444",
    "danger_dim":     "#3b0000",
    "info":           "#3b82f6",
    "info_dim":       "#0f1f4a",

    # Text hierarchy
    "text_primary":   "#fafafa",  # Main — near-pure white
    "text_secondary": "#a1a1aa",  # Labels, secondary info
    "text_muted":     "#52525b",  # Placeholders, captions, disabled
    "text_accent":    "#a5b4fc",  # Indigo-tinted interactive text
    "text_success":   "#4ade80",
    "text_warning":   "#fbbf24",
    "text_danger":    "#f87171",

    # Status chips
    "chip_planned":   "#1c1917",
    "chip_loading":   "#341a00",
    "chip_transit":   "#0f1f4a",
    "chip_delivered": "#052e16",
    "chip_cancelled": "#3b0000",
    "chip_idle":      "#27272a",
}

# ─────────────────────────────────────────────────────────────────
# TYPOGRAPHY — Segoe UI scale
# ─────────────────────────────────────────────────────────────────
FONTS = {
    "display":    ("Segoe UI", 28, "bold"),   # Page titles
    "h1":         ("Segoe UI", 20, "bold"),   # Section page titles
    "h2":         ("Segoe UI", 16, "bold"),   # Card titles, dialogs
    "h3":         ("Segoe UI", 13, "bold"),   # Sub-section titles
    "body":       ("Segoe UI", 13),           # All body text
    "body_bold":  ("Segoe UI", 13, "bold"),
    "small":      ("Segoe UI", 12),           # Secondary text
    "label":      ("Segoe UI", 11),           # Field labels (uppercase)
    "mono":       ("Consolas", 13),           # Numbers, IDs, dates
    "mono_lg":    ("Consolas", 20, "bold"),   # Large KPI values
    "mono_xl":    ("Consolas", 32, "bold"),   # Hero profit number
}

# ─────────────────────────────────────────────────────────────────
# SPACING — 8px grid
# Use S["N"] everywhere. Never hardcode spacing values.
# ─────────────────────────────────────────────────────────────────
S = {
    "1":  4,    # micro
    "2":  8,    # xs — between icon and text
    "3":  12,   # sm — between items in a group
    "4":  16,   # md — between form fields
    "5":  20,   # lg — card internal padding (sides)
    "6":  24,   # xl — card internal padding (top/bottom)
    "8":  32,   # 2xl — between major sections
    "10": 40,   # 3xl — view outer padding
    "12": 48,   # 4xl — section top margin
}

# ─────────────────────────────────────────────────────────────────
# DIMENSIONS
# ─────────────────────────────────────────────────────────────────
RADIUS_CARD   = 8
RADIUS_INPUT  = 6
RADIUS_BUTTON = 6
RADIUS_CHIP   = 4

MAX_FORM_WIDTH = 720  # Forms never wider than this — ever

# ─────────────────────────────────────────────────────────────────
# COMPONENT FACTORY FUNCTIONS
# Always use these instead of raw CTk constructors for consistency.
# ─────────────────────────────────────────────────────────────────

def card(parent, **frame_kwargs) -> ctk.CTkFrame:
    """
    Create a card with a subtle 1px border effect.
    Returns the INNER content frame — place all children inside this.
    Pack or grid the returned frame's ._outer attribute to position it.

    Usage:
        inner = card(parent)
        inner._outer.pack(fill="x", pady=(0, S["3"]))
        ctk.CTkLabel(inner, text="Hello").pack()
    """
    outer = ctk.CTkFrame(
        parent,
        fg_color=COLORS["border"],
        corner_radius=RADIUS_CARD + 1
    )
    inner = ctk.CTkFrame(
        outer,
        fg_color=COLORS["bg_surface"],
        corner_radius=RADIUS_CARD,
        **frame_kwargs
    )
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    inner._outer = outer
    return inner


def card_header(parent, title: str,
                subtitle: str = None) -> ctk.CTkFrame:
    """
    Add a section header + divider to a card's top.
    Call this as the FIRST thing inside a card's content area.
    Returns the header frame.
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=S["5"], pady=(S["6"], 0))

    ctk.CTkLabel(
        frame,
        text=title,
        font=FONTS["h3"],
        text_color=COLORS["text_primary"],
        anchor="w"
    ).pack(anchor="w")

    if subtitle:
        ctk.CTkLabel(
            frame,
            text=subtitle,
            font=FONTS["small"],
            text_color=COLORS["text_muted"],
            anchor="w"
        ).pack(anchor="w", pady=(S["1"], 0))

    # Divider
    ctk.CTkFrame(
        parent,
        fg_color=COLORS["border"],
        height=1,
        corner_radius=0
    ).pack(fill="x", pady=(S["4"], 0))

    return frame


def field(parent, label: str,
          var=None,
          kind: str = "entry",
          **widget_kwargs) -> ctk.CTkBaseClass:
    """
    Create a labeled input field (label above, input below).
    Returns the input widget.
    kind: "entry" | "combobox" | "textbox" | "spinbox"

    Usage:
        self.truck_entry = field(content, t("form.truck"), self.truck_var)
        self.status_box = field(content, t("form.status"),
                                self.status_var, "combobox",
                                values=["Planned","In Transit"])
    """
    wrapper = ctk.CTkFrame(parent, fg_color="transparent")
    wrapper.pack(fill="x", pady=(0, S["4"]))

    ctk.CTkLabel(
        wrapper,
        text=label.upper(),
        font=FONTS["label"],
        text_color=COLORS["text_muted"],
        anchor="w"
    ).pack(anchor="w", pady=(0, S["1"]))

    base = dict(
        fg_color=COLORS["bg_input"],
        border_color=COLORS["border"],
        border_width=1,
        text_color=COLORS["text_primary"],
        font=FONTS["body"],
        height=38,
        corner_radius=RADIUS_INPUT,
    )

    if kind == "entry":
        base["placeholder_text_color"] = COLORS["text_muted"]
        w = ctk.CTkEntry(wrapper, textvariable=var,
                         **{**base, **widget_kwargs})
    elif kind == "combobox":
        base.update(dict(
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["border_hover"],
            dropdown_fg_color=COLORS["bg_surface"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["bg_elevated"],
        ))
        w = ctk.CTkComboBox(wrapper, variable=var,
                            **{**base, **widget_kwargs})
    elif kind == "textbox":
        base.pop("height", None)
        base.pop("border_color", None)
        base.pop("border_width", None)
        h = widget_kwargs.pop("height", 90)
        w = ctk.CTkTextbox(wrapper, height=h,
                           **{**base, **widget_kwargs})
    else:
        w = ctk.CTkEntry(wrapper, textvariable=var,
                         **{**base, **widget_kwargs})

    w.pack(fill="x")
    return w


def two_col_row(parent) -> tuple:
    """
    Create a 2-column equal-width row frame.
    Returns (left_frame, right_frame).
    Place field() calls inside each frame.

    Usage:
        left, right = two_col_row(content)
        field(left,  t("form.start_date"), self.date_var)
        field(right, t("form.duration"),   self.days_var)
    """
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x")
    row.columnconfigure(0, weight=1, uniform="twocol")
    row.columnconfigure(1, weight=1, uniform="twocol")

    left = ctk.CTkFrame(row, fg_color="transparent")
    left.grid(row=0, column=0, sticky="ew",
              padx=(0, S["3"]))

    right = ctk.CTkFrame(row, fg_color="transparent")
    right.grid(row=0, column=1, sticky="ew")

    return left, right


def btn(parent, text: str,
        command=None,
        variant: str = "primary",
        **kwargs) -> ctk.CTkButton:
    """
    Create a styled button.
    variant: "primary" | "secondary" | "danger" | "ghost"
    """
    base = dict(
        font=FONTS["body_bold"],
        corner_radius=RADIUS_BUTTON,
        border_width=0,
        height=38,
        cursor="hand2",
        command=command,
    )
    styles = {
        "primary":   dict(fg_color=COLORS["accent"],
                          hover_color=COLORS["accent_hover"],
                          text_color="#ffffff"),
        "secondary": dict(fg_color="transparent",
                          hover_color=COLORS["bg_elevated"],
                          text_color=COLORS["text_secondary"],
                          border_width=1,
                          border_color=COLORS["border"]),
        "danger":    dict(fg_color=COLORS["danger"],
                          hover_color="#b91c1c",
                          text_color="#ffffff"),
        "ghost":     dict(fg_color="transparent",
                          hover_color=COLORS["bg_elevated"],
                          text_color=COLORS["text_muted"]),
    }
    return ctk.CTkButton(
        parent, text=text,
        **{**base, **styles.get(variant, styles["primary"]), **kwargs}
    )


def divider(parent) -> ctk.CTkFrame:
    """1px horizontal separator."""
    d = ctk.CTkFrame(parent, fg_color=COLORS["border"],
                     height=1, corner_radius=0)
    d.pack(fill="x")
    d.pack_propagate(False)
    return d


def kpi_card(parent, label: str, value: str,
             trend: str = None,
             value_color: str = None) -> ctk.CTkFrame:
    """
    KPI metric card. Returns the outer border frame.
    value_color: if None, uses text_primary.
    trend: e.g. "▲ 12%" or "▼ 3%"
    """
    outer = ctk.CTkFrame(parent, fg_color=COLORS["border"],
                         corner_radius=RADIUS_CARD + 1)
    inner = ctk.CTkFrame(outer, fg_color=COLORS["bg_surface"],
                         corner_radius=RADIUS_CARD)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    c = ctk.CTkFrame(inner, fg_color="transparent")
    c.pack(fill="both", expand=True, padx=S["5"], pady=S["5"])

    ctk.CTkLabel(c, text=label.upper(), font=FONTS["label"],
                 text_color=COLORS["text_muted"],
                 anchor="w").pack(anchor="w")
    ctk.CTkLabel(c, text=value, font=FONTS["mono_lg"],
                 text_color=value_color or COLORS["text_primary"],
                 anchor="w").pack(anchor="w", pady=(S["2"], 0))
    if trend:
        tc = (COLORS["text_success"] if trend.startswith("▲")
              else COLORS["text_danger"])
        ctk.CTkLabel(c, text=trend, font=FONTS["small"],
                     text_color=tc, anchor="w").pack(anchor="w")
    return outer


def page_heading(parent, title: str,
                 subtitle: str = None) -> ctk.CTkFrame:
    """
    Top-of-view page title block. Pack this as the first element
    in any view before the form container or content.
    """
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", padx=S["10"],
           pady=(S["10"], S["6"]))
    ctk.CTkLabel(f, text=title, font=FONTS["h1"],
                 text_color=COLORS["text_primary"],
                 anchor="w").pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(f, text=subtitle, font=FONTS["small"],
                     text_color=COLORS["text_muted"],
                     anchor="w").pack(anchor="w", pady=(S["1"], 0))
    return f


def scrollable_form_container(parent) -> ctk.CTkFrame:
    """
    Creates a scrollable area with MAX_FORM_WIDTH constraint.
    Returns the content frame — place cards/sections inside this.
    Forms never exceed MAX_FORM_WIDTH regardless of window size.
    """
    scroll = ctk.CTkScrollableFrame(
        parent,
        fg_color=COLORS["bg_base"],
        scrollbar_button_color=COLORS["border"],
        scrollbar_button_hover_color=COLORS["border_hover"],
    )
    scroll.pack(fill="both", expand=True)

    container = ctk.CTkFrame(scroll, fg_color="transparent",
                             width=MAX_FORM_WIDTH)
    container.pack(anchor="nw", padx=S["10"],
                   pady=(0, S["10"]))
    container.pack_propagate(False)
    return container


# ─────────────────────────────────────────────────────────────────
# BACKWARD COMPATIBILITY — chart constants & helpers
# Preserved so existing views continue to work.  These will be
# migrated to a dedicated chart module in a future refactor.
# ─────────────────────────────────────────────────────────────────

CHART_PRIMARY   = "#3730a3"
CHART_SECONDARY = "#4338ca"
CHART_INDIGO    = "#6366f1"
CHART_DIM       = "#1e1b4b"
CHART_MID       = "#312e81"
CHART_COLORS = [
    "#3730a3", "#4338ca", "#6366f1",
    "#4f46e5", "#1e1b4b", "#312e81",
]
CHART_PALETTE = CHART_COLORS

CHART_GREEN       = "#4ADE80"
CHART_GREEN_HOVER = "#22C55E"
CHART_GREEN_GLOW  = "#16A34A"
CHART_GREEN_DIM   = "#14532d"


def apply_chart_style(fig, ax=None) -> None:
    """Apply consistent indigo-on-black styling to a matplotlib figure/axes."""
    fig.patch.set_facecolor(COLORS["bg_base"])
    if ax is None:
        return
    ax.set_facecolor(COLORS["bg_base"])
    ax.tick_params(colors=COLORS["text_secondary"], labelsize=9)
    ax.xaxis.label.set_color(COLORS["text_secondary"])
    ax.yaxis.label.set_color(COLORS["text_secondary"])
    ax.title.set_color(COLORS["text_primary"])
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["border"])
