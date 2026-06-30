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

from ui.design_tokens import TEXT_WHITE
from ui.theme import COLORS, RADIUS_BUTTON, RADIUS_CARD, RADIUS_CHIP, RADIUS_INPUT, S

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
        return FONT_SIZES.get(role, FONT_SIZES.get("body", 13))

    @classmethod
    def _px(cls, key: str) -> int:
        return S[key]

    # ── Base / reset ──────────────────────────────────────────────────────────

    @classmethod
    def _base_qss(cls) -> str:
        return f"""
        QWidget {{
            background-color: {COLORS["bg_base"]};
            color: {COLORS["text_primary"]};
            font-family: {cls._ff("sans")};
            font-size: {cls._fs("body")}px;
            outline: none;
        }}

        QMainWindow, QDialog, QMessageBox {{
            background-color: {COLORS["bg_base"]};
        }}

        QWidget:disabled {{
            color: {COLORS["text_muted"]};
        }}
        """

    # ── Typography ────────────────────────────────────────────────────────────

    @classmethod
    def _typography_qss(cls) -> str:
        return f"""
        QLabel {{
            background-color: transparent;
            color: {COLORS["text_primary"]};
        }}

        QLabel[fontRole="muted"] {{
            color: {COLORS["text_muted"]};
        }}

        QLabel[fontRole="secondary"] {{
            color: {COLORS["text_secondary"]};
        }}

        QLabel[fontRole="accent"] {{
            color: {COLORS["text_accent"]};
        }}

        QLabel[fontRole="success"] {{
            color: {COLORS["text_success"]};
        }}

        QLabel[fontRole="warning"] {{
            color: {COLORS["text_warning"]};
        }}

        QLabel[fontRole="danger"] {{
            color: {COLORS["text_danger"]};
        }}

        QLabel[fontRole="label"] {{
            color: {COLORS["text_muted"]};
            font-size: {cls._fs("label")}px;
            text-transform: uppercase;
        }}

        QLabel[fontRole="small"] {{
            font-size: {cls._fs("small")}px;
        }}

        QLabel[fontRole="helper"] {{
            color: {COLORS["text_muted"]};
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
            color: {COLORS["text_primary"]};
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
            color: {COLORS["accent"]};
            font-size: {cls._fs("body")}px;
            font-weight: bold;
        }}

        QLabel[fontRole="kpi-title"] {{
            color: {COLORS["text_muted"]};
            font-size: {cls._fs("label")}px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        QLabel[fontRole="kpi-value"] {{
            color: {COLORS["text_primary"]};
            font-size: {cls._fs("mono_lg")}px;
            font-family: {cls._ff("mono")};
            font-weight: bold;
        }}

        QLabel[class="page-title"] {{
            font-size: 20px;
            font-weight: 600;
            color: {COLORS["text_primary"]};
        }}

        QLabel[class="section-title"] {{
            font-size: 13px;
            font-weight: 600;
            color: {COLORS["text_primary"]};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        QLabel[class="field-label"] {{
            font-size: 11px;
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        QLabel[class="kpi-value"] {{
            font-size: 22px;
            font-weight: 700;
            font-family: {cls._ff("mono")};
            color: {COLORS["text_primary"]};
        }}

        QLabel[class="kpi-label"] {{
            font-size: 11px;
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
        }}
        """

    # ── Buttons ─────────────────────────────────────────────────────────────────

    @classmethod
    def _button_qss(cls) -> str:
        return f"""
        QPushButton {{
            background-color: {COLORS["accent"]};
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
            background-color: {COLORS["accent_hover"]};
        }}

        QPushButton:pressed {{
            background-color: {COLORS["accent"]};
        }}

        QPushButton:disabled {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_muted"]};
        }}

        QPushButton[variant="secondary"] {{
            background-color: transparent;
            color: {COLORS["text_secondary"]};
            border: 1px solid {COLORS["border"]};
        }}

        QPushButton[variant="secondary"]:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QPushButton[variant="danger"] {{
            background-color: transparent;
            color: {COLORS["text_danger"]};
            border: 1px solid {COLORS["danger_dim"]};
        }}

        QPushButton[variant="danger"]:hover {{
            background-color: {COLORS["danger_dim"]};
        }}

        QPushButton[variant="ghost"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            border: none;
        }}

        QPushButton[variant="ghost"]:hover {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
        }}

        QPushButton[variant="success"] {{
            background-color: {COLORS["success_dim"]};
            color: {COLORS["text_success"]};
            border: 1px solid {COLORS["success_dim"]};
        }}

        QPushButton[variant="success"]:hover {{
            background-color: {COLORS["success_dim"]};
            border-color: {COLORS["text_success"]};
        }}
        """

    # ── Inputs ──────────────────────────────────────────────────────────────────

    @classmethod
    def _input_qss(cls) -> str:
        return f"""
        QLineEdit, QPlainTextEdit, QTextEdit, QDateEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {COLORS["bg_input"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_INPUT}px;
            padding: 6px 10px;
            font-family: {cls._ff("sans")};
            font-size: {cls._fs("body")}px;
            selection-background-color: {COLORS["accent"]};
            selection-color: {TEXT_WHITE};
        }}

        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
        QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {COLORS["border_focus"]};
        }}

        QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
        QDateEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_muted"]};
        }}

        QPlainTextEdit, QTextEdit {{
            padding: 8px;
        }}

        QLineEdit::placeholder, QPlainTextEdit::placeholder {{
            color: {COLORS["text_muted"]};
        }}

        QDateEdit::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: 1px solid {COLORS["border"]};
            border-top-right-radius: {RADIUS_INPUT}px;
            border-bottom-right-radius: {RADIUS_INPUT}px;
        }}

        QDateEdit::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {COLORS["text_secondary"]};
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
            color: {COLORS["text_primary"]};
            spacing: {cls._px("2")}px;
            font-size: {cls._fs("body")}px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {COLORS["border"]};
            border-radius: 4px;
            background-color: {COLORS["bg_input"]};
        }}

        QCheckBox::indicator:hover {{
            border-color: {COLORS["border_hover"]};
        }}

        QCheckBox::indicator:checked {{
            background-color: {COLORS["accent"]};
            border-color: {COLORS["accent"]};
            image: none;
        }}

        QCheckBox::indicator:disabled {{
            background-color: {COLORS["bg_elevated"]};
            border-color: {COLORS["border"]};
        }}
        """

    @classmethod
    def _radiobutton_qss(cls) -> str:
        return f"""
        QRadioButton {{
            background-color: transparent;
            color: {COLORS["text_primary"]};
            spacing: {cls._px("2")}px;
            font-size: {cls._fs("body")}px;
        }}

        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {COLORS["border"]};
            border-radius: 9px;
            background-color: {COLORS["bg_input"]};
        }}

        QRadioButton::indicator:hover {{
            border-color: {COLORS["border_hover"]};
        }}

        QRadioButton::indicator:checked {{
            background-color: {COLORS["accent"]};
            border-color: {COLORS["accent"]};
        }}
        """

    # ── ComboBox ────────────────────────────────────────────────────────────────

    @classmethod
    def _combobox_qss(cls) -> str:
        return f"""
        QComboBox {{
            background-color: {COLORS["bg_input"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_INPUT}px;
            padding: 6px 10px;
            min-height: 38px;
            font-size: {cls._fs("body")}px;
        }}

        QComboBox:focus {{
            border-color: {COLORS["border_focus"]};
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: 1px solid {COLORS["border"]};
            border-top-right-radius: {RADIUS_INPUT}px;
            border-bottom-right-radius: {RADIUS_INPUT}px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {COLORS["text_secondary"]};
            width: 0px;
            height: 0px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            selection-background-color: {COLORS["bg_elevated"]};
            selection-color: {COLORS["text_primary"]};
            outline: none;
        }}

        QComboBox QAbstractItemView::item {{
            padding: 6px 10px;
            min-height: 28px;
        }}

        QComboBox QAbstractItemView::item:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QComboBox QAbstractItemView::item:selected {{
            background-color: {COLORS["accent_dim"]};
            color: {COLORS["text_accent"]};
        }}
        """

    # ── SpinBox ─────────────────────────────────────────────────────────────────

    @classmethod
    def _spinbox_qss(cls) -> str:
        return f"""
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {COLORS["bg_elevated"]};
            border: 1px solid {COLORS["border"]};
            width: 20px;
        }}

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {COLORS["border_hover"]};
        }}
        """

    # ── Tables ──────────────────────────────────────────────────────────────────

    @classmethod
    def _table_qss(cls) -> str:
        return f"""
        QTableWidget, QTableView {{
            background-color: {COLORS["bg_surface"]};
            alternate-background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_primary"]};
            gridline-color: {COLORS["border"]};
            border: none;
            font-size: {cls._fs("body")}px;
        }}

        QTableWidget::item, QTableView::item {{
            padding: 6px 8px;
            border: none;
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {COLORS["accent_dim"]};
            color: {COLORS["text_primary"]};
        }}

        QTableWidget::item:hover, QTableView::item:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QHeaderView {{
            background-color: {COLORS["bg_base"]};
        }}

        QHeaderView::section {{
            background-color: {COLORS["bg_base"]};
            color: {COLORS["text_muted"]};
            padding: 8px 12px;
            border: none;
            border-bottom: 1px solid {COLORS["border"]};
            font-weight: 600;
            font-size: {cls._fs("label")}px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        QHeaderView::section:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QTableCornerButton::section {{
            background-color: {COLORS["bg_base"]};
            border: none;
        }}
        """

    # ── Trees ───────────────────────────────────────────────────────────────────

    @classmethod
    def _tree_qss(cls) -> str:
        return f"""
        QTreeWidget, QTreeView {{
            background-color: {COLORS["bg_surface"]};
            alternate-background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_primary"]};
            border: none;
            outline: none;
        }}

        QTreeWidget::item, QTreeView::item {{
            padding: 6px 8px;
            border: none;
        }}

        QTreeWidget::item:selected, QTreeView::item:selected {{
            background-color: {COLORS["accent_dim"]};
            color: {COLORS["text_primary"]};
        }}

        QTreeWidget::item:hover, QTreeView::item:hover {{
            background-color: {COLORS["bg_elevated"]};
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
            background-color: {COLORS["bg_base"]};
            width: 8px;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {COLORS["border"]};
            min-height: 40px;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {COLORS["border_hover"]};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            background: none;
            height: 0px;
        }}

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            background-color: {COLORS["bg_base"]};
            height: 8px;
            border-radius: 4px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {COLORS["border"]};
            min-width: 40px;
            border-radius: 4px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {COLORS["border_hover"]};
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
            background-color: {COLORS["bg_base"]};
            top: -1px;
        }}

        QTabBar::tab {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
            border: none;
            border-top-left-radius: {RADIUS_CHIP}px;
            border-top-right-radius: {RADIUS_CHIP}px;
            padding: 10px 18px;
            margin-right: 2px;
            font-weight: bold;
        }}

        QTabBar::tab:selected {{
            background-color: {COLORS["accent"]};
            color: {TEXT_WHITE};
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {COLORS["bg_input"]};
            color: {COLORS["text_primary"]};
        }}

        QTabBar::tab:disabled {{
            color: {COLORS["text_muted"]};
        }}
        """

    # ── ProgressBar ─────────────────────────────────────────────────────────────

    @classmethod
    def _progressbar_qss(cls) -> str:
        return f"""
        QProgressBar {{
            background-color: {COLORS["bg_elevated"]};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            text-align: center;
            color: {COLORS["text_primary"]};
            font-size: {cls._fs("small")}px;
        }}

        QProgressBar::chunk {{
            background-color: {COLORS["accent"]};
            border-radius: {RADIUS_CHIP}px;
        }}
        """

    # ── GroupBox / Frame ────────────────────────────────────────────────────────

    @classmethod
    def _groupbox_qss(cls) -> str:
        return f"""
        QGroupBox {{
            background-color: {COLORS["bg_surface"]};
            border: 1px solid {COLORS["border"]};
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
            color: {COLORS["text_secondary"]};
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
            background-color: {COLORS["bg_surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="card-elevated"] {{
            background-color: {COLORS["bg_elevated"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="input"] {{
            background-color: {COLORS["bg_input"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_INPUT}px;
        }}

        QFrame[role="divider"] {{
            background-color: {COLORS["border"]};
            max-height: 1px;
            min-height: 1px;
        }}

        QFrame[role="accent-bar"] {{
            background-color: {COLORS["accent"]};
            max-width: 3px;
            min-width: 3px;
            border-radius: 2px;
        }}

        QFrame[role="section-line"] {{
            background-color: {COLORS["border"]};
            max-height: 1px;
            min-height: 1px;
        }}

        QFrame[role="kpi-card"] {{
            background-color: {COLORS["bg_surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="chip-critical"] {{
            background-color: {COLORS["danger_dim"]};
            color: {COLORS["text_danger"]};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-warning"] {{
            background-color: {COLORS["warning_dim"]};
            color: {COLORS["text_warning"]};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-info"] {{
            background-color: {COLORS["info_dim"]};
            color: {COLORS["text_accent"]};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-success"] {{
            background-color: {COLORS["success_dim"]};
            color: {COLORS["text_success"]};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 2px 8px;
        }}

        QFrame[role="chip-neutral"] {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
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
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
            border-bottom: 1px solid {COLORS["border"]};
        }}

        QMenuBar::item:selected {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QMenu {{
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            padding: 4px;
        }}

        QMenu::item {{
            padding: 6px 20px;
            border-radius: {RADIUS_CHIP}px;
        }}

        QMenu::item:selected {{
            background-color: {COLORS["accent"]};
            color: {TEXT_WHITE};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {COLORS["border"]};
            margin: 4px 8px;
        }}
        """

    @classmethod
    def _tooltip_qss(cls) -> str:
        return f"""
        QToolTip {{
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
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
            background-color: {COLORS["bg_base"]};
        }}

        QMessageBox QLabel {{
            color: {COLORS["text_primary"]};
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
            background-color: {COLORS["border"]};
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
            background-color: {COLORS["bg_surface"]};
            border: none;
            border-right: 1px solid {COLORS["border"]};
        }}

        QFrame[role="nav-top-section"] {{
            background-color: transparent;
            border: none;
        }}

        QFrame[role="nav-divider"] {{
            background-color: {COLORS["border"]};
            max-height: 1px;
            min-height: 1px;
        }}

        QFrame[role="nav-item"] {{
            background-color: transparent;
            border: none;
            border-radius: 6px;
        }}

        QFrame[role="nav-item"]:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QFrame[role="nav-item"][state="active"] {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QFrame[role="nav-accent"] {{
            background-color: transparent;
            max-width: 3px;
            min-width: 3px;
            border-radius: 2px;
        }}

        QFrame[role="nav-item"][state="active"] QFrame[role="nav-accent"] {{
            background-color: {COLORS["accent"]};
        }}

        QLabel[role="nav-icon"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            font-family: "'Segoe UI Emoji', 'Segoe UI Symbol', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif";
            font-size: 18px;
        }}

        QFrame[role="nav-item"][state="active"] QLabel[role="nav-icon"] {{
            color: {COLORS["text_accent"]};
        }}

        QLabel[role="nav-label"] {{
            background-color: transparent;
            color: {COLORS["text_secondary"]};
            font-size: {cls._fs("body")}px;
        }}

        QFrame[role="nav-item"][state="active"] QLabel[role="nav-label"] {{
            color: {COLORS["text_primary"]};
            font-weight: bold;
        }}

        QLabel[role="nav-group-label"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            font-size: {cls._fs("label")}px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        QFrame[role="nav-monogram"] {{
            background-color: {COLORS["accent"]};
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
            color: {COLORS["text_primary"]};
            font-weight: bold;
            font-size: 13px;
        }}

        QLabel[role="nav-app-subtitle"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            font-size: 11px;
        }}

        QPushButton[role="nav-toggle"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            border: none;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 12px;
            font-weight: bold;
            min-width: 24px;
            min-height: 24px;
        }}

        QPushButton[role="nav-toggle"]:hover {{
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_secondary"]};
        }}
        """

    # ── Top bar ─────────────────────────────────────────────────────────────────

    @classmethod
    def _topbar_qss(cls) -> str:
        return f"""
        QFrame[role="top-bar"] {{
            background-color: {COLORS["bg_base"]};
            border: none;
            border-bottom: 1px solid {COLORS["border"]};
        }}

        QFrame[role="top-bar-divider"] {{
            background-color: {COLORS["border"]};
            max-height: 1px;
            min-height: 1px;
        }}

        QLabel[role="breadcrumb"] {{
            background-color: transparent;
            color: {COLORS["text_primary"]};
            font-size: {cls._fs("body")}px;
            font-weight: bold;
        }}

        QLabel[role="fuel-status"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("small")}px;
        }}

        QLabel[role="clock"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            font-family: {cls._ff("mono")};
            font-size: {cls._fs("body")}px;
        }}

        QLabel[role="bell"] {{
            background-color: transparent;
            color: {COLORS["text_muted"]};
            font-size: 16px;
        }}

        QLabel[role="bell"][alert="true"] {{
            color: {COLORS["text_danger"]};
        }}

        QLabel[role="badge"] {{
            background-color: {COLORS["danger"]};
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
            background-color: {COLORS["bg_surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_CARD}px;
        }}

        QCalendarWidget QWidget {{
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
        }}

        QCalendarWidget QToolButton {{
            background-color: transparent;
            color: {COLORS["text_primary"]};
            border: none;
            border-radius: {RADIUS_CHIP}px;
            padding: 4px 8px;
            font-weight: bold;
        }}

        QCalendarWidget QToolButton:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QCalendarWidget QMenu {{
            background-color: {COLORS["bg_surface"]};
        }}

        QCalendarWidget QSpinBox {{
            background-color: {COLORS["bg_input"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
        }}

        QCalendarWidget QAbstractItemView:enabled {{
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
            selection-background-color: {COLORS["accent"]};
            selection-color: {TEXT_WHITE};
        }}

        QCalendarWidget QAbstractItemView:disabled {{
            color: {COLORS["text_muted"]};
        }}

        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: {COLORS["bg_elevated"]};
            border-bottom: 1px solid {COLORS["border"]};
        }}

        QCalendarWidget QAbstractItemView::item {{
            outline: none;
            border-radius: {RADIUS_CHIP}px;
        }}

        QCalendarWidget QAbstractItemView::item:hover {{
            background-color: {COLORS["bg_elevated"]};
        }}

        QCalendarWidget QAbstractItemView::item:selected {{
            background-color: {COLORS["accent"]};
            color: {TEXT_WHITE};
        }}
        """

    @classmethod
    def _toast_qss(cls) -> str:
        return f"""
        QFrame[role="toast"] {{
            background-color: {COLORS["bg_surface"]};
            color: {COLORS["text_primary"]};
            border: 1px solid {COLORS["border"]};
            border-radius: {RADIUS_CARD}px;
        }}

        QFrame[role="toast"][state="error"] {{
            border: 1px solid {COLORS["danger"]};
        }}

        QLabel[role="toast-icon"] {{
            background-color: transparent;
            font-size: 16px;
        }}

        QLabel[role="toast-label"] {{
            background-color: transparent;
            color: {COLORS["text_primary"]};
            font-size: {cls._fs("body")}px;
        }}
        """
