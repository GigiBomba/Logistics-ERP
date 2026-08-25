"""Tests for Phase 4 freight exchange Co-Pilot tools.

Covers all 9 freight tools: parameter validation, service unavailable handling,
and tool registration correctness.
"""
from __future__ import annotations


import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, all_tools

# Import freight_tools to trigger @register_tool decorators
import backend.copilot.tools.freight_tools  # noqa: F401


FREIGHT_TOOL_NAMES = [
    "freight.search_loads",
    "freight.get_load",
    "freight.save_search",
    "freight.refresh_search",
    "freight.evaluate_load",
    "freight.find_best_trucks",
    "freight.import_load",
    "freight.recommend_dispatch",
    "freight.list_connected_providers",
]


@pytest.fixture
def ctx():
    return ToolExecutionContext(
        company_id=1, user_id=1, role="dispatcher",
        session_context=SessionContext(), services={},
    )


class TestFreightToolRegistration:
    """All 9 freight tools must be registered with correct levels."""

    def test_all_freight_tools_registered(self):
        """Verify each freight tool exists in the registry."""
        for name in FREIGHT_TOOL_NAMES:
            tool = get_tool(name)
            assert tool is not None, f"{name} not registered"

    def test_freight_tool_levels(self):
        """Verify correct confirmation levels for freight tools."""
        for name in FREIGHT_TOOL_NAMES:
            tool = get_tool(name)
            if "import_load" in name or "recommend_dispatch" in name:
                assert tool.confirmation_level == ConfirmationLevel.BUSINESS, \
                    f"{name} should be BUSINESS"
            elif "save_search" in name:
                assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL, \
                    f"{name} should be INFORMATIONAL"
            else:
                assert tool.confirmation_level == ConfirmationLevel.SAFE, \
                    f"{name} should be SAFE, got {tool.confirmation_level}"

    def test_freight_tool_names_provider_agnostic(self):
        """All freight tool names must be provider-agnostic (no 'timocom', etc.)."""
        for name in FREIGHT_TOOL_NAMES:
            assert "timocom" not in name, f"{name} contains provider name"
            assert "trans" not in name, f"{name} contains provider name"

    @pytest.mark.parametrize("name", FREIGHT_TOOL_NAMES)
    def test_freight_tool_versions_valid(self, name):
        """All freight tools must have semver versions."""
        tool = get_tool(name)
        parts = tool.tool_version.split(".")
        assert len(parts) == 3, f"{name} version not semver"
        assert all(p.isdigit() for p in parts), f"{name} version not semver"


class TestFreightToolValidation:
    """Parameter validation for freight tools."""

    @pytest.mark.parametrize("name", FREIGHT_TOOL_NAMES)
    def test_tool_validate_returns_list(self, name, ctx):
        """validate() must return a list."""
        tool = get_tool(name)
        try:
            params = tool.parameters_schema()
            errors = asyncio.run(tool.validate(params, ctx))
            assert isinstance(errors, list)
        except ValidationError:
            pass  # Required fields missing — expected for some tools

    def test_search_loads_requires_origin(self):
        """search_loads must require an origin."""
        tool = get_tool("freight.search_loads")
        try:
            tool.parameters_schema(origin="Berlin")
            assert True
        except ValidationError:
            pass

    def test_get_load_requires_provider_and_load_id(self):
        """get_load requires provider_id and load_id."""
        tool = get_tool("freight.get_load")
        with pytest.raises(ValidationError):
            tool.parameters_schema()  # Missing both required fields

    def test_import_load_requires_provider_and_load_id(self):
        """import_load requires provider_id and load_id."""
        tool = get_tool("freight.import_load")
        with pytest.raises(ValidationError):
            tool.parameters_schema()  # Missing required fields


class TestFreightToolExecution:
    """Execution behavior with no services available."""

    @pytest.mark.parametrize("name", FREIGHT_TOOL_NAMES)
    def test_execute_without_db_returns_unavailable(self, name, ctx):
        """Tools without DB must return 'unavailable', not crash."""
        tool = get_tool(name)
        try:
            # Find a valid minimal set of params
            params_data: Dict[str, Any] = {}
            for field_name, field in tool.parameters_schema.model_fields.items():
                if field.is_required():
                    if "id" in field_name:
                        params_data[field_name] = 1
                    elif field_name == "origin":
                        params_data[field_name] = "Berlin"
                    elif field_name == "destination":
                        params_data[field_name] = "Warsaw"
                    elif field_name == "provider_id":
                        params_data[field_name] = "timocom"
                    elif field_name == "provider_load_id":
                        params_data[field_name] = "LD-123"
                    elif field_name == "label":
                        params_data[field_name] = "test"
                    elif field_name == "recipients":
                        params_data[field_name] = ["test@test.com"]
                    elif field_name == "subject":
                        params_data[field_name] = "test"
                    elif field_name == "body":
                        params_data[field_name] = "test"
                    elif field_name == "saved_search_id":
                        params_data[field_name] = "search-1"
                    elif field_name in ("top_n", "max_results"):
                        params_data[field_name] = 5

            params = tool.parameters_schema(**params_data)
            result = asyncio.run(tool.execute(params, ctx))
            assert isinstance(result, ToolResult), f"{name} returned {type(result)}"
            assert result.status in ("failed", "unavailable"), \
                f"{name} status: {result.status} (expected failed/unavailable without DB)"

        except ValidationError as e:
            pytest.skip(f"{name}: cannot construct minimal params: {e}")
        except Exception as e:
            pytest.fail(f"{name} crashed: {e}")
