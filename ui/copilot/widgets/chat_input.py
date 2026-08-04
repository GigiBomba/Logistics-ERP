"""ChatInputWidget — text input + send + mic button for the Co-Pilot.

Emits send_clicked(str) when the user presses Enter or clicks Send.
Emits mic_pressed / mic_released for push-to-talk voice capture.
Disables input while processing to prevent duplicate submissions.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    BTN_HEIGHT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    FONT_SIZE_BASE,
    FONT_WEIGHT_MEDIUM,
    INPUT_HEIGHT,
    RADIUS_LG,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)

# ── Mic button style constants ─────────────────────────────────────────

MIC_STYLE_IDLE = f"""
    QPushButton {{
        background-color: transparent;
        border: 1px solid {COLOR_BORDER_SUBTLE};
        border-radius: {RADIUS_LG}px;
        font-size: 16px;
        padding: 0px;
        height: {BTN_HEIGHT}px;
        width: {BTN_HEIGHT}px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BG_OVERLAY};
    }}
"""

MIC_STYLE_LISTENING = f"""
    QPushButton {{
        background-color: {COLOR_ERROR_DEFAULT};
        border: 2px solid {COLOR_ERROR_DEFAULT};
        border-radius: {RADIUS_LG}px;
        font-size: 16px;
        padding: 0px;
        height: {BTN_HEIGHT}px;
        width: {BTN_HEIGHT}px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ERROR_DEFAULT}CC;
    }}
"""

MIC_STYLE_PROCESSING = f"""
    QPushButton {{
        background-color: {COLOR_WARNING_DEFAULT};
        border: 2px solid {COLOR_WARNING_DEFAULT};
        border-radius: {RADIUS_LG}px;
        font-size: 16px;
        padding: 0px;
        height: {BTN_HEIGHT}px;
        width: {BTN_HEIGHT}px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_WARNING_DEFAULT}CC;
    }}
"""


class ChatInputWidget(QFrame):
    """Bottom input bar with a text field, mic button, and Send button.

    Signals:
        send_clicked(str): Emitted with the trimmed text when the user
            presses Enter or clicks Send.
        mic_pressed: Emitted when the microphone button is pressed down.
        mic_released: Emitted when the microphone button is released.
    """

    send_clicked = Signal(str)
    mic_pressed = Signal()
    mic_released = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Chat input")
        self.setAccessibleDescription("Text input bar for Co-Pilot chat")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("background: transparent; border: none;")

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_4, 0, SPACE_4, 0)
        layout.setSpacing(SPACE_3)

        # Text input
        self._input = QLineEdit()
        self._input.setAccessibleName("Chat message input")
        self._input.setPlaceholderText(
            t("copilot.input.placeholder", default="Ask me anything about your fleet...")
        )
        self._input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_LG}px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: {FONT_SIZE_BASE}px;
                padding: {SPACE_2}px {SPACE_3}px;
                height: {INPUT_HEIGHT}px;
            }}
            QLineEdit:focus {{
                border-color: {COLOR_ACCENT_PRIMARY};
            }}
            QLineEdit:disabled {{
                color: {COLOR_TEXT_TERTIARY};
                border-color: {COLOR_BORDER_SUBTLE};
            }}
            """
        )
        self._input.returnPressed.connect(self._on_send)
        layout.addWidget(self._input, 1)

        # Microphone button — push-to-talk
        self._mic_btn = QPushButton("\U0001f3a4")  # 🎤
        self._mic_btn.setAccessibleName("Microphone")
        self._mic_btn.setToolTip(
            t("copilot.voice.ptt_tooltip", default="Hold to record — release to send")
        )
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.pressed.connect(self.mic_pressed)
        self._mic_btn.released.connect(self.mic_released)
        self.set_mic_state("idle")
        layout.addWidget(self._mic_btn)

        # Send button
        self._send_btn = QPushButton(t("copilot.input.send", default="Send"))
        self._send_btn.setAccessibleName("Send message")
        self._send_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_PRIMARY};
                color: white;
                border: none;
                border-radius: {RADIUS_LG}px;
                padding: {SPACE_2}px {SPACE_5}px;
                font-size: {FONT_SIZE_BASE}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                height: {BTN_HEIGHT}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_TERTIARY};
            }}
            """
        )
        self._send_btn.clicked.connect(self._on_send)
        layout.addWidget(self._send_btn)

    def _on_send(self) -> None:
        """Emit the trimmed text and clear the input."""
        text = self._input.text().strip()
        if text:
            # Client-side pre-sanitization: strip control characters
            # and zero-width characters before the text reaches the
            # API.  This is defense-in-depth — the server also
            # sanitizes via InputSanitizationMiddleware.
            import re as _re
            text = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\u200c\u200d\ufeff]', '', text)
            if text:
                self.send_clicked.emit(text)
            self._input.clear()

    def set_text(self, text: str) -> None:
        """Pre-fill the input field with text without sending."""
        self._input.setText(text)

    def set_processing(self, processing: bool) -> None:
        """Enable/disable the input while processing a request."""
        self._input.setEnabled(not processing)
        self._send_btn.setEnabled(not processing)
        if not processing:
            self._input.setFocus()

    # ── Mic state management ───────────────────────────────────────────

    def set_mic_state(self, state: str) -> None:
        """Update the mic button appearance.

        Args:
            state: One of ``"idle"``, ``"listening"``, ``"processing"``.
        """
        style_map = {
            "idle": MIC_STYLE_IDLE,
            "listening": MIC_STYLE_LISTENING,
            "processing": MIC_STYLE_PROCESSING,
        }
        ss = style_map.get(state, MIC_STYLE_IDLE)
        self._mic_btn.setStyleSheet(ss)

        tooltip_map = {
            "idle": t("copilot.voice.ptt_tooltip",
                       default="Hold to record — release to send"),
            "listening": t("copilot.voice.listening_tooltip",
                           default="Recording… release to send"),
            "processing": t("copilot.voice.processing_tooltip",
                            default="Processing voice…"),
        }
        self._mic_btn.setToolTip(tooltip_map.get(state, tooltip_map["idle"]))

    def set_mic_visible(self, visible: bool) -> None:
        """Show or hide the microphone button."""
        self._mic_btn.setVisible(visible)

    def set_mic_enabled(self, enabled: bool) -> None:
        """Enable or disable the microphone button."""
        self._mic_btn.setEnabled(enabled)
