"""UI component factory helpers for Operion ERP.

Import and use these everywhere instead of building widgets inline.
"""

from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtWidgets import (
    QLabel, QPushButton, QFrame, QWidget, QHBoxLayout,
    QVBoxLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

from ui.design_tokens import (
    BG_SURFACE, BG_ELEVATED, BG_OVERLAY,
    BORDER_DEFAULT, BORDER_STRONG, BORDER_FAINT,
    ACCENT, ACCENT_HOVER, ACCENT_DIM, ACCENT_TEXT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DISABLED,
    SUCCESS, SUCCESS_DIM, SUCCESS_TEXT,
    WARNING, WARNING_DIM, WARNING_TEXT,
    DANGER, DANGER_DIM, DANGER_TEXT,
    INFO, INFO_DIM, INFO_TEXT,
    FONT_FAMILY, FONT_MONO, FONT_SIZES, SP, RADIUS, STATUS,
)

import qtawesome as qta


def Label(parent, text="", role="", **props) -> QLabel:
    """Create a label with a semantic role."""
    lbl = QLabel(text, parent)
    if role:
        lbl.setProperty("role", role)
    for k, v in props.items():
        if hasattr(lbl, k):
            setattr(lbl, k, v)
    lbl.style().unpolish(lbl)
    lbl.style().polish(lbl)
    return lbl


def PageTitle(parent, text="") -> QLabel:
    return Label(parent, text, role="page-title")


def SectionTitle(parent, text="") -> QLabel:
    return Label(parent, text.upper(), role="section-title")


def FieldLabel(parent, text="") -> QLabel:
    return Label(parent, text.upper(), role="field-label")


def MonoLabel(parent, text="", size="body") -> QLabel:
    lbl = Label(parent, text, role="mono")
    sizes = {"body": 13, "lg": 20, "xl": 28}
    font = QFont(FONT_MONO, sizes.get(size, 13))
    font.setWeight(QFont.Weight.Medium)
    lbl.setFont(font)
    return lbl


def Btn(parent, text="", variant="secondary",
        icon_name=None, size="md", command=None) -> QPushButton:
    """Create a styled button."""
    btn = QPushButton(text, parent)
    btn.setProperty("variant", variant)
    if size == "sm":
        btn.setProperty("size", "sm")
    if icon_name:
        color_map = {
            "primary": "white",
            "secondary": TEXT_SECONDARY,
            "danger": DANGER_TEXT,
            "ghost": TEXT_MUTED,
        }
        btn.setIcon(qta.icon(icon_name,
                             color=color_map.get(variant, TEXT_MUTED)))
        btn.setIconSize(QSize(16, 16))
    if command:
        btn.clicked.connect(command)
    return btn


def Card(parent=None, padding=True) -> QFrame:
    """
    A surface card — the basic visual container for grouped content.
    Returns a QFrame with a VBoxLayout. Add children to card.layout().
    """
    frame = QFrame(parent)
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    if padding:
        layout.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])
        layout.setSpacing(SP["3"])
    else:
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
    return frame


def CardHeader(parent_layout, title="", subtitle="",
               right_widget=None) -> QWidget:
    """
    Add a card header to a layout.
    title: the card's section name
    subtitle: optional secondary text
    right_widget: optional widget placed at the right edge (e.g. a button)
    """
    header = QWidget()
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, SP["2"])
    row.setSpacing(SP["2"])

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    title_lbl = Label(None, title, role="section-title")
    text_col.addWidget(title_lbl)
    if subtitle:
        sub_lbl = Label(None, subtitle, role="muted")
        text_col.addWidget(sub_lbl)

    row.addLayout(text_col)
    row.addStretch()
    if right_widget:
        row.addWidget(right_widget)

    parent_layout.addWidget(header)
    # Divider below header
    div = Divider(None)
    parent_layout.addWidget(div)
    return header


def Divider(parent=None, vertical=False) -> QFrame:
    d = QFrame(parent)
    d.setObjectName("divider")
    if vertical:
        d.setFrameShape(QFrame.Shape.VLine)
    else:
        d.setFrameShape(QFrame.Shape.HLine)
    d.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed
    )
    return d


def KPICard(parent, label="", value="",
            value_color=None, subtitle=None) -> QFrame:
    """
    A KPI metric card showing a large number with a label above it.
    """
    card = Card(parent)
    layout = card.layout()
    layout.setSpacing(SP["1"])

    lbl = Label(card, label.upper(), role="kpi-label")
    layout.addWidget(lbl)

    val = MonoLabel(card, value, size="lg")
    val.setObjectName("kpi-value")
    if value_color:
        val.setStyleSheet(f"color: {value_color};")
    layout.addWidget(val)

    if subtitle:
        sub = Label(card, subtitle, role="muted")
        layout.addWidget(sub)

    layout.addStretch()
    return card


def StatusChip(parent, status="", text="") -> QLabel:
    """
    A small colored chip indicating status.
    status: key from STATUS dict in design_tokens
    """
    bg, fg = STATUS.get(status.lower().replace(" ", "_"),
                         ("#27272a", "#a1a1aa"))
    chip = QLabel(text or status.replace("_", " ").title(), parent)
    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip.setStyleSheet(f"""
        background: {bg};
        color: {fg};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
    """)
    chip.setFixedHeight(22)
    return chip


def Icon(name: str, color=TEXT_SECONDARY,
         size=16):
    """Return an icon widget."""
    return qta.IconWidget(name, options=[{
        "color": color, "scale_factor": 1.0
    }])
