"""Comprehensive unit tests for automail.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for all 3 automail tools
- Tool execution with mocked NotificationCenter / AutoMailRepository
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, no DB, exceptions)

Blueprint: §9 — Registry enforcement.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, run_startup_validation


# ── Module-level setup ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def _ensure_registry():
    run_startup_validation()
    yield


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    return ToolExecutionContext(
        company_id=1,
        user_id=42,
        role="dispatcher",
        session_context=SessionContext(),
        services={},
    )


@pytest.fixture
def ctx_with_db():
    return ToolExecutionContext(
        company_id=1,
        user_id=42,
        role="dispatcher",
        session_context=SessionContext(),
        services={"db": MagicMock()},
    )


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — all automail tools
# ═══════════════════════════════════════════════════════════════════════════

AUTOMAIL_TOOL_NAMES = [
    "automail.schedule_reminder",
    "automail.send_now",
    "email.send_bulk",
]


class TestAutomailToolContract:
    """Every automail/email tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()

    def test_schedule_reminder_permission(self):
        tool = get_tool("automail.schedule_reminder")
        assert tool.required_permission == "automail:write"

    def test_send_now_permission(self):
        tool = get_tool("automail.send_now")
        assert tool.required_permission == "automail:send"

    def test_send_bulk_permission(self):
        tool = get_tool("email.send_bulk")
        assert tool.required_permission == "email:send_bulk"

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    def test_schedule_reminder_confirmation_level(self):
        tool = get_tool("automail.schedule_reminder")
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    def test_send_now_confirmation_level(self):
        tool = get_tool("automail.send_now")
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE

    def test_send_bulk_confirmation_level(self):
        tool = get_tool("email.send_bulk")
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_tool_supports_undo_correct(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        if name == "automail.schedule_reminder":
            params = tool.parameters_schema(invoice_id=1)
        elif name == "automail.send_now":
            params = tool.parameters_schema(invoice_id=1, recipient_email="test@example.com")
        elif name == "email.send_bulk":
            params = tool.parameters_schema(
                recipients=["a@b.com", "c@d.com"], subject="Hello", body="World"
            )
        else:
            params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", AUTOMAIL_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        if name == "automail.schedule_reminder":
            params = tool.parameters_schema(invoice_id=1)
        elif name == "automail.send_now":
            params = tool.parameters_schema(invoice_id=1, recipient_email="test@example.com")
        elif name == "email.send_bulk":
            params = tool.parameters_schema(
                recipients=["a@b.com"], subject="Hello", body="World"
            )
        else:
            params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════


class TestScheduleReminderParams:
    """automail.schedule_reminder parameter schema edge cases."""

    def test_accepts_minimal_params(self):
        tool = get_tool("automail.schedule_reminder")
        params = tool.parameters_schema(invoice_id=1)
        assert params.invoice_id == 1
        assert params.reminder_type == "overdue"
        assert params.template == "standard"
        assert params.send_immediately is False

    def test_accepts_all_params(self):
        tool = get_tool("automail.schedule_reminder")
        params = tool.parameters_schema(
            invoice_id=42,
            reminder_type="due_soon",
            template="custom",
            send_immediately=True,
        )
        assert params.invoice_id == 42
        assert params.reminder_type == "due_soon"
        assert params.template == "custom"
        assert params.send_immediately is True

    def test_rejects_invoice_id_zero(self):
        tool = get_tool("automail.schedule_reminder")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=0)

    def test_rejects_invoice_id_negative(self):
        tool = get_tool("automail.schedule_reminder")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=-1)

    def test_rejects_extra_fields(self):
        tool = get_tool("automail.schedule_reminder")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=1, extra_field="x")

    def test_validate_rejects_invalid_reminder_type(self, ctx):
        tool = get_tool("automail.schedule_reminder")
        params = tool.parameters_schema(invoice_id=1, reminder_type="bogus")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("bogus" in e for e in errors)

    def test_validate_accepts_valid_reminder_types(self, ctx):
        tool = get_tool("automail.schedule_reminder")
        for rtype in ("overdue", "due_soon"):
            params = tool.parameters_schema(invoice_id=1, reminder_type=rtype)
            errors = asyncio.run(tool.validate(params, ctx))
            assert len(errors) == 0


class TestSendNowParams:
    """automail.send_now parameter schema edge cases."""

    def test_accepts_minimal_params(self):
        tool = get_tool("automail.send_now")
        params = tool.parameters_schema(invoice_id=1, recipient_email="user@example.com")
        assert params.invoice_id == 1
        assert params.recipient_email == "user@example.com"
        assert params.subject == ""
        assert params.body == ""

    def test_accepts_full_params(self):
        tool = get_tool("automail.send_now")
        params = tool.parameters_schema(
            invoice_id=5,
            recipient_email="user@example.com",
            subject="Reminder",
            body="Please pay",
        )
        assert params.subject == "Reminder"
        assert params.body == "Please pay"

    def test_rejects_invoice_id_zero(self):
        tool = get_tool("automail.send_now")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=0, recipient_email="a@b.com")

    def test_rejects_empty_email(self):
        tool = get_tool("automail.send_now")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=1, recipient_email="")

    def test_rejects_extra_fields(self):
        tool = get_tool("automail.send_now")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=1, recipient_email="a@b.com", extra="x")

    def test_validate_rejects_invalid_email(self, ctx):
        tool = get_tool("automail.send_now")
        params = tool.parameters_schema(invoice_id=1, recipient_email="not-an-email")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("email" in e.lower() for e in errors)

    def test_validate_accepts_valid_email(self, ctx):
        tool = get_tool("automail.send_now")
        params = tool.parameters_schema(invoice_id=1, recipient_email="user@example.com")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


class TestSendBulkParams:
    """email.send_bulk parameter schema edge cases."""

    def test_accepts_minimal_params(self):
        tool = get_tool("email.send_bulk")
        params = tool.parameters_schema(
            recipients=["a@b.com"], subject="Hello", body="World"
        )
        assert params.recipients == ["a@b.com"]
        assert params.subject == "Hello"
        assert params.body == "World"
        assert params.trip_id is None

    def test_accepts_multiple_recipients(self):
        tool = get_tool("email.send_bulk")
        recipients = ["a@b.com", "c@d.com", "e@f.com"]
        params = tool.parameters_schema(
            recipients=recipients, subject="S", body="B", trip_id=42
        )
        assert params.recipients == recipients
        assert params.trip_id == 42

    def test_rejects_empty_recipients(self):
        tool = get_tool("email.send_bulk")
        with pytest.raises(ValidationError):
            tool.parameters_schema(recipients=[], subject="S", body="B")

    def test_rejects_too_many_recipients(self):
        tool = get_tool("email.send_bulk")
        with pytest.raises(ValidationError):
            tool.parameters_schema(
                recipients=["a@b.com"] * 101, subject="S", body="B"
            )

    def test_rejects_empty_subject(self):
        tool = get_tool("email.send_bulk")
        with pytest.raises(ValidationError):
            tool.parameters_schema(recipients=["a@b.com"], subject="", body="B")

    def test_rejects_empty_body(self):
        tool = get_tool("email.send_bulk")
        with pytest.raises(ValidationError):
            tool.parameters_schema(recipients=["a@b.com"], subject="S", body="")

    def test_rejects_extra_fields(self):
        tool = get_tool("email.send_bulk")
        with pytest.raises(ValidationError):
            tool.parameters_schema(
                recipients=["a@b.com"], subject="S", body="B", extra="x"
            )

    def test_validate_rejects_invalid_emails(self, ctx):
        tool = get_tool("email.send_bulk")
        params = tool.parameters_schema(
            recipients=["valid@a.com", "bad-email", "also@bad"],
            subject="S", body="B",
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("bad-email" in e for e in errors)

    def test_validate_accepts_all_valid_emails(self, ctx):
        tool = get_tool("email.send_bulk")
        params = tool.parameters_schema(
            recipients=["a@b.com", "c@d.com"],
            subject="S", body="B",
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — mocked services
#  execute() imports are inside function body, so we patch at source.
# ═══════════════════════════════════════════════════════════════════════════


class TestScheduleReminderExecution:
    """automail.schedule_reminder execute() with mocked services."""

    @patch("repositories.automail_repository.AutoMailRepository")
    def test_execute_schedule_only(self, MockRepo, ctx_with_db):
        """Schedule a reminder without immediate send."""
        tool = get_tool("automail.schedule_reminder")

        mock_repo = MagicMock()
        mock_repo.get_all_templates.return_value = [
            {"id": 1, "name": "standard"},
            {"id": 2, "name": "custom"},
        ]
        mock_repo.create_schedule.return_value = 100
        MockRepo.return_value = mock_repo

        params = tool.parameters_schema(invoice_id=42, reminder_type="due_soon")
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["schedule_id"] == 100
        assert result.data["invoice_id"] == 42
        assert result.data["reminder_type"] == "due_soon"
        assert result.data["sent_immediately"] is False
        assert result.message_key == "copilot.automail.schedule_created"
        mock_repo.create_schedule.assert_called_once()

    @patch("repositories.automail_repository.AutoMailRepository")
    def test_execute_schedule_with_template_resolved(self, MockRepo, ctx_with_db):
        """Template name is resolved to template_id."""
        tool = get_tool("automail.schedule_reminder")

        mock_repo = MagicMock()
        mock_repo.get_all_templates.return_value = [
            {"id": 1, "name": "standard"},
            {"id": 5, "name": "custom_template"},
        ]
        mock_repo.create_schedule.return_value = 200
        MockRepo.return_value = mock_repo

        params = tool.parameters_schema(
            invoice_id=10, template="custom_template"
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        call_kwargs = mock_repo.create_schedule.call_args[0][0]
        assert call_kwargs["template_id"] == 5

    @patch("repositories.automail_repository.AutoMailRepository")
    def test_execute_without_template_match(self, MockRepo, ctx_with_db):
        """When template name is not found, no template_id is set."""
        tool = get_tool("automail.schedule_reminder")

        mock_repo = MagicMock()
        mock_repo.get_all_templates.return_value = [
            {"id": 1, "name": "standard"},
        ]
        mock_repo.create_schedule.return_value = 300
        MockRepo.return_value = mock_repo

        params = tool.parameters_schema(
            invoice_id=10, template="nonexistent_template"
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        call_kwargs = mock_repo.create_schedule.call_args[0][0]
        assert "template_id" not in call_kwargs

    @patch("services.operations.notification_center.NotificationCenter")
    @patch("repositories.invoice_repository.InvoiceRepository")
    @patch("repositories.client_repository.ClientRepository")
    @patch("repositories.automail_repository.AutoMailRepository")
    def test_execute_send_immediately(
        self, MockRepo, MockClientRepo, MockInvoiceRepo, MockNC, ctx_with_db
    ):
        """send_immediately=True sends the email right away."""
        tool = get_tool("automail.schedule_reminder")

        mock_repo = MagicMock()
        mock_repo.get_all_templates.return_value = []
        mock_repo.create_schedule.return_value = 400
        MockRepo.return_value = mock_repo

        # Mock invoice lookup
        mock_inv_repo = MagicMock()
        mock_inv_repo.get_by_id.return_value = {"client_id": "7"}
        MockInvoiceRepo.return_value = mock_inv_repo

        # Mock client lookup
        mock_client_repo = MagicMock()
        mock_client_repo.get_by_id.return_value = {"email": "client@example.com"}
        MockClientRepo.return_value = mock_client_repo

        # Mock notification center
        mock_nc = MagicMock()
        mock_nc.send_email.return_value = True
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            invoice_id=1, reminder_type="overdue", send_immediately=True
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.data["sent_immediately"] is True
        mock_nc.send_email.assert_called_once()
        mock_repo.log_manual_send.assert_called_once()

    def test_execute_no_db(self, ctx):
        """Without db, returns unavailable."""
        tool = get_tool("automail.schedule_reminder")
        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    @patch("repositories.automail_repository.AutoMailRepository")
    def test_execute_exception(self, MockRepo, ctx_with_db):
        """Service exception is caught and returned as failed."""
        tool = get_tool("automail.schedule_reminder")
        mock_repo = MagicMock()
        mock_repo.get_all_templates.side_effect = RuntimeError("DB error")
        MockRepo.return_value = mock_repo

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.unexpected"


class TestSendNowExecution:
    """automail.send_now execute() with mocked NotificationCenter."""

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_success(self, MockNC, ctx_with_db):
        """Successful immediate send."""
        tool = get_tool("automail.send_now")

        mock_nc = MagicMock()
        mock_nc.send_email.return_value = True
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            invoice_id=1, recipient_email="user@example.com",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        assert result.message_key == "copilot.automail.sent"
        mock_nc.send_email.assert_called_once_with(
            to_address="user@example.com",
            subject="Reminder: Invoice #1",
            body="Please process invoice #1.",
            trip_id=1,
        )

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_with_custom_subject_body(self, MockNC, ctx_with_db):
        """Custom subject and body are used when provided."""
        tool = get_tool("automail.send_now")

        mock_nc = MagicMock()
        mock_nc.send_email.return_value = True
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            invoice_id=2,
            recipient_email="user@example.com",
            subject="Custom Subject",
            body="Custom Body",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "success"
        mock_nc.send_email.assert_called_once_with(
            to_address="user@example.com",
            subject="Custom Subject",
            body="Custom Body",
            trip_id=2,
        )

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_send_failed(self, MockNC, ctx_with_db):
        """When send_email returns False, returns failed."""
        tool = get_tool("automail.send_now")

        mock_nc = MagicMock()
        mock_nc.send_email.return_value = False
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            invoice_id=1, recipient_email="user@example.com",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.automail.send_failed"

    def test_execute_no_db(self, ctx):
        """Without db, returns unavailable."""
        tool = get_tool("automail.send_now")
        params = tool.parameters_schema(
            invoice_id=1, recipient_email="user@example.com",
        )
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_exception(self, MockNC, ctx_with_db):
        """Exception is caught and returned as failed."""
        tool = get_tool("automail.send_now")

        mock_nc = MagicMock()
        mock_nc.send_email.side_effect = RuntimeError("SMTP error")
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            invoice_id=1, recipient_email="user@example.com",
        )
        result = asyncio.run(tool.execute(params, ctx_with_db))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.unexpected"


class TestSendBulkExecution:
    """email.send_bulk execute() with mocked NotificationCenter."""

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_all_success(self, MockNC, ctx):
        """All recipients receive the email successfully."""
        tool = get_tool("email.send_bulk")

        mock_nc = MagicMock()
        mock_nc.send_email.return_value = True
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            recipients=["a@b.com", "c@d.com"],
            subject="Hello",
            body="World",
            trip_id=42,
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["sent_count"] == 2
        assert result.data["failed_count"] == 0
        assert result.message_key == "copilot.email.bulk_sent"
        assert mock_nc.send_email.call_count == 2

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_partial_failure(self, MockNC, ctx):
        """Some recipients fail — result still succeeds but reports failures."""
        tool = get_tool("email.send_bulk")

        mock_nc = MagicMock()
        # First succeeds, second fails (returns False), third raises
        mock_nc.send_email.side_effect = [True, False, RuntimeError("fail")]
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            recipients=["a@b.com", "c@d.com", "e@f.com"],
            subject="S", body="B",
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["sent_count"] == 1
        assert result.data["failed_count"] == 2

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_all_fail(self, MockNC, ctx):
        """All recipients fail — returns failed."""
        tool = get_tool("email.send_bulk")

        mock_nc = MagicMock()
        mock_nc.send_email.return_value = False
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            recipients=["a@b.com"], subject="S", body="B",
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.email.bulk_failed"

    @patch("services.operations.notification_center.NotificationCenter")
    def test_execute_exception(self, MockNC, ctx):
        """Top-level exception is caught."""
        tool = get_tool("email.send_bulk")

        mock_nc = MagicMock()
        mock_nc.send_email.side_effect = RuntimeError("Total failure")
        MockNC.return_value = mock_nc

        params = tool.parameters_schema(
            recipients=["a@b.com"], subject="S", body="B",
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.unexpected"
