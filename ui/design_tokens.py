# ── ui/design_tokens.py ──────────────────────────────────────────
# Design tokens for Operion ERP visual identity.
# Canonical tokens follow the Linear / Stripe Dashboard / JetBrains
# dark-first design system.  Backward-compatible aliases are provided
# so existing view modules continue to work during migration.
# ─────────────────────────────────────────────────────────────────

# ═════════════════════════════════════════════════════════════════
#  CANONICAL TOKENS — use these for all new / refactored code
# ═════════════════════════════════════════════════════════════════

# === SURFACE COLORS ===
COLOR_BG_BASE       = "#0C0C0E"   # True near-black app background
COLOR_BG_ELEVATED   = "#141416"   # Card/panel background
COLOR_BG_OVERLAY    = "#1C1C1F"   # Input fields, dropdowns, table rows
COLOR_BG_HOVER      = "#222226"   # Hover state for interactive rows/items
COLOR_BG_SELECTED   = "#27272C"   # Selected row/item
COLOR_BG_CARD       = "#1A1A24"   # StatCard background
COLOR_BG_CARD_HOVER = "#1F1F2C"   # StatCard hover background

# === BORDER COLORS ===
COLOR_BORDER_SUBTLE = "#2A2A30"   # Default card/panel border (1px)
COLOR_BORDER_MEDIUM = "#38383F"   # Input/focused border
COLOR_BORDER_STRONG = "#505058"   # Emphasized separator

# === TEXT COLORS ===
COLOR_TEXT_PRIMARY   = "#F0F0F3"  # Main text, values, headings
COLOR_TEXT_SECONDARY = "#8E8EA0"  # Labels, captions, metadata
COLOR_TEXT_TERTIARY  = "#5A5A6E"  # Disabled text, placeholders
COLOR_TEXT_INVERSE   = "#0C0C0E"  # Text on colored buttons
COLOR_TEXT_WHITE     = "#FFFFFF"  # Pure white for high-contrast elements

# === ACCENT / BRAND ===
COLOR_ACCENT_PRIMARY   = "#6366F1"  # Primary actions (Indigo-500)
COLOR_ACCENT_HOVER     = "#5254CC"  # Primary button hover
COLOR_ACCENT_SUBTLE    = "#1E1F3D"  # Tinted background for accented sections
COLOR_ACCENT_BORDER    = "#3A3C7A"  # Subtle accent border

# === SEMANTIC COLORS ===
# Success / Delivered / Positive
COLOR_SUCCESS_DEFAULT = "#10B981"  # Emerald-500
COLOR_SUCCESS_SUBTLE  = "#0D2B20"  # Background tint
COLOR_SUCCESS_TEXT    = "#34D399"  # Text in success context

# Warning / Planned / In-Progress
COLOR_WARNING_DEFAULT = "#F59E0B"  # Amber-500
COLOR_WARNING_SUBTLE  = "#2B2010"
COLOR_WARNING_TEXT    = "#FCD34D"

# Error / Critical / Negative Profit
COLOR_ERROR_DEFAULT   = "#EF4444"  # Red-500
COLOR_ERROR_SUBTLE    = "#2B1010"
COLOR_ERROR_TEXT      = "#F87171"

# Neutral / Cancelled / Muted
COLOR_NEUTRAL_DEFAULT = "#6B7280"  # Gray-500
COLOR_NEUTRAL_SUBTLE  = "#1A1A20"
COLOR_NEUTRAL_TEXT    = "#9CA3AF"

# Info / Reference
COLOR_INFO_DEFAULT    = "#3B82F6"  # Blue-500
COLOR_INFO_SUBTLE     = "#0F1A2E"
COLOR_INFO_TEXT       = "#60A5FA"

# === DATA VISUALIZATION ===
COLOR_CHART_1 = "#6366F1"   # Primary series
COLOR_CHART_2 = "#10B981"   # Secondary series
COLOR_CHART_3 = "#F59E0B"   # Tertiary series
COLOR_CHART_4 = "#3B82F6"   # Quaternary series
COLOR_CHART_5 = "#EC4899"   # Quinary series
COLOR_CHART_GRID  = "#1E1E24"
COLOR_CHART_AXIS  = "#38383F"

# === TYPOGRAPHY ===
# Font sizes in px (use QFont with pixel size)
FONT_SIZE_XS   = 10  # Timestamps, metadata footnotes
FONT_SIZE_SM   = 11  # Table cell data, secondary labels
FONT_SIZE_BASE = 12  # Default body, form labels, most UI text
FONT_SIZE_MD   = 13  # Card values (secondary), navigation labels
FONT_SIZE_LG   = 16  # Card primary values
FONT_SIZE_XL   = 22  # KPI metric values (large)
FONT_SIZE_2XL  = 32  # Hero numbers (main dashboard KPIs)
FONT_SIZE_3XL  = 26  # StatCard value (between XL and 2XL)

# Font weights
FONT_WEIGHT_REGULAR  = 400
FONT_WEIGHT_MEDIUM   = 500
FONT_WEIGHT_SEMIBOLD = 600
FONT_WEIGHT_BOLD     = 700

# === SPACING ===
SPACE_1  = 4
SPACE_2  = 8
SPACE_3  = 12
SPACE_4  = 16
SPACE_5  = 20
SPACE_6  = 24
SPACE_8  = 32
SPACE_10 = 40
SPACE_12 = 48
SPACE_16 = 64

# === BORDER RADIUS ===
RADIUS_SM  = 4
RADIUS_MD  = 6
RADIUS_LG  = 8
RADIUS_XL  = 12
RADIUS_PILL = 100

# === STATUS BADGE MAP ===
# (label, text_color, bg_color)
STATUS_STYLES = {
    "delivered":   ("Livrat",      COLOR_SUCCESS_TEXT, COLOR_SUCCESS_SUBTLE),
    "planned":     ("Planificat",  COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SUBTLE),
    "in_progress": ("În curs",     COLOR_WARNING_TEXT, COLOR_WARNING_SUBTLE),
    "in_transit":  ("În curs",     COLOR_WARNING_TEXT, COLOR_WARNING_SUBTLE),
    "cancelled":   ("Anulat",      COLOR_NEUTRAL_TEXT, COLOR_NEUTRAL_SUBTLE),
    "overdue":     ("Restant",     COLOR_ERROR_TEXT, COLOR_ERROR_SUBTLE),
    "maintenance": ("Mentenanță",  COLOR_INFO_TEXT, COLOR_INFO_SUBTLE),
    "loading":     ("Se încarcă",  COLOR_TEXT_TERTIARY, COLOR_BG_OVERLAY),
    "invoiced":    ("Facturat",    COLOR_INFO_TEXT, COLOR_INFO_SUBTLE),
    "paid":        ("Plătit",      COLOR_SUCCESS_TEXT, COLOR_SUCCESS_SUBTLE),
}

# ═════════════════════════════════════════════════════════════════
#  BACKWARD-COMPATIBILITY ALIASES — existing modules rely on these
# ═════════════════════════════════════════════════════════════════

# Surfaces
BG_BASE     = COLOR_BG_BASE
BG_SURFACE  = COLOR_BG_ELEVATED
BG_ELEVATED = COLOR_BG_OVERLAY
BG_OVERLAY  = COLOR_BG_OVERLAY

# Borders
BORDER_FAINT   = COLOR_BORDER_SUBTLE
BORDER_DEFAULT = COLOR_BORDER_MEDIUM
BORDER_STRONG  = COLOR_BORDER_STRONG
BORDER_FOCUS   = COLOR_ACCENT_PRIMARY

# Accent
ACCENT       = COLOR_ACCENT_PRIMARY
ACCENT_HOVER = COLOR_ACCENT_HOVER
ACCENT_DIM   = COLOR_ACCENT_SUBTLE
ACCENT_TEXT  = "#818CF8"  # Closest indigo-400 for legacy usage

# Text
TEXT_PRIMARY   = COLOR_TEXT_PRIMARY
TEXT_SECONDARY = COLOR_TEXT_SECONDARY
TEXT_MUTED     = COLOR_TEXT_TERTIARY
TEXT_DISABLED  = "#3F3F46"
TEXT_WHITE     = COLOR_TEXT_WHITE

# Semantic
SUCCESS     = COLOR_SUCCESS_DEFAULT
SUCCESS_DIM = COLOR_SUCCESS_SUBTLE
SUCCESS_TEXT = COLOR_SUCCESS_TEXT
WARNING     = COLOR_WARNING_DEFAULT
WARNING_DIM = COLOR_WARNING_SUBTLE
WARNING_TEXT = COLOR_WARNING_TEXT
DANGER      = COLOR_ERROR_DEFAULT
DANGER_DIM  = COLOR_ERROR_SUBTLE
DANGER_TEXT = COLOR_ERROR_TEXT
INFO        = COLOR_INFO_DEFAULT
INFO_DIM    = COLOR_INFO_SUBTLE
INFO_TEXT   = COLOR_INFO_TEXT

# Status chips (legacy tuple order: background, text)
STATUS = {
    "planned":    (COLOR_NEUTRAL_SUBTLE, COLOR_NEUTRAL_TEXT),
    "loading":    (COLOR_WARNING_SUBTLE, COLOR_WARNING_TEXT),
    "in_transit": (COLOR_INFO_SUBTLE, COLOR_INFO_TEXT),
    "delivered":  (COLOR_SUCCESS_SUBTLE, COLOR_SUCCESS_TEXT),
    "cancelled":  (COLOR_NEUTRAL_SUBTLE, COLOR_NEUTRAL_TEXT),
    "invoiced":   (COLOR_ACCENT_SUBTLE, ACCENT_TEXT),
    "paid":       (COLOR_SUCCESS_SUBTLE, COLOR_SUCCESS_TEXT),
}

# Typography (legacy)
FONT_FAMILY = "Inter"
FONT_MONO   = "Consolas"

FONT_SIZES = {
    "display": FONT_SIZE_XL,
    "h1":      FONT_SIZE_LG,
    "h2":      FONT_SIZE_MD,
    "h3":      FONT_SIZE_BASE,
    "body":    FONT_SIZE_BASE,
    "small":   FONT_SIZE_SM,
    "label":   FONT_SIZE_SM,
    "mono":    FONT_SIZE_BASE,
    "mono_lg": FONT_SIZE_LG,
    "mono_xl": FONT_SIZE_2XL,
}

# Spacing (legacy dict)
SP = {
    "1": SPACE_1,
    "2": SPACE_2,
    "3": SPACE_3,
    "4": SPACE_4,
    "5": SPACE_5,
    "6": SPACE_6,
    "8": SPACE_8,
    "10": SPACE_10,
    "12": SPACE_12,
    "16": SPACE_16,
}

# Radii (legacy dict)
RADIUS = {
    "sm": RADIUS_SM,
    "md": RADIUS_MD,
    "lg": RADIUS_LG,
    "xl": RADIUS_XL,
}

# Dimensions
SIDEBAR_EXPANDED  = 200
SIDEBAR_COLLAPSED = 48
TOPBAR_HEIGHT     = 44
ROW_HEIGHT        = 38
INPUT_HEIGHT      = 32
BTN_HEIGHT        = 32
BTN_HEIGHT_SM     = 28
