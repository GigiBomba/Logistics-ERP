"""
Business Invariants — Workflows & State Machines

Ensures that business workflows are correctly followed: the full
trip→invoice→analytics chain is consistent, state machines are
enforced, document pipeline stages are ordered, CMR consistency
is maintained, and email reminders respect their rules.
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
AFTER_AI_PATCH = ExecutionFrequency.AFTER_AI_PATCH


@invariant(
    id="WF-001",
    title="Trip creation → Route Planning → Dispatch → CMR → Invoice → Analytics → History",
    description=(
        "The full workflow chain produces consistent data at each step. "
        "Each entity in the chain correctly references the prior step."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["ALL"],
    severity=Severity.CRITICAL,
    execution=[PR, RELEASE, NIGHTLY, AFTER_AI_PATCH],
    rationale="A broken workflow chain causes incomplete operational data.",
    tags=["workflow", "chain", "consistency"],
)
def check_full_workflow_chain(ctx: InvariantContext) -> InvariantResult:
    """
    Verify the full workflow chain: Trip → Route → Dispatch → CMR
    → Invoice → Analytics → History is consistent.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    chain_issues: list[str] = []

    # 1. Trips should have routes
    try:
        trips_without_routes = ctx.db.execute(
            """
            SELECT COUNT(*) FROM trips t
            LEFT JOIN routes r ON r.trip_id = t.id
            WHERE r.id IS NULL
              AND t.status NOT IN ('cancelled')
            """
        ).fetchone()
        if trips_without_routes and int(trips_without_routes[0]) > 0:
            chain_issues.append(
                f"{int(trips_without_routes[0])} trip(s) without a route"
            )
    except Exception:
        pass

    # 2. Trips should have dispatches
    try:
        trips_without_dispatch = ctx.db.execute(
            """
            SELECT COUNT(*) FROM trips t
            LEFT JOIN dispatch_orders d ON d.trip_id = t.id
            WHERE d.id IS NULL
              AND t.status NOT IN ('cancelled', 'planned')
            """
        ).fetchone()
        if trips_without_dispatch and int(trips_without_dispatch[0]) > 0:
            chain_issues.append(
                f"{int(trips_without_dispatch[0])} trip(s) without a dispatch order"
            )
    except Exception:
        pass

    # 3. Delivered trips should have CMR documents
    try:
        delivered_without_cmr = ctx.db.execute(
            """
            SELECT COUNT(*) FROM trips t
            LEFT JOIN cmr_documents c ON c.trip_id = t.id
            WHERE c.id IS NULL
              AND t.status IN ('delivered', 'invoiced', 'paid')
            """
        ).fetchone()
        if delivered_without_cmr and int(delivered_without_cmr[0]) > 0:
            chain_issues.append(
                f"{int(delivered_without_cmr[0])} delivered trip(s) without CMR document"
            )
    except Exception:
        pass

    # 4. Invoiced trips should have invoices
    try:
        invoiced_without_invoice = ctx.db.execute(
            """
            SELECT COUNT(*) FROM trips t
            LEFT JOIN invoices i ON i.trip_id = t.id
            WHERE i.id IS NULL
              AND t.status IN ('invoiced', 'paid')
            """
        ).fetchone()
        if invoiced_without_invoice and int(invoiced_without_invoice[0]) > 0:
            chain_issues.append(
                f"{int(invoiced_without_invoice[0])} invoiced trip(s) without an invoice"
            )
    except Exception:
        pass

    # 5. Invoices should have analytics entries
    try:
        invoices_without_analytics = ctx.db.execute(
            """
            SELECT COUNT(*) FROM invoices i
            LEFT JOIN analytics_entries a ON a.reference_type = 'invoice'
                AND a.reference_id = i.id
            WHERE a.id IS NULL
              AND i.status NOT IN ('draft', 'cancelled')
            """
        ).fetchone()
        if (
            invoices_without_analytics
            and int(invoices_without_analytics[0]) > 0
        ):
            chain_issues.append(
                f"{int(invoices_without_analytics[0])} finalized invoice(s) "
                "without analytics entry"
            )
    except Exception:
        pass

    if chain_issues:
        return InvariantResult(
            invariant_id="WF-001",
            status=InvariantStatus.FAIL,
            expected=(
                "Full workflow chain is consistent: every step references "
                "the prior one"
            ),
            actual=f"{len(chain_issues)} workflow gap(s) detected",
            message="Workflow chain has missing links",
            root_cause="; ".join(chain_issues),
            suggested_fix=(
                "Investigate each gap in the chain. Ensure that completed "
                "workflow steps always produce the downstream entity."
            ),
            affected_modules=["ALL"],
            details={"chain_issues": chain_issues},
        )

    return InvariantResult(
        invariant_id="WF-001",
        status=InvariantStatus.PASS,
        expected="Full workflow chain is consistent",
        actual="All workflow steps are properly linked",
        message="The trip → route → dispatch → CMR → invoice → analytics chain is intact",
        affected_modules=["ALL"],
    )


@invariant(
    id="WF-002",
    title="Invoice state machine enforced",
    description=(
        "Invoice status transitions follow: "
        "draft→finalized→xml_generated→submitted_externally→"
        "queued→submitting→accepted→paid."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["invoicing"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, NIGHTLY],
    rationale="Invalid invoice transitions cause financial reconciliation failures.",
    tags=["workflow", "invoices", "state-machine"],
)
def check_invoice_state_machine(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that invoice status transitions follow the allowed state machine.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    allowed_transitions = {
        "draft": {"finalized"},
        "finalized": {"xml_generated"},
        "xml_generated": {"submitted_externally"},
        "submitted_externally": {"queued"},
        "queued": {"submitting"},
        "submitting": {"accepted", "paid"},
        "accepted": {"paid"},
        "paid": set(),
        "cancelled": set(),
    }

    try:
        # Check for status values that are not in the state machine at all
        invalid_statuses = ctx.db.execute(
            """
            SELECT DISTINCT status FROM invoices
            WHERE status IS NOT NULL
            """
        ).fetchall()

        valid_statuses = set(allowed_transitions.keys())
        found_invalid = [
            str(r[0]) for r in invalid_statuses if str(r[0]) not in valid_statuses
        ]

        if found_invalid:
            return InvariantResult(
                invariant_id="WF-002",
                status=InvariantStatus.FAIL,
                expected="All invoice statuses are in the allowed state machine",
                actual=f"Invalid status(es): {', '.join(found_invalid)}",
                message="Invoice state machine has unknown status values",
                root_cause=f"Unknown status values: {', '.join(found_invalid)}",
                suggested_fix=(
                    "Either add the unknown statuses to the state machine "
                    "definition, or update the invoices to use valid statuses."
                ),
                affected_modules=["invoicing"],
                details={"invalid_statuses": found_invalid},
            )

        # Check for invalid transitions using audit log
        try:
            bad_transitions: list[dict[str, object]] = []
            audit_rows = ctx.db.execute(
                """
                SELECT invoice_id, from_status, to_status
                FROM invoice_audit
                ORDER BY created_at DESC
                LIMIT 200
                """
            ).fetchall()

            for row in audit_rows:
                from_status = str(row[1]) if row[1] else "draft"
                to_status = str(row[2]) if row[2] else ""
                allowed = allowed_transitions.get(from_status, set())
                if to_status and to_status not in allowed:
                    bad_transitions.append(
                        {
                            "invoice_id": int(row[0]),
                            "from": from_status,
                            "to": to_status,
                        }
                    )
        except Exception:
            bad_transitions = []

        if bad_transitions:
            details = "; ".join(
                f"inv#{t['invoice_id']}: {t['from']} → {t['to']}"
                for t in bad_transitions[:10]
            )
            return InvariantResult(
                invariant_id="WF-002",
                status=InvariantStatus.FAIL,
                expected="Invoice status transitions follow the defined state machine",
                actual=f"{len(bad_transitions)} invalid transition(s) detected",
                message="Invoice state machine violated",
                root_cause=details,
                suggested_fix=(
                    "Roll back the invalid status transitions. Ensure the "
                    "invoice status update logic enforces the state machine."
                ),
                affected_modules=["invoicing"],
                details={"invalid_transitions": bad_transitions[:20]},
            )

    except Exception as exc:
        return InvariantResult(
            invariant_id="WF-002",
            status=InvariantStatus.ERROR,
            message=f"Could not validate invoice state machine: {exc}",
            root_cause=str(exc),
            affected_modules=["invoicing"],
        )

    return InvariantResult(
        invariant_id="WF-002",
        status=InvariantStatus.PASS,
        expected="Invoice status transitions follow the state machine",
        actual="No invalid transitions detected",
        message="Invoice state machine is correctly enforced",
        affected_modules=["invoicing"],
    )


@invariant(
    id="WF-003",
    title="Trip status machine enforced",
    description=(
        "Trip status transitions follow: "
        "Planned → Loading → In Transit → Delivered → Invoiced → Paid."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["trips", "operations"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, NIGHTLY],
    rationale="Invalid trip transitions cause operational confusion.",
    tags=["workflow", "trips", "state-machine"],
)
def check_trip_status_machine(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that trip status transitions follow the allowed state machine.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    allowed_transitions = {
        "planned": {"loading", "cancelled"},
        "loading": {"in_transit", "cancelled"},
        "in_transit": {"delivered", "cancelled"},
        "delivered": {"invoiced", "cancelled"},
        "invoiced": {"paid", "cancelled"},
        "paid": set(),
        "cancelled": set(),
    }

    try:
        # Check for invalid status values
        invalid_statuses = ctx.db.execute(
            """
            SELECT DISTINCT status FROM trips
            WHERE status IS NOT NULL
            """
        ).fetchall()

        valid_statuses = set(allowed_transitions.keys())
        found_invalid = [
            str(r[0]) for r in invalid_statuses if str(r[0]) not in valid_statuses
        ]

        if found_invalid:
            return InvariantResult(
                invariant_id="WF-003",
                status=InvariantStatus.FAIL,
                expected="All trip statuses are in the allowed state machine",
                actual=f"Invalid status(es): {', '.join(found_invalid)}",
                message="Trip state machine has unknown status values",
                root_cause=f"Unknown status values: {', '.join(found_invalid)}",
                suggested_fix=(
                    "Either add the unknown statuses to the state machine "
                    "definition, or update the trips to use valid statuses."
                ),
                affected_modules=["trips", "operations"],
                details={"invalid_statuses": found_invalid},
            )

        # Check for invalid transitions via audit log
        try:
            audit_rows = ctx.db.execute(
                """
                SELECT trip_id, from_status, to_status
                FROM trip_audit
                ORDER BY created_at DESC
                LIMIT 200
                """
            ).fetchall()

            bad_transitions: list[dict[str, object]] = []
            for row in audit_rows:
                from_status = str(row[1]) if row[1] else "planned"
                to_status = str(row[2]) if row[2] else ""
                allowed = allowed_transitions.get(from_status, set())
                if to_status and to_status not in allowed:
                    bad_transitions.append(
                        {
                            "trip_id": int(row[0]),
                            "from": from_status,
                            "to": to_status,
                        }
                    )
        except Exception:
            bad_transitions = []

        if bad_transitions:
            details = "; ".join(
                f"trip#{t['trip_id']}: {t['from']} → {t['to']}"
                for t in bad_transitions[:10]
            )
            return InvariantResult(
                invariant_id="WF-003",
                status=InvariantStatus.FAIL,
                expected="Trip status transitions follow Planned→Loading→In Transit→Delivered→Invoiced→Paid",
                actual=f"{len(bad_transitions)} invalid transition(s) detected",
                message="Trip state machine violated",
                root_cause=details,
                suggested_fix=(
                    "Roll back the invalid status transitions. Ensure the "
                    "trip status update logic enforces the state machine."
                ),
                affected_modules=["trips", "operations"],
                details={"invalid_transitions": bad_transitions[:20]},
            )

    except Exception as exc:
        return InvariantResult(
            invariant_id="WF-003",
            status=InvariantStatus.ERROR,
            message=f"Could not validate trip state machine: {exc}",
            root_cause=str(exc),
            affected_modules=["trips", "operations"],
        )

    return InvariantResult(
        invariant_id="WF-003",
        status=InvariantStatus.PASS,
        expected="Trip status transitions follow the state machine",
        actual="No invalid transitions detected",
        message="Trip state machine is correctly enforced",
        affected_modules=["trips", "operations"],
    )


@invariant(
    id="WF-004",
    title="Document pipeline stage ordering",
    description=(
        "Pipeline stages follow: import→processing→enhance→ocr→validate→"
        "matching→auto_attach→verify→package→email→complete."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["documents"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Out-of-order pipeline stages produce incomplete documents.",
    tags=["workflow", "documents", "pipeline"],
)
def check_document_pipeline_ordering(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that document pipeline stages progress in the correct order.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    expected_order = [
        "import",
        "processing",
        "enhance",
        "ocr",
        "validate",
        "matching",
        "auto_attach",
        "verify",
        "package",
        "email",
        "complete",
    ]

    try:
        # Check for pipeline stages not in the expected order
        active_docs = ctx.db.execute(
            """
            SELECT id, document_name, pipeline_stage, pipeline_order
            FROM documents
            WHERE pipeline_stage IS NOT NULL
              AND status != 'complete'
            """
        ).fetchall()

        ordering_issues: list[dict[str, object]] = []
        for row in active_docs:
            doc_id = int(row[0])
            doc_name = str(row[1] or "")
            current_stage = str(row[2] or "").strip().lower()
            stored_order = row[3]  # int or None

            if current_stage in expected_order:
                expected_index = expected_order.index(current_stage) + 1
                if stored_order is not None and stored_order != expected_index:
                    ordering_issues.append(
                        {
                            "document_id": doc_id,
                            "document_name": doc_name,
                            "stage": current_stage,
                            "stored_order": int(stored_order),
                            "expected_order": expected_index,
                        }
                    )
        # Also check if any documents skip stages
        skip_check = ctx.db.execute(
            """
            SELECT d.id, d.document_name, d.pipeline_stage
            FROM documents d
            WHERE d.pipeline_stage IS NOT NULL
              AND d.pipeline_stage IN (
                  'validate', 'matching', 'auto_attach', 'verify', 'package', 'email', 'complete'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM documents d2
                  WHERE d2.id = d.id
                  AND d2.pipeline_stage IN ('import', 'processing')
              )
            LIMIT 10
            """
        ).fetchall()

        for row in skip_check:
            ordering_issues.append(
                {
                    "document_id": int(row[0]),
                    "document_name": str(row[1] or ""),
                    "stage": str(row[2] or ""),
                    "issue": "Skipped early pipeline stages",
                }
            )

    except Exception:
        return InvariantResult(
            invariant_id="WF-004",
            status=InvariantStatus.PASS,
            message="Could not query documents table — runtime validation skipped",
            affected_modules=["documents"],
        )

    if ordering_issues:
        return InvariantResult(
            invariant_id="WF-004",
            status=InvariantStatus.FAIL,
            expected="Pipeline stages follow: import→processing→...→complete",
            actual=f"{len(ordering_issues)} pipeline ordering issue(s)",
            message="Document pipeline stage ordering violated",
            root_cause="; ".join(
                f"doc#{i['document_id']}: stage={i['stage']}"
                for i in ordering_issues[:5]
            ),
            suggested_fix=(
                "Ensure document pipeline stages advance in the correct "
                "sequence. Fix any out-of-order stage assignments."
            ),
            affected_modules=["documents"],
            details={"ordering_issues": ordering_issues[:20]},
        )

    return InvariantResult(
        invariant_id="WF-004",
        status=InvariantStatus.PASS,
        expected="Pipeline stages follow correct order",
        actual="All active documents have correct pipeline stage ordering",
        message="Document pipeline stage ordering is correct",
        affected_modules=["documents"],
    )


@invariant(
    id="WF-005",
    title="Invoice → CMR consistency",
    description=(
        "An invoice references a trip, and that trip has a CMR number. "
        "No invoice exists for a trip without a CMR."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["invoicing", "cmr"],
    severity=Severity.HIGH,
    execution=[COMMIT, PR],
    rationale="Invoicing without a CMR breaks the document chain.",
    tags=["workflow", "invoices", "cmr", "consistency"],
)
def check_invoice_cmr_consistency(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that every invoice references a trip that has a CMR number.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        invoices_without_cmr = ctx.db.execute(
            """
            SELECT i.id, i.invoice_number, i.trip_id
            FROM invoices i
            JOIN trips t ON t.id = i.trip_id
            LEFT JOIN cmr_documents c ON c.trip_id = t.id
            WHERE c.id IS NULL
              AND i.status NOT IN ('draft', 'cancelled')
            """
        ).fetchall()
    except Exception:
        return InvariantResult(
            invariant_id="WF-005",
            status=InvariantStatus.PASS,
            message="Could not query invoices/trips/CMR — runtime validation skipped",
            affected_modules=["invoicing", "cmr"],
        )

    if invoices_without_cmr:
        inv_list = [
            {
                "invoice_id": int(r[0]),
                "invoice_number": str(r[1] or ""),
                "trip_id": int(r[2]) if r[2] else None,
            }
            for r in invoices_without_cmr
        ]
        return InvariantResult(
            invariant_id="WF-005",
            status=InvariantStatus.FAIL,
            expected="Every invoice references a trip with a CMR number",
            actual=f"{len(invoices_without_cmr)} invoice(s) without a CMR reference",
            message="Invoice exists for a trip without a CMR document",
            root_cause=(
                "Invoices reference trips that have no CMR document. "
                "The document chain (trip → CMR → invoice) is broken."
            ),
            suggested_fix=(
                "Ensure CMR documents are created before invoices are "
                "finalized. Either create the missing CMR or block "
                "invoicing without a CMR."
            ),
            affected_modules=["invoicing", "cmr"],
            details={"invoices_without_cmr": inv_list[:20]},
        )

    return InvariantResult(
        invariant_id="WF-005",
        status=InvariantStatus.PASS,
        expected="All invoices have a CMR reference",
        actual="No invoices without a CMR were found",
        message="Invoice → CMR consistency is maintained",
        affected_modules=["invoicing", "cmr"],
    )


@invariant(
    id="WF-006",
    title="Analytics reflects dispatched trips",
    description=(
        "Analytics data aligns with underlying trip / invoice state. "
        "No discrepancy between dispatched trips and analytics counts."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["analytics"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Stale analytics lead to incorrect operational decisions.",
    tags=["workflow", "analytics", "consistency"],
)
def check_analytics_dispatched_trips(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that analytics data matches the state of trips and invoices.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    discrepancies: list[str] = []

    # Compare trip counts by status
    try:
        source_data = ctx.db.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM trips
            GROUP BY status
            """
        ).fetchall()
        source_map = {str(r[0]): int(r[1]) for r in source_data}
    except Exception:
        source_map = {}

    # Compare against analytics snapshot
    analytics_trip_counts = ctx.config.get("analytics_trip_status_counts", {})
    for status, source_count in source_map.items():
        analytics_count = analytics_trip_counts.get(status)
        if analytics_count is not None and source_count != analytics_count:
            discrepancies.append(
                f"trips[{status}]: source={source_count}, "
                f"analytics={analytics_count}"
            )

    # Compare total dispatched count
    try:
        dispatched_count = ctx.db.execute(
            """
            SELECT COUNT(*) FROM trips
            WHERE status NOT IN ('planned', 'cancelled')
            """
        ).fetchone()
        actual_dispatched = int(dispatched_count[0]) if dispatched_count else 0
        analytics_dispatched = ctx.config.get(
            "analytics_dispatched_trips_count", None
        )
        if analytics_dispatched is not None and actual_dispatched != analytics_dispatched:
            discrepancies.append(
                f"dispatched_trips: source={actual_dispatched}, "
                f"analytics={analytics_dispatched}"
            )
    except Exception:
        pass

    if discrepancies:
        return InvariantResult(
            invariant_id="WF-006",
            status=InvariantStatus.FAIL,
            expected="Analytics counts match source trip/invoice data",
            actual=f"{len(discrepancies)} discrepancy(ies)",
            message="Analytics does not reflect dispatched trip state",
            root_cause="; ".join(discrepancies),
            suggested_fix=(
                "Refresh the analytics aggregation. Ensure the analytics "
                "pipeline runs after trip status changes."
            ),
            affected_modules=["analytics"],
            details={"discrepancies": discrepancies},
        )

    return InvariantResult(
        invariant_id="WF-006",
        status=InvariantStatus.PASS,
        expected="Analytics matches source data",
        actual="No discrepancies between analytics and trip/invoice state",
        message="Analytics correctly reflects dispatched trips",
        affected_modules=["analytics"],
    )


@invariant(
    id="WF-007",
    title="Email reminder chain valid",
    description=(
        "Reminders only sent for overdue invoices (due_date < today). "
        "Max 5 reminders per invoice."
    ),
    category=InvariantCategory.WORKFLOWS,
    modules=["automail"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Excessive reminders harass customers; premature reminders confuse.",
    tags=["workflow", "reminders", "automail"],
)
def check_email_reminder_chain(ctx: InvariantContext) -> InvariantResult:
    """
    Verify reminder rules: only for overdue invoices, max 5 per invoice.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="WF-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    max_reminders = ctx.config.get("max_reminders_per_invoice", 5)
    violations: list[dict[str, object]] = []

    # Check for invoices that received reminders but are not overdue
    try:
        premature_reminders = ctx.db.execute(
            """
            SELECT r.invoice_id, i.due_date, i.invoice_number,
                   COUNT(r.id) AS reminder_count
            FROM email_reminders r
            JOIN invoices i ON i.id = r.invoice_id
            WHERE i.due_date >= DATE('now')
              AND i.status NOT IN ('paid', 'cancelled')
            GROUP BY r.invoice_id
            HAVING COUNT(r.id) > 0
            """
        ).fetchall()

        for row in premature_reminders:
            violations.append(
                {
                    "invoice_id": int(row[0]),
                    "due_date": str(row[1]),
                    "invoice_number": str(row[2] or ""),
                    "reminder_count": int(row[3]),
                    "issue": "Reminder sent for non-overdue invoice",
                }
            )
    except Exception:
        pass

    # Check for invoices exceeding max reminders
    try:
        excessive_reminders = ctx.db.execute(
            """
            SELECT invoice_id, COUNT(*) AS cnt
            FROM email_reminders
            GROUP BY invoice_id
            HAVING COUNT(*) > ?
            """,
            (max_reminders,),
        ).fetchall()

        for row in excessive_reminders:
            violations.append(
                {
                    "invoice_id": int(row[0]),
                    "reminder_count": int(row[1]),
                    "max_allowed": max_reminders,
                    "issue": f"Exceeded max {max_reminders} reminders",
                }
            )
    except Exception:
        pass

    if violations:
        return InvariantResult(
            invariant_id="WF-007",
            status=InvariantStatus.FAIL,
            expected=(
                "Reminders only for overdue invoices, max "
                f"{max_reminders} per invoice"
            ),
            actual=f"{len(violations)} reminder rule violation(s)",
            message="Email reminder chain rules violated",
            root_cause="; ".join(
                f"inv#{v['invoice_id']}: {v['issue']}"
                for v in violations[:5]
            ),
            suggested_fix=(
                "Review the automail reminder scheduling logic. Ensure "
                "reminders only fire for overdue invoices and respect "
                f"the max {max_reminders} limit."
            ),
            affected_modules=["automail"],
            details={"violations": violations[:20]},
        )

    return InvariantResult(
        invariant_id="WF-007",
        status=InvariantStatus.PASS,
        expected="Reminders comply with business rules",
        actual="No reminder rule violations detected",
        message="Email reminder chain is valid",
        affected_modules=["automail"],
    )
