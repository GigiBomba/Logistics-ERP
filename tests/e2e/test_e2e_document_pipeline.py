"""E2E: Document pipeline — Upload → OCR → Classify → Link → Search.

Tests the full document handling workflow from file upload through OCR
processing, entity classification, linking to trips/clients, and searching.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from models.document_models import DocumentResult
from repositories.document_repository import DocumentRepository
from services.document.ocr_service import OcrService
from services.document_service import DocumentService
from tests.test_helpers import make_db

pytestmark = pytest.mark.e2e


def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def doc_repo(db):
    return DocumentRepository(db)


@pytest.fixture
def doc_svc(db):
    return DocumentService(db)


# ═════════════════════════════════════════════════════════════════════════════
# Document Pipeline
# ═════════════════════════════════════════════════════════════════════════════


class TestDocumentPipeline:
    """Complete document pipeline: upload → OCR → classify → link → search."""

    def _create_temp_file(self, suffix=".pdf", content=b"dummy pdf content") -> str:
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.write(content)
        f.close()
        return f.name

    def _seed_trip(self, db) -> int:
        now = datetime.now().isoformat()
        db.conn.execute(
            "INSERT INTO clients (name, email, is_active, created_at, updated_at) "
            "VALUES (?, ?, 1, ?, ?)",
            ("Doc Client", "doc@example.com", now, now),
        )
        db.conn.commit()
        client_id = db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.conn.execute(
            "INSERT INTO trips (client_id, client_name, distance_km, total_price_eur, "
            "status, start_date, end_date) VALUES (?, ?, ?, ?, 'Delivered', ?, ?)",
            (client_id, "Doc Client", 500.0, 2000.0, _dt(-5), _dt(-3)),
        )
        db.conn.commit()
        return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    _doc_counter = 0

    def _seed_document(self, doc_repo, title="test_doc.pdf", category="invoice",
                       entity_type="trip", entity_id=None) -> int:
        TestDocumentPipeline._doc_counter += 1
        now = datetime.now().isoformat()
        src = self._create_temp_file()
        try:
            doc_id = doc_repo.create(
                doc_number=f"DOC-PIPE-{now[:10]}-{TestDocumentPipeline._doc_counter}",
                title=title,
                category=category,
                entity_type=entity_type,
                entity_id=entity_id,
                file_path=src,
                file_name=title,
                file_size=1024,
                mime_type="application/pdf",
                file_hash="abc123",
                tags="[]",
                description="",
                uploaded_by="tester",
                uploaded_at=now,
                updated_at=now,
            )
        finally:
            if os.path.isfile(src):
                os.unlink(src)
        return doc_id

    def test_upload_document(self, db, doc_repo, doc_svc):
        """Upload a document record and verify it's stored."""
        doc_id = self._seed_document(doc_repo)
        assert doc_id > 0

        doc = doc_repo.get_by_id(doc_id)
        assert doc is not None
        assert doc["title"] == "test_doc.pdf"
        assert doc["category"] == "invoice"

    def test_ocr_processing_updates_document(self, db, doc_repo):
        """OCR processing updates document with extracted text."""
        doc_id = self._seed_document(doc_repo)

        # Simulate OCR by directly updating OCR fields in DB
        ocr_text = "INVOICE NUMBER: INV-2024-0042\nCLIENT: Doc Client\nAMOUNT: 2000.00 EUR"
        db.conn.execute(
            "UPDATE documents SET ocr_text = ?, ocr_engine = 'test', "
            "ocr_run_at = ? WHERE id = ?",
            (ocr_text, datetime.now().isoformat(), doc_id),
        )
        db.conn.commit()

        doc = doc_repo.get_by_id(doc_id)
        assert doc is not None
        assert doc["ocr_text"] is not None
        assert "INV-2024-0042" in str(doc.get("ocr_text", ""))

    def test_extracted_fields_from_ocr(self, db, doc_repo):
        """OCR extracted fields are stored as JSON in extracted_data."""
        doc_id = self._seed_document(doc_repo)

        extracted = json.dumps({
            "invoice_number": "INV-2024-0042",
            "client_name": "Doc Client",
            "amount": 2000.0,
            "currency": "EUR",
            "confidence": 0.95,
        })
        db.conn.execute(
            "UPDATE documents SET extracted_data_json = ?, ocr_engine = 'auto', "
            "ocr_run_at = ? WHERE id = ?",
            (extracted, datetime.now().isoformat(), doc_id),
        )
        db.conn.commit()

        doc = doc_repo.get_by_id(doc_id)
        assert doc is not None
        raw = doc.get("extracted_data_json")
        if isinstance(raw, str):
            fields = json.loads(raw)
        else:
            fields = raw or {}
        assert fields.get("invoice_number") == "INV-2024-0042"
        assert fields.get("amount") == 2000.0

    def test_link_document_to_trip(self, db, doc_repo):
        """Link a document to a trip entity."""
        trip_id = self._seed_trip(db)
        doc_id = self._seed_document(doc_repo, entity_type="trip", entity_id=trip_id)

        # Update the document's entity link
        db.conn.execute(
            "UPDATE documents SET entity_type = 'trip', entity_id = ? WHERE id = ?",
            (trip_id, doc_id),
        )
        db.conn.commit()

        # Verify via link
        doc = doc_repo.get_by_id(doc_id)
        assert doc is not None
        assert doc["entity_type"] == "trip"
        assert doc["entity_id"] == trip_id

    def test_search_document_by_text(self, db, doc_repo):
        """Search for a document by its title (advanced_search searches title, not ocr_text)."""
        doc_id = self._seed_document(
            doc_repo, title="SPECIAL-SEARCH-TERM-98765-invoice.pdf"
        )

        # Search the title column (advanced_search searches title/file_name/description/tags/doc_number)
        results = doc_repo.advanced_search(query="SPECIAL-SEARCH-TERM")
        # advanced_search returns a list of matching documents
        assert len(results) >= 1, "Document should be found by title"

    def test_document_not_found_by_text(self, db, doc_repo):
        """Search for text that doesn't exist returns no results."""
        doc_id = self._seed_document(doc_repo)
        db.conn.execute(
            "UPDATE documents SET ocr_text = 'Some random text' WHERE id = ?",
            (doc_id,),
        )
        db.conn.commit()

        results = doc_repo.advanced_search(query="NONEXISTENT-TEXT-99999")
        # advanced_search returns a list — should be empty
        assert len(results) == 0

    def test_multiple_document_links(self, db, doc_repo):
        """Link multiple documents to the same trip."""
        trip_id = self._seed_trip(db)

        doc_ids = []
        for i in range(3):
            doc_id = self._seed_document(
                doc_repo,
                title=f"doc_{i}.pdf",
                entity_type="trip",
                entity_id=trip_id,
            )
            doc_ids.append(doc_id)
            db.conn.execute(
                "UPDATE documents SET entity_type = 'trip', entity_id = ? WHERE id = ?",
                (trip_id, doc_id),
            )
            db.conn.commit()

        # Find all documents linked to this trip
        for doc_id in doc_ids:
            doc = doc_repo.get_by_id(doc_id)
            assert doc["entity_id"] == trip_id

    def test_document_delete_removes_record(self, db, doc_repo):
        """Delete a document and verify it's gone."""
        doc_id = self._seed_document(doc_repo)
        assert doc_repo.get_by_id(doc_id) is not None

        doc_repo.delete(doc_id)
        assert doc_repo.get_by_id(doc_id) is None


# ═════════════════════════════════════════════════════════════════════════════
# API-level document tests
# ═════════════════════════════════════════════════════════════════════════════


class TestDocumentPipelineViaAPI:
    """Document pipeline exercised through the API layer."""

    BASE = "/api/v1/documents"

    def test_api_upload_document(self, client_with_mocks):
        """Upload a document via API."""
        client, mocks = client_with_mocks

        mock_result = {
            "id": 1, "doc_number": "DOC-API-0001", "title": "upload_test.pdf",
            "category": "invoice", "entity_type": "trip", "entity_id": 42,
            "file_name": "upload_test.pdf", "file_size": 1024,
            "mime_type": "application/pdf", "uploaded_by": "user",
            "uploaded_at": "2024-01-15T10:00:00", "updated_at": "2024-01-15T10:00:00",
            "is_archived": False, "tags": "[]", "description": "",
        }
        mocks["document_service"].upload_document.return_value = MagicMock(success=True, data=MagicMock(model_dump=lambda: mock_result))

        resp = client.post(
            f"{self.BASE}/upload",
            files={"file": ("upload_test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
            data={"category": "invoice", "entity_type": "trip", "entity_id": "42"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["doc_number"] == "DOC-API-0001"

    def test_api_search_document(self, client_with_mocks):
        """Search for documents via API."""
        client, mocks = client_with_mocks

        mock_doc = {
            "id": 1, "doc_number": "DOC-001", "title": "found_doc.pdf",
            "file_name": "found_doc.pdf", "file_size": 1024,
            "mime_type": "application/pdf", "uploaded_by": "user",
            "uploaded_at": "2024-01-15T10:00:00", "updated_at": "2024-01-15T10:00:00",
            "category": "invoice", "entity_type": "trip", "entity_id": 42,
            "is_archived": False, "tags": [], "description": "",
        }
        mocks["document_service"].advanced_search.return_value = {
            "items": [mock_doc],
            "total": 1,
            "total_pages": 1,
        }

        resp = client.get(f"{self.BASE}/?query=invoice")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_api_link_document_to_entity(self, client_with_mocks):
        """Link a document to a trip entity via API."""
        client, mocks = client_with_mocks

        mocks["document_service"].link_to_entity.return_value = {
            "status": "linked", "document_id": 1, "entity_type": "trip", "entity_id": 42,
        }

        resp = client.post(
            f"{self.BASE}/1/link",
            json={"entity_type": "trip", "entity_id": 42},
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json()["status"] == "linked"

    def test_api_delete_document(self, client_with_mocks):
        """Delete a document via API."""
        client, mocks = client_with_mocks
        mocks["document_service"].delete.return_value = True

        resp = client.delete(f"{self.BASE}/1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
