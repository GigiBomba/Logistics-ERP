"""Dataclasses and enums shared by all migration modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ImportFormat(str, Enum):
    """Supported source formats for digital imports (Tab 1)."""

    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    XML = "xml"


class EntityType(str, Enum):
    """Entity types that can be imported / exported."""

    TRIP = "trip"
    CLIENT = "client"
    DRIVER = "driver"
    TRUCK = "truck"
    DOCUMENT = "document"
    INVOICE = "invoice"


class ImportStage(str, Enum):
    """Discrete stages of a digital import pipeline."""

    VALIDATING = "validating"
    DEDUP_CHECK = "dedup_check"
    MAPPING = "mapping"
    VALIDATING_ROWS = "validating_rows"
    COMMITTING = "committing"
    COMPLETE = "complete"
    FAILED = "failed"


class ArchiveStage(str, Enum):
    """Discrete stages of a physical archive import pipeline."""

    UPLOADING = "uploading"
    IMAGE_PROCESSING = "image_processing"
    OCR = "ocr"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    MATCHING = "matching"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PERSISTING = "persisting"
    COMPLETE = "complete"


class ExportFormat(str, Enum):
    """Supported output formats for data export (Tab 3)."""

    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"


@dataclass
class ImportStats:
    """Aggregated statistics for a completed import operation."""

    total_rows: int = 0
    valid_rows: int = 0
    duplicates_skipped: int = 0
    validation_failures: int = 0
    committed: int = 0


@dataclass
class MappingConfig:
    """Describes how source columns map to target entity fields."""

    source_columns: list[str]
    target_fields: dict[str, str]  # source_col -> target_field
    entity_type: EntityType
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicateCandidate:
    """One potential duplicate detected during dedup."""

    existing: dict[str, Any]
    incoming: dict[str, Any]
    entity_type: EntityType
    score: float
    matched_on: list[str]


# Callback signature used for progress reporting across the migration services.
# (stage_label: str, percent: int, message: str) -> None
ProgressCallback = Optional[Callable[[str, int, str], None]]
