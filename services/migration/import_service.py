"""Orchestrates digital imports (Tab 1): file → rows → validate → dedup → commit.

Serves as the primary entry point for the software import workflow,
coordinating the importer registry, validator, duplicate detector, and
repositories within a transactional boundary.
"""

from __future__ import annotations

import logging
from typing import Any

from database.db_manager import DatabaseManager
from services.migration.duplicate_detector import DuplicateDetector
from services.migration.importer_registry import _import_registry
from services.migration.import_validator import ImportValidator
from services.migration.types import (
    DuplicateCandidate,
    EntityType,
    ImportFormat,
    ImportStage,
    ImportStats,
    MappingConfig,
    ProgressCallback,
)

logger = logging.getLogger(__name__)


class ImportService:
    """End-to-end orchestrator for digital import operations.

    Typical flow::

        svc = ImportService(db)
        rows, errors = svc.preview(path, ImportFormat.CSV, EntityType.CLIENT)
        mapped = svc.apply_mapping(rows, mapping_config)
        valid, invalid, summary = svc.validate_all(mapped, EntityType.CLIENT)
        duplicates = svc.check_duplicates(valid, EntityType.CLIENT)
        stats = svc.commit(valid, EntityType.CLIENT)
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self._registry = _import_registry
        self._validator = ImportValidator()
        self._dedup = DuplicateDetector(db)
        self._repos: dict[EntityType, Any] = {}

    # ── Repo cache ─────────────────────────────────────────────────────

    def _get_repo(self, entity_type: EntityType) -> Any:
        """Lazy-load and cache the repository for *entity_type*."""
        if entity_type not in self._repos:
            try:
                if entity_type == EntityType.CLIENT:
                    from repositories.client_repository import ClientRepository
                    self._repos[entity_type] = ClientRepository(self.db)
                elif entity_type == EntityType.DRIVER:
                    from repositories.driver_repository import DriverRepository
                    self._repos[entity_type] = DriverRepository(self.db)
                elif entity_type == EntityType.TRUCK:
                    from repositories.fleet_repository import FleetRepository
                    self._repos[entity_type] = FleetRepository(self.db)
                elif entity_type == EntityType.TRIP:
                    from repositories.trip_repository import TripRepository
                    self._repos[entity_type] = TripRepository(self.db)
                elif entity_type == EntityType.INVOICE:
                    from repositories.invoice_repository import InvoiceRepository
                    self._repos[entity_type] = InvoiceRepository(self.db)
                elif entity_type == EntityType.DOCUMENT:
                    from repositories.document_repository import DocumentRepository
                    self._repos[entity_type] = DocumentRepository(self.db)
            except Exception as exc:
                logger.exception("Failed to load repo for %s: %s", entity_type, exc)
                raise
        return self._repos[entity_type]

    # ── Step 1: Preview ────────────────────────────────────────────────

    def preview(
        self,
        path: str,
        fmt: ImportFormat,
        entity_type: EntityType,
        progress_cb: ProgressCallback = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Read a source file and return a preview of rows plus schema errors.

        Returns:
            ``(rows, errors)`` where *rows* are the raw parsed rows
            and *errors* are schema-level validation messages.
        """
        if progress_cb:
            progress_cb(ImportStage.VALIDATING.value, 5, f"Reading {fmt.value} file...")

        importer = self._registry.get(fmt)
        rows = importer.read(path)

        if progress_cb:
            progress_cb(ImportStage.VALIDATING.value, 30, f"Parsed {len(rows)} rows")

        errors = importer.validate_schema(rows)

        if progress_cb:
            level = 100 if not errors else 70
            progress_cb(ImportStage.VALIDATING.value, level, "Preview ready")

        return rows, errors

    # ── Step 2: Mapping ────────────────────────────────────────────────

    def apply_mapping(
        self,
        rows: list[dict[str, Any]],
        mapping: MappingConfig,
    ) -> list[dict[str, Any]]:
        """Transform raw rows by applying a field-mapping configuration.

        Uses ``mapping.target_fields`` to rename source columns to target
        fields.  Drops unmapped columns.  Applies default values for any
        missing target fields defined in ``mapping.defaults``.
        """
        if not rows:
            return []

        mapped_rows: list[dict[str, Any]] = []
        for row in rows:
            mapped: dict[str, Any] = {}
            for src_col, target_field in mapping.target_fields.items():
                value = row.get(src_col)
                if value is not None:
                    mapped[target_field] = value
            # Apply defaults
            for field, default_val in mapping.defaults.items():
                if field not in mapped or mapped[field] is None:
                    mapped[field] = default_val
            mapped_rows.append(mapped)

        return mapped_rows

    # ── Step 3: Validate all rows ──────────────────────────────────────

    def validate_all(
        self,
        rows: list[dict[str, Any]],
        entity_type: EntityType,
        progress_cb: ProgressCallback = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
        """Run per-row validation across all rows.

        Returns:
            Tuple of ``(valid_rows, invalid_rows, error_summary)`` where
            *error_summary* maps error messages to their occurrence count.
        """
        valid_rows: list[dict[str, Any]] = []
        invalid_rows: list[dict[str, Any]] = []
        error_summary: dict[str, int] = {}
        total = len(rows)

        for idx, row in enumerate(rows):
            is_valid, errors, cleaned = self._validator.validate_row(row, entity_type)
            if is_valid:
                valid_rows.append(cleaned)
            else:
                invalid_rows.append({"row_index": idx, "original": row, "errors": errors})
                for err in errors:
                    error_summary[err] = error_summary.get(err, 0) + 1

            # Report progress every 10 rows
            if progress_cb and (idx + 1) % 10 == 0:
                pct = int((idx + 1) / total * 100) if total else 100
                progress_cb(
                    ImportStage.VALIDATING_ROWS.value,
                    pct,
                    f"Validated {idx + 1}/{total} rows",
                )

        if progress_cb and total > 0:
            progress_cb(
                ImportStage.VALIDATING_ROWS.value,
                100,
                f"Validation complete: {len(valid_rows)} valid, {len(invalid_rows)} invalid",
            )

        return valid_rows, invalid_rows, error_summary

    # ── Step 4: Duplicate check ────────────────────────────────────────

    def check_duplicates(
        self,
        rows: list[dict[str, Any]],
        entity_type: EntityType,
        progress_cb: ProgressCallback = None,
    ) -> list[DuplicateCandidate]:
        """Check each row for duplicates in the existing database."""
        all_duplicates: list[DuplicateCandidate] = []
        total = len(rows)

        if progress_cb:
            progress_cb(ImportStage.DEDUP_CHECK.value, 0, f"Checking {total} rows for duplicates...")

        for idx, row in enumerate(rows):
            duplicates = self._dedup.find_duplicates(row, entity_type)
            all_duplicates.extend(duplicates)

            if progress_cb and (idx + 1) % 10 == 0:
                pct = int((idx + 1) / total * 100) if total else 100
                progress_cb(
                    ImportStage.DEDUP_CHECK.value,
                    pct,
                    f"Checked {idx + 1}/{total} rows — {len(all_duplicates)} potential duplicates found",
                )

        if progress_cb:
            progress_cb(ImportStage.DEDUP_CHECK.value, 100, f"Dedup check complete: {len(all_duplicates)} candidates")

        return all_duplicates

    # ── Full pipeline convenience ───────────────────────────────────────

    def import_data(
        self,
        path: str,
        fmt: ImportFormat,
        entity_type: EntityType,
        mapping: MappingConfig | None = None,
        dedup_action: str = "skip",
        progress_cb: ProgressCallback = None,
    ) -> ImportStats:
        """Full import pipeline: preview → map → validate → dedup → commit."""
        rows, errors = self.preview(path, fmt, entity_type, progress_cb)
        if errors:
            logger.warning("Import preview errors: %s", errors)
        if mapping:
            rows = self.apply_mapping(rows, mapping)
        valid_rows, invalid_rows, _ = self.validate_all(rows, entity_type, progress_cb)
        if not valid_rows:
            return ImportStats(total_rows=len(rows))
        stats = self.commit(valid_rows, entity_type, dedup_action=dedup_action, progress_cb=progress_cb)
        stats.validation_failures += len(invalid_rows)
        stats.total_rows = len(rows)
        return stats

    # ── Step 5: Commit ─────────────────────────────────────────────────

    def commit(
        self,
        rows: list[dict[str, Any]],
        entity_type: EntityType,
        dedup_action: str = "skip",
        progress_cb: ProgressCallback = None,
        skip_duplicates: set[str] | None = None,
    ) -> ImportStats:
        """Commit rows to the database within a single transaction.

        Args:
            rows: Validated rows to insert.
            entity_type: Target entity type.
            dedup_action: How to handle duplicates. One of:
                - ``"skip"``: skip duplicate rows (default)
                - ``"overwrite"``: update existing records
                - ``"import"``: import regardless (force insert)

        Returns:
            An :class:`ImportStats` instance summarising the operation.
        """
        stats = ImportStats(total_rows=len(rows))
        repo = self._get_repo(entity_type)

        if progress_cb:
            progress_cb(ImportStage.COMMITTING.value, 0, f"Committing {len(rows)} rows...")

        # Begin transaction
        repo.begin_transaction()

        committed = 0
        skipped = 0
        failed = 0
        total = len(rows)

        try:
            for idx, row in enumerate(rows):
                # Check duplicates before insert
                if dedup_action in ("skip", "overwrite"):
                    if dedup_action == "skip" and skip_duplicates is not None:
                        # Use pre-computed duplicate keys
                        row_key = str(sorted(row.items()))
                        is_duplicate = row_key in skip_duplicates
                        if is_duplicate:
                            duplicates = [DuplicateCandidate(existing={}, incoming=row, entity_type=entity_type, score=1.0, matched_on=[])]
                        else:
                            duplicates = []
                    else:
                        duplicates = self._dedup.find_duplicates(row, entity_type)
                    if duplicates:
                        if dedup_action == "skip":
                            skipped += 1
                            if progress_cb and (idx + 1) % 10 == 0:
                                pct = int((idx + 1) / total * 100) if total else 100
                                progress_cb(
                                    ImportStage.COMMITTING.value,
                                    pct,
                                    f"Skipped duplicate {idx + 1}/{total}",
                                )
                            continue
                        elif dedup_action == "overwrite" and duplicates:
                            # Update existing record
                            try:
                                existing_id = duplicates[0].existing.get("id")
                                if existing_id:
                                    try:
                                        if hasattr(repo, "TABLE") and repo.TABLE == "documents":
                                            repo.update(existing_id, **row)
                                        else:
                                            repo.update(existing_id, row)
                                    except TypeError:
                                        repo.update(existing_id, row)
                                    committed += 1
                            except Exception as exc:
                                logger.warning("Overwrite failed for row %d: %s", idx, exc)
                                failed += 1
                            continue

                # Insert new row — use direct SQL to avoid
                # repo.create() auto-committing within our transaction.
                try:
                    enriched = self._enrich_row(row, entity_type)
                    self._fallback_insert(repo, enriched)
                    committed += 1
                except Exception as exc:
                    logger.warning("Insert failed for row %d: %s", idx, exc)
                    failed += 1

                if progress_cb and (idx + 1) % 10 == 0:
                    pct = int((idx + 1) / total * 100) if total else 100
                    progress_cb(
                        ImportStage.COMMITTING.value,
                        pct,
                        f"Committed {idx + 1}/{total} rows",
                    )

            # Commit transaction
            repo.commit_transaction()

        except Exception as exc:
            logger.exception("Commit failed, rolling back transaction")
            repo.rollback_transaction()
            if progress_cb:
                progress_cb(ImportStage.FAILED.value, 0, f"Commit failed: {exc}")
            stats.valid_rows = 0
            stats.committed = 0
            stats.duplicates_skipped = 0
            stats.validation_failures = 0
            return stats

        stats.valid_rows = committed
        stats.committed = committed
        stats.duplicates_skipped = skipped
        stats.validation_failures = failed

        if progress_cb:
            progress_cb(
                ImportStage.COMPLETE.value,
                100,
                f"Import complete: {committed} committed, {skipped} skipped, {failed} failed",
            )

        # Publish completion event
        try:
            from services.operations.event_bus import EventBus

            EventBus().publish("migration.import_completed", {
                "entity_type": entity_type.value,
                "stats": {
                    "total_rows": stats.total_rows,
                    "committed": stats.committed,
                    "duplicates_skipped": stats.duplicates_skipped,
                    "validation_failures": stats.validation_failures,
                },
            })
        except Exception as exc:
            logger.debug("Failed to publish migration.import_completed event: %s", exc)

        return stats

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _enrich_row(row: dict[str, Any], entity_type: EntityType) -> dict[str, Any]:
        """Add default values that repos normally inject via create()."""
        enriched = dict(row)
        if entity_type in (EntityType.CLIENT, EntityType.DRIVER, EntityType.TRIP, EntityType.INVOICE, EntityType.DOCUMENT):
            if "created_at" not in enriched or not enriched.get("created_at"):
                from datetime import datetime
                enriched["created_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        if entity_type == EntityType.CLIENT and "is_active" not in enriched:
            enriched["is_active"] = 1
        if entity_type == EntityType.DRIVER and "is_active" not in enriched:
            enriched["is_active"] = 1
        return enriched

    @staticmethod
    def _fallback_insert(repo: Any, row: dict[str, Any]) -> int:
        """Fallback insert when *repo* has no ``create()`` method.

        Builds an INSERT statement from the row dict keys.
        """
        if hasattr(repo, "_validate_columns"):
            repo._validate_columns(row)
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        query = f"INSERT INTO {getattr(repo, 'TABLE', 'entities')} ({cols}) VALUES ({placeholders})"
        return repo._execute_insert(query, tuple(row.values()), commit=False)
