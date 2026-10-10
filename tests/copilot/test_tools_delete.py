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
    """BaseTool contract shared by all 6 delete/remove tools.

    One parametrized test with all 14 contract assertions in a single body —
    previously 14 separate per-tool tests (14 × 6 = 84 cases).
    """

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_tool_contract(self, name):
        tool = get_tool(name)
        assert tool is not None, f"{name} not in registry"
        assert tool.name == name, f"{name}: tool.name mismatch"
        parts = tool.tool_version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), (
            f"{name}: tool_version is not semver: {tool.tool_version!r}"
        )
        assert tool.description.strip(), f"{name}: description is empty"
        assert tool.required_permission == DELETE_TOOLS[name]["permission"], (
            f"{name}: required_permission mismatch"
        )
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE, (
            f"{name}: must be DESTRUCTIVE"
        )
        assert not tool.supports_undo, f"{name}: must not support undo"
        assert not tool.deprecated, f"{name}: must not be deprecated"
        assert issubclass(tool.parameters_schema, BaseModel), (
            f"{name}: parameters_schema must be a BaseModel"
        )
        fields = tool.parameters_schema.model_fields
        id_field = DELETE_TOOLS[name]["id_field"]
        assert id_field in fields, f"{name}: missing id field {id_field!r}"
        assert "confirmation_phrase" in fields, f"{name}: missing confirmation_phrase"
        assert fields[id_field].is_required(), f"{name}: {id_field} must be required"
        assert fields["confirmation_phrase"].is_required(), (
            f"{name}: confirmation_phrase must be required"
        )
        config = tool.parameters_schema.model_config
        assert config.get("extra") == "forbid", f"{name}: extra fields must be forbidden"
        with pytest.raises(NotImplementedError):
            asyncio.run(tool.undo("token", _make_ctx()))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Schema validation for all delete tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteToolsParams:
    """Parameter schema validation for all 6 delete/remove tools.

    One parametrized test with all 7 validation assertions in a single body —
    previously 7 separate per-tool tests (7 × 6 = 42 cases).
    """

    @pytest.mark.parametrize("name", sorted(DELETE_TOOLS))
    def test_params_validation(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]

        # Valid id + confirmation phrase are accepted.
        params = tool.parameters_schema(**{id_field: 42, "confirmation_phrase": "42"})
        assert getattr(params, id_field) == 42, f"{name}: valid id not accepted"
        assert params.confirmation_phrase == "42", f"{name}: phrase not accepted"

        # The ID field has gt=0: zero and negative ids are rejected.
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: 0, "confirmation_phrase": "0"})
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: -1, "confirmation_phrase": "-1"})

        # confirmation_phrase has min_length=1 and is required.
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: 1, "confirmation_phrase": ""})
        with pytest.raises(ValidationError):
            tool.parameters_schema(**{id_field: 1})

        # validate() accepts valid params (returns a list).
        params = tool.parameters_schema(**{id_field: 5, "confirmation_phrase": "5"})
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert isinstance(errors, list), f"{name}: validate() must return a list"

        # validate() catches an empty phrase even if the schema was bypassed.
        params = tool.parameters_schema.model_construct(**{id_field: 1, "confirmation_phrase": ""})
        errors = asyncio.run(tool.validate(params, _make_ctx()))
        assert len(errors) > 0, f"{name}: validate() must reject empty confirmation_phrase"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Execute — success paths (trip, vehicle, driver, client, invoice)
# ═══════════════════════════════════════════════════════════════════════════════


def _get_delete_service_mock(name: str) -> str:
    """Return the import path for the service class to mock."""
    info = DELETE_TOOLS[name]
    return info["service_path"]


class TestDeleteToolsExecuteSuccess:
    """Execute() success paths for the 5 standard delete tools.

    One parametrized test with the 3 success sub-scenarios as sequential
    blocks — previously 3 separate per-tool tests (3 × 5 = 15 cases).
    """

    _EXECUTE_TOOLS = ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"]

    @pytest.mark.parametrize("name", _EXECUTE_TOOLS)
    def test_execute_success_paths(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"
        service_path = _get_delete_service_mock(name)

        # Sub-scenario 1: success result carries the entity id.
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 42, "confirmation_phrase": "42"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success", f"{name}: expected success"
            assert result.data is not None, f"{name}: expected data"
            assert result.data[id_field] == 42, f"{name}: entity id not echoed in result"

        # Sub-scenario 2: the service receives user_id from context.
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
            ctx = _make_ctx(services={"db": MagicMock()}, user_id=99)
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success", f"{name}: expected success"
            call_args = getattr(mock_service, delete_method).call_args
            _, call_kwargs = call_args if isinstance(call_args, tuple) else ((), {})
            assert call_kwargs is not None, f"{name}: service must be called with kwargs"
            assert call_kwargs.get("user_id") == 99, f"{name}: user_id not forwarded"

        # Sub-scenario 3: the delete method is called with the entity id.
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 77, "confirmation_phrase": "77"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))

            assert result.status == "success", f"{name}: expected success"
            call_args = getattr(mock_service, delete_method).call_args
            assert call_args is not None, f"{name}: delete method not called"
            call_pos_args, _ = call_args if isinstance(call_args, tuple) else (call_args.args, {})
            assert call_pos_args[0] == 77, f"{name}: entity id not forwarded as first arg"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Execute — error handling (trip, vehicle, driver, client, invoice)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeleteToolsExecuteErrors:
    """Error handling for the 5 standard delete tools.

    One parametrized test with the 5 error sub-scenarios as sequential
    blocks — previously 5 separate per-tool tests (5 × 5 = 25 cases).
    """

    _EXECUTE_TOOLS = ["trip.delete", "vehicle.delete", "driver.remove", "client.delete", "invoice.delete"]

    @pytest.mark.parametrize("name", _EXECUTE_TOOLS)
    def test_execute_error_paths(self, name):
        tool = get_tool(name)
        id_field = DELETE_TOOLS[name]["id_field"]
        delete_method = "delete_driver" if name == "driver.remove" else "delete"
        service_path = _get_delete_service_mock(name)

        # Sub-scenario 1: no services at all → unavailable.
        params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
        result = asyncio.run(tool.execute(params, _make_ctx()))
        assert result.status == "unavailable", f"{name}: no db → unavailable"

        # Sub-scenario 2: db explicitly None → unavailable.
        params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
        result = asyncio.run(tool.execute(params, _make_ctx(services={"db": None})))
        assert result.status == "unavailable", f"{name}: db=None → unavailable"

        # Sub-scenario 3: service returns success=False → failed.
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(
                success=False, error_message="Entity not found",
            )
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 999, "confirmation_phrase": "999"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))
            assert result.status == "failed", f"{name}: service failure → failed"

        # Sub-scenario 4: service raises → failed with the message surfaced.
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).side_effect = RuntimeError("Database connection lost")
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))
            assert result.status == "failed", f"{name}: exception → failed"
            assert "Database connection lost" in result.message_params.get("error", ""), (
                f"{name}: exception message not surfaced"
            )

        # Sub-scenario 5: success carries a domain-specific message_key.
        with patch(service_path) as mock_service_class:
            mock_service = MagicMock()
            getattr(mock_service, delete_method).return_value = _make_service_result(success=True)
            mock_service_class.return_value = mock_service

            params = tool.parameters_schema(**{id_field: 1, "confirmation_phrase": "1"})
            ctx = _make_ctx(services={"db": MagicMock()})
            result = asyncio.run(tool.execute(params, ctx))
            assert result.status == "success", f"{name}: expected success"
            # Each tool has a domain-specific success key.
            assert result.message_key.startswith("copilot."), f"{name}: message_key prefix"
            assert result.message_key.endswith(".deleted") or result.message_key.endswith(".removed"), (
                f"{name}: message_key suffix"
            )


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
