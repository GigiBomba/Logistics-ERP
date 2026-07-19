"""Test the 6 newly-fixed Co-Pilot tools — import, registration, metadata."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.copilot.schemas import ConfirmationLevel
from backend.copilot.tools.base import BaseTool
from backend.copilot.tools.registry import get_tool, all_tools


# ── Tool classes under test ────────────────────────────────────────────────
# Proforma domain (3 tools)
from backend.copilot.tools.proforma_tools import (
    ProformaCreateTool,
    ProformaUpdateTool,
    ProformaConvertToInvoiceTool,
    ProformaCreateParams,
    ProformaUpdateParams,
    ProformaConvertToInvoiceParams,
)

# Receipt domain (3 tools)
from backend.copilot.tools.receipt_tools import (
    ReceiptDraftTool,
    ReceiptGeneratePdfTool,
    ReceiptFinalizeTool,
    ReceiptDraftParams,
    ReceiptGeneratePdfParams,
    ReceiptFinalizeParams,
)


TOOL_PARAMS_MAP = {
    ProformaCreateTool: ProformaCreateParams,
    ProformaUpdateTool: ProformaUpdateParams,
    ProformaConvertToInvoiceTool: ProformaConvertToInvoiceParams,
    ReceiptDraftTool: ReceiptDraftParams,
    ReceiptGeneratePdfTool: ReceiptGeneratePdfParams,
    ReceiptFinalizeTool: ReceiptFinalizeParams,
}


TOOL_CLASSES = [
    ProformaCreateTool,
    ProformaUpdateTool,
    ProformaConvertToInvoiceTool,
    ReceiptDraftTool,
    ReceiptGeneratePdfTool,
    ReceiptFinalizeTool,
]


class TestToolImport:
    """Each tool class can be imported and instantiates as a BaseTool."""

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_can_instantiate(self, tool_cls):
        instance = tool_cls()
        assert isinstance(instance, BaseTool)

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_has_name(self, tool_cls):
        assert tool_cls.name

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_has_description(self, tool_cls):
        assert tool_cls.description


class TestToolMetadata:
    """required_permission, confirmation_level, tool_version are non-empty."""

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_required_permission_non_empty(self, tool_cls):
        assert tool_cls.required_permission
        assert tool_cls.required_permission.strip()

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_tool_version_non_empty(self, tool_cls):
        assert tool_cls.tool_version
        assert tool_cls.tool_version.strip()

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_confirmation_level_is_valid(self, tool_cls):
        assert isinstance(tool_cls.confirmation_level, ConfirmationLevel)

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_supports_undo_is_bool(self, tool_cls):
        assert isinstance(tool_cls.supports_undo, bool)

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_deprecated_is_bool(self, tool_cls):
        assert isinstance(tool_cls.deprecated, bool)


class TestParametersSchema:
    """parameters_schema is a proper Pydantic BaseModel subclass."""

    @pytest.mark.parametrize(
        "tool_cls,expected_params_cls",
        [
            (ProformaCreateTool, ProformaCreateParams),
            (ProformaUpdateTool, ProformaUpdateParams),
            (ProformaConvertToInvoiceTool, ProformaConvertToInvoiceParams),
            (ReceiptDraftTool, ReceiptDraftParams),
            (ReceiptGeneratePdfTool, ReceiptGeneratePdfParams),
            (ReceiptFinalizeTool, ReceiptFinalizeParams),
        ],
        ids=["proforma.create", "proforma.update", "proforma.convert_to_invoice",
             "receipt.draft", "receipt.generate_pdf", "receipt.finalize"],
    )
    def test_parameters_schema_is_base_model(self, tool_cls, expected_params_cls):
        assert issubclass(tool_cls.parameters_schema, BaseModel)
        assert tool_cls.parameters_schema is expected_params_cls

    @pytest.mark.parametrize("params_cls", [
        ProformaCreateParams,
        ProformaUpdateParams,
        ProformaConvertToInvoiceParams,
        ReceiptDraftParams,
        ReceiptGeneratePdfParams,
        ReceiptFinalizeParams,
    ], ids=lambda c: c.__name__)
    def test_params_are_base_model(self, params_cls):
        assert issubclass(params_cls, BaseModel)

    @pytest.mark.parametrize("params_cls", [
        ProformaCreateParams,
        ProformaUpdateParams,
        ProformaConvertToInvoiceParams,
        ReceiptDraftParams,
        ReceiptGeneratePdfParams,
        ReceiptFinalizeParams,
    ], ids=lambda c: c.__name__)
    def test_params_can_be_constructed(self, params_cls):
        """Verify that each params model can be constructed with valid data."""
        kwargs = _sample_params(params_cls)
        instance = params_cls(**kwargs)
        assert isinstance(instance, params_cls)


class TestToolRegistration:
    """Each tool appears in the global registry."""

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_tool_is_registered(self, tool_cls):
        tool = get_tool(tool_cls.name)
        assert tool is not None, f"Tool {tool_cls.name} not found in registry"

    def test_all_six_are_in_registry(self):
        registered_names = [t.name for t in all_tools()]
        for tool_cls in TOOL_CLASSES:
            assert tool_cls.name in registered_names, f"{tool_cls.name} missing from all_tools()"

    @pytest.mark.parametrize("tool_cls", TOOL_CLASSES, ids=lambda c: c.name)
    def test_registry_instance_matches_class(self, tool_cls):
        tool = get_tool(tool_cls.name)
        assert tool is not None
        # Type-narrow for the type checker
        registered: BaseTool = tool  # type: ignore[assignment]
        assert registered.name == tool_cls.name
        assert registered.tool_version == tool_cls.tool_version
        assert registered.required_permission == tool_cls.required_permission
        assert registered.confirmation_level == tool_cls.confirmation_level


# ── Helpers ────────────────────────────────────────────────────────────────

def _sample_params(params_cls: type[BaseModel]) -> dict:
    """Return a minimal valid kwargs dict for the given params model."""
    mapping = {
        ProformaCreateParams: {
            "client_id": 1,
            "trip_id": 1,
            "amount": 100.0,
            "currency": "EUR",
        },
        ProformaUpdateParams: {
            "proforma_id": 1,
            "notes": "Updated notes",
        },
        ProformaConvertToInvoiceParams: {
            "proforma_id": 1,
        },
        ReceiptDraftParams: {
            "client_id": 1,
            "amount": 100.0,
        },
        ReceiptGeneratePdfParams: {
            "receipt_id": 1,
        },
        ReceiptFinalizeParams: {
            "receipt_id": 1,
        },
    }
    return mapping[params_cls]
