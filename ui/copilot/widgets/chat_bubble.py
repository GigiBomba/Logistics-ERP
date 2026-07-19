"""ChatBubbleWidget — single message bubble for the Co-Pilot conversation.

Blueprint: §2.2. Two variants: user (right-aligned) and assistant (left-aligned).
Uses design tokens for styling and i18n for role labels.
"""

from __future__ import annotations

from datetime import datetime

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
from ui.design_tokens import (
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_CARD,
    COLOR_BG_ELEVATED,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_2,
    SPACE_3,
    SPACE_4,
)


class ChatBubbleWidget(QFrame):
    """A single message bubble in the Co-Pilot conversation.

    Args:
        message: The message text to display.
        is_user: True for "You" (right-aligned), False for "Co-Pilot" (left-aligned).
        timestamp: Optional datetime for the timestamp label.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        message: str,
        is_user: bool = False,
        timestamp: datetime | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_user = is_user
        self._message = message
        self._timestamp = timestamp or datetime.now()

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("background: transparent; border: none;")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add stretch on the opposite side to push bubble to correct alignment
        if self._is_user:
            layout.addStretch(1)

        # Bubble container
        bubble = QFrame()
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        bubble.setMaximumWidth(480)

        bubble_style = f"""
            QFrame {{
                background-color: {COLOR_ACCENT_SUBTLE if self._is_user else COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_LG}px;
            }}
        """
        bubble.setStyleSheet(bubble_style)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        bubble_layout.setSpacing(SPACE_2)

        # Role label
        role_key = "copilot.chat.you" if self._is_user else "copilot.chat.co_pilot"
        role_lbl = QLabel(t(role_key))
        role_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_XS}px; "
            f"font-weight: {FONT_WEIGHT_SEMIBOLD}; background: transparent; border: none;"
        )
        bubble_layout.addWidget(role_lbl)

        # Message text
        msg_lbl = QLabel(self._message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SM}px; "
            f"background: transparent; border: none;"
        )
        bubble_layout.addWidget(msg_lbl)

        # Timestamp
        ts_str = self._timestamp.strftime("%H:%M")
        ts_lbl = QLabel(ts_str)
        ts_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_XS}px; "
            f"background: transparent; border: none;"
        )
        ts_lbl.setAlignment(Qt.AlignRight if self._is_user else Qt.AlignLeft)
        bubble_layout.addWidget(ts_lbl)

        layout.addWidget(bubble)

        if not self._is_user:
            layout.addStretch(1)
