"""PySide6 compatibility layer for the existing ``ui.styles.Theme`` API.

Existing view modules reference ``Theme.BG``, ``Theme.ACCENT``, etc. This module
keeps those constants alive while redirecting theme application to the global
QSS engine in ``ui.qt_theme``.

This file is meant to be imported by PySide6 view modules in place of
``ui.styles`` once migration begins. The CustomTkinter ``ui/styles.py`` file
remains untouched so the legacy ``main.py`` continues to work.
"""

from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_STRONG,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_INFO_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING_DEFAULT,
    SP,
)
from ui.theme_engine import QtTheme

class Theme:
    """Drop-in replacement for ``ui.styles.Theme`` in the PySide6 branch.

    .. deprecated::
       This class is a compatibility shim. New code should import colors,
       spacing, and font values directly from ``ui.theme`` (COLORS, S, FONTS).
       This shim will be removed in a future refactor.
    """

    # ── Backgrounds ────────────────────────────────────────────────────────────
    BG = COLOR_BG_BASE
    SURFACE = COLOR_BG_ELEVATED
    SURFACE2 = COLOR_BG_OVERLAY
    SURFACE3 = COLOR_BG_OVERLAY  # Intentionally same as SURFACE2 per current design
    INPUT_BG = COLOR_BG_OVERLAY
    INPUT_HOVER = COLOR_BG_HOVER

    # ── Text ───────────────────────────────────────────────────────────────────
    TEXT = COLOR_TEXT_PRIMARY
    MUTED = COLOR_TEXT_SECONDARY

    # ── Accents ────────────────────────────────────────────────────────────────
    ACCENT = COLOR_ACCENT_PRIMARY
    ACCENT_HOVER = COLOR_ACCENT_PRIMARY  # hover approximates to primary
    ACCENT_SUCCESS = COLOR_SUCCESS_DEFAULT
    ACCENT_PRIMARY = ACCENT
    ACCENT_SECONDARY = ACCENT_HOVER
    HOVER = ACCENT_HOVER

    # ── Borders ────────────────────────────────────────────────────────────────
    BORDER = COLOR_BORDER_SUBTLE
    BORDER_FOCUS = COLOR_ACCENT_PRIMARY

    # ── Semantic colors ────────────────────────────────────────────────────────
    DANGER = COLOR_ERROR_DEFAULT
    WARNING = COLOR_WARNING_DEFAULT
    SUCCESS = COLOR_SUCCESS_DEFAULT
    GREEN = COLOR_SUCCESS_DEFAULT
    BLUE = COLOR_INFO_DEFAULT
    INFO = BLUE
    ORANGE = COLOR_WARNING_DEFAULT
    YELLOW = COLOR_WARNING_DEFAULT
    PURPLE_SOFT = COLOR_ACCENT_SUBTLE
    EXCEL = COLOR_SUCCESS_DEFAULT

    # ── Cards / effects ────────────────────────────────────────────────────────
    CARD_BG = COLOR_BG_ELEVATED
    CARD_ACCENT = COLOR_ACCENT_PRIMARY
    GLOW = COLOR_ACCENT_PRIMARY

    # ── Fonts (CSS string form for Qt) ─────────────────────────────────────────
    # NOTE: These are hardcoded CSS strings because ui.theme.FONTS stores
    # (family, size, weight) tuples. They should be migrated to derive from
    # ui.theme.FONTS in a future refactor.
    FONT_MAIN = "13px 'IBM Plex Sans', 'Segoe UI', sans-serif"
    FONT_BOLD = "bold 13px 'IBM Plex Sans', 'Segoe UI', sans-serif"
    FONT_TITLE = "bold 20px 'IBM Plex Sans', 'Segoe UI', sans-serif"

    # ── Spacing ────────────────────────────────────────────────────────────────
    PAD_X = SP["4"]
    PAD_Y = SP["2"]

    _applied = False

    @classmethod
    def apply(cls, root=None) -> None:
        """Apply the global dark theme to the running QApplication.

        The ``root`` argument is accepted for API compatibility with the
        CustomTkinter ``Theme.apply(root)`` signature but is ignored in Qt,
        because QSS is applied globally via ``QApplication``.
        """
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return
        QtTheme.apply(app)
        cls._applied = True

    @classmethod
    def style_option_menu(cls, widget) -> None:
        """No-op compatibility shim for ``Theme.style_option_menu``.

        In the PySide6 branch option menus are replaced by ``QComboBox``,
        which is already styled by the global QSS.
        """
        pass
