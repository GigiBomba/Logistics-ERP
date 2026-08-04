"""
Operion Business Invariant Framework — Fleet Module Checks

All invariants related to truck management, maintenance, and fleet health.
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


# ──────────────────────────────────────────────
# FLE-001 — Truck plate numbers are unique
# ──────────────────────────────────────────────

@invariant(
    id="FLE-001",
    title="Truck plate numbers are unique",
    description="No two active trucks share the same plate_number.",
    category=InvariantCategory.FLEET,
    modules=["fleet"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.PR],
    rationale="Duplicate plate numbers would cause regulatory violations and "
    "operational confusion in dispatch and toll systems.",
)
def check_fleet_unique_plate_numbers(ctx: InvariantContext) -> InvariantResult:
    """Verify that no two active (non-deleted) trucks share a plate number."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT plate_number, COUNT(*) AS cnt
            FROM trucks
            WHERE deleted_at IS NULL
            GROUP BY plate_number
            HAVING COUNT(*) > 1
            """
        )
        duplicates = cursor.fetchall()
        if duplicates:
            detail = "; ".join(
                f"{row[0]!r} appears {row[1]} times" for row in duplicates
            )
            return InvariantResult(
                invariant_id="FLE-001",
                status=InvariantStatus.FAIL,
                expected="All active trucks have unique plate numbers",
                actual=f"Duplicate plate numbers found: {detail}",
                message="Truck plate numbers are not unique",
                root_cause="Multiple active trucks share the same registration plate",
                suggested_fix="Reassign or update duplicate plate numbers so each "
                "truck has a unique plate",
                affected_modules=["fleet"],
            )
        return InvariantResult(
            invariant_id="FLE-001",
            status=InvariantStatus.PASS,
            message="All active trucks have unique plate numbers",
            affected_modules=["fleet"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-001",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet"],
        )


# ──────────────────────────────────────────────
# FLE-002 — Truck assignments cannot overlap
# ──────────────────────────────────────────────

@invariant(
    id="FLE-002",
    title="Truck assignments cannot overlap",
    description="A truck cannot be assigned to two trips with overlapping date ranges.",
    category=InvariantCategory.FLEET,
    modules=["fleet", "trips", "dispatch"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.NIGHTLY],
    rationale="Overlapping truck assignments lead to double-booking and "
    "operational conflicts in the dispatch schedule.",
)
def check_fleet_no_overlapping_truck_assignments(
    ctx: InvariantContext,
) -> InvariantResult:
    """Verify no truck is assigned to overlapping trips."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT a.truck_id,
                   a.id AS trip_a_id,
                   b.id AS trip_b_id,
                   a.start_date,
                   a.end_date
            FROM trips a
            JOIN trips b
               ON a.truck_id = b.truck_id
              AND a.id < b.id
              AND a.start_date < b.end_date
              AND b.start_date < a.end_date
            WHERE a.truck_id IS NOT NULL
              AND b.truck_id IS NOT NULL
            """
        )
        overlaps = cursor.fetchall()
        if overlaps:
            detail = "; ".join(
                f"Truck {row[0]}: Trip {row[1]} overlaps with Trip {row[2]} "
                f"({row[3]} to {row[4]})"
                for row in overlaps[:10]
            )
            remaining = len(overlaps) - 10
            if remaining > 0:
                detail += f" (and {remaining} more overlapping pairs)"
            return InvariantResult(
                invariant_id="FLE-002",
                status=InvariantStatus.FAIL,
                expected="Each truck has at most one active trip per time period",
                actual=f"Found {len(overlaps)} overlapping trip pairs",
                message="Truck assignments overlap in time",
                root_cause="A truck was scheduled for multiple trips with "
                "conflicting date ranges",
                suggested_fix="Reschedule trips so that no truck has overlapping "
                "date ranges",
                affected_modules=["fleet", "trips", "dispatch"],
            )
        return InvariantResult(
            invariant_id="FLE-002",
            status=InvariantStatus.PASS,
            message="No overlapping truck assignments found",
            affected_modules=["fleet", "trips", "dispatch"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-002",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet", "trips", "dispatch"],
        )


# ──────────────────────────────────────────────
# FLE-003 — Deleted trucks cannot be assigned
# ──────────────────────────────────────────────

@invariant(
    id="FLE-003",
    title="Deleted trucks cannot be assigned",
    description="Trips must not reference trucks with deleted_at IS NOT NULL.",
    category=InvariantCategory.FLEET,
    modules=["fleet", "trips"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.NIGHTLY],
    rationale="Assigning a deleted truck to a trip results in broken references "
    "and missing operational data.",
)
def check_fleet_deleted_trucks_not_assigned(ctx: InvariantContext) -> InvariantResult:
    """Verify no active trip references a soft-deleted truck."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT t.id, t.truck_id, tr.plate_number, tr.deleted_at
            FROM trips t
            JOIN trucks tr ON t.truck_id = tr.id
            WHERE tr.deleted_at IS NOT NULL
            """
        )
        bad_references = cursor.fetchall()
        if bad_references:
            detail = "; ".join(
                f"Trip {row[0]} references deleted truck {row[1]} ({row[2]})"
                for row in bad_references[:10]
            )
            remaining = len(bad_references) - 10
            if remaining > 0:
                detail += f" (and {remaining} more references)"
            return InvariantResult(
                invariant_id="FLE-003",
                status=InvariantStatus.FAIL,
                expected="Trips reference only non-deleted trucks",
                actual=f"{len(bad_references)} trip(s) reference deleted trucks",
                message="Deleted trucks are still assigned to trips",
                root_cause="Trips still reference trucks that have been "
                "soft-deleted (deleted_at IS NOT NULL)",
                suggested_fix="Reassign those trips to active trucks, or restore "
                "the referenced trucks",
                affected_modules=["fleet", "trips"],
            )
        return InvariantResult(
            invariant_id="FLE-003",
            status=InvariantStatus.PASS,
            message="No trips reference deleted trucks",
            affected_modules=["fleet", "trips"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-003",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet", "trips"],
        )


# ──────────────────────────────────────────────
# FLE-004 — Maintenance windows block dispatch
# ──────────────────────────────────────────────

@invariant(
    id="FLE-004",
    title="Maintenance windows block dispatch",
    description="If a truck has overdue maintenance, it should not be in active trips.",
    category=InvariantCategory.FLEET,
    modules=["fleet", "dispatch"],
    severity=Severity.HIGH,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.NIGHTLY],
    rationale="Running trucks with overdue maintenance increases risk of "
    "breakdowns, safety violations, and regulatory penalties.",
)
def check_fleet_overdue_maintenance_blocks_dispatch(
    ctx: InvariantContext,
) -> InvariantResult:
    """Verify trucks with overdue maintenance are not in active trips."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT DISTINCT tr.id, tr.plate_number
            FROM trucks tr
            JOIN maintenance_records mr ON mr.truck_id = tr.id
            JOIN trips t ON t.truck_id = tr.id
            WHERE mr.status IN ('overdue', 'pending')
              AND mr.scheduled_date <= CURRENT_DATE
              AND t.status IN ('active', 'in_progress')
              AND tr.deleted_at IS NULL
            """
        )
        blocked_trucks = cursor.fetchall()
        if blocked_trucks:
            detail = "; ".join(
                f"Truck {row[0]} ({row[1]})" for row in blocked_trucks
            )
            return InvariantResult(
                invariant_id="FLE-004",
                status=InvariantStatus.FAIL,
                expected="Trucks with overdue maintenance are not in active trips",
                actual=f"{len(blocked_trucks)} truck(s) with overdue maintenance "
                f"are on active trips: {detail}",
                message="Overdue maintenance trucks are still dispatched",
                root_cause="Trips are active for trucks that have maintenance "
                "records past their scheduled date",
                suggested_fix="Complete the overdue maintenance or remove the "
                "truck from the active trip",
                affected_modules=["fleet", "dispatch"],
            )
        return InvariantResult(
            invariant_id="FLE-004",
            status=InvariantStatus.PASS,
            message="No trucks with overdue maintenance are in active trips",
            affected_modules=["fleet", "dispatch"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-004",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet", "dispatch"],
        )


# ──────────────────────────────────────────────
# FLE-005 — Truck status consistency
# ──────────────────────────────────────────────

@invariant(
    id="FLE-005",
    title="Truck status consistency",
    description="active_status == 1 when status == 'active', else 0.",
    category=InvariantCategory.FLEET,
    modules=["fleet"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Status inconsistency causes dispatch logic to misread "
    "truck availability, leading to scheduling errors.",
)
def check_fleet_truck_status_consistency(ctx: InvariantContext) -> InvariantResult:
    """Verify the boolean active_status matches the text status field."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT id, plate_number, status, active_status
            FROM trucks
            WHERE (status = 'active' AND active_status != 1)
               OR (status != 'active' AND active_status != 0)
            """
        )
        inconsistent = cursor.fetchall()
        if inconsistent:
            detail = "; ".join(
                f"Truck {row[0]} ({row[1]}): status={row[2]!r}, "
                f"active_status={row[3]!r}"
                for row in inconsistent[:10]
            )
            remaining = len(inconsistent) - 10
            if remaining > 0:
                detail += f" (and {remaining} more)"
            return InvariantResult(
                invariant_id="FLE-005",
                status=InvariantStatus.FAIL,
                expected="active_status=1 when status='active', otherwise 0",
                actual=f"{len(inconsistent)} truck(s) have inconsistent status",
                message="Truck status fields are inconsistent",
                root_cause="The active_status flag does not match the status text field",
                suggested_fix="Update active_status to 1 for active trucks and "
                "0 for all other statuses",
                affected_modules=["fleet"],
            )
        return InvariantResult(
            invariant_id="FLE-005",
            status=InvariantStatus.PASS,
            message="All trucks have consistent status fields",
            affected_modules=["fleet"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-005",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet"],
        )


# ──────────────────────────────────────────────
# FLE-006 — Truck health score is within 0-100
# ──────────────────────────────────────────────

@invariant(
    id="FLE-006",
    title="Truck health score is within 0-100",
    description="truck_health_scores.score between 0 and 100.",
    category=InvariantCategory.FLEET,
    modules=["fleet", "maintenance"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.NIGHTLY],
    rationale="Health scores outside the valid range indicate data corruption "
    "or integration errors in the telemetry pipeline.",
)
def check_fleet_truck_health_score_range(ctx: InvariantContext) -> InvariantResult:
    """Verify all truck health scores are within the valid 0-100 range."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT truck_id, score, recorded_at
            FROM truck_health_scores
            WHERE score < 0 OR score > 100
            """
        )
        out_of_range = cursor.fetchall()
        if out_of_range:
            detail = "; ".join(
                f"Truck {row[0]}: score={row[1]} (at {row[2]})"
                for row in out_of_range[:10]
            )
            remaining = len(out_of_range) - 10
            if remaining > 0:
                detail += f" (and {remaining} more)"
            return InvariantResult(
                invariant_id="FLE-006",
                status=InvariantStatus.FAIL,
                expected="All truck_health_scores.score between 0 and 100",
                actual=f"{len(out_of_range)} score(s) outside valid range: {detail}",
                message="Truck health scores outside valid range",
                root_cause="Health score values were recorded outside the "
                "expected 0-100 boundary",
                suggested_fix="Investigate the telemetry or manual entry source; "
                "clamp or correct out-of-range values",
                affected_modules=["fleet", "maintenance"],
            )
        return InvariantResult(
            invariant_id="FLE-006",
            status=InvariantStatus.PASS,
            message="All truck health scores are within 0-100",
            affected_modules=["fleet", "maintenance"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-006",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet", "maintenance"],
        )


# ──────────────────────────────────────────────
# FLE-007 — Maintenance records link to existing truck
# ──────────────────────────────────────────────

@invariant(
    id="FLE-007",
    title="Maintenance records link to existing truck",
    description="Every maintenance_record has a valid truck_id FK.",
    category=InvariantCategory.FLEET,
    modules=["fleet", "maintenance"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Orphaned maintenance records cause gaps in service history "
    "and inaccurate truck lifecycle reporting.",
)
def check_fleet_maintenance_record_truck_fk(ctx: InvariantContext) -> InvariantResult:
    """Verify all maintenance records reference existing trucks."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FLE-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT mr.id, mr.truck_id
            FROM maintenance_records mr
            LEFT JOIN trucks tr ON mr.truck_id = tr.id
            WHERE tr.id IS NULL
            """
        )
        orphaned = cursor.fetchall()
        if orphaned:
            detail = "; ".join(
                f"Record {row[0]} references truck_id={row[1]} (missing)"
                for row in orphaned[:10]
            )
            remaining = len(orphaned) - 10
            if remaining > 0:
                detail += f" (and {remaining} more)"
            return InvariantResult(
                invariant_id="FLE-007",
                status=InvariantStatus.FAIL,
                expected="Every maintenance_record has a valid truck_id",
                actual=f"{len(orphaned)} orphaned maintenance record(s): {detail}",
                message="Maintenance records reference non-existent trucks",
                root_cause="truck_id in maintenance_records does not correspond "
                "to an existing entry in the trucks table",
                suggested_fix="Remove or reassign orphaned maintenance records "
                "to a valid truck_id",
                affected_modules=["fleet", "maintenance"],
            )
        return InvariantResult(
            invariant_id="FLE-007",
            status=InvariantStatus.PASS,
            message="All maintenance records reference valid trucks",
            affected_modules=["fleet", "maintenance"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="FLE-007",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["fleet", "maintenance"],
        )
