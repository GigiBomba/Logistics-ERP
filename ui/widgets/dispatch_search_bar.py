"""Search and filter bar for the dispatch board kanban (PySide6).

Replaces ``ui/widgets/dispatch_search_bar.py``. Provides a search entry, status
filter checkboxes with colored indicators, and a result count label.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_SUBTLE,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_SUCCESS_SUBTLE,
    COLOR_WARNING_SUBTLE,
    SP,
)
from ui.widgets import ActionButton, StyledCheckBox
from ui.widgets.debounced_line_edit import DebouncedLineEdit

STATUS_OPTIONS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]

_STATUS_COLORS: dict[str, str] = {
    "Planned": COLOR_ACCENT_SUBTLE,
    "Loading": COLOR_WARNING_SUBTLE,
    "In Transit": COLOR_WARNING_SUBTLE,
    "Delivered": COLOR_SUCCESS_SUBTLE,
    "Cancelled": COLOR_NEUTRAL_SUBTLE,
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
        parent: QWidget | None = None,
        on_search: Callable[[str, list[str]], None] | None = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self._on_search = on_search
        self._checkboxes: dict[str, StyledCheckBox] = {}
        self._result_lbl: QLabel | None = None

        self._build()

    # ── Layout ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["2"], SP["1"], SP["2"], 0)
        layout.setSpacing(SP["1"])

        # Top row ----------------------------------------------------------------
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SP["2"])

        # Search icon
        icon = QLabel("\U0001f50d")
        icon.setProperty("fontRole", "muted")
        icon.setFixedWidth(20)
        row_layout.addWidget(icon)

        # Search entry
        self._entry = DebouncedLineEdit(
            parent=row,
            placeholder=t("dispatch_board.search_placeholder"),
        )
        self._entry.debouncedTextChanged.connect(self._fire_search)
        row_layout.addWidget(self._entry, 1)

        # Status checkboxes with colored dots
        status_frame = QWidget()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(SP["1"])

        for status in STATUS_OPTIONS:
            item = QWidget(status_frame)
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(4)

            # Colored dot (8px circle)
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background-color: {_STATUS_COLORS[status]};"
                f" border-radius: 4px; border: none;"
            )
            item_layout.addWidget(dot)

            cb = StyledCheckBox(parent=item, text=status)
            cb.setProperty("role", "filter")
            cb.setChecked(True)
            cb.stateChanged.connect(self._fire_search)
            self._checkboxes[status] = cb
            item_layout.addWidget(cb)

            status_layout.addWidget(item)

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
        self._result_lbl.setContentsMargins(SP["2"], 0, 0, SP["1"])
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
                t("dispatch_board.showing_trips", default="Showing {} of {} trips").format(visible, total)
            )
        else:
            self._result_lbl.setText(t("dispatch_board.count_trips", default="{} trips").format(total))

    # ── Internals ───────────────────────────────────────────────────────────────

    def _fire_search(self, *args: object) -> None:
        """Collect current query and active statuses, then invoke callback."""
        if self._on_search is None:
            return
        query = self._entry.text().strip().lower()
        statuses = [s for s, cb in self._checkboxes.items() if cb.isChecked()]
        self._on_search(query, statuses)

    def _destroy(self) -> None:
        """Clear callback and checkbox references, then schedule deletion."""
        self._on_search = None
        self._checkboxes.clear()
        self._result_lbl = None
        super().deleteLater()

    def _clear(self) -> None:
        """Reset search text and check all statuses."""
        self._entry.setText("")
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._fire_search()
