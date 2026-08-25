"""Contract tests for the Local Download manifest (blueprint §5.3).

Validates ``DownloadCategory`` / ``DownloadRequest`` / ``DownloadManifestEntry``
(``backend/schemas/mobile.py``) against the mobile ``download_manifest.dart``
contract:

- ``DownloadCategory`` enum values exactly: documents, invoices, receipts,
  ocr_results, trip_history (Dart: documents/invoices/receipts/ocrResults/
  tripHistory serialized snake_case).
- ``DownloadManifestEntry``: record_id (str), filename (str), size_bytes (int),
  download_url (str), url_expires_at (ISO-8601 str, Dart ``DateTime.parse``).
"""
from __future__ import annotations


from datetime import datetime, timedelta, timezone

from backend.schemas.mobile import DownloadCategory, DownloadManifestEntry, DownloadRequest

EXPECTED_ENTRY_KEYS = {
    "record_id", "filename", "size_bytes", "download_url", "url_expires_at",
}

CATEGORY_VALUES = {
    "documents", "invoices", "receipts", "ocr_results", "trip_history",
}

FULL_ENTRY = {
    "record_id": "42",
    "filename": "cmr-100.pdf",
    "size_bytes": 12345,
    "download_url": "/api/v1/mobile/company/export/download/abc.def",
    "url_expires_at": "2026-07-31T15:00:00+00:00",
}


class TestDownloadCategoryContract:
    """The 5 blueprint categories, exact string values."""

    def test_enum_members_match_blueprint(self) -> None:
        assert {c.value for c in DownloadCategory} == CATEGORY_VALUES

    def test_category_values_are_snake_case_strings(self) -> None:
        for cat in DownloadCategory:
            assert isinstance(cat.value, str)
            assert cat.value == cat.value.lower()

    def test_request_requires_category(self) -> None:
        body = DownloadRequest(category=DownloadCategory.invoices)
        assert body.category == DownloadCategory.invoices
        assert body.date_from is None and body.date_to is None

    def test_request_serializes_category_as_string(self) -> None:
        data = DownloadRequest(category=DownloadCategory.ocr_results).model_dump()
        assert data["category"] == "ocr_results"


class TestDownloadManifestEntryContract:
    """Entry fields match the Dart DownloadManifestEntry exactly."""

    def test_full_entry_round_trips_with_exact_fields(self) -> None:
        entry = DownloadManifestEntry.model_validate(FULL_ENTRY)
        data = entry.model_dump()
        assert set(data) == EXPECTED_ENTRY_KEYS
        assert data == FULL_ENTRY

    def test_record_id_is_a_string(self) -> None:
        data = DownloadManifestEntry.model_validate(FULL_ENTRY).model_dump()
        assert isinstance(data["record_id"], str)
        assert data["record_id"] == "42"

    def test_size_bytes_is_an_int(self) -> None:
        data = DownloadManifestEntry.model_validate(FULL_ENTRY).model_dump()
        assert isinstance(data["size_bytes"], int)
        assert data["size_bytes"] == 12345

    def test_url_expires_at_is_iso8601(self) -> None:
        data = DownloadManifestEntry.model_validate(FULL_ENTRY).model_dump()
        parsed = datetime.fromisoformat(data["url_expires_at"].replace("Z", "+00:00"))
        assert parsed.year == 2026
        assert isinstance(data["url_expires_at"], str)

    def test_url_expires_at_defaults_to_empty_string(self) -> None:
        entry = DownloadManifestEntry.model_validate(
            {"record_id": "1", "filename": "a.pdf"}
        )
        assert entry.url_expires_at == ""
        assert entry.size_bytes == 0

    def test_download_url_is_a_signed_url_path(self) -> None:
        entry = DownloadManifestEntry.model_validate(FULL_ENTRY)
        assert entry.download_url.startswith("/api/v1/mobile/company/export/download/")

    def test_unknown_fields_ignored_like_dart(self) -> None:
        """The Dart model reads only its known keys — unknown keys never
        surface in the serialized payload."""
        entry = DownloadManifestEntry.model_validate(
            {**FULL_ENTRY, "category": "cmr", "modified_at": "2026-01-01"}
        )
        assert "category" not in entry.model_dump()
        assert "modified_at" not in entry.model_dump()
