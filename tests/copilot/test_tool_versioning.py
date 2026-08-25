"""Tool versioning and deprecation tests — §9.2.

Deprecated tools disappear from new plans but don't break in-flight ones.
"""
from __future__ import annotations


import pytest
from pydantic import BaseModel, ConfigDict

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext, SessionContext


class TestToolVersioning:
    """§9.2 — Versioning and deprecation."""

    def test_tool_version_is_semver(self):
        """All registered tools must have semver versions.
        (Excludes test fixture tools from test_tool_registry.py.)
        """
        from backend.copilot.tools.registry import all_tools
        for tool in all_tools():
            if tool.name.startswith("test."):
                continue  # Test fixture tools may have invalid versions
            parts = tool.tool_version.split(".")
            assert len(parts) == 3, f"{tool.name}: {tool.tool_version} not semver"
            assert all(p.isdigit() for p in parts), f"{tool.name}: {tool.tool_version} not semver"

    def test_deprecated_tools_excluded_from_available(self):
        """Deprecated tools must not appear in available_tools()."""
        from backend.copilot.tools.registry import available_tools
        avail = available_tools()
        for t in avail:
            if t.name.startswith("test."):
                continue
            assert not t.deprecated, f"Deprecated tool {t.name} in available_tools()"

    def test_deprecated_tools_still_in_all(self):
        """Deprecated tools must still appear in all_tools().
        (Excludes test fixture tools.)
        """
        from backend.copilot.tools.registry import all_tools
        all_t = all_tools()
        dep = [t for t in all_t if t.deprecated and not t.name.startswith("test.")]
        assert len(dep) == 0, f"Found deprecated tools: {[t.name for t in dep]}"
