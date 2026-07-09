"""Unit tests for migration type definitions — enums and dataclasses."""
from __future__ import annotations

import pytest

from services.migration.types import (
    ArchiveStage,
    DuplicateCandidate,
    EntityType,
    ExportFormat,
    ImportFormat,
    ImportStage,
    ImportStats,
    MappingConfig,
)


class TestImportFormat:
    def test_members_have_correct_values(self):
        assert ImportFormat.CSV.value == "csv"
        assert ImportFormat.EXCEL.value == "excel"
        assert ImportFormat.JSON.value == "json"
        assert ImportFormat.XML.value == "xml"

    def test_is_str_enum(self):
        assert isinstance(ImportFormat.CSV, str)


class TestEntityType:
    def test_members_have_singular_values(self):
        assert EntityType.TRIP.value == "trip"
        assert EntityType.CLIENT.value == "client"
        assert EntityType.DRIVER.value == "driver"
        assert EntityType.TRUCK.value == "truck"
        assert EntityType.DOCUMENT.value == "document"
        assert EntityType.INVOICE.value == "invoice"

    def test_members_are_not_plural(self):
        for member in EntityType:
            assert not member.value.endswith("s"), f"{member.value} should be singular"

    def test_is_str_enum(self):
        assert isinstance(EntityType.CLIENT, str)


class TestImportStage:
    def test_members_have_correct_values(self):
        assert ImportStage.VALIDATING.value == "validating"
        assert ImportStage.DEDUP_CHECK.value == "dedup_check"
        assert ImportStage.MAPPING.value == "mapping"
        assert ImportStage.VALIDATING_ROWS.value == "validating_rows"
        assert ImportStage.COMMITTING.value == "committing"
        assert ImportStage.COMPLETE.value == "complete"
        assert ImportStage.FAILED.value == "failed"


class TestArchiveStage:
    def test_members_have_correct_values(self):
        assert ArchiveStage.UPLOADING.value == "uploading"
        assert ArchiveStage.IMAGE_PROCESSING.value == "image_processing"
        assert ArchiveStage.OCR.value == "ocr"
        assert ArchiveStage.CLASSIFYING.value == "classifying"
        assert ArchiveStage.EXTRACTING.value == "extracting"
        assert ArchiveStage.MATCHING.value == "matching"
        assert ArchiveStage.AWAITING_CONFIRMATION.value == "awaiting_confirmation"
        assert ArchiveStage.PERSISTING.value == "persisting"
        assert ArchiveStage.COMPLETE.value == "complete"


class TestExportFormat:
    def test_members_have_correct_values(self):
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.EXCEL.value == "excel"
        assert ExportFormat.PDF.value == "pdf"
        assert ExportFormat.JSON.value == "json"

    def test_is_str_enum(self):
        assert isinstance(ExportFormat.CSV, str)


class TestImportStats:
    def test_defaults_are_all_zero(self):
        stats = ImportStats()
        assert stats.total_rows == 0
        assert stats.valid_rows == 0
        assert stats.duplicates_skipped == 0
        assert stats.validation_failures == 0
        assert stats.committed == 0

    def test_can_set_values(self):
        stats = ImportStats(
            total_rows=100,
            valid_rows=80,
            duplicates_skipped=5,
            validation_failures=15,
            committed=80,
        )
        assert stats.total_rows == 100
        assert stats.valid_rows == 80
        assert stats.duplicates_skipped == 5
        assert stats.validation_failures == 15
        assert stats.committed == 80

    def test_partial_override(self):
        stats = ImportStats(total_rows=50, committed=40)
        assert stats.total_rows == 50
        assert stats.committed == 40
        assert stats.duplicates_skipped == 0  # default

    def test_repr(self):
        stats = ImportStats(total_rows=10)
        assert "ImportStats" in repr(stats)
        assert "total_rows=10" in repr(stats)


class TestMappingConfig:
    def test_creates_with_defaults(self):
        config = MappingConfig(
            source_columns=["a", "b"],
            target_fields={"a": "name", "b": "email"},
            entity_type=EntityType.CLIENT,
        )
        assert config.source_columns == ["a", "b"]
        assert config.target_fields == {"a": "name", "b": "email"}
        assert config.entity_type == EntityType.CLIENT
        assert config.defaults == {}

    def test_defaults_field(self):
        config = MappingConfig(
            source_columns=["a"],
            target_fields={"a": "name"},
            entity_type=EntityType.CLIENT,
            defaults={"is_active": 1},
        )
        assert config.defaults == {"is_active": 1}

    def test_defaults_are_empty_dict_when_not_provided(self):
        config = MappingConfig(
            source_columns=["x"],
            target_fields={"x": "y"},
            entity_type=EntityType.TRIP,
        )
        assert config.defaults == {}


class TestDuplicateCandidate:
    def test_stores_all_fields(self):
        candidate = DuplicateCandidate(
            existing={"id": 1, "name": "ACME"},
            incoming={"name": "ACME Corp"},
            entity_type=EntityType.CLIENT,
            score=0.95,
            matched_on=["name"],
        )
        assert candidate.existing == {"id": 1, "name": "ACME"}
        assert candidate.incoming == {"name": "ACME Corp"}
        assert candidate.entity_type == EntityType.CLIENT
        assert candidate.score == 0.95
        assert candidate.matched_on == ["name"]

    def test_score_can_be_one_point_zero(self):
        candidate = DuplicateCandidate(
            existing={"id": 5, "plate_number": "AB123CD"},
            incoming={"plate_number": "AB123CD"},
            entity_type=EntityType.TRUCK,
            score=1.0,
            matched_on=["plate_number"],
        )
        assert candidate.score == 1.0
        assert candidate.matched_on == ["plate_number"]

    def test_matched_on_can_be_multiple_fields(self):
        candidate = DuplicateCandidate(
            existing={"id": 1, "name": "ACME", "vat_number": "RO123"},
            incoming={"name": "ACME", "vat_number": "RO123"},
            entity_type=EntityType.CLIENT,
            score=1.0,
            matched_on=["name", "vat_number"],
        )
        assert candidate.matched_on == ["name", "vat_number"]

    def test_incoming_can_be_empty(self):
        candidate = DuplicateCandidate(
            existing={"id": 1},
            incoming={},
            entity_type=EntityType.DOCUMENT,
            score=0.0,
            matched_on=[],
        )
        assert candidate.incoming == {}
        assert candidate.score == 0.0
