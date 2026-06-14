"""Global QSS stylesheet for Operion ERP.

Apply once at startup via app.setStyleSheet(build_stylesheet()).
"""

from __future__ import annotations


def build_stylesheet() -> str:
    from ui.design_tokens import (
        BG_BASE, BG_SURFACE, BG_ELEVATED, BG_OVERLAY,
        BORDER_FAINT, BORDER_DEFAULT, BORDER_STRONG, BORDER_FOCUS,
        ACCENT, ACCENT_HOVER, ACCENT_DIM, ACCENT_TEXT,
        TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DISABLED,
        SUCCESS, SUCCESS_DIM, SUCCESS_TEXT,
        WARNING, WARNING_DIM, WARNING_TEXT,
        DANGER, DANGER_DIM, DANGER_TEXT,
        INFO, INFO_DIM, INFO_TEXT,
        FONT_FAMILY, FONT_MONO,
    )
    return f"""

/* ── GLOBAL RESET ─────────────────────────────────────────── */
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI Variable", sans-serif;
    font-size: 13px;
    color: {TEXT_PRIMARY};
    outline: none;
    border: none;
}}

QMainWindow, QDialog {{
    background: {BG_BASE};
}}

QWidget {{
    background: transparent;
}}

/* ── SCROLLBARS ───────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_DEFAULT};
    border-radius: 4px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_STRONG};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_DEFAULT};
    border-radius: 4px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER_STRONG};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── LABELS ────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QLabel[role="page-title"] {{
    font-size: 22px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    letter-spacing: -0.3px;
}}
QLabel[role="section-title"] {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.6px;
}}
QLabel[role="field-label"] {{
    font-size: 11px;
    font-weight: 500;
    color: {TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.7px;
}}
QLabel[role="kpi-value"] {{
    font-family: "{FONT_MONO}";
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel[role="kpi-label"] {{
    font-size: 11px;
    font-weight: 500;
    color: {TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.6px;
}}
QLabel[role="secondary"] {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel[role="muted"] {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel[role="mono"] {{
    font-family: "{FONT_MONO}";
    font-size: 13px;
}}
QLabel[role="danger"]  {{ color: {DANGER_TEXT}; }}
QLabel[role="success"] {{ color: {SUCCESS_TEXT}; }}
QLabel[role="warning"] {{ color: {WARNING_TEXT}; }}
QLabel[role="accent"]  {{ color: {ACCENT_TEXT}; }}

/* ── BUTTONS ────────────────────────────────────────────────── */
/* Base — all buttons share these */
QPushButton {{
    font-size: 13px;
    font-weight: 500;
    height: 34px;
    padding: 0 14px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER_DEFAULT};
}}

/* Primary — ONE per form/section */
QPushButton[variant="primary"],
QPushButton#btn-primary {{
    background: {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover,
QPushButton#btn-primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton[variant="primary"]:pressed,
QPushButton#btn-primary:pressed {{
    background: #4338ca;
}}
QPushButton[variant="primary"]:disabled {{
    background: {ACCENT_DIM};
    color: {TEXT_DISABLED};
}}

/* Secondary — most action buttons */
QPushButton[variant="secondary"],
QPushButton#btn-secondary {{
    background: transparent;
    border: 1px solid {BORDER_DEFAULT};
    color: {TEXT_SECONDARY};
}}
QPushButton[variant="secondary"]:hover,
QPushButton#btn-secondary:hover {{
    background: {BG_ELEVATED};
    border-color: {BORDER_STRONG};
    color: {TEXT_PRIMARY};
}}
QPushButton[variant="secondary"]:pressed,
QPushButton#btn-secondary:pressed {{
    background: {BG_OVERLAY};
}}

/* Danger — delete, remove */
QPushButton[variant="danger"],
QPushButton#btn-danger {{
    background: transparent;
    border: 1px solid {DANGER_DIM};
    color: {DANGER_TEXT};
}}
QPushButton[variant="danger"]:hover,
QPushButton#btn-danger:hover {{
    background: {DANGER_DIM};
    border-color: {DANGER};
}}

/* Ghost — icon buttons, subtle actions */
QPushButton[variant="ghost"],
QPushButton#btn-ghost {{
    background: transparent;
    border: none;
    color: {TEXT_MUTED};
    padding: 0 8px;
}}
QPushButton[variant="ghost"]:hover,
QPushButton#btn-ghost:hover {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

/* Small variant */
QPushButton[size="sm"] {{
    height: 28px;
    padding: 0 10px;
    font-size: 12px;
    border-radius: 5px;
}}

/* ── INPUTS ─────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 10px;
    height: 36px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {BORDER_FOCUS};
    background: {BG_ELEVATED};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border-color: {BORDER_STRONG};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background: {BG_SURFACE};
    color: {TEXT_DISABLED};
    border-color: {BORDER_DEFAULT};
}}
QLineEdit::placeholder {{
    color: {TEXT_MUTED};
}}

QTextEdit, QPlainTextEdit {{
    padding: 8px 10px;
    height: auto;
}}

/* ── COMBOBOX ───────────────────────────────────────────────── */
QComboBox {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 10px;
    height: 36px;
}}
QComboBox:hover {{
    border-color: {BORDER_STRONG};
}}
QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {BG_OVERLAY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    selection-background-color: {BG_ELEVATED};
    selection-color: {TEXT_PRIMARY};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    height: 32px;
    padding: 0 10px;
    border-radius: 4px;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {BG_ELEVATED};
}}

/* ── SPINBOX ────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 10px;
    height: 36px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {BORDER_FOCUS};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BG_OVERLAY};
    border: none;
    width: 20px;
    border-radius: 3px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BORDER_STRONG};
}}

/* ── DATE EDIT ──────────────────────────────────────────────── */
QDateEdit {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 10px;
    height: 36px;
}}
QDateEdit:focus {{ border-color: {BORDER_FOCUS}; }}
QDateEdit::drop-down {{
    border: none;
    width: 24px;
}}
QCalendarWidget {{
    background: {BG_OVERLAY};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
}}
QCalendarWidget QAbstractItemView:enabled {{
    background: {BG_OVERLAY};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {BG_SURFACE};
    border-radius: 6px;
}}

/* ── CHECKBOX & RADIO ────────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 4px;
    background: {BG_ELEVATED};
}}
QCheckBox::indicator:hover {{
    border-color: {BORDER_STRONG};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url(none);
}}
QCheckBox::indicator:checked:hover {{
    background: {ACCENT_HOVER};
}}
QRadioButton {{
    spacing: 8px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    background: {BG_ELEVATED};
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── TABLES ─────────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background: {BG_SURFACE};
    alternate-background-color: {BG_ELEVATED};
    gridline-color: {BORDER_FAINT};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_PRIMARY};
}}
QTableWidget::item, QTableView::item {{
    padding: 0 12px;
    height: 36px;
    border: none;
    border-bottom: 1px solid {BORDER_FAINT};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {ACCENT_DIM};
    color: {ACCENT_TEXT};
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background: {BG_ELEVATED};
}}
QHeaderView::section {{
    background: {BG_BASE};
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    padding: 0 12px;
    height: 36px;
    border: none;
    border-bottom: 1px solid {BORDER_DEFAULT};
    border-right: 1px solid {BORDER_FAINT};
}}
QHeaderView::section:last {{
    border-right: none;
}}
QHeaderView::section:hover {{
    background: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
}}
QTableCornerButton::section {{
    background: {BG_BASE};
    border: none;
    border-bottom: 1px solid {BORDER_DEFAULT};
    border-right: 1px solid {BORDER_FAINT};
}}

/* ── TREE VIEW ──────────────────────────────────────────────── */
QTreeView {{
    background: {BG_SURFACE};
    alternate-background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    selection-background-color: {ACCENT_DIM};
}}
QTreeView::item {{
    padding: 4px 8px;
    border: none;
}}
QTreeView::item:selected {{ background: {ACCENT_DIM}; color: {ACCENT_TEXT}; }}
QTreeView::item:hover    {{ background: {BG_ELEVATED}; }}
QTreeView::branch {{
    background: transparent;
}}

/* ── LIST VIEW ──────────────────────────────────────────────── */
QListView, QListWidget {{
    background: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}
QListView::item, QListWidget::item {{
    padding: 6px 12px;
    border: none;
    border-radius: 4px;
    margin: 1px 4px;
}}
QListView::item:selected, QListWidget::item:selected {{
    background: {ACCENT_DIM};
    color: {ACCENT_TEXT};
}}
QListView::item:hover, QListWidget::item:hover {{
    background: {BG_ELEVATED};
}}

/* ── TAB BAR ────────────────────────────────────────────────── */
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    font-size: 13px;
    font-weight: 500;
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {TEXT_PRIMARY};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_SECONDARY};
}}
QTabWidget::pane {{
    background: transparent;
    border: none;
    border-top: 1px solid {BORDER_DEFAULT};
    top: -1px;
}}

/* ── SPLITTER ───────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BORDER_FAINT};
    width: 1px;
    height: 1px;
}}
QSplitter::handle:hover {{
    background: {BORDER_DEFAULT};
}}

/* ── GROUP BOX ──────────────────────────────────────────────── */
QGroupBox {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 16px;
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.7px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background: {BG_SURFACE};
}}

/* ── PROGRESS BAR ───────────────────────────────────────────── */
QProgressBar {{
    background: {BG_ELEVATED};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QProgressBar[variant="success"]::chunk {{ background: {SUCCESS}; }}
QProgressBar[variant="warning"]::chunk {{ background: {WARNING}; }}
QProgressBar[variant="danger"]::chunk  {{ background: {DANGER};  }}

/* ── SLIDER ─────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {BG_ELEVATED};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
}}

/* ── TOOLTIP ────────────────────────────────────────────────── */
QToolTip {{
    background: {BG_OVERLAY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── MENU ───────────────────────────────────────────────────── */
QMenu {{
    background: {BG_OVERLAY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 14px;
    border-radius: 5px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QMenu::item:selected {{
    background: {BG_ELEVATED};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_DEFAULT};
    margin: 4px 8px;
}}

/* ── MESSAGE BOX ────────────────────────────────────────────── */
QMessageBox {{
    background: {BG_OVERLAY};
}}
QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

/* ── STATUS BAR ─────────────────────────────────────────────── */
QStatusBar {{
    background: {BG_SURFACE};
    color: {TEXT_MUTED};
    font-size: 12px;
    border-top: 1px solid {BORDER_DEFAULT};
}}

/* ── SIDEBAR (setObjectName "sidebar") ──────────────────────── */
QWidget#sidebar {{
    background: {BG_SURFACE};
    border-right: 1px solid {BORDER_DEFAULT};
}}

/* ── TOPBAR (setObjectName "topbar") ───────────────────────── */
QWidget#topbar {{
    background: {BG_BASE};
    border-bottom: 1px solid {BORDER_DEFAULT};
    min-height: 44px;
    max-height: 44px;
}}

/* ── CARD (setObjectName "card") ────────────────────────────── */
QFrame#card, QWidget#card {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
}}

/* ── DIVIDER (setObjectName "divider") ─────────────────────── */
QFrame#divider {{
    background: {BORDER_DEFAULT};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

"""
