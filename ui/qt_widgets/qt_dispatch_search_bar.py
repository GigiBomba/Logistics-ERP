"""Search and filter bar for the dispatch board kanban (PySide6).

Replaces ``ui/widgets/dispatch_search_bar.py``. Provides a search entry, status
filter checkboxes with colored indicators, and a result count label.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.theme import COLORS, S
from ui.qt_widgets import ActionButton, StyledCheckBox, StyledLineEdit


STATUS_OPTIONS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]

_STATUS_COLORS: dict[str, str] = {
    "Planned": COLORS["chip_planned"],
    "Loading": COLORS["chip_loading"],
    "In Transit": COLORS["chip_transit"],
    "Delivered": COLORS["chip_delivered"],
    "Cancelled": COLORS["chip_cancelled"],
}


class QtDispatchSearchBar(QFrame):
    """Search + status filter bar above kanban columns.

    Parameters
    ----------
    parent : QWidget or None
        Parent widget.
    on_search : callable or None
        Called as ``on_search(query: str, statuses: list[str])`` whenever the
        search query or status filter selection changes.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_search: Optional[Callable[[str, list[str]], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self._on_search = on_search
        self._checkboxes: dict[str, StyledCheckBox] = {}
        self._result_lbl: Optional[QLabel] = None

        self._build()

    # ── Layout ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S["2"], S["1"], S["2"], 0)
        layout.setSpacing(S["1"])

        # Top row ----------------------------------------------------------------
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(S["2"])

        # Search icon
        icon = QLabel("\U0001f50d")
        icon.setProperty("fontRole", "muted")
        icon.setFixedWidth(20)
        row_layout.addWidget(icon)

        # Search entry
        self._entry = StyledLineEdit(
            parent=row,
            placeholder=t("dispatch_board.search_placeholder"),
            height=30,
        )
        self._entry.textEdited.connect(self._fire_search)
        row_layout.addWidget(self._entry, 1)

        # Status checkboxes
        status_frame = QWidget()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(S["1"])

        for status in STATUS_OPTIONS:
            cb = StyledCheckBox(parent=status_frame, text=status)
            cb.setChecked(True)
            chip_color = _STATUS_COLORS.get(status, COLORS["chip_idle"])
            cb.setStyleSheet(
                "QCheckBox::indicator:checked {"
                f"  background-color: {chip_color};"
                f"  border-color: {chip_color};"
                "}"
            )
            cb.stateChanged.connect(self._fire_search)
            self._checkboxes[status] = cb
            status_layout.addWidget(cb)

        row_layout.addWidget(status_frame)

        # Clear button
        clear_btn = ActionButton(parent=row, text="\u2715", variant="ghost")
        clear_btn.setFixedSize(28, 28)
        clear_btn.clicked.connect(self._clear)
        row_layout.addWidget(clear_btn)

        layout.addWidget(row)

        # Result count label -----------------------------------------------------
        self._result_lbl = QLabel("")
        self._result_lbl.setProperty("fontRole", "muted")
        self._result_lbl.setContentsMargins(S["2"], 0, 0, S["1"])
        layout.addWidget(self._result_lbl)

    # ── Public API ──────────────────────────────────────────────────────────────

    def set_result_count(self, visible: int, total: int) -> None:
        """Update the result count label.

        Shows "Showing X of Y trips" when a filter is active, or "Y trips"
        when all results are visible.
        """
        if self._result_lbl is None:
            return
        if visible < total:
            self._result_lbl.setText(
                f"Showing {visible} of {total} trips"
            )
        else:
            self._result_lbl.setText(f"{total} trips")

    # ── Internals ───────────────────────────────────────────────────────────────

    def _fire_search(self, *args: object) -> None:
        """Collect current query and active statuses, then invoke callback."""
        if self._on_search is None:
            return
        query = self._entry.text().strip().lower()
        statuses = [s for s, cb in self._checkboxes.items() if cb.isChecked()]
        self._on_search(query, statuses)

    def _clear(self) -> None:
        """Reset search text and check all statuses."""
        self._entry.setText("")
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._fire_search()
