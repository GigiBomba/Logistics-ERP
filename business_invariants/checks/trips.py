"""
Business Invariant Framework — Trip Invariants

All business invariants related to the Trips domain:
trip lifecycle, status transitions, financial consistency, data integrity.
"""

from __future__ import annotations

from business_invariants.decorators import invariant
from business_invariants.models import (
    CRITICAL,
    HIGH,
    MEDIUM,
    COMMIT,
    NIGHTLY,
    PR,
    InvariantCategory,
    InvariantContext,
    InvariantResult,
    InvariantStatus,
)

# ──────────────────────────────────────────────
# TRP-001: Every trip has exactly one status
# ──────────────────────────────────────────────

KNOWN_STATUSES = frozenset({
    "Planned",
    "Loading",
    "In Transit",
    "Delivered",
    "Invoiced",
    "Paid",
    "Cancelled",
})


@invariant(
    id="TRP-001",
    title="Every trip has exactly one status",
    description=(
        "trips.status must be a non-empty string from known statuses. "
        "A null, empty, or unrecognised status indicates data corruption."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips"],
    severity=CRITICAL,
    execution=[COMMIT],
    rationale="The trip lifecycle is driven by status. An invalid or missing status "
    "breaks every downstream workflow (invoicing, dispatching, analytics).",
)
def check_trip_has_status(ctx: InvariantContext) -> InvariantResult:
    """TRP-001: Verify every trip record has a valid, non-empty status."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute("SELECT id, status FROM trips")
    invalid: list[str] = []
    for row in cursor:
        trip_id, status = row
        if not status or status not in KNOWN_STATUSES:
            invalid.append(f"Trip {trip_id}: status={status!r}")

    if invalid:
        return InvariantResult(
            invariant_id="TRP-001",
            status=InvariantStatus.FAIL,
            expected="Every trip has a non-empty status from {Planned, Loading, In Transit, Delivered, Invoiced, Paid, Cancelled}",
            actual=f"{len(invalid)} trip(s) with invalid or missing status",
            message="; ".join(invalid),
            affected_modules=["trips"],
        )

    return InvariantResult(
        invariant_id="TRP-001",
        status=InvariantStatus.PASS,
        expected="All trips have a valid non-empty status",
        actual=f"All {len(list(cursor)) if hasattr(cursor, '__iter__') else 'queried'} trips valid",
    )


# ──────────────────────────────────────────────
# TRP-002: Valid trip status transitions
# ──────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    "Planned": {"Loading", "Cancelled"},
    "Loading": {"In Transit", "Cancelled"},
    "In Transit": {"Delivered", "Cancelled"},
    "Delivered": {"Invoiced"},
    "Invoiced": {"Paid"},
    "Paid": set(),
    "Cancelled": set(),
}


@invariant(
    id="TRP-002",
    title="Valid trip status transitions",
    description=(
        "Status transitions must follow the state machine: "
        "Planned → Loading → In Transit → Delivered → Invoiced → Paid. "
        "trip_status_history must preserve valid transitions; "
        "any disallowed step (e.g. Planned → Paid) is a violation."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips", "operations"],
    severity=CRITICAL,
    execution=[COMMIT, PR, NIGHTLY],
    rationale="Skipping lifecycle steps causes financial and operational chaos — "
    "invoices generated before delivery, payments collected before invoicing, etc.",
)
def check_valid_status_transitions(ctx: InvariantContext) -> InvariantResult:
    """TRP-002: Validate that every status transition in history is legal."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT h.trip_id, h.from_status, h.to_status
        FROM trip_status_history h
        ORDER BY h.trip_id, h.changed_at
        """
    )
    violations: list[str] = []
    for row in cursor:
        trip_id, from_status, to_status = row
        allowed = VALID_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            violations.append(
                f"Trip {trip_id}: {from_status!r} → {to_status!r} is not allowed"
            )

    if violations:
        return InvariantResult(
            invariant_id="TRP-002",
            status=InvariantStatus.FAIL,
            expected="Every status transition follows the lifecycle: "
            "Planned→Loading→In Transit→Delivered→Invoiced→Paid",
            actual=f"{len(violations)} invalid transition(s) detected",
            message="; ".join(violations),
            affected_modules=["trips", "operations"],
        )

    return InvariantResult(
        invariant_id="TRP-002",
        status=InvariantStatus.PASS,
        expected="All status transitions are valid",
        actual="No invalid transitions found in trip_status_history",
    )


# ──────────────────────────────────────────────
# TRP-003: Completed trips cannot return to Draft
# ──────────────────────────────────────────────

REGressed_STATUSES = {"Planned", "Loading"}


@invariant(
    id="TRP-003",
    title="Completed trips cannot return to Draft",
    description=(
        "Once a trip reaches Delivered (or beyond), it cannot go back "
        "to Planned or Loading. Regressing to an earlier lifecycle phase "
        "invalidates downstream operations."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips", "operations"],
    severity=CRITICAL,
    execution=[COMMIT, PR],
    rationale="Trust in the trip lifecycle is broken if completed trips can "
    "be sent back to draft status, potentially re-triggering dispatches or duplicate invoices.",
)
def check_no_regression_from_delivered(ctx: InvariantContext) -> InvariantResult:
    """TRP-003: Ensure trips that reached Delivered never go back to Planned/Loading."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT DISTINCT h.trip_id
        FROM trip_status_history h
        WHERE h.from_status IN ('Delivered', 'Invoiced', 'Paid')
          AND h.to_status IN ('Planned', 'Loading')
        """
    )
    trip_ids = [row[0] for row in cursor]

    if trip_ids:
        return InvariantResult(
            invariant_id="TRP-003",
            status=InvariantStatus.FAIL,
            expected="Trips that have reached Delivered must not transition back to Planned or Loading",
            actual=f"{len(trip_ids)} trip(s) regressed: {trip_ids}",
            message=f"Trip IDs with illegal regression: {trip_ids}",
            affected_modules=["trips", "operations"],
        )

    return InvariantResult(
        invariant_id="TRP-003",
        status=InvariantStatus.PASS,
        expected="No completed trip has regressed to Planned or Loading",
        actual="All completed trips maintain forward lifecycle progression",
    )


# ──────────────────────────────────────────────
# TRP-004: Cancelled trips cannot generate invoices
# ──────────────────────────────────────────────

@invariant(
    id="TRP-004",
    title="Cancelled trips cannot generate invoices",
    description=(
        "No invoice should exist for a trip with status Cancelled. "
        "A cancelled trip represents a service that was not performed "
        "and therefore must not be billed."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips", "invoicing"],
    severity=CRITICAL,
    execution=[COMMIT, NIGHTLY],
    rationale="Billing for cancelled trips creates financial liabilities, "
    "customer disputes, and reconciliation overhead.",
)
def check_cancelled_trips_no_invoice(ctx: InvariantContext) -> InvariantResult:
    """TRP-004: Verify no invoices reference a trip in Cancelled status."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT i.id, i.trip_id
        FROM invoices i
        JOIN trips t ON i.trip_id = t.id
        WHERE t.status = 'Cancelled'
        """
    )
    offending: list[str] = [f"Invoice {row[0]} (trip {row[1]})" for row in cursor]

    if offending:
        return InvariantResult(
            invariant_id="TRP-004",
            status=InvariantStatus.FAIL,
            expected="No invoices linked to Cancelled trips",
            actual=f"{len(offending)} invoice(s) linked to cancelled trips",
            message="; ".join(offending),
            affected_modules=["trips", "invoicing"],
        )

    return InvariantResult(
        invariant_id="TRP-004",
        status=InvariantStatus.PASS,
        expected="No invoices linked to Cancelled trips",
        actual="All invoices reference non-cancelled trips only",
    )


# ──────────────────────────────────────────────
# TRP-005: Trip profitability calculation consistency
# ──────────────────────────────────────────────

@invariant(
    id="TRP-005",
    title="Trip profitability calculation consistency",
    description=(
        "If all cost fields are populated: net_profit == price_eur - "
        "(fuel_cost + toll_cost + salary_cost + extra_costs). "
        "This ensures the profitability metric is computed correctly."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips", "analytics"],
    severity=HIGH,
    execution=[COMMIT, NIGHTLY],
    rationale="Inconsistent profitability figures erode trust in the analytics "
    "dashboard and lead to incorrect business decisions.",
)
def check_profitability_consistency(ctx: InvariantContext) -> InvariantResult:
    """TRP-005: Validate net_profit = price - sum(costs) when all costs are populated."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, price_eur, fuel_cost, toll_cost, salary_cost, extra_costs, net_profit
        FROM trips
        WHERE price_eur IS NOT NULL
          AND fuel_cost IS NOT NULL
          AND toll_cost IS NOT NULL
          AND salary_cost IS NOT NULL
          AND extra_costs IS NOT NULL
          AND net_profit IS NOT NULL
        """
    )
    mismatches: list[str] = []
    for row in cursor:
        trip_id = row[0]
        price_eur, fuel_cost, toll_cost, salary_cost, extra_costs, net_profit = row[1:]
        expected_profit = price_eur - (fuel_cost + toll_cost + salary_cost + extra_costs)
        if abs(net_profit - expected_profit) > 0.01:  # tolerance for float rounding
            mismatches.append(
                f"Trip {trip_id}: net_profit={net_profit}, expected={expected_profit:.2f} "
                f"(price={price_eur} - costs={fuel_cost + toll_cost + salary_cost + extra_costs})"
            )

    if mismatches:
        return InvariantResult(
            invariant_id="TRP-005",
            status=InvariantStatus.FAIL,
            expected="net_profit == price_eur - (fuel_cost + toll_cost + salary_cost + extra_costs)",
            actual=f"{len(mismatches)} trip(s) with inconsistent profitability",
            message="; ".join(mismatches),
            affected_modules=["trips", "analytics"],
        )

    return InvariantResult(
        invariant_id="TRP-005",
        status=InvariantStatus.PASS,
        expected="Profitability calculation is consistent for all trips",
        actual="All populated trips have correct net_profit values",
    )


# ──────────────────────────────────────────────
# TRP-006: Trip distance is positive
# ──────────────────────────────────────────────

@invariant(
    id="TRP-006",
    title="Trip distance is positive",
    description=(
        "distance_km > 0 when a trip has status In Transit or beyond. "
        "Zero or negative distance at these stages indicates corrupt data."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips"],
    severity=MEDIUM,
    execution=[COMMIT],
    rationale="Distance is used for fuel estimation, driver compensation, "
    "and customer billing. Invalid distances propagate errors everywhere.",
)
def check_distance_positive(ctx: InvariantContext) -> InvariantResult:
    """TRP-006: Verify distance_km > 0 for trips in or past In Transit."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, distance_km, status
        FROM trips
        WHERE status IN ('In Transit', 'Delivered', 'Invoiced', 'Paid')
          AND (distance_km IS NULL OR distance_km <= 0)
        """
    )
    invalid: list[str] = [
        f"Trip {row[0]}: distance_km={row[1]}, status={row[2]}" for row in cursor
    ]

    if invalid:
        return InvariantResult(
            invariant_id="TRP-006",
            status=InvariantStatus.FAIL,
            expected="distance_km > 0 when trip status is 'In Transit' or beyond",
            actual=f"{len(invalid)} trip(s) with non-positive distance",
            message="; ".join(invalid),
            affected_modules=["trips"],
        )

    return InvariantResult(
        invariant_id="TRP-006",
        status=InvariantStatus.PASS,
        expected="All in-progress/completed trips have positive distance",
        actual="All active trips have distance_km > 0",
    )


# ──────────────────────────────────────────────
# TRP-007: Trip price is non-negative
# ──────────────────────────────────────────────

@invariant(
    id="TRP-007",
    title="Trip price is non-negative",
    description="price_eur >= 0 for all trips. A negative price is a data error.",
    category=InvariantCategory.TRIPS,
    modules=["trips"],
    severity=HIGH,
    execution=[COMMIT],
    rationale="Negative prices break invoicing, revenue reporting, and "
    "commission calculations. They should never exist in the system.",
)
def check_price_non_negative(ctx: InvariantContext) -> InvariantResult:
    """TRP-007: Verify no trip has a negative price_eur."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        "SELECT id, price_eur FROM trips WHERE price_eur < 0"
    )
    negative: list[str] = [
        f"Trip {row[0]}: price_eur={row[1]}" for row in cursor
    ]

    if negative:
        return InvariantResult(
            invariant_id="TRP-007",
            status=InvariantStatus.FAIL,
            expected="All trips have price_eur >= 0",
            actual=f"{len(negative)} trip(s) with negative price",
            message="; ".join(negative),
            affected_modules=["trips"],
        )

    return InvariantResult(
        invariant_id="TRP-007",
        status=InvariantStatus.PASS,
        expected="All trips have price_eur >= 0",
        actual="No trips with negative price",
    )


# ──────────────────────────────────────────────
# TRP-008: Trip references exist
# ──────────────────────────────────────────────

@invariant(
    id="TRP-008",
    title="Trip references exist",
    description=(
        "When truck_id / driver_id / client_id is set on a trip, "
        "the referenced entity must exist (and not be soft-deleted). "
        "Orphaned references break joins, reporting, and UI lookups."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips"],
    severity=HIGH,
    execution=[COMMIT, NIGHTLY],
    rationale="Orphaned foreign keys cause silent failures in reporting "
    "and break user-facing screens that need to display reference data.",
)
def check_trip_references_exist(ctx: InvariantContext) -> InvariantResult:
    """TRP-008: Verify truck/driver/client references point to active entities."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-008",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    violations: list[str] = []

    # Check truck references
    cursor = ctx.db.execute(
        """
        SELECT t.id, t.truck_id
        FROM trips t
        LEFT JOIN trucks tr ON t.truck_id = tr.id AND (tr.deleted_at IS NULL)
        WHERE t.truck_id IS NOT NULL AND tr.id IS NULL
        """
    )
    for row in cursor:
        violations.append(f"Trip {row[0]} references non-existent truck_id={row[1]}")

    # Check driver references
    cursor = ctx.db.execute(
        """
        SELECT t.id, t.driver_id
        FROM trips t
        LEFT JOIN drivers d ON t.driver_id = d.id AND (d.deleted_at IS NULL)
        WHERE t.driver_id IS NOT NULL AND d.id IS NULL
        """
    )
    for row in cursor:
        violations.append(f"Trip {row[0]} references non-existent driver_id={row[1]}")

    # Check client references
    cursor = ctx.db.execute(
        """
        SELECT t.id, t.client_id
        FROM trips t
        LEFT JOIN clients c ON t.client_id = c.id AND (c.deleted_at IS NULL)
        WHERE t.client_id IS NOT NULL AND c.id IS NULL
        """
    )
    for row in cursor:
        violations.append(f"Trip {row[0]} references non-existent client_id={row[1]}")

    if violations:
        return InvariantResult(
            invariant_id="TRP-008",
            status=InvariantStatus.FAIL,
            expected="All referenced truck/driver/client entities exist and are not soft-deleted",
            actual=f"{len(violations)} orphaned reference(s) found",
            message="; ".join(violations),
            affected_modules=["trips"],
        )

    return InvariantResult(
        invariant_id="TRP-008",
        status=InvariantStatus.PASS,
        expected="All trip references point to existing (non-deleted) entities",
        actual="No orphaned references found",
    )


# ──────────────────────────────────────────────
# TRP-009: Trip dates are ordered
# ──────────────────────────────────────────────

@invariant(
    id="TRP-009",
    title="Trip dates are ordered",
    description=(
        "start_date <= end_date when both are set. "
        "A start date after an end date is a logical impossibility."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips"],
    severity=MEDIUM,
    execution=[COMMIT],
    rationale="Date ordering is assumed by scheduling, dispatch, "
    "and driver assignment. Reversed dates cause planning conflicts.",
)
def check_dates_ordered(ctx: InvariantContext) -> InvariantResult:
    """TRP-009: Verify start_date <= end_date for every trip."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-009",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, start_date, end_date
        FROM trips
        WHERE start_date IS NOT NULL
          AND end_date IS NOT NULL
          AND start_date > end_date
        """
    )
    invalid: list[str] = [
        f"Trip {row[0]}: start_date={row[1]} > end_date={row[2]}" for row in cursor
    ]

    if invalid:
        return InvariantResult(
            invariant_id="TRP-009",
            status=InvariantStatus.FAIL,
            expected="start_date <= end_date for all trips where both are set",
            actual=f"{len(invalid)} trip(s) with reversed dates",
            message="; ".join(invalid),
            affected_modules=["trips"],
        )

    return InvariantResult(
        invariant_id="TRP-009",
        status=InvariantStatus.PASS,
        expected="All trip dates are chronologically ordered",
        actual="No date ordering violations found",
    )


# ──────────────────────────────────────────────
# TRP-010: Trip source tracking consistent
# ──────────────────────────────────────────────

@invariant(
    id="TRP-010",
    title="Trip source tracking consistent",
    description=(
        "If source == 'freight_exchange', source_provider_id and "
        "source_reference_id must both be set. Missing provider/reference "
        "IDs break traceability back to the original freight exchange listing."
    ),
    category=InvariantCategory.TRIPS,
    modules=["trips", "freight_exchange"],
    severity=MEDIUM,
    execution=[COMMIT],
    rationale="Traceability to the original freight exchange listing is "
    "essential for auditing commission payments and resolving disputes.",
)
def check_source_tracking_consistent(ctx: InvariantContext) -> InvariantResult:
    """TRP-010: Verify freight_exchange trips have provider and reference IDs."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="TRP-010",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, source, source_provider_id, source_reference_id
        FROM trips
        WHERE source = 'freight_exchange'
          AND (source_provider_id IS NULL OR source_reference_id IS NULL)
        """
    )
    incomplete: list[str] = [
        (
            f"Trip {row[0]}: source={row[1]!r}, "
            f"source_provider_id={row[2]!r}, source_reference_id={row[3]!r}"
        )
        for row in cursor
    ]

    if incomplete:
        return InvariantResult(
            invariant_id="TRP-010",
            status=InvariantStatus.FAIL,
            expected="Trips with source='freight_exchange' must have both "
            "source_provider_id and source_reference_id set",
            actual=f"{len(incomplete)} trip(s) with incomplete source tracking",
            message="; ".join(incomplete),
            affected_modules=["trips", "freight_exchange"],
        )

    return InvariantResult(
        invariant_id="TRP-010",
        status=InvariantStatus.PASS,
        expected="All freight_exchange trips have complete tracking fields",
        actual="No incomplete source tracking records found",
    )
