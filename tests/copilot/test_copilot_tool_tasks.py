"""Long-running tool task tests (§13).

Covers the progress-key helpers, the tool-step runner (progress payloads,
result envelope), the sync task body (audit terminal row + completion
notification), and graceful failure paths.  No real broker / Redis / DB used —
everything is faked.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.copilot.tools.registry import get_tool


@pytest.fixture(autouse=True)
def _fake_cache():
    """Point every cache access at an in-memory fake."""
    from backend.copilot.channels.whatsapp import registry as _  # noqa: F401 (import order safety)

    store = {}
    fake = MagicMock()

    def fake_set(key, value, ttl=None):
        store[key] = value
        return True

    def fake_get(key):
        return store.get(key)

    def fake_rpush(key, value):
        store.setdefault(key, []).append(value)
        return True

    def fake_lrange(key, start=0, end=-1):
        return list(store.get(key, []))

    def fake_expire(key, ttl):
        return True

    fake.set.side_effect = fake_set
    fake.get.side_effect = fake_get
    fake.rpush.side_effect = fake_rpush
    fake.lrange.side_effect = fake_lrange
    fake.expire.side_effect = fake_expire
    with patch("backend.cache.get_cache", return_value=fake):
        yield store


# ═══════════════════════════════════════════════════════════════════════════
# Progress-key helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestProgressHelpers:
    def test_write_read_progress(self, _fake_cache):
        from backend.celery_app.tasks.copilot_tool_tasks import (
            progress_key,
            read_progress,
            write_progress,
        )

        write_progress(
            "task-1", 50, "copilot.tool.progress.executing", "running",
            tool_name="freight.search_loads", step_id="step-1",
            conversation_id="conv-1", plan_id="plan-1",
        )
        payload = read_progress("task-1")
        assert payload["task_id"] == "task-1"
        assert payload["percent"] == 50
        assert payload["message_key"] == "copilot.tool.progress.executing"
        assert payload["status"] == "running"
        assert payload["tool_name"] == "freight.search_loads"
        assert payload["updated_at"]
        assert progress_key("task-1") == "copilot:tool-progress:task-1"

    def test_register_and_get_conversation_progress(self, _fake_cache):
        from backend.celery_app.tasks.copilot_tool_tasks import (
            get_conversation_progress_keys,
            register_conversation_progress,
        )

        register_conversation_progress("conv-1", "task-1")
        register_conversation_progress("conv-1", "task-2")
        keys = get_conversation_progress_keys("conv-1")
        assert keys == ["copilot:tool-progress:task-1", "copilot:tool-progress:task-2"]


# ═══════════════════════════════════════════════════════════════════════════
# _run_tool_step (the async core)
# ═══════════════════════════════════════════════════════════════════════════

class TestRunToolStep:
    @pytest.mark.asyncio
    async def test_success_writes_progress_and_result(self, _fake_cache):
        from backend.celery_app.tasks.copilot_tool_tasks import _run_tool_step, read_progress

        tool = get_tool("whatsapp.send_message")
        with patch("backend.copilot.channels.whatsapp.registry.get_whatsapp_provider") as mock_provider:
            provider = MagicMock()
            provider.provider_id = "whatsapp_cloud_api"
            provider.available = True
            provider.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.x"}]})
            mock_provider.return_value = provider

            outcome = await _run_tool_step(
                MagicMock(),
                task_id="task-ok",
                tool_name="whatsapp.send_message",
                params_json=json.dumps({"recipient": "+40712345678", "body": "Hi", "confirmation_phrase": "CONFIRM"}),
                company_id=1,
                user_id=1,
                role="manager",
                conversation_id="conv-1",
                plan_id="plan-1",
                step_id="step-1",
            )

        assert outcome["status"] == "succeeded"
        assert outcome["result"]["status"] == "success"
        final = read_progress("task-ok")
        assert final["status"] == "succeeded"
        assert final["percent"] == 100
        assert final["result"]["message_key"] == "copilot.tool.whatsapp.send_ok"

    @pytest.mark.asyncio
    async def test_unknown_tool_fails_gracefully(self, _fake_cache):
        from backend.celery_app.tasks.copilot_tool_tasks import _run_tool_step, read_progress

        outcome = await _run_tool_step(
            MagicMock(), task_id="task-missing", tool_name="no.such.tool",
            params_json="{}", company_id=1, user_id=1, role="manager",
            conversation_id="conv-1", plan_id="plan-1", step_id="step-1",
        )
        assert outcome["status"] == "failed"
        assert "not found" in outcome["error"]
        assert read_progress("task-missing")["status"] == "failed"

    @pytest.mark.asyncio
    async def test_validation_errors_fail_step(self, _fake_cache):
        from backend.celery_app.tasks.copilot_tool_tasks import _run_tool_step

        outcome = await _run_tool_step(
            MagicMock(), task_id="task-inv", tool_name="whatsapp.send_message",
            params_json=json.dumps({"recipient": "not-a-phone", "body": "x", "confirmation_phrase": "CONFIRM"}),
            company_id=1, user_id=1, role="manager",
            conversation_id="conv-1", plan_id="plan-1", step_id="step-1",
        )
        assert outcome["status"] == "failed"
        assert "Invalid phone number" in outcome["error"]

    @pytest.mark.asyncio
    async def test_tool_exception_fails_step(self, _fake_cache):
        from backend.celery_app.tasks.copilot_tool_tasks import _run_tool_step

        with patch("backend.copilot.channels.whatsapp.registry.get_whatsapp_provider") as mock_provider:
            provider = MagicMock()
            provider.available = True
            provider.send_text = AsyncMock(side_effect=RuntimeError("boom"))
            mock_provider.return_value = provider

            outcome = await _run_tool_step(
                MagicMock(), task_id="task-boom", tool_name="whatsapp.send_message",
                params_json=json.dumps({"recipient": "+40712345678", "body": "x", "confirmation_phrase": "CONFIRM"}),
                company_id=1, user_id=1, role="manager",
                conversation_id="conv-1", plan_id="plan-1", step_id="step-1",
            )
        # The whatsapp tool swallows provider exceptions into a per-recipient
        # failure ToolResult (never raises) → the step fails with the i18n key.
        assert outcome["status"] == "failed"
        assert outcome["error"] == "copilot.tool.whatsapp.send_failed"


# ═══════════════════════════════════════════════════════════════════════════
# _execute_step_sync (the task body)
# ═══════════════════════════════════════════════════════════════════════════

class TestExecuteStepSync:
    def _run_sync(self, _fake_cache, **overrides):
        from backend.celery_app.tasks.copilot_tool_tasks import _execute_step_sync

        args = {
            "task_id": "task-sync",
            "tool_name": "whatsapp.send_message",
            "params_json": json.dumps({"recipient": "+40712345678", "body": "Hi", "confirmation_phrase": "CONFIRM"}),
            "company_id": 1,
            "user_id": 1,
            "role": "manager",
            "conversation_id": "conv-1",
            "plan_id": "plan-1",
            "step_id": "step-1",
        }
        args.update(overrides)
        return _execute_step_sync(**args)

    def test_task_writes_audit_and_notification(self, _fake_cache):
        fake_db = MagicMock()
        fake_db.close = MagicMock()

        with (
            patch("backend.db.DatabaseManager", return_value=fake_db),
            patch("backend.celery_app.tasks.copilot_tool_tasks._write_audit_terminal") as mock_audit,
            patch("backend.celery_app.tasks.copilot_tool_tasks._fire_completion_notification") as mock_notify,
            patch("backend.copilot.channels.whatsapp.registry.get_whatsapp_provider") as mock_provider,
        ):
            provider = MagicMock()
            provider.available = True
            provider.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.x"}]})
            mock_provider.return_value = provider

            outcome = self._run_sync(_fake_cache)

        assert outcome["status"] == "succeeded"
        mock_audit.assert_called_once()
        _, kwargs = mock_audit.call_args
        assert kwargs["status"] == "succeeded"
        assert kwargs["step_id"] == "step-1"
        assert kwargs["tool_name"] == "whatsapp.send_message"
        mock_notify.assert_called_once()
        assert mock_notify.call_args[1]["status"] == "succeeded"
        fake_db.close.assert_called_once()

    def test_task_returns_failed_without_raising(self, _fake_cache):
        fake_db = MagicMock()
        with (
            patch("backend.db.DatabaseManager", return_value=fake_db),
            patch("backend.celery_app.tasks.copilot_tool_tasks._write_audit_terminal"),
            patch("backend.celery_app.tasks.copilot_tool_tasks._fire_completion_notification"),
        ):
            outcome = self._run_sync(_fake_cache, tool_name="no.such.tool")
        assert outcome["status"] == "failed"


# ═══════════════════════════════════════════════════════════════════════════
# Completion notification + audit terminal
# ═══════════════════════════════════════════════════════════════════════════

class TestCompletionNotification:
    def test_fire_completion_notification_creates_alert(self):
        from backend.celery_app.tasks.copilot_tool_tasks import _fire_completion_notification

        fake_alert_mgr = MagicMock()
        with patch("services.operations.alert_manager.AlertManager.get_instance", return_value=fake_alert_mgr):
            _fire_completion_notification(
                MagicMock(), company_id=1, user_id=1, tool_name="freight.search_loads",
                status="succeeded", step_id="step-1", plan_id="plan-1", conversation_id="conv-1",
            )
        fake_alert_mgr.create_alert.assert_called_once()
        _, kwargs = fake_alert_mgr.create_alert.call_args
        assert kwargs["alert_type"].value == "copilot_tool_completed"
        assert kwargs["severity"].value == "info"
        assert kwargs["metadata"]["tool_name"] == "freight.search_loads"
        assert kwargs["metadata"]["step_id"] == "step-1"

    def test_fire_completion_notification_failed_status(self):
        from backend.celery_app.tasks.copilot_tool_tasks import _fire_completion_notification

        fake_alert_mgr = MagicMock()
        with patch("services.operations.alert_manager.AlertManager.get_instance", return_value=fake_alert_mgr):
            _fire_completion_notification(
                MagicMock(), company_id=1, user_id=1, tool_name="freight.search_loads",
                status="failed", step_id="step-1", plan_id="plan-1", conversation_id="conv-1",
            )
        assert fake_alert_mgr.create_alert.call_args[1]["severity"].value == "warning"

    def test_write_audit_terminal(self):
        from backend.celery_app.tasks.copilot_tool_tasks import _write_audit_terminal

        fake_repo = MagicMock()
        with patch("repositories.copilot_repository.CopilotAuditRepository", return_value=fake_repo):
            _write_audit_terminal(
                MagicMock(), company_id=1, user_id=1, conversation_id="conv-1",
                plan_id="plan-1", step_id="step-1", tool_name="freight.search_loads",
                tool_version="1.0.0", parameters={"origin": "Bucharest"},
                status="succeeded", result={"status": "success"}, error=None,
            )
        fake_repo.log_step_execution.assert_called_once()
        _, kwargs = fake_repo.log_step_execution.call_args
        assert kwargs["status"] == "succeeded"
        assert kwargs["step_id"] == "step-1"
        assert kwargs["conversation_id"] == "conv-1"