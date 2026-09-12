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
    - Voice mode selector (Enterprise tier) — Push-to-Talk or continuous
      wake-word listening (§3.5, §16), with TTS response output opt-in
    - i18n language changes via register_listener
"""

from __future__ import annotations

import array
import asyncio
import dataclasses
import logging
import threading
import time
from typing import Callable, Optional

import shiboken6

from PySide6.QtCore import QTimer, Signal
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
    COLOR_TEXT_WHITE,
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

# ── Voice state machine (§16) ──────────────────────────────────────────────
# The voice flow is a 4-state machine shared by push-to-talk and wake-word:
#   Idle -> Listening -> Processing -> Responding -> Idle
VOICE_IDLE = "idle"
VOICE_LISTENING = "listening"
VOICE_PROCESSING = "processing"
VOICE_RESPONDING = "responding"

# Wake-word / utterance-capture timings (ms unless noted).
_UTTERANCE_MAX_MS = 7000        # hard cap after a wake-word trigger
_SILENCE_MS = 900               # trailing silence this long ends the utterance
_MIN_SOUND_MS = 350             # require some speech before silence can end it
_SILENCE_ENERGY = 350.0         # RMS amplitude below this counts as silence
_RESPONDING_COOLDOWN_MS = 2000  # re-arm the wake word after a response (TTS)
_WAKE_WORD_STATUS_MS = 3000     # how long the "listening" status banner shows


def _pcm_rms(data: bytes) -> float:
    """Return the RMS amplitude of 16-bit mono PCM *data* (silence ≈ 0)."""
    if not data:
        return 0.0
    n_samples = len(data) // 2
    if n_samples == 0:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data[: n_samples * 2])
    if not samples:
        return 0.0
    energy = sum(s * s for s in samples)
    return (energy / len(samples)) ** 0.5


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

    # ── Signals ──────────────────────────────────────────────────────
    # Worker threads emit these instead of touching widgets directly; Qt
    # auto-queues the emission to the receiver's (main) thread, so the
    # slots always run on the GUI thread.
    response_ready = Signal(dict)   # backend response dict → _handle_response
    request_failed = Signal(str)    # error message → _handle_error
    insights_toggled = Signal(bool)  # True → show insight queue, False → hide

    def _schedule_after(self, ms: int, fn: Callable[[], None]) -> None:
        """Run *fn* after *ms* ms, no-op if this widget was destroyed first.

        ``QTimer.singleShot`` callbacks that capture ``self`` fire even after
        the underlying C++ object was deleted (panel torn down while a wake
        word / cooldown timer is still pending), which raises "Signal source
        has been deleted" from inside the Qt event loop and poisons later
        tests.  Checking ``shiboken6.isValid`` drops the callback once the
        object is gone.
        """
        target = self

        def _run() -> None:
            if not shiboken6.isValid(target):
                return
            fn()

        QTimer.singleShot(ms, _run)

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

        # Cross-thread results are delivered via queued Qt signals so worker
        # threads never touch widgets directly.
        self.response_ready.connect(self._handle_response)
        self.request_failed.connect(self._handle_error)

        self._voice_mode_combo: Optional[QComboBox] = None
        self._wake_word_notice: Optional[QLabel] = None

        # Wake-word / voice state machine (§16): Idle→Listening→Processing→Responding
        self._wake_word_enabled: bool = False
        self._voice_state: str = VOICE_IDLE
        self._capturing: bool = False
        self._utterance_started_at: float = 0.0
        self._last_sound_at: Optional[float] = None
        self._sound_ever: bool = False
        self._utterance_timer = QTimer(self)
        self._utterance_timer.setSingleShot(True)
        self._utterance_timer.timeout.connect(self._finish_utterance)

        self._i18n_callback = self._on_language_changed
        register_listener(self._i18n_callback)

        self._build_ui()
        self._connect_voice()

        # Voice mode is an opt-in per session: a voice mode selected in the
        # combo box (Enterprise tier) activates TTS response output.
        if self._voice_mode_combo is not None:
            self._set_voice_mode_active(True)

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

        # Insights toggle button
        self._insights_btn = QPushButton(
            t("copilot.insights.toggle", default="Insights")
        )
        self._insights_btn.setCheckable(True)
        self._insights_btn.setChecked(False)
        self._insights_btn.setStyleSheet(
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
            QPushButton:checked {{
                background-color: {COLOR_ACCENT_PRIMARY};
                color: {COLOR_TEXT_WHITE};
                border: 1px solid {COLOR_ACCENT_PRIMARY};
            }}
            QPushButton:checked:hover {{
                background-color: {COLOR_ACCENT_HOVER};
                border: 1px solid {COLOR_ACCENT_HOVER};
            }}
            """
        )
        self._insights_btn.clicked.connect(self._on_insights_toggled)
        header_layout.addWidget(self._insights_btn)

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
        self._recorder.chunk_ready.connect(self._on_chunk_ready)
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
        # Re-propagate the current voice-mode opt-in state.
        if self._voice_mode_combo is not None:
            self._set_voice_mode_active(True)
        if self._wake_word_enabled:
            try:
                if hasattr(controller, "set_wake_word_enabled"):
                    controller.set_wake_word_enabled(True)
            except Exception:
                logger.exception("Failed to propagate wake-word state to controller")

    def set_enterprise_voice(self, enabled: bool) -> None:
        """Show/hide the voice-mode selector (Enterprise tier gate)."""
        self._enterprise_voice = enabled
        if self._voice_mode_combo is not None:
            self._voice_mode_combo.setVisible(enabled)
        if self._wake_word_notice is not None:
            self._wake_word_notice.setVisible(False)
        if not enabled:
            self._disable_wake_word()
        # TTS response output follows the voice-mode opt-in state.
        self._set_voice_mode_active(
            bool(enabled and self._voice_mode_combo is not None)
        )

    def shutdown(self) -> None:
        """Clean up i18n listener, wake-word monitoring, and recorder."""
        try:
            unregister_listener(self._i18n_callback)
        except Exception:
            pass
        self._wake_word_enabled = False
        self._utterance_timer.stop()
        self._recorder.stop_recording()

    # -- Mic / Push-to-Talk ------------------------------------------------

    def _on_mic_pressed(self) -> None:
        """Begin recording when the mic button is pressed."""
        logger.debug("Mic pressed -- starting recording")
        self._voice_state = VOICE_LISTENING
        self._chat_input.set_mic_state("listening")
        self._recorder.start_recording()

    def _on_mic_released(self) -> None:
        """Stop recording when the mic button is released."""
        logger.debug("Mic released -- stopping recording")
        self._voice_state = VOICE_PROCESSING
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
                # Forward the backend plan as a plain dict, mirroring the chat
                # path so downstream consumers (controller plan tracking) see it.
                plan = response.plan
                # Emit on the Qt signal — auto-queued to the main thread
                self.response_ready.emit(
                    {
                        "summary_key": response.summary_key,
                        "summary_params": response.summary_params,
                        "clarification_question_key": response.clarification_question_key,
                        "clarification_params": response.clarification_params,
                        "status": "ok",
                        "plan": dataclasses.asdict(plan) if dataclasses.is_dataclass(plan) else None,
                    }
                )
            except Exception as exc:
                logger.exception("Voice processing failed")
                error_msg = str(exc)
                self.request_failed.emit(error_msg)

        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()

    def _on_recorder_error(self, message: str) -> None:
        """Handle audio-recorder errors gracefully."""
        logger.error("AudioRecorder error: %s", message)
        self._chat_input.set_mic_state("idle")
        if self._wake_word_enabled:
            # Mic unavailable during wake-word monitoring — fall back to PTT
            # silently (logged) instead of spamming error bubbles.
            self._revert_to_ptt()
            return
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
            self._handle_error(
                t(
                    "copilot.chat.no_controller",
                    default="Co-Pilot is not available in this connection mode. "
                    "Connect to a server or restart with a local database.",
                )
            )
            return

        language = get_language()

        def _run_async():
            """Run the async send in a background thread with its own event loop."""
            try:
                response = asyncio.run(
                    self._controller.send_utterance(text, language=language)
                )
                # Convert CoPilotResponse dataclass to dict for _handle_response.
                # ``plan`` is forwarded as a plain dict so downstream consumers
                # (controller plan tracking) see the backend plan; it stays
                # in-process, so no serialization round-trip is involved.
                plan = response.plan
                response_dict = {
                    "summary_key": response.summary_key,
                    "summary_params": response.summary_params,
                    "clarification_question_key": response.clarification_question_key,
                    "clarification_params": response.clarification_params,
                    "timeline": response.timeline,
                    "conversation_id": response.conversation_id,
                    "plan": dataclasses.asdict(plan) if dataclasses.is_dataclass(plan) else None,
                }
                # Emit on the Qt signal — auto-queued to the main thread
                self.response_ready.emit(response_dict)
            except Exception as exc:
                logger.exception("Co-Pilot request failed")
                error_msg = str(exc)
                self.request_failed.emit(error_msg)

        thread = threading.Thread(target=_run_async, daemon=True)
        thread.start()

    def _handle_response(self, response_dict: dict) -> None:
        """Display the Co-Pilot response."""
        self._conversation.hide_thinking()
        self._chat_input.set_processing(False)

        # Build display text from response
        display_text = self._format_response(response_dict)
        self._conversation.add_message(display_text, is_user=False)

        self._finish_voice_turn()

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

        self._finish_voice_turn()

    def _format_response(self, response_dict: dict) -> str:
        """Format a CoPilotResponse dict into a display string.

        Uses summary_key -> t() if present (falling back to the executed
        timeline when the key has no translation — local mode), then the
        clarification question, then ``message``, then the timeline, then a
        status fallback.
        """
        parts: list[str] = []

        # Summary text
        summary_key = response_dict.get("summary_key")
        if summary_key:
            if summary_key == "copilot.summary.llm_chat":
                # Verbatim passthrough — the LLM answer may contain {, } or
                # newlines that str.format() would mangle or crash on, so it
                # must never go through t()/format().
                answer = (response_dict.get("summary_params") or {}).get("answer")
                if isinstance(answer, str) and answer.strip():
                    parts.append(answer)
            else:
                summary_params = response_dict.get("summary_params", {})
                summary_text = t(summary_key, **summary_params)
                timeline = response_dict.get("timeline") or []
                timeline_text = self._render_timeline(timeline)
                if summary_text and summary_text != summary_key:
                    parts.append(summary_text)
                elif timeline_text:
                    # Untranslated summary key — render the executed steps instead
                    # of showing a raw i18n key (common for local in-process runs).
                    parts.append(timeline_text)
                else:
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

        # Fallback: render the executed timeline when available
        timeline = response_dict.get("timeline") or []
        timeline_text = self._render_timeline(timeline)
        if timeline_text:
            return timeline_text

        # Last resort: show status
        status = response_dict.get("status", "ok")
        return t(f"copilot.step_status.{status}", default=status)

    @staticmethod
    def _render_timeline(timeline) -> str:
        """Render executed execution steps as readable text.

        Handles both ``ExecutionStep`` dataclasses (local/parsed responses)
        and plain dicts (API responses).  Returns ``""`` when nothing
        renderable is found.
        """
        if not timeline:
            return ""
        lines: list[str] = []
        for step in timeline:
            if isinstance(step, dict):
                tool_name = step.get("tool_name") or ""
                status = step.get("status") or "succeeded"
                error = step.get("error")
                result = step.get("result")
            else:
                tool_name = getattr(step, "tool_name", "") or ""
                status = getattr(step, "status", "") or "succeeded"
                error = getattr(step, "error", None)
                result = getattr(step, "result", None)
            if not tool_name:
                continue
            human = tool_name.replace(".", " ").replace("_", " ").title()
            status_text = t(f"copilot.step_status.{status}", default=status.capitalize())
            line = f"{human}: {status_text}"
            if status in ("failed", "skipped") and error:
                line += f" — {error}"
            elif isinstance(result, dict):
                detail_parts: list[str] = []
                msg_key = result.get("message_key")
                if msg_key:
                    msg_params = result.get("message_params") or {}
                    msg_text = t(msg_key, **msg_params)
                    if msg_text and msg_text != msg_key:
                        detail_parts.append(msg_text)
                data = result.get("data")
                if isinstance(data, dict):
                    answer = data.get("answer")
                    if isinstance(answer, dict):
                        a_key = answer.get("answer_key")
                        if a_key:
                            a_text = t(a_key, **answer.get("answer_params", {}))
                            if a_text and a_text != a_key:
                                detail_parts.append(a_text)
                    else:
                        summary = ", ".join(
                            f"{k}: {v}"
                            for k, v in list(data.items())[:6]
                            if not isinstance(v, (list, dict))
                        )
                        if summary:
                            detail_parts.append(summary)
                if detail_parts:
                    line += " — " + " ".join(detail_parts)
            lines.append(line)
        return "\n".join(lines)

    # -- Voice mode selector -----------------------------------------------

    def _on_voice_mode_changed(self, mode: str) -> None:
        """Handle voice-mode combo-box changes (Enterprise only).

        Push to Talk → PTT capture.  Wake Word → continuous wake-word
        listening (§3.5): the mic streams PCM, the wake-word engine is
        consulted per chunk, and a trigger activates the voice turn exactly
        like a PTT press.
        """
        if self._wake_word_notice is None:
            return

        is_wake_word = "Wake Word" in mode or "activare vocala" in mode.lower()

        # Selecting any voice mode opts the session into TTS response output.
        self._set_voice_mode_active(True)

        if is_wake_word:
            self._enable_wake_word()
        else:
            self._disable_wake_word()

    # -- Wake-word monitoring (§3.5, §16) -----------------------------------

    def _enable_wake_word(self) -> None:
        """Turn on continuous wake-word monitoring (Enterprise)."""
        self._wake_word_enabled = True
        if self._controller is not None and hasattr(self._controller, "set_wake_word_enabled"):
            try:
                self._controller.set_wake_word_enabled(True)
            except Exception:
                logger.exception("Failed to propagate wake-word state to controller")

        # A stale Responding state (e.g. from an earlier PTT turn) must not
        # block fresh monitoring.
        if self._voice_state == VOICE_RESPONDING:
            self._voice_state = VOICE_IDLE

        if not self._wake_word_available():
            logger.info("Wake-word engine unavailable — falling back to push-to-talk")
            self._revert_to_ptt()
            return
        if self._start_wake_word_listening():
            self._show_wake_word_status()

    def _disable_wake_word(self) -> None:
        """Turn off wake-word monitoring (back to push-to-talk)."""
        self._wake_word_enabled = False
        if self._controller is not None and hasattr(self._controller, "set_wake_word_enabled"):
            try:
                self._controller.set_wake_word_enabled(False)
            except Exception:
                logger.exception("Failed to propagate wake-word state to controller")
        self._stop_wake_word_listening()

    def _start_wake_word_listening(self) -> bool:
        """Begin continuous mic monitoring for the wake word (non-blocking).

        Returns ``True`` when monitoring is active, ``False`` when the mic
        could not be opened (an ``_on_recorder_error`` revert already ran).
        """
        if not self._wake_word_enabled:
            return False
        if self._voice_state != VOICE_IDLE:
            return False  # a turn is in flight — never overlap capture/TTS
        self._capturing = False
        self._recorder.clear_buffer()
        self._recorder.start_recording()  # idempotent; streams chunk_ready
        if not self._wake_word_enabled:
            # Mic unavailable — _on_recorder_error already reverted to PTT.
            return False
        if self._wake_word_notice is not None:
            self._wake_word_notice.setVisible(False)
        logger.info("Wake-word monitoring active")
        return True

    def _stop_wake_word_listening(self) -> None:
        """Stop wake-word mic monitoring and any pending utterance timer."""
        self._utterance_timer.stop()
        self._capturing = False
        if self._voice_state in (VOICE_IDLE, VOICE_RESPONDING):
            # Mid-utterance (Listening/Processing) is owned by the turn and
            # is stopped by the normal audio_ready flow.
            self._recorder.stop_recording()
        if self._wake_word_notice is not None:
            self._wake_word_notice.setVisible(False)

    def _wake_word_available(self) -> bool:
        if self._controller is None:
            return False
        try:
            if hasattr(self._controller, "wake_word_available"):
                return bool(self._controller.wake_word_available)
        except Exception:
            logger.exception("Wake-word availability check failed")
        return False

    def _revert_to_ptt(self) -> None:
        """Graceful fallback: stop monitoring and select Push to Talk."""
        self._wake_word_enabled = False
        if self._controller is not None and hasattr(self._controller, "set_wake_word_enabled"):
            try:
                self._controller.set_wake_word_enabled(False)
            except Exception:
                pass
        self._stop_wake_word_listening()
        if self._voice_mode_combo is not None:
            ptt_label = t("copilot.voice.mode_ptt", default="Push to Talk")
            idx = self._voice_mode_combo.findText(ptt_label)
            if idx >= 0:
                self._voice_mode_combo.blockSignals(True)
                self._voice_mode_combo.setCurrentIndex(idx)
                self._voice_mode_combo.blockSignals(False)
        if self._wake_word_notice is not None:
            self._wake_word_notice.setText(
                t(
                    "copilot.voice.wake_word_unavailable",
                    default="Wake word engine unavailable — switched back to Push to Talk.",
                )
            )
            self._wake_word_notice.setVisible(True)
            self._schedule_after(_WAKE_WORD_STATUS_MS, self._hide_wake_word_status)
        # PTT is still a voice mode — TTS output stays active.
        self._set_voice_mode_active(True)

    def _show_wake_word_status(self) -> None:
        """Show a short "listening for wake word" status banner."""
        if self._wake_word_notice is None:
            return
        self._wake_word_notice.setText(
            t(
                "copilot.voice.wake_word_listening",
                default="Listening for wake word…",
            )
        )
        self._wake_word_notice.setVisible(True)
        self._schedule_after(_WAKE_WORD_STATUS_MS, self._hide_wake_word_status)

    def _hide_wake_word_status(self) -> None:
        if self._wake_word_notice is not None:
            self._wake_word_notice.setVisible(False)

    # -- Streaming audio plumbing --------------------------------------------

    def _on_chunk_ready(self, chunk: bytes) -> None:
        """Stream each PCM chunk — wake-word detection or utterance capture."""
        if self._capturing:
            # Post-trigger utterance capture — VAD + auto-stop.
            self._track_utterance_audio(chunk)
            return
        if self._voice_state == VOICE_LISTENING:
            # Push-to-talk: the buffer accumulates for stop_recording.
            return
        if self._wake_word_enabled and self._voice_state == VOICE_IDLE:
            if self._feed_wake_word(chunk):
                self._on_wake_word_triggered()
                return
        # Monitoring (or a stale state) — keep the buffer from growing.
        self._recorder.clear_buffer()

    def _feed_wake_word(self, chunk: bytes) -> bool:
        """Feed one PCM chunk to the controller's wake-word engine."""
        if self._controller is None:
            return False
        try:
            if hasattr(self._controller, "process_wake_word_audio"):
                return bool(self._controller.process_wake_word_audio(chunk))
        except Exception:
            logger.exception("Wake-word feed failed")
        return False

    def _on_wake_word_triggered(self) -> None:
        """Wake word heard — start capturing the utterance (like a PTT press)."""
        if self._voice_state != VOICE_IDLE:
            return
        logger.info("Wake word detected — listening")
        if self._controller is not None and hasattr(self._controller, "reset_wake_word"):
            try:
                self._controller.reset_wake_word()
            except Exception:
                pass
        self._voice_state = VOICE_LISTENING
        self._capturing = True
        self._recorder.clear_buffer()
        self._chat_input.set_mic_state("listening")
        self._utterance_started_at = time.monotonic()
        self._last_sound_at = None
        self._sound_ever = False
        self._utterance_timer.start(_UTTERANCE_MAX_MS)

    def _track_utterance_audio(self, chunk: bytes) -> None:
        """Simple energy-based end-of-speech detection on captured PCM."""
        now = time.monotonic()
        if _pcm_rms(chunk) >= _SILENCE_ENERGY:
            self._last_sound_at = now
            self._sound_ever = True
            return
        if not self._sound_ever or self._last_sound_at is None:
            return
        silent_for = now - self._last_sound_at
        elapsed = now - self._utterance_started_at
        if silent_for >= (_SILENCE_MS / 1000.0) and elapsed >= (_MIN_SOUND_MS / 1000.0):
            self._finish_utterance()

    def _finish_utterance(self) -> None:
        """End utterance capture and submit it (like a PTT release)."""
        if self._voice_state != VOICE_LISTENING or not self._capturing:
            return
        self._utterance_timer.stop()
        self._capturing = False
        self._voice_state = VOICE_PROCESSING
        self._chat_input.set_mic_state("processing")
        self._recorder.stop_recording()  # → audio_ready → _process_voice

    def _finish_voice_turn(self) -> None:
        """Voice turn complete — enter Responding, then re-arm the wake word.

        The Responding state intentionally keeps the wake word disarmed while
        TTS playback (or the displayed answer) is still happening, so a new
        trigger can never overlap the assistant's response.
        """
        self._voice_state = VOICE_RESPONDING
        self._chat_input.set_mic_state("idle")
        if self._wake_word_enabled:
            self._schedule_after(_RESPONDING_COOLDOWN_MS, self._maybe_restart_wake_word)

    def _maybe_restart_wake_word(self) -> None:
        """Re-arm the wake word once the response (TTS) has finished."""
        if not self._wake_word_enabled:
            return
        if self._voice_state != VOICE_RESPONDING:
            return
        if self._controller_is_speaking():
            # TTS still playing — poll again shortly.
            self._schedule_after(1000, self._maybe_restart_wake_word)
            return
        self._voice_state = VOICE_IDLE
        self._start_wake_word_listening()

    def _controller_is_speaking(self) -> bool:
        """Whether the controller is currently playing TTS audio."""
        if self._controller is None:
            return False
        try:
            if hasattr(self._controller, "tts_playing"):
                return bool(self._controller.tts_playing)
        except Exception:
            return False
        return False

    def _set_voice_mode_active(self, active: bool) -> None:
        """Propagate the voice-mode opt-in state to the controller (TTS output).

        Failures are logged and swallowed — the chat flow must never break
        because of voice-mode state plumbing.
        """
        if self._controller is None:
            return
        try:
            if hasattr(self._controller, "set_voice_mode_active"):
                self._controller.set_voice_mode_active(active)
        except Exception:
            logger.exception("Failed to propagate voice-mode state to controller")

    def _on_insights_toggled(self, checked: bool) -> None:
        """Emit the insights_toggled signal when the user clicks the toggle."""
        self.insights_toggled.emit(checked)

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
            if self._insights_btn is not None:
                self._insights_btn.setText(
                    t("copilot.insights.toggle", default="Insights")
                )
            # Sub-widgets will pick up language changes via their own listeners
        except Exception:
            logger.exception("CoPilotPanel language refresh failed")
