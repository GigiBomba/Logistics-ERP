"""
Operion Business Invariant Framework — Drivers Module Checks

All invariants related to driver management, assignments, licensing, and compliance.
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
# DRV-001 — Driver assigned to at most one truck
# ──────────────────────────────────────────────

@invariant(
    id="DRV-001",
    title="Driver assigned to at most one truck",
    description="Each driver can have at most one active truck assignment.",
    category=InvariantCategory.DRIVERS,
    modules=["drivers", "fleet"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT],
    rationale="A driver cannot physically operate multiple trucks simultaneously; "
    "dual assignments lead to payroll and compliance violations.",
)
def check_drivers_at_most_one_truck(ctx: InvariantContext) -> InvariantResult:
    """Verify no driver has more than one active truck assignment."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT driver_id, COUNT(*) AS cnt
            FROM driver_truck_assignments
            WHERE active = 1
               OR (ended_at IS NULL AND deleted_at IS NULL)
            GROUP BY driver_id
            HAVING COUNT(*) > 1
            """
        )
        multi_assigned = cursor.fetchall()
        if multi_assigned:
            detail = "; ".join(
                f"Driver {row[0]} has {row[1]} active assignments"
                for row in multi_assigned
            )
            return InvariantResult(
                invariant_id="DRV-001",
                status=InvariantStatus.FAIL,
                expected="Each driver has at most one active truck assignment",
                actual=f"Found {len(multi_assigned)} driver(s) with multiple "
                f"active assignments: {detail}",
                message="Driver assigned to more than one truck",
                root_cause="Multiple active driver_truck_assignments exist for "
                "the same driver",
                suggested_fix="End the redundant assignment(s) so each driver "
                "is linked to at most one active truck",
                affected_modules=["drivers", "fleet"],
            )
        return InvariantResult(
            invariant_id="DRV-001",
            status=InvariantStatus.PASS,
            message="All drivers have at most one active truck assignment",
            affected_modules=["drivers", "fleet"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-001",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers", "fleet"],
        )


# ──────────────────────────────────────────────
# DRV-002 — Truck assigned to at most one driver
# ──────────────────────────────────────────────

@invariant(
    id="DRV-002",
    title="Truck assigned to at most one driver",
    description="Each truck can have at most one active driver assignment.",
    category=InvariantCategory.DRIVERS,
    modules=["drivers", "fleet"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT],
    rationale="A truck shared by multiple drivers creates liability and "
    "maintenance accountability gaps.",
)
def check_drivers_truck_at_most_one_driver(ctx: InvariantContext) -> InvariantResult:
    """Verify no truck has more than one active driver assignment."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT truck_id, COUNT(*) AS cnt
            FROM driver_truck_assignments
            WHERE active = 1
               OR (ended_at IS NULL AND deleted_at IS NULL)
            GROUP BY truck_id
            HAVING COUNT(*) > 1
            """
        )
        multi_assigned = cursor.fetchall()
        if multi_assigned:
            detail = "; ".join(
                f"Truck {row[0]} has {row[1]} active driver assignments"
                for row in multi_assigned
            )
            return InvariantResult(
                invariant_id="DRV-002",
                status=InvariantStatus.FAIL,
                expected="Each truck has at most one active driver assignment",
                actual=f"Found {len(multi_assigned)} truck(s) with multiple "
                f"active assignments: {detail}",
                message="Truck assigned to more than one driver",
                root_cause="Multiple active driver_truck_assignments exist for "
                "the same truck",
                suggested_fix="End the redundant assignment(s) so each truck "
                "is linked to at most one active driver",
                affected_modules=["drivers", "fleet"],
            )
        return InvariantResult(
            invariant_id="DRV-002",
            status=InvariantStatus.PASS,
            message="All trucks have at most one active driver assignment",
            affected_modules=["drivers", "fleet"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-002",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers", "fleet"],
        )


# ──────────────────────────────────────────────
# DRV-003 — Driver cannot exceed legal driving limits
# ──────────────────────────────────────────────

@invariant(
    id="DRV-003",
    title="Driver cannot exceed legal driving limits",
    description="Daily driving <= 540 min (9h), weekly <= 3360 min (56h).",
    category=InvariantCategory.DRIVERS,
    modules=["drivers", "tacho"],
    severity=Severity.HIGH,
    execution=[ExecutionFrequency.NIGHTLY, ExecutionFrequency.WEEKLY],
    rationale="Exceeding legal driving hours violates EU/UK/US transport "
    "regulations and incurs severe penalties.",
)
def check_drivers_legal_driving_limits(ctx: InvariantContext) -> InvariantResult:
    """Verify no driver exceeds daily (540 min) or weekly (3360 min) limits."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        # Check daily limits
        cursor.execute(
            """
            SELECT driver_id,
                   DATE(recorded_at) AS driving_date,
                   SUM(driving_minutes) AS total_minutes
            FROM tacho_records
            WHERE recorded_at >= DATE('now', '-7 days')
            GROUP BY driver_id, DATE(recorded_at)
            HAVING SUM(driving_minutes) > 540
            """
        )
        daily_violations = cursor.fetchall()

        # Check weekly limits
        cursor.execute(
            """
            SELECT driver_id,
                   SUM(driving_minutes) AS weekly_minutes
            FROM tacho_records
            WHERE recorded_at >= DATE('now', '-7 days')
            GROUP BY driver_id
            HAVING SUM(driving_minutes) > 3360
            """
        )
        weekly_violations = cursor.fetchall()

        issues = []
        if daily_violations:
            for row in daily_violations[:10]:
                issues.append(
                    f"Driver {row[0]} drove {row[2]} min on {row[1]} "
                    f"(limit 540 min)"
                )
        if weekly_violations:
            for row in weekly_violations[:10]:
                issues.append(
                    f"Driver {row[0]} drove {row[1]} min this week "
                    f"(limit 3360 min)"
                )

        if issues:
            detail = "; ".join(issues)
            remaining_daily = max(0, len(daily_violations) - 10)
            remaining_weekly = max(0, len(weekly_violations) - 10)
            remaining = remaining_daily + remaining_weekly
            if remaining > 0:
                detail += f" (and {remaining} more violation(s))"
            return InvariantResult(
                invariant_id="DRV-003",
                status=InvariantStatus.FAIL,
                expected="Daily driving <= 540 min, weekly <= 3360 min",
                actual=f"Daily violations: {len(daily_violations)}, "
                f"Weekly violations: {len(weekly_violations)}",
                message="Driver has exceeded legal driving limits",
                root_cause="Tacho records show driving time above the "
                "regulated maximum",
                suggested_fix="Ensure drivers take mandatory rest periods; "
                "review dispatch schedule to prevent limit breaches",
                affected_modules=["drivers", "tacho"],
            )
        return InvariantResult(
            invariant_id="DRV-003",
            status=InvariantStatus.PASS,
            message="All drivers within legal driving limits",
            affected_modules=["drivers", "tacho"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-003",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers", "tacho"],
        )


# ──────────────────────────────────────────────
# DRV-004 — Driver availability reflects assignments
# ──────────────────────────────────────────────

@invariant(
    id="DRV-004",
    title="Driver availability reflects assignments",
    description="If driver has active trip with overlapping times, "
    "driver is unavailable.",
    category=InvariantCategory.DRIVERS,
    modules=["drivers", "dispatch"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Dispatch relies on accurate availability flags; stale "
    "availability causes missed pickups or overbooking.",
)
def check_drivers_availability_reflects_assignments(
    ctx: InvariantContext,
) -> InvariantResult:
    """Verify drivers on active trips are marked unavailable."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT d.id, d.name, t.id AS trip_id
            FROM drivers d
            JOIN trips t ON t.driver_id = d.id
            WHERE t.status IN ('active', 'in_progress')
              AND d.availability_status = 'available'
              AND d.deleted_at IS NULL
            """
        )
        unavailable_drivers = cursor.fetchall()
        if unavailable_drivers:
            detail = "; ".join(
                f"Driver {row[0]} ({row[1]}) on trip {row[2]}"
                for row in unavailable_drivers[:10]
            )
            remaining = len(unavailable_drivers) - 10
            if remaining > 0:
                detail += f" (and {remaining} more)"
            return InvariantResult(
                invariant_id="DRV-004",
                status=InvariantStatus.FAIL,
                expected="Drivers on active trips are marked unavailable",
                actual=f"{len(unavailable_drivers)} driver(s) marked available "
                f"while on active trips: {detail}",
                message="Driver availability does not reflect active assignments",
                root_cause="availability_status was not updated when the driver "
                "was assigned to an active trip",
                suggested_fix="Update availability_status to 'unavailable' for "
                "drivers on active or in-progress trips",
                affected_modules=["drivers", "dispatch"],
            )
        return InvariantResult(
            invariant_id="DRV-004",
            status=InvariantStatus.PASS,
            message="Driver availability correctly reflects assignments",
            affected_modules=["drivers", "dispatch"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-004",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers", "dispatch"],
        )


# ──────────────────────────────────────────────
# DRV-005 — Deleted drivers cannot be assigned
# ──────────────────────────────────────────────

@invariant(
    id="DRV-005",
    title="Deleted drivers cannot be assigned",
    description="Trips must not reference drivers with deleted_at IS NOT NULL.",
    category=InvariantCategory.DRIVERS,
    modules=["drivers", "trips"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.NIGHTLY],
    rationale="Assigning a deleted driver to a trip breaks audit trails, "
    "payroll, and regulatory reporting.",
)
def check_drivers_deleted_drivers_not_assigned(
    ctx: InvariantContext,
) -> InvariantResult:
    """Verify no active trip references a soft-deleted driver."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT t.id, t.driver_id, d.name, d.deleted_at
            FROM trips t
            JOIN drivers d ON t.driver_id = d.id
            WHERE d.deleted_at IS NOT NULL
            """
        )
        bad_references = cursor.fetchall()
        if bad_references:
            detail = "; ".join(
                f"Trip {row[0]} references deleted driver {row[1]} ({row[2]})"
                for row in bad_references[:10]
            )
            remaining = len(bad_references) - 10
            if remaining > 0:
                detail += f" (and {remaining} more references)"
            return InvariantResult(
                invariant_id="DRV-005",
                status=InvariantStatus.FAIL,
                expected="Trips reference only non-deleted drivers",
                actual=f"{len(bad_references)} trip(s) reference deleted drivers",
                message="Deleted drivers are still assigned to trips",
                root_cause="Trips still reference drivers that have been "
                "soft-deleted (deleted_at IS NOT NULL)",
                suggested_fix="Reassign those trips to active drivers, or restore "
                "the referenced driver records",
                affected_modules=["drivers", "trips"],
            )
        return InvariantResult(
            invariant_id="DRV-005",
            status=InvariantStatus.PASS,
            message="No trips reference deleted drivers",
            affected_modules=["drivers", "trips"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-005",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers", "trips"],
        )


# ──────────────────────────────────────────────
# DRV-006 — Driver license expiry tracked
# ──────────────────────────────────────────────

@invariant(
    id="DRV-006",
    title="Driver license expiry tracked",
    description="Drivers with expired licenses trigger alerts.",
    category=InvariantCategory.DRIVERS,
    modules=["drivers"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.NIGHTLY],
    rationale="Operating with an expired license is a legal violation; "
    "the system must proactively flag affected drivers.",
)
def check_drivers_license_expiry(ctx: InvariantContext) -> InvariantResult:
    """Verify no driver has an expired license without an alert."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT d.id, d.name, d.license_number, d.license_expiry_date
            FROM drivers d
            WHERE d.license_expiry_date <= CURRENT_DATE
              AND d.deleted_at IS NULL
            ORDER BY d.license_expiry_date ASC
            """
        )
        expired = cursor.fetchall()
        if expired:
            detail = "; ".join(
                f"Driver {row[0]} ({row[1]}), license {row[2]}, "
                f"expired {row[3]}"
                for row in expired[:10]
            )
            remaining = len(expired) - 10
            if remaining > 0:
                detail += f" (and {remaining} more)"
            return InvariantResult(
                invariant_id="DRV-006",
                status=InvariantStatus.FAIL,
                expected="No active drivers have expired licenses",
                actual=f"{len(expired)} driver(s) with expired licenses: {detail}",
                message="Drivers with expired licenses detected",
                root_cause="License expiry date has passed and the driver "
                "is still active in the system",
                suggested_fix="Notify the driver to renew their license, or "
                "mark the driver as inactive until renewal is complete",
                affected_modules=["drivers"],
            )
        return InvariantResult(
            invariant_id="DRV-006",
            status=InvariantStatus.PASS,
            message="No active drivers have expired licenses",
            affected_modules=["drivers"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-006",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers"],
        )


# ──────────────────────────────────────────────
# DRV-007 — Driver assignment history consistent
# ──────────────────────────────────────────────

@invariant(
    id="DRV-007",
    title="Driver assignment history consistent",
    description="driver_truck_assignments has exactly 0 or 1 rows per driver.",
    category=InvariantCategory.DRIVERS,
    modules=["drivers", "fleet"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="The assignment table should model a clear current assignment "
    "per driver; stale or duplicate rows corrupt reporting.",
)
def check_drivers_assignment_history_consistent(
    ctx: InvariantContext,
) -> InvariantResult:
    """Verify the driver_truck_assignments table has at most one row per driver."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="DRV-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT driver_id, COUNT(*) AS cnt
            FROM driver_truck_assignments
            WHERE deleted_at IS NULL
            GROUP BY driver_id
            HAVING COUNT(*) > 1
            """
        )
        duplicates = cursor.fetchall()
        if duplicates:
            detail = "; ".join(
                f"Driver {row[0]} has {row[1]} assignment records"
                for row in duplicates[:10]
            )
            remaining = len(duplicates) - 10
            if remaining > 0:
                detail += f" (and {remaining} more)"
            return InvariantResult(
                invariant_id="DRV-007",
                status=InvariantStatus.FAIL,
                expected="driver_truck_assignments has 0 or 1 rows per driver",
                actual=f"{len(duplicates)} driver(s) with multiple assignment "
                f"records: {detail}",
                message="Driver assignment history has duplicate entries",
                root_cause="Multiple non-deleted driver_truck_assignments exist "
                "for the same driver",
                suggested_fix="Soft-delete stale assignment records so each "
                "driver has at most one current assignment",
                affected_modules=["drivers", "fleet"],
            )
        return InvariantResult(
            invariant_id="DRV-007",
            status=InvariantStatus.PASS,
            message="All driver assignment histories are consistent "
            "(0 or 1 rows per driver)",
            affected_modules=["drivers", "fleet"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id="DRV-007",
            status=InvariantStatus.ERROR,
            message=f"Check failed with exception: {exc}",
            root_cause=str(exc),
            affected_modules=["drivers", "fleet"],
        )
