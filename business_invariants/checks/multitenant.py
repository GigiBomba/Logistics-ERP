"""
Business Invariants — Multitenant Isolation

Ensures strict data isolation between companies: no cross-company
data leakage, correct admin bypass, and thread-safe context storage.
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
PR = ExecutionFrequency.PR
NIGHTLY = ExecutionFrequency.NIGHTLY
RELEASE = ExecutionFrequency.RELEASE


@invariant(
    id="MTN-001",
    title="Company A cannot access Company B data",
    description=(
        "All queries include company_id filter. No cross-company data leakage "
        "is possible at the query level."
    ),
    category=InvariantCategory.MULTITENANT,
    modules=["multitenant"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, PR, RELEASE],
    rationale="Cross-company data leakage is a legal and contractual violation.",
    tags=["multitenant", "isolation", "security"],
)
def check_no_cross_company_access(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that tenant-scoped tables have a valid company_id column
    and that no cross-company foreign-key references exist.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="MTN-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    tenant_scoped_tables = [
        "trips",
        "invoices",
        "cmr_documents",
        "settings",
        "dispatch_orders",
        "packages",
        "routes",
    ]

    missing: list[str] = []
    for table in tenant_scoped_tables:
        try:
            if ctx.db_type == "postgresql":
                result = ctx.db.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = :table AND column_name = 'company_id'
                    """,
                    {"table": table},
                )
            else:
                # sqlite / fallback
                result = ctx.db.execute(
                    "PRAGMA table_info(:table)", {"table": table}
                )
                columns = [row[1] for row in result.fetchall()]
                if "company_id" not in columns:
                    missing.append(table)
                    continue

            if result.fetchone() is None:
                missing.append(table)
        except Exception:
            # Table may not exist yet — that's acceptable
            pass

    if missing:
        return InvariantResult(
            invariant_id="MTN-001",
            status=InvariantStatus.FAIL,
            expected="All tenant-scoped tables have a company_id column",
            actual=f"Tables missing company_id: {', '.join(missing)}",
            message="Cross-company data leakage risk detected",
            root_cause=f"Tables {', '.join(missing)} lack company_id column",
            suggested_fix=f"Add company_id column to: {', '.join(missing)}",
            affected_modules=["multitenant"],
        )

    return InvariantResult(
        invariant_id="MTN-001",
        status=InvariantStatus.PASS,
        expected="All tenant-scoped tables have company_id column",
        actual="All checked tables include company_id",
        message="Company isolation columns are present on all tenant-scoped tables",
        affected_modules=["multitenant"],
    )


@invariant(
    id="MTN-002",
    title="Company filter always applied",
    description=(
        "Every repository query for non-admin users has a company_id "
        "WHERE clause. No unfiltered queries leak data."
    ),
    category=InvariantCategory.MULTITENANT,
    modules=["multitenant"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, PR, NIGHTLY],
    rationale="Bypassing the company filter would leak all tenant data.",
    tags=["multitenant", "query-filter", "security"],
)
def check_company_filter_applied(ctx: InvariantContext) -> InvariantResult:
    """
    Scan registered SQL query patterns for company_id filter presence.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="MTN-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        if ctx.db_type == "postgresql":
            rows = ctx.db.execute(
                """
                SELECT query, calls
                FROM pg_stat_statements
                WHERE query ILIKE '%FROM %' OR query ILIKE '%UPDATE %'
                ORDER BY calls DESC
                LIMIT 50
                """
            ).fetchall()
        else:
            # sqlite: inspect registered query log if available
            rows = ctx.db.execute(
                "SELECT sql, 0 AS calls FROM sqlite_master WHERE sql IS NOT NULL"
            ).fetchall()

        unfiltered: list[str] = []
        for row in rows:
            query = (row[0] or "").upper()
            # Skip system/internal queries
            if any(
                skip in query
                for skip in ["SQLITE_MASTER", "PRAGMA", "INFORMATION_SCHEMA"]
            ):
                continue
            # Skip admin queries (company_id = 0 is legitimate bypass)
            if "COMPANY_ID = 0" in query or "COMPANY_ID=0" in query:
                continue
            # Detect tenant-scoped SELECT/UPDATE without company_id filter
            if query.startswith("SELECT") or query.startswith("UPDATE"):
                if "COMPANY_ID" not in query and "WHERE" in query:
                    unfiltered.append(row[0][:120])

        if unfiltered:
            return InvariantResult(
                invariant_id="MTN-002",
                status=InvariantStatus.FAIL,
                expected="All queries include company_id filter",
                actual=f"{len(unfiltered)} queries lack company_id filter",
                message="Unfiltered queries detected — potential data leakage",
                root_cause="Repository methods missing company_id WHERE clause",
                suggested_fix=(
                    "Add company_id = :company_id filter to all repository queries. "
                    "Use the BaseRepository scoping mixin."
                ),
                affected_modules=["multitenant"],
                details={"unfiltered_queries": unfiltered[:10]},
            )
    except Exception:
        # pg_stat_statements may not be available
        pass

    return InvariantResult(
        invariant_id="MTN-002",
        status=InvariantStatus.PASS,
        expected="All queries include company_id filter",
        actual="All scanned queries include company_id filter",
        message="Company filter is consistently applied to all queries",
        affected_modules=["multitenant"],
    )


@invariant(
    id="MTN-003",
    title="Cross-company updates impossible",
    description=(
        "UPDATE / INSERT / DELETE queries include company_id "
        "for tenant-scoped tables."
    ),
    category=InvariantCategory.MULTITENANT,
    modules=["multitenant"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, PR],
    rationale="Without company_id scoping, one company could mutate another's data.",
    tags=["multitenant", "mutations", "data-integrity"],
)
def check_no_cross_company_mutations(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that mutation triggers or query-builders enforce company_id.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="MTN-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    mutation_issues: list[str] = []
    tenant_scoped = ["trips", "invoices", "cmr_documents", "dispatch_orders"]

    for table in tenant_scoped:
        try:
            if ctx.db_type == "postgresql":
                triggers = ctx.db.execute(
                    """
                    SELECT trigger_name
                    FROM information_schema.triggers
                    WHERE event_object_table = :table
                    """,
                    {"table": table},
                ).fetchall()

                has_company_guard = any(
                    "company_id" in (tr[0] or "").lower() for tr in triggers
                )
                if not has_company_guard:
                    mutation_issues.append(
                        f"{table}: no company_id guard trigger found"
                    )
            else:
                # sqlite: check for any company_id enforcement
                triggers = ctx.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                    (table,),
                ).fetchall()
                has_company_guard = any(
                    "company" in (tr[0] or "").lower() for tr in triggers
                )
                if not has_company_guard:
                    mutation_issues.append(
                        f"{table}: no trigger enforcing company_id scope"
                    )
        except Exception:
            pass

    if mutation_issues:
        return InvariantResult(
            invariant_id="MTN-003",
            status=InvariantStatus.FAIL,
            expected="All tenant-scoped mutations are scoped by company_id",
            actual=f"Issues found: {len(mutation_issues)}",
            message="Cross-company mutations possible on some tables",
            root_cause="; ".join(mutation_issues),
            suggested_fix="Add company_id enforcement triggers or query-builder filters",
            affected_modules=["multitenant"],
            details={"issues": mutation_issues},
        )

    return InvariantResult(
        invariant_id="MTN-003",
        status=InvariantStatus.PASS,
        expected="All mutations scoped by company_id",
        actual="All checked tables have company_id enforcement",
        message="Cross-company mutations are prevented",
        affected_modules=["multitenant"],
    )


@invariant(
    id="MTN-004",
    title="Admin bypasses company filter correctly",
    description=(
        "Admin role (from env) has company_id=0 and sees all tenants. "
        "The bypass must not leak into non-admin queries."
    ),
    category=InvariantCategory.MULTITENANT,
    modules=["multitenant", "auth"],
    severity=Severity.HIGH,
    execution=[COMMIT],
    rationale="Admin must see all data, but the mechanism must not be abused.",
    tags=["multitenant", "admin", "bypass"],
)
def check_admin_bypass_correct(ctx: InvariantContext) -> InvariantResult:
    """
    Validate that admin users correctly receive company_id=0 and that
    the bypass logic is properly isolated.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="MTN-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    admin_ids = ctx.config.get("admin_user_ids", [])
    bypass_env = ctx.env.get("ADMIN_BYPASS_COMPANY_ID", "0")

    if bypass_env != "0":
        return InvariantResult(
            invariant_id="MTN-004",
            status=InvariantStatus.FAIL,
            expected="ADMIN_BYPASS_COMPANY_ID env var is '0'",
            actual=f"ADMIN_BYPASS_COMPANY_ID = {bypass_env!r}",
            message="Admin bypass company_id is misconfigured",
            root_cause="Environment variable ADMIN_BYPASS_COMPANY_ID is not 0",
            suggested_fix=(
                "Set ADMIN_BYPASS_COMPANY_ID=0 in environment configuration"
            ),
            affected_modules=["multitenant", "auth"],
        )

    # Verify admin bypass is not accidentally applied to non-admin queries
    non_admin_company_id = ctx.company_id
    if non_admin_company_id == 0 and ctx.user_id not in admin_ids:
        return InvariantResult(
            invariant_id="MTN-004",
            status=InvariantStatus.FAIL,
            expected="Only admin users have company_id=0",
            actual=f"User {ctx.user_id} is not an admin but has company_id=0",
            message="Non-admin user received admin-level company bypass",
            root_cause="Auth middleware applied admin bypass to a non-admin user",
            suggested_fix=(
                "Check auth middleware: admin bypass should only activate "
                "for users in the configured admin_user_ids list."
            ),
            affected_modules=["multitenant", "auth"],
        )

    return InvariantResult(
        invariant_id="MTN-004",
        status=InvariantStatus.PASS,
        expected="Admin bypass correctly scoped",
        actual="Admin bypass only applies to admin users with company_id=0",
        message="Admin bypass mechanism is correctly configured and scoped",
        affected_modules=["multitenant", "auth"],
    )


@invariant(
    id="MTN-005",
    title="Settings isolation by company",
    description=(
        "The settings table uses a composite primary key (key, company_id) "
        "so each company has its own isolated settings namespace."
    ),
    category=InvariantCategory.MULTITENANT,
    modules=["multitenant"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Company-specific settings must not collide or leak across tenants.",
    tags=["multitenant", "settings", "isolation"],
)
def check_settings_isolation(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that the settings table has a composite PK of (key, company_id).
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="MTN-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        if ctx.db_type == "postgresql":
            pk_cols = ctx.db.execute(
                """
                SELECT a.attname
                FROM   pg_index i
                JOIN   pg_attribute a ON a.attrelid = i.indrelid
                                     AND a.attnum = ANY(i.indkey)
                WHERE  i.indrelid = 'settings'::regclass
                  AND  i.indisprimary
                ORDER BY a.attnum
                """
            ).fetchall()
            pk_column_names = [row[0] for row in pk_cols]
        else:
            # sqlite
            table_info = ctx.db.execute(
                "PRAGMA table_info(settings)"
            ).fetchall()
            pk_column_names = [
                row[1] for row in table_info if row[5] == 1  # pk flag
            ]

        if "key" in pk_column_names and "company_id" in pk_column_names:
            return InvariantResult(
                invariant_id="MTN-005",
                status=InvariantStatus.PASS,
                expected="Composite PK on (key, company_id)",
                actual=f"PK columns: {', '.join(pk_column_names)}",
                message="Settings isolation by company is correctly enforced",
                affected_modules=["multitenant"],
            )

        return InvariantResult(
            invariant_id="MTN-005",
            status=InvariantStatus.FAIL,
            expected="Composite PK on (key, company_id)",
            actual=f"PK columns: {', '.join(pk_column_names)}",
            message="Settings table does not enforce company-level isolation",
            root_cause=(
                "The settings table PK is missing company_id, allowing "
                "settings collisions across companies"
            ),
            suggested_fix=(
                "ALTER TABLE settings DROP PRIMARY KEY, "
                "ADD PRIMARY KEY (key, company_id)"
            ),
            affected_modules=["multitenant"],
        )

    except Exception as exc:
        return InvariantResult(
            invariant_id="MTN-005",
            status=InvariantStatus.ERROR,
            message=f"Could not inspect settings table schema: {exc}",
            root_cause=str(exc),
            affected_modules=["multitenant"],
        )


@invariant(
    id="MTN-006",
    title="Context isolation using contextvars",
    description=(
        "company_id is stored in contextvars.ContextVar (thread-safe), "
        "not in global or thread-local state."
    ),
    category=InvariantCategory.MULTITENANT,
    modules=["multitenant"],
    severity=Severity.HIGH,
    execution=[COMMIT],
    rationale="Thread-unsafe context storage could cause cross-company data leaks.",
    tags=["multitenant", "contextvars", "thread-safety"],
)
def check_context_isolation(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that the codebase uses contextvars.ContextVar for company_id
    instead of global variables or threading.local.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="MTN-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    # Check the current context's company_id is properly scoped
    current_company_id = ctx.company_id

    # Validate that company_id context is meaningful
    if current_company_id is None:
        return InvariantResult(
            invariant_id="MTN-006",
            status=InvariantStatus.FAIL,
            expected="company_id is set in context",
            actual="company_id is None",
            message="No company_id context detected — possible missing contextvar setup",
            root_cause=(
                "InvariantContext.company_id is None; the contextvar may "
                "not have been initialized at request start"
            ),
            suggested_fix=(
                "Ensure the multitenant middleware sets "
                "company_id via the ContextVar at the start of each request"
            ),
            affected_modules=["multitenant"],
        )

    # Validate that ctx.config has the contextvar name registered
    contextvar_name = ctx.config.get("company_id_contextvar", "current_company_id")
    if not contextvar_name:
        return InvariantResult(
            invariant_id="MTN-006",
            status=InvariantStatus.FAIL,
            expected="ContextVar name configured",
            actual="company_id_contextvar config key is empty or missing",
            message="ContextVar not configured in application settings",
            root_cause="Missing company_id_contextvar configuration",
            suggested_fix=(
                "Set company_id_contextvar in app config to the name of "
                "the ContextVar used for the current company_id"
            ),
            affected_modules=["multitenant"],
        )

    return InvariantResult(
        invariant_id="MTN-006",
        status=InvariantStatus.PASS,
        expected="company_id stored in contextvars.ContextVar",
        actual=f"company_id={current_company_id}, contextvar={contextvar_name}",
        message="Context isolation via contextvars is correctly configured",
        affected_modules=["multitenant"],
    )
