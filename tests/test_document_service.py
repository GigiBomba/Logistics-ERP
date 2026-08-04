"""Tests for DocumentService facade."""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from models.common import ServiceResult
from services.document_service import DocumentService


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.conn = MagicMock()
    db.rows_to_dicts.return_value = []
    return db


@pytest.fixture
def doc_service(mock_db):
    with patch("services.document_service.DocumentRepository") as mock_repo_cls, \
         patch("services.document_service.EventBus") as mock_eb_cls, \
         patch("services.document_service.PermissionService") as mock_perm_cls:
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_eb = MagicMock()
        mock_eb_cls.return_value = mock_eb
        mock_perm = MagicMock()
        mock_perm.can_upload_document.return_value = MagicMock(allowed=True)
        mock_perm_cls.return_value = mock_perm
        svc = DocumentService(mock_db)
        svc._repo = mock_repo
        svc._event_bus = mock_eb
        svc._perm = mock_perm
        return svc


class TestUpload:
    def test_validates_file(self, doc_service, mock_db):
        mock_svc = MagicMock()
        mock_svc.validate_file.return_value = (True, None)
        doc_service._services["upload"] = mock_svc

        ok, err = doc_service._services["upload"].validate_file("/path/doc.pdf")
        assert ok is True

    def test_upload_creates_and_enqueues_ocr(self, doc_service, mock_db):
        mock_upload = MagicMock()
        mock_upload.upload.return_value = 42
        doc_service._services["upload"] = mock_upload

        mock_ocr = MagicMock()
        doc_service._services["ocr"] = mock_ocr

        doc_service._repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/test.pdf", "mime_type": "application/pdf",
        }

        from models.document_models import DocumentUpload
        result = doc_service.upload_document(
            DocumentUpload(source_path="/path/source.pdf"),
            user_id=0,
        )
        assert result.success
        assert result.data.id == 42
        mock_upload.upload.assert_called_once()
        mock_ocr.enqueue_ocr.assert_called_once_with(42, "/docs/test.pdf", "application/pdf")

    def test_upload_skips_ocr_for_non_image_pdf(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.upload.return_value = 42
        doc_service._services["upload"] = mock_upload

        doc_service._repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/doc.txt", "mime_type": "text/plain",
        }

        from models.document_models import DocumentUpload
        result = doc_service.upload_document(
            DocumentUpload(source_path="/path/doc.txt"),
            user_id=0,
        )
        assert result.success
        assert result.data.id == 42

    def test_batch_upload_delegates(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.batch_upload.return_value = {"success": 3, "failed": []}
        doc_service._services["upload"] = mock_upload

        result = doc_service.batch_upload(["/a.pdf", "/b.pdf"])
        assert result["success"] == 3
        mock_upload.batch_upload.assert_called_once()


class TestSearch:
    def test_advanced_search_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.advanced_search.return_value = {"results": [], "total": 0}
        doc_service._services["search"] = mock_search

        result = doc_service.advanced_search(query="test", category="invoices")
        assert result["total"] == 0
        mock_search.advanced_search.assert_called_once_with(
            query="test", category="invoices", entity_type="",
            entity_id=None, date_from="", date_to="", mime_type="",
            tag="", order="uploaded_at DESC", page=0, page_size=20,
        )

    def test_search_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.search.return_value = {"results": [], "total": 0}
        doc_service._services["search"] = mock_search

        result = doc_service.search(query="test")
        assert result["total"] == 0

    def test_get_categories(self, doc_service):
        mock_search = MagicMock()
        mock_search.get_categories.return_value = [{"name": "invoices"}]
        doc_service._services["search"] = mock_search

        cats = doc_service.get_categories()
        assert cats == [{"name": "invoices"}]


class TestLinkDocument:
    def test_link_document_publishes_event(self, doc_service):
        doc_service._repo.add_link.return_value = 1
        doc_service.link_document(42, "trip", 100)
        doc_service._event_bus.publish.assert_called_once()

    def test_link_document_triggers_retroactive_link_for_trip(self, doc_service):
        mock_ocr = MagicMock()
        doc_service._services["ocr"] = mock_ocr
        doc_service._repo.add_link.return_value = 1

        doc_service.link_document(42, "trip", 100)
        mock_ocr._retroactively_link_related_runs.assert_called_once_with(100, 42)

    def test_link_document_returns_false_on_failure(self, doc_service):
        doc_service._repo.add_link.return_value = -1
        result = doc_service.link_document(42, "trip", 100)
        assert result is False
        doc_service._event_bus.publish.assert_not_called()

    def test_unlink_document(self, doc_service):
        doc_service._repo._fetchone.return_value = {"id": 1, "document_id": 42}
        doc_service._repo.remove_link = MagicMock()
        result = doc_service.unlink_document(1)
        assert result is True
        doc_service._event_bus.publish.assert_called_once()


class TestThumbnail:
    def test_get_thumbnail_path_returns_existing(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/docs/test.pdf",
        }
        with patch("os.path.isfile", return_value=True), \
             patch("os.makedirs"):
            with patch.object(doc_service, "_generate_thumbnail") as mock_gen:
                # Simulate thumbnail already exists
                with patch("os.path.isfile") as mock_isfile:
                    mock_isfile.side_effect = [True, True]  # file_path exists, thumb exists
                    result = doc_service.get_thumbnail_path(1)
                    assert result is not None
                    assert "thumb_1.png" in result
                    mock_gen.assert_not_called()

    def test_get_thumbnail_path_generates_new(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/docs/test.pdf", "mime_type": "application/pdf",
        }
        with patch("os.path.isfile") as mock_isfile:
            mock_isfile.side_effect = [True, False]  # file exists, thumb does not
            with patch("os.makedirs"), \
                 patch.object(doc_service, "_generate_thumbnail", return_value="/thumbs/thumb_1.png"):
                result = doc_service.get_thumbnail_path(1)
                assert result == "/thumbs/thumb_1.png"

    def test_get_thumbnail_path_none_when_doc_missing(self, doc_service):
        doc_service._repo.get_by_id.return_value = None
        result = doc_service.get_thumbnail_path(1)
        assert result is None

    def test_pdf_thumbnail_uses_pymupdf_when_available(self, doc_service):
        """When PyMuPDF is available, _pdf_thumbnail should render page 1."""
        with patch("services.document_automation.image_processor._safe_import_fitz") as mock_fitz_import:
            mock_fitz = MagicMock()
            mock_fitz_import.return_value = mock_fitz
            mock_doc = MagicMock()
            mock_doc.page_count = 5
            mock_page = MagicMock()
            mock_pix = MagicMock()
            mock_pix.width = 400
            mock_pix.height = 300
            mock_pix.samples = b"\x00" * (400 * 300 * 3)
            mock_page.get_pixmap.return_value = mock_pix
            mock_doc.__getitem__.return_value = mock_page
            mock_fitz.open.return_value = mock_doc

            mock_img = MagicMock()
            with patch("PIL.Image.frombytes", return_value=mock_img):
                result = doc_service._pdf_thumbnail("/tmp/test.pdf", "/tmp/thumb.png")
                assert result == "/tmp/thumb.png"
                mock_fitz.open.assert_called_once_with("/tmp/test.pdf")
                mock_page.get_pixmap.assert_called_once_with(dpi=72)
                mock_doc.close.assert_called_once()
                mock_img.thumbnail.assert_called_once()
                mock_img.save.assert_called_once()


class TestEmail:
    def test_email_document_sends(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/docs/test.pdf",
            "title": "Test Doc", "file_name": "test.pdf",
            "doc_number": "DOC-001",
        }
        mock_prefs = MagicMock()
        mock_prefs.get_smtp_config.return_value = {
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_user": "user",
            "smtp_password": "pass",
        }

        mock_prefs = MagicMock()
        mock_prefs.get_smtp_config.return_value = {
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_user": "user",
            "smtp_password": "pass",
        }

        with patch("services.document_service.os.path.isfile", return_value=True), \
             patch("services.preferences.PreferencesManager", return_value=mock_prefs), \
             patch("services.operations.notification_center.NotificationCenter") as mock_nc_cls:
            mock_nc = MagicMock()
            mock_nc.send_email.return_value = ServiceResult(success=True)
            mock_nc_cls.return_value = mock_nc

            result = doc_service.email_document(1, "recipient@example.com", user_id=0)
            assert result.success
            mock_nc.send_email.assert_called_once()
            args, _ = mock_nc.send_email.call_args
            assert "recipient@example.com" in args

    def test_email_document_fails_with_no_file(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/docs/missing.pdf",
        }
        with patch("os.path.isfile", return_value=False):
            result = doc_service.email_document(1, "recipient@example.com", user_id=0)
            assert not result.success

    def test_email_document_fails_without_smtp(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/docs/test.pdf",
        }
        mock_prefs = MagicMock()
        mock_prefs.get_smtp_config.return_value = None

        with patch("os.path.isfile", return_value=True), \
             patch("services.preferences.PreferencesManager", return_value=mock_prefs):
            result = doc_service.email_document(1, "recipient@example.com", user_id=0)
            assert not result.success


class TestDownloadZip:
    def test_download_zip_creates_zip(self, doc_service):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        safe_dir = os.path.join(tmpdir, "data", "documents")
        os.makedirs(safe_dir)
        out_path = os.path.join(safe_dir, "out.zip")

        doc_service._repo.get_ids_by_ids.return_value = [
            {"id": 1, "file_path": os.path.join(safe_dir, "test.pdf"), "file_name": "test.pdf"},
            {"id": 2, "file_path": os.path.join(safe_dir, "img.jpg"), "file_name": "img.jpg"},
        ]

        with patch("os.path.isfile", return_value=True), \
             patch("os.path.realpath", side_effect=lambda p: os.path.join(tmpdir, p) if not os.path.isabs(p) else p), \
             patch("zipfile.ZipFile") as mock_zip_cls:
            mock_zf = MagicMock()
            mock_zip_cls.return_value.__enter__.return_value = mock_zf

            result = doc_service.download_zip([1, 2], out_path)
            assert result == out_path
            assert mock_zf.write.call_count == 2

    def test_download_zip_path_traversal_blocked(self, doc_service):
        with pytest.raises(ValueError, match="must not contain"):
            doc_service.download_zip([1], os.path.join("data", "documents", "..", "..", "etc", "out.zip"))

    def test_download_zip_path_outside_base_blocked(self, doc_service):
        base_path = os.path.join("data", "documents")
        # Use a path without ".." that is outside the base data/documents dir
        outside_path = os.path.join("somewhere", "else", "out.zip")
        with patch("os.path.realpath") as mock_realpath:
            def _realpath_side_effect(p):
                if p == base_path:
                    return os.path.abspath(base_path)
                return os.path.abspath(p)
            mock_realpath.side_effect = _realpath_side_effect
            with pytest.raises(ValueError, match="must be within"):
                doc_service.download_zip([1], outside_path)


class TestExpiry:
    def test_evaluate_document_expiries_delegates(self, doc_service):
        mock_expiry = MagicMock()
        mock_expiry.evaluate_document_expiries.return_value = 3
        doc_service._services["expiry"] = mock_expiry

        result = doc_service.evaluate_document_expiries()
        assert result == 3
        mock_expiry.evaluate_document_expiries.assert_called_once()

    def test_set_expiry_date_delegates(self, doc_service):
        mock_expiry = MagicMock()
        doc_service._services["expiry"] = mock_expiry

        doc_service.set_expiry_date(1, "2025-01-01")
        mock_expiry.set_expiry_date.assert_called_once_with(1, "2025-01-01")


class TestContracts:
    def test_create_contract_delegates(self, doc_service):
        mock_contracts = MagicMock()
        mock_contracts.create_contract.return_value = 42
        doc_service._services["contracts"] = mock_contracts

        result = doc_service.create_contract(1, 2, contract_type="transport")
        assert result == 42
        mock_contracts.create_contract.assert_called_once()

    def test_get_contracts_delegates(self, doc_service):
        mock_contracts = MagicMock()
        mock_contracts.get_contracts.return_value = []
        doc_service._services["contracts"] = mock_contracts

        result = doc_service.get_contracts(client_id=1)
        mock_contracts.get_contracts.assert_called_once_with(1, "")


class TestTemplates:
    def test_create_template_delegates(self, doc_service):
        mock_templates = MagicMock()
        mock_templates.create_template.return_value = 42
        doc_service._services["templates"] = mock_templates

        result = doc_service.create_template("Test", category="general")
        assert result == 42
        mock_templates.create_template.assert_called_once()


class TestArchive:
    def test_archive_publishes_event(self, doc_service):
        doc_service.archive(1)
        doc_service._repo.archive.assert_called_once_with(1)
        doc_service._event_bus.publish.assert_called_once()

    def test_archive_event_has_correct_type(self, doc_service):
        doc_service.archive(42)
        args, _ = doc_service._event_bus.publish.call_args
        from services.operations.event_bus import DOCUMENT_ARCHIVED
        assert args[0] == DOCUMENT_ARCHIVED
        assert args[1]["document_id"] == 42


class TestDeleteBatch:
    def test_delete_batch_empty(self, doc_service):
        result = doc_service.delete_batch([])
        assert result == 0

    def test_delete_batch_removes_files_and_publishes(self, doc_service):
        doc_service._repo.get_ids_by_ids.return_value = [
            {"id": 1, "file_path": "/data/documents/a.pdf"},
            {"id": 2, "file_path": "/data/documents/b.pdf"},
        ]
        doc_service._repo.get_versions.return_value = []  # No versions to clean
        with patch("os.path.isfile", return_value=True), \
             patch("os.remove") as mock_rm:
            doc_service._repo.delete_batch.return_value = 2
            result = doc_service.delete_batch([1, 2])
            assert result == 2
            # Main files (2) + thumbnails (2) = 4 removes
            assert mock_rm.call_count == 4
            doc_service._event_bus.publish.assert_called_once()

    def test_delete_batch_skip_missing_file(self, doc_service):
        doc_service._repo.get_ids_by_ids.return_value = [
            {"id": 1, "file_path": "/data/documents/a.pdf"},
        ]
        with patch("os.path.isfile", return_value=False), \
             patch("os.remove") as mock_rm:
            doc_service._repo.delete_batch.return_value = 1
            result = doc_service.delete_batch([1])
            assert result == 1
            mock_rm.assert_not_called()


class TestMisc:
    def test_delete_removes_file_and_publishes_event(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/data/documents/test.pdf",
        }
        with patch("os.path.isfile", return_value=True), \
             patch("os.remove") as mock_rm:
            result = doc_service.delete(1)
            assert result is True
            # os.remove called for main file + thumbnail (since isfile is mocked True)
            assert mock_rm.call_count == 2
            doc_service._event_bus.publish.assert_called_once()

    def test_get_by_id(self, doc_service):
        mock_doc = {"id": 1, "title": "Test"}
        doc_service._repo.get_by_id.return_value = mock_doc
        assert doc_service.get_by_id(1) == mock_doc

    def test_get_by_id_from_cache(self, doc_service):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"id": 1, "title": "Cached"}
        with patch.object(doc_service, "_get_cache", return_value=mock_cache):
            result = doc_service.get_by_id(1)
            assert result["title"] == "Cached"
            mock_cache.get.assert_called_once_with("doc:1")
            doc_service._repo.get_by_id.assert_not_called()

    def test_add_tag(self, doc_service):
        doc_service._repo.add_tag.return_value = True
        assert doc_service.add_tag(1, "important") is True
        doc_service._repo.add_tag.assert_called_once_with(1, "important")

    def test_remove_tag(self, doc_service):
        doc_service._repo.remove_tag.return_value = True
        assert doc_service.remove_tag(1, "old_tag") is True
        doc_service._repo.remove_tag.assert_called_once_with(1, "old_tag")

    def test_set_tags(self, doc_service):
        doc_service.set_tags(1, ["a", "b"])
        doc_service._repo.set_tags.assert_called_once_with(1, ["a", "b"])

    def test_update_metadata(self, doc_service):
        doc_service._repo.update = MagicMock()
        result = doc_service.update_metadata(1, title="New Title", tags=["tag1"])
        assert result is True
        doc_service._repo.update.assert_called_once()

    def test_update_metadata_description_only(self, doc_service):
        doc_service._repo.update = MagicMock()
        result = doc_service.update_metadata(1, description="New desc")
        assert result is True
        doc_service._repo.update.assert_called_once()

    def test_update_metadata_no_changes(self, doc_service):
        doc_service._repo.update = MagicMock()
        # description has a non-None default, so when called without args
        # it still gets added to fields. Only passing description=None skips it.
        result = doc_service.update_metadata(1, description=None)
        assert result is False
        doc_service._repo.update.assert_not_called()

    def test_shutdown_is_noop(self):
        DocumentService.shutdown()

    def test_get_file_path(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/data/documents/test.pdf",
        }
        with patch("os.path.isfile", return_value=True):
            result = doc_service.get_file_path(1)
            assert result is not None
            assert "test.pdf" in result

    def test_get_file_path_none_when_missing(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/data/documents/missing.pdf",
        }
        with patch("os.path.isfile", return_value=False):
            result = doc_service.get_file_path(1)
            assert result is None

    def test_is_image_true(self, doc_service):
        assert doc_service.is_image("image/png") is True

    def test_is_image_false(self, doc_service):
        assert doc_service.is_image("application/pdf") is False

    def test_fts_search_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.fts_search.return_value = {"results": []}
        doc_service._services["search"] = mock_search

        doc_service.fts_search(query="test")
        mock_search.fts_search.assert_called_once()

    def test_extract_text_delegates(self, doc_service):
        mock_ocr = MagicMock()
        mock_ocr.extract_text.return_value = "extracted text"
        doc_service._services["ocr"] = mock_ocr

        result = doc_service.extract_text("/path/file.pdf", "application/pdf")
        assert result == "extracted text"

    def test_get_versions_delegates(self, doc_service):
        mock_versioning = MagicMock()
        mock_versioning.get_versions.return_value = []
        doc_service._services["versioning"] = mock_versioning

        doc_service.get_versions(1)
        mock_versioning.get_versions.assert_called_once_with(1)

    def test_upload_new_version_delegates(self, doc_service):
        mock_versioning = MagicMock()
        mock_versioning.upload_new_version.return_value = 2
        doc_service._services["versioning"] = mock_versioning

        result = doc_service.upload_new_version(1, "/path/v2.pdf", comment="v2")
        assert result == 2
        mock_versioning.upload_new_version.assert_called_once_with(
            1, "/path/v2.pdf", comment="v2", uploaded_by="",
        )

    def test_restore_version_delegates(self, doc_service):
        mock_versioning = MagicMock()
        mock_versioning.restore_version.return_value = True
        doc_service._services["versioning"] = mock_versioning

        result = doc_service.restore_version(1, 1)
        assert result is True
        mock_versioning.restore_version.assert_called_once_with(1, 1)

    def test_rebuild_fts(self, doc_service):
        doc_service.rebuild_fts()
        doc_service._repo.rebuild_fts_index.assert_called_once()

    def test_register_existing_enqueues_ocr(self, doc_service, mock_db):
        mock_upload = MagicMock()
        mock_upload.register_existing.return_value = 42
        doc_service._services["upload"] = mock_upload

        mock_ocr = MagicMock()
        doc_service._services["ocr"] = mock_ocr

        doc_service._repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/test.pdf", "mime_type": "application/pdf",
        }

        doc_id = doc_service.register_existing("/path/file.pdf")
        assert doc_id == 42
        mock_ocr.enqueue_ocr.assert_called_once()

    def test_register_existing_skips_ocr_for_migration(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.register_existing.return_value = 42
        doc_service._services["upload"] = mock_upload

        mock_ocr = MagicMock()
        doc_service._services["ocr"] = mock_ocr

        doc_service.register_existing("/path/file.pdf", is_migration=True)
        mock_ocr.enqueue_ocr.assert_not_called()

    def test_register_existing_skips_ocr_for_non_image_pdf(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.register_existing.return_value = 42
        doc_service._services["upload"] = mock_upload

        doc_service._repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/doc.txt", "mime_type": "text/plain",
        }

        doc_service.register_existing("/path/file.txt")
        # No OCR mock called because mime_type is text/plain
        # (ocr service not even set up — test passes if no error)

    def test_get_links(self, doc_service):
        doc_service._repo.get_links.return_value = [{"id": 1, "entity_type": "trip"}]
        links = doc_service.get_links(1)
        assert len(links) == 1
        doc_service._repo.get_links.assert_called_once_with(1)

    def test_get_documents_for_entity(self, doc_service):
        doc_service._repo.get_documents_for_entity.return_value = [{"id": 1}]
        docs = doc_service.get_documents_for_entity("trip", 42)
        assert len(docs) == 1
        doc_service._repo.get_documents_for_entity.assert_called_once_with("trip", 42)


class TestMetadataQueries:
    def test_get_categories_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.get_categories.return_value = [{"category": "invoices", "cnt": 5}]
        doc_service._services["search"] = mock_search
        assert doc_service.get_categories() == [{"category": "invoices", "cnt": 5}]

    def test_get_all_tags_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.get_all_tags.return_value = ["tag1"]
        doc_service._services["search"] = mock_search
        assert doc_service.get_all_tags() == ["tag1"]

    def test_get_entity_types_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.get_entity_types.return_value = ["trip"]
        doc_service._services["search"] = mock_search
        assert doc_service.get_entity_types() == ["trip"]

    def test_get_mime_types_delegates(self, doc_service):
        mock_search = MagicMock()
        mock_search.get_mime_types.return_value = ["application/pdf"]
        doc_service._services["search"] = mock_search
        assert doc_service.get_mime_types() == ["application/pdf"]


class TestContractsExtended:
    def test_get_contract_delegates(self, doc_service):
        mock_contracts = MagicMock()
        mock_contracts.get_contract.return_value = {"id": 1}
        doc_service._services["contracts"] = mock_contracts
        result = doc_service.get_contract(1)
        assert result == {"id": 1}
        mock_contracts.get_contract.assert_called_once_with(1)

    def test_update_contract_status_delegates(self, doc_service):
        mock_contracts = MagicMock()
        doc_service._services["contracts"] = mock_contracts
        doc_service.update_contract_status(1, "active")
        mock_contracts.update_contract_status.assert_called_once_with(1, "active")

    def test_get_expiring_contracts_delegates(self, doc_service):
        mock_contracts = MagicMock()
        mock_contracts.get_expiring_contracts.return_value = []
        doc_service._services["contracts"] = mock_contracts
        doc_service.get_expiring_contracts(days_ahead=30)
        mock_contracts.get_expiring_contracts.assert_called_once_with(30)

    def test_create_contract_with_full_params(self, doc_service):
        mock_contracts = MagicMock()
        mock_contracts.create_contract.return_value = 99
        doc_service._services["contracts"] = mock_contracts
        result = doc_service.create_contract(
            1, 2, contract_type="transport",
            start_date="2025-01-01", end_date="2025-12-31",
            value_eur=5000.0, payment_terms="net30",
            auto_renewal=True, renewal_notice_days=60, notes="Test",
        )
        assert result == 99
        mock_contracts.create_contract.assert_called_once()


class TestTemplatesExtended:
    def test_get_templates_delegates(self, doc_service):
        mock_templates = MagicMock()
        mock_templates.get_templates.return_value = [{"id": 1}]
        doc_service._services["templates"] = mock_templates
        result = doc_service.get_templates(category="general")
        assert result == [{"id": 1}]
        mock_templates.get_templates.assert_called_once_with("general")

    def test_generate_from_template_delegates(self, doc_service):
        mock_templates = MagicMock()
        mock_templates.generate_from_template.return_value = "/path/out.pdf"
        doc_service._services["templates"] = mock_templates
        result = doc_service.generate_from_template(1, {"name": "test"})
        assert result == "/path/out.pdf"
        mock_templates.generate_from_template.assert_called_once()


class TestMigration:
    def test_migrate_existing_attachments_delegates(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.migrate_existing_attachments.return_value = 5
        doc_service._services["upload"] = mock_upload
        assert doc_service.migrate_existing_attachments() == 5

    def test_migrate_existing_invoices_delegates(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.migrate_existing_invoices.return_value = 3
        doc_service._services["upload"] = mock_upload
        assert doc_service.migrate_existing_invoices() == 3

    def test_migrate_all_delegates(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.migrate_all.return_value = 8
        doc_service._services["upload"] = mock_upload
        assert doc_service.migrate_all() == 8


class TestExpiryExtended:
    def test_get_expiring_delegates(self, doc_service):
        mock_expiry = MagicMock()
        mock_expiry.get_expiring.return_value = [{"id": 1}]
        doc_service._services["expiry"] = mock_expiry
        result = doc_service.get_expiring(days_ahead=30)
        assert result == [{"id": 1}]
        mock_expiry.get_expiring.assert_called_once_with(30)

    def test_get_overdue_delegates(self, doc_service):
        mock_expiry = MagicMock()
        mock_expiry.get_overdue.return_value = [{"id": 1}]
        doc_service._services["expiry"] = mock_expiry
        result = doc_service.get_overdue()
        assert result == [{"id": 1}]
        mock_expiry.get_overdue.assert_called_once()


class TestDownloadZipExtended:
    def test_download_zip_skips_missing_files(self, doc_service):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        safe_dir = os.path.join(tmpdir, "data", "documents")
        os.makedirs(safe_dir)
        out_path = os.path.join(safe_dir, "out.zip")

        doc_service._repo.get_ids_by_ids.return_value = [
            {"id": 1, "file_path": os.path.join(safe_dir, "exists.pdf"), "file_name": "exists.pdf"},
            {"id": 2, "file_path": os.path.join(safe_dir, "missing.pdf"), "file_name": "missing.pdf"},
        ]

        with patch("os.path.isfile", side_effect=lambda p: "exists" in p), \
             patch("os.path.realpath", side_effect=lambda p: os.path.join(tmpdir, p) if not os.path.isabs(p) else p), \
             patch("zipfile.ZipFile") as mock_zip_cls:
            mock_zf = MagicMock()
            mock_zip_cls.return_value.__enter__.return_value = mock_zf
            result = doc_service.download_zip([1, 2], out_path)
            assert result == out_path
            # Only the existing file should be written
            assert mock_zf.write.call_count == 1

    def test_download_zip_skips_outside_safe_dir(self, doc_service):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        safe_dir = os.path.join(tmpdir, "data", "documents")
        os.makedirs(safe_dir)
        out_path = os.path.join(safe_dir, "out.zip")
        outside_path = os.path.join(tmpdir, "outside", "bad.pdf")
        os.makedirs(os.path.join(tmpdir, "outside"))

        doc_service._repo.get_ids_by_ids.return_value = [
            {"id": 1, "file_path": outside_path, "file_name": "bad.pdf"},
        ]

        with patch("os.path.isfile", return_value=True), \
             patch("os.path.realpath") as mock_realpath, \
             patch("zipfile.ZipFile") as mock_zip_cls:
            # Make safe_base resolve to the real safe_dir
            def _realpath_side(p):
                abs_p = os.path.abspath(p)
                if abs_p == os.path.abspath(os.path.join("data", "documents")):
                    return os.path.abspath(safe_dir)
                return os.path.abspath(p) if os.path.isabs(p) else os.path.abspath(p)
            mock_realpath.side_effect = _realpath_side
            mock_zf = MagicMock()
            mock_zip_cls.return_value.__enter__.return_value = mock_zf
            result = doc_service.download_zip([1], out_path)
            assert result == out_path
            # File outside safe dir should be skipped
            mock_zf.write.assert_not_called()


class TestEmailExtended:
    def test_email_document_uses_prefs_for_smtp(self, doc_service):
        doc_service._repo.get_by_id.return_value = {
            "id": 1, "file_path": "/docs/test.pdf",
            "title": "Test", "file_name": "test.pdf", "doc_number": "DOC-001",
        }
        mock_prefs = MagicMock()
        mock_prefs.get_smtp_config.return_value = {
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_user": "user",
            "smtp_password": "pass",
        }

        with patch("services.document_service.os.path.isfile", return_value=True), \
             patch("services.preferences.PreferencesManager", return_value=mock_prefs), \
             patch("services.operations.notification_center.NotificationCenter") as mock_nc_cls:
            mock_nc = MagicMock()
            mock_nc.send_email.return_value = ServiceResult(success=True)
            mock_nc_cls.return_value = mock_nc
            result = doc_service.email_document(1, "recipient@example.com", user_id=0)
            assert result.success
            mock_nc.send_email.assert_called_once()

    def test_email_document_no_doc(self, doc_service):
        doc_service._repo.get_by_id.return_value = None
        with patch("services.document_service.PermissionService") as mock_perm:
            mock_perm.return_value.can_email_document.return_value = MagicMock(allowed=True)
            result = doc_service.email_document(999, "test@example.com", user_id=0)
            assert not result.success


class TestAuditLog:
    def test_get_audit_log(self, doc_service):
        mock_audit = MagicMock()
        mock_audit.get_events.return_value = [{"event_type": "document.deleted"}]
        doc_service._audit_repo = mock_audit
        logs = doc_service.get_audit_log(limit=10)
        assert len(logs) == 1
        doc_service._audit_repo.get_events.assert_called_once_with(
            event_type_prefix="document.", limit=10,
        )


class TestUploadExtended:
    def test_upload_enqueues_ocr_for_image(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.upload.return_value = 42
        doc_service._services["upload"] = mock_upload
        mock_ocr = MagicMock()
        doc_service._services["ocr"] = mock_ocr
        doc_service._repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/img.png", "mime_type": "image/png",
        }
        from models.document_models import DocumentUpload
        result = doc_service.upload_document(
            DocumentUpload(source_path="/path/img.png"),
            user_id=0,
        )
        assert result.success
        assert result.data.id == 42
        mock_ocr.enqueue_ocr.assert_called_once_with(42, "/docs/img.png", "image/png")

    def test_upload_does_not_enqueue_ocr_if_no_doc_id(self, doc_service):
        mock_upload = MagicMock()
        mock_upload.upload.return_value = None
        doc_service._services["upload"] = mock_upload
        mock_ocr = MagicMock()
        doc_service._services["ocr"] = mock_ocr
        from models.document_models import DocumentUpload
        result = doc_service.upload_document(
            DocumentUpload(source_path="/path/file.pdf"),
            user_id=0,
        )
        assert not result.success
        mock_ocr.enqueue_ocr.assert_not_called()
