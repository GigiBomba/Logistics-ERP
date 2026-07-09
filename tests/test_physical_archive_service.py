"""Tests for PhysicalArchiveService (Tab 2 migration pipeline)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.migration.physical_archive_service import PhysicalArchiveService
from tests.test_helpers import make_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def service(db):
    return PhysicalArchiveService(db)


# ── _classify (static) ────────────────────────────────────────────────────

class TestClassify:
    """Tests for PhysicalArchiveService._classify static method."""

    def test_classify_returns_cmr_for_cmr_patterns(self):
        """OCR text containing 'CMR' classifies as cmr."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            "ocr_text": "This is a CMR document for transport",
        })
        assert result == "cmr"

    def test_classify_returns_cmr_for_cmr_number_field(self):
        """Extracted cmr_number field takes priority."""
        result = PhysicalArchiveService._classify({
            "extracted": {"cmr_number": "CMR-001"},
            "ocr_text": "some random text",
        })
        assert result == "cmr"

    def test_classify_returns_invoice_for_invoice_patterns(self):
        """OCR text containing 'INVOICE' classifies as invoice."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            "ocr_text": "INVOICE dated 2026-01-15",
        })
        assert result == "invoice"

    def test_classify_returns_invoice_for_invoice_number_field(self):
        """Extracted invoice_number field takes priority."""
        result = PhysicalArchiveService._classify({
            "extracted": {"invoice_number": "INV-2026-001"},
            "ocr_text": "",
        })
        assert result == "invoice"

    def test_classify_returns_delivery_note_for_patterns(self):
        """OCR text containing 'delivery note' classifies as delivery_note."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            "ocr_text": "Delivery Note #1234",
        })
        assert result == "delivery_note"

    def test_classify_returns_contract_for_patterns(self):
        """OCR text containing 'contract' classifies as contract."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            "ocr_text": "Contract of carriage",
        })
        assert result == "contract"

    def test_classify_returns_unknown_for_no_match(self):
        """OCR text with no known keywords returns 'unknown'."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            "ocr_text": "Some random scanned text",
        })
        assert result == "unknown"

    def test_classify_uses_extracted_doc_type_when_present(self):
        """If extracted has a doc_type field, use that."""
        result = PhysicalArchiveService._classify({
            "extracted": {"doc_type": "DeliveryNote"},
            "ocr_text": "",
        })
        assert result == "deliverynote"

    def test_classify_handles_none_ocr_text(self):
        """pipeline_result with ocr_text=None does not crash."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            "ocr_text": None,
        })
        assert result == "unknown"

    def test_classify_handles_empty_extracted(self):
        """pipeline_result with extracted=None does not crash."""
        result = PhysicalArchiveService._classify({
            "extracted": None,
            "ocr_text": "",
        })
        assert result == "unknown"

    def test_classify_handles_missing_keys(self):
        """pipeline_result missing both keys returns unknown."""
        result = PhysicalArchiveService._classify({})
        assert result == "unknown"

    def test_classify_scores_multiple_types_correctly(self):
        """If both cmr and invoice match, the one with higher score wins."""
        result = PhysicalArchiveService._classify({
            "extracted": {},
            # "cmr" appears 3 times, "invoice" appears 2 times -> cmr wins
            "ocr_text": "cmr cmr cmr and invoice invoice here",
        })
        assert result == "cmr"


# ── process_document ─────────────────────────────────────────────────────

class TestProcessDocument:
    """Tests for PhysicalArchiveService.process_document."""

    @patch("services.migration.physical_archive_service.PhysicalArchiveService.process_batch")
    def test_process_document_delegates_to_process_batch(self, mock_process_batch, service):
        """process_document calls process_batch with a single-element list."""
        mock_process_batch.return_value = {
            "test.pdf": {"status": "ok", "doc_id": 1, "doc_type": "cmr"},
        }
        result = service.process_document("/path/to/test.pdf")
        mock_process_batch.assert_called_once_with(["/path/to/test.pdf"], None)
        assert result["doc_id"] == 1

    @patch("services.migration.physical_archive_service.PhysicalArchiveService.process_batch")
    def test_process_document_returns_unknown_on_missing_key(self, mock_process_batch, service):
        """If batch result lacks the filename key, return an error dict."""
        mock_process_batch.return_value = {}
        result = service.process_document("/path/to/missing.pdf")
        assert result["status"] == "error"


# ── process_batch ────────────────────────────────────────────────────────

class TestProcessBatch:
    """Tests for PhysicalArchiveService.process_batch."""

    @patch("services.migration.physical_archive_service.os.path.isfile")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_handles_empty_list(self, mock_doc_svc, mock_isfile, service):
        """An empty file list returns an empty results dict."""
        results = service.process_batch([])
        assert results == {}

    @patch("services.migration.physical_archive_service.os.path.isfile", return_value=False)
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_handles_file_not_found_per_file(
        self, mock_doc_svc, mock_isfile, service,
    ):
        """A non-existent file gets a FileNotFound error in its result."""
        results = service.process_batch(["/path/to/nonexistent.pdf"])
        entry = results.get("/path/to/nonexistent.pdf")
        assert entry is not None
        assert entry["error"] is not None
        assert "File not found" in entry["error"]

    @patch("services.migration.physical_archive_service.os.path.isfile", return_value=True)
    @patch("services.migration.physical_archive_service.run_for_existing_document")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_ocr_failure_produces_error_entry(
        self, mock_doc_svc, mock_run, mock_isfile, service,
    ):
        """When run_for_existing_document raises, the entry has an error."""
        mock_doc_svc.upload.return_value = 99
        mock_run.side_effect = RuntimeError("OCR engine crashed")
        results = service.process_batch(["/path/to/doc.pdf"])
        entry = results.get("/path/to/doc.pdf")
        assert entry is not None
        assert "OCR failed" in entry["error"]

    @patch("services.migration.physical_archive_service.os.path.isfile", return_value=True)
    @patch("services.migration.physical_archive_service.run_for_existing_document")
    @patch("services.migration.physical_archive_service.TripMatcher")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_successful_cmr_flow(
        self, mock_doc_svc, mock_trip_matcher_cls, mock_run, mock_isfile, service,
    ):
        """A successful CMR document goes through the full pipeline."""
        mock_doc_svc.upload.return_value = 42
        mock_run.return_value = {
            "extracted": {"cmr_number": "CMR-001"},
            "confidence": 0.92,
            "ocr_text": "CMR for transport",
        }
        fake_matcher = MagicMock()
        fake_matcher.confidence = 0.88
        fake_matcher.best_match = {"trip_id": 7}
        fake_candidate = MagicMock()
        fake_candidate.trip = {"id": 7}
        fake_candidate.confidence = 0.88
        fake_matcher.candidates = [fake_candidate]
        fake_matcher.match.return_value = fake_matcher
        mock_trip_matcher_cls.return_value = fake_matcher

        results = service.process_batch(["/path/to/cmr.pdf"])
        entry = results.get("/path/to/cmr.pdf")
        assert entry is not None
        assert entry["doc_id"] == 42
        assert entry["doc_type"] == "cmr"
        assert entry["confidence"] == 0.92
        assert entry["needs_confirmation"] is False  # 0.92 >= 0.75
        assert entry["match_result"]["best_match"]["trip_id"] == 7

    @patch("services.migration.physical_archive_service.os.path.isfile", return_value=True)
    @patch("services.migration.physical_archive_service.run_for_existing_document")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_low_confidence_needs_confirmation(
        self, mock_doc_svc, mock_run, mock_isfile, service,
    ):
        """Confidence below 0.75 sets needs_confirmation to True."""
        mock_doc_svc.upload.return_value = 43
        mock_run.return_value = {
            "extracted": {"cmr_number": "CMR-002"},
            "confidence": 0.50,
            "ocr_text": "CMR",
        }
        results = service.process_batch(["/path/to/lowconf.pdf"])
        entry = results.get("/path/to/lowconf.pdf")
        assert entry["needs_confirmation"] is True

    @patch("services.migration.physical_archive_service.os.path.isfile", return_value=True)
    @patch("services.migration.physical_archive_service.run_for_existing_document")
    @patch("services.migration.physical_archive_service.TripMatcher")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_trip_match_failure_does_not_block(
        self, mock_doc_svc, mock_trip_matcher_cls, mock_run, mock_isfile, service,
    ):
        """Trip matching failure for CMR/invoice produces an error in match_result but does not break the pipeline."""
        mock_doc_svc.upload.return_value = 44
        mock_run.return_value = {
            "extracted": {"cmr_number": "CMR-003"},
            "confidence": 0.80,
            "ocr_text": "CMR stuff",
        }
        fake_matcher = MagicMock()
        fake_matcher.match.side_effect = ValueError("No trips found")
        mock_trip_matcher_cls.return_value = fake_matcher

        results = service.process_batch(["/path/to/cmr_no_match.pdf"])
        entry = results.get("/path/to/cmr_no_match.pdf")
        assert entry["match_result"]["error"] == "No trips found"

    @patch("services.migration.physical_archive_service.os.path.isfile", return_value=True)
    @patch("services.migration.physical_archive_service.run_for_existing_document")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_process_batch_upload_failure_sets_error(
        self, mock_doc_svc, mock_run, mock_isfile, service,
    ):
        """When upload returns None/falsy, an error is recorded."""
        mock_doc_svc.upload.return_value = None
        results = service.process_batch(["/path/to/fail.pdf"])
        entry = results.get("/path/to/fail.pdf")
        assert entry["error"] is not None
        assert "no ID" in entry["error"].lower() or "returned no" in entry["error"].lower()


# ── confirm_document ─────────────────────────────────────────────────────

class TestConfirmDocument:
    """Tests for PhysicalArchiveService.confirm_document."""

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_confirm_document_updates_extracted_data(
        self, mock_doc_svc, mock_repo_cls, service,
    ):
        """Corrections are merged into extracted_data_json and saved."""
        fake_repo = MagicMock()
        fake_repo.get_by_id.return_value = {
            "extracted_data_json": '{"cmr_number": "OLD"}',
        }
        mock_repo_cls.return_value = fake_repo

        result = service.confirm_document(doc_id=1, corrections={"cmr_number": "NEW"})
        assert result is True

        # repo.update should have been called with merged JSON (keyword arg)
        import json
        merged = json.loads(
            fake_repo.update.call_args.kwargs["extracted_data_json"]
        )
        assert merged["cmr_number"] == "NEW"

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_confirm_document_links_to_trip(
        self, mock_doc_svc, mock_repo_cls, service,
    ):
        """When trip_id is provided, doc_svc.link_document is called."""
        fake_repo = MagicMock()
        fake_repo.get_by_id.return_value = {
            "extracted_data_json": "{}",
        }
        mock_repo_cls.return_value = fake_repo

        result = service.confirm_document(doc_id=2, corrections={}, trip_id=15)
        assert result is True

        mock_doc_svc.link_document.assert_called_once_with(
            doc_id=2,
            entity_type="trip",
            entity_id=15,
            relation_type="attached",
        )

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_confirm_document_not_found_returns_false(
        self, mock_doc_svc, mock_repo_cls, service,
    ):
        """When the document does not exist, return False."""
        fake_repo = MagicMock()
        fake_repo.get_by_id.return_value = None
        mock_repo_cls.return_value = fake_repo

        result = service.confirm_document(doc_id=999)
        assert result is False

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_confirm_document_handles_invalid_json(
        self, mock_doc_svc, mock_repo_cls, service,
    ):
        """If extracted_data_json is invalid, start fresh."""
        fake_repo = MagicMock()
        fake_repo.get_by_id.return_value = {
            "extracted_data_json": "not valid json",
        }
        mock_repo_cls.return_value = fake_repo

        result = service.confirm_document(doc_id=3, corrections={"key": "val"})
        assert result is True

        import json
        merged = json.loads(
            fake_repo.update.call_args.kwargs["extracted_data_json"]
        )
        assert merged == {"key": "val"}

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.migration.physical_archive_service.PhysicalArchiveService.doc_svc")
    def test_confirm_document_no_corrections_keeps_existing(
        self, mock_doc_svc, mock_repo_cls, service,
    ):
        """With no corrections, existing extracted data is preserved unchanged."""
        fake_repo = MagicMock()
        fake_repo.get_by_id.return_value = {
            "extracted_data_json": '{"cmr_number": "EXISTING"}',
        }
        mock_repo_cls.return_value = fake_repo

        result = service.confirm_document(doc_id=4, corrections=None)
        assert result is True

        import json
        merged = json.loads(
            fake_repo.update.call_args.kwargs["extracted_data_json"]
        )
        assert merged == {"cmr_number": "EXISTING"}
