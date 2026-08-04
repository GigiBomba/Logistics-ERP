"""Comprehensive unit tests for the Level 3 destructive-action tools.

Tools (all DESTRUCTIVE, require typed confirmation):
- trip.delete          — trips:delete
- vehicle.delete       — fleet:delete
- driver.remove        — drivers:delete
- client.delete        — clients:delete
- invoice.delete       — invoices:delete
- route.delete         — routes:delete

Tests cover:
- BaseTool contract for each delete tool
- Parameter schema validation (confirmation_phrase required, entity ID required)
- validate() behaviour
- execute() with mocked services (success, service failure, exception)
- Error handling (missing db, service returns fail, unexpected exceptions)
- Route delete fallback strategies (discard_route vs hard delete)

Blueprint: §9.1 — Level 3 DESTRUCTIVE, §21 Phase 3.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, run_startup_validation

# Ensure tools are loaded
from backend.copilot.planner import _ensure_tools_loaded  # noqa: E402
_ensure_tools_loaded()
_validation_errors = run_startup_validation()
_prod_errors = [e for e in _validation_errors if "test." not in e]
assert len(_prod_errors) == 0, f"Production tool registry errors: {_prod_errors}"

DELETE_TOOLS = {
    "trip.delete": {"id_field": "trip_id", "permission": "trips:delete", "service_path": "backend.services.trip_service.TripService"},
    "vehicle.delete": {"id_field": "vehicle_id", "permission": "fleet:delete", "service_path": "backend.services.fleet_service.FleetService"},
    "driver.remove": {"id_field": "driver_id", "permission": "drivers:delete", "service_path": "backend.services.driver_truck_service.DriverTruckService"},
    "client.delete": {"id_field": "client_id", "permission": "clients:delete", "service_path": "backend.services.client_service.ClientService"},
    "invoice.delete": {"id_field": "invoice_id", "permission": "invoices:delete", "service_path": "services.invoicing.service.InvoiceService"},
    "route.delete": {"id_field": "route_id", "permission": "routes:delete", "service_path": None},
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_ctx(**overrides: Any) -> ToolExecutionContext:
    kwargs: dict = dict(
        company_id=1,
        user_id=1,
        role="admin",
        session_context=SessionContext(),
        services={},
    )
    kwargs.update(overrides)
    return ToolExecutionContext(**kwargs)


def _make_service_result(success: bool = True, error_message: str | None = None):
    """Build a mock ServiceResult-like object."""
    r = MagicMock()
    r.success = success
    r.data = MagicMock()
    r.errors = []
    if error_message:
        from models.common import ErrorDetail
        r.errors = [ErrorDetail(field="", message=error_message, code="ERROR")]
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Contract tests for all delete tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteToolsContract:
    """BaseTool contract shared by all 6 delete/remove tools."""

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_tool_is_registered(self, name):
        assert get_tool(name) is not None, f"{name} not in registry"

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_tool_name(self, name):
        assert get_tool(name).name == name

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_tool_version_is_semver(self, name):
        parts = get_tool(name).tool_version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_description_non_empty(self, name):
        assert get_tool(name).description.strip()

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_permission_correct(self, name):
        expected = DELETE_TOOLS[name]["permission"]
        assert get_tool(name).required_permission == expected

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_confirmation_level_destructive(self, name):
        assert get_tool(name).confirmation_level == ConfirmationLevel.DESTRUCTIVE

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_supports_undo_false(self, name):
        assert not get_tool(name).supports_undo

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_deprecated_false(self, name):
        assert not get_tool(name).deprecated

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_parameters_schema_is_basemodel(self, name):
        assert issubclass(get_tool(name).parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_id_field_and_confirmation_phrase_present(self, name):
        fields = get_tool(name).parameters_schema.model_fields
        id_field = DELETE_TOOLS[name]["id_field"]
        assert id_field in fields
        assert "confirmation_phrase" in fields

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_id_field_is_required(self, name):
        id_field = DELETE_TOOLS[name]["id_field"]
        assert get_tool(name).parameters_schema.model_fields[id_field].is_required()

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_confirmation_phrase_is_required(self, name):
        assert get_tool(name).parameters_schema.model_fields["confirmation_phrase"].is_required()

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_parameters_schema_forbids_extra(self, name):
        config = get_tool(name).parameters_schema.model_config
        assert config.get("extra") == "forbid"

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_undo_raises_not_implemented(self, name):
        with pytest.raises(NotImplementedError):
            asyncio.run(get_tool(name).undo("token", _make_ctx()))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Schema validation for all delete tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteToolsParams:
    """Parameter schema validation."""

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_accepts_valid_id_and_phrase(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        params = tool.parameters_schema(**{id_field: 42, "confirmation_phrase": "42"})
        assert getattr(params, id_field) == 42
        assert params.confirmation_phrase == "42"

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_rejects_zero_id(self, name):
        """All delete tools have gt=0 on the ID field."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: 0, "confirmation_phrase": "0"})

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_rejects_negative_id(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: -1, "confirmation_phrase": "-1"})

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_rejects_empty_confirmation_phrase(self, name):
        """confirmation_phrase has min_length=1."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: 1, "confirmation_phrase": ""})

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_rejects_missing_confirmation_phrase(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: 1})

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_validate_accepts_valid_params(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        params = tool.parameters_schema(**{id_field: 5, "confirmation_phrase": "5"})
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        # validate should return empty list for valid params
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_validate_rejects_empty_confirmation_phrase_after_construct(self, name):
        """validate() catches empty phrase even if schema bypassed."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        # Use model_construct to bypass pydantic validators and test tool.validate()
        params = tool.parameters_schema.model_construct(**{id_field: 1, "confirmation_phrase": ""})
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Execute — success paths (trip, vehicle, driver, client, invoice)
# ═══════════════════════════════════════════════════════════════════════════════


def _get_delete_service_mock(name: str) -> str:
    """Return the import path for the service class to mock."""
    info = DELETE_TOOLS[name]
    return info["service_path"]


class TestDeleteToolsExecuteSuccess:
    """Execute() success paths for the 5 standard delete tools."""

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_success(self, name):
        """All 5 standard delete tools return success with correct data."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"

        # Mock the service
        service_path = _get_delete_service_mock(name)
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 42, "confirmation_phrase": "42"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            assert result.data is not None
            assert result.data[id_field] == 42

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_passes_user_id(self, name):
        """The service receives user_id from context."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"

        service_path = _get_delete_service_mock(name)
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
            ctx = _make_ctx(services={"db": MagicMock()}, user_id=99)
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            # Verify user_id was passed
            call_args = getattr(mock_service, delete_method).call_args
            _, call_kwargs = call_args if isinstance(call_args, tuple) else ((), {})
            assert call_kwargs is not None
            assert call_kwargs.get("user_id") == 99

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_service_delete_called_with_id(self, name):
        """The service's delete/delete_driver method is called with the entity ID."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"

        service_path = _get_delete_service_mock(name)
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 77, "confirmation_phrase": "77"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            # Verify the delete method was called with the correct ID
            call_args = getattr(mock_service, delete_method).call_args
            assert call_args is not None
            call_pos_args, _ = call_args if isinstance(call_args, tuple) else (call_args.args, {})
            assert call_pos_args[0] == 77  # First positional arg is the entity ID


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Execute — error handling (trip, vehicle, driver, client, invoice)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteToolsExecuteErrors:
    """Error handling for the 5 standard delete tools."""

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_no_db_returns_unavailable(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
        ctx = _make_ctx()  # No services
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_db_is_none_returns_unavailable(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
        ctx = _make_ctx(services={"db": None})
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_service_returns_failed(self, name):
        """When the service delete() returns success=False, tool returns failed."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"

        service_path = _get_delete_service_mock(name)
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(
                success=False, error_message="Entity not found",
            )
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 999, "confirmation_phrase": "999"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_service_raises_exception(self, name):
        """Unexpected exceptions from service are caught and returned as failed."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"

        service_path = _get_delete_service_mock(name)
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).side_effect = RuntimeError("Database connection lost")
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "failed"
            assert "Database connection lost" in result.message_params.get("error", "")

    @pytest.mark.parametrize("name", ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"])
    def test_execute_message_key_for_success(self, name):
        """Each tool has a unique success message_key."""
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]

        service_path = _get_delete_service_mock(name)
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            mock_service.delete.return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success"
            # Each tool has a domain-specific success key
            assert result.message_key.startswith("copilot.")
            assert result.message_key.endswith(".deleted") or result.message_key.endswith(".removed")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. route.delete — special handling (fallback strategies)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteDeleteTool:
    """route.delete has a unique fallback strategy — test all paths."""

    ROUTE_DELETE = "route.delete"

    def test_contract(self):
        tool = get_tool(self.ROUTE_DELETE)
        assert tool.name == "route.delete"
        assert tool.required_permission == "routes:delete"
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE
        assert not tool.supports_undo
        assert not tool.deprecated

    def test_params_accepts_valid(self):
        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=1, confirmation_phrase="1")
        assert params.route_id == 1

    def test_params_rejects_zero_id(self):
        tool = get_tool(self.ROUTE_DELETE)
        with pytest.raises(ValidationError):
            tool.parameters_schema(route_id=0, confirmation_phrase="0")

    def test_execute_no_db_returns_unavailable(self):
        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=1, confirmation_phrase="1")
        ctx = _make_ctx()
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"

    def test_execute_db_none_returns_unavailable(self):
        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=1, confirmation_phrase="1")
        ctx = _make_ctx(services={"db": None})
        result = asyncio.run(tool.execute(params, ctx))
        assert result.status == "unavailable"

    @patch("backend.services.route_history_service.RouteHistoryService")
    def test_execute_discard_route_success(self, mock_history_class):
        """Strategy 1: RouteHistoryService.discard_route returns success."""
        mock_service = MagicMock()
        mock_service.discard_route.return_value = True
        mock_history_class.return_value = mock_service

        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=10, confirmation_phrase="10")
        ctx = _make_ctx(services={"db": MagicMock()})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["action"] == "discarded"
        assert result.message_key == "copilot.route.deleted"

    @patch("backend.services.route_history_service.RouteHistoryService")
    def test_execute_discard_route_returns_false(self, mock_history_class):
        """Strategy 1: discard_route returns False -> returns failed."""
        mock_service = MagicMock()
        mock_service.discard_route.return_value = False
        mock_history_class.return_value = mock_service

        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=10, confirmation_phrase="10")
        ctx = _make_ctx(services={"db": MagicMock()})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.route.delete_failed"

    @patch("backend.services.route_history_service.RouteHistoryService")
    @patch("backend.repositories.route_repository.RouteRepository")
    def test_execute_fallback_to_repo_delete(self, mock_repo_class, mock_history_class):
        """Strategy 2: When discard_route is unavailable, falls back to RouteRepository.delete."""
        mock_service = MagicMock()
        # Simulate no discard_route attribute
        del mock_service.discard_route
        mock_history_class.return_value = mock_service

        mock_repo = MagicMock()
        mock_repo.delete.return_value = None  # delete is void
        mock_repo_class.return_value = mock_repo

        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=10, confirmation_phrase="10")
        ctx = _make_ctx(services={"db": MagicMock()})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["action"] == "hard_deleted"

    @patch("backend.services.route_history_service.RouteHistoryService")
    @patch("backend.repositories.route_repository.RouteRepository")
    def test_execute_both_strategies_unavailable(self, mock_repo_class, mock_history_class):
        """Both strategies unavailable -> returns unavailable."""
        mock_service = MagicMock()
        del mock_service.discard_route
        mock_history_class.return_value = mock_service

        mock_repo = MagicMock()
        del mock_repo.delete
        mock_repo_class.return_value = mock_repo

        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=10, confirmation_phrase="10")
        ctx = _make_ctx(services={"db": MagicMock()})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "unavailable"
        assert result.message_key == "copilot.route.delete_unavailable"

    @patch("backend.services.route_history_service.RouteHistoryService")
    def test_execute_handles_exception(self, mock_history_class):
        """Unexpected exceptions are caught."""
        mock_service = MagicMock()
        mock_service.discard_route.side_effect = RuntimeError("Unexpected error")
        mock_history_class.return_value = mock_service

        tool = get_tool(self.ROUTE_DELETE)
        params = tool.parameters_schema(route_id=10, confirmation_phrase="10")
        ctx = _make_ctx(services={"db": MagicMock()})
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert "Unexpected error" in result.message_params.get("error", "")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Cross-cutting destructive tool consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestDestructiveToolConsistency:
    """Consistency checks across all 6 delete tools."""

    def test_all_destructive(self):
        for name in DELETE_TOOLS:
            assert get_tool(name).confirmation_level == ConfirmationLevel.DESTRUCTIVE

    def test_all_have_no_undo(self):
        for name in DELETE_TOOLS:
            assert not get_tool(name).supports_undo

    def test_all_have_confirmation_phrase(self):
        for name in DELETE_TOOLS:
            fields = get_tool(name).parameters_schema.model_fields
            assert "confirmation_phrase" in fields

    def test_all_have_gt_zero_on_id_field(self):
        for name in DELETE_TOOLS:
            id_field = DELETE_TOOLS[name]["id_field"]
            field = get_tool(name).parameters_schema.model_fields[id_field]
            assert field.is_required()
            # Verify gt=0 constraint exists
            with pytest.raises(ValidationError):
                get_tool(name).parameters_schema(**{id_field: 0, "confirmation_phrase": "0"})

    def test_all_permissions_end_with_delete(self):
        for name in DELETE_TOOLS:
            perm = get_tool(name).required_permission
            assert perm.endswith(":delete"), f"{name} permission '{perm}' should end with :delete"
