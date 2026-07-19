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

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.design_tokens import (
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BG_SELECTED,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_STRONG,
    COLOR_BORDER_SUBTLE,
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
    RADIUS_SM as RADIUS_CHIP,
    RADIUS_MD as RADIUS_INPUT,
    RADIUS_LG as RADIUS_CARD,
    RADIUS_MD as RADIUS_BUTTON,
    SPACE_2 as _P2,
    SPACE_4 as _P4,
)

# ──────────────────────────────────────────────────────────────────────────────
# TYPOGRAPHY
# ──────────────────────────────────────────────────────────────────────────────

FONT_FAMILIES = {
    "sans": "'IBM Plex Sans', 'Segoe UI', 'Microsoft YaHei', sans-serif",
    "hero": "'Impact', 'Arial Black', 'Helvetica Neue', sans-serif",
    "mono": "'IBM Plex Mono', 'Consolas', 'Courier New', monospace",
}

FONT_SIZES = {
    "display": 28,
    "h1": 20,
    "h2": 16,
    "h3": 13,
    "body": 13,
    "body_bold": 13,
    "small": 12,
    "label": 11,
    "mono": 13,
    "mono_lg": 20,
    "mono_xl": 32,
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
        app.setFont(QFont("IBM Plex Sans", FONT_SIZES["body"]))

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

        QWidget:disabled {{
            color: {COLOR_TEXT_TERTIARY};
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
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {COLOR_ACCENT_SUBTLE};
            color: {COLOR_TEXT_PRIMARY};
        }}

        QTableWidget::item:hover, QTableView::item:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QHeaderView {{
            background-color: {COLOR_BG_BASE};
        }}

        QHeaderView::section {{
            background-color: {COLOR_BG_BASE};
            color: {COLOR_TEXT_TERTIARY};
            padding: 8px 12px;
            border: none;
            border-bottom: 1px solid {COLOR_BORDER_MEDIUM};
            font-weight: 600;
            font-size: {cls._fs("label")}px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        QHeaderView::section:hover {{
            background-color: {COLOR_BG_OVERLAY};
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
            width: 8px;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {COLOR_BORDER_MEDIUM};
            min-height: 40px;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {COLOR_BORDER_STRONG};
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
            height: 8px;
            border-radius: 4px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {COLOR_BORDER_MEDIUM};
            min-width: 40px;
            border-radius: 4px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {COLOR_BORDER_STRONG};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            background: none;
            width: 0px;
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

        QTabBar::tab {{
            background-color: {COLOR_BG_OVERLAY};
            color: {COLOR_TEXT_SECONDARY};
            border: none;
            border-top-left-radius: {RADIUS_CHIP}px;
            border-top-right-radius: {RADIUS_CHIP}px;
            padding: 10px 18px;
            margin-right: 2px;
            font-weight: bold;
        }}

        QTabBar::tab:selected {{
            background-color: {COLOR_ACCENT_PRIMARY};
            color: {TEXT_WHITE};
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {COLOR_BG_OVERLAY};
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

        QFrame[role="card"] {{
            background-color: {COLOR_BG_ELEVATED};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="card-elevated"] {{
            background-color: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CARD}px;
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
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_CARD}px;
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
            padding: 6px 20px;
            border-radius: {RADIUS_CHIP}px;
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

        QDialogButtonBox QPushButton {{
            min-width: 80px;
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
        }}

        QFrame[role="nav-item"]:hover {{
            background-color: {COLOR_BG_OVERLAY};
        }}

        QFrame[role="nav-item"][state="active"] {{
            background-color: {COLOR_BG_OVERLAY};
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
            font-size: 18px;
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
            font-size: 14px;
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
            border-bottom: 1px solid {COLOR_BORDER_MEDIUM};
        }}

        QFrame[role="top-bar-divider"] {{
            background-color: {COLOR_BORDER_MEDIUM};
            max-height: 1px;
            min-height: 1px;
        }}

        QLabel[role="breadcrumb"] {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            font-size: {cls._fs("body")}px;
            font-weight: bold;
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
