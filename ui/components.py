"""UI component factory helpers for Operion ERP.

Import and use these everywhere instead of building widgets inline.
"""

from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import QPoint, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import (
    BORDER_FAINT,
    BTN_HEIGHT,
    BTN_HEIGHT_LG,
    BTN_HEIGHT_SM,
    COLOR_ACCENT_BORDER,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_STRONG,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_TEXT_WHITE,
    DANGER_TEXT,
    FADE_MS,
    FONT_MONO,
    FONT_SIZE_BASE,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
    FONT_SIZE_XS,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_SEMIBOLD,
    HOVER_MS,
    INPUT_HEIGHT,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_PILL,
    RADIUS_SM,
    SLIDE_MS,
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
    lbl.setAccessibleName(text)
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
    lbl = Label(parent, text, role="page-title")
    lbl.setAccessibleName(text)
    return lbl


def SectionTitle(parent, text="") -> QLabel:
    lbl = Label(parent, text.upper(), role="section-title")
    lbl.setAccessibleName(text)
    return lbl


def FieldLabel(parent, text="") -> QLabel:
    return Label(parent, text.upper(), role="field-label")


def MonoLabel(parent, text="", size="body") -> QLabel:
    lbl = Label(parent, text, role="mono")
    sizes = {"body": 13, "lg": 20, "xl": 28}
    font = QFont(FONT_MONO, max(1, sizes.get(size, 13)))
    if font.pointSize() <= 0:
        font.setPointSize(max(1, sizes.get(size, 13)))
    font.setWeight(QFont.Weight.Medium)
    lbl.setFont(font)
    return lbl


class _Btn(QPushButton):
    """QPushButton that also activates on Enter/Return when focused.

    QPushButton only activates on Enter when ``autoDefault`` is True (or it
    is the dialog's default button).  This subclass makes a *focused* button
    respond to Enter/Return too, without the dialog default-button side
    effects of enabling ``autoDefault`` globally.
    """

    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and not event.isAutoRepeat()
        ):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


def Btn(parent, text="", variant="secondary",
        icon_name=None, size="md", command=None) -> QPushButton:
    """Create a styled button."""
    btn = _Btn(text, parent)
    btn.setAccessibleName(text)
    btn.setProperty("variant", variant)
    if size == "sm":
        btn.setProperty("button-size", "sm")
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
    frame.setAccessibleName("Card")
    frame.setAccessibleDescription("Content card container")
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


# ──────────────────────────────────────────────────────────────────────────────
# UniversalCard — standardised info card pattern
# ──────────────────────────────────────────────────────────────────────────────

class UniversalCard(QFrame):
    """Standardized card with title, primary info, secondary info, icon, and optional action.

    Layout:
        ┌──────────────────────────┐
        │  [icon]  Title    [action]│
        │          Primary info     │
        │          Secondary info   │
        └──────────────────────────┘
    """

    def __init__(
        self,
        parent=None,
        title="",
        primary="",
        secondary="",
        icon_name=None,
        icon_color=None,
        action_icon=None,
        action_tooltip="",
        on_action=None,
        on_click=None,
        **kwargs,
    ):
        super().__init__(parent)
        self.setObjectName("universal-card")
        self.setMinimumHeight(88)
        self.setAccessibleName("Universal Card")
        self.setAccessibleDescription("Information card with title and details")
        self._icon_name = icon_name
        self._icon_color = icon_color or COLOR_TEXT_TERTIARY
        self._on_click = on_click

        if on_click:
            self.setCursor(Qt.PointingHandCursor)

        # ── Main layout ──────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        layout.setSpacing(SPACE_2)

        # ── Header row: icon + title + stretch + action button ───────
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACE_2)

        # Icon container (32x32 rounded box)
        icon_lbl = None
        if icon_name:
            icon_container = QFrame(header)
            icon_container.setFixedSize(32, 32)
            icon_container.setStyleSheet(
                f"background: {COLOR_BG_OVERLAY}; border-radius: {RADIUS_SM}px; "
                f"border: none;"
            )
            icon_lyt = QHBoxLayout(icon_container)
            icon_lyt.setContentsMargins(0, 0, 0, 0)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(
                qta.icon(icon_name, color=self._icon_color).pixmap(16, 16)
            )
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lyt.addWidget(icon_lbl)
            header_layout.addWidget(icon_container)

        self._icon_widget = icon_lbl

        # Title
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; "
            f"color: {COLOR_TEXT_PRIMARY}; background: transparent; border: none;"
        )
        header_layout.addWidget(self._title_lbl)

        header_layout.addStretch()

        # Action button (ghost icon button)
        if action_icon:
            action_btn = IconButton(
                header,
                icon_name=action_icon,
                tooltip=action_tooltip,
                variant="ghost",
                size=28,
                command=on_action,
            )
            header_layout.addWidget(action_btn)

        layout.addWidget(header)

        # ── Primary info ─────────────────────────────────────────────
        self._primary_lbl = None
        if primary:
            self._primary_lbl = QLabel(primary)
            self._primary_lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_MD}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
                f"color: {COLOR_TEXT_PRIMARY}; background: transparent; border: none;"
            )
            layout.addWidget(self._primary_lbl)

        # ── Secondary info ───────────────────────────────────────────
        self._secondary_lbl = None
        if secondary:
            self._secondary_lbl = QLabel(secondary)
            self._secondary_lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_REGULAR}; "
                f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;"
            )
            layout.addWidget(self._secondary_lbl)

        # ── Card styling ─────────────────────────────────────────────
        self._apply_style(False)

    # ── Public setters ────────────────────────────────────────────────

    def set_title(self, text: str) -> None:
        self._title_lbl.setText(text)

    def set_primary(self, text: str) -> None:
        if self._primary_lbl:
            self._primary_lbl.setText(text)

    def set_secondary(self, text: str) -> None:
        if self._secondary_lbl:
            self._secondary_lbl.setText(text)

    def set_icon_color(self, color: str) -> None:
        """Update the icon tint (useful for status changes)."""
        self._icon_color = color
        if self._icon_widget and self._icon_name:
            self._icon_widget.setPixmap(
                qta.icon(self._icon_name, color=color).pixmap(16, 16)
            )

    # ── Hover / style ────────────────────────────────────────────────

    def _apply_style(self, hovered: bool) -> None:
        border = COLOR_BORDER_STRONG if hovered else COLOR_BORDER_SUBTLE
        self.setStyleSheet(f"""
            UniversalCard {{
                background: {COLOR_BG_ELEVATED};
                border: 1px solid {border};
                border-radius: {RADIUS_LG}px;
            }}
        """)

    def enterEvent(self, event) -> None:
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._on_click:
            self._on_click()
        super().mousePressEvent(event)


def CardRow(parent, cards: list[QFrame], spacing=SPACE_3) -> QWidget:
    """Horizontal row of evenly-spaced cards."""
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for card in cards:
        if card:
            layout.addWidget(card, 1)  # equal stretch
    return row


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
        self.setAccessibleName("Compact KPI Card")
        self.setAccessibleDescription("Compact key performance indicator card")

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
    badge.setAccessibleName(text or status_key or "Status badge")
    badge.setAccessibleDescription(f"Status: {display}")
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
        self.setAccessibleName("Empty state")
        self.setAccessibleDescription(f"No items: {title}")

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


# ──────────────────────────────────────────────────────────────────────────────
# SearchInput
# ──────────────────────────────────────────────────────────────────────────────

def SearchInput(parent, placeholder="", on_text_changed=None) -> QLineEdit:
    """Search input with magnifying glass icon (left) and clear button (right)."""
    search = QLineEdit(parent)
    search.setAccessibleName(placeholder or "Search")
    search.setPlaceholderText(placeholder)
    search.addAction(
        qta.icon("fa5s.search", color=COLOR_TEXT_TERTIARY),
        QLineEdit.LeadingPosition,
    )
    search.setClearButtonEnabled(True)
    if on_text_changed:
        search.textChanged.connect(on_text_changed)
    search.setStyleSheet(f"""
        QLineEdit {{
            background: {COLOR_BG_OVERLAY};
            border: 1px solid {COLOR_BORDER_MEDIUM};
            border-radius: {RADIUS_MD}px;
            padding: 6px 10px;
            color: {COLOR_TEXT_PRIMARY};
        }}
        QLineEdit:hover {{
            border-color: {COLOR_BORDER_STRONG};
        }}
        QLineEdit:focus {{
            border-color: {COLOR_ACCENT_PRIMARY};
        }}
        QLineEdit::placeholder {{
            color: {COLOR_TEXT_TERTIARY};
        }}
    """)
    search.setFixedHeight(INPUT_HEIGHT)
    search.setMinimumWidth(200)
    return search


# ──────────────────────────────────────────────────────────────────────────────
# IconButton
# ──────────────────────────────────────────────────────────────────────────────

class _IconButton(QPushButton):
    """Internal icon button that changes icon color on hover."""

    def __init__(self, parent=None, icon_name="", icon_color="",
                 hover_color="", icon_size=16):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._hover_color = hover_color
        self._icon_size = icon_size
        self._hovering = False
        self._update_icon()

    def _update_icon(self):
        color = self._hover_color if self._hovering else self._icon_color
        self.setIcon(qta.icon(self._icon_name, color=color))
        self.setIconSize(QSize(self._icon_size, self._icon_size))

    def enterEvent(self, event):
        self._hovering = True
        self._update_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovering = False
        self._update_icon()
        super().leaveEvent(event)


def IconButton(parent, icon_name="", tooltip="", variant="ghost",
               size=16, command=None) -> QPushButton:
    """Icon-only button. Variants: ghost, primary, danger, success, muted.
    size = button height in px.
    """
    _BTN_ICON_COLOR = {
        "ghost": COLOR_TEXT_SECONDARY,
        "primary": COLOR_ACCENT_PRIMARY,
        "danger": COLOR_ERROR_TEXT,
        "success": COLOR_SUCCESS_TEXT,
        "muted": COLOR_TEXT_TERTIARY,
    }
    _BTN_HOVER_ICON = {
        "ghost": COLOR_TEXT_PRIMARY,
        "primary": COLOR_ACCENT_PRIMARY,
        "danger": COLOR_ERROR_TEXT,
        "success": COLOR_SUCCESS_TEXT,
        "muted": COLOR_TEXT_SECONDARY,
    }
    _BTN_HOVER_BG = {
        "ghost": COLOR_BG_OVERLAY,
        "primary": COLOR_ACCENT_SUBTLE,
        "danger": COLOR_ERROR_SUBTLE,
        "success": COLOR_SUCCESS_SUBTLE,
        "muted": COLOR_BG_OVERLAY,
    }

    icon_size = max(1, size - 8)
    radius = RADIUS_SM if size <= 28 else RADIUS_MD
    icon_color = _BTN_ICON_COLOR.get(variant, COLOR_TEXT_SECONDARY)
    hover_icon = _BTN_HOVER_ICON.get(variant, icon_color)
    hover_bg = _BTN_HOVER_BG.get(variant, "transparent")

    btn = _IconButton(
        parent=parent,
        icon_name=icon_name,
        icon_color=icon_color,
        hover_color=hover_icon,
        icon_size=icon_size,
    )
    btn.setAccessibleName(tooltip or icon_name)
    btn.setToolTip(tooltip)
    btn.setFixedSize(size, size)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setProperty("variant", variant)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            border: none;
            border-radius: {radius}px;
        }}
        QPushButton:hover {{
            background: {hover_bg};
        }}
    """)
    if command:
        btn.clicked.connect(command)
    return btn


# ──────────────────────────────────────────────────────────────────────────────
# FilterChip
# ──────────────────────────────────────────────────────────────────────────────

class FilterChip(QFrame):
    """Clickable filter chip. Toggles active state on click."""

    def __init__(self, parent=None, text="", icon_name=None,
                 active=False, on_toggled=None):
        super().__init__(parent)
        self.setAccessibleName(text)
        self._active = active
        self._on_toggled = on_toggled
        self._icon_name = icon_name
        self.setFixedHeight(BTN_HEIGHT_SM)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_2, 0, SPACE_2, 0)
        layout.setSpacing(SPACE_1)

        if icon_name:
            self._icon_lbl = QLabel(self)
            layout.addWidget(self._icon_lbl)

        self._text_lbl = QLabel(text.upper(), self)
        layout.addWidget(self._text_lbl)

        self._remove_lbl = QLabel(self)
        self._remove_lbl.setPixmap(
            qta.icon("fa5s.times", color=COLOR_ACCENT_PRIMARY).pixmap(12, 12)
        )
        layout.addWidget(self._remove_lbl)

        self._apply_state()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_state()
        if self._on_toggled:
            self._on_toggled(self._active)

    def is_active(self) -> bool:
        return self._active

    def _apply_state(self):
        if self._active:
            bg = COLOR_ACCENT_SUBTLE
            border = COLOR_ACCENT_BORDER
            text_color = COLOR_ACCENT_PRIMARY
            hover_bg = bg
            hover_border = COLOR_ACCENT_PRIMARY
            remove_visible = True
        else:
            bg = COLOR_BG_OVERLAY
            border = COLOR_BORDER_SUBTLE
            text_color = COLOR_TEXT_SECONDARY
            hover_bg = COLOR_BG_HOVER
            hover_border = COLOR_BORDER_MEDIUM
            remove_visible = False

        self.setStyleSheet(f"""
            FilterChip {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {RADIUS_PILL}px;
            }}
            FilterChip:hover {{
                background: {hover_bg};
                border-color: {hover_border};
            }}
        """)

        self._text_lbl.setStyleSheet(f"""
            font-size: {FONT_SIZE_SM}px;
            font-weight: {FONT_WEIGHT_MEDIUM};
            letter-spacing: 0.04em;
            color: {text_color};
            background: transparent;
        """)

        if hasattr(self, '_icon_lbl') and self._icon_name:
            self._icon_lbl.setPixmap(
                qta.icon(self._icon_name, color=text_color).pixmap(16, 16)
            )

        self._remove_lbl.setVisible(remove_visible)

    def mousePressEvent(self, event):
        self._active = not self._active
        self._apply_state()
        if self._on_toggled:
            self._on_toggled(self._active)
        super().mousePressEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Badge
# ──────────────────────────────────────────────────────────────────────────────

class Badge(QLabel):
    """Notification count badge. Hides when count is 0."""

    def __init__(self, parent=None, count=0, max_count=99):
        super().__init__(parent)
        self._max_count = max_count
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(20)
        self.setMinimumWidth(20)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            background: {COLOR_ERROR_DEFAULT};
            color: {COLOR_TEXT_WHITE};
            font-size: {FONT_SIZE_XS}px;
            font-weight: {FONT_WEIGHT_BOLD};
            border-radius: {RADIUS_PILL}px;
            padding: 0 {SPACE_1}px;
        """)
        self.set_count(count)

    def set_count(self, count: int) -> None:
        if count <= 0:
            self.setVisible(False)
            self.setText("")
        elif count > self._max_count:
            self.setText(f"+{self._max_count}")
            self.setVisible(True)
        else:
            self.setText(str(count))
            self.setVisible(True)


# ──────────────────────────────────────────────────────────────────────────────
# Toggle
# ──────────────────────────────────────────────────────────────────────────────

class Toggle(QFrame):
    """On/off switch toggle."""

    TRACK_WIDTH = 40
    TRACK_HEIGHT = 22
    THUMB_SIZE = 16
    INSET = 3

    def __init__(self, parent=None, checked=False, on_toggled=None):
        super().__init__(parent)
        self._checked = checked
        self._on_toggled = on_toggled
        self._anim = None
        self.setFixedSize(self.TRACK_WIDTH, self.TRACK_HEIGHT)
        self.setAccessibleName("Toggle switch")
        self.setAccessibleDescription("On/off toggle switch control")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        # Thumb circle
        self._thumb = QLabel(self)
        self._thumb.setFixedSize(self.THUMB_SIZE, self.THUMB_SIZE)

        self._apply_styles()
        self._set_thumb_position(animate=False)

    def _set_thumb_position(self, animate=True):
        target_x = (
            self.TRACK_WIDTH - self.THUMB_SIZE - self.INSET
            if self._checked
            else self.INSET
        )
        target_y = (self.TRACK_HEIGHT - self.THUMB_SIZE) // 2

        if animate:
            if self._anim and self._anim.state() == QPropertyAnimation.Running:
                self._anim.stop()
            self._anim = QPropertyAnimation(self._thumb, b"pos")
            self._anim.setDuration(SLIDE_MS)
            self._anim.setStartValue(self._thumb.pos())
            self._anim.setEndValue(QPoint(target_x, target_y))
            self._anim.start()
        else:
            self._thumb.move(target_x, target_y)

    def _apply_styles(self):
        if self._checked:
            track_bg = COLOR_ACCENT_PRIMARY
            track_border = COLOR_ACCENT_PRIMARY
            thumb_bg = COLOR_TEXT_WHITE
            hover_track = COLOR_ACCENT_HOVER
            hover_border = COLOR_ACCENT_HOVER
        else:
            track_bg = COLOR_BG_OVERLAY
            track_border = COLOR_BORDER_MEDIUM
            thumb_bg = COLOR_TEXT_SECONDARY
            hover_track = track_bg
            hover_border = COLOR_BORDER_STRONG

        self.setStyleSheet(f"""
            Toggle {{
                background: {track_bg};
                border: 1px solid {track_border};
                border-radius: {RADIUS_PILL}px;
            }}
            Toggle:hover {{
                background: {hover_track};
                border-color: {hover_border};
            }}
        """)
        self._thumb.setStyleSheet(f"""
            background: {thumb_bg};
            border-radius: {RADIUS_PILL}px;
        """)

    def set_checked(self, checked: bool) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        self._apply_styles()
        self._set_thumb_position(animate=True)
        if self._on_toggled:
            self._on_toggled(self._checked)

    def is_checked(self) -> bool:
        return self._checked

    def mousePressEvent(self, event):
        self.set_checked(not self._checked)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter)
            and not event.isAutoRepeat()
        ):
            self.set_checked(not self._checked)
            event.accept()
            return
        super().keyPressEvent(event)
