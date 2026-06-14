# ── ui/design_tokens.py ──────────────────────────────────────────
# Design tokens for Operion ERP visual identity.
# Do NOT modify values here — they are the canonical design system.
# ─────────────────────────────────────────────────────────────────

# ── SURFACES ─────────────────────────────────────────────────────
# Three levels of elevation via color, not shadow.
BG_BASE       = "#09090b"   # Root window, page backgrounds
BG_SURFACE    = "#111113"   # Cards, sidebar, panels
BG_ELEVATED   = "#18181b"   # Hover states, selected rows, inputs
BG_OVERLAY    = "#1c1c1f"   # Tooltips, dropdowns, modals

# ── BORDERS ──────────────────────────────────────────────────────
BORDER_FAINT  = "#1c1c1f"   # Hairline dividers, table gridlines
BORDER_DEFAULT= "#27272a"   # Card outlines, input borders
BORDER_STRONG = "#3f3f46"   # Hover borders, focus-adjacent
BORDER_FOCUS  = "#6366f1"   # Focused input ring only

# ── ACCENT (ONE color — use sparingly) ───────────────────────────
ACCENT        = "#6366f1"   # Primary CTA, active nav, progress
ACCENT_HOVER  = "#4f46e5"   # Button hover
ACCENT_DIM    = "#1e1b4b"   # Badge backgrounds, subtle fills
ACCENT_TEXT   = "#a5b4fc"   # Accent text on dark surfaces

# ── TEXT ─────────────────────────────────────────────────────────
TEXT_PRIMARY  = "#fafafa"   # Headings, values, important labels
TEXT_SECONDARY= "#a1a1aa"   # Body text, secondary labels
TEXT_MUTED    = "#52525b"   # Captions, disabled, placeholders
TEXT_DISABLED = "#3f3f46"   # Truly disabled content

# ── SEMANTIC ─────────────────────────────────────────────────────
SUCCESS       = "#22c55e"
SUCCESS_DIM   = "#052e16"
SUCCESS_TEXT  = "#4ade80"
WARNING       = "#f59e0b"
WARNING_DIM   = "#341a00"
WARNING_TEXT  = "#fbbf24"
DANGER        = "#ef4444"
DANGER_DIM    = "#3b0000"
DANGER_TEXT   = "#f87171"
INFO          = "#3b82f6"
INFO_DIM      = "#0f1f4a"
INFO_TEXT     = "#93c5fd"

# ── STATUS CHIPS ─────────────────────────────────────────────────
STATUS = {
    "planned":    ("#1c1917", "#a8a29e"),
    "loading":    ("#341a00", "#fbbf24"),
    "in_transit": ("#0f1f4a", "#93c5fd"),
    "delivered":  ("#052e16", "#4ade80"),
    "cancelled":  ("#3b0000", "#f87171"),
    "invoiced":   ("#1e1b4b", "#a5b4fc"),
    "paid":       ("#052e16", "#4ade80"),
}  # (background, text)

# ── TYPOGRAPHY ───────────────────────────────────────────────────
FONT_FAMILY   = "Segoe UI"
FONT_MONO     = "Consolas"

FONT_SIZES = {
    "display": 22,   # Page titles (one per view)
    "h1":      18,   # Section headings within a page
    "h2":      15,   # Card titles, dialog headings
    "h3":      13,   # Sub-section labels, group labels
    "body":    13,   # All body text, table rows
    "small":   12,   # Secondary text, captions
    "label":   11,   # Field labels, column headers (ALL CAPS)
    "mono":    13,   # Numbers, IDs, codes (Consolas)
    "mono_lg": 20,   # KPI values (Consolas)
    "mono_xl": 28,   # Hero profit number (Consolas)
}

# ── SPACING (8px grid) ────────────────────────────────────────────
# Use these everywhere. Never hardcode spacing values.
SP = {
    "1": 4,    # micro gap (icon↔text)
    "2": 8,    # tight (between items in same group)
    "3": 12,   # comfortable (between field rows inside a card)
    "4": 16,   # card internal horizontal padding
    "5": 20,   # card internal vertical padding (top/bottom)
    "6": 24,   # between cards
    "8": 32,   # between major sections
    "10": 40,  # view outer margins
}

# ── RADII ─────────────────────────────────────────────────────────
RADIUS = {
    "sm":  4,    # chips, tags, small elements
    "md":  6,    # buttons, inputs
    "lg":  8,    # cards, panels
    "xl":  12,   # dialogs, large cards
}

# ── DIMENSIONS ────────────────────────────────────────────────────
SIDEBAR_EXPANDED  = 220
SIDEBAR_COLLAPSED = 52
TOPBAR_HEIGHT     = 44
ROW_HEIGHT        = 36    # All table rows
INPUT_HEIGHT      = 36    # All input fields
BTN_HEIGHT        = 34    # All buttons
BTN_HEIGHT_SM     = 28    # Small/icon buttons
