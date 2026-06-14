"""PySide6 compatibility layer for the existing ``ui.styles.Theme`` API.

Existing view modules reference ``Theme.BG``, ``Theme.ACCENT``, etc. This module
keeps those constants alive while redirecting theme application to the global
QSS engine in ``ui.qt_theme``.

This file is meant to be imported by PySide6 view modules in place of
``ui.styles`` once migration begins. The CustomTkinter ``ui/styles.py`` file
remains untouched so the legacy ``main.py`` continues to work.
"""

from ui.theme import COLORS, S
from ui.qt_theme import QtTheme


class Theme:
    """Drop-in replacement for ``ui.styles.Theme`` in the PySide6 branch."""

    # ── Backgrounds ────────────────────────────────────────────────────────────
    BG = COLORS["bg_base"]
    SURFACE = COLORS["bg_surface"]
    SURFACE2 = COLORS["bg_elevated"]
    SURFACE3 = COLORS["bg_elevated"]
    INPUT_BG = COLORS["bg_input"]
    INPUT_HOVER = COLORS["bg_elevated"]

    # ── Text ───────────────────────────────────────────────────────────────────
    TEXT = COLORS["text_primary"]
    MUTED = COLORS["text_secondary"]

    # ── Accents ────────────────────────────────────────────────────────────────
    ACCENT = COLORS["accent"]
    ACCENT_HOVER = COLORS["accent_hover"]
    ACCENT_SUCCESS = COLORS["success"]
    ACCENT_PRIMARY = ACCENT
    ACCENT_SECONDARY = ACCENT_HOVER
    HOVER = ACCENT_HOVER

    # ── Borders ────────────────────────────────────────────────────────────────
    BORDER = COLORS["border"]
    BORDER_FOCUS = COLORS["border_focus"]

    # ── Semantic colors ────────────────────────────────────────────────────────
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

    # ── Cards / effects ────────────────────────────────────────────────────────
    CARD_BG = COLORS["bg_surface"]
    CARD_ACCENT = COLORS["accent"]
    GLOW = COLORS["accent"]

    # ── Fonts (CSS string form for Qt) ─────────────────────────────────────────
    FONT_MAIN = "13px 'IBM Plex Sans', 'Segoe UI', sans-serif"
    FONT_BOLD = "bold 13px 'IBM Plex Sans', 'Segoe UI', sans-serif"
    FONT_TITLE = "bold 20px 'IBM Plex Sans', 'Segoe UI', sans-serif"

    # ── Spacing ────────────────────────────────────────────────────────────────
    PAD_X = S["4"]
    PAD_Y = S["2"]

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
