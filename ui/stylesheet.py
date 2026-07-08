"""Global QSS stylesheet for Operion ERP.

Apply once at startup via app.setStyleSheet(build_stylesheet()).
"""

from __future__ import annotations

def build_stylesheet() -> str:
    from ui.design_tokens import (
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
        COLOR_ERROR_DEFAULT,
        COLOR_ERROR_SUBTLE,
        COLOR_ERROR_TEXT,
        COLOR_INFO_DEFAULT,
        COLOR_INFO_SUBTLE,
        COLOR_SUCCESS_DEFAULT,
        COLOR_SUCCESS_TEXT,
        COLOR_TEXT_INVERSE,
        COLOR_TEXT_PRIMARY,
        COLOR_TEXT_SECONDARY,
        COLOR_TEXT_TERTIARY,
        COLOR_WARNING_DEFAULT,
        COLOR_WARNING_SUBTLE,
        COLOR_WARNING_TEXT,
        FONT_FAMILY,
        FONT_MONO,
        FONT_SIZE_BASE,
        FONT_SIZE_SM,
        FONT_WEIGHT_BOLD,
        FONT_WEIGHT_MEDIUM,
        FONT_WEIGHT_REGULAR,
        FONT_WEIGHT_SEMIBOLD,
        RADIUS_LG,
        RADIUS_MD,
        RADIUS_SM,
        RADIUS_XL,
        SPACE_4,
    )
    return f"""

/* === 1. RESET & BASE === */
QWidget {{
    background: {COLOR_BG_BASE};
    color: {COLOR_TEXT_PRIMARY};
    font-family: '{FONT_FAMILY}', 'Segoe UI', sans-serif;
    font-size: {FONT_SIZE_BASE}px;
    outline: none;
}}
QFrame, QStackedWidget {{
    border: none;
}}
QMainWindow, QDialog, QStackedWidget {{
    background: {COLOR_BG_BASE};
}}
QLabel {{
    background: transparent;
}}

/* === 2. MAIN WINDOW === */
QMainWindow {{ background: {COLOR_BG_BASE}; }}

/* === 2b. SCROLL AREA === */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* === 3. SIDEBAR NAVIGATION === */
QWidget#sidebar {{
    background: {COLOR_BG_ELEVATED};
    border-right: 1px solid {COLOR_BORDER_SUBTLE};
}}

/* === 4. CARDS & PANELS === */
QFrame#card, QWidget#card {{
    background: {COLOR_BG_ELEVATED};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG}px;
}}
QFrame#card[variant="alert-critical"], QWidget#card[variant="alert-critical"] {{
    background: {COLOR_ERROR_SUBTLE};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-left: 3px solid {COLOR_ERROR_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}
QFrame#card[variant="alert-warning"], QWidget#card[variant="alert-warning"] {{
    background: {COLOR_WARNING_SUBTLE};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-left: 3px solid {COLOR_WARNING_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}
QFrame#card[variant="alert-info"], QWidget#card[variant="alert-info"] {{
    background: {COLOR_INFO_SUBTLE};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-left: 3px solid {COLOR_INFO_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}

/* StatCard — compact KPI metric card */
QFrame#stat-card, QWidget#stat-card {{
    background: {COLOR_BG_CARD};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADIUS_XL}px;
}}
QFrame#stat-card[hovered="true"], QWidget#stat-card[hovered="true"] {{
    background: {COLOR_BG_CARD_HOVER};
    border: 1px solid rgba(255,255,255,0.16);
}}

/* === Filter controls (shared across screens) === */
QCheckBox[role="filter"] {{
    spacing: 8px;
    font-size: 13px;
    color: rgba(255,255,255,0.75);
}}
QCheckBox[role="filter"]::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 4px;
    background: transparent;
}}
QCheckBox[role="filter"]::indicator:checked {{
    background: {COLOR_ACCENT_PRIMARY};
    border-color: {COLOR_ACCENT_PRIMARY};
    image: none;
}}
QCheckBox[role="filter"]::indicator:unchecked:hover {{
    border-color: rgba(255,255,255,0.4);
}}
QLineEdit[role="filter"], QComboBox[role="filter"] {{
    height: 36px;
    background: #14141C;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 0 12px;
    font-size: 13px;
    color: {COLOR_TEXT_PRIMARY};
}}
QLineEdit[role="filter"]:focus, QComboBox[role="filter"]:focus {{
    border-color: {COLOR_ACCENT_PRIMARY};
    background: #14141C;
}}
QLineEdit[role="filter"]:hover, QComboBox[role="filter"]:hover {{
    border-color: rgba(255,255,255,0.25);
}}
QComboBox[role="filter"]::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox[role="filter"]::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOR_TEXT_TERTIARY};
    margin-right: 8px;
}}

/* === 5. TABLES === */
QTableWidget, QTableView {{
    background: {COLOR_BG_ELEVATED};
    alternate-background-color: {COLOR_BG_BASE};
    gridline-color: {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_PRIMARY};
    font-size: {FONT_SIZE_BASE}px;
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG}px;
    selection-background-color: {COLOR_ACCENT_SUBTLE};
    selection-color: {COLOR_TEXT_PRIMARY};
}}
QTableWidget::item, QTableView::item {{
    padding: 0 {SPACE_4}px;
    height: 38px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {COLOR_BG_SELECTED};
    color: {COLOR_TEXT_PRIMARY};
    border-left: 2px solid {COLOR_ACCENT_PRIMARY};
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background: {COLOR_BG_HOVER};
}}
QHeaderView::section {{
    background: {COLOR_BG_ELEVATED};
    color: {COLOR_TEXT_TERTIARY};
    font-size: {FONT_SIZE_SM}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0 {SPACE_4}px;
    height: 34px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_MEDIUM};
    border-right: 1px solid {COLOR_BORDER_SUBTLE};
}}
QHeaderView::section:last {{
    border-right: none;
}}
QHeaderView::section:hover {{
    background: {COLOR_BG_HOVER};
    color: {COLOR_TEXT_SECONDARY};
}}
QTableCornerButton::section {{
    background: {COLOR_BG_ELEVATED};
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_MEDIUM};
    border-right: 1px solid {COLOR_BORDER_SUBTLE};
}}

/* === 6. INPUTS === */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_SM}px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 12px;
    height: 32px;
    selection-background-color: {COLOR_ACCENT_SUBTLE};
    selection-color: {COLOR_TEXT_PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {COLOR_ACCENT_PRIMARY};
    background: {COLOR_BG_OVERLAY};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border-color: {COLOR_BORDER_STRONG};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background: {COLOR_BG_ELEVATED};
    color: {COLOR_TEXT_TERTIARY};
    border-color: {COLOR_BORDER_SUBTLE};
    opacity: 0.5;
}}
QLineEdit::placeholder {{
    color: {COLOR_TEXT_TERTIARY};
}}
QTextEdit, QPlainTextEdit {{
    padding: 8px 12px;
    height: auto;
}}

/* ComboBox */
QComboBox {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_SM}px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 12px;
    height: 32px;
}}
QComboBox:hover {{ border-color: {COLOR_BORDER_STRONG}; }}
QComboBox:focus {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
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
    border-top: 5px solid {COLOR_TEXT_TERTIARY};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_MD}px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    selection-background-color: {COLOR_BG_HOVER};
    selection-color: {COLOR_TEXT_PRIMARY};
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    height: 32px;
    padding: 0 12px;
    border-radius: {RADIUS_SM}px;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {COLOR_BG_SELECTED};
    color: {COLOR_ACCENT_PRIMARY};
}}

/* SpinBox */
QSpinBox, QDoubleSpinBox {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_SM}px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 12px;
    height: 32px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {COLOR_BG_OVERLAY};
    border: none;
    width: 20px;
    border-radius: 3px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {COLOR_BORDER_STRONG};
}}

/* DateEdit */
QDateEdit {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_SM}px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    padding: 0 12px;
    height: 32px;
}}
QDateEdit:focus {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
QDateEdit::drop-down {{
    border: none;
    width: 24px;
}}
QCalendarWidget {{
    background: {COLOR_BG_OVERLAY};
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_MD}px;
}}
QCalendarWidget QAbstractItemView:enabled {{
    background: {COLOR_BG_OVERLAY};
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_ACCENT_PRIMARY};
    selection-color: white;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {COLOR_BG_ELEVATED};
    border-radius: {RADIUS_MD}px;
}}

/* Checkbox & Radio */
QCheckBox {{
    spacing: 8px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 12px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_SM}px;
    background: {COLOR_BG_OVERLAY};
}}
QCheckBox::indicator:hover {{ border-color: {COLOR_BORDER_STRONG}; }}
QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT_PRIMARY};
    border-color: {COLOR_ACCENT_PRIMARY};
    image: url(ui/assets/checkmark.svg);
}}
QCheckBox::indicator:checked:hover {{
    background: {COLOR_ACCENT_HOVER};
}}
QRadioButton {{
    spacing: 8px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 12px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: 8px;
    background: {COLOR_BG_OVERLAY};
}}
QRadioButton::indicator:checked {{
    background: {COLOR_ACCENT_PRIMARY};
    border-color: {COLOR_ACCENT_PRIMARY};
}}

/* === 7. BUTTONS === */
QPushButton {{
    font-size: 12px;
    font-weight: {FONT_WEIGHT_MEDIUM};
    height: 32px;
    padding: 0 16px;
    border-radius: {RADIUS_MD}px;
    border: none;
    background: transparent;
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton:disabled {{
    color: {COLOR_TEXT_TERTIARY};
    border-color: {COLOR_BORDER_SUBTLE};
}}

/* Primary */
QPushButton[variant="primary"], QPushButton#btn-primary {{
    background: {COLOR_ACCENT_PRIMARY};
    color: {COLOR_TEXT_INVERSE};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}
QPushButton[variant="primary"]:hover, QPushButton#btn-primary:hover {{
    background: {COLOR_ACCENT_HOVER};
}}
QPushButton[variant="primary"]:pressed, QPushButton#btn-primary:pressed {{
    background: {COLOR_ACCENT_HOVER};
    opacity: 0.9;
}}
QPushButton[variant="primary"]:disabled {{
    background: {COLOR_ACCENT_SUBTLE};
    color: {COLOR_TEXT_TERTIARY};
}}

/* Secondary */
QPushButton[variant="secondary"], QPushButton#btn-secondary {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    color: {COLOR_TEXT_PRIMARY};
    font-weight: {FONT_WEIGHT_REGULAR};
}}
QPushButton[variant="secondary"]:hover, QPushButton#btn-secondary:hover {{
    background: {COLOR_BG_HOVER};
    border-color: {COLOR_BORDER_STRONG};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton[variant="secondary"]:pressed, QPushButton#btn-secondary:pressed {{
    background: {COLOR_BG_SELECTED};
}}

/* Ghost */
QPushButton[variant="ghost"], QPushButton#btn-ghost {{
    background: transparent;
    border: none;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: {FONT_WEIGHT_REGULAR};
    padding: 0 8px;
}}
QPushButton[variant="ghost"]:hover, QPushButton#btn-ghost:hover {{
    background: {COLOR_BG_HOVER};
    color: {COLOR_TEXT_PRIMARY};
}}

/* Destructive */
QPushButton[variant="danger"], QPushButton#btn-danger,
QPushButton[variant="destructive"], QPushButton#btn-destructive {{
    background: transparent;
    border: 1px solid {COLOR_BORDER_SUBTLE};
    color: {COLOR_ERROR_TEXT};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}
QPushButton[variant="danger"]:hover, QPushButton#btn-danger:hover,
QPushButton[variant="destructive"]:hover, QPushButton#btn-destructive:hover {{
    background: {COLOR_ERROR_SUBTLE};
    border-color: {COLOR_ERROR_DEFAULT};
}}

/* Icon button */
QPushButton[variant="icon"], QPushButton#btn-icon {{
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: {RADIUS_SM}px;
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
}}
QPushButton[variant="icon"]:hover, QPushButton#btn-icon:hover {{
    background: {COLOR_BG_OVERLAY};
    color: {COLOR_TEXT_PRIMARY};
}}

/* Small variant */
QPushButton[size="sm"] {{
    height: 28px;
    padding: 0 10px;
    font-size: 11px;
    border-radius: 5px;
}}

/* === 8. SCROLL BARS === */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_MEDIUM};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLOR_BORDER_STRONG};
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
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER_MEDIUM};
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLOR_BORDER_STRONG};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* === 9. TOOLTIPS === */
QToolTip {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    color: {COLOR_TEXT_PRIMARY};
    border-radius: {RADIUS_MD}px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* === 10. STATUS BAR === */
QStatusBar {{
    background: {COLOR_BG_ELEVATED};
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
    border-top: 1px solid {COLOR_BORDER_SUBTLE};
    padding: 0 8px;
}}

/* === 11. DIALOGS === */
QDialog {{
    background: {COLOR_BG_BASE};
}}
QMessageBox {{
    background: {COLOR_BG_OVERLAY};
}}
QMessageBox QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

/* === 12. LABELS (semantic roles) === */
QLabel {{ background: transparent; }}
QLabel[role="page-title"] {{
    font-size: 18px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    color: {COLOR_TEXT_PRIMARY};
}}
QLabel[role="section-header"] {{
    font-size: 14px;
    font-weight: 600;
    color: #FFFFFF;
    letter-spacing: 0.3px;
    background: transparent;
}}
QLabel[role="section-title"] {{
    font-size: 11px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    color: {COLOR_TEXT_TERTIARY};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
QLabel[role="field-label"] {{
    font-size: 11px;
    font-weight: {FONT_WEIGHT_MEDIUM};
    color: {COLOR_TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
QLabel[role="kpi-value"] {{
    font-family: '{FONT_MONO}', 'Consolas', monospace;
    font-size: 28px;
    font-weight: {FONT_WEIGHT_BOLD};
    color: {COLOR_TEXT_PRIMARY};
}}
QLabel[role="kpi-label"] {{
    font-size: 11px;
    font-weight: {FONT_WEIGHT_MEDIUM};
    color: {COLOR_TEXT_SECONDARY};
    letter-spacing: 0.04em;
}}
QLabel[role="secondary"] {{ color: {COLOR_TEXT_SECONDARY}; font-size: 12px; }}
QLabel[role="muted"] {{ color: {COLOR_TEXT_TERTIARY}; font-size: 12px; }}
QLabel[role="mono"] {{
    font-family: '{FONT_MONO}', 'Consolas', monospace;
    font-size: 13px;
}}
QLabel[role="danger"]  {{ color: {COLOR_ERROR_TEXT}; }}
QLabel[role="success"] {{ color: {COLOR_SUCCESS_TEXT}; }}
QLabel[role="warning"] {{ color: {COLOR_WARNING_TEXT}; }}
QLabel[role="accent"]  {{ color: {COLOR_ACCENT_PRIMARY}; }}

/* === 13. TABS === */
QTabBar::tab {{
    background: transparent;
    color: {COLOR_TEXT_TERTIARY};
    font-size: 13px;
    font-weight: 500;
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {COLOR_TEXT_PRIMARY};
    border-bottom: 2px solid {COLOR_ACCENT_PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    color: {COLOR_TEXT_SECONDARY};
}}
QTabWidget::pane {{
    background: transparent;
    border: none;
    border-top: 1px solid {COLOR_BORDER_SUBTLE};
    top: -1px;
}}

/* === 14. SPLITTER === */
QSplitter::handle {{
    background: {COLOR_BORDER_SUBTLE};
    width: 1px;
    height: 1px;
}}
QSplitter::handle:hover {{
    background: {COLOR_BORDER_MEDIUM};
}}

/* === 15. GROUP BOX === */
QGroupBox {{
    background: {COLOR_BG_ELEVATED};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG}px;
    margin-top: 10px;
    padding-top: 16px;
    font-size: 11px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    color: {COLOR_TEXT_TERTIARY};
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background: {COLOR_BG_ELEVATED};
}}

/* === 16. PROGRESS BAR === */
QProgressBar {{
    background: {COLOR_BG_OVERLAY};
    border: none;
    border-radius: {RADIUS_SM}px;
    height: 4px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {COLOR_ACCENT_PRIMARY};
    border-radius: {RADIUS_SM}px;
}}
QProgressBar[variant="success"]::chunk {{ background: {COLOR_SUCCESS_DEFAULT}; }}
QProgressBar[variant="warning"]::chunk {{ background: {COLOR_WARNING_DEFAULT}; }}
QProgressBar[variant="danger"]::chunk  {{ background: {COLOR_ERROR_DEFAULT}; }}

/* === 17. SLIDER === */
QSlider::groove:horizontal {{
    background: {COLOR_BG_OVERLAY};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {COLOR_ACCENT_PRIMARY};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {COLOR_ACCENT_PRIMARY};
    border-radius: 3px;
}}
QSlider::handle:horizontal:hover {{
    background: {COLOR_ACCENT_HOVER};
}}

/* === 18. MENU === */
QMenu {{
    background: {COLOR_BG_OVERLAY};
    border: 1px solid {COLOR_BORDER_MEDIUM};
    border-radius: {RADIUS_LG}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 14px;
    border-radius: 5px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}
QMenu::item:selected {{
    background: {COLOR_BG_HOVER};
}}
QMenu::separator {{
    height: 1px;
    background: {COLOR_BORDER_SUBTLE};
    margin: 4px 8px;
}}

/* === 19. LIST / TREE === */
QListView, QListWidget {{
    background: {COLOR_BG_ELEVATED};
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG}px;
    selection-background-color: {COLOR_ACCENT_SUBTLE};
    outline: none;
}}
QListView::item, QListWidget::item {{
    padding: 6px 12px;
    border: none;
    border-radius: {RADIUS_SM}px;
    margin: 1px 4px;
}}
QListView::item:selected, QListWidget::item:selected {{
    background: {COLOR_ACCENT_SUBTLE};
    color: {COLOR_ACCENT_PRIMARY};
}}
QListView::item:hover, QListWidget::item:hover {{
    background: {COLOR_BG_HOVER};
}}
QTreeView {{
    background: {COLOR_BG_ELEVATED};
    alternate-background-color: {COLOR_BG_BASE};
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG}px;
    selection-background-color: {COLOR_ACCENT_SUBTLE};
}}
QTreeView::item {{
    padding: 4px 8px;
    border: none;
}}
QTreeView::item:selected {{ background: {COLOR_ACCENT_SUBTLE}; color: {COLOR_ACCENT_PRIMARY}; }}
QTreeView::item:hover    {{ background: {COLOR_BG_HOVER}; }}
QTreeView::branch {{ background: transparent; }}

/* === 20. DIVIDER === */
QFrame#divider {{
    background: {COLOR_BORDER_SUBTLE};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

"""
