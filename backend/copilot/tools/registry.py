"""Tool Registry — decorator-based registration with startup validation.

Blueprint: §9 — Registry enforcement.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from pydantic import BaseModel

from backend.copilot.tools.base import BaseTool

logger = logging.getLogger(__name__)

# ── Global registry ────────────────────────────────────────────────────────

_registry: Dict[str, BaseTool] = {}
_pending_registrations: List[Type[BaseTool]] = []


def register_tool(cls: Type[BaseTool]) -> Type[BaseTool]:
    """Class decorator: register a BaseTool subclass at import time.

    Usage:
        @register_tool
        class DispatchCreateTool(BaseTool):
            name = "dispatch.create"
            ...
    """
    if not issubclass(cls, BaseTool):
        raise TypeError(f"@register_tool can only be applied to BaseTool subclasses, got {cls.__name__}")

    instance = cls()
    _registry[instance.name] = instance
    _pending_registrations.append(cls)
    logger.debug("Registered tool: %s v%s", instance.name, instance.tool_version)
    return cls


def all_tools() -> List[BaseTool]:
    """Return all registered tools (including deprecated)."""
    return list(_registry.values())


def get_tool(name: str) -> Optional[BaseTool]:
    """Look up a single tool by name."""
    return _registry.get(name)


def available_tools(deprecated: bool = False) -> List[BaseTool]:
    """Return tools available for new plans (excludes deprecated unless requested)."""
    return [t for t in _registry.values() if not t.deprecated or deprecated]


# ── Startup validation (fail fast, not at request time) ────────────────────

def validate_registry() -> List[str]:
    """Run at startup. Returns list of validation errors (empty = all tools valid).

    Checks:
    - Every tool has a non-empty required_permission
    - Every tool has a valid confirmation_level
    - Every tool has a non-empty tool_version
    - Every tool's parameters_schema is a proper Pydantic model (not dict[str, Any])
    """
    errors: List[str] = []

    for name, tool in _registry.items():
        if not tool.required_permission or not tool.required_permission.strip():
            errors.append(f"Tool '{name}': required_permission is empty")

        if tool.confirmation_level is None:
            errors.append(f"Tool '{name}': confirmation_level is None")

        if not tool.tool_version or not tool.tool_version.strip():
            errors.append(f"Tool '{name}': tool_version is empty")

        if not issubclass(tool.parameters_schema, BaseModel):
            errors.append(
                f"Tool '{name}': parameters_schema must be a Pydantic BaseModel subclass, "
                f"got {type(tool.parameters_schema).__name__}"
            )

    if errors:
        logger.error("Tool registry validation FAILED: %d error(s)", len(errors))
        for err in errors:
            logger.error("  - %s", err)
    else:
        logger.info("Tool registry validated: %d tool(s) registered, 0 errors", len(_registry))

    return errors


def run_startup_validation() -> List[str]:
    """Import all tool modules and validate the full registry.

    Should be called during application startup (before any requests).
    """
    # Import tool modules to trigger @register_tool
    try:
        import backend.copilot.tools.vehicle_tools        # noqa: F401
        import backend.copilot.tools.vehicle_crud_tools   # noqa: F401
        import backend.copilot.tools.driver_tools         # noqa: F401
        import backend.copilot.tools.driver_crud_tools    # noqa: F401
        import backend.copilot.tools.route_tools          # noqa: F401
        import backend.copilot.tools.trip_tools           # noqa: F401
        import backend.copilot.tools.trip_crud_tools      # noqa: F401
        import backend.copilot.tools.client_tools         # noqa: F401
        import backend.copilot.tools.client_crud_tools    # noqa: F401
        import backend.copilot.tools.document_tools       # noqa: F401
        import backend.copilot.tools.currency_tools       # noqa: F401
        import backend.copilot.tools.tracking_tools       # noqa: F401
        import backend.copilot.tools.analytics_tools      # noqa: F401
        import backend.copilot.tools.invoice_tools       # noqa: F401
        import backend.copilot.tools.receipt_tools       # noqa: F401
        import backend.copilot.tools.proforma_tools      # noqa: F401
        import backend.copilot.tools.dispatch_tools      # noqa: F401
        import backend.copilot.tools.maintenance_tools   # noqa: F401
        import backend.copilot.tools.route_sharing_tools  # noqa: F401
        import backend.copilot.tools.cmr_tools            # noqa: F401
        import backend.copilot.tools.tacho_tools          # noqa: F401
        import backend.copilot.tools.export_tools         # noqa: F401
        import backend.copilot.tools.ocr_tools           # noqa: F401
        import backend.copilot.tools.automail_tools       # noqa: F401
        import backend.copilot.tools.delete_tools        # noqa: F401
        import backend.copilot.tools.undo_tools          # noqa: F401
        import backend.copilot.tools.freight_tools       # noqa: F401
        import backend.copilot.tools.payment_tools       # noqa: F401
        import backend.copilot.tools.help_tools          # noqa: F401
    except ImportError as e:
        return [f"Failed to import tool modules: {e}"]

    return validate_registry()
