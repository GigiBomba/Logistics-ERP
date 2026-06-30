# ── ui/theme.py ──────────────────────────────────────────────────

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
    "chip_cancelled":       "#1A1A20",
    "chip_cancelled_text":  "#9CA3AF",
    "chip_idle":            "#27272a",
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
# BACKWARD COMPATIBILITY — chart colour aliases
# Preserved because ``ui.views.dashboard`` still references them.
# ─────────────────────────────────────────────────────────────────

CHART_PRIMARY   = "#3730a3"
CHART_SECONDARY = "#4338ca"
