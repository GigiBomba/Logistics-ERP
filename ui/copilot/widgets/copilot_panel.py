"""CoPilotPanel — full chat UI for the AI Co-Pilot with voice support.

Blueprint: §2 — INPUT LAYER, §12 — Explainability & Timeline.

Composes:
    - Header with title + "New Conversation" button + voice mode selector (Enterprise)
    - ConversationDisplayWidget (scrollable chat bubbles)
    - ThinkingIndicatorWidget (3-dot animation)
    - ChatInputWidget (text input + mic + send)

Handles:
    - Text send -> display user bubble -> call controller -> display response/error
    - Push-to-talk via AudioRecorder + mic button
    - Voice mode selector (Enterprise tier) with wake-word placeholder (Phase 3)
    - i18n language changes via register_listener
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import get_language, register_listener, t, unregister_listener
from ui.copilot.audio_recorder import AudioRecorder
from ui.copilot.controllers.copilot_controller import CoPilotController
from ui.copilot.widgets.chat_input import ChatInputWidget
from ui.copilot.widgets.conversation_display import ConversationDisplayWidget
from ui.design_tokens import (
    BTN_HEIGHT_SM,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG,
    RADIUS_MD,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)
from ui.widgets import StyledComboBox

logger = logging.getLogger(__name__)


class CoPilotPanel(QFrame):
    """AI Co-Pilot chat panel -- dockable, Phase 1+ chat UI with voice.

    Parameters
    ----------
    parent : QWidget | None
        Parent widget.
    controller : CoPilotController | None
        Backend controller for chat / voice actions.
    enterprise_voice : bool
        When ``True`` the voice-mode combo box is shown (Enterprise tier).
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        controller: Optional[CoPilotController] = None,
        enterprise_voice: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("copilot-panel")
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setStyleSheet(f"background-color: {COLOR_BG_BASE};")

        self._controller = controller
        self._enterprise_voice = enterprise_voice
        self._recorder = AudioRecorder(self)

        self._voice_mode_combo: Optional[QComboBox] = None
        self._wake_word_notice: Optional[QLabel] = None

        self._i18n_callback = self._on_language_changed
        register_listener(self._i18n_callback)

        self._build_ui()
        self._connect_voice()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Header --------------------------------------------------------
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {COLOR_BG_ELEVATED}; border: none;"
            f"border-bottom: 1px solid {COLOR_BORDER_SUBTLE};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)

        self._title_label = QLabel(
            t("copilot.panel.title", default="AI Co-Pilot")
        )
        self._title_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_LG}px; "
            f"font-weight: {FONT_WEIGHT_SEMIBOLD}; background: transparent; border: none;"
        )
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)

        # Voice mode selector (Enterprise only)
        if self._enterprise_voice:
            self._voice_mode_combo = StyledComboBox(
                values=[
                    t("copilot.voice.mode_ptt", default="Push to Talk"),
                    t("copilot.voice.mode_wake_word", default="Wake Word"),
                ],
            )
            self._voice_mode_combo.setStyleSheet(
                f"font-size: {FONT_SIZE_XS}px; height: {BTN_HEIGHT_SM}px;"
            )
            self._voice_mode_combo.currentTextChanged.connect(
                self._on_voice_mode_changed
            )
            header_layout.addWidget(self._voice_mode_combo)

            # Wake-word coming-soon notice (hidden by default)
            self._wake_word_notice = QLabel(
                t(
                    "copilot.voice.wake_word_phase3",
                    default="Wake word support coming in Phase 3. "
                    "Switching back to Push to Talk.",
                )
            )
            self._wake_word_notice.setWordWrap(True)
            self._wake_word_notice.setStyleSheet(
                f"""
                color: {COLOR_WARNING_DEFAULT};
                font-size: {FONT_SIZE_BASE}px;
                padding: {SPACE_2}px {SPACE_3}px;
                background-color: {COLOR_BG_OVERLAY};
                border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
            """
            )
            self._wake_word_notice.setVisible(False)

        # New Conversation button
        self._new_btn = QPushButton(t("copilot.chat.new_conversation"))
        self._new_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_MD}px;
                font-size: {FONT_SIZE_XS}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                padding: 4px {SPACE_3}px;
                height: {BTN_HEIGHT_SM}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
            }}
            """
        )
        self._new_btn.clicked.connect(self._on_new_conversation)
        header_layout.addWidget(self._new_btn)

        layout.addWidget(header)

        # Wake-word notice (placed below header bar if visible)
        if self._wake_word_notice is not None:
            layout.addWidget(self._wake_word_notice)

        # -- Conversation display -----------------------------------------
        self._conversation = ConversationDisplayWidget()
        layout.addWidget(self._conversation, 1)

        # -- Chat input ----------------------------------------------------
        self._chat_input = ChatInputWidget()
        self._chat_input.send_clicked.connect(self._on_send_clicked)
        layout.addWidget(self._chat_input)

    # -- Voice wiring ------------------------------------------------------

    def _connect_voice(self) -> None:
        """Connect mic button and recorder signals."""
        self._chat_input.mic_pressed.connect(self._on_mic_pressed)
        self._chat_input.mic_released.connect(self._on_mic_released)
        self._recorder.audio_ready.connect(self._on_audio_ready)
        self._recorder.error_occurred.connect(self._on_recorder_error)

    # -- Public API --------------------------------------------------------

    def ask_about_element(self, question: str, active_screen: str | None = None) -> None:
        """Pre-fill and send a question about a UI element (§34.12).

        Called from the right-click "Ask AI about this" context menu.
        Pre-fills the chat input so the user can see the question, then
        sends it through the normal utterance pipeline.
        """
        self._chat_input.set_text(question)
        self._on_send_clicked(question)

    def set_controller(self, controller: CoPilotController) -> None:
        """Set or replace the controller after construction."""
        self._controller = controller

    def set_enterprise_voice(self, enabled: bool) -> None:
        """Show/hide the voice-mode selector (Enterprise tier gate)."""
        self._enterprise_voice = enabled
        if self._voice_mode_combo is not None:
            self._voice_mode_combo.setVisible(enabled)
        if self._wake_word_notice is not None:
            self._wake_word_notice.setVisible(False)

    def shutdown(self) -> None:
        """Clean up i18n listener and recorder."""
        try:
            unregister_listener(self._i18n_callback)
        except Exception:
            pass
        self._recorder.stop_recording()

    # -- Mic / Push-to-Talk ------------------------------------------------

    def _on_mic_pressed(self) -> None:
        """Begin recording when the mic button is pressed."""
        logger.debug("Mic pressed -- starting recording")
        self._chat_input.set_mic_state("listening")
        self._recorder.start_recording()

    def _on_mic_released(self) -> None:
        """Stop recording when the mic button is released."""
        logger.debug("Mic released -- stopping recording")
        self._chat_input.set_mic_state("processing")
        self._recorder.stop_recording()

    def _on_audio_ready(self, audio_bytes: bytes) -> None:
        """Send captured audio to the controller for transcription."""
        logger.info(
            "Audio captured (%d bytes) -- sending to controller", len(audio_bytes)
        )
        language = get_language()
        self._process_voice(audio_bytes, language)
        self._chat_input.set_mic_state("idle")

    def _process_voice(self, audio_bytes: bytes, language: str) -> None:
        """Transcribe and submit voice audio in a background thread."""
        if self._controller is None:
            logger.warning("CoPilotPanel: no controller, cannot process voice")
            return

        def _run_async():
            """Run the async voice pipeline in a thread with its own event loop."""
            try:
                response = asyncio.run(
                    self._controller.send_voice(audio_bytes, language=language)
                )
                # Schedule UI update back on the main thread
                QTimer.singleShot(
                    0,
                    lambda: self._handle_response(
                        {
                            "summary_key": response.summary_key,
                            "summary_params": response.summary_params,
                            "clarification_question_key": response.clarification_question_key,
                            "clarification_params": response.clarification_params,
                            "status": "ok",
                        }
                    ),
                )
            except Exception as exc:
                logger.exception("Voice processing failed")
                error_msg = str(exc)
                QTimer.singleShot(0, lambda: self._handle_error(error_msg))

        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()

    def _on_recorder_error(self, message: str) -> None:
        """Handle audio-recorder errors gracefully."""
        logger.error("AudioRecorder error: %s", message)
        self._chat_input.set_mic_state("idle")
        self._conversation.add_message(
            t(
                "copilot.voice.recording_error",
                default="Microphone error: {error}",
                error=message,
            ),
            is_user=False,
        )

    # -- Text send ---------------------------------------------------------

    def _on_send_clicked(self, text: str) -> None:
        """Handle user sending a message."""
        # Display user bubble immediately
        self._conversation.add_message(text, is_user=True)
        self._chat_input.set_processing(True)
        self._conversation.show_thinking()

        # Kick off async request
        self._process_utterance(text)

    def _process_utterance(self, text: str) -> None:
        """Send utterance to controller and handle the response."""
        if self._controller is None:
            logger.warning("CoPilotPanel: no controller, cannot process utterance")
            self._handle_error(t("copilot.chat.no_controller", default="Co-Pilot is not available"))
            return

        language = get_language()

        def _run_async():
            """Run the async send in a background thread with its own event loop."""
            try:
                response = asyncio.run(
                    self._controller.send_utterance(text, language=language)
                )
                # Convert CoPilotResponse dataclass to dict for _handle_response
                response_dict = {
                    "summary_key": response.summary_key,
                    "summary_params": response.summary_params,
                    "clarification_question_key": response.clarification_question_key,
                    "clarification_params": response.clarification_params,
                    "timeline": response.timeline,
                    "conversation_id": response.conversation_id,
                }
                # Schedule UI update back on the main thread
                QTimer.singleShot(0, lambda: self._handle_response(response_dict))
            except Exception as exc:
                logger.exception("Co-Pilot request failed")
                error_msg = str(exc)
                QTimer.singleShot(0, lambda: self._handle_error(error_msg))

        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()

    def _handle_response(self, response_dict: dict) -> None:
        """Display the Co-Pilot response."""
        self._conversation.hide_thinking()
        self._chat_input.set_processing(False)

        # Build display text from response
        display_text = self._format_response(response_dict)
        self._conversation.add_message(display_text, is_user=False)

    def _handle_error(self, error_message: str) -> None:
        """Display an error message.

        Uses the *error_message* as a translation key — if a translation
        exists (e.g. ``copilot.error.stt_unavailable``) it is shown;
        otherwise falls back to the generic ``copilot.chat.error`` key,
        and finally to the raw message string.
        """
        self._conversation.hide_thinking()
        self._chat_input.set_processing(False)

        error_text = t(
            error_message,
            default=t("copilot.chat.error", default=str(error_message)),
        )
        self._conversation.add_message(error_text, is_user=False)

    def _format_response(self, response_dict: dict) -> str:
        """Format a CoPilotResponse dict into a display string.

        Uses summary_key -> t() if present, then clarification_question_key.
        Falls back to raw dict representation.
        """
        parts: list[str] = []

        # Summary text
        summary_key = response_dict.get("summary_key")
        if summary_key:
            summary_params = response_dict.get("summary_params", {})
            summary_text = t(summary_key, **summary_params)
            parts.append(summary_text)

        # Clarification question
        clarification_key = response_dict.get("clarification_question_key")
        if clarification_key:
            clarification_params = response_dict.get("clarification_params", {})
            clarification_text = t(clarification_key, **clarification_params)
            parts.append(clarification_text)

        if parts:
            return "\n\n".join(parts)

        # Fallback: if backend returned a "message" key, use it
        message = response_dict.get("message")
        if message:
            return str(message)

        # Last resort: show status
        status = response_dict.get("status", "ok")
        return t(f"copilot.step_status.{status}", default=status)

    # -- Voice mode selector -----------------------------------------------

    def _on_voice_mode_changed(self, mode: str) -> None:
        """Handle voice-mode combo-box changes (Enterprise only)."""
        if self._wake_word_notice is None:
            return

        is_wake_word = "Wake Word" in mode or "activare vocala" in mode.lower()
        self._wake_word_notice.setVisible(is_wake_word)

        if is_wake_word:
            logger.info("Wake Word selected -- showing Phase 3 notice, reverting in 3 s")
            QTimer.singleShot(3000, self._reset_voice_mode)

    def _reset_voice_mode(self) -> None:
        """Switch the combo box back to 'Push to Talk' after the wake-word notice."""
        if self._voice_mode_combo is not None:
            ptt_label = t("copilot.voice.mode_ptt", default="Push to Talk")
            idx = self._voice_mode_combo.findText(ptt_label)
            if idx >= 0:
                self._voice_mode_combo.blockSignals(True)
                self._voice_mode_combo.setCurrentIndex(idx)
                self._voice_mode_combo.blockSignals(False)
        if self._wake_word_notice is not None:
            self._wake_word_notice.setVisible(False)

    def _on_new_conversation(self) -> None:
        """Clear the conversation and reset state."""
        self._conversation.clear()
        self._chat_input.set_processing(False)
        self._chat_input.set_mic_state("idle")
        if self._controller is not None:
            self._controller.conversation_id = None

    def _on_language_changed(self, lang: str) -> None:
        """Refresh UI labels when the language changes."""
        try:
            self._title_label.setText(t("copilot.panel.title", default="AI Co-Pilot"))
            # Sub-widgets will pick up language changes via their own listeners
        except Exception:
            logger.exception("CoPilotPanel language refresh failed")
