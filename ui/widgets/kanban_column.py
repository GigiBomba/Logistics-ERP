"""QtKanbanColumn — PySide6 kanban column for the dispatch board.

Replaces ``ui/widgets/kanban_column.py`` (CTkFrame) with a QFrame-based
widget that holds :class:`QtTripCard` widgets.  Appearance is driven by
the global QSS in ``ui.qt_theme``; only dynamic state borders are set
inline (drag-drop visual feedback).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.theme import COLORS, S
from ui.widgets import ActionButton
from ui.widgets.trip_card import QtTripCard

logger = logging.getLogger(__name__)


class QtKanbanColumn(QFrame):
    """A single kanban column that displays a stack of trip cards.

    Layout (top → bottom)::

        ┌─────────────────────────────────┐
        │  Accent bar (4px, status color) │
        ├─────────────────────────────────┤
        │  Title  • N                     │
        ├─────────────────────────────────┤
        │  ┌─ QScrollArea ──────────────┐ │
        │  │  [Loading / Error]          │ │
        │  │  Card 1                     │ │
        │  │  Card 2                     │ │
        │  │  …                          │ │
        │  └─────────────────────────────┘ │
        │  [Load older] (optional)         │
        └─────────────────────────────────┘
    """

    COLUMN_BG = COLORS["bg_base"]
    HEADER_BG = COLORS["bg_surface"]
    ACCENT_HEIGHT = 4

    STATUS_COLORS: dict[str, str] = {
        "Planned": COLORS["chip_planned"],
        "Loading": COLORS["chip_loading"],
        "In Transit": COLORS["chip_transit"],
        "Delivered": COLORS["chip_delivered"],
        "Cancelled": COLORS["chip_cancelled"],
    }

    # Drag-and-drop: a trip card drag started on this column (or any
    # other column) is received here, the trip_id is parsed from the
    # MIME payload, and the parent board re-emits ``tripDropped`` so
    # only the board decides whether the move is legal (status order,
    # backward-move confirmation, etc.).
    tripDropped = Signal(int)   # trip_id

    def __init__(
        self,
        parent: QWidget,
        status_key: str,
        title_key: str,
        accent_color: str | None = None,
        on_card_click: Callable[[dict], None] | None = None,
        on_drag_start: Callable[[dict], None] | None = None,
        on_assign_truck: Callable[[dict], None] | None = None,
        on_assign_driver: Callable[[dict], None] | None = None,
        on_select_changed: Callable[[dict, bool], None] | None = None,
        on_assign_both: Callable[[dict], None] | None = None,
        show_load_older: bool = False,
        on_load_older: Callable[[], None] | None = None,
        on_retry: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "kanban-column")
        self.setFrameShape(QFrame.StyledPanel)
        # Accept drops on the column itself.  Without this, Qt's
        # drag-and-drop never reaches ``dragEnterEvent`` /
        # ``dropEvent`` on the column — the previous bug was that
        # the dispatch board set ``dropEvent`` on itself, but no
        # widget on the column was accepting drops, so the event
        # propagated past the column without firing the handler.
        self.setAcceptDrops(True)

        # ── Stored config ────────────────────────────────────────────────
        self.status_key: str = status_key
        self.title_key: str = title_key
        self.accent_color: str = (
            accent_color
            or self.STATUS_COLORS.get(status_key, COLORS["chip_planned"])
        )
        self._on_card_click = on_card_click
        self._on_drag_start = on_drag_start
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._on_select_changed = on_select_changed
        self._on_assign_both = on_assign_both
        self._show_load_older = show_load_older
        self._on_load_older = on_load_older
        self._on_retry = on_retry

        # ── Runtime state ────────────────────────────────────────────────
        self._cards: list[QtTripCard] = []
        self._state: str = "idle"  # "idle" | "loading" | "error"

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_accent_bar(layout)
        self._build_header(layout)
        self._build_scroll_area(layout)
        self._build_load_older_button(layout)

    # ── Accent bar ───────────────────────────────────────────────────────

    def _build_accent_bar(self, layout: QVBoxLayout) -> None:
        self._accent_bar = QFrame(self)
        self._accent_bar.setFixedHeight(self.ACCENT_HEIGHT)
        self._accent_bar.setStyleSheet(
            f"background-color: {self.accent_color}; border: none;"
        )
        layout.addWidget(self._accent_bar)

    # ── Header ──────────────────────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QWidget(self)
        header.setProperty("role", "kanban-column-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        header_layout.setSpacing(S["1"])

        self._title_label = QLabel(t(self.title_key))
        self._title_label.setProperty("fontRole", "kanban-column-title")
        header_layout.addWidget(self._title_label)

        self._count_label = QLabel(t("kanban.empty_count"))
        self._count_label.setProperty("fontRole", "kanban-column-count")
        header_layout.addWidget(self._count_label)

        header_layout.addStretch(1)
        layout.addWidget(header)

    # ── Scrollable card area ─────────────────────────────────────────────

    def _build_scroll_area(self, layout: QVBoxLayout) -> None:
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        scroll_content = QWidget()
        scroll_content.setProperty("role", "kanban-column-scroll")
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(S["1"], 0, S["1"], 0)
        self._scroll_layout.setSpacing(S["2"])
        self._scroll_layout.setAlignment(Qt.AlignTop)

        # -- Loading state widget (hidden by default) ---------------------
        self._loading_widget = QWidget()
        loading_layout = QVBoxLayout(self._loading_widget)
        loading_layout.setContentsMargins(0, S["10"], 0, 0)
        self._loading_label = QLabel("")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setProperty("fontRole", "kanban-column-loading")
        loading_layout.addWidget(self._loading_label)
        self._loading_widget.hide()
        self._scroll_layout.addWidget(self._loading_widget)

        # -- Error state widget (hidden by default) -----------------------
        self._error_widget = QWidget()
        error_layout = QVBoxLayout(self._error_widget)
        error_layout.setContentsMargins(S["3"], S["10"], S["3"], 0)
        error_layout.setSpacing(S["3"])
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.setProperty("fontRole", "kanban-column-error")
        error_layout.addWidget(self._error_label)

        self._retry_btn = ActionButton(
            self._error_widget,
            text=t("dispatch_board.retry"),
            variant="primary",
            command=self._handle_retry,
        )
        error_layout.addWidget(self._retry_btn, alignment=Qt.AlignCenter)
        self._error_widget.hide()
        self._scroll_layout.addWidget(self._error_widget)

        self._scroll_area.setWidget(scroll_content)
        layout.addWidget(self._scroll_area, 1)

    # ── Load-older button (optional) ─────────────────────────────────────

    def _build_load_older_button(self, layout: QVBoxLayout) -> None:
        if not self._show_load_older:
            self._load_older_widget = None  # type: ignore[assignment]
            return
        self._load_older_widget = QWidget(self)
        load_older_layout = QVBoxLayout(self._load_older_widget)
        load_older_layout.setContentsMargins(
            S["3"], S["1"], S["3"], S["1"]
        )
        self._load_older_btn = ActionButton(
            self._load_older_widget,
            text=t("dispatch_board.load_older"),
            variant="ghost",
            command=self._handle_load_older,
        )
        load_older_layout.addWidget(self._load_older_btn)
        layout.addWidget(self._load_older_widget)

    # ══════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ══════════════════════════════════════════════════════════════════════

    def _handle_retry(self) -> None:
        if self._on_retry is not None:
            self._on_retry()

    def _handle_load_older(self) -> None:
        if self._on_load_older is not None:
            self._on_load_older()

    def _card_layout_start_index(self) -> int:
        """Return the layout index where card widgets begin.

        The scroll layout always has two upfront items:
            index 0 → loading widget (hidden)
            index 1 → error widget (hidden)
        Cards start at index 2.
        """
        return 2

    def _update_count(self) -> None:
        self._count_label.setText(f" \u2022 {len(self._cards)}")

    def _clear_cards(self) -> None:
        """Remove and destroy all trip cards, hide loading/error overlays."""
        for card in self._cards:
            self._scroll_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._loading_widget.hide()
        self._error_widget.hide()

    # ══════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════

    # ── Trip data ────────────────────────────────────────────────────────

    def set_trips(self, trips: list[dict]) -> None:
        """Replace the column contents with the given *trips*.

        Existing cards whose ``trip_id_num`` still appears in *trips* are
        reused and updated via :meth:`QtTripCard.update_data`.  Removed
        cards are destroyed and new ones are created via
        :class:`~ui.widgets.trip_card.QtTripCard`.
        """
        self._loading_widget.hide()
        self._error_widget.hide()
        self._state = "idle"

        # Build lookup of existing cards by trip_id_num
        existing: dict[Any, QtTripCard] = {}
        stale: list[QtTripCard] = list(self._cards)
        for card in self._cards:
            tid = card.trip_data.get("trip_id_num")
            if tid is not None:
                existing[tid] = card

        # Reuse or create cards
        new_cards: list[QtTripCard] = []
        for trip in trips:
            tid = trip.get("trip_id_num")
            if tid is not None and tid in existing:
                card = existing[tid]
                card.update_data(trip)
                if card in stale:
                    stale.remove(card)
                new_cards.append(card)
            else:
                card = QtTripCard(
                    self._scroll_area.widget(),
                    trip,
                    on_click=self._on_card_click,
                    on_drag_start=self._on_drag_start,
                    on_assign_truck=self._on_assign_truck,
                    on_assign_driver=self._on_assign_driver,
                    on_select_changed=self._on_select_changed,
                    on_assign_both=self._on_assign_both,
                )
                self._scroll_layout.addWidget(card)
                new_cards.append(card)

        # Remove cards that are no longer in the trip list
        for old_card in stale:
            self._scroll_layout.removeWidget(old_card)
            old_card.deleteLater()

        # Reorder cards in layout to match new_cards order
        for card in new_cards:
            self._scroll_layout.removeWidget(card)
        for card in new_cards:
            self._scroll_layout.addWidget(card)

        self._cards = new_cards
        self._count_label.setText(f" \u2022 {len(trips)}")

        if self._show_load_older and self._load_older_widget is not None:
            self._load_older_widget.show()

    # ── Loading / error states ───────────────────────────────────────────

    def show_loading(self) -> None:
        """Clear cards and show a centered "Loading…" label."""
        self._clear_cards()
        self._state = "loading"
        self._count_label.setText(" \u2022 ...")
        self._loading_label.setText(t("dispatch_board.loading"))
        self._loading_widget.show()
        if self._show_load_older and self._load_older_widget is not None:
            self._load_older_widget.hide()

    def show_error(self, error_msg: str) -> None:
        """Clear cards and show the given *error_msg* with a retry button."""
        self._clear_cards()
        self._state = "error"
        self._count_label.setText(" \u2022 \u26a0")
        self._error_label.setText(error_msg)
        self._error_widget.show()
        if self._show_load_older and self._load_older_widget is not None:
            self._load_older_widget.hide()

    # ── Card manipulation ────────────────────────────────────────────────

    def add_card(self, card: QtTripCard, index: int = 0) -> None:
        """Insert *card* at the given *index* (default 0 = top).

        Hides any visible loading/error overlay before insertion.
        """
        self._loading_widget.hide()
        self._error_widget.hide()
        pos = self._card_layout_start_index() + index
        self._scroll_layout.insertWidget(pos, card)
        if index < len(self._cards):
            self._cards.insert(index, card)
        else:
            self._cards.append(card)
        self._update_count()

    def remove_card(self, card: QtTripCard) -> None:
        """Remove *card* from the column and schedule it for deletion."""
        if card in self._cards:
            self._cards.remove(card)
            self._scroll_layout.removeWidget(card)
            card.deleteLater()
            self._update_count()

    # ── Cleanup ──────────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Clear callbacks and schedule the widget for deletion."""
        self._clear_cards()
        self._on_card_click = None
        self._on_drag_start = None
        self._on_assign_truck = None
        self._on_assign_driver = None
        self._on_select_changed = None
        self._on_assign_both = None
        self._on_load_older = None
        self._on_retry = None
        super().deleteLater()

    # ── Translation refresh ──────────────────────────────────────────────

    def refresh_title(self) -> None:
        """Re-read i18n strings for the title, load-older, and retry button."""
        self._title_label.setText(t(self.title_key))
        if (
            self._show_load_older
            and self._load_older_widget is not None
            and hasattr(self, "_load_older_btn")
        ):
            self._load_older_btn.setText(t("dispatch_board.load_older"))
        if hasattr(self, "_retry_btn"):
            self._retry_btn.setText(t("dispatch_board.retry"))

    # ── Drag-drop visual feedback ────────────────────────────────────────

    def highlight_drop_zone(self) -> None:
        """Highlight the column border with the status accent color."""
        self.setStyleSheet(
            f"QtKanbanColumn {{ border: 2px solid {self.accent_color}; }}"
        )

    def unhighlight_drop_zone(self) -> None:
        """Remove the drag-drop border highlight."""
        self.setStyleSheet("")

    def highlight_valid(self) -> None:
        """Highlight the column border green (valid drop target)."""
        self.setStyleSheet(
            f"QtKanbanColumn {{ border: 2px solid {COLORS['success']}; }}"
        )

    def highlight_invalid(self) -> None:
        """Highlight the column border red (invalid drop target)."""
        self.setStyleSheet(
            f"QtKanbanColumn {{ border: 2px solid {COLORS['danger']}; }}"
        )

    # ══════════════════════════════════════════════════════════════════════
    # Drag-and-drop event handling
    # ══════════════════════════════════════════════════════════════════════

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept a drag if it carries a trip id.  This is the gate:
        without ``setAcceptDrops(True)`` (set in ``__init__``) and an
        accepting ``dragEnterEvent``, Qt's drop machinery never reaches
        the column."""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.highlight_valid()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Required by Qt — without it the cursor turns into the
        "no-drop" icon and the drop is rejected."""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        """Clear the visual highlight when the drag leaves the column."""
        self.unhighlight_drop_zone()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Parse the trip id from the MIME payload and re-emit
        ``tripDropped`` to the board.  The board decides whether the
        move is legal (status order, backward-move confirmation).
        """
        if not event.mimeData().hasText():
            event.ignore()
            return
        trip_id_str = event.mimeData().text()
        try:
            trip_id = int(trip_id_str)
        except (TypeError, ValueError):
            event.ignore()
            return
        event.acceptProposedAction()
        self.unhighlight_drop_zone()
        self.tripDropped.emit(trip_id)
