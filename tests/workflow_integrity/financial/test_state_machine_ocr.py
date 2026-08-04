"""OCR document state machine: document upload → processing → OCR complete → matched → grouped.

The document automation pipeline follows a multi-stage process:

  1. **Uploaded** — file received, stored on disk
  2. **Processing** — image enhancement (deskew, contrast, etc.)
  3. **OCR Running** — text extracted from processed image
  4. **OCR Complete** — extracted data persisted on document row
  5. **Matched** — extracted fields matched to an existing trip/client
  6. **Grouped** — document linked to a document group/package

Events in event_bus.py track these states:
  - DOCUMENT_UPLOADED (= "document.uploaded")
  - DOCUMENT_PROCESSED (= "document.automation.processed")
  - DOCUMENT_OCR_COMPLETE (= "document.automation.ocr_complete")
  - DOCUMENT_MATCHED (= "document.automation.matched")
  - DOCUMENT_GROUPED (= "document.automation.grouped")
  - DOCUMENT_LINKED (= "document.linked")

Documents also have an `ocr_processed` boolean flag and `ocr_run_at` timestamp.
"""

from __future__ import annotations

import pytest

from models.document_models import DocumentUpload
from services.document_service import DocumentService
from services.operations.event_bus import (
    DOCUMENT_UPLOADED,
    DOCUMENT_LINKED,
    DOCUMENT_ARCHIVED,
)

pytestmark = pytest.mark.state_machine


class TestDocumentUploadState:
    """Document upload: file received → stored → event emitted."""

    def test_upload_document(self, db, workflow_env, event_monitor, tmp_path):
        """Uploading a document transitions to the Uploaded state."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Delivered",
        )

        doc_file = tmp_path / "test_cmr.pdf"
        doc_file.write_text("%PDF-1.4 test document")
        assert doc_file.exists()

        event_monitor.track("document.uploaded")

        doc_svc = DocumentService(db)
        result = doc_svc.upload_document(
            DocumentUpload(
                source_path=str(doc_file),
                title="Test CMR Document",
                category="trip",
                entity_type="trip",
                entity_id=trip_id,
                tags=["test", "cmr"],
            ),
            user_id=0,
        )
        assert result.success is True, f"Upload failed: {result.errors}"
        assert result.data is not None
        doc = result.data
        assert doc.id > 0
        assert doc.ocr_processed is False

        event_monitor.assert_event_published("document.uploaded")

    def test_upload_without_entity(self, db, workflow_env, tmp_path):
        """Document can be uploaded without linking to an entity."""
        doc_file = tmp_path / "standalone.pdf"
        doc_file.write_text("%PDF-1.4 standalone document")

        doc_svc = DocumentService(db)
        result = doc_svc.upload_document(
            DocumentUpload(
                source_path=str(doc_file),
                title="Standalone Document",
                tags=["standalone"],
            ),
            user_id=0,
        )
        assert result.success is True
        assert result.data is not None
        doc = result.data
        assert doc.id > 0

    def test_link_document_to_entity(self, db, workflow_env, event_monitor, tmp_path):
        """Linking a document to a trip emits document.linked event."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Delivered",
        )

        doc_file = tmp_path / "link_test.pdf"
        doc_file.write_text("%PDF-1.4 for linking test")

        doc_svc = DocumentService(db)
        upload_result = doc_svc.upload_document(
            DocumentUpload(source_path=str(doc_file), title="Link Test"),
            user_id=0,
        )
        assert upload_result.success is True
        assert upload_result.data is not None
        doc_id = upload_result.data.id

        event_monitor.track("document.linked")
        link_result = doc_svc.link_to_entity(
            document_id=doc_id,
            entity_type="trip",
            entity_id=trip_id,
        )
        assert link_result.success is True, f"Link failed: {link_result.errors}"
        event_monitor.assert_event_published("document.linked")

    def test_document_state_after_link(self, db, workflow_env, tmp_path):
        """After linking, the document appears in entity's document list."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Delivered",
        )

        doc_file = tmp_path / "state_test.pdf"
        doc_file.write_text("%PDF-1.4 state test")

        doc_svc = DocumentService(db)
        up_result = doc_svc.upload_document(
            DocumentUpload(
                source_path=str(doc_file),
                title="State Test",
                entity_type="trip",
                entity_id=trip_id,
            ),
            user_id=0,
        )
        doc_id = up_result.data.id

        linked_docs = doc_svc.get_documents_for_entity("trip", trip_id)
        linked_ids = [d["id"] for d in linked_docs]
        assert doc_id in linked_ids, (
            f"Document {doc_id} not found in entity documents"
        )


class TestDocumentArchiveState:
    """Document archival/deletion lifecycle."""

    def test_archive_document(self, db, workflow_env, event_monitor, tmp_path):
        """Archiving a document transitions to Archived state."""
        doc_file = tmp_path / "to_archive.pdf"
        doc_file.write_text("%PDF-1.4 to be archived")

        doc_svc = DocumentService(db)
        result = doc_svc.upload_document(
            DocumentUpload(source_path=str(doc_file), title="To Archive"),
            user_id=0,
        )
        assert result.success is True
        doc_id = result.data.id

        event_monitor.track("document.archived")
        doc_svc.archive(doc_id)
        event_monitor.assert_event_published("document.archived")

    def test_delete_document(self, db, workflow_env, event_monitor, tmp_path):
        """Deleting a document transitions to deleted state and emits event."""
        doc_file = tmp_path / "to_delete.pdf"
        doc_file.write_text("%PDF-1.4 to be deleted")

        doc_svc = DocumentService(db)
        result = doc_svc.upload_document(
            DocumentUpload(source_path=str(doc_file), title="To Delete"),
            user_id=0,
        )
        assert result.success is True
        doc_id = result.data.id

        event_monitor.track("document.deleted")
        delete_result = doc_svc.delete_document(doc_id, user_id=0)
        assert delete_result.success is True, f"Delete failed: {delete_result.errors}"
        event_monitor.assert_event_published("document.deleted")


class TestDocumentOcrProcessingState:
    """OCR processing pipeline states (skip if OCR service not available)."""

    def test_ocr_pipeline_not_implemented_as_state_machine(self):
        """Documented gap: OCR pipeline does not have persistable states.

        Known gap: The OCR automation pipeline runs as a monolithic synchronous
        call (run_for_existing_document) without persistable intermediate states.

        When a proper pipeline state machine is implemented, expected states:
          Pending → Processing → OCR_Complete → Matched → Grouped
          Pending → Failed, Processing → Failed

        Events defined in event_bus.py for the pipeline:
          document.automation.imported, document.automation.processed,
          document.automation.ocr_complete, document.automation.matched,
          document.automation.grouped
        """
        # Documented gap — OCR pipeline state machine is not yet testable as
        # independent state transitions. The pipeline is a monolithic call.
        assert True
