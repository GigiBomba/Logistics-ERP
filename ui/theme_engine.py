"""PySide6 theme engine for Operion ERP.

This module bridges the existing design tokens in ``ui.theme`` (COLORS, S, radii)
with Qt Style Sheets (QSS). It intentionally does *not* import ``FONTS`` from
``ui.theme`` because the visual revamp changes the typeface:

- IBM Plex Sans  -> functional data, navigation, tables, labels, body text
- Impact         -> high-level, single-word dashboard metrics
- IBM Plex Mono  -> numbers, IDs, dates (monospace data)

All styling is applied globally via ``QApplication.setStyleSheet()`` so individual
widgets do not need inline stylesheets.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from ui.design_tokens import (
    ACCENT_TEXT,
    BTN_HEIGHT,
    COLOR_ACCENT_BORDER,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_BASE,
    COLOR_BG_CARD,
    COLOR_BG_CARD_HOVER,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BG_SELECTED,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_STRONG,
    COLOR_BORDER_SUBTLE,
    ELEVATION_FLAT,
    ELEVATION_RAISED,
    ELEVATION_OVERLAY,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_INFO_DEFAULT,
    COLOR_INFO_SUBTLE,
    COLOR_INFO_TEXT,
    COLOR_NEUTRAL_DEFAULT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_INVERSE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    TEXT_WHITE,
    HOVER_MS,
    RADIUS_SM as RADIUS_CHIP,
    RADIUS_MD as RADIUS_INPUT,
    RADIUS_LG as RADIUS_CARD,
    RADIUS_MD as RADIUS_BUTTON,
    RADIUS_PILL,
    SPACE_2 as _P2,
    SPACE_4 as _P4,
    FONT_SIZE_2XL,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
    FONT_SIZE_XS,
    INPUT_HEIGHT,
    SPACE_1,
)

# ──────────────────────────────────────────────────────────────────────────────
# TYPOGRAPHY
# ──────────────────────────────────────────────────────────────────────────────

FONT_FAMILIES = {
    "sans": "'IBM Plex Sans', 'Segoe UI', 'Microsoft YaHei', sans-serif",
    "hero": "'Impact', 'Arial Black', 'Helvetica Neue', sans-serif",
    "mono": "'IBM Plex Mono', 'Courier New', monospace",
}

# Single ladder of truth: every size is a reference to the canonical
# ``ui.design_tokens.FONT_SIZE_*`` constants (no literal px values here).
FONT_SIZES = {
    "display": FONT_SIZE_2XL,  # 32
    "h1": FONT_SIZE_XL,        # 22
    "h2": FONT_SIZE_LG,        # 16
    "h3": FONT_SIZE_MD,        # 13
    "body": FONT_SIZE_MD,      # 13
    "body_bold": FONT_SIZE_MD,  # 13
    "small": FONT_SIZE_BASE,   # 12
    "label": FONT_SIZE_SM,     # 11
    "mono": FONT_SIZE_MD,      # 13
    "mono_lg": FONT_SIZE_XL,   # 22
    "mono_xl": FONT_SIZE_2XL,  # 32
}

# ──────────────────────────────────────────────────────────────────────────────
# QSS GENERATOR
# ──────────────────────────────────────────────────────────────────────────────


class QtTheme:
    """Global QSS theme manager."""

    _style_sheet: str | None = None

    @classmethod
    def apply(cls, app: QApplication) -> None:
        """Apply the global dark theme to a QApplication instance."""
        app.setStyleSheet(cls.qss())

        # Check font availability to avoid Qt font substitution warnings
        families = QFontDatabase.families()
        preferred = "IBM Plex Sans"
        fallback = "Segoe UI"
        family = preferred if preferred in families else fallback
        font = QFont(family, FONT_SIZES["body"])
        if font.pointSize() <= 0:
            font.setPointSize(13)
        app.setFont(font)

    @classmethod
    def qss(cls) -> str:
        """Return the complete global stylesheet."""
        if cls._style_sheet is None:
            cls._style_sheet = cls._build_qss()
        return cls._style_sheet

    @classmethod
    def refresh(cls, app: QApplication) -> None:
        """Rebuild and re-apply the stylesheet (useful after COLORS change)."""
        cls._style_sheet = None
        cls.apply(app)

    @classmethod
    def _build_qss(cls) -> str:
        return "\n\n".join(
            [
                cls._base_qss(),
                cls._typography_qss(),
                cls._button_qss(),
                cls._input_qss(),
                cls._checkbox_qss(),
                cls._radiobutton_qss(),
                cls._combobox_qss(),
                cls._spinbox_qss(),
                cls._table_qss(),
                cls._tree_qss(),
                cls._scrollarea_qss(),
                cls._scrollbar_qss(),
                cls._tabwidget_qss(),
                cls._progressbar_qss(),
                cls._groupbox_qss(),
                cls._frame_qss(),
                cls._menu_qss(),
                cls._tooltip_qss(),
                cls._dialog_qss(),
                cls._splitter_qss(),
                cls._nav_qss(),
                cls._topbar_qss(),
                cls._stackedwidget_qss(),
                cls._calendar_qss(),
                cls._toast_qss(),
                cls._stat_card_qss(),
                cls._filter_qss(),
                cls._section_header_qss(),
                cls._tab_button_qss(),
                cls._kanban_qss(),
                cls._freight_exchange_qss(),
                cls._cmr_qss(),
                cls._analytics_qss(),
                cls._dialogs_qss(),
            ]
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @classmethod
    def _ff(cls, role: str) -> str:
        return FONT_FAMILIES.get(role, FONT_FAMILIES.get("sans", "Segoe UI"))

    @classmethod
    def _fs(cls, role: str) -> int:
        return max(1, FONT_SIZES.get(role, FONT_SIZES.get("body", 13)))

    @classmethod
    def _px(cls, key: str) -> int:
        sizes = {"2": 8, "4": 16, "5": 20, "6": 24, "8": 32, "10": 40, "12": 48, "16": 64}
        return sizes.get(key, 8)

    # ── QSS ROLE CATALOG ────────────────────────────────────────────────────
    # The attribute selectors used across the QSS below are the widget-styling
    # vocabulary.  Keep every new selector inside this grammar:
    #
    # Attribute vocabulary
    #   * ``fontRole``            - hyphenated size-weight-color grammar, e.g.
    #                               ``sm-bold-error`` (11px / bold / error
    #                               text).  Values are STRICTLY REUSED from the
    #                               catalog below — never introduce a synonym
    #                               for an existing value.
    #                               ``fontRole`` is QLabel-PRIMARY: every
    #                               ``[fontRole=...]`` selector is ``QLabel``-
    #                               scoped.  Other widget classes (QCheckBox,
    #                               QPushButton, ...) must OPT IN with their
    #                               own scoped rule before a ``fontRole``
    #                               property has any effect on them.
    #                               ``fontRole`` = pure font properties on the
    #                               FONT_SIZES ladder (size/weight/color/
    #                               family/style).  ``QLabel[role=...]`` =
    #                               labels with off-ladder sizes, letter-
    #                               spacing, padding or surface roles;
    #                               ``role`` + ``state`` = STATEFUL variants.
    #                               NEVER mint fontRole values for state-
    #                               dependent colors (they would multiply
    #                               values per label kind).
    #   * ``role`` / ``variant``  - generic component roles / button variants
    #                               ("panel-elevated", "danger-panel",
    #                               "dialog-primary", ...).
    #   * ``*Role`` suffix        - enum-valued attributes (``sizeRole``,
    #                               ``tabRole``).
    #   * NEVER use built-in QWidget property names as QSS attributes.  The
    #     ``size`` collision (QWidget.size() is a real property, so a dynamic
    #     ``setProperty("size", ...)`` never survives) is the canonical
    #     counter-example.  Denylist: size, width, height, pos, geometry,
    #     visible, enabled, font, cursor, minimumWidth, minimumHeight,
    #     maximumWidth, maximumHeight, fixedWidth, fixedHeight, objectName.
    #
    # Ordering hazards
    #   * Qt resolves equal-specificity rules by source order, so ordering can
    #     be load-bearing.  Example: the ``base-surface`` dialog ``role``
    #     override MUST stay AFTER the modal-dialog rule (``QDialog`` + the
    #     ``modal`` attribute) — both are single-attribute selectors, so the
    #     base-surface override only wins because it appears later in the
    #     sheet.
    #   * Qt negation selectors: ``:!checked`` is UNRELIABLE in this Qt build
    #     (matches both states) — never use it; drive check-state styling with
    #     an explicit ``state`` property instead.  ``:!hover`` /
    #     ``:focus:!hover`` are VERIFIED WORKING (gate 3) and are acceptable
    #     where hover-priority ordering is needed.
    #
    # Convention
    #   * Panel/button roles are generic and reusable.  A domain prefix
    #     ("nav-*", "alert-*", "tacho-*") is acceptable ONLY when the role
    #     styles hard-coded dialog chrome that will never be reused as a
    #     generic component.

    # ── Base / reset ──────────────────────────────────────────────────────────

    @classmethod
    def _base_qss(cls) -> str:
        return f"""
        QWidget {{
            background-color: {COLOR_BG_BASE};
            color: {COLOR_TEXT_PRIMARY};
            font-family: {cls._ff("sans")};
            font-size: {cls._fs("body")}px;
            outline: none;
        }}

        QMainWindow, QDialog, QMessageBox {{
            background-color: {COLOR_BG_BASE};
        }}

        QWidget:focus {{
            outline: none;
        }}

        QWidget:disabled {{
            color: {COLOR_TEXT_TERTIARY};
        }}

        /* Elevated scroll-content sheet: a widget marked surface="elevated"
           paints the elevated panel surface for itself and every plain QWidget
           descendant. Styled widgets (inputs/buttons/…) keep their own rules
           because those selectors appear later in the stylesheet and tie on
           specificity. */
        QWidget[surface="elevated"] {{
            background-color: {COLOR_BG_ELEVATED};
        }}

        [surface="elevated"] QWidget {{
            background-color: {COLOR_BG_ELEVATED};
        }}

        /* Pinned action-bar surface (route planner Calculate/Export/Share
           bar): elevated sheet with a subtle top divider. Selector-scoped so
           it does not cascade to the buttons inside it. */
        QWidget[role="button-bar"] {{
            background-color: {COLOR_BG_ELEVATED};
            border-top: 1px solid {COLOR_BORDER_SUBTLE};
        }}

        /* Transparent container: plain QWidget sheets that must show the
           parent surface instead of the default COLOR_BG_BASE sheet. */
        QWidget[role="transparent"] {{
            background-color: transparent;
            border: none;
        }}
        """

    # ── Typography ────────────────────────────────────────────────────────────

    @classmethod
    def _typography_qss(cls) -> str:
        return f"""
        QLabel {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
        }}

        QLabel[fontRole="muted"] {{
            color: {COLOR_TEXT_TERTIARY};
        }}

        QLabel[fontRole="secondary"] {{
            color: {COLOR_TEXT_SECONDARY};
        }}

        QLabel[fontRole="accent"] {{
            color: {COLOR_ACCENT_PRIMARY};
        }}

        QLabel[fontRole="success"] {{
            color: {COLOR_SUCCESS_TEXT};
        }}

        QLabel[fontRole="warning"] {{
            color: {COLOR_WARNING_TEXT};
        }}

        QLabel[fontRole="danger"] {{
            color: {COLOR_ERROR_TEXT};
        }}

        QLabel[fontRole="label"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {cls._fs("label")}px;
            text-transform: uppercase;
        }}

        QLabel[fontRole="small"] {{
            font-size: {cls._fs("small")}px;
        }}

        QLabel[fontRole="helper"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {cls._fs("small")}px;
        }}

        QLabel[fontRole="xs-muted"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_XS}px;
        }}

        QLabel[fontRole="sm"] {{
            font-size: {FONT_SIZE_SM}px;
        }}

        QLabel[fontRole="sm-secondary"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_SM}px;
        }}

        QLabel[fontRole="sm-muted-italic"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_SM}px;
            font-style: italic;
        }}

        QLabel[fontRole="sm-error"] {{
            color: {COLOR_ERROR_TEXT};
            font-size: {FONT_SIZE_SM}px;
        }}

        QLabel[fontRole="sm-bold-error"] {{
            color: {COLOR_ERROR_TEXT};
            font-size: {FONT_SIZE_SM}px;
            font-weight: bold;
        }}

        QLabel[fontRole="sm-bold-success"] {{
            color: {COLOR_SUCCESS_TEXT};
            font-size: {FONT_SIZE_SM}px;
            font-weight: bold;
        }}

        QLabel[fontRole="sm-bold-muted"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: bold;
        }}

        QLabel[fontRole="base-medium"] {{
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
        }}

        QLabel[fontRole="base-semibold"] {{
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 600;
        }}

        QLabel[fontRole="base-secondary"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_BASE}px;
        }}

        QLabel[fontRole="base-secondary-italic"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_BASE}px;
            font-style: italic;
        }}

        QLabel[fontRole="base-warning"] {{
            color: {COLOR_WARNING_TEXT};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
        }}

        QLabel[fontRole="lg-semibold"] {{
            font-size: {FONT_SIZE_LG}px;
            font-weight: 600;
        }}

        QLabel[role="danger-panel"] {{
            background-color: {COLOR_ERROR_SUBTLE};
            color: {COLOR_ERROR_TEXT};
            border: 1px solid {COLOR_ERROR_DEFAULT};
            border-radius: {RADIUS_INPUT}px;
            padding: 12px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 500;
        }}

        QLabel[role="warning-panel"] {{
            background-color: {COLOR_WARNING_SUBTLE};
            color: {COLOR_WARNING_TEXT};
            border: 1px solid {COLOR_WARNING_DEFAULT};
            border-radius: {RADIUS_INPUT}px;
            padding: 12px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 500;
        }}

        QLabel[fontRole="sm-neutral"] {{
            color: {COLOR_NEUTRAL_TEXT};
            font-size: {FONT_SIZE_SM}px;
        }}

        QLabel[fontRole="sm-medium-secondary"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 500;
        }}

        QLabel[role="empty-hint"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: 13px;
            padding: 40px;
        }}

        QLabel[role="field-error"] {{
            color: {COLOR_ERROR_TEXT};
            font-size: {FONT_SIZE_SM}px;
            padding-top: {SPACE_1}px;
        }}

        QLabel[fontRole="h1"] {{
            font-size: {cls._fs("h1")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="h2"] {{
            font-size: {cls._fs("h2")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="h3"] {{
            font-size: {cls._fs("h3")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="hero"] {{
            font-family: {cls._ff("hero")};
            font-size: {cls._fs("mono_xl")}px;
            color: {COLOR_TEXT_PRIMARY};
        }}

        QLabel[fontRole="mono"] {{
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("mono")}px;
        }}

        QLabel[fontRole="mono_lg"] {{
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("mono_lg")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="mono_xl"] {{
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("mono_xl")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="section"] {{
            color: {COLOR_ACCENT_PRIMARY};
            font-size: {cls._fs("body")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="kpi-title"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {cls._fs("label")}px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        QLabel[fontRole="kpi-value"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {cls._fs("mono_lg")}px;
            font-family: {cls._ff("mono")};
            font-weight: bold;
        }}

        QLabel[class="page-title"] {{
            font-size: 20px;
            font-weight: 600;
            color: {COLOR_TEXT_PRIMARY};
        }}

        QLabel[class="section-title"] {{
            font-size: 13px;
            font-weight: 600;
            color: {COLOR_TEXT_PRIMARY};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        QLabel[class="field-label"] {{
            font-size: 11px;
            color: {COLOR_TEXT_TERTIARY};
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        QLabel[class="kpi-value"] {{
            font-size: 22px;
            font-weight: 700;
            font-family: {cls._ff("mono")};
            color: {COLOR_TEXT_PRIMARY};
        }}

        QLabel[class="kpi-label"] {{
            font-size: 11px;
            color: {COLOR_TEXT_TERTIARY};
            text-transform: uppercase;
        }}
        """

    # ── Buttons ─────────────────────────────────────────────────────────────────

    @classmethod
    def _button_qss(cls) -> str:
        return f"""
        QPushButton {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_BUTTON}px;
            padding: {cls._px("2")}px {cls._px("4")}px;
            font-family: {cls._ff("sans")};
            font-size: {cls._fs("body")}px;
            font-weight: bold;
            min-height: 38px;
            /* Transition for smooth hover */
        }}

        QPushButton:focus {{
            border: 1px solid {COLOR_ACCENT_PRIMARY};
        }}

        QPushButton:focus:!hover {{
            /* Subtle inner glow on focus */
            border: 2px solid {COLOR_ACCENT_PRIMARY};
        }}

        QPushButton:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}

        QPushButton:pressed {{
            background-color: {COLOR_ACCENT_PRIMARY};
        }}

        QPushButton:disabled {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_TERTIARY};
        }}

        QPushButton[variant="secondary"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        QPushButton[variant="secondary"]:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QPushButton[variant="danger"] {{
            background-color: transparent;
            color: {COLOR_ERROR_TEXT};
            border: 1px solid {COLOR_ERROR_SUBTLE};
        }}

        QPushButton[variant="danger"]:hover {{
            background-color: {COLOR_ERROR_SUBTLE};
        }}

        QPushButton[variant="ghost"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            border: none;
        }}

        QPushButton[variant="ghost"]:focus {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_ACCENT_PRIMARY};
        }}

        QPushButton[variant="ghost"]:hover {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
        }}

        QPushButton[variant="success"] {{
            background-color: {COLOR_SUCCESS_SUBTLE};
            color: {COLOR_SUCCESS_TEXT};
            border: 1px solid {COLOR_SUCCESS_SUBTLE};
        }}

        QPushButton[variant="success"]:hover {{
            background-color: {COLOR_SUCCESS_SUBTLE};
            border-color: {COLOR_SUCCESS_TEXT};
        }}

        /* Compact size class (route planner action buttons). Reproduces the
           planner's measured compact buttons: the global min-height/padding
           still apply, so heights stay 54/56px; only the style differs. */
        QPushButton[compact="true"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_INPUT}px;
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
        }}

        QPushButton[compact="true"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}

        QPushButton[compact="true"]:pressed {{
            background-color: {COLOR_ACCENT_HOVER};
        }}

        QPushButton[compact="true"]:disabled {{
            background-color: rgba(99, 102, 241, 0.4);
            color: rgba(255, 255, 255, 0.4);
        }}

        QPushButton[compact="true"][variant="secondary"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 400;
        }}

        QPushButton[compact="true"][variant="secondary"]:hover {{
            background-color: {COLOR_BG_HOVER};
            color: {COLOR_TEXT_PRIMARY};
            border-color: {COLOR_BORDER_MEDIUM};
        }}

        /* Tight-padding compact primary (route planner "Create Trip"): SM
           radius/font and zero vertical padding keep it ~40px tall. */
        QPushButton[compact="true"][size="sm"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 500;
            padding: 0 16px;
        }}

        QPushButton[compact="true"][size="sm"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}

        QPushButton[compact="true"][size="sm"]:pressed {{
            background-color: {COLOR_ACCENT_HOVER};
        }}

        /* Tight-padding compact secondary (route planner "Google Maps"): SM
           radius/font and zero vertical padding keep it ~40px tall. */
        QPushButton[compact="true"][variant="secondary"][size="sm"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 400;
            padding: 0 12px;
        }}

        QPushButton[compact="true"][variant="secondary"][size="sm"]:hover {{
            background-color: {COLOR_BG_HOVER};
            color: {COLOR_TEXT_PRIMARY};
            border-color: {COLOR_BORDER_MEDIUM};
        }}

        /* Dialog primary action (CoPilot confirmation modal): accent-filled,
           fixed BTN_HEIGHT, 8px/20px padding. */
        QPushButton[variant="dialog-primary"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_INPUT}px;
            padding: 8px 20px;
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
            height: {BTN_HEIGHT}px;
        }}
        QPushButton[variant="dialog-primary"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        QPushButton[variant="dialog-primary"]:disabled {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_TERTIARY};
        }}

        /* Dialog secondary action (CoPilot confirmation modal cancel). */
        QPushButton[variant="dialog-secondary"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_INPUT}px;
            padding: 8px 20px;
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
            height: {BTN_HEIGHT}px;
        }}
        QPushButton[variant="dialog-secondary"]:hover {{
            background-color: {COLOR_BG_HOVER};
            border-color: {COLOR_BORDER_MEDIUM};
        }}

        /* Warning action button (CoPilot timeline confirmation bar). */
        QPushButton[variant="warning"] {{
            background-color: {COLOR_WARNING_DEFAULT};
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            border-radius: {RADIUS_INPUT}px;
            padding: 8px 20px;
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
        }}
        QPushButton[variant="warning"]:hover {{
            background-color: {COLOR_WARNING_TEXT};
        }}

        QPushButton[variant="warning-outline"] {{
            background-color: transparent;
            color: {COLOR_WARNING_TEXT};
            border: 1px solid {COLOR_WARNING_DEFAULT};
            border-radius: {RADIUS_INPUT}px;
            padding: 8px 20px;
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
        }}
        QPushButton[variant="warning-outline"]:hover {{
            background-color: {COLOR_WARNING_SUBTLE};
        }}

        /* Compact secondary toggle (CoPilot timeline view-switch button).
           NB: a plain "size" attribute cannot be used — it collides with
           QWidget's built-in ``size`` property, so the compact variant is
           keyed on ``sizeRole`` instead. */
        QPushButton[variant="secondary"][sizeRole="sm"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_INPUT}px;
            padding: 4px 12px;
            font-size: {FONT_SIZE_SM}px;
        }}
        QPushButton[variant="secondary"][sizeRole="sm"]:hover {{
            background-color: {COLOR_BG_HOVER};
            color: {COLOR_TEXT_PRIMARY};
        }}

        /* Small 28px action buttons (AutoMail inline schedule editor). */
        QPushButton[variant="sm-primary"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
            padding: 0 12px;
        }}
        QPushButton[variant="sm-primary"]:hover {{
            background-color: {COLOR_ACCENT_PRIMARY}CC;
        }}

        QPushButton[variant="sm-outline-accent"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_ACCENT_PRIMARY};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
            padding: 0 12px;
        }}
        QPushButton[variant="sm-outline-accent"]:hover {{
            background-color: {COLOR_BG_HOVER};
        }}

        QPushButton[variant="sm-outline"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            padding: 0 12px;
        }}
        QPushButton[variant="sm-outline"]:hover {{
            background-color: {COLOR_BG_HOVER};
            color: {COLOR_TEXT_PRIMARY};
        }}

        /* Strong primary action (AutoMail "Add Reminder"). */
        QPushButton[variant="primary-strong"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_INPUT}px;
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 600;
            padding: 0 16px;
        }}
        QPushButton[variant="primary-strong"]:hover {{
            background-color: {COLOR_ACCENT_PRIMARY}CC;
        }}
        QPushButton[variant="primary-strong"]:pressed {{
            background-color: {COLOR_ACCENT_PRIMARY}AA;
        }}

        /* Checkable filter pill (AutoMail timeline status filters).
           Qt's ``:!checked`` negation is unreliable in this Qt build, so the
           two visual states are driven by an explicit ``state`` property
           ("active"/"inactive") that the view toggles with unpolish/polish. */
        QPushButton[role="filter-pill"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: {FONT_SIZE_SM}px;
        }}
        QPushButton[role="filter-pill"][state="inactive"] {{
            border: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QPushButton[role="filter-pill"][state="inactive"]:hover {{
            background-color: {COLOR_BG_HOVER};
        }}
        QPushButton[role="filter-pill"][state="active"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
        }}

        /* Rich-text formatting toolbar button (AutoMail editor). */
        QToolButton[role="format-btn"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 4px 8px;
            font-size: {FONT_SIZE_BASE}px;
        }}
        QToolButton[role="format-btn"]:hover {{
            background-color: {COLOR_BG_HOVER};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QToolButton[role="format-btn"]:checked {{
            background-color: {COLOR_ACCENT_SUBTLE};
            color: {COLOR_ACCENT_PRIMARY};
        }}
        """

    # ── Inputs ──────────────────────────────────────────────────────────────────

    @classmethod
    def _input_qss(cls) -> str:
        return f"""
        QLineEdit, QPlainTextEdit, QTextEdit, QDateEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
            padding: 6px 10px;
            font-family: {cls._ff("sans")};
            font-size: {cls._fs("body")}px;
            selection-background-color: {COLOR_ACCENT_PRIMARY};
            selection-color: {TEXT_WHITE};
            /* Transition for smooth border change */
        }}

        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
        QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}

        QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
        QDateEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_TERTIARY};
        }}

        QPlainTextEdit, QTextEdit {{
            padding: 8px;
        }}

        QLineEdit::placeholder, QPlainTextEdit::placeholder {{
            color: {COLOR_TEXT_TERTIARY};
        }}

        QDateEdit::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: 1px solid {COLOR_BORDER_MEDIUM};
            border-top-right-radius: {RADIUS_INPUT}px;
            border-bottom-right-radius: {RADIUS_INPUT}px;
        }}

        QDateEdit::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {COLOR_TEXT_SECONDARY};
            width: 0px;
            height: 0px;
        }}

        /* Validation states */
        QLineEdit[validation="error"], QPlainTextEdit[validation="error"] {{
            border-color: {COLOR_ERROR_DEFAULT};
        }}

        QLineEdit[validation="success"], QPlainTextEdit[validation="success"] {{
            border-color: {COLOR_SUCCESS_DEFAULT};
        }}

        /* Compact size class (route planner waypoint fields): SUBTLE border,
           SM radius, zero vertical padding, 12px font (FONT_SIZE_BASE).
           Background is set explicitly so the compact rule ties with the
           elevated-surface rule and wins by stylesheet order. */
        QLineEdit[compact="true"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
            padding: 0 10px;
            font-size: {FONT_SIZE_BASE}px;
        }}

        QLineEdit[role="dialog-input"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
            color: {COLOR_TEXT_PRIMARY};
            padding: 8px 12px;
            font-size: {FONT_SIZE_BASE}px;
            height: {INPUT_HEIGHT}px;
        }}
        QLineEdit[role="dialog-input"]:focus {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}

        QLineEdit[role="panel-input"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_INPUT}px;
            padding: 8px 10px;
            font-size: {FONT_SIZE_BASE}px;
        }}

        QTextEdit[role="panel-input"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_INPUT}px;
            padding: 8px;
            font-size: {FONT_SIZE_BASE}px;
        }}
        """

    # ── Checkboxes / Radio buttons ──────────────────────────────────────────────

    @classmethod
    def _checkbox_qss(cls) -> str:
        return f"""
        QCheckBox {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            spacing: {cls._px("2")}px;
            font-size: {cls._fs("body")}px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 4px;
            background-color: {COLOR_BG_OVERLAY};
            /* Transition for smooth state changes */
        }}

        QCheckBox:focus::indicator {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}

        QCheckBox::indicator:hover {{
            border-color: {COLOR_BORDER_STRONG};
        }}

        QCheckBox::indicator:checked {{
            background-color: {COLOR_ACCENT_PRIMARY};
            border-color: {COLOR_ACCENT_PRIMARY};
            image: none;
        }}

        QCheckBox::indicator:disabled {{
            background-color: {COLOR_BG_OVERLAY};
            border-color: {COLOR_BORDER_MEDIUM};
        }}

        /* Compact size class (route planner toggles): 16px indicator and
           secondary text vs the global 18px/primary. Font stays at the
           planner's 12px (FONT_SIZE_BASE), not the theme's 13px body.
           Background set explicitly so the compact rule ties with the
           elevated-surface rule and wins by stylesheet order. */
        QCheckBox[compact="true"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 400;
            spacing: 8px;
        }}

        QCheckBox[compact="true"]:hover {{
            color: {COLOR_TEXT_PRIMARY};
        }}

        QCheckBox[compact="true"]::indicator {{
            width: 16px;
            height: 16px;
        }}

        QCheckBox[compact="true"]::indicator:hover {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}

        /* ``fontRole`` is QLabel-primary but OPT-IN per widget class; checkbox
           labels opt into the 12px ``small`` size here. */
        QCheckBox[fontRole="small"] {{
            font-size: {FONT_SIZE_BASE}px;
        }}
        """

    @classmethod
    def _radiobutton_qss(cls) -> str:
        return f"""
        QRadioButton {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            spacing: {cls._px("2")}px;
            font-size: {cls._fs("body")}px;
        }}

        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 9px;
            background-color: {COLOR_BG_OVERLAY};
        }}

        QRadioButton:focus::indicator {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}

        QRadioButton::indicator:hover {{
            border-color: {COLOR_BORDER_STRONG};
        }}

        QRadioButton::indicator:checked {{
            background-color: {COLOR_ACCENT_PRIMARY};
            border-color: {COLOR_ACCENT_PRIMARY};
        }}
        """

    # ── ComboBox ────────────────────────────────────────────────────────────────

    @classmethod
    def _combobox_qss(cls) -> str:
        return f"""
        QComboBox {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
            padding: 6px 10px;
            min-height: 38px;
            font-size: {cls._fs("body")}px;
        }}

        QComboBox:focus {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: 1px solid {COLOR_BORDER_MEDIUM};
            border-top-right-radius: {RADIUS_INPUT}px;
            border-bottom-right-radius: {RADIUS_INPUT}px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {COLOR_TEXT_SECONDARY};
            width: 0px;
            height: 0px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            selection-background-color: {COLOR_BG_OVERLAY};
            selection-color: {COLOR_TEXT_PRIMARY};
            outline: none;
        }}

        QComboBox QAbstractItemView::item {{
            padding: 6px 10px;
            min-height: 28px;
        }}

        QComboBox QAbstractItemView::item:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QComboBox QAbstractItemView::item:selected {{
            background-color: {COLOR_ACCENT_SUBTLE};
            color: {COLOR_ACCENT_PRIMARY};
        }}

        /* Compact size class (route planner combos): SUBTLE border, SM radius,
           zero vertical padding (keeps height ~40px vs the global ~52px),
           12px font (FONT_SIZE_BASE). Background set explicitly to tie with
           the elevated-surface rule and win by stylesheet order. */
        QComboBox[compact="true"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
            padding: 0 10px;
            font-size: {FONT_SIZE_BASE}px;
        }}

        QComboBox[compact="true"]::drop-down {{
            border: none;
        }}

        QComboBox[compact="true"]::down-arrow {{
            width: 12px;
            height: 12px;
        }}

        QComboBox[compact="true"] QAbstractItemView {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_BG_HOVER};
        }}
        """

    # ── SpinBox ─────────────────────────────────────────────────────────────────

    @classmethod
    def _spinbox_qss(cls) -> str:
        return f"""
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            width: 20px;
        }}

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {COLOR_BORDER_STRONG};
        }}
        """

    # ── Tables ──────────────────────────────────────────────────────────────────

    @classmethod
    def _table_qss(cls) -> str:
        return f"""
        QTableWidget, QTableView {{
            background-color: {COLOR_BG_ELEVATED};
            alternate-background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            gridline-color: {COLOR_BORDER_MEDIUM};
            border: none;
            font-size: {cls._fs("body")}px;
        }}

        QTableWidget::item, QTableView::item {{
            padding: 6px 8px;
            border: none;
            /* Transition for smooth hover */
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {COLOR_BG_SELECTED};
            color: {COLOR_TEXT_PRIMARY};
        }}

        QTableWidget::item:hover, QTableView::item:hover {{
            background-color: {COLOR_BG_HOVER};
        }}

        QHeaderView {{
            background-color: {COLOR_BG_BASE};
        }}

        QHeaderView::section {{
            background-color: {COLOR_BG_BASE};
            color: {COLOR_TEXT_TERTIARY};
            padding: 8px 12px;
            border: none;
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
            font-weight: 600;
            font-size: {cls._fs("label")}px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        QHeaderView::section:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QHeaderView::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {COLOR_TEXT_TERTIARY};
        }}

        QHeaderView::up-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-bottom: 6px solid {COLOR_TEXT_TERTIARY};
        }}

        QTableCornerButton::section {{
            background-color: {COLOR_BG_BASE};
            border: none;
        }}
        """

    # ── Trees ───────────────────────────────────────────────────────────────────

    @classmethod
    def _tree_qss(cls) -> str:
        return f"""
        QTreeWidget, QTreeView {{
            background-color: {COLOR_BG_ELEVATED};
            alternate-background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            outline: none;
        }}

        QTreeWidget::item, QTreeView::item {{
            padding: 6px 8px;
            border: none;
        }}

        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {COLOR_ACCENT_SUBTLE};
            color: {COLOR_TEXT_PRIMARY};
        }}

        QTreeWidget::item:hover, QTreeView::item:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QTreeWidget::branch:has-siblings:!adjoins-item {{
            border-image: none;
        }}

        QTreeWidget::branch:has-siblings:adjoins-item {{
            border-image: none;
        }}

        /* Transparent reasoning-graph tree (CoPilot timeline). */
        QTreeWidget[role="transparent"] {{
            background-color: transparent;
            border: none;
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
        }}
        QTreeWidget[role="transparent"]::item {{
            padding: {SPACE_1}px {_P2}px;
        }}
        """

    # ── ScrollArea / ScrollBar ──────────────────────────────────────────────────

    @classmethod
    def _scrollarea_qss(cls) -> str:
        return """
        QScrollArea {
            border: none;
            background-color: transparent;
        }

        QScrollArea > QWidget > QWidget {
            background-color: transparent;
        }
        """

    @classmethod
    def _scrollbar_qss(cls) -> str:
        return f"""
        QScrollBar:vertical {{
            background-color: {COLOR_BG_BASE};
            width: 6px;
            border-radius: 3px;
        }}

        QScrollBar:vertical:hover {{
            width: 8px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {COLOR_BORDER_MEDIUM};
            min-height: 36px;
            border-radius: 3px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {COLOR_BORDER_STRONG};
            min-height: 40px;
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            background: none;
            height: 0px;
        }}

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            background-color: {COLOR_BG_BASE};
            height: 6px;
            border-radius: 3px;
        }}

        QScrollBar:horizontal:hover {{
            height: 8px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {COLOR_BORDER_MEDIUM};
            min-width: 36px;
            border-radius: 3px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {COLOR_BORDER_STRONG};
            min-width: 40px;
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            background: none;
            width: 0px;
        }}

        /* Compact size class (route planner scrollbar): 4px track with
           hover-expand, 20px handle min-height (vs global 6px/36px). */
        QScrollBar:vertical[compact="true"] {{
            background: transparent;
            width: 4px;
        }}

        QScrollBar:vertical[compact="true"]:hover {{
            width: 6px;
        }}

        QScrollBar::handle:vertical[compact="true"] {{
            background-color: {COLOR_BORDER_MEDIUM};
            border-radius: 2px;
            min-height: {cls._px("5")}px;
        }}
        """

    # ── TabWidget ───────────────────────────────────────────────────────────────

    @classmethod
    def _tabwidget_qss(cls) -> str:
        return f"""
        QTabWidget::pane {{
            border: none;
            background-color: {COLOR_BG_BASE};
            top: -1px;
        }}

        QTabBar {{
            background-color: transparent;
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}

        QTabBar::tab {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 8px 16px;
            margin-right: 2px;
            font-size: {cls._fs("label")}px;
            font-weight: 600;
            letter-spacing: 0.08em;
            /* Transition for smooth state changes */
        }}

        QTabBar::tab:selected {{
            color: {COLOR_ACCENT_PRIMARY};
            border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        }}

        QTabBar::tab:hover:!selected {{
            color: {COLOR_TEXT_PRIMARY};
        }}

        QTabBar::tab:disabled {{
            color: {COLOR_TEXT_TERTIARY};
        }}
        """

    # ── ProgressBar ─────────────────────────────────────────────────────────────

    @classmethod
    def _progressbar_qss(cls) -> str:
        return f"""
        QProgressBar {{
            background-color: {COLOR_BG_OVERLAY};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            text-align: center;
            color: {COLOR_TEXT_PRIMARY};
            font-size: {cls._fs("small")}px;
            /* Hint: animate chunk width for subtle progress pulse */
        }}

        QProgressBar::chunk {{
            background-color: {COLOR_ACCENT_PRIMARY};
            border-radius: {RADIUS_CHIP}px;
        }}
        """

    # ── GroupBox / Frame ────────────────────────────────────────────────────────

    @classmethod
    def _groupbox_qss(cls) -> str:
        return f"""
        QGroupBox {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CARD}px;
            margin-top: 12px;
            padding: 12px;
            font-weight: bold;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: -10px;
            padding: 0 6px;
            color: {COLOR_TEXT_SECONDARY};
        }}
        """

    @classmethod
    def _frame_qss(cls) -> str:
        return f"""
        QFrame {{
            background-color: transparent;
            border: none;
        }}

        QFrame[role="card"], QFrame#card {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
            /* Transition for smooth hover elevation */
        }}

        QFrame[role="card"]:hover, QFrame#card:hover {{
            border-color: {ELEVATION_RAISED};
        }}

        QFrame[role="card-elevated"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
            /* Transition for smooth hover elevation */
        }}

        QFrame[role="card-elevated"]:hover {{
            border-color: {ELEVATION_RAISED};
        }}

        QFrame[role="input"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
        }}

        QFrame[role="divider"] {{
            background-color: {COLOR_BORDER_MEDIUM};
            max-height: 1px;
            min-height: 1px;
        }}

        QFrame[role="accent-bar"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            max-width: 3px;
            min-width: 3px;
            border-radius: 2px;
        }}

        QFrame[role="section-line"] {{
            background-color: {COLOR_BORDER_MEDIUM};
            max-height: 1px;
            min-height: 1px;
        }}

        QFrame[role="kpi-card"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
            /* Transition for smooth hover elevation */
        }}

        QFrame[role="kpi-card"]:hover {{
            border-color: {ELEVATION_RAISED};
        }}

        QFrame[role="chip-critical"] {{
            background-color: {COLOR_ERROR_SUBTLE};
            color: {COLOR_ERROR_TEXT};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-warning"] {{
            background-color: {COLOR_WARNING_SUBTLE};
            color: {COLOR_WARNING_TEXT};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-info"] {{
            background-color: {COLOR_INFO_SUBTLE};
            color: {COLOR_ACCENT_PRIMARY};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-success"] {{
            background-color: {COLOR_SUCCESS_SUBTLE};
            color: {COLOR_SUCCESS_TEXT};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-neutral"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QLabel[role="status-chip"][solid="true"] {{
            /* Solid (borderless) status chip surface — used by StatusBadge
               with ``solid=True``; per-instance colours are applied inline. */
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
            font-size: {FONT_SIZE_SM}px;
        }}

        QFrame[role="panel-elevated"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_INPUT}px;
        }}

        QFrame[role="panel-danger"] {{
            background-color: {COLOR_ERROR_SUBTLE};
            border: 1px solid {COLOR_ERROR_DEFAULT};
            border-radius: {RADIUS_CHIP}px;
        }}

        QFrame[role="panel-success"] {{
            background-color: {COLOR_SUCCESS_SUBTLE};
            border: 1px solid {COLOR_SUCCESS_DEFAULT};
            border-radius: {RADIUS_CHIP}px;
        }}

        QFrame[role="warning-panel"] {{
            background-color: {COLOR_WARNING_SUBTLE};
            border: 1px solid {COLOR_WARNING_DEFAULT};
            border-radius: {RADIUS_INPUT}px;
        }}

        QFrame[role="option-row"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_INPUT}px;
        }}
        QFrame[role="option-row"]:hover {{
            background-color: {COLOR_BG_HOVER};
            border-color: {COLOR_BORDER_MEDIUM};
        }}

        /* AutoMail cluster surfaces (domain-prefixed: hard-coded panel chrome). */
        QFrame[role="automail-config-panel"],
        QFrame[role="automail-editor-panel"],
        QFrame[role="automail-timeline-panel"] {{
            background-color: {COLOR_BG_ELEVATED};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="automail-master-toggle"],
        QFrame[role="inline-schedule-editor"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
        }}
        QFrame[role="automail-master-toggle"] {{
            padding: 16px;
        }}

        QFrame[role="schedule-card"],
        QFrame[role="invoice-timeline-card"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
        }}
        QFrame[role="schedule-card"] {{
            padding: 12px;
        }}

        QFrame[role="panel-surface"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="step-connector"] {{
            background-color: {COLOR_BORDER_SUBTLE};
            border: none;
            margin-left: 4px;
            margin-right: 4px;
        }}

        QFrame[role="format-toolbar"] {{
            background-color: {COLOR_BG_OVERLAY};
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        """

    # ── Menu / ToolTip ──────────────────────────────────────────────────────────

    @classmethod
    def _menu_qss(cls) -> str:
        return f"""
        QMenuBar {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
            border-bottom: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        QMenuBar::item:selected {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QMenu {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            padding: 4px;
        }}

        QMenu::item {{
            padding: 8px 20px;
            border-radius: {RADIUS_CHIP}px;
        }}

        QMenu::item:hover {{
            background-color: {COLOR_BG_HOVER};
        }}

        QMenu::item:selected {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {COLOR_BORDER_MEDIUM};
            margin: 4px 8px;
        }}
        """

    @classmethod
    def _tooltip_qss(cls) -> str:
        return f"""
        QToolTip {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CHIP}px;
            padding: 4px 8px;
            font-size: {cls._fs("small")}px;
        }}
        """

    # ── Dialogs ─────────────────────────────────────────────────────────────────

    @classmethod
    def _dialog_qss(cls) -> str:
        return f"""
        QMessageBox {{
            background-color: {COLOR_BG_BASE};
        }}

        QMessageBox QLabel {{
            color: {COLOR_TEXT_PRIMARY};
        }}

        QMessageBox QSpacerItem {{
            width: 0px;
            height: 0px;
        }}

        QDialogButtonBox QPushButton {{
            min-width: 80px;
        }}

        QDialog {{
            background-color: {COLOR_BG_ELEVATED};
        }}

        QDialog[modal="true"] {{
            background-color: {COLOR_BG_ELEVATED};
        }}

        QDialog[role="base-surface"] {{
            background-color: {COLOR_BG_BASE};
        }}
        """

    # ── Splitter ────────────────────────────────────────────────────────────────

    @classmethod
    def _splitter_qss(cls) -> str:
        return f"""
        QSplitter::handle {{
            background-color: {COLOR_BORDER_MEDIUM};
        }}

        QSplitter::handle:horizontal {{
            width: 1px;
        }}

        QSplitter::handle:vertical {{
            height: 1px;
        }}
        """

    # ── Navigation panel ────────────────────────────────────────────────────────

    @classmethod
    def _nav_qss(cls) -> str:
        return f"""
        QFrame[role="nav-panel"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: none;
            border-right: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        QFrame[role="nav-top-section"] {{
            background-color: transparent;
            border: none;
        }}

        QFrame[role="nav-divider"] {{
            background-color: {COLOR_BORDER_MEDIUM};
            max-height: 1px;
            min-height: 1px;
        }}

        QFrame[role="nav-item"] {{
            background-color: transparent;
            border: none;
            border-radius: 6px;
            /* Transition for smooth state changes */
        }}

        QFrame[role="nav-item"]:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QFrame[role="nav-item"][state="active"] {{
            background-color: {COLOR_BG_OVERLAY};
            border-left: 3px solid {COLOR_ACCENT_PRIMARY};
        }}

        QFrame[role="nav-accent"] {{
            background-color: transparent;
            max-width: 3px;
            min-width: 3px;
            border-radius: 2px;
        }}

        QFrame[role="nav-item"][state="active"] QFrame[role="nav-accent"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
        }}

        QLabel[role="nav-icon"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            font-family: "'Segoe UI Emoji', 'Segoe UI Symbol', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif";
            font-size: {cls._fs("h2")}px;
        }}

        QFrame[role="nav-item"][state="active"] QLabel[role="nav-icon"] {{
            color: {COLOR_ACCENT_PRIMARY};
        }}

        QLabel[role="nav-label"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            font-size: {cls._fs("body")}px;
        }}

        QFrame[role="nav-item"][state="active"] QLabel[role="nav-label"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-weight: bold;
        }}

        QLabel[role="nav-group-label"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            font-size: {cls._fs("label")}px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        QFrame[role="nav-monogram"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            border-radius: 6px;
        }}

        QLabel[role="nav-monogram-text"] {{
            background-color: transparent;
            color: {TEXT_WHITE};
            font-weight: bold;
            font-size: {cls._fs("body")}px;
        }}

        QLabel[role="nav-app-name"] {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            font-weight: bold;
            font-size: 13px;
        }}

        QLabel[role="nav-app-subtitle"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            font-size: 11px;
        }}

        QPushButton[role="nav-toggle"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            border: none;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 12px;
            font-weight: bold;
            min-width: 24px;
            min-height: 24px;
        }}

        QPushButton[role="nav-toggle"]:hover {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
        }}
        """

    # ── Top bar ─────────────────────────────────────────────────────────────────

    @classmethod
    def _topbar_qss(cls) -> str:
        return f"""
        QFrame[role="top-bar"] {{
            background-color: {COLOR_BG_BASE};
            border: none;
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}

        QFrame[role="top-bar-divider"] {{
            background-color: {COLOR_BORDER_MEDIUM};
            max-height: 1px;
            min-height: 1px;
        }}

        QLabel[role="fuel-status"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("small")}px;
        }}

        QLabel[role="clock"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("body")}px;
        }}

        QLabel[role="bell"] {{
            background-color: transparent;
            color: {COLOR_TEXT_TERTIARY};
            font-size: 16px;
        }}

        QLabel[role="bell"][alert="true"] {{
            color: {COLOR_ERROR_TEXT};
        }}

        QLabel[role="badge"] {{
            background-color: {COLOR_ERROR_DEFAULT};
            color: {TEXT_WHITE};
            border-radius: 9px;
            font-size: {cls._fs("label")}px;
            font-weight: bold;
            min-width: 18px;
            max-width: 18px;
            min-height: 18px;
            max-height: 18px;
            qproperty-alignment: AlignCenter;
        }}
        """

    # ── Stacked widget (view container) ─────────────────────────────────────────

    @classmethod
    def _stackedwidget_qss(cls) -> str:
        return """
        QStackedWidget {
            border: none;
            background-color: transparent;
        }
        """

    # ── Calendar (custom dark popup) ────────────────────────────────────────────

    @classmethod
    def _calendar_qss(cls) -> str:
        return f"""
        QCalendarWidget {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CARD}px;
        }}

        QCalendarWidget QWidget {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
        }}

        QCalendarWidget QToolButton {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 4px 8px;
            font-weight: bold;
        }}

        QCalendarWidget QToolButton:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QCalendarWidget QMenu {{
            background-color: {COLOR_BG_ELEVATED};
        }}

        QCalendarWidget QSpinBox {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        QCalendarWidget QAbstractItemView:enabled {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_ACCENT_PRIMARY};
            selection-color: {TEXT_WHITE};
        }}

        QCalendarWidget QAbstractItemView:disabled {{
            color: {COLOR_TEXT_TERTIARY};
        }}

        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: {COLOR_BG_OVERLAY};
            border-bottom: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        QCalendarWidget QAbstractItemView::item {{
            outline: none;
            border-radius: {RADIUS_CHIP}px;
        }}

        QCalendarWidget QAbstractItemView::item:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QCalendarWidget QAbstractItemView::item:selected {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
        }}
        """

    @classmethod
    def _toast_qss(cls) -> str:
        return f"""
        QFrame[role="toast"] {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="toast"][state="error"] {{
            border: 1px solid {COLOR_ERROR_DEFAULT};
        }}

        QLabel[role="toast-icon"] {{
            background-color: transparent;
            font-size: 16px;
        }}

        QLabel[role="toast-label"] {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            font-size: {cls._fs("body")}px;
        }}
        """

    # ── App-specific fragments (formerly ui/stylesheet.py) ──────────────────

    @classmethod
    def _stat_card_qss(cls) -> str:
        return f"""
        QFrame#stat-card {{
            background-color: {COLOR_BG_CARD};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
            padding: 16px;
        }}

        QFrame#stat-card[hovered="true"] {{
            background-color: {COLOR_BG_CARD_HOVER};
            border-color: {COLOR_ACCENT_PRIMARY};
        }}
        """

    @classmethod
    def _filter_qss(cls) -> str:
        return f"""
        QCheckBox[role="filter"] {{
            spacing: 6px;
        }}

        QCheckBox[role="toggle-switch"] {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_MD}px;
            font-weight: 500;
            spacing: 12px;
        }}

        QCheckBox[role="filter"]::indicator {{
            width: 16px;
            height: 16px;
            border-radius: {RADIUS_CHIP}px;
        }}

        QLineEdit[role="filter"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
            padding: 4px 8px;
            color: {COLOR_TEXT_PRIMARY};
        }}

        QComboBox[role="filter"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_INPUT}px;
            padding: 4px 8px;
            color: {COLOR_TEXT_PRIMARY};
            min-height: 28px;
        }}
        """

    @classmethod
    def _section_header_qss(cls) -> str:
        return f"""
        QLabel[role="section-header"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {cls._fs("label")}px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            padding: 4px 0;
        }}
        """

    @classmethod
    def _tab_button_qss(cls) -> str:
        return f"""
        QPushButton[tabRole="tab-button"] {{
            background-color: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-bottom: 2px solid transparent;
            border-radius: 0;
            padding: 8px 16px;
            font-weight: 600;
            font-size: {cls._fs("label")}px;
            letter-spacing: 0.04em;
        }}

        QPushButton[tabRole="tab-button"]:hover {{
            color: {COLOR_TEXT_PRIMARY};
        }}

        QPushButton[tabRole="tab-button"][tabActive="true"] {{
            color: {COLOR_ACCENT_PRIMARY};
            border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        }}
        """

    @classmethod
    def _kanban_qss(cls) -> str:
        return f"""
        QFrame[role="kanban-column"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
        }}

        QWidget[role="kanban-column-header"] {{
            background-color: transparent;
            padding: 8px 12px 4px;
        }}

        QWidget[role="kanban-column-header"] QLabel[class="kanban-column-title"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-weight: 600;
            font-size: {cls._fs("body")}px;
        }}

        QWidget[role="kanban-column-header"] QLabel[class="kanban-column-count"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {cls._fs("label")}px;
        }}

        QScrollArea[class="kanban-columns-container"] {{
            border: none;
            background-color: transparent;
        }}
        """

    # ── Freight Exchange cluster (Phase 3) ─────────────────────────────────
    # Connection view (connect_view), search view (search_view) and load
    # detail view (load_detail_view).  Domain-prefixed roles only where the
    # styled widget is hard-coded cluster chrome (score bars, match rows);
    # generic roles/variants where the component could be reused elsewhere.
    # ``QLabel`` typography roles (match-rank / score-value / match-profit)
    # are used because the closest ``fontRole`` values differ by exactly one
    # property (e.g. ``h2`` for match-rank), so minting a fontRole is barred
    # by the "≥2 properties" reuse rule; the family stays whatever QFont the
    # widget carries (QLabel roles do not set font-family).

    @classmethod
    def _freight_exchange_qss(cls) -> str:
        return f"""
        QLabel[role="status-badge"] {{
            padding: 4px 12px;
            border-radius: {RADIUS_PILL}px;
        }}
        QLabel[role="status-badge"][state="neutral"] {{
            background-color: {COLOR_NEUTRAL_SUBTLE};
            color: {COLOR_NEUTRAL_TEXT};
        }}
        QLabel[role="status-badge"][state="connected"] {{
            background-color: {COLOR_SUCCESS_SUBTLE};
            color: {COLOR_SUCCESS_TEXT};
        }}
        QLabel[role="status-badge"][state="connecting"] {{
            background-color: {COLOR_WARNING_SUBTLE};
            color: {COLOR_WARNING_TEXT};
        }}

        QPushButton[variant="primary-bordered"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_BUTTON}px;
            padding: 6px 12px;
        }}
        QPushButton[variant="primary-bordered"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        /* The inline styles these buttons replaced also beat the global
           :focus rules (inline > app stylesheet), so the focus border must
           be re-declared here or the global 2px accent focus ring shows. */
        QPushButton[variant="primary-bordered"]:focus,
        QPushButton[variant="primary-bordered"]:focus:!hover {{
            border: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        /* Accent primary with 6px vertical padding (connect button). The
           global QPushButton rule pads 8px, so this is a distinct variant. */
        QPushButton[variant="primary-tight"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_BUTTON}px;
            padding: 6px 16px;
        }}
        QPushButton[variant="primary-tight"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        QPushButton[variant="primary-tight"]:focus,
        QPushButton[variant="primary-tight"]:focus:!hover {{
            border: none;
        }}

        QPushButton[variant="danger-bordered"] {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {COLOR_ERROR_TEXT};
            border: 1px solid {COLOR_ERROR_DEFAULT};
            border-radius: {RADIUS_BUTTON}px;
            padding: 6px 12px;
        }}
        QPushButton[variant="danger-bordered"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        QPushButton[variant="danger-bordered"]:focus,
        QPushButton[variant="danger-bordered"]:focus:!hover {{
            border: 1px solid {COLOR_ERROR_DEFAULT};
        }}

        QPushButton[variant="outline-accent"] {{
            background-color: transparent;
            color: {COLOR_ACCENT_PRIMARY};
            border: 1px solid {COLOR_ACCENT_BORDER};
            border-radius: {RADIUS_CHIP}px;
        }}
        QPushButton[variant="outline-accent"]:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}
        /* Reproduces the replaced ghost-variant focus: overlay surface with
           the accent-border outline (the old inline overrode the global
           accent focus ring the same way). */
        QPushButton[variant="outline-accent"]:focus,
        QPushButton[variant="outline-accent"]:focus:!hover {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_ACCENT_BORDER};
        }}

        QFrame[role="match-row"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_BUTTON}px;
        }}
        QFrame[role="match-row"]:hover {{
            background-color: {COLOR_BG_HOVER};
        }}
        QFrame[role="match-row"]:focus {{
            border: 1px solid {COLOR_ACCENT_PRIMARY};
        }}

        QLabel[role="match-rank"] {{
            font-size: {FONT_SIZE_LG}px;
            font-weight: bold;
            color: {COLOR_TEXT_TERTIARY};
        }}

        QFrame[role="score-track"] {{
            background-color: {COLOR_BG_BASE};
            border-radius: {RADIUS_PILL}px;
            border: none;
        }}

        QFrame[role="score-fill"] {{
            border-radius: {RADIUS_PILL}px;
            border: none;
        }}
        QFrame[role="score-fill"][state="high"] {{
            background-color: {COLOR_SUCCESS_DEFAULT};
        }}
        QFrame[role="score-fill"][state="mid"] {{
            background-color: {COLOR_WARNING_DEFAULT};
        }}
        QFrame[role="score-fill"][state="low"] {{
            background-color: {COLOR_ERROR_DEFAULT};
        }}

        QLabel[role="score-value"] {{
            font-size: {FONT_SIZE_MD}px;
            font-weight: bold;
        }}
        QLabel[role="score-value"][state="high"] {{
            color: {COLOR_SUCCESS_DEFAULT};
        }}
        QLabel[role="score-value"][state="mid"] {{
            color: {COLOR_WARNING_DEFAULT};
        }}
        QLabel[role="score-value"][state="low"] {{
            color: {COLOR_ERROR_DEFAULT};
        }}

        QLabel[role="match-profit"] {{
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 500;
        }}
        QLabel[role="match-profit"][state="positive"] {{
            color: {COLOR_SUCCESS_TEXT};
        }}
        QLabel[role="match-profit"][state="negative"] {{
            color: {COLOR_ERROR_TEXT};
        }}

        QWidget[role="panel-card"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CARD}px;
        }}

        QListView[role="combo-popup"] {{
            background-color: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
        }}

        QFrame[role="panel-danger-lg"] {{
            background-color: {COLOR_ERROR_SUBTLE};
            border: 1px solid {COLOR_ERROR_DEFAULT};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="scrim"] {{
            background-color: rgba(12, 12, 14, 0.7);
        }}

        QFrame[role="separator"] {{
            background-color: {COLOR_BORDER_SUBTLE};
        }}
        """

    # ── CMR form cluster (Phase 3) ─────────────────────────────────────────
    # Box-number badges (QLabel[role="box-badge"]), compact date edits, the
    # ADR toggle, inset input rows and the collapsible-section header button
    # from cmr_form.py / cmr_fields.py.

    @classmethod
    def _cmr_qss(cls) -> str:
        return f"""
        QLabel[role="box-badge"] {{
            background-color: {COLOR_ACCENT_SUBTLE};
            color: {ACCENT_TEXT};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_XS}px;
            font-weight: bold;
        }}
        QLabel[role="box-badge"][sizeRole="sm"] {{
            border-radius: 3px;
        }}
        QLabel[role="box-badge"][state="complete"] {{
            background-color: {COLOR_SUCCESS_SUBTLE};
            color: {COLOR_SUCCESS_DEFAULT};
        }}
        QLabel[role="box-badge"][state="partial"] {{
            background-color: {COLOR_WARNING_SUBTLE};
            color: {COLOR_WARNING_DEFAULT};
        }}
        QLabel[role="box-badge"][state="empty"] {{
            background-color: {COLOR_ACCENT_SUBTLE};
            color: {ACCENT_TEXT};
        }}

        QDateEdit[role="cmr-date"] {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 6px;
        }}

        QCheckBox[role="adr-toggle"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-weight: bold;
            spacing: 6px;
        }}

        QFrame[role="input-row"] {{
            background-color: {COLOR_BG_OVERLAY};
            border-radius: {RADIUS_CHIP}px;
        }}

        QPushButton[role="collapsible-header"] {{
            text-align: left;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
            color: {COLOR_TEXT_PRIMARY};
            padding: 0;
            border: none;
            background-color: transparent;
            letter-spacing: 0.5px;
        }}
        QPushButton[role="collapsible-header"]:hover {{
            color: {COLOR_ACCENT_PRIMARY};
        }}
        QPushButton[role="collapsible-header"]:focus,
        QPushButton[role="collapsible-header"]:focus:!hover {{
            border: none;
            background-color: transparent;
        }}
        """

    # ── Analytics cluster (Phase 4) ─────────────────────────────────────────
    # Base tab chrome (titles, KPI cards, section headers, scroll), the
    # period strip (pill group + refresh), and the per-tab widgets
    # (client/route/driver/financial/document).  Statful severity/KPI
    # colors use ``role`` + ``state`` (never fontRole); static typography
    # reuses existing fontRole values where the nearest value is exact.

    @classmethod
    def _analytics_qss(cls) -> str:
        return f"""
        QLabel[role="analytics-title"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
        }}
        QLabel[fontRole="xs-semibold"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_XS}px;
            font-weight: 600;
        }}
        QLabel[role="kpi-spark-label"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 600;
            letter-spacing: 0.05em;
        }}
        QLabel[role="analytics-section-icon"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: 14px;
        }}
        QLabel[role="analytics-section-title"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.04em;
        }}
        QLabel[role="chart-card-title"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 600;
            padding-bottom: 2px;
        }}
        QLabel[role="kpi-card-label"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
            letter-spacing: 0.05em;
        }}
        QLabel[role="row-label"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
        }}
        QLabel[role="doc-days"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_SM}px;
        }}
        QLabel[role="list-more"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
            font-weight: 600;
            padding-top: 8px;
        }}
        QLabel[role="doc-expiry-header"] {{
            color: {COLOR_WARNING_TEXT};
            font-size: 13px;
            font-weight: 600;
            padding-bottom: 8px;
        }}
        QLabel[role="success-note"] {{
            color: {COLOR_SUCCESS_TEXT};
            font-size: {FONT_SIZE_BASE}px;
            padding: 8px;
            background-color: {COLOR_BG_ELEVATED};
            border-radius: {RADIUS_CHIP}px;
        }}
        QLabel[role="warning-note"] {{
            color: {COLOR_WARNING_TEXT};
            font-size: {FONT_SIZE_SM}px;
            padding: 4px 8px;
            background-color: {COLOR_WARNING_SUBTLE};
            border-radius: {RADIUS_CHIP}px;
        }}
        QLabel[role="period-label"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
            letter-spacing: 0.08em;
            padding-right: 8px;
        }}
        QLabel[role="dialog-title"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel[role="insight-icon"] {{
            font-size: 14px;
        }}
        QLabel[role="insight-icon"][state="warning"] {{
            color: {COLOR_WARNING_TEXT};
        }}
        QLabel[role="insight-icon"][state="info"] {{
            color: {COLOR_INFO_TEXT};
        }}
        QLabel[role="delay-status"] {{
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
        }}
        QLabel[role="delay-status"][state="ok"] {{
            color: {COLOR_SUCCESS_DEFAULT};
        }}
        QLabel[role="delay-status"][state="warn"] {{
            color: {COLOR_WARNING_DEFAULT};
        }}
        QLabel[role="delay-status"][state="bad"] {{
            color: {COLOR_ERROR_DEFAULT};
        }}
        QFrame[role="insight-banner"][state="warning"] {{
            background: {COLOR_WARNING_SUBTLE};
            border-left: 3px solid {COLOR_WARNING_DEFAULT};
            border-radius: 4px;
            padding: 0px;
        }}
        QFrame[role="insight-banner"][state="info"] {{
            background: {COLOR_INFO_SUBTLE};
            border-left: 3px solid {COLOR_INFO_DEFAULT};
            border-radius: 4px;
            padding: 0px;
        }}
        QFrame[role="delay-bar"] {{
            border-radius: {RADIUS_CHIP}px;
        }}
        QFrame[role="delay-bar"][state="ok"] {{
            background: {COLOR_SUCCESS_DEFAULT};
        }}
        QFrame[role="delay-bar"][state="warn"] {{
            background: {COLOR_WARNING_DEFAULT};
        }}
        QFrame[role="delay-bar"][state="bad"] {{
            background: {COLOR_ERROR_DEFAULT};
        }}
        QScrollArea[role="analytics-scroll"] {{
            background: {COLOR_BG_BASE};
            border: none;
            padding-right: 6px;
        }}
        QScrollArea[role="analytics-scroll"] QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 0px;
            border-radius: 6px;
        }}
        QScrollArea[role="analytics-scroll"] QScrollBar::handle:vertical {{
            background: {COLOR_BORDER_STRONG};
            border-radius: 6px;
            min-height: 40px;
            margin: 2px;
        }}
        QScrollArea[role="analytics-scroll"] QScrollBar::handle:vertical:hover {{
            background: {COLOR_ACCENT_PRIMARY};
        }}
        QPushButton[role="analytics-grid-btn"] {{
            background: transparent;
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: 4px;
            padding: 2px;
        }}
        QPushButton[role="analytics-grid-btn"]:hover {{
            background: {COLOR_BG_OVERLAY};
            border-color: {COLOR_BORDER_MEDIUM};
        }}
        QPushButton[role="analytics-grid-btn"]:focus,
        QPushButton[role="analytics-grid-btn"]:focus:!hover {{
            border: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QFrame[role="hairline"] {{
            background: {COLOR_BORDER_SUBTLE};
            max-height: 1px;
            min-height: 1px;
        }}
        QFrame[role="kpi-spark-card"] {{
            background: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 8px;
        }}
        QFrame[role="kpi-spark-card"][state="overlay"] {{
            background: {COLOR_BG_OVERLAY};
            border-color: {COLOR_BG_ELEVATED};
        }}
        QFrame[role="kpi-spark-card"][state="warning"] {{
            background: {COLOR_WARNING_SUBTLE};
            border: 1px solid {COLOR_WARNING_DEFAULT};
        }}
        QFrame[role="panel-outline"] {{
            background: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BG_OVERLAY};
            border-radius: 6px;
        }}
        QFrame[role="list-panel"] {{
            background: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CHIP}px;
        }}
        QFrame[role="hover-row"]:hover {{
            background: {COLOR_BG_ELEVATED};
        }}
        QFrame[role="activity-cell"] {{
            background: {COLOR_BG_OVERLAY};
            border-radius: {RADIUS_CHIP}px;
        }}
        QFrame[role="activity-cell"][state="active"] {{
            background: {COLOR_ACCENT_PRIMARY};
        }}
        QTabWidget[role="analytics-tabs"]::pane {{
            border: none;
            background: {COLOR_BG_ELEVATED};
        }}
        QTabWidget[role="analytics-tabs"] QTabBar::tab {{
            background: transparent;
            color: {COLOR_TEXT_TERTIARY};
            padding: 8px 16px;
            border: none;
            font-size: 13px;
        }}
        QTabWidget[role="analytics-tabs"] QTabBar::tab:selected {{
            color: {COLOR_TEXT_PRIMARY};
            border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
        }}
        QTabWidget[role="analytics-tabs"] QTabBar::tab:hover {{
            color: {COLOR_TEXT_PRIMARY};
        }}
        QWidget#period-strip {{
            background: {COLOR_BG_ELEVATED};
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QWidget[role="pill-group"] {{
            background: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 6px;
        }}
        QPushButton[role="period-pill"] {{
            background: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-radius: 4px;
            padding: 4px 12px;
            font-size: {FONT_SIZE_BASE}px;
        }}
        QPushButton[role="period-pill"]:hover {{
            color: {COLOR_TEXT_PRIMARY};
        }}
        QPushButton[role="period-pill"]:checked {{
            background: {COLOR_ACCENT_PRIMARY};
            color: white;
            font-weight: 600;
        }}
        QPushButton[role="period-pill"]:focus,
        QPushButton[role="period-pill"]:focus:!hover {{
            border: none;
        }}
        QPushButton[role="analytics-refresh"] {{
            background: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 14px;
        }}
        QPushButton[role="analytics-refresh"]:hover {{
            background: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QPushButton[role="analytics-refresh"]:focus,
        QPushButton[role="analytics-refresh"]:focus:!hover {{
            border: 1px solid {COLOR_BORDER_MEDIUM};
        }}
        QProgressBar[role="margin-bar"] {{
            background: {COLOR_TEXT_TERTIARY}22;
            border: none;
            border-radius: {RADIUS_CHIP}px;
        }}
        QProgressBar[role="margin-bar"]::chunk {{
            background: {COLOR_ACCENT_PRIMARY};
            border-radius: {RADIUS_CHIP}px;
        }}
        QFrame[role="accent-panel"] {{
            background: {COLOR_ACCENT_PRIMARY}0D;
            border: 1px solid {COLOR_ACCENT_PRIMARY}33;
            border-radius: 6px;
            padding: 8px;
        }}
        QFrame#chart-card {{
            background: transparent;
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 8px;
        }}
        """

    # ── Dialog cluster (Phase 4) ───────────────────────────────────────────
    # Paired-assignment dialog, dispatch detail drawer, share-route dialog,
    # automail dialogs (variable picker / template / schedule editor) and
    # the country-exclusions dialog.  Buttons keep explicit ``:focus`` /
    # ``:focus:!hover`` re-declarations so the global accent focus ring
    # reproduces what the removed inline stylesheets overrode.

    @classmethod
    def _dialogs_qss(cls) -> str:
        return f"""
        QLabel[role="accent-hint"] {{
            color: {COLOR_ACCENT_PRIMARY};
            font-size: {FONT_SIZE_BASE}px;
        }}
        QLabel[role="item-status"] {{
            color: {COLOR_WARNING_DEFAULT};
            font-size: {FONT_SIZE_SM}px;
        }}
        QLabel[role="url-label"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
        }}
        QLabel[role="share-url-field"] {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_SM}px;
            background: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CHIP}px;
            padding: {SPACE_1}px {_P2}px;
        }}
        QLabel[role="helper-italic"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-style: italic;
            font-size: {FONT_SIZE_SM}px;
        }}
        QLabel[role="list-empty"] {{
            color: {COLOR_TEXT_TERTIARY};
            font-size: {FONT_SIZE_SM}px;
            padding: 8px;
        }}
        QLabel[role="error-banner"] {{
            background-color: {COLOR_ERROR_DEFAULT};
            color: {TEXT_WHITE};
            border-radius: 6px;
            padding: 8px 12px;
        }}
        QLabel[role="severity-chip"] {{
            color: {TEXT_WHITE};
            border-radius: {RADIUS_CHIP}px;
            padding: 1px 4px;
        }}
        QLabel[role="severity-chip"][state="critical"] {{
            background-color: {COLOR_ERROR_DEFAULT};
        }}
        QLabel[role="severity-chip"][state="warning"] {{
            background-color: {COLOR_WARNING_DEFAULT};
        }}
        QLabel[role="severity-chip"][state="info"] {{
            background-color: {COLOR_INFO_DEFAULT};
        }}
        QFrame[role="surface-md"] {{
            background-color: {COLOR_BG_ELEVATED};
            border-radius: {RADIUS_INPUT}px;
        }}
        QWidget[role="action-bar"] {{
            background-color: {COLOR_BG_OVERLAY};
        }}
        QScrollArea[role="elevated-surface"] {{
            background-color: {COLOR_BG_ELEVATED};
        }}
        QWidget[role="elevated-surface"] {{
            background-color: {COLOR_BG_ELEVATED};
        }}
        QFrame[role="item-row"] {{
            background-color: {COLOR_BG_ELEVATED};
            border-radius: {RADIUS_CHIP}px;
        }}
        QFrame[role="item-row"][state="selected"] {{
            background-color: {COLOR_ACCENT_SUBTLE};
        }}
        QFrame[role="avail-dot"] {{
            border-radius: {RADIUS_CHIP}px;
        }}
        QFrame[role="avail-dot"][state="ok"] {{
            background-color: {COLOR_SUCCESS_DEFAULT};
        }}
        QFrame[role="avail-dot"][state="bad"] {{
            background-color: {COLOR_ERROR_DEFAULT};
        }}
        QWidget[role="alert-item"] {{
            background-color: {COLOR_BG_OVERLAY};
            border-radius: 4px;
        }}
        QWidget[role="detail-drawer"] {{
            background-color: {COLOR_BG_ELEVATED};
            border-left: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QPushButton[role="close-btn"] {{
            border: none;
            border-radius: 4px;
            background: transparent;
        }}
        QPushButton[role="close-btn"]:hover {{
            background-color: {COLOR_ACCENT_HOVER};
        }}
        QPushButton[role="close-btn"]:focus,
        QPushButton[role="close-btn"]:focus:!hover {{
            border: none;
            background: transparent;
        }}
        QDialog[role="dialog-outlined"] {{
            background: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: 8px;
        }}
        QScrollArea[role="thin-scroll"] {{
            background: transparent;
            border: none;
        }}
        QScrollArea[role="thin-scroll"] QScrollBar:vertical {{
            width: 4px;
            background: transparent;
        }}
        QScrollArea[role="thin-scroll"] QScrollBar::handle:vertical {{
            background: {COLOR_BORDER_MEDIUM};
            border-radius: 2px;
        }}
        QCheckBox[role="country-check"] {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_BASE}px;
            spacing: 8px;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        QCheckBox[role="country-check"]:hover {{
            color: {COLOR_TEXT_PRIMARY};
            background: {COLOR_BG_HOVER};
        }}
        QCheckBox[role="country-check"]::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {COLOR_BORDER_MEDIUM};
            background: {COLOR_BG_OVERLAY};
        }}
        QCheckBox[role="country-check"]::indicator:checked {{
            background: {COLOR_ACCENT_PRIMARY};
            border-color: {COLOR_ACCENT_PRIMARY};
        }}
        QCheckBox[role="country-check"]::indicator:hover {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}
        QPushButton[role="dialog-btn"] {{
            background: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_SUBTLE};
            border-radius: 4px;
            padding: 6px 16px;
            font-size: {FONT_SIZE_BASE}px;
        }}
        QPushButton[role="dialog-btn"]:hover {{
            background: {COLOR_BG_HOVER};
        }}
        QPushButton[role="dialog-btn"]:focus,
        QPushButton[role="dialog-btn"]:focus:!hover {{
            border: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QPushButton[role="variable-chip"] {{
            background: {COLOR_ACCENT_SUBTLE};
            color: {COLOR_ACCENT_PRIMARY};
            border: none;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 500;
        }}
        QPushButton[role="variable-chip"]:hover {{
            background: {COLOR_ACCENT_PRIMARY};
            color: white;
        }}
        QPushButton[role="variable-chip"]:focus,
        QPushButton[role="variable-chip"]:focus:!hover {{
            border: none;
        }}
        QPushButton[variant="sm-accent"] {{
            background: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
        }}
        QPushButton[variant="sm-accent"]:hover {{
            background: {COLOR_ACCENT_HOVER};
        }}
        QPushButton[variant="sm-accent"]:pressed {{
            background: {COLOR_ACCENT_HOVER};
        }}
        QPushButton[variant="sm-accent"]:focus,
        QPushButton[variant="sm-accent"]:focus:!hover {{
            border: none;
        }}
        QPushButton[role="sm-outline-solid"] {{
            background: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
            font-weight: 600;
            padding: 0 12px;
        }}
        QPushButton[role="sm-outline-solid"]:hover {{
            background: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QPushButton[role="sm-outline-solid"]:focus,
        QPushButton[role="sm-outline-solid"]:focus:!hover {{
            border: 1px solid {COLOR_BORDER_MEDIUM};
        }}
        QPushButton[role="dialog-outline"] {{
            background: transparent;
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CHIP}px;
            font-size: {FONT_SIZE_SM}px;
        }}
        QPushButton[role="dialog-outline"]:hover {{
            background: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QPushButton[role="dialog-outline"]:focus,
        QPushButton[role="dialog-outline"]:focus:!hover {{
            border: 1px solid {COLOR_BORDER_MEDIUM};
        }}
        """
