# ── ui/theme.py ──────────────────────────────────────────────────
# BACKWARD-COMPATIBILITY SHIM — do not import in new code.
# Use ``ui.design_tokens`` directly for all new / refactored code.
# ─────────────────────────────────────────────────────────────────

from __future__ import annotations

from ui.design_tokens import (
    # Surface colors
    COLOR_BG_BASE as BG_BASE,
    COLOR_BG_ELEVATED as BG_SURFACE,
    COLOR_BG_OVERLAY as BG_ELEVATED,
    COLOR_BG_HOVER as BG_HOVER,
    COLOR_BG_SELECTED as BG_SELECTED,
    COLOR_BG_CARD as BG_CARD,
    COLOR_BG_ELEVATED as _BG_BASE_ALIAS,

    # Border colors
    COLOR_BORDER_SUBTLE as BORDER_FAINT,
    COLOR_BORDER_MEDIUM as BORDER_DEFAULT,
    COLOR_BORDER_STRONG as BORDER_STRONG,
    COLOR_ACCENT_PRIMARY as BORDER_FOCUS,

    # Accent
    COLOR_ACCENT_PRIMARY as ACCENT,
    COLOR_ACCENT_HOVER as ACCENT_HOVER,
    COLOR_ACCENT_SUBTLE as ACCENT_DIM,
    COLOR_ACCENT_PRIMARY as _ACCENT_ALIAS,

    # Text colors
    COLOR_TEXT_PRIMARY as TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY as TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY as TEXT_MUTED,
    COLOR_TEXT_WHITE as TEXT_WHITE,

    # Semantic
    COLOR_SUCCESS_DEFAULT as SUCCESS,
    COLOR_SUCCESS_SUBTLE as SUCCESS_DIM,
    COLOR_SUCCESS_TEXT as SUCCESS_TEXT,
    COLOR_WARNING_DEFAULT as WARNING,
    COLOR_WARNING_SUBTLE as WARNING_DIM,
    COLOR_WARNING_TEXT as WARNING_TEXT,
    COLOR_ERROR_DEFAULT as DANGER,
    COLOR_ERROR_SUBTLE as DANGER_DIM,
    COLOR_ERROR_TEXT as DANGER_TEXT,
    COLOR_INFO_DEFAULT as INFO,
    COLOR_INFO_SUBTLE as INFO_DIM,
    COLOR_INFO_TEXT as INFO_TEXT,

    # Spacing
    SP,
    SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5,
    SPACE_6, SPACE_8, SPACE_10, SPACE_12, SPACE_16,

    # Radius
    RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_XL, RADIUS_PILL,

    # Typography
    FONT_FAMILY, FONT_MONO,
    FONT_SIZE_XS, FONT_SIZE_SM, FONT_SIZE_BASE, FONT_SIZE_MD,
    FONT_SIZE_LG, FONT_SIZE_XL, FONT_SIZE_2XL,

    # Font weights
    FONT_WEIGHT_REGULAR, FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD, FONT_WEIGHT_BOLD,

    # Dimensions
    SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED, TOPBAR_HEIGHT,
    ROW_HEIGHT, INPUT_HEIGHT, BTN_HEIGHT, BTN_HEIGHT_SM,

    # Status
    STATUS_STYLES, STATUS,

    # Chart
    COLOR_CHART_1, COLOR_CHART_2, COLOR_CHART_3,
    COLOR_CHART_4, COLOR_CHART_5, COLOR_CHART_GRID, COLOR_CHART_AXIS,

    # Legacy aliases
    TEXT_DISABLED,
    ACCENT_TEXT,
)

# ── Legacy COLORS dict (preserved for existing ui.theme imports) ──
COLORS = {
    "bg_base":          BG_BASE,
    "bg_surface":       BG_SURFACE,
    "bg_elevated":      BG_ELEVATED,
    "bg_input":         BG_ELEVATED,
    "bg_card":          BG_CARD,
    "bg_hover":         BG_HOVER,
    "bg_disabled":      "#18181b",

    "border":           BORDER_DEFAULT,
    "border_hover":     BORDER_STRONG,
    "border_focus":     BORDER_FOCUS,

    "accent":           ACCENT,
    "accent_hover":     ACCENT_HOVER,
    "accent_dim":       ACCENT_DIM,
    "accent_text":      ACCENT_TEXT,

    "success":          SUCCESS,
    "success_dim":      SUCCESS_DIM,
    "warning":          WARNING,
    "warning_dim":      WARNING_DIM,
    "danger":           DANGER,
    "danger_dim":       DANGER_DIM,
    "info":             INFO,
    "info_dim":         INFO_DIM,

    "text_primary":     TEXT_PRIMARY,
    "text_secondary":   TEXT_SECONDARY,
    "text_muted":       TEXT_MUTED,
    "text_accent":      ACCENT_TEXT,
    "text_success":     SUCCESS_TEXT,
    "text_warning":     WARNING_TEXT,
    "text_danger":      DANGER_TEXT,

    "chip_planned":     "#1c1917",
    "chip_loading":     "#341a00",
    "chip_transit":     "#0f1f4a",
    "chip_delivered":   "#052e16",
    "chip_cancelled":        "#1A1A20",
    "chip_cancelled_text":   "#9CA3AF",
    "chip_idle":             "#27272a",
}

# ── Legacy S dict (preserved for backward compat) ──
S = {
    "1":  SPACE_1,
    "2":  SPACE_2,
    "3":  SPACE_3,
    "4":  SPACE_4,
    "5":  SPACE_5,
    "6":  SPACE_6,
    "8":  SPACE_8,
    "10": SPACE_10,
    "12": SPACE_12,
}

MAX_FORM_WIDTH = 720

RADIUS_CARD   = RADIUS_LG
RADIUS_INPUT  = RADIUS_MD
RADIUS_BUTTON = RADIUS_MD
RADIUS_CHIP   = RADIUS_SM

CHART_PRIMARY   = COLOR_CHART_1
CHART_SECONDARY = COLOR_CHART_2
CHART_ACCENT    = COLOR_CHART_1

# Legacy FONTS dict — populated from design_tokens
import ui.design_tokens as _dt
FONTS = {
    k: (_dt.FONT_SIZES[k], _dt.FONT_WEIGHT_REGULAR)
    for k in ("display", "h1", "h2", "h3", "body", "small", "label")
}
FONTS["body_bold"] = (FONTS["body"][0], _dt.FONT_WEIGHT_BOLD)
FONTS["mono"] = (_dt.FONT_SIZES.get("mono", _dt.FONT_SIZE_BASE), _dt.FONT_WEIGHT_REGULAR)
FONTS["mono_lg"] = (_dt.FONT_SIZES.get("mono_lg", _dt.FONT_SIZE_LG), _dt.FONT_WEIGHT_REGULAR)
FONTS["mono_xl"] = (_dt.FONT_SIZES.get("mono_xl", _dt.FONT_SIZE_2XL), _dt.FONT_WEIGHT_REGULAR)
