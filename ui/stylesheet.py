"""Global QSS stylesheet builder for the Operion ERP PySide6 frontend.

This module ties the design tokens in ``ui.design_tokens`` / ``ui.theme`` to
the Qt Style Sheet engine in ``ui.theme_engine.QtTheme`` and adds
application-specific widget styles (stat cards, kanban board, filters, etc).

Usage::

    from ui.stylesheet import build_stylesheet
    app.setStyleSheet(build_stylesheet())
"""

from __future__ import annotations

from ui.design_tokens import (
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_BASE,
    COLOR_BG_CARD,
    COLOR_BG_CARD_HOVER,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_SIZE_SM,
    HOVER_MS,
    RADIUS_LG as RADIUS_CARD,
    RADIUS_MD as RADIUS_INPUT,
    RADIUS_SM as RADIUS_CHIP,
)
from ui.theme_engine import QtTheme


def build_stylesheet() -> str:
    """Return the complete global stylesheet for the application."""
    return "\n\n".join(
        [
            QtTheme.qss(),
            _stat_card_qss(),
            _filter_qss(),
            _section_header_qss(),
            _tab_button_qss(),
            _kanban_qss(),
            _card_qss(),
        ]
    )


# ── Application-specific widget styles ──────────────────────────────


def _stat_card_qss() -> str:
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


def _filter_qss() -> str:
    return f"""
    QCheckBox[role="filter"] {{
        spacing: 6px;
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


def _section_header_qss() -> str:
    return f"""
    QLabel[role="section-header"] {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 4px 0;
    }}
    """


def _tab_button_qss() -> str:
    return f"""
    QPushButton[tabRole="tab-button"] {{
        background-color: transparent;
        color: {COLOR_TEXT_SECONDARY};
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 8px 16px;
        font-weight: 600;
        font-size: {FONT_SIZE_SM}px;
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


def _kanban_qss() -> str:
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
        font-size: 13px;
    }}

    QWidget[role="kanban-column-header"] QLabel[class="kanban-column-count"] {{
        color: {COLOR_TEXT_TERTIARY};
        font-size: 11px;
    }}

    QScrollArea[class="kanban-columns-container"] {{
        border: none;
        background-color: transparent;
    }}
    """


def _card_qss() -> str:
    return f"""
    QFrame#card {{
        background-color: {COLOR_BG_ELEVATED};
        border: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: {RADIUS_CARD}px;
    }}
    """
