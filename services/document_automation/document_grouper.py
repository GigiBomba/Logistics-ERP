"""Document grouping + trip auto-linking.

After the trip matcher picks a trip, this module:

    1. Calls :meth:`DocumentService.register_existing` with the
       processed PDF and the right ``category="trips"`` /
       ``entity_type="trip"`` / ``entity_id=trip_id`` fields.
    2. Persists the structured OCR result into
       ``documents.extracted_data_json``.
    3. Updates ``trips.documents_attached``.

Writes are sequenced so that a crash mid-way cannot orphan a document
or leave missing metadata: Step 2 atomically persists extraction +
trip metadata, and if that fails the document created in Step 1 is
removed via a compensating delete.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime
from typing import Any

from repositories.document_repository import DocumentRepository
from repositories.pipeline_repository import PipelineRepository
from repositories.trip_repository import TripRepository

logger = logging.getLogger("document_automation.document_grouper")


def _read_documents_attached(db, trip_id: int) -> list[int]:
    return TripRepository(db).get_documents_attached(trip_id)


class DocumentGrouper:
    """Stateless grouper — safe to call from worker threads.

    Constructor takes a :class:`DatabaseManager` instance and creates
    its own :class:`DocumentService` and :class:`PipelineRepository`.
    """

    def __init__(self, db, document_service=None,
                 pipeline_repo=None, doc_repo=None, trip_repo=None) -> None:
        self.db = db
        self._document_service = document_service
        self.pipeline = pipeline_repo if pipeline_repo is not None else PipelineRepository(db)
        self._doc_repo = doc_repo if doc_repo is not None else DocumentRepository(db)
        self._trip_repo = trip_repo if trip_repo is not None else TripRepository(db)

    def group_and_link(
        self,
        run_id: int,
        trip_id: int,
        ocr_text: str = "",
    ) -> int | None:
        """Register the processed PDF against ``trip_id`` and link it.

        Returns the new (or existing) document id, or ``None`` on
        failure.  The entire operation runs inside a single database
        transaction — if anything fails, no partial state is left
        on disk and no orphan document remains.

        Document registration is handled by ``register_existing``
        (which deduplicates by path and hash) with auto-commit
        suppressed so the caller controls the transaction boundary.
        """
        run = self.pipeline.get_run_by_id(run_id)
        if not run:
            logger.error("group_and_link: run %s not found", run_id)
            return None

        processed_pdf = run.get("processed_pdf_path") or run.get("source_file_path")
        if not processed_pdf or not os.path.isfile(processed_pdf):
            logger.error(
                "group_and_link: processed PDF missing for run %s: %s",
                run_id, processed_pdf,
            )
            return None

        extracted = self.pipeline.get_extracted_data(run_id)
        cmr_number = (extracted.get("cmr_number") or "").strip()
        invoice_number = (extracted.get("invoice_number") or "").strip()
        doc_type = (extracted.get("doc_type") or "other").strip() or "other"

        # Build a sensible title.
        # If both CMR and Invoice exist, prefer Invoice for the title.
        title_bits: list[str] = []
        if invoice_number:
            title_bits.append(f"Invoice {invoice_number}")
        elif cmr_number:
            title_bits.append(f"CMR {cmr_number}")
        else:
            title_bits.append("Document")
        if extracted.get("date"):
            title_bits.append(extracted["date"])
        title = " - ".join(title_bits)

        # Tags carry the automation metadata so the Document Center
        # can filter on them later.
        tags: list[str] = ["automation", "ocr-extracted", doc_type]
        if cmr_number:
            tags.append("cmr")
        if invoice_number:
            tags.append("invoice")

        cmr_metadata = json.dumps(
            {k: v for k, v in extracted.items() if k != "raw_text"},
            ensure_ascii=False,
            default=str,
        )
        is_signed = 1 if cmr_number else 0

        # ── Single transaction for all writes ───────────────────────
        # ``register_existing`` normally auto-commits; we pass
        # ``commit=False`` so all its INSERTs are deferred until
        # we COMMIT together with the extraction + trip metadata.
        if self._document_service is None:
            from repositories.document_repository import DocumentRepository
            from services.document.upload_service import UploadService
            self._document_service = UploadService(self.db, DocumentRepository(self.db))
        try:
            self._doc_repo.begin_transaction()
            doc_id = self._document_service.register_existing(
                file_path=processed_pdf,
                title=title,
                category="trips",
                entity_type="trip",
                entity_id=trip_id,
                tags=tags,
                cmr_number=cmr_number,
                cmr_metadata=cmr_metadata,
                is_signed=is_signed,
                commit=False,
            )
            if doc_id is None:
                self._doc_repo.rollback_transaction()
                logger.error("group_and_link: register_existing returned None")
                return None
            self._update_document_extraction(doc_id, extracted, ocr_text, tags)
            self._update_trip_after_link(trip_id, cmr_number, doc_id)
            self._doc_repo.commit_transaction()
        except Exception:
            logger.exception("group_and_link: transaction failed — rolling back")
            with contextlib.suppress(Exception):
                self._doc_repo.rollback_transaction()
            return None

        # Save the resolved document id on the pipeline run.
        self.pipeline.set_document_id(run_id, doc_id)

        return doc_id

    def link_existing_document_to_trip(
        self,
        doc_id: int,
        trip_id: int,
        extracted: dict[str, Any],
        ocr_text: str = "",
    ) -> bool:
        """Link an existing document to a trip without a pipeline run.

        Used by the Document Center background OCR worker after it runs
        field extraction and trip matching.  The document already exists
        in the ``documents`` table — this method handles the linking
        metadata, trip association, and related-document tracking.

        All writes run inside a single ``BEGIN IMMEDIATE`` / ``COMMIT``
        so a crash mid-way cannot leave partial state.

        Returns ``True`` on success, ``False`` on failure.
        """
        cmr_number = (extracted.get("cmr_number") or "").strip()
        invoice_number = (extracted.get("invoice_number") or "").strip()
        doc_type = (extracted.get("doc_type") or "other").strip() or "other"

        tags: list[str] = ["automation", "ocr-extracted", doc_type]
        if cmr_number:
            tags.append("cmr")
        if invoice_number:
            tags.append("invoice")

        cmr_metadata = json.dumps(
            {k: v for k, v in extracted.items() if k != "raw_text"},
            ensure_ascii=False,
            default=str,
        )
        is_signed = 1 if cmr_number else 0
        automation_tags = ",".join(str(t) for t in tags if t)
        extraction_json = json.dumps(extracted, ensure_ascii=False, default=str)
        now = datetime.now().isoformat()

        try:
            self._doc_repo.begin_transaction()

            # Update document metadata and extracted data.
            self._doc_repo.update(
                doc_id,
                entity_type="trip",
                entity_id=trip_id,
                extracted_data_json=extraction_json,
                automation_tags=automation_tags,
                cmr_number=cmr_number,
                cmr_metadata_json=cmr_metadata,
                is_signed=is_signed,
                text_content=ocr_text or None,
                updated_at=now,
                commit=False,
            )

            # Create document link if not already present.
            if not self._doc_repo.has_link(doc_id, "trip", trip_id):
                self._doc_repo.add_link(
                    doc_id, "trip", trip_id, "attached", now, commit=False,
                )

            # Update trip's documents_attached.
            existing = self._trip_repo.get_documents_attached(trip_id)
            if doc_id not in existing:
                existing.append(doc_id)
            self._trip_repo._execute(
                "UPDATE trips SET documents_attached = ? WHERE id = ?",
                (json.dumps(existing), trip_id),
                commit=False,
            )

            # Update trip's CMR number if the document is a CMR.
            if cmr_number:
                self._trip_repo._execute(
                    "UPDATE trips SET "
                    "cmr_number = COALESCE(NULLIF(?, ''), cmr_number), "
                    "cmr_status = 'signed' WHERE id = ?",
                    (cmr_number, trip_id),
                    commit=False,
                )

            self._doc_repo.commit_transaction()
            logger.info(
                "Linked document %d to trip %d (cmr=%s, invoice=%s, type=%s)",
                doc_id, trip_id, cmr_number or "-",
                invoice_number or "-", doc_type,
            )
            return True
        except Exception:
            logger.exception(
                "Failed to link document %d to trip %d", doc_id, trip_id
            )
            with contextlib.suppress(Exception):
                self._doc_repo.rollback_transaction()
            return False

    def _update_document_extraction(
        self,
        doc_id: int,
        extracted: dict[str, Any],
        ocr_text: str,
        tags: list[str] | None = None,
    ) -> None:
        extraction_json = json.dumps(extracted, ensure_ascii=False, default=str)
        automation_tags = ",".join(
            str(t) for t in (tags or []) if t
        ) if tags else ""
        self._doc_repo.update(
            doc_id,
            extracted_data_json=extraction_json,
            text_content=ocr_text or None,
            automation_tags=automation_tags,
            commit=False,
        )

    def _update_trip_after_link(
        self,
        trip_id: int,
        cmr_number: str,
        doc_id: int,
    ) -> None:
        if cmr_number:
            self._trip_repo._execute(
                "UPDATE trips SET cmr_number = COALESCE(NULLIF(?, ''), cmr_number), "
                "cmr_status = 'signed' "
                "WHERE id = ?",
                (cmr_number, trip_id),
                commit=False,
            )
        existing = self._trip_repo.get_documents_attached(trip_id)
        if doc_id not in existing:
            existing.append(doc_id)
        self._trip_repo._execute(
            "UPDATE trips SET documents_attached = ? WHERE id = ?",
            (json.dumps(existing), trip_id),
            commit=False,
        )
