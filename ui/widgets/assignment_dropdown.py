"""QtAssignmentDropdown — PySide6 popup for selecting assignable items (trucks/drivers).

Replaces ``ui/widgets/assignment_dropdown.py`` (CTkToplevel).

Usage::

    items = self._fetch_assignable()
    dropdown = QtAssignmentDropdown(
        self,
        anchor_widget=self._truck_btn,
        title=t("dispatch_board.assign_truck"),
        fetch_func=self._fetch_assignable,
        on_select=self._on_truck_selected,
    )
    dropdown.show_anchored(self._truck_btn)
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_BG_OVERLAY,
    COLOR_ERROR_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
    SP,
)

_MAX_HEIGHT = 300
_WIDTH = 280
_ROW_HEIGHT = 44


class _ItemRow(QFrame):
    """A single selectable row in the assignment dropdown.

    Shows an availability dot, label, sublabel, and optional status text.
    Unavailable items render with muted text and no hover/click interaction.
    """

    def __init__(
        self,
        item: dict[str, Any],
        on_select: Callable[[Any], None],
    ) -> None:
        super().__init__()
        self.setProperty("role", "assignment-row")
        self.setFixedHeight(_ROW_HEIGHT)

        available = item.get("available", True)
        item_id = item.get("id")
        label = item.get("label", "")
        sublabel = item.get("sublabel", "")
        status_text = item.get("status_text", "")

        self._available = available
        self._item_id = item_id
        self._on_select = on_select

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SP["3"], 0, SP["3"], 0)
        layout.setSpacing(SP["2"])

        # -- Availability dot ------------------------------------------------
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setProperty("role", "availability-dot")
        if available:
            dot.setStyleSheet(
                f"background-color: {COLOR_SUCCESS_DEFAULT};"
                f"border-radius: 4px;"
            )
        else:
            dot.setStyleSheet(
                f"background-color: {COLOR_TEXT_TERTIARY};"
                f"border-radius: 4px;"
            )
        layout.addWidget(dot, 0)

        # -- Text area -------------------------------------------------------
        text_widget = QWidget()
        text_widget.setProperty("role", "assignment-row-text")
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        text_color = COLOR_TEXT_PRIMARY if available else COLOR_TEXT_TERTIARY

        label_widget = QLabel(label)
        label_widget.setProperty("fontRole", "small")
        label_widget.setStyleSheet(f"color: {text_color};")
        text_layout.addWidget(label_widget)

        if sublabel:
            sub_widget = QLabel(sublabel)
            sub_widget.setProperty("fontRole", "muted")
            text_layout.addWidget(sub_widget)

        layout.addWidget(text_widget, 1)

        # -- Status text (unavailable only) ----------------------------------
        if status_text and not available:
            status_label = QLabel(status_text)
            status_label.setProperty("fontRole", "warning")
            layout.addWidget(status_label, 0)

        # -- Click / hover behaviour -----------------------------------------
        if available:
            self.setCursor(Qt.PointingHandCursor)
            self._install_click_handler()
        else:
            self.setCursor(Qt.ArrowCursor)

    def _install_click_handler(self) -> None:
        """Wire up mouse clicks and hover events on this row and its children."""
        self.mousePressEvent = self._on_click  # type: ignore[assignment]
        # Walk all child widgets so clicks land regardless of where the
        # user presses.
        self._walk_set_click(self)

    def _walk_set_click(self, widget: QWidget) -> None:
        """Recursively assign click and hover handlers to *widget* and its children."""
        original = getattr(widget, "mousePressEvent", None)
        if original is None or original.__func__ is QWidget.mousePressEvent:
            widget.mousePressEvent = self._on_click  # type: ignore[assignment]

        for child in widget.findChildren(QWidget, options=Qt.FindChildrenRecursively):
            if child.mousePressEvent is None or child.mousePressEvent.__func__ is QWidget.mousePressEvent:
                child.mousePressEvent = self._on_click  # type: ignore[assignment]

    def _on_click(self, event=None) -> None:
        if self._available and self._on_select:
            self._on_select(self._item_id)

    def enterEvent(self, event) -> None:
        if self._available:
            self.setStyleSheet(
                f"QFrame[role=\"assignment-row\"] {{"
                f"  background-color: {COLOR_BG_OVERLAY};"
                f"}}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._available:
            self.setStyleSheet("")
        super().leaveEvent(event)


class QtAssignmentDropdown(QFrame):
    """Popup dropdown anchored below a widget, showing assignable items.

    Displays a header with a title and close button, a scrollable list of
    item rows, loading/error/empty states, and auto-closes on focus loss.
    """

    MAX_HEIGHT = _MAX_HEIGHT
    WIDTH = _WIDTH

    def __init__(
        self,
        parent: QWidget,
        anchor_widget: QWidget,
        title: str,
        fetch_func: Callable[[], list[dict[str, Any]]],
        on_select: Callable[[Any], None],
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setProperty("role", "assignment-dropdown")
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self._anchor = anchor_widget
        self._fetch_func = fetch_func
        self._on_select = on_select
        self._on_close = on_close
        self._items: list[dict[str, Any]] = []

        # Outer container with a 1px border simulation using a QFrame border
        # style. The QSS theme handles the visual border via role selector.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header(layout, title)
        self._build_scroll_area(layout)
        self._show_loading()

        # Pre-position before showing so the popup appears at the correct
        # location immediately.
        self._pre_position()

        # Start loading items after a short deferral so the UI thread
        # has time to paint the initial state.
        QTimer.singleShot(0, self._load_items)

    # ── Public API ──────────────────────────────────────────────────────────

    def show_anchored(self, anchor: QWidget) -> None:
        """Position the dropdown below *anchor* and show it."""
        if anchor is None:
            return
        self._position_at_anchor(anchor)
        self.show()
        self.raise_()
        self.setFocus()

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout, title: str) -> None:
        header = QWidget()
        header.setProperty("role", "assignment-dropdown-header")
        header.setFixedHeight(38)

        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(SP["3"], 0, SP["2"], 0)
        hdr_layout.setSpacing(0)

        title_label = QLabel(title)
        title_label.setProperty("fontRole", "small")
        hdr_layout.addWidget(title_label)
        hdr_layout.addStretch(1)

        close_btn = QLabel("\u2715")
        close_btn.setProperty("role", "assignment-dropdown-close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.mousePressEvent = lambda _: self._close()  # type: ignore[assignment]
        hdr_layout.addWidget(close_btn)

        layout.addWidget(header)

    # ── Scroll area ─────────────────────────────────────────────────────────

    def _build_scroll_area(self, layout: QVBoxLayout) -> None:
        self._scroll = QScrollArea()
        self._scroll.setProperty("role", "assignment-dropdown-scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(self.MAX_HEIGHT)

        self._content = QWidget()
        self._content.setProperty("role", "assignment-dropdown-list")
        self._list_layout = QVBoxLayout(self._content)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(1)
        self._list_layout.setAlignment(Qt.AlignTop)

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    # ── Loading / error / empty states ──────────────────────────────────────

    def _show_loading(self) -> None:
        """Replace list content with a loading indicator."""
        self._clear_list()
        spinner = QLabel(t("dispatch_board.loading_options"))
        spinner.setProperty("fontRole", "muted")
        spinner.setAlignment(Qt.AlignCenter)
        spinner.setFixedHeight(self.MAX_HEIGHT)
        self._list_layout.addWidget(spinner)

    def _show_error(self, error_msg: str) -> None:
        """Replace list content with an error message."""
        self._clear_list()
        err_label = QLabel(f"{t('dispatch_board.load_error')}: {error_msg}")
        err_label.setProperty("fontRole", "danger")
        err_label.setAlignment(Qt.AlignCenter)
        err_label.setWordWrap(True)
        err_label.setFixedHeight(self.MAX_HEIGHT)
        self._list_layout.addWidget(err_label)

    def _show_empty(self) -> None:
        """Replace list content with an empty-state message."""
        self._clear_list()
        empty_label = QLabel(t("dispatch_board.no_options"))
        empty_label.setProperty("fontRole", "muted")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setFixedHeight(self.MAX_HEIGHT)
        self._list_layout.addWidget(empty_label)

    def _clear_list(self) -> None:
        """Remove all widgets from the list layout."""
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    # ── Data loading ────────────────────────────────────────────────────────

    def _load_items(self) -> None:
        """Execute the fetch function and render items (or show error)."""
        try:
            items = self._fetch_func()
            self._items = items
            self._render_items()
        except Exception as exc:
            self._show_error(str(exc))

    def _render_items(self) -> None:
        """Render item rows or show empty state."""
        self._clear_list()

        if not self._items:
            self._show_empty()
            return

        for item in self._items:
            row = _ItemRow(item, self._on_select)
            self._list_layout.addWidget(row)

    # ── Positioning ─────────────────────────────────────────────────────────

    def _pre_position(self) -> None:
        """Apply initial geometry before show() to avoid flicker."""
        self.setFixedSize(self.WIDTH, self.MAX_HEIGHT + 38)  # header + scroll

    def _position_at_anchor(self, anchor: QWidget) -> None:
        """Move the dropdown below *anchor*, flipping above if off-screen."""
        if anchor is None:
            return
        global_pos = anchor.mapToGlobal(QPoint(0, 0))
        x = global_pos.x()
        y = global_pos.y() + anchor.height() + 2

        screen = self.screen()
        if screen:
            screen_geom = screen.availableGeometry()
            if y + self.height() > screen_geom.bottom():
                y = global_pos.y() - self.height() - 2

        self.move(x, y)

    # ── Focus-out auto-close ────────────────────────────────────────────────

    def focusOutEvent(self, event) -> None:
        """Close when focus moves outside this dropdown."""
        super().focusOutEvent(event)
        QTimer.singleShot(0, self._close)

    # ── Close ───────────────────────────────────────────────────────────────

    def _close(self) -> None:
        """Close the dropdown and fire the *on_close* callback if set."""
        try:
            self.close()
        except Exception:
            pass
        finally:
            if self._on_close:
                self._on_close()
