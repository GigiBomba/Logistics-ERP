"""UI component factory helpers for Operion ERP.

Import and use these everywhere instead of building widgets inline.
"""

from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import (
    BORDER_FAINT,
    COLOR_BG_OVERLAY,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    DANGER_TEXT,
    FONT_MONO,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_PILL,
    RADIUS_SM,
    SP,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    STATUS_STYLES,
    TEXT_MUTED,
    TEXT_SECONDARY,
)

# Module-level color map for button icon colors — avoid recreating per call
_BTN_COLOR_MAP = {
    "primary": "white",
    "secondary": TEXT_SECONDARY,
    "danger": DANGER_TEXT,
    "ghost": TEXT_MUTED,
}


def Label(parent, text="", role="", **props) -> QLabel:
    """Create a label with a semantic role."""
    lbl = QLabel(text, parent)
    if role:
        lbl.setProperty("role", role)
    for k, v in props.items():
        if hasattr(lbl, k):
            setattr(lbl, k, v)
    if role and lbl.style():
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
        btn.setIcon(qta.icon(icon_name,
                             color=_BTN_COLOR_MAP.get(variant, TEXT_MUTED)))
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
               right_widget=None, title_role="section-title") -> QWidget:
    """
    Add a card header to a layout.
    title: the card's section name
    subtitle: optional secondary text
    right_widget: optional widget placed at the right edge (e.g. a button)
    title_role: QSS role for the title label (default "section-title")
    """
    header = QWidget()
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, SP["2"])
    row.setSpacing(SP["2"])

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    title_lbl = Label(header, title, role=title_role)
    text_col.addWidget(title_lbl)
    if subtitle:
        sub_lbl = Label(header, subtitle, role="muted")
        text_col.addWidget(sub_lbl)

    row.addLayout(text_col)
    row.addStretch()
    if right_widget:
        row.addWidget(right_widget)

    parent_layout.addWidget(header)
    # Divider below header
    div = Divider(header)
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


def SectionDivider(parent, title: str) -> QFrame:
    """Section divider with overlaid text: ─── TITLE ───────────────

    Matches the design-system spec (Section 3.7):
    - 1px line in COLOR_BORDER_SUBTLE
    - Text: 11px, weight 600, ALL-CAPS, letter-spacing 0.08em,
            COLOR_TEXT_TERTIARY
    - 4px margin above text, 12px below the widget
    """
    container = QFrame(parent)
    container.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 4, 0, 0)
    layout.setSpacing(0)

    line = QFrame(container)
    line.setStyleSheet(f"background: {BORDER_FAINT};")
    line.setFixedHeight(1)
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    lbl = QLabel(f"  {title.upper()}  ", container)
    lbl.setStyleSheet(
        f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; "
        f"letter-spacing: 0.08em; background: transparent;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    layout.addWidget(line)
    layout.addWidget(lbl)
    layout.addStretch()
    return container


# ──────────────────────────────────────────────────────────────────────────────
# Legacy KPI card (preserved for backward compatibility)
# ──────────────────────────────────────────────────────────────────────────────

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
    card.value_label = val
    card.title_label = lbl
    return card


# ──────────────────────────────────────────────────────────────────────────────
# Compact KPI card (new, per design system)
# ──────────────────────────────────────────────────────────────────────────────

class CompactKPICard(QFrame):
    """Compact 88px KPI card with icon, label, value, and optional trend."""

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "",
        value: str = "",
        icon_name: str | None = None,
        trend: str | None = None,
        trend_positive: bool | None = None,
        value_color: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(88)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_3)

        # Left: icon in a rounded square
        if icon_name:
            icon_container = QFrame(self)
            icon_container.setFixedSize(28, 28)
            icon_container.setStyleSheet(
                f"background: {COLOR_BG_OVERLAY}; border-radius: {RADIUS_SM}px;"
            )
            icon_layout = QHBoxLayout(icon_container)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(
                qta.icon(icon_name, color=COLOR_TEXT_TERTIARY).pixmap(16, 16)
            )
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_layout.addWidget(icon_lbl)
            layout.addWidget(icon_container)

        # Middle: label + value stacked
        text_layout = QVBoxLayout()
        text_layout.setSpacing(SPACE_1)
        text_layout.setAlignment(Qt.AlignVCenter)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
            f"color: {COLOR_TEXT_SECONDARY}; letter-spacing: 0.04em;"
        )
        text_layout.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(
            f"font-size: {FONT_SIZE_XL}px; font-weight: {FONT_WEIGHT_BOLD}; "
            f"color: {value_color or COLOR_TEXT_PRIMARY};"
        )
        text_layout.addWidget(val)

        layout.addLayout(text_layout, 1)

        # Right: trend indicator
        if trend:
            trend_lbl = QLabel(trend)
            if trend_positive is True:
                trend_color = COLOR_SUCCESS_TEXT
            elif trend_positive is False:
                trend_color = COLOR_ERROR_TEXT
            else:
                trend_color = COLOR_TEXT_TERTIARY
            trend_lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; "
                f"color: {trend_color};"
            )
            trend_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(trend_lbl)

        self.value_label = val
        self.title_label = lbl


# ──────────────────────────────────────────────────────────────────────────────
# Status badge (pill-shaped, per design system)
# ──────────────────────────────────────────────────────────────────────────────

def StatusBadge(parent, status_key: str = "", text: str = "") -> QLabel:
    """Create a pill-shaped status badge.

    status_key: one of the keys in STATUS_STYLES (e.g. "Delivered", "Cancelled")
    """
    label, text_color, bg_color = STATUS_STYLES.get(
        status_key.lower().replace(" ", "_"),
        (status_key or text, COLOR_NEUTRAL_TEXT, COLOR_NEUTRAL_SUBTLE),
    )
    display = text or label
    # 1px border at 30% opacity of text color
    border_color = f"{text_color}4D"  # 30% alpha hex

    badge = QLabel(display.upper(), parent)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(f"""
        background: {bg_color};
        color: {text_color};
        border-radius: {RADIUS_PILL}px;
        border: 1px solid {border_color};
        padding: 2px 8px;
        font-size: {FONT_SIZE_SM}px;
        font-weight: {FONT_WEIGHT_SEMIBOLD};
        letter-spacing: 0.04em;
    """)
    badge.setFixedHeight(20)
    badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return badge


# Backward-compatible alias
StatusChip = StatusBadge


# ──────────────────────────────────────────────────────────────────────────────
# Empty state widget
# ──────────────────────────────────────────────────────────────────────────────

class EmptyState(QFrame):
    """Standard empty state: icon + title + subtitle + optional CTA."""

    def __init__(
        self,
        parent: QWidget | None = None,
        icon_name: str = "mdi6.information-outline",
        title: str = "",
        subtitle: str = "",
        cta_button: QPushButton | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(120)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        layout.setSpacing(SPACE_2)
        layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon(icon_name, color=COLOR_TEXT_TERTIARY).pixmap(48, 48)
        )
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                "font-size: 15px; font-weight: 500; "
                f"color: {COLOR_TEXT_SECONDARY};"
            )
            title_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 400; "
                f"color: {COLOR_TEXT_TERTIARY};"
            )
            sub_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(sub_lbl)

        if cta_button:
            layout.addSpacing(SPACE_3)
            cta_button.setParent(self)
            cta_layout = QHBoxLayout()
            cta_layout.setAlignment(Qt.AlignCenter)
            cta_layout.addWidget(cta_button)
            layout.addLayout(cta_layout)


# ──────────────────────────────────────────────────────────────────────────────
# Icon helper
# ──────────────────────────────────────────────────────────────────────────────

def Icon(name: str, color=TEXT_SECONDARY, size=16):
    """Return an icon widget."""
    return qta.IconWidget(name, options=[{
        "color": color, "scale_factor": 1.0
    }])


def get_icon(name: str, color: str = TEXT_SECONDARY, size: int = 16) -> QIcon:
    """Return a recolored QIcon for use in buttons, menus, etc.

    This is the canonical icon utility referenced by the design system.
    It wraps qtawesome and ensures consistent color/size across the app.
    """
    return qta.icon(name, color=color, color_active=color)
