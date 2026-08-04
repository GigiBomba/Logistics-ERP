"""Tests for the Co-Pilot API router (``/api/v1/copilot``).

Covers all 10 endpoints plus internal helpers:
- POST /copilot/chat
- POST /copilot/voice
- GET  /copilot/plans/{plan_id}
- POST /copilot/plans/{plan_id}/confirm
- POST /copilot/plans/{plan_id}/cancel
- POST /copilot/plans/{plan_id}/undo
- GET  /copilot/conversations
- GET  /copilot/conversations/{id}
- GET  /copilot/insights
- WS   /copilot/ws/{conversation_id}

Internal helpers:
- _check_kill_switch
- _set_kill_switch
- _cancel_inflight_plans
- _push_plan_update
- _validate_plan_ownership
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, PropertyMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.copilot.schemas import (
    CoPilotResponse,
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    Intent,
)
from tests.test_api.conftest import StrippedMock

BASE = "/api/v1/copilot"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_step(
    step_id: str = "step-0",
    tool_name: str = "vehicle.search",
    status: str = "succeeded",
    result: dict | None = None,
    error: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ExecutionStep:
    # status is a Literal but we accept str for test convenience
    return ExecutionStep(
        step_id=step_id,
        tool_name=tool_name,
        tool_version="1.0.0",
        parameters={},
        depends_on=[],
        confirmation_level=ConfirmationLevel.SAFE,
        status=status,
        result=result,
        error=error,
        started_at=started_at or datetime.utcnow(),
        finished_at=finished_at or datetime.utcnow(),
    )


def _make_plan(
    plan_id: str = "plan-1",
    conversation_id: str = "conv-1",
    requires_confirmation: bool = False,
    steps: list | None = None,
    intent_name: str = "vehicle.search",
) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id=plan_id,
        conversation_id=conversation_id,
        reasoning_graph_id="rg-1",
        intent=Intent(
            name=intent_name,
            entities=[],
            missing_required_entities=[],
            raw_utterance="show me trucks",
        ),
        steps=steps or [_make_step()],
        overall_confidence=0.95,
        requires_confirmation=requires_confirmation,
        created_at=datetime.utcnow(),
    )


def _make_chat_response(
    conversation_id: str = "conv-1",
    plan: ExecutionPlan | None = None,
    summary_key: str | None = "copilot.summary.vehicle.search",
    summary_params: dict | None = None,
) -> CoPilotResponse:
    return CoPilotResponse(
        conversation_id=conversation_id,
        summary_key=summary_key,
        summary_params=summary_params or {},
        plan=plan,
        timeline=plan.steps if plan else [],
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _cleanup_copilot_state():
    """Clear in-memory state between tests to prevent cross-test pollution."""
    import backend.api.v1.copilot_router as cr
    cr._pending_plans.clear()
    cr._plan_owners.clear()
    cr._company_conversations.clear()
    cr._ws_connections.clear()
    yield


@pytest.fixture
def mock_db():
    """A mock database with ``conn.execute`` returning empty results by default."""
    db = MagicMock(spec_set=["conn", "row_to_dict", "rows_to_dicts"])
    db.conn = MagicMock()
    db.row_to_dict = lambda row: row
    db.rows_to_dicts = lambda rows: rows
    # Default: fetchall returns empty list
    db.conn.execute.return_value.fetchall.return_value = []
    db.conn.execute.return_value.fetchone.return_value = None
    return db


@pytest.fixture
def client_with_db(app, mock_db):
    """TestClient with auth and ``get_db`` overridden so db-dependent endpoints can be tested."""
    from backend.dependencies import get_db
    from backend.dependencies_security import get_current_user, require_dispatcher, require_admin, require_manager

    mock_user = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    app.dependency_overrides[require_manager] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, mock_db
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# POST /copilot/chat
# ══════════════════════════════════════════════════════════════════════════════

class TestChat:
    """POST /api/v1/copilot/chat — process a natural-language utterance."""

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_chat_returns_200_with_response(self, mock_process, client):
        """Happy path: valid utterance returns a ChatResponse."""
        mock_response = _make_chat_response(
            conversation_id="conv-abc",
            summary_key="copilot.summary.vehicle.search",
        )
        mock_process.return_value = mock_response

        resp = client.post(f"{BASE}/chat", json={
            "utterance": "show me available trucks",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv-abc"
        assert data["summary_key"] == "copilot.summary.vehicle.search"
        mock_process.assert_called_once()

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_chat_stores_plan_when_confirmation_needed(self, mock_process, client):
        """When the plan requires confirmation, it should be stored in-memory."""
        plan = _make_plan(plan_id="plan-abc", requires_confirmation=True)
        mock_response = _make_chat_response(conversation_id="conv-1", plan=plan)
        mock_process.return_value = mock_response

        resp = client.post(f"{BASE}/chat", json={
            "utterance": "create a new dispatch",
        })

        assert resp.status_code == 200
        assert resp.json()["plan_id"] == "plan-abc"

        # Verify in-memory state
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners
        assert "plan-abc" in _pending_plans
        assert _plan_owners["plan-abc"] == 1  # company_id from mock user

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_chat_rejects_empty_utterance(self, mock_process, client):
        """Empty utterance should be rejected by Pydantic validation."""
        resp = client.post(f"{BASE}/chat", json={"utterance": ""})

        assert resp.status_code == 422
        mock_process.assert_not_called()

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_chat_rejects_utterance_too_long(self, mock_process, client):
        """Utterance exceeding max_length should be rejected."""
        resp = client.post(f"{BASE}/chat", json={"utterance": "x" * 2001})

        assert resp.status_code == 422
        mock_process.assert_not_called()

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_chat_rejects_extra_fields(self, mock_process, client):
        """Extra fields should be rejected (model_config extra='forbid')."""
        resp = client.post(f"{BASE}/chat", json={
            "utterance": "hello",
            "bad_field": "should_not_be_allowed",
        })

        assert resp.status_code == 422
        mock_process.assert_not_called()

    def test_chat_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/chat", json={"utterance": "hello"})
        assert resp.status_code == 401

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_chat_returns_500_on_service_error(self, mock_process, client):
        """When process_utterance raises, the endpoint returns 500."""
        mock_process.side_effect = RuntimeError("LLM provider timeout")

        resp = client.post(f"{BASE}/chat", json={"utterance": "show me trucks"})

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert detail["message_key"] == "copilot.error.internal"


# ══════════════════════════════════════════════════════════════════════════════
# POST /copilot/voice
# ══════════════════════════════════════════════════════════════════════════════

class TestVoice:
    """POST /api/v1/copilot/voice — process voice STT transcript."""

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_voice_returns_200_with_response(self, mock_process, client):
        """Happy path: valid voice transcript returns a ChatResponse."""
        mock_response = _make_chat_response(
            conversation_id="conv-voice",
            summary_key="copilot.summary.tracking.get_live_positions",
        )
        mock_process.return_value = mock_response

        resp = client.post(f"{BASE}/voice", json={
            "utterance": "where is truck 42",
            "language": "en",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv-voice"
        assert data["summary_key"] == "copilot.summary.tracking.get_live_positions"
        mock_process.assert_called_once()

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_voice_rejects_empty_transcript(self, mock_process, client):
        """Empty utterance should be rejected by validation."""
        resp = client.post(f"{BASE}/voice", json={"utterance": ""})
        assert resp.status_code == 422
        mock_process.assert_not_called()

    def test_voice_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/voice", json={"utterance": "hello"})
        assert resp.status_code == 401

    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_voice_returns_500_on_service_error(self, mock_process, client):
        """When process_utterance raises, the endpoint returns 500."""
        mock_process.side_effect = RuntimeError("STT engine failure")

        resp = client.post(f"{BASE}/voice", json={"utterance": "where is truck 42"})

        assert resp.status_code == 500
        assert "copilot.error.internal" in resp.json()["detail"]["message_key"]


# ══════════════════════════════════════════════════════════════════════════════
# GET /copilot/plans/{plan_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestGetPlan:
    """GET /api/v1/copilot/plans/{plan_id} — retrieve plan status."""

    def test_get_plan_returns_plan_when_found(self, client):
        """Happy path: plan exists and is returned."""
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners

        plan = _make_plan(plan_id="plan-found", requires_confirmation=True)
        _pending_plans["plan-found"] = plan
        _plan_owners["plan-found"] = 1  # same company as mock user

        resp = client.get(f"{BASE}/plans/plan-found")

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "plan-found"
        assert data["status"] == "awaiting_confirmation"
        assert data["intent"] == "vehicle.search"
        assert "steps" in data

    def test_get_plan_returns_not_found_when_missing(self, client):
        """When plan does not exist, return 200 with status='not_found'."""
        resp = client.get(f"{BASE}/plans/non-existent-plan")

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "non-existent-plan"
        assert data["status"] == "not_found"

    def test_get_plan_returns_plan_for_completed(self, client):
        """A plan without requires_confirmation should show as completed."""
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners

        plan = _make_plan(plan_id="plan-done", requires_confirmation=False)
        _pending_plans["plan-done"] = plan
        _plan_owners["plan-done"] = 1

        resp = client.get(f"{BASE}/plans/plan-done")

        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_get_plan_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/plans/plan-1")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /copilot/plans/{plan_id}/confirm
# ══════════════════════════════════════════════════════════════════════════════

class TestConfirmPlan:
    """POST /api/v1/copilot/plans/{plan_id}/confirm — execute a confirmed plan."""

    @patch("backend.copilot.executor.confirm_and_execute")
    def test_confirm_plan_returns_completed(self, mock_confirm, client):
        """Happy path: plan is confirmed and executed successfully."""
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners

        plan = _make_plan(plan_id="plan-confirm", requires_confirmation=True)
        _pending_plans["plan-confirm"] = plan
        _plan_owners["plan-confirm"] = 1

        executed_plan = _make_plan(
            plan_id="plan-confirm",
            requires_confirmation=False,
            steps=[_make_step(status="succeeded", result={"data": {"ok": True}})],
        )
        mock_confirm.return_value = executed_plan

        resp = client.post(f"{BASE}/plans/plan-confirm/confirm")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["plan_id"] == "plan-confirm"
        mock_confirm.assert_called_once()

        # Plan should be removed from pending store
        assert "plan-confirm" not in _pending_plans

    def test_confirm_plan_returns_404_when_not_found(self, client):
        """Confirming a non-existent plan returns 404."""
        resp = client.post(f"{BASE}/plans/ghost-plan/confirm")

        assert resp.status_code == 404
        assert resp.json()["detail"]["message_key"] == "copilot.plan.not_found"

    def test_confirm_plan_returns_403_wrong_company(self, client):
        """A plan owned by another company returns 403."""
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners

        plan = _make_plan(plan_id="plan-other", requires_confirmation=True)
        _pending_plans["plan-other"] = plan
        _plan_owners["plan-other"] = 999  # different company

        resp = client.post(f"{BASE}/plans/plan-other/confirm")

        assert resp.status_code == 403
        assert resp.json()["detail"]["message_key"] == "copilot.plan.not_owned"

    def test_confirm_plan_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/plans/any-plan/confirm")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /copilot/plans/{plan_id}/cancel
# ══════════════════════════════════════════════════════════════════════════════

class TestCancelPlan:
    """POST /api/v1/copilot/plans/{plan_id}/cancel — cancel an in-flight plan."""

    @patch("backend.copilot.executor.cancel_plan")
    def test_cancel_plan_returns_cancelled(self, mock_cancel, client):
        """Happy path: plan is cancelled successfully."""
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners

        plan = _make_plan(plan_id="plan-cancel", requires_confirmation=True)
        _pending_plans["plan-cancel"] = plan
        _plan_owners["plan-cancel"] = 1

        cancelled_plan = _make_plan(plan_id="plan-cancel", requires_confirmation=False)
        mock_cancel.return_value = cancelled_plan

        resp = client.post(f"{BASE}/plans/plan-cancel/cancel")

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "plan-cancel"
        assert data["status"] == "cancelled"
        mock_cancel.assert_called_once()

        # Plan removed from pending store
        assert "plan-cancel" not in _pending_plans

    def test_cancel_plan_returns_404_when_not_found(self, client):
        """Cancelling a non-existent plan returns 404."""
        resp = client.post(f"{BASE}/plans/ghost-plan/cancel")
        assert resp.status_code == 404

    def test_cancel_plan_returns_403_wrong_company(self, client):
        """A plan owned by another company returns 403."""
        from backend.api.v1.copilot_router import _pending_plans, _plan_owners

        plan = _make_plan(plan_id="plan-other-cancel", requires_confirmation=True)
        _pending_plans["plan-other-cancel"] = plan
        _plan_owners["plan-other-cancel"] = 999

        resp = client.post(f"{BASE}/plans/plan-other-cancel/cancel")
        assert resp.status_code == 403

    def test_cancel_plan_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/plans/any-plan/cancel")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /copilot/plans/{plan_id}/undo
# ══════════════════════════════════════════════════════════════════════════════

class TestUndoPlan:
    """POST /api/v1/copilot/plans/{plan_id}/undo — reverse a completed step."""

    def _make_audit_row(self, **overrides):
        """Build a dict simulating a DB row from copilot_audit_log."""
        row = {
            "plan_id": "plan-undo",
            "tool_name": "vehicle.search",
            "started_at": datetime.utcnow() - timedelta(minutes=5),
            "result": json.dumps({"undo_token": "utok-123"}),
            "status": "succeeded",
        }
        row.update(overrides)
        return row

    def test_undo_plan_returns_success(self, client_with_db):
        """Happy path: undo token found and tool supports undo."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchone.return_value = self._make_audit_row()

        with patch("backend.copilot.executor.is_undo_expired", return_value=False), \
             patch("backend.copilot.tools.registry.get_tool") as mock_get_tool:

            mock_tool = MagicMock()
            mock_tool.supports_undo = True
            mock_tool.undo = AsyncMock()
            mock_tool.undo.return_value = MagicMock(
                status="success",
                message_key="copilot.undo.completed",
            )
            mock_get_tool.return_value = mock_tool

            resp = client.post(f"{BASE}/plans/plan-undo/undo")

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "plan-undo"
        assert data["undo_status"] == "success"

    def test_undo_plan_returns_404_no_audit_log(self, client_with_db):
        """When audit log has no matching row, return 404."""
        client, mock_db = client_with_db
        mock_db.conn.execute.return_value.fetchone.return_value = None

        resp = client.post(f"{BASE}/plans/plan-no-audit/undo")

        assert resp.status_code == 404
        assert resp.json()["detail"]["message_key"] == "copilot.undo.not_found"

    def test_undo_plan_returns_400_no_undo_token(self, client_with_db):
        """When audit log result has no undo_token, return 400."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchone.return_value = self._make_audit_row(
            result=json.dumps({"some_key": "some_value"}),
        )

        with patch("backend.copilot.executor.is_undo_expired", return_value=False):
            resp = client.post(f"{BASE}/plans/plan-no-undo/undo")

        assert resp.status_code == 400
        assert resp.json()["detail"]["message_key"] == "copilot.undo.not_available"

    def test_undo_plan_returns_400_expired(self, client_with_db):
        """When undo window has expired, return 400."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchone.return_value = self._make_audit_row(
            result=json.dumps({"undo_token": "utok-old"}),
            started_at=datetime.utcnow() - timedelta(hours=2),
        )

        with patch("backend.copilot.executor.is_undo_expired", return_value=True):
            resp = client.post(f"{BASE}/plans/plan-expired/undo")

        assert resp.status_code == 400
        assert resp.json()["detail"]["message_key"] == "copilot.undo.expired"

    def test_undo_plan_returns_400_tool_not_support_undo(self, client_with_db):
        """When the tool does not support undo, return 400."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchone.return_value = self._make_audit_row()

        with patch("backend.copilot.executor.is_undo_expired", return_value=False), \
             patch("backend.copilot.tools.registry.get_tool") as mock_get_tool:

            mock_get_tool.return_value = MagicMock(supports_undo=False)

            resp = client.post(f"{BASE}/plans/plan-no-support/undo")

        assert resp.status_code == 400
        assert resp.json()["detail"]["message_key"] == "copilot.undo.not_supported"

    def test_undo_plan_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/plans/any-plan/undo")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /copilot/conversations
# ══════════════════════════════════════════════════════════════════════════════

class TestListConversations:
    """GET /api/v1/copilot/conversations — list user conversations."""

    def _make_conv_row(self, conv_id, started_at="2025-01-01T00:00:00",
                       ended_at=None, turn_count=5, outcome="completed"):
        return {
            "id": conv_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "turn_count": turn_count,
            "outcome": outcome,
        }

    def test_list_conversations_returns_items(self, client_with_db):
        """Happy path: conversations are returned with pagination cursor."""
        client, mock_db = client_with_db

        rows = [
            self._make_conv_row("conv-1", turn_count=5),
            self._make_conv_row("conv-2", started_at="2025-01-02T00:00:00",
                                turn_count=3, outcome="abandoned"),
        ]
        mock_db.conn.execute.return_value.fetchall.return_value = rows

        resp = client.get(f"{BASE}/conversations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["conversation_id"] == "conv-1"
        assert data["items"][1]["conversation_id"] == "conv-2"
        assert data["limit"] == 20
        # next_cursor is None because len(rows) < limit
        assert data["next_cursor"] is None

    def test_list_conversations_empty(self, client_with_db):
        """When no conversations exist, return empty items list."""
        client, mock_db = client_with_db
        mock_db.conn.execute.return_value.fetchall.return_value = []

        resp = client.get(f"{BASE}/conversations")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["next_cursor"] is None

    def test_list_conversations_with_cursor(self, client_with_db):
        """Pagination cursor filters conversations after the cursor."""
        client, mock_db = client_with_db

        rows = [self._make_conv_row("conv-3", started_at="2025-01-03T00:00:00", turn_count=1)]
        mock_db.conn.execute.return_value.fetchall.return_value = rows

        resp = client.get(f"{BASE}/conversations?cursor=conv-2&limit=10")

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        # Verify the query used the cursor parameter
        call_args = mock_db.conn.execute.call_args
        assert call_args is not None
        assert "created_at < ?" in call_args[0][0]

    def test_list_conversations_handles_db_error(self, client_with_db):
        """When the database query fails, return empty list gracefully."""
        client, mock_db = client_with_db
        mock_db.conn.execute.side_effect = RuntimeError("DB connection lost")

        resp = client.get(f"{BASE}/conversations")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["next_cursor"] is None

    def test_list_conversations_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/conversations")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /copilot/conversations/{conversation_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestGetConversation:
    """GET /api/v1/copilot/conversations/{id} — conversation detail."""

    def _make_conv_detail_row(self, **overrides):
        row = {
            "id": "conv-detail",
            "started_at": "2025-01-01T00:00:00",
            "ended_at": None,
            "turn_count": 5,
            "outcome": "completed",
            "pinned_provider_id": "openai",
            "pinned_model_id": "gpt-4",
            "pinned_prompt_version": "v2.1",
        }
        row.update(overrides)
        return row

    def test_get_conversation_returns_detail(self, client_with_db):
        """Happy path: returns conversation detail with turns."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchone.return_value = self._make_conv_detail_row()

        resp = client.get(f"{BASE}/conversations/conv-detail")

        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv-detail"
        assert data["turn_count"] == 5
        assert data["pinned_provider_id"] == "openai"
        assert data["pinned_model_id"] == "gpt-4"

    def test_get_conversation_returns_404(self, client_with_db):
        """When conversation is not found, return 404."""
        client, mock_db = client_with_db
        mock_db.conn.execute.return_value.fetchone.return_value = None

        resp = client.get(f"{BASE}/conversations/unknown-conv")

        assert resp.status_code == 404

    def test_get_conversation_handles_db_error(self, client_with_db):
        """Database error returns 500."""
        client, mock_db = client_with_db
        mock_db.conn.execute.side_effect = RuntimeError("DB failure")

        resp = client.get(f"{BASE}/conversations/conv-1")

        assert resp.status_code == 500
        assert resp.json()["detail"]["message_key"] == "copilot.error.internal"

    def test_get_conversation_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/conversations/conv-1")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /copilot/insights
# ══════════════════════════════════════════════════════════════════════════════

class TestListInsights:
    """GET /api/v1/copilot/insights — proactive insights queue."""

    def _make_insight_row(self, **overrides):
        row = {
            "id": 1,
            "insight_type": "fuel_anomaly",
            "payload": json.dumps({"vehicle_id": 42, "saving_potential": 150}),
            "severity": "high",
            "status": "new",
            "created_at": "2025-01-01T00:00:00",
        }
        row.update(overrides)
        return row

    def test_list_insights_returns_items(self, client_with_db):
        """Happy path: insights are returned."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchall.return_value = [self._make_insight_row()]

        resp = client.get(f"{BASE}/insights")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["insight_type"] == "fuel_anomaly"
        assert data["items"][0]["payload"]["vehicle_id"] == 42
        assert data["limit"] == 20

    def test_list_insights_with_status_filter(self, client_with_db):
        """Status filter is passed to the database query."""
        client, mock_db = client_with_db

        mock_db.conn.execute.return_value.fetchall.return_value = [
            self._make_insight_row(id=2, insight_type="maintenance_due",
                                   payload="{}", severity="medium"),
        ]

        resp = client.get(f"{BASE}/insights?status_filter=new")

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

        # Verify SQL used status filter
        call_args = mock_db.conn.execute.call_args
        assert call_args is not None
        assert "status = ?" in call_args[0][0]
        assert call_args[0][1][1] == "new"

    def test_list_insights_empty(self, client_with_db):
        """When no insights exist, return empty list."""
        client, mock_db = client_with_db
        mock_db.conn.execute.return_value.fetchall.return_value = []

        resp = client.get(f"{BASE}/insights")

        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_list_insights_handles_db_error(self, client_with_db):
        """Database error returns empty list gracefully."""
        client, mock_db = client_with_db
        mock_db.conn.execute.side_effect = RuntimeError("DB unavailable")

        resp = client.get(f"{BASE}/insights")

        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_list_insights_requires_auth(self, app):
        """Without a valid JWT token, the endpoint returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/insights")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# WS /copilot/ws/{conversation_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestWebSocket:
    """WebSocket endpoint for real-time plan updates."""

    def test_websocket_connects_with_valid_token(self, client):
        """Happy path: valid token establishes WebSocket and receives connected."""
        with patch("backend.security.decode_access_token") as mock_decode:
            mock_decode.return_value = {"company_id": 1, "sub": "test@test.com"}

            with client.websocket_connect(
                f"{BASE}/ws/conv-ws-1?token=valid.jwt.token"
            ) as ws:
                data = ws.receive_json()
                assert data["type"] == "connected"
                assert data["conversation_id"] == "conv-ws-1"

    def test_websocket_receives_pong_on_ping(self, client):
        """Sending 'ping' text should return a pong JSON message."""
        with patch("backend.security.decode_access_token") as mock_decode:
            mock_decode.return_value = {"company_id": 1}

            with client.websocket_connect(
                f"{BASE}/ws/conv-ws-2?token=valid.jwt.token"
            ) as ws:
                ws.receive_json()  # consume "connected"
                ws.send_text("ping")
                pong = ws.receive_json()
                assert pong["type"] == "pong"

    def test_websocket_rejects_missing_token(self, client):
        """When no token query param is provided, the connection is rejected."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"{BASE}/ws/conv-ws-no-token"):
                pass  # Should not reach here
        assert exc_info.value.code == 4001

    def test_websocket_rejects_invalid_token(self, client):
        """When the token is invalid, the connection is rejected."""
        with patch("backend.security.decode_access_token") as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"{BASE}/ws/conv-ws-bad?token=bad.token.here"
                ):
                    pass
            assert exc_info.value.code == 4001

    def test_websocket_disconnect_cleans_up(self, client):
        """When a WebSocket disconnects, it should be removed from _ws_connections."""
        from backend.api.v1.copilot_router import _ws_connections

        with patch("backend.security.decode_access_token") as mock_decode:
            mock_decode.return_value = {"company_id": 1}

            with client.websocket_connect(
                f"{BASE}/ws/conv-cleanup?token=valid.jwt.token"
            ) as ws:
                ws.receive_json()  # consume "connected"
                # After connect, the connection should be registered
                assert "conv-cleanup" in _ws_connections
                assert len(_ws_connections["conv-cleanup"]) == 1

            # After exiting the context manager, the connection should be removed
            assert len(_ws_connections.get("conv-cleanup", [])) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestKillSwitch:
    """_check_kill_switch — platform and per-company kill switch."""

    @patch("backend.cache.get_cache")
    def test_check_kill_switch_platform_tripped(self, mock_get_cache, client):
        """When platform-wide kill switch is active, return 503."""
        mock_cache = MagicMock()
        mock_cache.get.side_effect = lambda key: True if "platform" in key else None
        mock_get_cache.return_value = mock_cache

        resp = client.post(f"{BASE}/chat", json={"utterance": "hello"})

        assert resp.status_code == 503
        assert resp.json()["detail"]["message_key"] == "copilot.error.unavailable"

    @patch("backend.cache.get_cache")
    def test_check_kill_switch_company_tripped(self, mock_get_cache, client):
        """When per-company kill switch is active, return 503."""
        mock_cache = MagicMock()
        # Platform key returns None (not killed), company key returns True (killed)
        def cache_get(key):
            if "platform" in key:
                return None
            if "company:1" in key:
                return True
            return None
        mock_cache.get.side_effect = cache_get
        mock_get_cache.return_value = mock_cache

        resp = client.post(f"{BASE}/chat", json={"utterance": "hello"})

        assert resp.status_code == 503
        assert resp.json()["detail"]["message_key"] == "copilot.error.unavailable"

    @patch("backend.cache.get_cache")
    @patch("backend.api.v1.copilot_router.process_utterance")
    def test_check_kill_switch_not_tripped(self, mock_process, mock_get_cache, client):
        """When neither kill switch is active, the request proceeds normally."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get_cache.return_value = mock_cache
        mock_process.return_value = _make_chat_response()

        resp = client.post(f"{BASE}/chat", json={"utterance": "hello"})

        assert resp.status_code == 200
        mock_process.assert_called_once()


class TestSetKillSwitch:
    """_set_kill_switch — toggling kill switch state."""

    @patch("backend.cache.get_cache")
    @patch("backend.api.v1.copilot_router._cancel_inflight_plans")
    def test_set_kill_switch_platform(self, mock_cancel_inflight, mock_get_cache):
        """Setting platform-wide kill switch stores key without company_id."""
        import backend.api.v1.copilot_router as cr

        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        # Use asyncio.run since _set_kill_switch is async
        import asyncio
        asyncio.run(cr._set_kill_switch(company_id=None, killed=True))

        mock_cache.set.assert_called_once_with(
            "copilot:kill_switch:platform", True, ttl=86400
        )
        mock_cancel_inflight.assert_called_once_with(None)

    @patch("backend.cache.get_cache")
    @patch("backend.api.v1.copilot_router._cancel_inflight_plans")
    def test_set_kill_switch_company(self, mock_cancel_inflight, mock_get_cache):
        """Setting per-company kill switch stores key with company_id."""
        import backend.api.v1.copilot_router as cr

        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        import asyncio
        asyncio.run(cr._set_kill_switch(company_id=42, killed=True))

        mock_cache.set.assert_called_once_with(
            "copilot:kill_switch:company:42", True, ttl=86400
        )
        mock_cancel_inflight.assert_called_once_with(42)

    @patch("backend.cache.get_cache")
    def test_set_kill_switch_disables_without_cancelling(self, mock_get_cache):
        """Disabling kill switch should not cancel inflight plans."""
        import backend.api.v1.copilot_router as cr

        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        import asyncio
        asyncio.run(cr._set_kill_switch(company_id=42, killed=False))

        mock_cache.set.assert_called_once_with(
            "copilot:kill_switch:company:42", False, ttl=86400
        )


class TestCancelInflightPlans:
    """_cancel_inflight_plans — cancel pending plans for a company."""

    @patch("backend.copilot.executor.cancel_plan")
    def test_cancel_inflight_plans_all(self, mock_cancel_plan):
        """Cancel all pending plans when company_id is None."""
        import backend.api.v1.copilot_router as cr

        plan1 = _make_plan(plan_id="p1", requires_confirmation=True)
        plan2 = _make_plan(plan_id="p2", requires_confirmation=True)
        cr._pending_plans["p1"] = plan1
        cr._pending_plans["p2"] = plan2
        cr._plan_owners["p1"] = 1
        cr._plan_owners["p2"] = 2

        mock_cancel_plan.side_effect = lambda p: p

        import asyncio
        asyncio.run(cr._cancel_inflight_plans(company_id=None))

        assert len(cr._pending_plans) == 0
        assert len(cr._plan_owners) == 0
        assert mock_cancel_plan.call_count == 2

    @patch("backend.copilot.executor.cancel_plan")
    def test_cancel_inflight_plans_specific_company(self, mock_cancel_plan):
        """Cancel only plans belonging to the specified company."""
        import backend.api.v1.copilot_router as cr

        plan1 = _make_plan(plan_id="p1", requires_confirmation=True)
        plan2 = _make_plan(plan_id="p2", requires_confirmation=True)
        cr._pending_plans["p1"] = plan1
        cr._pending_plans["p2"] = plan2
        cr._plan_owners["p1"] = 1
        cr._plan_owners["p2"] = 2

        mock_cancel_plan.side_effect = lambda p: p

        import asyncio
        asyncio.run(cr._cancel_inflight_plans(company_id=1))

        assert "p1" not in cr._pending_plans  # Cancelled
        assert "p2" in cr._pending_plans      # Not cancelled (company 2)
        assert mock_cancel_plan.call_count == 1

    @patch("backend.copilot.executor.cancel_plan")
    def test_cancel_inflight_plans_no_matching(self, mock_cancel_plan):
        """When no plans match the company, nothing is cancelled."""
        import backend.api.v1.copilot_router as cr

        plan = _make_plan(plan_id="p1", requires_confirmation=True)
        cr._pending_plans["p1"] = plan
        cr._plan_owners["p1"] = 1

        mock_cancel_plan.side_effect = lambda p: p

        import asyncio
        asyncio.run(cr._cancel_inflight_plans(company_id=999))

        assert "p1" in cr._pending_plans  # Still there
        mock_cancel_plan.assert_not_called()


class TestPushPlanUpdate:
    """_push_plan_update — push step status via WebSocket."""

    @pytest.mark.asyncio
    async def test_push_plan_update_sends_message(self):
        """Should send a step_update JSON message to all connections."""
        import backend.api.v1.copilot_router as cr

        mock_ws = AsyncMock()
        cr._ws_connections["conv-push"] = [mock_ws]

        await cr._push_plan_update(
            step_id="step-0",
            status="running",
            tool_name="vehicle.search",
            conversation_id="conv-push",
        )

        mock_ws.send_json.assert_called_once()
        call_arg = mock_ws.send_json.call_args[0][0]
        assert call_arg["type"] == "step_update"
        assert call_arg["step_id"] == "step-0"
        assert call_arg["status"] == "running"
        assert call_arg["tool_name"] == "vehicle.search"
        assert "timestamp" in call_arg

    @pytest.mark.asyncio
    async def test_push_plan_update_no_connections(self):
        """Should not raise when there are no connections for the conversation."""
        import backend.api.v1.copilot_router as cr

        # No connections for this conversation
        await cr._push_plan_update(
            step_id="step-0",
            status="completed",
            tool_name="vehicle.search",
            conversation_id="conv-nonexistent",
        )
        # No assertion needed — just verifying no exception

    @pytest.mark.asyncio
    async def test_push_plan_update_removes_dead_connections(self):
        """Dead connections should be removed after a failed send."""
        import backend.api.v1.copilot_router as cr

        dead_ws = AsyncMock()
        dead_ws.send_json.side_effect = Exception("Connection lost")

        cr._ws_connections["conv-dead"] = [dead_ws]

        await cr._push_plan_update(
            step_id="step-0",
            status="failed",
            tool_name="vehicle.search",
            conversation_id="conv-dead",
        )

        # Dead connection should be removed
        assert len(cr._ws_connections["conv-dead"]) == 0


class TestValidatePlanOwnership:
    """_validate_plan_ownership — company isolation check."""

    def test_validate_plan_ownership_returns_plan(self):
        """When plan exists and belongs to the company, return it."""
        from backend.api.v1.copilot_router import (
            _pending_plans,
            _plan_owners,
            _validate_plan_ownership,
        )

        plan = _make_plan(plan_id="my-plan")
        _pending_plans["my-plan"] = plan
        _plan_owners["my-plan"] = 1

        result = _validate_plan_ownership("my-plan", 1)
        assert result is plan

    def test_validate_plan_ownership_raises_404_not_found(self):
        """When plan does not exist, raise 404."""
        from backend.api.v1.copilot_router import _validate_plan_ownership

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("ghost-plan", 1)
        assert exc.value.status_code == 404

    def test_validate_plan_ownership_raises_403_wrong_company(self):
        """When plan belongs to another company, raise 403."""
        from backend.api.v1.copilot_router import (
            _pending_plans,
            _plan_owners,
            _validate_plan_ownership,
        )

        plan = _make_plan(plan_id="other-plan")
        _pending_plans["other-plan"] = plan
        _plan_owners["other-plan"] = 999

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("other-plan", 1)
        assert exc.value.status_code == 403

    def test_validate_plan_ownership_no_owner_safe(self):
        """Plan without owner entry is still returned (backward compat)."""
        from backend.api.v1.copilot_router import (
            _pending_plans,
            _validate_plan_ownership,
        )

        plan = _make_plan(plan_id="unowned-plan")
        _pending_plans["unowned-plan"] = plan
        # No owner entry — should still return the plan

        result = _validate_plan_ownership("unowned-plan", 1)
        assert result is plan


# ══════════════════════════════════════════════════════════════════════════════
# Kill switch integration via endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestKillSwitchIntegration:
    """End-to-end kill switch behaviour through real endpoints."""

    @patch("backend.cache.get_cache")
    def test_all_endpoints_respect_platform_kill_switch(self, mock_get_cache, client):
        """Every copilot endpoint should return 503 when platform kill switch is on."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = True  # Kill switch active
        mock_get_cache.return_value = mock_cache

        # These endpoints should all be blocked by the kill switch
        endpoints = [
            ("POST", f"{BASE}/chat", {"json": {"utterance": "hello"}}),
            ("POST", f"{BASE}/voice", {"json": {"utterance": "hello"}}),
            ("GET", f"{BASE}/plans/fake"),
            ("POST", f"{BASE}/plans/fake/confirm"),
            ("POST", f"{BASE}/plans/fake/cancel"),
            ("POST", f"{BASE}/plans/fake/undo"),
            ("GET", f"{BASE}/conversations"),
            ("GET", f"{BASE}/conversations/fake"),
            ("GET", f"{BASE}/insights"),
        ]

        for method, url, *kwargs in endpoints:
            kwargs_dict = kwargs[0] if kwargs else {}
            resp = getattr(client, method.lower())(url, **kwargs_dict)
            assert resp.status_code == 503, (
                f"{method} {url} expected 503, got {resp.status_code}"
            )
