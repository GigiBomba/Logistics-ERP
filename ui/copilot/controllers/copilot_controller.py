"""CoPilotController — bridges UI widgets to backend /api/v1/copilot/* endpoints.

Full implementation with Qt signal/slot pattern for thread-safe UI updates,
dependency injection, WebSocket management with exponential backoff reconnect,
and local STT transcription via Whisper (conditional import).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, QUrl
from PySide6.QtWebSockets import QWebSocket

from client.remote_copilot import RemoteCopilotService
from services.i18n import get_language, t
from ui.copilot.models import (
    CoPilotResponse,
    ExecutionPlan,
    ExecutionStep,
    Insight,
    ConfirmationLevel,
    Intent,
    Entity,
)

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────

async def _await_if_needed(result: Any) -> Any:
    """Await *result* when it is a coroutine, otherwise return it unchanged.

    ``RemoteCopilotService`` methods are synchronous; the local in-process
    service (:class:`client.local_copilot.LocalCopilotService`) exposes the
    same surface with async methods.  The controller stays mode-agnostic by
    awaiting transparently.
    """
    if asyncio.iscoroutine(result):
        return await result
    return result


def _parse_step(raw: dict) -> ExecutionStep:
    """Deserialize a raw step dict into an ExecutionStep dataclass."""
    started = raw.get("started_at")
    finished = raw.get("finished_at")
    return ExecutionStep(
        step_id=raw.get("step_id", ""),
        tool_name=raw.get("tool_name", ""),
        tool_version=raw.get("tool_version", ""),
        parameters=raw.get("parameters", {}),
        depends_on=raw.get("depends_on", []),
        confirmation_level=ConfirmationLevel(raw["confirmation_level"]) if raw.get("confirmation_level") is not None else ConfirmationLevel.SAFE,
        status=raw.get("status", "pending"),
        result=raw.get("result"),
        error=raw.get("error"),
        started_at=datetime.fromisoformat(started) if isinstance(started, str) else started,
        finished_at=datetime.fromisoformat(finished) if isinstance(finished, str) else finished,
    )


def _parse_plan(raw: dict) -> ExecutionPlan:
    """Deserialize a raw plan dict into an ExecutionPlan dataclass."""
    intent_raw = raw.get("intent", {})
    intent = Intent(
        name=intent_raw.get("name", ""),
        entities=[Entity(**e) for e in intent_raw.get("entities", [])],
        missing_required_entities=intent_raw.get("missing_required_entities", []),
        raw_utterance=intent_raw.get("raw_utterance", ""),
    )
    steps = [_parse_step(s) for s in raw.get("steps", [])]
    created = raw.get("created_at")
    return ExecutionPlan(
        plan_id=raw.get("plan_id", ""),
        conversation_id=raw.get("conversation_id", ""),
        reasoning_graph_id=raw.get("reasoning_graph_id", ""),
        intent=intent,
        steps=steps,
        overall_confidence=raw.get("overall_confidence", 0.0),
        requires_confirmation=raw.get("requires_confirmation", False),
        created_at=datetime.fromisoformat(created) if isinstance(created, str) else created,
    )


def _parse_response(raw: dict) -> CoPilotResponse:
    """Deserialize a raw chat/voice response dict into a CoPilotResponse."""
    plan_raw = raw.get("plan")
    plan = _parse_plan(plan_raw) if plan_raw and isinstance(plan_raw, dict) else None
    timeline = [_parse_step(s) for s in raw.get("timeline", [])]
    return CoPilotResponse(
        conversation_id=raw.get("conversation_id", ""),
        reasoning_graph=raw.get("reasoning_graph"),
        plan=plan,
        clarification_question_key=raw.get("clarification_question_key"),
        clarification_params=raw.get("clarification_params", {}),
        timeline=timeline,
        summary_key=raw.get("summary_key"),
        summary_params=raw.get("summary_params", {}),
    )


def _parse_insight(raw: dict) -> Insight:
    """Deserialize a raw insight dict into an Insight dataclass."""
    return Insight(
        id=raw.get("id", raw.get("insight_id", "")),
        conversation_id=raw.get("conversation_id", ""),
        insight_type=raw.get("insight_type", ""),
        payload=raw.get("payload", {}),
        severity=raw.get("severity", ""),
        status=raw.get("status", "new"),
        created_at=raw.get("created_at"),
    )


# ── Controller ──────────────────────────────────────────────────────────

class CoPilotController(QObject):
    """Orchestrates Co-Pilot UI state and API communication.

    Responsibilities:
    - Send utterances to POST /api/v1/copilot/chat
    - Transcribe voice locally via Whisper (conditional), then call voice_input
    - Manage WebSocket connection for real-time timeline updates
    - Handle plan confirmation/cancellation/undo
    - Manage conversation context lifecycle
    - List/dismiss proactive insights
    """

    # ── Signals ──────────────────────────────────────────────────────
    new_turn = Signal(dict)                # emitted after send_utterance / send_voice
    step_update = Signal(dict)             # emitted when WS step_update arrives
    plan_changed = Signal(str)             # plan_id — after confirm/cancel/undo
    timeline_updated = Signal(list)        # list[dict] — full timeline after a turn
    conversation_loaded = Signal(dict)     # full conversation detail
    error_occurred = Signal(str)           # user-facing error message key
    ws_connected = Signal()                # WebSocket connected
    ws_disconnected = Signal()             # WebSocket disconnected
    tts_audio_ready = Signal(object)       # synthesized TTS bytes → GUI-thread playback

    def __init__(
        self,
        remote: Optional[RemoteCopilotService] = None,
        event_bus: Any = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the controller.

        Args:
            remote: Service implementing the ``RemoteCopilotService`` surface
                (``chat``, ``voice_input``, plan/conversation/insight methods).
                In LOCAL mode this is a :class:`client.local_copilot.LocalCopilotService`
                which executes the pipeline in-process; in REMOTE mode it is the
                HTTP-backed ``RemoteCopilotService``.  May be ``None`` when no
                backend or database is available — every call then surfaces a
                clear user-facing error instead of crashing.
            event_bus: Optional ``EventBus`` singleton for publishing copilot events.
            parent: Optional ``QObject`` parent.
        """
        super().__init__(parent)
        self._remote = remote
        self._event_bus = event_bus

        # Conversation / plan tracking
        self._conversation_id: Optional[str] = None
        self._active_plan_id: Optional[str] = None

        # WebSocket state
        self._ws: Optional[QWebSocket] = None
        self._ws_conversation_id: Optional[str] = None
        self._ws_reconnect_attempt: int = 0
        self._ws_max_reconnect_attempts: int = 10
        self._ws_reconnect_delay: float = 1.0  # seconds, doubles each attempt
        self._ws_reconnect_task: Any = None
        self._ws_intentional_disconnect: bool = False

        # STT (lazy — loaded on first voice use)
        self._stt_provider: Any = None

        # TTS output (lazy — provider/player loaded on first voice-mode response)
        self._tts_provider: Any = None
        self._tts_player: Any = None
        self._voice_mode_active: bool = False
        self.tts_audio_ready.connect(self._on_tts_audio_ready)

        # Wake word (lazy — engine loaded on first Enterprise wake-word use)
        self._wake_word_provider: Any = None
        self._wake_word_enabled: bool = False

        # Dismissed insights (client-side tracking)
        self._dismissed_insights: set[str] = set()

        logger.info("CoPilotController initialised")

    # ── Properties ───────────────────────────────────────────────────

    @property
    def conversation_id(self) -> Optional[str]:
        return self._conversation_id

    @conversation_id.setter
    def conversation_id(self, value: Optional[str]) -> None:
        self._conversation_id = value

    @property
    def active_plan_id(self) -> Optional[str]:
        return self._active_plan_id

    @active_plan_id.setter
    def active_plan_id(self, value: Optional[str]) -> None:
        self._active_plan_id = value

    # ── Chat / Voice ─────────────────────────────────────────────────

    async def send_utterance(
        self,
        text: str,
        language: Optional[str] = None,
    ) -> CoPilotResponse:
        """Send a user utterance to the Co-Pilot backend.

        Args:
            text: The natural-language utterance.
            language: ISO language code (defaults to the active UI language).

        Returns:
            A parsed ``CoPilotResponse`` dataclass.

        Emits:
            ``new_turn`` with the raw response dict.
            ``timeline_updated`` with the deserialised timeline list.
            ``error_occurred`` on failure.
        """
        language = language or get_language()
        try:
            chat_kwargs: dict[str, Any] = {
                "utterance": text,
                "language": language,
            }
            if self._conversation_id is not None:
                chat_kwargs["conversation_id"] = self._conversation_id
            self._require_remote("chat")
            raw = await _await_if_needed(self._remote.chat(**chat_kwargs))
            response = _parse_response(raw)
            self._conversation_id = response.conversation_id
            if response.plan:
                self._active_plan_id = response.plan.plan_id
            # Emit signals for UI update
            self.new_turn.emit(raw)
            self.timeline_updated.emit([s.__dict__ for s in response.timeline])
            self._publish_event("copilot.turn.completed", {"conversation_id": self._conversation_id})
            self._schedule_speech(response, language)
            return response
        except Exception as exc:
            logger.exception("send_utterance failed")
            self.error_occurred.emit(self._describe_error(exc))
            raise

    async def send_voice(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
    ) -> CoPilotResponse:
        """Transcribe audio locally (Whisper) then submit to voice endpoint.

        Args:
            audio_data: Raw audio bytes (WAV, MP3, etc.).
            language: Optional language hint for the STT engine (defaults to
                the active UI language).

        Returns:
            A parsed ``CoPilotResponse`` dataclass.

        Emits:
            ``new_turn`` with the raw response dict.
            ``timeline_updated`` with the deserialised timeline list.
            ``error_occurred`` on failure (including if STT unavailable).
        """
        language = language or get_language()
        try:
            transcript, stt_error = self._transcribe_audio(audio_data, language)
            if stt_error:
                self.error_occurred.emit(stt_error)
                raise RuntimeError(stt_error)

            if not transcript:
                msg = "copilot.error.stt_no_speech"
                self.error_occurred.emit(msg)
                raise RuntimeError(msg)

            voice_kwargs: dict[str, Any] = {
                "utterance": transcript,
                "language": language,
            }
            if self._conversation_id is not None:
                voice_kwargs["conversation_id"] = self._conversation_id
            self._require_remote("voice_input")
            raw = await _await_if_needed(self._remote.voice_input(**voice_kwargs))
            response = _parse_response(raw)
            self._conversation_id = response.conversation_id
            if response.plan:
                self._active_plan_id = response.plan.plan_id
            self.new_turn.emit(raw)
            self.timeline_updated.emit([s.__dict__ for s in response.timeline])
            self._publish_event("copilot.voice.completed", {"conversation_id": self._conversation_id})
            self._schedule_speech(response, language)
            return response
        except Exception as exc:
            logger.exception("send_voice failed")
            self.error_occurred.emit(self._describe_error(exc))
            raise

    # ── Plans ────────────────────────────────────────────────────────

    async def confirm_plan(self, plan_id: str) -> dict:
        """Confirm a plan awaiting confirmation.

        Emits ``plan_changed`` with the plan_id on success,
        ``error_occurred`` on failure.
        """
        try:
            self._require_remote("confirm_plan")
            result = await _await_if_needed(self._remote.confirm_plan(plan_id))
            self._active_plan_id = None
            self.plan_changed.emit(plan_id)
            self._publish_event("copilot.plan.confirmed", {"plan_id": plan_id})
            return result
        except Exception as exc:
            logger.exception("confirm_plan failed: %s", plan_id)
            self.error_occurred.emit(self._describe_error(exc))
            raise

    async def cancel_plan(self, plan_id: str) -> dict:
        """Cancel an in-flight plan.

        Emits ``plan_changed`` with the plan_id on success,
        ``error_occurred`` on failure.
        """
        try:
            self._require_remote("cancel_plan")
            result = await _await_if_needed(self._remote.cancel_plan(plan_id))
            if self._active_plan_id == plan_id:
                self._active_plan_id = None
            self.plan_changed.emit(plan_id)
            self._publish_event("copilot.plan.cancelled", {"plan_id": plan_id})
            return result
        except Exception as exc:
            logger.exception("cancel_plan failed: %s", plan_id)
            self.error_occurred.emit(self._describe_error(exc))
            raise

    async def undo_step(self, plan_id: str) -> dict:
        """Undo the last reversible step of a plan.

        Emits ``plan_changed`` with the plan_id on success,
        ``error_occurred`` on failure.
        """
        try:
            self._require_remote("undo_plan")
            result = await _await_if_needed(self._remote.undo_plan(plan_id))
            self.plan_changed.emit(plan_id)
            self._publish_event("copilot.plan.undone", {"plan_id": plan_id})
            return result
        except Exception as exc:
            logger.exception("undo_step failed: %s", plan_id)
            self.error_occurred.emit(self._describe_error(exc))
            raise

    # ── Conversations ────────────────────────────────────────────────

    async def list_conversations(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> list[CoPilotResponse]:
        """List the user's conversations.

        Args:
            limit: Maximum number of items to return.
            cursor: Pagination cursor (conversation_id).

        Returns:
            A list of ``CoPilotResponse`` dataclass instances.

        Emits ``error_occurred`` on failure.
        """
        try:
            conv_kwargs: dict[str, Any] = {"limit": limit}
            if cursor is not None:
                conv_kwargs["cursor"] = cursor
            self._require_remote("list_conversations")
            items = await _await_if_needed(self._remote.list_conversations(**conv_kwargs))
            return [_parse_response(item) for item in items]
        except Exception as exc:
            logger.exception("list_conversations failed")
            self.error_occurred.emit(self._describe_error(exc))
            raise

    async def get_conversation(self, conversation_id: str) -> dict:
        """Get full details for a specific conversation.

        Emits ``conversation_loaded`` with the raw response on success,
        ``error_occurred`` on failure.
        """
        try:
            self._require_remote("get_conversation")
            result = await _await_if_needed(self._remote.get_conversation(conversation_id))
            self.conversation_loaded.emit(result)
            return result
        except Exception as exc:
            logger.exception("get_conversation failed: %s", conversation_id)
            self.error_occurred.emit(self._describe_error(exc))
            raise

    # ── Plan status ──────────────────────────────────────────────────

    async def get_plan(self, plan_id: str) -> dict:
        """Get the current status of an execution plan.

        Emits ``error_occurred`` on failure.
        """
        try:
            self._require_remote("get_plan")
            return await _await_if_needed(self._remote.get_plan(plan_id))
        except Exception as exc:
            logger.exception("get_plan failed: %s", plan_id)
            self.error_occurred.emit(self._describe_error(exc))
            raise

    # ── WebSocket ────────────────────────────────────────────────────

    async def _connect_ws(self, conversation_id: str) -> None:
        """Open a WebSocket connection for real-time timeline updates.

        Args:
            conversation_id: The conversation to subscribe to.

        If a connection is already open for a different conversation it
        is closed first.  Automatic reconnection with exponential backoff
        up to ``_ws_max_reconnect_attempts``.
        """
        self._ws_intentional_disconnect = False
        self._ws_conversation_id = conversation_id
        self._ws_reconnect_attempt = 0
        self._ws_reconnect_delay = 1.0

        # Close existing connection if any
        self._close_ws_internal()

        self._do_connect_ws()

    def _do_connect_ws(self) -> None:
        """Initiate (or re-initiate) the WebSocket connection."""
        if self._ws_conversation_id is None:
            return

        if self._remote is None:
            logger.warning("CoPilot WS: no remote service — skipping WebSocket connection")
            return

        url_str = self._remote.ws_url(self._ws_conversation_id)
        if not url_str:
            # Local mode / backends without a WS endpoint — no live updates.
            logger.info("CoPilot WS: remote provides no WebSocket URL — skipping")
            return

        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.disconnected.connect(self._on_ws_disconnected)

        self._ws.open(QUrl(url_str))

    def disconnect_ws(self) -> None:
        """Disconnect the WebSocket intentionally (no reconnect)."""
        self._ws_intentional_disconnect = True
        self._cancel_reconnect_task()
        self._close_ws_internal()
        self._ws_conversation_id = None
        self._ws_reconnect_attempt = 0
        logger.info("CoPilot WebSocket intentionally disconnected")

    def _close_ws_internal(self) -> None:
        """Close the underlying socket without affecting reconnect state."""
        if self._ws is not None:
            try:
                self._ws.textMessageReceived.disconnect()
                self._ws.connected.disconnect()
                self._ws.disconnected.disconnect()
            except (RuntimeError, TypeError):
                pass
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def _on_ws_connected(self) -> None:
        """Handle WebSocket connected event."""
        self._ws_reconnect_attempt = 0
        self._ws_reconnect_delay = 1.0
        self.ws_connected.emit()
        logger.info(
            "CoPilot WebSocket connected: conversation=%s",
            self._ws_conversation_id,
        )

    def _on_ws_disconnected(self) -> None:
        """Handle WebSocket disconnected event."""
        self.ws_disconnected.emit()
        logger.info(
            "CoPilot WebSocket disconnected: conversation=%s",
            self._ws_conversation_id,
        )

        if not self._ws_intentional_disconnect and self._ws_conversation_id is not None:
            self._schedule_reconnect()

    def _on_ws_message(self, message: str) -> None:
        """Handle an incoming WebSocket text message.

        Expected message format (JSON)::

            {"type": "step_update", "step_id": "...", "status": "...",
             "tool_name": "...", "timestamp": "..."}
            {"type": "connected", "conversation_id": "..."}
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("CoPilot WS: ignoring non-JSON message: %s", message[:120])
            return

        msg_type = data.get("type", "")
        if msg_type == "step_update":
            self.step_update.emit(data)
        elif msg_type == "connected":
            logger.info("CoPilot WS: connection confirmed for %s", data.get("conversation_id"))
        elif msg_type == "pong":
            pass  # keepalive, no action needed
        else:
            logger.debug("CoPilot WS: unhandled message type %s", msg_type)

    # ── Reconnect logic ──────────────────────────────────────────────

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if self._ws_reconnect_attempt >= self._ws_max_reconnect_attempts:
            logger.warning(
                "CoPilot WS: max reconnect attempts (%d) reached, giving up",
                self._ws_max_reconnect_attempts,
            )
            self.error_occurred.emit("copilot.error.ws_reconnect_failed")
            return

        self._ws_reconnect_attempt += 1
        delay = self._ws_reconnect_delay
        self._ws_reconnect_delay = min(self._ws_reconnect_delay * 2, 60.0)
        logger.info(
            "CoPilot WS: reconnecting in %.1fs (attempt %d/%d)",
            delay,
            self._ws_reconnect_attempt,
            self._ws_max_reconnect_attempts,
        )

        self._cancel_reconnect_task()
        reconnect_timer = QTimer(self)
        reconnect_timer.setSingleShot(True)
        reconnect_timer.timeout.connect(self._do_connect_ws)
        reconnect_timer.start(int(delay * 1000))
        self._ws_reconnect_task = reconnect_timer

    def _cancel_reconnect_task(self) -> None:
        """Cancel any pending reconnect timer."""
        if self._ws_reconnect_task is not None:
            try:
                self._ws_reconnect_task.stop()
                self._ws_reconnect_task.deleteLater()
            except Exception:
                pass
            self._ws_reconnect_task = None

    # ── Insights ─────────────────────────────────────────────────────

    async def list_insights(
        self,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> list[Insight]:
        """List proactive insights for the review queue.

        Args:
            limit: Maximum number of items to return.
            status_filter: Optional filter (e.g. ``"new"``, ``"reviewed"``).

        Returns:
            A list of ``Insight`` dataclass instances (with dismissed ones
            filtered out client-side).

        Emits ``error_occurred`` on failure.
        """
        try:
            insight_kwargs: dict[str, Any] = {"limit": limit}
            if status_filter is not None:
                insight_kwargs["status_filter"] = status_filter
            self._require_remote("list_insights")
            items = await _await_if_needed(self._remote.list_insights(**insight_kwargs))
            insights = [_parse_insight(item) for item in items]
            # Client-side dismiss filtering
            return [i for i in insights if i.id not in self._dismissed_insights]
        except Exception as exc:
            logger.exception("list_insights failed")
            self.error_occurred.emit(self._describe_error(exc))
            raise

    async def dismiss_insight(self, insight_id: str) -> None:
        """Dismiss an insight (client-side tracking for now).

        Args:
            insight_id: The insight identifier to dismiss.

        Once dismissed, the insight will be filtered out of
        ``list_insights()`` results in the current session.
        """
        self._dismissed_insights.add(insight_id)
        logger.info("Insight dismissed (client-side): %s", insight_id)

    # ── TTS response output (voice mode, opt-in) ──────────────────────

    def set_voice_mode_active(self, active: bool) -> None:
        """Enable/disable TTS response output (voice-mode opt-in).

        Called by the UI when the user selects/reverts a voice mode.  When
        inactive, responses are never synthesized — TTS is strictly opt-in.
        """
        self._voice_mode_active = bool(active)
        logger.info("CoPilot TTS voice output %s", "enabled" if active else "disabled")

    def _schedule_speech(self, response: CoPilotResponse, language: str) -> None:
        """Fire-and-forget TTS synthesis + playback when voice mode is active.

        Runs on a daemon thread so neither the GUI thread nor the response
        path is ever blocked.  Failures are logged and swallowed — TTS output
        must never break the chat experience.
        """
        if not getattr(self, "_voice_mode_active", False):
            return
        text = self._resolve_speakable_text(response)
        if not text.strip():
            return

        def _run() -> None:
            try:
                provider = self._load_tts_provider()
                if provider is None:
                    logger.info("TTS provider not available — skipping speech output")
                    return
                from backend.copilot.voice.tts import TTSRequest
                audio = asyncio.run(
                    provider.synthesize(TTSRequest(text=text, language=language))
                )
                if not audio:
                    logger.warning("TTS synthesis returned no audio — skipping playback")
                    return
                # Queued signal → the TTSPlayer slot runs on the GUI thread.
                self.tts_audio_ready.emit(audio)
            except Exception as exc:
                logger.error("TTS synthesis failed: %s", exc)

        threading.Thread(target=_run, daemon=True).start()

    def _resolve_speakable_text(self, response: CoPilotResponse) -> str:
        """Resolve the response's summary/clarification into speakable text.

        Mirrors the panel's display formatting for the summary and clarification
        parts (TTS never speaks raw i18n keys or the execution timeline).
        """
        parts: list[str] = []
        summary_key = response.summary_key
        if summary_key:
            if summary_key == "copilot.summary.llm_chat":
                # Verbatim passthrough — the LLM answer may contain {, } or
                # newlines that str.format() would mangle or crash on.
                answer = (response.summary_params or {}).get("answer")
                if isinstance(answer, str) and answer.strip():
                    parts.append(answer)
            else:
                summary_text = t(summary_key, **response.summary_params)
                if summary_text and summary_text != summary_key:
                    parts.append(summary_text)
        clarification_key = response.clarification_question_key
        if clarification_key:
            clarification_text = t(clarification_key, **response.clarification_params)
            if clarification_text and clarification_text != clarification_key:
                parts.append(clarification_text)
        return "\n\n".join(parts)

    @staticmethod
    def _load_tts_provider() -> Any:
        """Conditionally import and instantiate the Piper TTS provider.

        Returns the provider instance, or ``None`` if the ``piper-tts``
        package is not installed (TTS output is then skipped silently).
        """
        try:
            from backend.copilot.voice.providers.piper_tts import PiperTTSProvider
            return PiperTTSProvider()
        except ImportError:
            logger.info("piper-tts not installed — TTS output disabled")
            return None
        except Exception as exc:
            logger.error("Failed to initialise Piper TTS provider: %s", exc)
            return None

    def _on_tts_audio_ready(self, audio: bytes) -> None:
        """Play synthesized TTS audio on the GUI thread (Qt slot).

        ``TTSPlayer.play_audio`` stops any in-flight utterance first, so
        responses never overlap.
        """
        try:
            player = getattr(self, "_tts_player", None)
            if player is None:
                from ui.copilot.tts_player import TTSPlayer
                player = TTSPlayer(self)
                self._tts_player = player
            player.play_audio(audio)
        except Exception as exc:
            logger.error("TTS playback failed: %s", exc)

    @property
    def tts_playing(self) -> bool:
        """Whether TTS audio is currently being played.

        Used by the panel to keep the wake word disarmed while the assistant
        is still speaking (no capture can overlap TTS playback).
        """
        player = getattr(self, "_tts_player", None)
        if player is None:
            return False
        try:
            state = player._player.playbackState()
            return int(state) == 1  # QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            return False

    # ── Wake-word monitoring (Enterprise hands-free voice) ────────────

    def set_wake_word_enabled(self, enabled: bool) -> None:
        """Enable/disable wake-word monitoring (Enterprise voice mode).

        The panel owns the mic/state machine; this flag tells the controller
        whether the wake-word engine may be consulted for streamed audio.
        """
        self._wake_word_enabled = bool(enabled)
        logger.info("CoPilot wake word %s", "enabled" if enabled else "disabled")

    @property
    def wake_word_available(self) -> bool:
        """Whether a wake-word engine is usable (lazy-loads the provider).

        When the optional engine dependency is missing this returns
        ``False`` so the UI can fall back to push-to-talk silently.
        """
        provider = getattr(self, "_wake_word_provider", None)
        if provider is None:
            provider = self._load_wake_word_provider()
            self._wake_word_provider = provider
        if provider is None:
            return False
        try:
            return bool(provider.available)
        except Exception as exc:
            logger.error("Wake-word availability check failed: %s", exc)
            return False

    def process_wake_word_audio(self, audio: bytes) -> bool:
        """Feed a streamed PCM chunk to the wake-word engine.

        Args:
            audio: 16 kHz mono Int16 PCM bytes (the AudioRecorder format).

        Returns:
            ``True`` when the wake word is detected.  Never raises — any
            engine error is logged and reported as ``False`` so the chat
            flow (and push-to-talk) is never affected.
        """
        provider = getattr(self, "_wake_word_provider", None)
        if provider is None:
            provider = self._load_wake_word_provider()
            self._wake_word_provider = provider
        if provider is None or not getattr(self, "_wake_word_enabled", False):
            return False
        try:
            from backend.copilot.voice.wake_word import WakeWordRequest
            result = provider.process(WakeWordRequest(audio=audio))
            return bool(result and result.detected)
        except Exception as exc:
            logger.error("Wake-word processing failed: %s", exc)
            return False

    def reset_wake_word(self) -> None:
        """Clear the wake-word engine's streaming state after a trigger."""
        provider = getattr(self, "_wake_word_provider", None)
        if provider is None:
            return
        try:
            provider.reset()
        except Exception as exc:
            logger.debug("Wake-word reset failed: %s", exc)

    @staticmethod
    def _load_wake_word_provider() -> Any:
        """Conditionally import and instantiate the wake-word engine.

        Returns the provider instance, or ``None`` when the optional engine
        package is not installed (wake word is then disabled and the panel
        falls back to push-to-talk).
        """
        try:
            from backend.copilot.voice.wake_word import OpenWakeWordProvider
            return OpenWakeWordProvider()
        except ImportError:
            logger.info("Wake-word engine not installed — wake word disabled")
            return None
        except Exception as exc:
            logger.error("Failed to initialise wake-word engine: %s", exc)
            return None

    # ── Internal helpers ─────────────────────────────────────────────

    def _require_remote(self, method: str) -> None:
        """Raise a clear error when no backing Co-Pilot service is configured."""
        if self._remote is None:
            logger.warning(
                "CoPilotController: no remote service configured — cannot call %s", method,
            )
            raise RuntimeError("copilot.error.not_configured")

    @staticmethod
    def _describe_error(exc: Exception) -> str:
        """Return a user-facing message for a remote/API failure.

        FastAPI error bodies are ``{"detail": {"message_key": ..., "detail": …}}``;
        extracting the inner ``detail`` gives the user something actionable
        instead of the raw ``requests.HTTPError`` repr.
        """
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                payload = response.json()
            except Exception:
                payload = None
            if isinstance(payload, dict):
                detail = payload.get("detail")
                if isinstance(detail, dict):
                    return detail.get("detail") or detail.get("message_key") or str(exc)
                if detail:
                    return str(detail)
        return str(exc)

    def _transcribe_audio(
        self, audio_data: bytes, language: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Transcribe audio bytes to text using Whisper STT (conditional).

        Returns ``(transcript, error_code)`` where *error_code* is ``None``
        on success.  Callers should check *error_code* first, then check
        whether *transcript* is empty (no speech detected).

        Error codes
        -----------
        ``copilot.error.stt_unavailable``
            The STT provider could not be loaded (faster-whisper not installed).
        ``copilot.error.stt_failed``
            The provider returned ``None`` or raised an exception.
        """
        if self._stt_provider is None:
            self._stt_provider = self._load_stt_provider()
        if self._stt_provider is None:
            logger.warning("STT provider not available — cannot transcribe voice input")
            return None, "copilot.error.stt_unavailable"
        try:
            result = self._stt_provider.transcribe(audio_data, language=language)
            if result is None:
                return None, "copilot.error.stt_failed"
            transcript = result.transcript or ""
            return transcript, None
        except Exception as exc:
            logger.error("STT transcription error: %s", exc)
            return None, "copilot.error.stt_failed"

    @staticmethod
    def _load_stt_provider() -> Any:
        """Conditionally import and instantiate the Whisper STT provider.

        Returns the provider instance, or ``None`` if the ``faster-whisper``
        package is not installed.
        """
        try:
            from backend.copilot.voice.providers.whisper_stt import WhisperSTTProvider
            return WhisperSTTProvider(model_size="small")
        except ImportError:
            logger.info("faster-whisper not installed — voice input disabled")
            return None
        except Exception as exc:
            logger.error("Failed to initialise Whisper STT provider: %s", exc)
            return None

    def _publish_event(self, event_type: str, data: dict) -> None:
        """Publish an event to the EventBus if one was injected."""
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event_type, data)
            except Exception as exc:
                logger.debug("EventBus publish failed for %s: %s", event_type, exc)
