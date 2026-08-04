"""
Business invariants for the Dispatch module (DSP-*).

Ensures dispatch assignments reference valid trips, trucks, and drivers;
timestamps remain ordered; no trip conflicts exist; board column mappings
are correct; and delivered-trip cutoffs are respected.
"""

from __future__ import annotations

from datetime import datetime, timedelta

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


_VALID_DISPATCH_STATUSES = [
    "Assigned",
    "EnRoute",
    "Loading",
    "InTransit",
    "Unloading",
    "Completed",
    "Delivered",
    "Cancelled",
    "OnHold",
]


# ──────────────────────────────────────────────
# DSP-001 — Dispatch references existing trip
# ──────────────────────────────────────────────


@invariant(
    id="DSP-001",
    title="Dispatch references existing trip",
    description="Every dispatch assignment references a trip that exists.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch", "trips"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Orphaned dispatch assignments cause runtime errors in trip tracking and billing.",
)
def check_dispatch_references_existing_trip(ctx: InvariantContext) -> InvariantResult:
    """Verify that every dispatch_assignment references a valid trip."""
    invariant_id = "DSP-001"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT da.id, da.trip_id
            FROM dispatch_assignments da
            LEFT JOIN trips t ON da.trip_id = t.id
            WHERE t.id IS NULL
            """
        )
        orphaned = cursor.fetchall()

        if orphaned:
            details = [{"assignment_id": row[0], "trip_id": row[1]} for row in orphaned]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="Every dispatch_assignment.trip_id references an existing trip",
                actual=f"Found {len(orphaned)} dispatch assignments referencing missing trips",
                message=f"Orphaned assignments: {[d['assignment_id'] for d in details]}",
                root_cause="Trips were deleted without cleaning up dispatch assignments",
                suggested_fix="Delete orphaned dispatch_assignments or restore the referenced trips",
                affected_modules=["dispatch", "trips"],
                details={"orphaned_assignments": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="Every dispatch_assignment.trip_id references an existing trip",
            actual="All dispatch assignments reference valid trips",
            affected_modules=["dispatch", "trips"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch", "trips"],
        )


# ──────────────────────────────────────────────
# DSP-002 — Dispatch references assigned truck
# ──────────────────────────────────────────────


@invariant(
    id="DSP-002",
    title="Dispatch references assigned truck",
    description="Dispatched trips reference a truck that exists and is active.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch", "fleet"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Dispatching to a missing or inactive truck causes operational failures.",
)
def check_dispatch_references_active_truck(ctx: InvariantContext) -> InvariantResult:
    """Verify that dispatched trips reference trucks that exist and are active."""
    invariant_id = "DSP-002"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT dt.id AS dispatch_id, dt.trip_id, dt.truck_id
            FROM dispatched_trips dt
            LEFT JOIN trucks t ON dt.truck_id = t.id
            WHERE t.id IS NULL OR t.active = 0
            """
        )
        invalid_trucks = cursor.fetchall()

        if invalid_trucks:
            details = [
                {
                    "dispatch_id": row[0],
                    "trip_id": row[1],
                    "truck_id": row[2],
                }
                for row in invalid_trucks
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All dispatched trucks exist and are active",
                actual=f"Found {len(invalid_trucks)} dispatched trips with invalid or inactive trucks",
                message=f"Invalid truck references: {[d['dispatch_id'] for d in details]}",
                root_cause="Truck was deactivated or deleted after dispatch assignment",
                suggested_fix="Reassign trips to active trucks or reactivate the referenced trucks",
                affected_modules=["dispatch", "fleet"],
                details={"invalid_truck_refs": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All dispatched trucks exist and are active",
            actual=f"All {len(invalid_trucks) if ctx.db else 0} dispatched trips reference active trucks",
            affected_modules=["dispatch", "fleet"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch", "fleet"],
        )


# ──────────────────────────────────────────────
# DSP-003 — Dispatch references assigned driver
# ──────────────────────────────────────────────


@invariant(
    id="DSP-003",
    title="Dispatch references assigned driver",
    description="Dispatched trips reference a driver that exists and is active.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch", "drivers"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Dispatching to a missing or inactive driver causes safety and compliance issues.",
)
def check_dispatch_references_active_driver(ctx: InvariantContext) -> InvariantResult:
    """Verify that dispatched trips reference drivers that exist and are active."""
    invariant_id = "DSP-003"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT dt.id AS dispatch_id, dt.trip_id, dt.driver_id
            FROM dispatched_trips dt
            LEFT JOIN drivers d ON dt.driver_id = d.id
            WHERE d.id IS NULL OR d.active = 0
            """
        )
        invalid_drivers = cursor.fetchall()

        if invalid_drivers:
            details = [
                {
                    "dispatch_id": row[0],
                    "trip_id": row[1],
                    "driver_id": row[2],
                }
                for row in invalid_drivers
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All dispatched drivers exist and are active",
                actual=f"Found {len(invalid_drivers)} dispatched trips with invalid or inactive drivers",
                message=f"Invalid driver references: {[d['dispatch_id'] for d in details]}",
                root_cause="Driver was deactivated or deleted after dispatch assignment",
                suggested_fix="Reassign trips to active drivers or reactivate the referenced drivers",
                affected_modules=["dispatch", "drivers"],
                details={"invalid_driver_refs": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All dispatched drivers exist and are active",
            actual="All dispatched trips reference active drivers",
            affected_modules=["dispatch", "drivers"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch", "drivers"],
        )


# ──────────────────────────────────────────────
# DSP-004 — Dispatch timestamps remain ordered
# ──────────────────────────────────────────────


@invariant(
    id="DSP-004",
    title="Dispatch timestamps remain ordered",
    description="Dispatch status changes: assigned_at <= started_at <= completed_at.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Out-of-order timestamps break scheduling analytics and payroll calculations.",
)
def check_dispatch_timestamps_ordered(ctx: InvariantContext) -> InvariantResult:
    """Verify that dispatch timestamps respect chronological ordering."""
    invariant_id = "DSP-004"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT id, trip_id, assigned_at, started_at, completed_at
            FROM dispatch_assignments
            WHERE (started_at IS NOT NULL AND assigned_at > started_at)
               OR (completed_at IS NOT NULL AND started_at IS NOT NULL AND started_at > completed_at)
            """
        )
        out_of_order = cursor.fetchall()

        if out_of_order:
            details = [
                {
                    "id": row[0],
                    "trip_id": row[1],
                    "assigned_at": str(row[2]),
                    "started_at": str(row[3]),
                    "completed_at": str(row[4]),
                }
                for row in out_of_order
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="assigned_at <= started_at <= completed_at",
                actual=f"Found {len(out_of_order)} dispatch assignments with out-of-order timestamps",
                message=f"Out-of-order timestamps on assignments: {[d['id'] for d in details]}",
                root_cause="Timestamps were set manually or by misconfigured logic",
                suggested_fix="Correct timestamps to obey assigned_at <= started_at <= completed_at; enforce ordering in application logic",
                affected_modules=["dispatch"],
                details={"out_of_order": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="assigned_at <= started_at <= completed_at",
            actual="All dispatch timestamps are chronologically ordered",
            affected_modules=["dispatch"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch"],
        )


# ──────────────────────────────────────────────
# DSP-005 — Trip conflicts detected
# ──────────────────────────────────────────────


@invariant(
    id="DSP-005",
    title="Trip conflicts detected",
    description="No two active (non-Delivered/Cancelled) trips for same truck have overlapping date ranges.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch", "trips"],
    severity=Severity.HIGH,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.NIGHTLY],
    rationale="Overlapping trips for the same truck cause double-booking and resource contention.",
)
def check_trip_conflicts(ctx: InvariantContext) -> InvariantResult:
    """Verify that no truck has overlapping active trip schedules."""
    invariant_id = "DSP-005"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT t1.id AS trip1_id, t2.id AS trip2_id,
                   t1.truck_id, t1.start_date AS trip1_start, t1.end_date AS trip1_end,
                   t2.start_date AS trip2_start, t2.end_date AS trip2_end
            FROM trips t1
            JOIN trips t2 ON t1.truck_id = t2.truck_id AND t1.id < t2.id
            WHERE t1.status NOT IN ('Delivered', 'Cancelled')
              AND t2.status NOT IN ('Delivered', 'Cancelled')
              AND t1.start_date <= t2.end_date
              AND t2.start_date <= t1.end_date
            """
        )
        conflicts = cursor.fetchall()

        if conflicts:
            details = [
                {
                    "trip_1": row[0],
                    "trip_2": row[1],
                    "truck_id": row[2],
                    "trip_1_range": f"{row[3]} to {row[4]}",
                    "trip_2_range": f"{row[5]} to {row[6]}",
                }
                for row in conflicts
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="No overlapping active trips for the same truck",
                actual=f"Found {len(conflicts)} overlapping trip pairs",
                message=f"Overlapping trips detected for truck IDs: {set(d['truck_id'] for d in details)}",
                root_cause="Trip date ranges were not checked against existing active trips",
                suggested_fix="Adjust start/end dates to eliminate overlaps; implement overlap validation at trip creation",
                affected_modules=["dispatch", "trips"],
                details={"conflicts": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="No overlapping active trips for the same truck",
            actual="No trip schedule conflicts found",
            affected_modules=["dispatch", "trips"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch", "trips"],
        )


# ──────────────────────────────────────────────
# DSP-006 — Dispatch board column mapping valid
# ──────────────────────────────────────────────


@invariant(
    id="DSP-006",
    title="Dispatch board column mapping valid",
    description="Status maps to correct dispatch board column.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch"],
    severity=Severity.LOW,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Incorrect column mappings cause board display errors and operator confusion.",
)
def check_dispatch_board_column_mapping(ctx: InvariantContext) -> InvariantResult:
    """Verify that all dispatch status values have valid board column mappings."""
    invariant_id = "DSP-006"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()

        # Check for dispatch statuses that don't have a valid board column mapping
        cursor.execute(
            """
            SELECT DISTINCT ds.status
            FROM dispatch_statuses ds
            LEFT JOIN dispatch_board_columns dbc ON ds.column_id = dbc.id
            WHERE dbc.id IS NULL
            """
        )
        unmapped_statuses = cursor.fetchall()

        if unmapped_statuses:
            status_list = [row[0] for row in unmapped_statuses]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="Every dispatch status maps to a valid board column",
                actual=f"Found {len(unmapped_statuses)} unmapped dispatch statuses",
                message=f"Unmapped statuses: {status_list}",
                root_cause="Status was added without a corresponding board column",
                suggested_fix="Create board columns for unmapped statuses or correct the column_id references",
                affected_modules=["dispatch"],
                details={"unmapped_statuses": status_list},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="Every dispatch status maps to a valid board column",
            actual="All dispatch statuses have valid board column mappings",
            affected_modules=["dispatch"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch"],
        )


# ──────────────────────────────────────────────
# DSP-007 — Delivered trip cutoff respected
# ──────────────────────────────────────────────


@invariant(
    id="DSP-007",
    title="Delivered trip cutoff respected",
    description="Trips older than delivered_window_days (default 30) excluded from dispatch board.",
    category=InvariantCategory.DISPATCH,
    modules=["dispatch"],
    severity=Severity.LOW,
    execution=[ExecutionFrequency.NIGHTLY],
    rationale="Stale delivered trips clutter the dispatch board and confuse operators.",
)
def check_delivered_trip_cutoff(ctx: InvariantContext) -> InvariantResult:
    """Verify that delivered trips beyond the cutoff window are excluded from the dispatch board."""
    invariant_id = "DSP-007"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        # Allow config override of the cutoff window; default to 30 days
        delivered_window_days = int(
            ctx.config.get("delivered_window_days", 30)
        )
        cutoff_date = datetime.utcnow() - timedelta(days=delivered_window_days)

        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT id, trip_number, delivered_at
            FROM trips
            WHERE status = 'Delivered'
              AND delivered_at IS NOT NULL
              AND delivered_at < ?
              AND on_dispatch_board = 1
            """,
            (cutoff_date.isoformat(),),
        )
        stale_trips = cursor.fetchall()

        if stale_trips:
            details = [
                {
                    "id": row[0],
                    "trip_number": row[1],
                    "delivered_at": str(row[2]),
                }
                for row in stale_trips
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected=f"Delivered trips older than {delivered_window_days} days are excluded from the dispatch board",
                actual=f"Found {len(stale_trips)} delivered trips past the cutoff still on the dispatch board",
                message=f"Stale delivered trips: {[d['id'] for d in details]}",
                root_cause="Dispatch board cleanup job is not running or the cutoff is misconfigured",
                suggested_fix=f"Remove stale trips from the dispatch board or run the scheduled cleanup; adjust delivered_window_days if needed (current: {delivered_window_days})",
                affected_modules=["dispatch"],
                details={
                    "cutoff_days": delivered_window_days,
                    "cutoff_date": cutoff_date.isoformat(),
                    "stale_trips": details,
                },
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected=f"Delivered trips older than {delivered_window_days} days excluded from dispatch board",
            actual="No stale delivered trips found on the dispatch board",
            affected_modules=["dispatch"],
            details={
                "cutoff_days": delivered_window_days,
                "cutoff_date": cutoff_date.isoformat(),
            },
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["dispatch"],
        )
