"""StatCardRow — a wrapping row of StatCard instances with intelligent width distribution.

Shared container used across all 4 screens (Panou, Alerte, Planificare, Control
Întreținere) to render KPI cards with consistent flow/wrap behavior.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.widgets.flow_layout import FlowLayout
from ui.widgets.stat_card import StatCard

_CARD_MIN_WIDTH = 200
_CARD_MAX_WIDTH = 320
_GAP = 12
_CONTAINER_MAX_WIDTH = 1400


class StatCardRow(QWidget):
    """Wrapping row of StatCard instances with width distribution.

    Cards are laid out in a FlowLayout. When there is enough horizontal space
    for all cards at their minimum width (200px), the row distributes available
    width evenly among cards, capping each at 320px. When the available width
    is insufficient, cards stay at min-width and the FlowLayout wraps them to a
    second row.

    The row container itself is capped at 1400px and centered within its parent
    when the parent is wider than 1400px (via ``StatCardRowContainer``).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMaximumWidth(_CONTAINER_MAX_WIDTH)

        self._cards: list[StatCard] = []
        self._layout = FlowLayout(self, margin=0, spacing=_GAP)
        self._resizing = False

    def add_card(self, card: StatCard) -> None:
        card.setMinimumWidth(_CARD_MIN_WIDTH)
        card.setMaximumWidth(_CARD_MAX_WIDTH)
        self._cards.append(card)
        self._layout.addWidget(card)

    def card_count(self) -> int:
        return len(self._cards)

    def clear(self) -> None:
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._resizing:
            self._resizing = True
            self._distribute()
            self._resizing = False

    def _distribute(self) -> None:
        n = len(self._cards)
        if n == 0:
            return

        ml, _, mr, _ = self._layout.getContentsMargins()
        available = self.width() - ml - mr
        gap_total = _GAP * (n - 1)
        min_total = _CARD_MIN_WIDTH * n + gap_total

        if available >= min_total:
            per_card = (available - gap_total) // n
            per_card = min(per_card, _CARD_MAX_WIDTH)
            per_card = max(per_card, _CARD_MIN_WIDTH)
            for card in self._cards:
                card.setFixedWidth(per_card)
        else:
            for card in self._cards:
                card.setFixedWidth(_CARD_MIN_WIDTH)


class StatCardRowContainer(QWidget):
    """Wraps a ``StatCardRow`` and centers it within the available width.

    When the parent window is wider than 1400px, the row stays at 1400px and
    the container distributes the leftover space as padding on both sides.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        from PySide6.QtWidgets import QHBoxLayout

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._row = StatCardRow(self)
        self._layout.addStretch()
        self._layout.addWidget(self._row)
        self._layout.addStretch()

    @property
    def row(self) -> StatCardRow:
        return self._row

    def add_card(self, card: StatCard) -> None:
        self._row.add_card(card)

    def card_count(self) -> int:
        return self._row.card_count()

    def clear(self) -> None:
        self._row.clear()
