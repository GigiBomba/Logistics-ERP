"""Tests for backend/schemas/document.py — document, link, and read-result schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import ValidationError

from backend.schemas.document import (
    DocumentCreate,
    DocumentLinkCreate,
    DocumentLinkResponse,
    DocumentReadResult,
    DocumentResponse,
    DocumentUpdate,
)


# ── DocumentCreate ────────────────────────────────────────────────────────────


class TestDocumentCreate:
    """Inherits DocumentBase — all fields have defaults, extra="forbid"."""

    def test_defaults(self):
        inst = DocumentCreate()
        assert inst.title == ""
        assert inst.category == ""
        assert inst.entity_type == ""
        assert inst.entity_id is None
        assert inst.tags is None
        assert inst.description == ""
        assert inst.expiry_date is None

    def test_all_fields(self):
        inst = DocumentCreate(
            title="Invoice 123",
            category="invoice",
            entity_type="trip",
            entity_id=42,
            tags=["urgent", "fiscal"],
            description="Monthly invoice",
            expiry_date="2025-12-31",
        )
        assert inst.title == "Invoice 123"
        assert inst.tags == ["urgent", "fiscal"]

    def test_entity_id_none(self):
        inst = DocumentCreate(entity_type="trip", entity_id=None)
        assert inst.entity_id is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DocumentCreate(unknown="x")  # type: ignore[call-arg]


# ── DocumentResponse ──────────────────────────────────────────────────────────


class TestDocumentResponse:
    """Tests JSON string → dict coercion for tags and extracted_data_json."""

    @pytest.fixture
    def minimal_kwargs(self) -> Dict[str, Any]:
        return {
            "id": 1,
            "doc_number": "DOC-001",
            "file_name": "invoice.pdf",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "uploaded_by": "admin",
            "uploaded_at": "2025-01-01T12:00:00Z",
            "updated_at": "2025-01-02T12:00:00Z",
        }

    def test_required_fields_only(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs)
        assert inst.id == 1
        assert inst.doc_number == "DOC-001"
        assert inst.is_archived is False
        # tags defaults to None (from DocumentBase); the validator only runs on provided values
        assert inst.tags is None
        assert inst.extracted_data_json == {}

    def test_tags_as_list(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs, tags=["a", "b"])
        assert inst.tags == ["a", "b"]

    def test_tags_as_json_string(self, minimal_kwargs: Dict[str, Any]):
        """Coercion: JSON string → list."""
        inst = DocumentResponse(**minimal_kwargs, tags='["urgent", "fiscal"]')
        assert inst.tags == ["urgent", "fiscal"]

    def test_tags_as_invalid_json_string_falls_back_to_empty(self, minimal_kwargs: Dict[str, Any]):
        """Invalid JSON string results in empty list."""
        inst = DocumentResponse(**minimal_kwargs, tags="not-json")
        assert inst.tags == []

    def test_tags_as_non_list_non_string_becomes_empty(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs, tags=42)
        assert inst.tags == []

    def test_extracted_data_json_as_dict(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs, extracted_data_json={"amount": 100.0})
        assert inst.extracted_data_json == {"amount": 100.0}

    def test_extracted_data_json_as_json_string(self, minimal_kwargs: Dict[str, Any]):
        """Coercion: JSON string → dict."""
        inst = DocumentResponse(**minimal_kwargs, extracted_data_json='{"amount": 100.0}')
        assert inst.extracted_data_json == {"amount": 100.0}

    def test_extracted_data_json_as_invalid_string_falls_back_to_empty(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs, extracted_data_json="bad-json")
        assert inst.extracted_data_json == {}

    def test_extracted_data_json_as_non_dict_non_string_becomes_empty(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs, extracted_data_json=[1, 2, 3])
        assert inst.extracted_data_json == {}

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentResponse(
                doc_number="D1",
                file_name="f.pdf",
                file_size=1,
                mime_type="t",
                uploaded_by="u",
                uploaded_at="t",
                updated_at="t",
            )  # type: ignore[call-arg]

    def test_tags_serialization_round_trip(self, minimal_kwargs: Dict[str, Any]):
        """Tags stored as list should survive dump + validate."""
        original = DocumentResponse(**minimal_kwargs, tags=["x", "y"])
        dumped = original.model_dump()
        restored = DocumentResponse.model_validate(dumped)
        assert restored.tags == ["x", "y"]

    # extra="ignore" — unknown fields are silently dropped
    def test_extra_field_ignored(self, minimal_kwargs: Dict[str, Any]):
        inst = DocumentResponse(**minimal_kwargs, unknown_extra="should_be_ignored")
        assert not hasattr(inst, "unknown_extra")


# ── DocumentUpdate ────────────────────────────────────────────────────────────


class TestDocumentUpdate:
    """All fields Optional, extra="forbid"."""

    def test_empty(self):
        inst = DocumentUpdate()
        assert inst.title is None
        assert inst.category is None
        assert inst.tags is None
        assert inst.description is None
        assert inst.expiry_date is None

    def test_partial_update(self):
        inst = DocumentUpdate(title="New Title", tags=["tag1"])
        assert inst.title == "New Title"
        assert inst.tags == ["tag1"]
        assert inst.category is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DocumentUpdate(unknown="x")  # type: ignore[call-arg]


# ── DocumentLinkCreate ────────────────────────────────────────────────────────


class TestDocumentLinkCreate:
    """linked_entity_type (required), linked_entity_id (required), relation_type (default)."""

    def test_required_only(self):
        inst = DocumentLinkCreate(linked_entity_type="trip", linked_entity_id=10)
        assert inst.linked_entity_type == "trip"
        assert inst.linked_entity_id == 10
        assert inst.relation_type == "attached"

    def test_custom_relation(self):
        inst = DocumentLinkCreate(linked_entity_type="client", linked_entity_id=5, relation_type="signed")
        assert inst.relation_type == "signed"

    def test_missing_linked_entity_type_raises(self):
        with pytest.raises(ValidationError):
            DocumentLinkCreate(linked_entity_id=1)  # type: ignore[call-arg]

    def test_missing_linked_entity_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentLinkCreate(linked_entity_type="trip")  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DocumentLinkCreate(linked_entity_type="t", linked_entity_id=1, extra="x")  # type: ignore[call-arg]


# ── DocumentLinkResponse ──────────────────────────────────────────────────────


class TestDocumentLinkResponse:
    """All fields required except no optional defaults."""

    def test_valid(self):
        inst = DocumentLinkResponse(
            id=1, document_id=10, linked_entity_type="trip",
            linked_entity_id=5, relation_type="attached", created_at="2025-01-01T00:00:00Z",
        )
        assert inst.id == 1
        assert inst.document_id == 10
        assert inst.relation_type == "attached"

    def test_missing_created_at_raises(self):
        with pytest.raises(ValidationError):
            DocumentLinkResponse(
                id=1, document_id=10, linked_entity_type="trip",
                linked_entity_id=5, relation_type="attached",
            )  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DocumentLinkResponse(
                id=1, document_id=10, linked_entity_type="t",
                linked_entity_id=1, relation_type="a", created_at="t", bad="x",
            )  # type: ignore[call-arg]


# ── DocumentReadResult ────────────────────────────────────────────────────────


class TestDocumentReadResult:
    """Nests DocumentResponse and DocumentLinkResponse lists."""

    @pytest.fixture
    def doc_resp_kwargs(self) -> Dict[str, Any]:
        return {
            "id": 1,
            "doc_number": "D1",
            "file_name": "f.pdf",
            "file_size": 100,
            "mime_type": "pdf",
            "uploaded_by": "u",
            "uploaded_at": "t",
            "updated_at": "t",
        }

    def test_minimal(self, doc_resp_kwargs: Dict[str, Any]):
        doc = DocumentResponse(**doc_resp_kwargs)
        inst = DocumentReadResult(document=doc)
        assert inst.document.id == 1
        assert inst.ocr_text == ""
        assert inst.extracted_fields == {}
        assert inst.linked_entities == []
        assert inst.versions == []
        assert inst.tags == []
        assert inst.expiry == ""
        assert inst.is_expired is False

    def test_all_fields(self, doc_resp_kwargs: Dict[str, Any]):
        doc = DocumentResponse(**doc_resp_kwargs)
        link = DocumentLinkResponse(
            id=1, document_id=1, linked_entity_type="trip",
            linked_entity_id=5, relation_type="attached", created_at="t",
        )
        inst = DocumentReadResult(
            document=doc,
            ocr_text="extracted text",
            extracted_fields={"amount": 99.0},
            linked_entities=[link],
            versions=[{"version": 1}],
            tags=["tag1"],
            expiry="2025-12-31",
            is_expired=True,
        )
        assert inst.ocr_text == "extracted text"
        assert len(inst.linked_entities) == 1
        assert inst.versions == [{"version": 1}]

    def test_extra_field_forbidden(self, doc_resp_kwargs: Dict[str, Any]):
        doc = DocumentResponse(**doc_resp_kwargs)
        with pytest.raises(ValidationError):
            DocumentReadResult(document=doc, unknown="x")  # type: ignore[call-arg]
