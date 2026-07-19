"""Tests for CoPilotController — direct, no Qt, using MagicMock for RemoteCopilotService.

The controller extends QObject, so we create a real QApplication once (session scope)
to satisfy Qt's requirement, then mock the RemoteCopilotService for each test.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject

from ui.copilot.controllers.copilot_controller import CoPilotController


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication once — required for any QObject subclass to function."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def remote():
    return MagicMock()


@pytest.fixture
def controller(remote, qapp):
    """Build controller with a mocked RemoteCopilotService."""
    ctrl = CoPilotController.__new__(CoPilotController)
    # Minimal QObject init (bypasses the full __init__ to avoid WS/STT setup)
    QObject.__init__(ctrl)
    # Assign controller-specific state
    ctrl._remote = remote
    ctrl._event_bus = None
    ctrl._conversation_id = None
    ctrl._active_plan_id = None
    ctrl._ws = None
    ctrl._ws_conversation_id = None
    ctrl._ws_reconnect_attempt = 0
    ctrl._ws_max_reconnect_attempts = 10
    ctrl._ws_reconnect_delay = 1.0
    ctrl._ws_reconnect_task = None
    ctrl._ws_intentional_disconnect = False
    ctrl._stt_provider = None
    ctrl._dismissed_insights = set()
    return ctrl


class TestSendUtterance:
    """send_utterance calls remote.chat with correct args."""

    @pytest.mark.asyncio
    async def test_calls_remote_chat(self, controller, remote):
        remote.chat.return_value = {
            "conversation_id": "c1",
            "plan": None,
            "timeline": [],
        }
        resp = await controller.send_utterance("Hello", language="ro")
        remote.chat.assert_called_once_with(utterance="Hello", language="ro")
        assert resp.conversation_id == "c1"

    @pytest.mark.asyncio
    async def test_sends_conversation_id_when_set(self, controller, remote):
        controller._conversation_id = "c_existing"
        remote.chat.return_value = {
            "conversation_id": "c_existing",
            "plan": None,
            "timeline": [],
        }
        await controller.send_utterance("Hello")
        remote.chat.assert_called_once_with(
            utterance="Hello", language="en", conversation_id="c_existing"
        )

    @pytest.mark.asyncio
    async def test_updates_conversation_id(self, controller, remote):
        remote.chat.return_value = {
            "conversation_id": "c_new",
            "plan": None,
            "timeline": [],
        }
        assert controller._conversation_id is None
        await controller.send_utterance("Hello")
        assert controller._conversation_id == "c_new"

    @pytest.mark.asyncio
    async def test_updates_active_plan_id_when_plan_returned(self, controller, remote):
        remote.chat.return_value = {
            "conversation_id": "c1",
            "plan": {"plan_id": "p1", "intent": {"name": "test"}, "steps": [], "requires_confirmation": False},
            "timeline": [],
        }
        await controller.send_utterance("Hello")
        assert controller._active_plan_id == "p1"

    @pytest.mark.asyncio
    async def test_emits_new_turn_signal(self, controller, remote):
        remote.chat.return_value = {"conversation_id": "c1", "plan": None, "timeline": []}
        handler = MagicMock()
        controller.new_turn.connect(handler)
        await controller.send_utterance("Hello")
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_timeline_updated_signal(self, controller, remote):
        remote.chat.return_value = {"conversation_id": "c1", "plan": None, "timeline": []}
        handler = MagicMock()
        controller.timeline_updated.connect(handler)
        await controller.send_utterance("Hello")
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_emits_error_occurred_on_failure(self, controller, remote):
        remote.chat.side_effect = RuntimeError("API down")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(RuntimeError, match="API down"):
            await controller.send_utterance("Hello")
        handler.assert_called_once_with("API down")


class TestConfirmPlan:
    @pytest.mark.asyncio
    async def test_calls_remote_confirm_plan(self, controller, remote):
        remote.confirm_plan.return_value = {"status": "confirmed"}
        result = await controller.confirm_plan("p1")
        remote.confirm_plan.assert_called_once_with("p1")
        assert result["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_clears_active_plan_id(self, controller, remote):
        controller._active_plan_id = "p1"
        remote.confirm_plan.return_value = {"status": "confirmed"}
        await controller.confirm_plan("p1")
        assert controller._active_plan_id is None

    @pytest.mark.asyncio
    async def test_emits_plan_changed(self, controller, remote):
        remote.confirm_plan.return_value = {"status": "confirmed"}
        handler = MagicMock()
        controller.plan_changed.connect(handler)
        await controller.confirm_plan("p1")
        handler.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_emits_error_occurred_on_failure(self, controller, remote):
        remote.confirm_plan.side_effect = ValueError("bad plan")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(ValueError, match="bad plan"):
            await controller.confirm_plan("p1")
        handler.assert_called_once_with("bad plan")


class TestCancelPlan:
    @pytest.mark.asyncio
    async def test_calls_remote_cancel_plan(self, controller, remote):
        remote.cancel_plan.return_value = {"status": "cancelled"}
        result = await controller.cancel_plan("p1")
        remote.cancel_plan.assert_called_once_with("p1")
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_clears_active_plan_id_when_matching(self, controller, remote):
        controller._active_plan_id = "p1"
        remote.cancel_plan.return_value = {"status": "cancelled"}
        await controller.cancel_plan("p1")
        assert controller._active_plan_id is None

    @pytest.mark.asyncio
    async def test_does_not_clear_active_plan_id_on_mismatch(self, controller, remote):
        controller._active_plan_id = "p_other"
        remote.cancel_plan.return_value = {"status": "cancelled"}
        await controller.cancel_plan("p1")
        assert controller._active_plan_id == "p_other"

    @pytest.mark.asyncio
    async def test_emits_plan_changed(self, controller, remote):
        remote.cancel_plan.return_value = {"status": "cancelled"}
        handler = MagicMock()
        controller.plan_changed.connect(handler)
        await controller.cancel_plan("p1")
        handler.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_emits_error_occurred_on_failure(self, controller, remote):
        remote.cancel_plan.side_effect = RuntimeError("fail")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(RuntimeError):
            await controller.cancel_plan("p1")
        handler.assert_called_once()


class TestUndoStep:
    @pytest.mark.asyncio
    async def test_calls_remote_undo_plan(self, controller, remote):
        remote.undo_plan.return_value = {"status": "undone"}
        result = await controller.undo_step("p1")
        remote.undo_plan.assert_called_once_with("p1")
        assert result["status"] == "undone"

    @pytest.mark.asyncio
    async def test_emits_plan_changed(self, controller, remote):
        remote.undo_plan.return_value = {"status": "undone"}
        handler = MagicMock()
        controller.plan_changed.connect(handler)
        await controller.undo_step("p1")
        handler.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_emits_error_occurred_on_failure(self, controller, remote):
        remote.undo_plan.side_effect = RuntimeError("undo fail")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(RuntimeError):
            await controller.undo_step("p1")
        handler.assert_called_once()


class TestListConversations:
    @pytest.mark.asyncio
    async def test_calls_remote_list_conversations(self, controller, remote):
        remote.list_conversations.return_value = []
        result = await controller.list_conversations(limit=10, cursor="c1")
        remote.list_conversations.assert_called_once_with(limit=10, cursor="c1")
        assert result == []

    @pytest.mark.asyncio
    async def test_calls_with_defaults(self, controller, remote):
        remote.list_conversations.return_value = []
        await controller.list_conversations()
        remote.list_conversations.assert_called_once_with(limit=20)

    @pytest.mark.asyncio
    async def test_emits_error_occurred_on_failure(self, controller, remote):
        remote.list_conversations.side_effect = RuntimeError("list fail")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(RuntimeError):
            await controller.list_conversations()
        handler.assert_called_once()


class TestGetConversation:
    @pytest.mark.asyncio
    async def test_calls_remote_get_conversation(self, controller, remote):
        remote.get_conversation.return_value = {"id": "c1"}
        result = await controller.get_conversation("c1")
        remote.get_conversation.assert_called_once_with("c1")
        assert result["id"] == "c1"

    @pytest.mark.asyncio
    async def test_emits_conversation_loaded(self, controller, remote):
        remote.get_conversation.return_value = {"id": "c1"}
        handler = MagicMock()
        controller.conversation_loaded.connect(handler)
        await controller.get_conversation("c1")
        handler.assert_called_once_with({"id": "c1"})

    @pytest.mark.asyncio
    async def test_emits_error_occurred_on_failure(self, controller, remote):
        remote.get_conversation.side_effect = RuntimeError("get fail")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(RuntimeError):
            await controller.get_conversation("c1")
        handler.assert_called_once()


class TestConversationIdStateTracking:
    """Verify conversation_id state is tracked across multiple utterances."""

    @pytest.mark.asyncio
    async def test_starts_as_none(self, controller):
        assert controller._conversation_id is None
        assert controller._active_plan_id is None

    @pytest.mark.asyncio
    async def test_tracks_across_multiple_utterances(self, controller, remote):
        remote.chat.side_effect = [
            {"conversation_id": "c1", "plan": None, "timeline": []},
            {"conversation_id": "c1", "plan": None, "timeline": []},
        ]
        await controller.send_utterance("first")
        assert controller._conversation_id == "c1"
        await controller.send_utterance("second")
        assert controller._conversation_id == "c1"

    @pytest.mark.asyncio
    async def test_tracks_active_plan(self, controller, remote):
        remote.chat.return_value = {
            "conversation_id": "c1",
            "plan": {"plan_id": "p42", "intent": {"name": "test"}, "steps": [], "requires_confirmation": False},
            "timeline": [],
        }
        await controller.send_utterance("do something")
        assert controller._active_plan_id == "p42"


class TestErrorOccurredSignal:
    """Every method emits error_occurred when remote raises."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name,args,remote_attr", [
        ("send_utterance", ("hi",), "chat"),
        ("confirm_plan", ("p1",), "confirm_plan"),
        ("cancel_plan", ("p1",), "cancel_plan"),
        ("undo_step", ("p1",), "undo_plan"),
        ("list_conversations", (), "list_conversations"),
        ("get_conversation", ("c1",), "get_conversation"),
    ])
    async def test_all_methods_emit_error_occurred(self, controller, remote, method_name, args, remote_attr):
        getattr(remote, remote_attr).side_effect = RuntimeError("fail")
        handler = MagicMock()
        controller.error_occurred.connect(handler)
        with pytest.raises(RuntimeError):
            await getattr(controller, method_name)(*args)
        handler.assert_called_once()
