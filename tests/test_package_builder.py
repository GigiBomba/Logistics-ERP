"""Tests for PackageBuilder service."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from services.document_automation.package_builder import Package, PackageBuilder


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.conn = MagicMock()
    return db


@pytest.fixture
def builder(mock_db):
    with patch("services.document_automation.package_builder.DocumentRepository"), \
         patch("services.document_automation.package_builder.TripRepository"), \
         patch("services.document_automation.package_builder.PipelineRepository"):
        return PackageBuilder(mock_db)


class TestListTripDocuments:
    def test_list_documents_from_links(self, builder):
        builder.docs.get_documents_for_entity.return_value = [
            {"id": 1, "doc_number": "DOC-001", "title": "CMR", "file_path": "/docs/cmr.pdf",
             "file_name": "cmr.pdf", "file_size": 1000, "mime_type": "application/pdf",
             "category": "trips", "cmr_number": "CMR001", "is_signed": 1},
        ]
        builder.trips.get_by_id.return_value = {}

        docs = builder.list_trip_documents(42)
        assert len(docs) == 1
        builder.docs.get_documents_for_entity.assert_called_once_with("trip", 42)

    def test_list_documents_from_json_column(self, builder):
        builder.docs.get_documents_for_entity.return_value = []
        builder.trips.get_by_id.return_value = {
            "documents_attached": json.dumps([2, 3]),
        }
        builder.docs.get_by_ids_batch.return_value = [
            {"id": 2, "doc_number": "DOC-002"},
            {"id": 3, "doc_number": "DOC-003"},
        ]

        docs = builder.list_trip_documents(42)
        assert len(docs) == 2

    def test_list_documents_sort_order(self, builder):
        builder.docs.get_documents_for_entity.return_value = [
            {"id": 1, "doc_number": "D1", "title": "Invoice", "file_path": "/i.pdf",
             "file_name": "i.pdf", "file_size": 100, "mime_type": "application/pdf",
             "category": "invoices", "cmr_number": "", "is_signed": 0},
            {"id": 2, "doc_number": "D2", "title": "CMR Signed", "file_path": "/c.pdf",
             "file_name": "c.pdf", "file_size": 200, "mime_type": "application/pdf",
             "category": "trips", "cmr_number": "CMR001", "is_signed": 1},
        ]
        builder.trips.get_by_id.return_value = {}

        docs = builder.list_trip_documents(42)
        # Signed CMRs should come first, then invoices
        assert docs[0]["id"] == 2  # Signed first
        assert docs[1]["id"] == 1  # Invoice second

    def test_list_documents_empty(self, builder):
        builder.docs.get_documents_for_entity.return_value = []
        builder.trips.get_by_id.return_value = {}

        docs = builder.list_trip_documents(42)
        assert docs == []


class TestBuildForTrip:
    def test_build_for_trip_creates_package(self, builder):
        builder.list_trip_documents = MagicMock(return_value=[
            {"id": 1, "doc_number": "DOC-001", "title": "CMR", "file_path": "/c.pdf",
             "file_name": "c.pdf", "file_size": 100, "mime_type": "application/pdf",
             "category": "trips", "cmr_number": "CMR001", "is_signed": 1},
        ])
        builder.pipeline.create_package.return_value = 101
        builder.pipeline.get_package_by_id.return_value = {
            "id": 101, "trip_id": 42, "package_uuid": "uuid-123",
        }

        pkg = builder.build_for_trip(42)
        assert pkg is not None
        assert isinstance(pkg, Package)
        assert pkg.package_id == 101
        assert pkg.trip_id == 42
        assert len(pkg.documents) == 1

    def test_build_for_trip_no_documents(self, builder):
        builder.list_trip_documents = MagicMock(return_value=[])
        pkg = builder.build_for_trip(42)
        assert pkg is None

    def test_build_for_trip_with_custom_order(self, builder):
        builder.list_trip_documents = MagicMock(return_value=[
            {"id": 1, "doc_number": "D1"},
            {"id": 2, "doc_number": "D2"},
            {"id": 3, "doc_number": "D3"},
        ])
        builder.pipeline.create_package.return_value = 101
        builder.pipeline.get_package_by_id.return_value = {
            "id": 101, "trip_id": 42, "package_uuid": "uuid-123",
        }

        pkg = builder.build_for_trip(42, document_ids=[3, 1])
        # Should reorder to 3, 1, 2
        assert len(pkg.documents) == 3
        assert pkg.documents[0]["id"] == 3
        assert pkg.documents[1]["id"] == 1


class TestBuildStandalone:
    def test_build_standalone(self, builder):
        documents = [
            {"id": 1, "doc_number": "DOC-001"},
        ]
        builder.pipeline.create_package.return_value = 201
        builder.pipeline.get_package_by_id.return_value = {
            "id": 201, "trip_id": None, "package_uuid": "uuid-456",
        }

        pkg = builder.build_standalone(documents)
        assert pkg is not None
        assert pkg.trip_id is None
        assert pkg.package_id == 201

    def test_build_standalone_no_docs(self, builder):
        pkg = builder.build_standalone([])
        assert pkg is None


class TestBuildZip:
    def test_build_zip_creates_archive(self, builder):
        builder.list_trip_documents = MagicMock(return_value=[
            {"id": 1, "file_path": "/docs/doc.pdf", "file_name": "doc.pdf"},
        ])
        with patch("tempfile.mkdtemp", return_value="/tmp/pkg_xxx"), \
             patch("os.path.isfile", return_value=True), \
             patch("os.makedirs"), \
             patch("os.path.getsize", return_value=1024), \
             patch("shutil.make_archive") as mock_archive:
            mock_archive.return_value = "/output/trip_42_20240703.zip"
            result = builder.build_zip(42, "/output")
            assert result is not None
            assert result.endswith(".zip")

    def test_build_zip_no_documents(self, builder):
        builder.list_trip_documents = MagicMock(return_value=[])
        result = builder.build_zip(42, "/output")
        assert result is None


class TestBuildCombinedPdf:
    @patch("services.document_automation.package_builder.os.path.isfile", return_value=True)
    def test_build_combined_pdf_no_docs(self, mock_isfile, builder):
        builder.list_trip_documents = MagicMock(return_value=[])
        result = builder.build_combined_pdf(42, "/output")
        assert result is None

    @patch("services.document_automation.package_builder.os.path.isfile", return_value=True)
    def test_build_combined_pdf_with_cover(self, mock_isfile, builder):
        builder.list_trip_documents = MagicMock(return_value=[
            {"id": 1, "file_path": "/docs/doc1.pdf", "file_name": "doc1.pdf"},
        ])

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]  # truthy so writer.write is called

        # Mock the cover page generator
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock()]
        with patch.object(builder, "_generate_cover_page") as mock_cover, \
             patch("os.makedirs"), \
             patch("builtins.open", MagicMock()), \
             patch("pypdf.PdfWriter", return_value=mock_writer), \
             patch("pypdf.PdfReader", return_value=mock_reader):
            mock_cover.return_value = MagicMock()
            result = builder.build_combined_pdf(42, "/output")
            assert result is not None
            assert result.endswith("_combined.pdf")
