"""Searchable variable insertion popup for the email template editor.

Appears as a frameless popup below the "Insert Variable" button. Users
can type to filter and click a variable to insert ``{variable_name}``
at the cursor position.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.automail.template_service import get_available_variables
from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_WEIGHT_MEDIUM,
    RADIUS_LG,
    RADIUS_MD,
    SPACE_2,
    SPACE_3,
)
from ui.widgets import StyledLineEdit

logger = logging.getLogger(__name__)


class VariablePickerPopup(QFrame):
    """Frameless popup with searchable variable list.

    Emits ``variable_chosen(str)`` when the user clicks a variable.
    Auto-closes on losing focus or after selection.
    """

    variable_chosen = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(
            f"background: {COLOR_BG_ELEVATED}; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: {RADIUS_LG}px;"
        )

        self._build_ui()
        self._variables = []

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_2, SPACE_2, SPACE_2, SPACE_2)
        layout.setSpacing(SPACE_2)

        self._search_input = StyledLineEdit(
            self, placeholder=t("automail.search_variable", "Search variables...")
        )
        self._search_input.textChanged.connect(self._on_search)
        layout.addWidget(self._search_input)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setFixedHeight(220)

        self._list_widget = QWidget(scroll)
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(SPACE_2)
        self._list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._list_widget)

        layout.addWidget(scroll)

    def show_popup(self, anchor: QWidget) -> None:
        """Position and show the popup below *anchor*."""
        self._variables = get_available_variables()
        self._render_list("")
        self._search_input.clear()
        self._search_input.setFocus()

        pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        # Ensure popup stays on screen
        screen_geo = self.screen().availableGeometry() if self.screen() else None
        popup_width = 260
        popup_height = 280
        x = min(pos.x(), (screen_geo.width() - popup_width) if screen_geo else pos.x())
        y = min(pos.y(), (screen_geo.height() - popup_height) if screen_geo else pos.y())
        self.setGeometry(x, y, popup_width, popup_height)
        self.show()

    def _on_search(self, text: str) -> None:
        self._render_list(text)

    def _render_list(self, query: str) -> None:
        # Clear
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        q = query.lower()
        for var in self._variables:
            name = var.get("name", "")
            label = var.get("label", name)
            example = var.get("example", "")
            description = var.get("description", "")

            if q and not label.lower().startswith(q) and q not in name.lower():
                continue

            row = QWidget(self._list_widget)
            row.setStyleSheet(
                f"background: transparent; border-radius: {RADIUS_MD}px;"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(SPACE_2, SPACE_2, SPACE_2, SPACE_2)
            row_layout.setSpacing(SPACE_2)

            btn = QPushButton(f"{{{name}}}", row)
            btn.setToolTip(f"{description}\nExample: {example}")
            btn.setStyleSheet(
                f"QPushButton {{ background: {COLOR_ACCENT_SUBTLE}; color: {COLOR_ACCENT_PRIMARY}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; "
                f"font-weight: {FONT_WEIGHT_MEDIUM}; }}"
                f"QPushButton:hover {{ background: {COLOR_ACCENT_PRIMARY}; color: white; }}"
            )
            btn.clicked.connect(lambda checked, v=name: self._on_variable_chosen(v))
            row_layout.addWidget(btn)

            lbl = QLabel(label, row)
            lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
            row_layout.addWidget(lbl, 1)

            self._list_layout.addWidget(row)

        if not self._list_layout.count():
            empty = QLabel(
                t("automail.no_variables", "No variables match."),
                self._list_widget,
            )
            empty.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; padding: 8px;")
            self._list_layout.addWidget(empty)

    def _on_variable_chosen(self, name: str) -> None:
        self.variable_chosen.emit(name)
        self.close()
