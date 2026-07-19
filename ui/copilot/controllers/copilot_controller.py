"""CoPilotController — bridges UI widgets to backend /api/v1/copilot/* endpoints.

Full implementation with Qt signal/slot pattern for thread-safe UI updates,
dependency injection, WebSocket management with exponential backoff reconnect,
and local STT transcription via Whisper (conditional import).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, QUrl
from PySide6.QtWebSockets import QWebSocket

from client.remote_copilot import RemoteCopilotService
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

    def __init__(
        self,
        remote: RemoteCopilotService,
        event_bus: Any = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the controller.

        Args:
            remote: Fully configured ``RemoteCopilotService`` instance.
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
        language: str = "en",
    ) -> CoPilotResponse:
        """Send a user utterance to the Co-Pilot backend.

        Args:
            text: The natural-language utterance.
            language: ISO language code (default ``"en"``).

        Returns:
            A parsed ``CoPilotResponse`` dataclass.

        Emits:
            ``new_turn`` with the raw response dict.
            ``timeline_updated`` with the deserialised timeline list.
            ``error_occurred`` on failure.
        """
        try:
            chat_kwargs: dict[str, Any] = {
                "utterance": text,
                "language": language,
            }
            if self._conversation_id is not None:
                chat_kwargs["conversation_id"] = self._conversation_id
            raw = self._remote.chat(**chat_kwargs)
            response = _parse_response(raw)
            self._conversation_id = response.conversation_id
            if response.plan:
                self._active_plan_id = response.plan.plan_id
            # Emit signals for UI update
            self.new_turn.emit(raw)
            self.timeline_updated.emit([s.__dict__ for s in response.timeline])
            self._publish_event("copilot.turn.completed", {"conversation_id": self._conversation_id})
            return response
        except Exception as exc:
            logger.exception("send_utterance failed")
            self.error_occurred.emit(str(exc))
            raise

    async def send_voice(
        self,
        audio_data: bytes,
        language: str = "en",
    ) -> CoPilotResponse:
        """Transcribe audio locally (Whisper) then submit to voice endpoint.

        Args:
            audio_data: Raw audio bytes (WAV, MP3, etc.).
            language: Optional language hint for the STT engine.

        Returns:
            A parsed ``CoPilotResponse`` dataclass.

        Emits:
            ``new_turn`` with the raw response dict.
            ``timeline_updated`` with the deserialised timeline list.
            ``error_occurred`` on failure (including if STT unavailable).
        """
        try:
            transcript = self._transcribe_audio(audio_data, language)
            if not transcript:
                msg = "copilot.error.stt_failed"
                self.error_occurred.emit(msg)
                raise RuntimeError(msg)

            voice_kwargs: dict[str, Any] = {
                "utterance": transcript,
                "language": language,
            }
            if self._conversation_id is not None:
                voice_kwargs["conversation_id"] = self._conversation_id
            raw = self._remote.voice_input(**voice_kwargs)
            response = _parse_response(raw)
            self._conversation_id = response.conversation_id
            if response.plan:
                self._active_plan_id = response.plan.plan_id
            self.new_turn.emit(raw)
            self.timeline_updated.emit([s.__dict__ for s in response.timeline])
            self._publish_event("copilot.voice.completed", {"conversation_id": self._conversation_id})
            return response
        except Exception as exc:
            logger.exception("send_voice failed")
            self.error_occurred.emit(str(exc))
            raise

    # ── Plans ────────────────────────────────────────────────────────

    async def confirm_plan(self, plan_id: str) -> dict:
        """Confirm a plan awaiting confirmation.

        Emits ``plan_changed`` with the plan_id on success,
        ``error_occurred`` on failure.
        """
        try:
            result = self._remote.confirm_plan(plan_id)
            self._active_plan_id = None
            self.plan_changed.emit(plan_id)
            self._publish_event("copilot.plan.confirmed", {"plan_id": plan_id})
            return result
        except Exception as exc:
            logger.exception("confirm_plan failed: %s", plan_id)
            self.error_occurred.emit(str(exc))
            raise

    async def cancel_plan(self, plan_id: str) -> dict:
        """Cancel an in-flight plan.

        Emits ``plan_changed`` with the plan_id on success,
        ``error_occurred`` on failure.
        """
        try:
            result = self._remote.cancel_plan(plan_id)
            if self._active_plan_id == plan_id:
                self._active_plan_id = None
            self.plan_changed.emit(plan_id)
            self._publish_event("copilot.plan.cancelled", {"plan_id": plan_id})
            return result
        except Exception as exc:
            logger.exception("cancel_plan failed: %s", plan_id)
            self.error_occurred.emit(str(exc))
            raise

    async def undo_step(self, plan_id: str) -> dict:
        """Undo the last reversible step of a plan.

        Emits ``plan_changed`` with the plan_id on success,
        ``error_occurred`` on failure.
        """
        try:
            result = self._remote.undo_plan(plan_id)
            self.plan_changed.emit(plan_id)
            self._publish_event("copilot.plan.undone", {"plan_id": plan_id})
            return result
        except Exception as exc:
            logger.exception("undo_step failed: %s", plan_id)
            self.error_occurred.emit(str(exc))
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
            items = self._remote.list_conversations(**conv_kwargs)
            return [_parse_response(item) for item in items]
        except Exception as exc:
            logger.exception("list_conversations failed")
            self.error_occurred.emit(str(exc))
            raise

    async def get_conversation(self, conversation_id: str) -> dict:
        """Get full details for a specific conversation.

        Emits ``conversation_loaded`` with the raw response on success,
        ``error_occurred`` on failure.
        """
        try:
            result = self._remote.get_conversation(conversation_id)
            self.conversation_loaded.emit(result)
            return result
        except Exception as exc:
            logger.exception("get_conversation failed: %s", conversation_id)
            self.error_occurred.emit(str(exc))
            raise

    # ── Plan status ──────────────────────────────────────────────────

    async def get_plan(self, plan_id: str) -> dict:
        """Get the current status of an execution plan.

        Emits ``error_occurred`` on failure.
        """
        try:
            return self._remote.get_plan(plan_id)
        except Exception as exc:
            logger.exception("get_plan failed: %s", plan_id)
            self.error_occurred.emit(str(exc))
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

        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.disconnected.connect(self._on_ws_disconnected)

        url_str = self._remote.ws_url(self._ws_conversation_id)
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
            items = self._remote.list_insights(**insight_kwargs)
            insights = [_parse_insight(item) for item in items]
            # Client-side dismiss filtering
            return [i for i in insights if i.id not in self._dismissed_insights]
        except Exception as exc:
            logger.exception("list_insights failed")
            self.error_occurred.emit(str(exc))
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

    # ── Internal helpers ─────────────────────────────────────────────

    def _transcribe_audio(self, audio_data: bytes, language: str) -> Optional[str]:
        """Transcribe audio bytes to text using Whisper STT (conditional).

        Returns the transcript string, or ``None`` if STT is unavailable
        or transcription fails.
        """
        if self._stt_provider is None:
            self._stt_provider = self._load_stt_provider()
        if self._stt_provider is None:
            logger.warning("STT provider not available — cannot transcribe voice input")
            return None
        try:
            result = self._stt_provider.transcribe(audio_data, language=language)
            if result is None:
                return None
            return result.transcript or None
        except Exception as exc:
            logger.error("STT transcription error: %s", exc)
            return None

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
