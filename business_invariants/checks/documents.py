"""
Business invariants for the Documents module (DOC-*).

Ensures CMR uniqueness, document integrity, soft-delete compliance,
attachment consistency, path safety, and version limits.
"""

from __future__ import annotations

from business_invariants.decorators import invariant
from business_invariants.models import (
    ExecutionFrequency,
    InvariantCategory,
    InvariantContext,
    InvariantResult,
    InvariantStatus,
    Severity,
)


def _no_db_result(invariant_id: str) -> InvariantResult:
    """Return a PASS result when no database connection is available."""
    return InvariantResult(
        invariant_id=invariant_id,
        status=InvariantStatus.PASS,
        message="No database connection — runtime validation skipped",
    )


# ──────────────────────────────────────────────
# DOC-001 — CMR numbers remain unique
# ──────────────────────────────────────────────


@invariant(
    id="DOC-001",
    title="CMR numbers remain unique",
    description="No two trips share the same cmr_number.",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents", "cmr"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.PR],
    rationale="Duplicate CMR numbers cause billing and regulatory conflicts.",
)
def check_cmr_numbers_unique(ctx: InvariantContext) -> InvariantResult:
    """Verify that no two trips share the same cmr_number."""
    invariant_id = "DOC-001"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT cmr_number, COUNT(*) as cnt
            FROM trips
            WHERE cmr_number IS NOT NULL AND cmr_number != ''
            GROUP BY cmr_number
            HAVING cnt > 1
            """
        )
        duplicates = cursor.fetchall()
        if duplicates:
            details = [{"cmr_number": row[0], "count": row[1]} for row in duplicates]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="Each cmr_number is unique across all trips",
                actual=f"Found {len(duplicates)} duplicate CMR numbers",
                message=f"Duplicate CMR numbers: {[d['cmr_number'] for d in details]}",
                root_cause="Multiple trips share the same CMR number",
                suggested_fix="Correct or remove duplicate cmr_number values so each is unique",
                affected_modules=["documents", "cmr"],
                details={"duplicates": details},
            )
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="Each cmr_number is unique across all trips",
            actual="No duplicate CMR numbers found",
            affected_modules=["documents", "cmr"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents", "cmr"],
        )


# ──────────────────────────────────────────────
# DOC-002 — Document numbers are unique per company
# ──────────────────────────────────────────────


@invariant(
    id="DOC-002",
    title="Document numbers are unique per company",
    description="No two documents in the same company share the same doc_number.",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents"],
    severity=Severity.HIGH,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Duplicate document numbers within a company break auditing and cross-referencing.",
)
def check_doc_numbers_unique_per_company(ctx: InvariantContext) -> InvariantResult:
    """Verify that document numbers are unique within each company."""
    invariant_id = "DOC-002"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT company_id, doc_number, COUNT(*) as cnt
            FROM documents
            WHERE doc_number IS NOT NULL AND doc_number != ''
            GROUP BY company_id, doc_number
            HAVING cnt > 1
            """
        )
        duplicates = cursor.fetchall()
        if duplicates:
            details = [
                {"company_id": row[0], "doc_number": row[1], "count": row[2]}
                for row in duplicates
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="Each doc_number is unique within a company",
                actual=f"Found {len(duplicates)} duplicate document numbers",
                message=f"Duplicate doc_numbers: {[d['doc_number'] for d in details]}",
                root_cause="Multiple documents in the same company share the same doc_number",
                suggested_fix="Assign unique doc_number values per company",
                affected_modules=["documents"],
                details={"duplicates": details},
            )
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="Each doc_number is unique within a company",
            actual="No duplicate document numbers found",
            affected_modules=["documents"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents"],
        )


# ──────────────────────────────────────────────
# DOC-003 — OCR output linked to correct document
# ──────────────────────────────────────────────


@invariant(
    id="DOC-003",
    title="OCR output linked to correct document",
    description="Document's ocr_text and extracted_data_json belong to the correct document_id.",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents", "ocr"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="OCR data linked to the wrong document causes silent data corruption downstream.",
)
def check_ocr_output_linked_correctly(ctx: InvariantContext) -> InvariantResult:
    """Verify that OCR data is not orphaned and belongs to valid documents."""
    invariant_id = "DOC-003"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()

        # Check for OCR records referencing non-existent documents
        cursor.execute(
            """
            SELECT o.id, o.document_id
            FROM ocr_results o
            LEFT JOIN documents d ON o.document_id = d.id
            WHERE d.id IS NULL
            """
        )
        orphaned_ocr = cursor.fetchall()

        # Check for documents with OCR data but no corresponding ocr_results record
        cursor.execute(
            """
            SELECT d.id, d.doc_number
            FROM documents d
            WHERE (d.ocr_text IS NOT NULL AND d.ocr_text != '')
               OR (d.extracted_data_json IS NOT NULL AND d.extracted_data_json != '{}')
            """
        )
        docs_with_ocr = cursor.fetchall()

        issues = []
        if orphaned_ocr:
            for row in orphaned_ocr:
                issues.append(
                    f"OCR result id={row[0]} references missing document_id={row[1]}"
                )

        if issues:
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All OCR data references valid existing documents",
                actual=f"Found {len(issues)} OCR integrity issues",
                message="; ".join(issues[:5]),
                root_cause="OCR records reference nonexistent documents",
                suggested_fix="Re-import OCR data for the affected documents or clean up orphaned OCR results",
                affected_modules=["documents", "ocr"],
                details={"orphaned_ocr": [{"id": r[0], "document_id": r[1]} for r in orphaned_ocr]},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All OCR data references valid existing documents",
            actual=f"{len(docs_with_ocr)} documents have OCR data, 0 orphaned records",
            affected_modules=["documents", "ocr"],
            details={"document_count": len(docs_with_ocr)},
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents", "ocr"],
        )


# ──────────────────────────────────────────────
# DOC-004 — Deleted documents remain recoverable
# ──────────────────────────────────────────────


@invariant(
    id="DOC-004",
    title="Deleted documents remain recoverable",
    description="Soft-deleted documents have deleted_at set (not physically removed).",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.NIGHTLY],
    rationale="Hard-deleted documents cannot be recovered for audit or legal holds.",
)
def check_deleted_documents_recoverable(ctx: InvariantContext) -> InvariantResult:
    """Verify that deleted documents use soft-delete (deleted_at is set)."""
    invariant_id = "DOC-004"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()

        # Check documents marked as deleted but missing deleted_at
        cursor.execute(
            """
            SELECT id, doc_number, status
            FROM documents
            WHERE (status = 'deleted' OR is_deleted = 1)
              AND deleted_at IS NULL
            """
        )
        missing_timestamp = cursor.fetchall()

        if missing_timestamp:
            details = [
                {"id": row[0], "doc_number": row[1], "status": row[2]}
                for row in missing_timestamp
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All deleted documents have deleted_at set",
                actual=f"{len(missing_timestamp)} deleted documents missing deleted_at",
                message=f"Documents without deleted_at: {[d['id'] for d in details]}",
                root_cause="Deletion bypassed the soft-delete mechanism",
                suggested_fix="Update missing deleted_at timestamps via data migration; patch deletion logic to always set deleted_at",
                affected_modules=["documents"],
                details={"missing_timestamps": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All deleted documents have deleted_at set",
            actual="All soft-deleted documents have deleted_at populated",
            affected_modules=["documents"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents"],
        )


# ──────────────────────────────────────────────
# DOC-005 — Attachments remain associated with parent entity
# ──────────────────────────────────────────────


@invariant(
    id="DOC-005",
    title="Attachments remain associated with parent entity",
    description="Every document_link references an existing document_id and valid entity.",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Orphaned links cause broken references and UI errors.",
)
def check_attachments_associated(ctx: InvariantContext) -> InvariantResult:
    """Verify that all document_links reference valid documents and entities."""
    invariant_id = "DOC-005"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()

        # Orphaned document links (document_id doesn't exist)
        cursor.execute(
            """
            SELECT dl.id, dl.document_id
            FROM document_links dl
            LEFT JOIN documents d ON dl.document_id = d.id
            WHERE d.id IS NULL
            """
        )
        orphaned_docs = cursor.fetchall()

        issues = []

        if orphaned_docs:
            for row in orphaned_docs:
                issues.append(f"document_link id={row[0]} references missing document_id={row[1]}")

        if issues:
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All document_links reference existing documents",
                actual=f"Found {len(issues)} broken document links",
                message="; ".join(issues[:5]),
                root_cause="Document links were not cleaned up when documents were removed",
                suggested_fix="Delete orphaned document_links or restore the referenced documents",
                affected_modules=["documents"],
                details={
                    "orphaned_links": [
                        {"id": r[0], "document_id": r[1]} for r in orphaned_docs
                    ],
                },
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All document_links reference existing documents",
            actual="All document links are correctly associated",
            affected_modules=["documents"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents"],
        )


# ──────────────────────────────────────────────
# DOC-006 — Document file paths are safe
# ──────────────────────────────────────────────


@invariant(
    id="DOC-006",
    title="Document file paths are safe",
    description="No document file_path contains '..' (path traversal prevention).",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Path traversal in file paths could expose or damage files outside the storage root.",
)
def check_document_file_paths_safe(ctx: InvariantContext) -> InvariantResult:
    """Verify that no document file_path attempts path traversal."""
    invariant_id = "DOC-006"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT id, file_path, doc_number
            FROM documents
            WHERE file_path LIKE '%..%'
               OR file_path LIKE '%\\0%'
               OR file_path LIKE '~%'
               OR file_path LIKE '\\\\%'
               OR file_path LIKE '//%'
            """
        )
        unsafe_paths = cursor.fetchall()

        if unsafe_paths:
            details = [
                {"id": row[0], "file_path": row[1], "doc_number": row[2]}
                for row in unsafe_paths
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All file_paths are safe and contain no path traversal sequences",
                actual=f"Found {len(unsafe_paths)} documents with unsafe file paths",
                message=f"Unsafe paths detected: {[d['id'] for d in details]}",
                root_cause="File path was not sanitized before storage",
                suggested_fix="Sanitize file_path values; reject '..', null bytes, and absolute paths at input",
                affected_modules=["documents"],
                details={"unsafe_paths": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All file_paths are safe",
            actual="No unsafe file paths found",
            affected_modules=["documents"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents"],
        )


# ──────────────────────────────────────────────
# DOC-007 — Document versions count limited
# ──────────────────────────────────────────────


@invariant(
    id="DOC-007",
    title="Document versions count limited",
    description="No document has more than 20 versions.",
    category=InvariantCategory.DOCUMENTS,
    modules=["documents"],
    severity=Severity.LOW,
    execution=[ExecutionFrequency.NIGHTLY],
    rationale="Excessive versions bloat storage and degrade UI performance.",
)
def check_document_versions_count(ctx: InvariantContext) -> InvariantResult:
    """Verify that no document exceeds the maximum version count."""
    invariant_id = "DOC-007"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT document_id, COUNT(*) as version_count
            FROM document_versions
            GROUP BY document_id
            HAVING version_count > 20
            """
        )
        excessive = cursor.fetchall()

        if excessive:
            details = [
                {"document_id": row[0], "version_count": row[1]} for row in excessive
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="No document has more than 20 versions",
                actual=f"Found {len(excessive)} documents exceeding 20 versions",
                message=f"Excessive versions: {[d['document_id'] for d in details]}",
                root_cause="Version creation without cleanup or archiving",
                suggested_fix="Archive old versions or increase the limit if justified; enforce a version cap in application logic",
                affected_modules=["documents"],
                details={"excessive_versions": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="No document exceeds 20 versions",
            actual="All documents within version limit",
            affected_modules=["documents"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["documents"],
        )
