"""Collapsible country exclusions panel for the Qt route planner.

Replaces ``ui/route_planner_exclusions.py``. Uses ``CountryAvoidanceManager``
for business logic and ``StyledCheckBox`` for the country chip layout.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
)

from services.country_avoidance import CountryAvoidanceManager
from services.i18n import t
from ui.widgets import StyledCheckBox
from ui.theme import COLORS

logger = logging.getLogger(__name__)


class CountryExclusionsPanel(QWidget):
    """Collapsible excluded-countries section with checkbox chips."""

    def __init__(
        self,
        parent: Optional[QWidget],
        avoidance: CountryAvoidanceManager,
        on_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.avoidance = avoidance
        self.on_change = on_change
        self._expanded = True
        self._checkboxes: List[StyledCheckBox] = []
        self._build()

    def _notify(self) -> None:
        if self.on_change:
            self.on_change()

    def get_selected(self) -> List[str]:
        return self.avoidance.get_selected()

    def set_selected(self, codes: List[str]) -> None:
        self.avoidance.set_selected(codes)
        self.refresh()

    def refresh(self) -> None:
        selected = set(self.avoidance.get_selected())
        for cb in self._checkboxes:
            code = cb.property("country_code")
            cb.blockSignals(True)
            cb.setChecked(code in selected)
            cb.blockSignals(False)
        self._update_count_label()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        section = QFrame(self)
        section.setProperty("role", "card")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 4, 8, 8)
        section_layout.setSpacing(4)

        # Header row
        header = QFrame(section)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(6)

        self._toggle_btn = QPushButton("\u25be" if self._expanded else "\u25b8")
        self._toggle_btn.setProperty("role", "nav-toggle")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_section)
        header_layout.addWidget(self._toggle_btn)

        self._header_label = QLabel(t("route.exclusions_label"))
        self._header_label.setProperty("fontRole", "body_bold")
        header_layout.addWidget(self._header_label)

        header_layout.addStretch(1)

        self._count_label = QLabel("0")
        self._count_label.setProperty("fontRole", "small")
        self._count_label.setStyleSheet(
            f"background-color: {COLORS.get('bg_elevated', '#27272a')};"
            " border-radius: 8px; padding: 2px 8px;"
        )
        header_layout.addWidget(self._count_label)

        section_layout.addWidget(header)

        # Country chips container
        self._chips_container = QFrame(section)
        self._chips_layout = QVBoxLayout(self._chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(2)
        section_layout.addWidget(self._chips_container)

        layout.addWidget(section)

        self._populate_countries()

    def _populate_countries(self) -> None:
        countries = self.avoidance.get_all_countries()
        selected = set(self.avoidance.get_selected())
        codes = sorted(countries.items(), key=lambda x: x[1])

        # Use a grid layout with 4 columns
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        for i, (code, name) in enumerate(codes):
            cb = StyledCheckBox(text=f"{name}")
            cb.setProperty("country_code", code)
            cb.setChecked(code in selected)
            cb.stateChanged.connect(self._on_country_toggled)
            row, col = divmod(i, 4)
            grid.addWidget(cb, row, col)
            self._checkboxes.append(cb)

        self._chips_layout.addLayout(grid)
        self._update_count_label()

    def _on_country_toggled(self, state: int) -> None:
        sender = self.sender()
        if sender is None:
            return
        code = sender.property("country_code")
        if code:
            try:
                self.avoidance.toggle(code)
            except Exception:
                pass
        self._update_count_label()
        self._notify()

    def _update_count_label(self) -> None:
        count = len(self.avoidance.get_selected())
        self._count_label.setText(str(count))

    def _toggle_section(self) -> None:
        self._expanded = not self._expanded
        self._chips_container.setVisible(self._expanded)
        self._toggle_btn.setText("\u25be" if self._expanded else "\u25b8")
