"""ConversationDisplayWidget — scrollable conversation view for the Co-Pilot.

Holds ChatBubbleWidget instances and a ThinkingIndicatorWidget.
Provides add_message(), show_thinking(), hide_thinking(), and clear().
Auto-scrolls to bottom on new content.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
from ui.copilot.widgets.thinking_indicator import ThinkingIndicatorWidget
from ui.design_tokens import (
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_BASE,
    SPACE_4,
)


class ConversationDisplayWidget(QScrollArea):
    """Scrollable container for chat bubbles and the thinking indicator.

    Public API:
        add_message(text, is_user, timestamp)
        show_thinking()
        hide_thinking()
        clear()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        # Container widget
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        self._layout.setSpacing(SPACE_4)
        self._layout.setAlignment(Qt.AlignTop)

        # Empty state
        self._empty_label = QLabel(t("copilot.chat.empty"))
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_BASE}px; "
            f"background: transparent; border: none;"
        )
        self._layout.addWidget(self._empty_label)

        # Thinking indicator (hidden by default)
        self._thinking = ThinkingIndicatorWidget()
        self._layout.addWidget(self._thinking)

        # Spacer to keep bubbles at top
        self._spacer = QWidget()
        self._spacer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._spacer.setStyleSheet("background: transparent;")
        self._layout.addWidget(self._spacer)

        self.setWidget(self._container)

    def add_message(
        self,
        text: str,
        is_user: bool = False,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Append a chat bubble to the conversation."""
        # Hide empty state on first message
        self._empty_label.setVisible(False)

        bubble = ChatBubbleWidget(
            message=text,
            is_user=is_user,
            timestamp=timestamp or datetime.now(),
        )
        # Insert before the thinking indicator
        self._layout.insertWidget(self._layout.count() - 2, bubble)

        # Auto-scroll to bottom
        self._scroll_to_bottom()

    def show_thinking(self) -> None:
        """Show the thinking indicator."""
        self._thinking.start()
        self._scroll_to_bottom()

    def hide_thinking(self) -> None:
        """Hide the thinking indicator."""
        self._thinking.stop()

    def clear(self) -> None:
        """Clear all messages and show empty state."""
        # Remove all ChatBubbleWidgets
        for i in range(self._layout.count() - 1, -1, -1):
            item = self._layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is not None and isinstance(w, ChatBubbleWidget):
                self._layout.removeWidget(w)
                w.deleteLater()

        self._empty_label.setVisible(True)
        self._thinking.stop()

    def _scroll_to_bottom(self) -> None:
        """Scroll the scroll area to the bottom."""
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self, self._perform_scroll)

    def _perform_scroll(self) -> None:
        """Actually perform the scroll (called via single-shot timer)."""
        scrollbar = self.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())
