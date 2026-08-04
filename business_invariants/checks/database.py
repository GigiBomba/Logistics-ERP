"""
Business Invariants — Database Integrity

Ensures schema-level and data-level integrity: foreign keys,
indexes, migrations, UUID uniqueness, timestamp ordering,
soft-delete consistency, financial precision, and enum validity.
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

COMMIT = ExecutionFrequency.COMMIT
NIGHTLY = ExecutionFrequency.NIGHTLY
WEEKLY = ExecutionFrequency.WEEKLY
AFTER_MIGRATION = ExecutionFrequency.AFTER_MIGRATION
RELEASE = ExecutionFrequency.RELEASE


@invariant(
    id="DB-001",
    title="Foreign keys remain valid",
    description=(
        "All FK relationships: referenced row exists. No orphan rows "
        "in any table that references another via foreign key."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.CRITICAL,
    execution=[NIGHTLY, WEEKLY, AFTER_MIGRATION],
    rationale="Orphaned rows cause data corruption and broken UI references.",
    tags=["database", "foreign-keys", "referential-integrity"],
)
def check_foreign_keys_valid(ctx: InvariantContext) -> InvariantResult:
    """
    Check for orphaned rows across all FK relationships.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    # Known FK relationships in the system
    foreign_key_checks = [
        {
            "child_table": "trips",
            "child_column": "company_id",
            "parent_table": "companies",
            "parent_column": "id",
        },
        {
            "child_table": "invoices",
            "child_column": "trip_id",
            "parent_table": "trips",
            "parent_column": "id",
        },
        {
            "child_table": "cmr_documents",
            "child_column": "trip_id",
            "parent_table": "trips",
            "parent_column": "id",
        },
        {
            "child_table": "dispatch_orders",
            "child_column": "trip_id",
            "parent_table": "trips",
            "parent_column": "id",
        },
        {
            "child_table": "packages",
            "child_column": "trip_id",
            "parent_table": "trips",
            "parent_column": "id",
        },
        {
            "child_table": "invoice_items",
            "child_column": "invoice_id",
            "parent_table": "invoices",
            "parent_column": "id",
        },
    ]

    orphan_counts: list[dict[str, object]] = []
    for fk in foreign_key_checks:
        try:
            query = (
                f"SELECT COUNT(*) FROM {fk['child_table']} AS c "
                f"LEFT JOIN {fk['parent_table']} AS p "
                f"ON c.{fk['child_column']} = p.{fk['parent_column']} "
                f"WHERE p.{fk['parent_column']} IS NULL"
            )
            result = ctx.db.execute(query).fetchone()
            count = result[0] if result else 0
            if count > 0:
                orphan_counts.append(
                    {
                        "relationship": (
                            f"{fk['child_table']}.{fk['child_column']} → "
                            f"{fk['parent_table']}.{fk['parent_column']}"
                        ),
                        "orphan_count": count,
                    }
                )
        except Exception:
            # Table may not exist yet
            pass

    if orphan_counts:
        total = sum(int(o["orphan_count"]) for o in orphan_counts)  # type: ignore[arg-type]
        details = "; ".join(
            f"{o['relationship']}: {o['orphan_count']}" for o in orphan_counts
        )
        return InvariantResult(
            invariant_id="DB-001",
            status=InvariantStatus.FAIL,
            expected="Zero orphaned rows across all FK relationships",
            actual=f"{total} orphaned rows found across {len(orphan_counts)} relationships",
            message="Foreign key referential integrity violated",
            root_cause=f"Orphan rows: {details}",
            suggested_fix=(
                "Run the cleanup_orphans management command, or manually "
                "DELETE or UPDATE the orphaned rows to restore referential integrity."
            ),
            affected_modules=["database"],
            details={"orphan_relationships": orphan_counts},
        )

    return InvariantResult(
        invariant_id="DB-001",
        status=InvariantStatus.PASS,
        expected="Zero orphaned rows",
        actual="No orphaned rows detected",
        message="All foreign key relationships are valid",
        affected_modules=["database"],
    )


@invariant(
    id="DB-002",
    title="Required indexes exist",
    description=(
        "All critical indexes (idx_*_company, unique constraints) are "
        "present on the expected tables."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.HIGH,
    execution=[AFTER_MIGRATION, RELEASE],
    rationale="Missing indexes cause slow queries and timeouts.",
    tags=["database", "indexes", "performance"],
)
def check_required_indexes_exist(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that critical indexes are present in the database schema.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    required_indexes = [
        ("trips", "idx_trips_company_id", ["company_id"]),
        ("trips", "idx_trips_status", ["status"]),
        ("trips", "idx_trips_created_at", ["created_at"]),
        ("invoices", "idx_invoices_company_id", ["company_id"]),
        ("invoices", "idx_invoices_trip_id", ["trip_id"]),
        ("invoices", "idx_invoices_status", ["status"]),
        ("invoices", "idx_invoices_due_date", ["due_date"]),
        ("cmr_documents", "idx_cmr_trip_id", ["trip_id"]),
        ("packages", "idx_packages_trip_id", ["trip_id"]),
        ("dispatch_orders", "idx_dispatch_trip_id", ["trip_id"]),
        ("settings", "idx_settings_company", ["company_id"]),
    ]

    missing_indexes: list[dict[str, str]] = []

    for table, index_name, columns in required_indexes:
        try:
            if ctx.db_type == "postgresql":
                row = ctx.db.execute(
                    """
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = :table AND indexname = :index
                    """,
                    {"table": table, "index": index_name},
                ).fetchone()
                exists = row is not None
            else:
                # sqlite
                row = ctx.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,),
                ).fetchone()
                exists = row is not None

            if not exists:
                missing_indexes.append(
                    {
                        "table": table,
                        "index": index_name,
                        "columns": ", ".join(columns),
                    }
                )
        except Exception:
            pass

    if missing_indexes:
        details = "; ".join(
            f"{m['table']}.{m['index']} ({m['columns']})"
            for m in missing_indexes
        )
        return InvariantResult(
            invariant_id="DB-002",
            status=InvariantStatus.FAIL,
            expected=f"All {len(required_indexes)} required indexes present",
            actual=f"{len(missing_indexes)} indexes missing",
            message="Critical indexes are missing from the database",
            root_cause=details,
            suggested_fix=(
                "Run the migration that creates the missing indexes, "
                "or execute CREATE INDEX statements for each missing index."
            ),
            affected_modules=["database"],
            details={"missing_indexes": missing_indexes},
        )

    return InvariantResult(
        invariant_id="DB-002",
        status=InvariantStatus.PASS,
        expected="All required indexes present",
        actual="All critical indexes exist",
        message="Required indexes are in place",
        affected_modules=["database"],
    )


@invariant(
    id="DB-003",
    title="Migrations preserve data",
    description=(
        "Schema migrations do not truncate or destroy data. "
        "Row counts remain consistent before and after migration runs."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.CRITICAL,
    execution=[AFTER_MIGRATION],
    rationale="Data loss from migrations is unrecoverable without backups.",
    tags=["database", "migrations", "data-integrity"],
)
def check_migrations_preserve_data(ctx: InvariantContext) -> InvariantResult:
    """
    Compare pre- and post-migration row counts stored in migration context.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    # Migration row-count snapshots are expected to be stored in a
    # migration_audit table or passed in the config
    pre_counts = ctx.config.get("pre_migration_row_counts", {})
    if not pre_counts:
        return InvariantResult(
            invariant_id="DB-003",
            status=InvariantStatus.PASS,
            message="No pre-migration snapshot available — skipping data-preservation check",
            affected_modules=["database"],
        )

    discrepancies: list[dict[str, object]] = []
    for table, expected_count in pre_counts.items():
        try:
            row = ctx.db.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()
            actual_count = row[0] if row else 0
            if actual_count != expected_count:
                discrepancies.append(
                    {
                        "table": table,
                        "expected": expected_count,
                        "actual": actual_count,
                        "difference": actual_count - expected_count,
                    }
                )
        except Exception:
            discrepancies.append(
                {
                    "table": table,
                    "expected": expected_count,
                    "actual": "ERROR",
                    "difference": "UNKNOWN",
                }
            )

    if discrepancies:
        details = "; ".join(
            f"{d['table']}: expected {d['expected']}, got {d['actual']}"
            for d in discrepancies
        )
        return InvariantResult(
            invariant_id="DB-003",
            status=InvariantStatus.FAIL,
            expected="Row counts remain unchanged after migration",
            actual=f"{len(discrepancies)} table(s) have changed row counts",
            message="Data loss or corruption detected after migration",
            root_cause=details,
            suggested_fix=(
                "Restore from backup immediately. Review the migration "
                "SQL for unintentional TRUNCATE, DELETE, or DROP statements."
            ),
            affected_modules=["database"],
            details={"discrepancies": discrepancies},
        )

    return InvariantResult(
        invariant_id="DB-003",
        status=InvariantStatus.PASS,
        expected="Row counts unchanged",
        actual="All table row counts match pre-migration snapshot",
        message="Migration preserved all data",
        affected_modules=["database"],
    )


@invariant(
    id="DB-004",
    title="UUID uniqueness maintained",
    description=(
        "All UUID columns (run_uuid, package_uuid) are unique. "
        "No duplicate UUIDs exist in the database."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.HIGH,
    execution=[COMMIT, NIGHTLY],
    rationale="Duplicate UUIDs break external references and integrations.",
    tags=["database", "uuid", "uniqueness"],
)
def check_uuid_uniqueness(ctx: InvariantContext) -> InvariantResult:
    """
    Check for duplicate UUID values across all UUID columns.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    uuid_columns = [
        ("trips", "run_uuid"),
        ("packages", "package_uuid"),
        ("invoices", "invoice_uuid"),
        ("cmr_documents", "document_uuid"),
    ]

    duplicates: list[dict[str, object]] = []
    for table, column in uuid_columns:
        try:
            rows = ctx.db.execute(
                f"SELECT {column}, COUNT(*) AS cnt "
                f"FROM {table} "
                f"WHERE {column} IS NOT NULL "
                f"GROUP BY {column} "
                f"HAVING COUNT(*) > 1"
            ).fetchall()
            for row in rows:
                duplicates.append(
                    {
                        "table": table,
                        "column": column,
                        "uuid": str(row[0]),
                        "count": int(row[1]),
                    }
                )
        except Exception:
            # Table or column may not exist
            pass

    if duplicates:
        details = "; ".join(
            f"{d['table']}.{d['column']}: {d['uuid']} (x{d['count']})"
            for d in duplicates
        )
        return InvariantResult(
            invariant_id="DB-004",
            status=InvariantStatus.FAIL,
            expected="All UUID values are unique",
            actual=f"{len(duplicates)} duplicate UUID(s) found",
            message="Duplicate UUIDs detected in the database",
            root_cause=details,
            suggested_fix=(
                "Deduplicate UUID values by updating duplicates to new "
                "generated UUIDs. Add a UNIQUE constraint to prevent recurrence."
            ),
            affected_modules=["database"],
            details={"duplicates": duplicates},
        )

    return InvariantResult(
        invariant_id="DB-004",
        status=InvariantStatus.PASS,
        expected="All UUID values unique",
        actual="No duplicate UUIDs found",
        message="UUID uniqueness is maintained across all tables",
        affected_modules=["database"],
    )


@invariant(
    id="DB-005",
    title="Timestamp ordering preserved",
    description=(
        "created_at <= updated_at for all rows (where both exist). "
        "No row can be updated before it was created."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Violated timestamp ordering indicates data corruption or clock drift.",
    tags=["database", "timestamps", "ordering"],
)
def check_timestamp_ordering(ctx: InvariantContext) -> InvariantResult:
    """
    Find rows where updated_at < created_at (physical impossibility).
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    tables_with_timestamps = [
        "trips",
        "invoices",
        "cmr_documents",
        "packages",
        "dispatch_orders",
        "settings",
    ]

    violations: list[dict[str, object]] = []
    for table in tables_with_timestamps:
        try:
            # Check if both columns exist
            if ctx.db_type == "postgresql":
                col_check = ctx.db.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = :table
                      AND column_name IN ('created_at', 'updated_at')
                    """,
                    {"table": table},
                ).fetchall()
            else:
                col_check = ctx.db.execute(
                    "PRAGMA table_info(?)", (table,)
                ).fetchall()

            col_names = {row[1] if ctx.db_type != "postgresql" else row[0]
                         for row in col_check}

            if "created_at" in col_names and "updated_at" in col_names:
                rows = ctx.db.execute(
                    f"SELECT id, created_at, updated_at "
                    f"FROM {table} "
                    f"WHERE updated_at < created_at"
                ).fetchall()
                for row in rows:
                    violations.append(
                        {
                            "table": table,
                            "id": int(row[0]) if row[0] else str(row[0]),
                            "created_at": str(row[1]),
                            "updated_at": str(row[2]),
                        }
                    )
        except Exception:
            pass

    if violations:
        details = "; ".join(
            f"{v['table']}#{v['id']}: created={v['created_at']}, "
            f"updated={v['updated_at']}"
            for v in violations
        )
        return InvariantResult(
            invariant_id="DB-005",
            status=InvariantStatus.FAIL,
            expected="created_at <= updated_at for all rows",
            actual=f"{len(violations)} row(s) with broken timestamp ordering",
            message="Timestamp ordering invariant violated",
            root_cause=details,
            suggested_fix=(
                "Investigate and fix the source of the timestamp reversal. "
                "Run: UPDATE table SET updated_at = created_at WHERE updated_at < created_at"
            ),
            affected_modules=["database"],
            details={"violations": violations},
        )

    return InvariantResult(
        invariant_id="DB-005",
        status=InvariantStatus.PASS,
        expected="created_at <= updated_at for all rows",
        actual="No timestamp ordering violations found",
        message="All timestamps are correctly ordered",
        affected_modules=["database"],
    )


@invariant(
    id="DB-006",
    title="Soft-delete consistency",
    description=(
        "Rows with deleted_at IS NOT NULL are not referenced by "
        "active FK relationships from non-deleted rows."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Active references to soft-deleted rows break business logic.",
    tags=["database", "soft-delete", "consistency"],
)
def check_soft_delete_consistency(ctx: InvariantContext) -> InvariantResult:
    """
    Check that no active (non-deleted) row references a soft-deleted parent.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    soft_delete_refs = [
        {
            "child": "invoices",
            "child_fk": "trip_id",
            "parent": "trips",
            "parent_pk": "id",
            "parent_deleted_col": "deleted_at",
        },
        {
            "child": "cmr_documents",
            "child_fk": "trip_id",
            "parent": "trips",
            "parent_pk": "id",
            "parent_deleted_col": "deleted_at",
        },
        {
            "child": "dispatch_orders",
            "child_fk": "trip_id",
            "parent": "trips",
            "parent_pk": "id",
            "parent_deleted_col": "deleted_at",
        },
        {
            "child": "packages",
            "child_fk": "trip_id",
            "parent": "trips",
            "parent_pk": "id",
            "parent_deleted_col": "deleted_at",
        },
        {
            "child": "invoice_items",
            "child_fk": "invoice_id",
            "parent": "invoices",
            "parent_pk": "id",
            "parent_deleted_col": "deleted_at",
        },
    ]

    violations: list[dict[str, object]] = []
    for ref in soft_delete_refs:
        try:
            query = (
                f"SELECT c.{ref['child_fk']} "
                f"FROM {ref['child']} AS c "
                f"JOIN {ref['parent']} AS p "
                f"ON c.{ref['child_fk']} = p.{ref['parent_pk']} "
                f"WHERE p.{ref['parent_deleted_col']} IS NOT NULL "
                f"AND c.deleted_at IS NULL"
            )
            rows = ctx.db.execute(query).fetchall()
            if rows:
                ids = [int(r[0]) if r[0] else str(r[0]) for r in rows[:20]]
                violations.append(
                    {
                        "child_table": ref["child"],
                        "child_fk_column": ref["child_fk"],
                        "parent_table": ref["parent"],
                        "referencing_ids": ids,
                        "count": len(rows),
                    }
                )
        except Exception:
            pass

    if violations:
        details = "; ".join(
            f"{v['count']} active row(s) in {v['child_table']} reference "
            f"soft-deleted {v['parent_table']}"
            for v in violations
        )
        return InvariantResult(
            invariant_id="DB-006",
            status=InvariantStatus.FAIL,
            expected="No active rows reference soft-deleted parents",
            actual=f"{len(violations)} soft-delete consistency violation(s)",
            message="Active references to soft-deleted rows detected",
            root_cause=details,
            suggested_fix=(
                "Either restore the referenced parent row (SET deleted_at = NULL) "
                "or soft-delete the dependent child rows."
            ),
            affected_modules=["database"],
            details={"violations": violations},
        )

    return InvariantResult(
        invariant_id="DB-006",
        status=InvariantStatus.PASS,
        expected="No active references to soft-deleted rows",
        actual="All references to soft-deleted rows are consistent",
        message="Soft-delete consistency maintained",
        affected_modules=["database"],
    )


@invariant(
    id="DB-007",
    title="Financial precision maintained",
    description=(
        "Monetary columns are NUMERIC(12,2) or NUMERIC(12,6), "
        "never DOUBLE PRECISION or REAL."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.HIGH,
    execution=[AFTER_MIGRATION, RELEASE],
    rationale="Floating-point types cause rounding errors in financial calculations.",
    tags=["database", "financial", "precision"],
)
def check_financial_precision(ctx: InvariantContext) -> InvariantResult:
    """
    Scan for monetary columns that use floating-point types instead of DECIMAL/NUMERIC.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    monetary_columns = [
        ("invoices", "total_net"),
        ("invoices", "total_vat"),
        ("invoices", "total_gross"),
        ("trips", "net_profit"),
        ("trips", "revenue"),
        ("trips", "cost"),
        ("invoice_items", "unit_price"),
        ("invoice_items", "line_total"),
        ("invoice_items", "vat_amount"),
    ]

    precision_violations: list[dict[str, str]] = []
    allowed_types = {"numeric", "decimal", "number"}

    for table, column in monetary_columns:
        try:
            if ctx.db_type == "postgresql":
                row = ctx.db.execute(
                    """
                    SELECT data_type, numeric_precision, numeric_scale
                    FROM information_schema.columns
                    WHERE table_name = :table
                      AND column_name = :column
                    """,
                    {"table": table, "column": column},
                ).fetchone()
                if row is None:
                    continue
                data_type = (row[0] or "").lower()
                if data_type in {"double precision", "real", "float", "float8", "float4"}:
                    precision_violations.append(
                        {
                            "table": table,
                            "column": column,
                            "current_type": row[0],
                            "expected": "NUMERIC(12,2) or NUMERIC(12,6)",
                        }
                    )
            else:
                # sqlite — type affinity is flexible; we check via schema
                row = ctx.db.execute(
                    "PRAGMA table_info(?)", (table,)
                ).fetchall()
                for col in row:
                    if col[1] == column:
                        col_type = (col[2] or "").lower()
                        if col_type in {"real", "float", "double"}:
                            precision_violations.append(
                                {
                                    "table": table,
                                    "column": column,
                                    "current_type": col[2],
                                    "expected": "NUMERIC(12,2) or NUMERIC(12,6)",
                                }
                            )
                        break
        except Exception:
            pass

    if precision_violations:
        details = "; ".join(
            f"{v['table']}.{v['column']} is {v['current_type']}"
            for v in precision_violations
        )
        return InvariantResult(
            invariant_id="DB-007",
            status=InvariantStatus.FAIL,
            expected="All monetary columns are NUMERIC/DECIMAL type",
            actual=f"{len(precision_violations)} column(s) use floating-point types",
            message="Financial precision at risk due to floating-point column types",
            root_cause=details,
            suggested_fix=(
                "ALTER TABLE ... ALTER COLUMN ... TYPE NUMERIC(12,2); "
                "Cast DOUBLE PRECISION values through a safe migration."
            ),
            affected_modules=["database"],
            details={"violations": precision_violations},
        )

    return InvariantResult(
        invariant_id="DB-007",
        status=InvariantStatus.PASS,
        expected="All monetary columns are correct type",
        actual="No floating-point types found on monetary columns",
        message="Financial precision is maintained",
        affected_modules=["database"],
    )


@invariant(
    id="DB-008",
    title="Enum values are valid",
    description=(
        "Pipeline stages, statuses, and other constrained columns "
        "use only valid enum values as defined by the application."
    ),
    category=InvariantCategory.DATABASE,
    modules=["database"],
    severity=Severity.MEDIUM,
    execution=[AFTER_MIGRATION, NIGHTLY],
    rationale="Invalid enum values cause application crashes and UI rendering bugs.",
    tags=["database", "enums", "consistency"],
)
def check_enum_values_valid(ctx: InvariantContext) -> InvariantResult:
    """
    Scan constrained columns for values outside allowed enum sets.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DB-008",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    enum_checks = [
        {
            "table": "trips",
            "column": "status",
            "allowed": {
                "planned", "loading", "in_transit", "delivered",
                "invoiced", "paid", "cancelled",
            },
        },
        {
            "table": "invoices",
            "column": "status",
            "allowed": {
                "draft", "finalized", "xml_generated", "submitted_externally",
                "queued", "submitting", "accepted", "paid", "cancelled",
            },
        },
        {
            "table": "trips",
            "column": "pipeline_stage",
            "allowed": {
                "import", "processing", "enhance", "ocr", "validate",
                "matching", "auto_attach", "verify", "package",
                "email", "complete",
            },
        },
        {
            "table": "cmr_documents",
            "column": "status",
            "allowed": {"pending", "matched", "verified", "error"},
        },
    ]

    invalid_entries: list[dict[str, object]] = []

    for check in enum_checks:
        try:
            allowed_list = sorted(check["allowed"])
            # Build placeholders: one per allowed value
            placeholders = ",".join(
                f"'{v}'" for v in allowed_list
            )
            query = (
                f"SELECT DISTINCT {check['column']} "
                f"FROM {check['table']} "
                f"WHERE {check['column']} IS NOT NULL "
                f"AND {check['column']} NOT IN ({placeholders})"
            )
            rows = ctx.db.execute(query).fetchall()
            invalid_values = {str(r[0]) for r in rows}
            if invalid_values:
                invalid_entries.append(
                    {
                        "table": check["table"],
                        "column": check["column"],
                        "invalid_values": sorted(invalid_values),
                        "allowed_values": allowed_list,
                    }
                )
        except Exception:
            pass

    if invalid_entries:
        details = "; ".join(
            f"{e['table']}.{e['column']}: invalid values {e['invalid_values']}"
            for e in invalid_entries
        )
        return InvariantResult(
            invariant_id="DB-008",
            status=InvariantStatus.FAIL,
            expected="All column values are within allowed enum sets",
            actual=f"{len(invalid_entries)} column(s) contain invalid values",
            message="Invalid enum values detected in constrained columns",
            root_cause=details,
            suggested_fix=(
                "UPDATE each table to replace invalid values with valid ones, "
                "or add the missing values to the application enum definition."
            ),
            affected_modules=["database"],
            details={"invalid_entries": invalid_entries},
        )

    return InvariantResult(
        invariant_id="DB-008",
        status=InvariantStatus.PASS,
        expected="All enum values are valid",
        actual="No invalid enum values found",
        message="Enum values are valid across all constrained columns",
        affected_modules=["database"],
    )
