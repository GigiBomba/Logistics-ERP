"""
Business Invariant Framework — Route Invariants

All business invariants related to the Routes domain:
distance validation, waypoint ordering, truck constraints, route profiles.
"""

from __future__ import annotations

import math

from business_invariants.decorators import invariant
from business_invariants.models import (
    HIGH,
    MEDIUM,
    COMMIT,
    PR,
    InvariantCategory,
    InvariantContext,
    InvariantResult,
    InvariantStatus,
)

# ──────────────────────────────────────────────
# RTE-001: Route distance >= straight-line distance
# ──────────────────────────────────────────────


def _great_circle_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Haversine formula for great-circle distance in kilometres."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@invariant(
    id="RTE-001",
    title="Route distance >= straight-line distance",
    description=(
        "Route calculated distance must be >= great-circle (straight-line) "
        "distance between the start and end points. A computed route that "
        "is shorter than the direct line is physically impossible."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=HIGH,
    execution=[COMMIT, PR],
    rationale="Route distances shorter than the straight line indicate "
    "corrupted geometry, incorrect coordinate pairs, or a broken routing engine.",
)
def check_distance_ge_great_circle(ctx: InvariantContext) -> InvariantResult:
    """RTE-001: Verify computed route distance >= straight-line distance."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, distance_km, start_lat, start_lon, end_lat, end_lon
        FROM routes
        WHERE distance_km IS NOT NULL
          AND start_lat IS NOT NULL AND start_lon IS NOT NULL
          AND end_lat IS NOT NULL AND end_lon IS NOT NULL
        """
    )
    violations: list[str] = []
    for row in cursor:
        route_id, distance_km, start_lat, start_lon, end_lat, end_lon = row
        straight_line = _great_circle_distance_km(
            start_lat, start_lon, end_lat, end_lon
        )
        if distance_km < straight_line - 0.1:  # small tolerance for float precision
            violations.append(
                f"Route {route_id}: computed distance={distance_km} km, "
                f"straight-line={straight_line:.2f} km"
            )

    if violations:
        return InvariantResult(
            invariant_id="RTE-001",
            status=InvariantStatus.FAIL,
            expected="Computed route distance >= great-circle distance between start and end",
            actual=f"{len(violations)} route(s) with distance less than straight-line",
            message="; ".join(violations),
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-001",
        status=InvariantStatus.PASS,
        expected="All route distances are >= straight-line distances",
        actual="No violations found",
    )


# ──────────────────────────────────────────────
# RTE-002: Route duration > 0
# ──────────────────────────────────────────────

@invariant(
    id="RTE-002",
    title="Route duration > 0",
    description="duration_min > 0 for all computed routes. Zero or negative duration indicates a routing failure.",
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=HIGH,
    execution=[COMMIT],
    rationale="Zero-duration routes break ETA calculations, driver scheduling, "
    "and customer delivery window commitments.",
)
def check_duration_positive(ctx: InvariantContext) -> InvariantResult:
    """RTE-002: Verify all computed routes have positive duration."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, duration_min
        FROM routes
        WHERE duration_min IS NULL OR duration_min <= 0
        """
    )
    invalid: list[str] = [
        f"Route {row[0]}: duration_min={row[1]}" for row in cursor
    ]

    if invalid:
        return InvariantResult(
            invariant_id="RTE-002",
            status=InvariantStatus.FAIL,
            expected="duration_min > 0 for all computed routes",
            actual=f"{len(invalid)} route(s) with non-positive duration",
            message="; ".join(invalid),
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-002",
        status=InvariantStatus.PASS,
        expected="All routes have positive duration",
        actual="No zero or negative durations found",
    )


# ──────────────────────────────────────────────
# RTE-003: ETA remains chronological
# ──────────────────────────────────────────────

@invariant(
    id="RTE-003",
    title="ETA remains chronological",
    description=(
        "Expected time at each waypoint must be >= the previous waypoint time. "
        "Non-chronological ETAs break driver schedules and customer notifications."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=MEDIUM,
    execution=[COMMIT],
    rationale="Non-chronological ETAs cause confusing delivery estimates "
    "and break downstream scheduling logic.",
)
def check_eta_chronological(ctx: InvariantContext) -> InvariantResult:
    """RTE-003: Verify waypoint ETAs are monotonically non-decreasing."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT rw.route_id, rw.stop_order, rw.eta
        FROM route_waypoints rw
        ORDER BY rw.route_id, rw.stop_order
        """
    )
    violations: list[str] = []
    prev_route: int | None = None
    prev_eta = None
    for row in cursor:
        route_id, stop_order, eta = row
        if route_id != prev_route:
            prev_route = route_id
            prev_eta = None
            continue
        if prev_eta is not None and eta is not None and prev_eta is not None:
            if eta < prev_eta:
                violations.append(
                    f"Route {route_id}: waypoint {stop_order} "
                    f"ETA {eta} < previous ETA {prev_eta}"
                )
        prev_eta = eta

    if violations:
        return InvariantResult(
            invariant_id="RTE-003",
            status=InvariantStatus.FAIL,
            expected="Waypoint ETAs are monotonically non-decreasing along the route",
            actual=f"{len(violations)} non-chronological ETA sequence(s) found",
            message="; ".join(violations[:20]),  # limit message length
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-003",
        status=InvariantStatus.PASS,
        expected="All waypoint ETAs are chronological",
        actual="No ETA ordering violations found",
    )


# ──────────────────────────────────────────────
# RTE-004: Waypoint ordering preserved
# ──────────────────────────────────────────────

@invariant(
    id="RTE-004",
    title="Waypoint ordering preserved",
    description=(
        "The stops array must maintain the order specified by the user: "
        "origin → intermediate(s) → destination. Reshuffling waypoints "
        "invalidates the user's intended route sequence."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=HIGH,
    execution=[COMMIT],
    rationale="The user explicitly specifies stop order. The routing engine "
    "must respect that order; rearranging waypoints breaks customer expectations.",
)
def check_waypoint_ordering(ctx: InvariantContext) -> InvariantResult:
    """RTE-004: Verify stops maintain user-specified origin → intermediate(s) → destination order."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT r.id, rw.stop_order, rw.waypoint_type
        FROM routes r
        JOIN route_waypoints rw ON rw.route_id = r.id
        ORDER BY r.id, rw.stop_order
        """
    )
    violations: list[str] = []
    prev_route: int | None = None
    seen_origin = False
    seen_destination = False
    for row in cursor:
        route_id, stop_order, waypoint_type = row
        if route_id != prev_route:
            # Validate previous route
            if prev_route is not None:
                if not seen_origin:
                    violations.append(f"Route {prev_route}: missing origin waypoint")
                if not seen_destination:
                    violations.append(f"Route {prev_route}: missing destination waypoint")
            prev_route = route_id
            seen_origin = False
            seen_destination = False

        if waypoint_type == "origin":
            if seen_origin:
                violations.append(f"Route {route_id}: duplicate origin at stop_order={stop_order}")
            if seen_destination:
                violations.append(
                    f"Route {route_id}: origin after destination at stop_order={stop_order}"
                )
            seen_origin = True
        elif waypoint_type == "destination":
            if seen_destination:
                violations.append(f"Route {route_id}: duplicate destination at stop_order={stop_order}")
            seen_destination = True
        elif waypoint_type == "intermediate":
            if seen_destination:
                violations.append(
                    f"Route {route_id}: intermediate after destination at stop_order={stop_order}"
                )

    # Check last route
    if prev_route is not None:
        if not seen_origin:
            violations.append(f"Route {prev_route}: missing origin waypoint")
        if not seen_destination:
            violations.append(f"Route {prev_route}: missing destination waypoint")

    if violations:
        return InvariantResult(
            invariant_id="RTE-004",
            status=InvariantStatus.FAIL,
            expected="Stops ordered as origin → intermediate(s) → destination",
            actual=f"{len(violations)} ordering violation(s) detected",
            message="; ".join(violations),
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-004",
        status=InvariantStatus.PASS,
        expected="All routes maintain correct waypoint ordering",
        actual="No ordering violations found",
    )


# ──────────────────────────────────────────────
# RTE-005: At least 2 unique stops required
# ──────────────────────────────────────────────

@invariant(
    id="RTE-005",
    title="At least 2 unique stops required",
    description=(
        "A route must have >= 2 unique stops after deduplication. "
        "A route with fewer stops (or all identical locations) is meaningless."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=MEDIUM,
    execution=[COMMIT],
    rationale="A route must connect at least two distinct locations. "
    "Single-stop or duplicate-stop routes cannot be dispatched.",
)
def check_minimum_unique_stops(ctx: InvariantContext) -> InvariantResult:
    """RTE-005: Verify every route has at least 2 unique stop locations."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT r.id, COUNT(DISTINCT (rw.lat, rw.lon)) as unique_stops
        FROM routes r
        JOIN route_waypoints rw ON rw.route_id = r.id
        GROUP BY r.id
        HAVING unique_stops < 2
        """
    )
    invalid: list[str] = [
        f"Route {row[0]}: only {row[1]} unique stop(s)" for row in cursor
    ]

    if invalid:
        return InvariantResult(
            invariant_id="RTE-005",
            status=InvariantStatus.FAIL,
            expected="Each route has at least 2 unique stop locations",
            actual=f"{len(invalid)} route(s) with insufficient unique stops",
            message="; ".join(invalid),
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-005",
        status=InvariantStatus.PASS,
        expected="All routes have >= 2 unique stops",
        actual="No violations found",
    )


# ──────────────────────────────────────────────
# RTE-006: Truck constraints respected
# ──────────────────────────────────────────────

TRUCK_CONSTRAINTS = {
    "height": {"max": 4.0, "label": "Height"},
    "weight": {"max": 40000, "label": "Weight"},
    "width": {"max": 2.55, "label": "Width"},
}


@invariant(
    id="RTE-006",
    title="Truck constraints respected",
    description=(
        "Routes must respect physical truck constraints: "
        "height > 4.0 m → rejected, weight > 40 000 kg → rejected, "
        "width > 2.55 m → rejected. These limits are based on EU road regulations."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes", "fleet"],
    severity=HIGH,
    execution=[COMMIT, PR],
    rationale="Routing a truck that exceeds legal or physical constraints "
    "causes bridge strikes, road damage fines, and safety hazards.",
)
def check_truck_constraints(ctx: InvariantContext) -> InvariantResult:
    """RTE-006: Verify route truck dimensions stay within legal limits."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT r.id, t.id, t.height_m, t.weight_kg, t.width_m
        FROM routes r
        JOIN trucks t ON r.truck_id = t.id
        WHERE (t.height_m IS NOT NULL AND t.height_m > 4.0)
           OR (t.weight_kg IS NOT NULL AND t.weight_kg > 40000)
           OR (t.width_m IS NOT NULL AND t.width_m > 2.55)
        """
    )
    violations: list[str] = []
    for row in cursor:
        route_id, truck_id, height, weight, width = row
        issues: list[str] = []
        if height is not None and height > 4.0:
            issues.append(f"height={height}m (max 4.0m)")
        if weight is not None and weight > 40000:
            issues.append(f"weight={weight}kg (max 40000kg)")
        if width is not None and width > 2.55:
            issues.append(f"width={width}m (max 2.55m)")
        violations.append(
            f"Route {route_id} with truck {truck_id}: {'; '.join(issues)}"
        )

    if violations:
        return InvariantResult(
            invariant_id="RTE-006",
            status=InvariantStatus.FAIL,
            expected="All trucks in routes respect height <= 4.0m, weight <= 40000kg, width <= 2.55m",
            actual=f"{len(violations)} constraint violation(s) detected",
            message="; ".join(violations),
            affected_modules=["routes", "fleet"],
        )

    return InvariantResult(
        invariant_id="RTE-006",
        status=InvariantStatus.PASS,
        expected="All truck constraints are respected",
        actual="No constraint violations found",
    )


# ──────────────────────────────────────────────
# RTE-007: Country avoidance respected
# ──────────────────────────────────────────────

@invariant(
    id="RTE-007",
    title="Country avoidance respected",
    description=(
        "If a user has specified avoided countries for a route, "
        "the computed route should not cross those countries. "
        "Crossing an avoided country defeats the purpose of the setting."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=MEDIUM,
    execution=[COMMIT, PR],
    rationale="Avoided countries are set for regulatory, insurance, or "
    "cost reasons. Violating this preference can lead to compliance issues.",
)
def check_country_avoidance(ctx: InvariantContext) -> InvariantResult:
    """RTE-007: Verify routes do not pass through user-specified avoided countries."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT r.id, rac.country_code
        FROM route_avoided_countries rac
        JOIN routes r ON rac.route_id = r.id
        JOIN route_country_crossings rcc
          ON rcc.route_id = r.id AND rcc.country_code = rac.country_code
        """
    )
    violations: list[str] = [
        f"Route {row[0]} crosses avoided country {row[1]!r}"
        for row in cursor
    ]

    if violations:
        return InvariantResult(
            invariant_id="RTE-007",
            status=InvariantStatus.FAIL,
            expected="Routes must not cross user-specified avoided countries",
            actual=f"{len(violations)} avoided-country crossing(s) detected",
            message="; ".join(violations),
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-007",
        status=InvariantStatus.PASS,
        expected="No routes cross avoided countries",
        actual="All avoided-country preferences are respected",
    )


# ──────────────────────────────────────────────
# RTE-008: Route profile is valid
# ──────────────────────────────────────────────

VALID_PROFILES = frozenset({
    "truck",
    "truck_fast",
    "truck_safe",
    "truck_cheap",
    "truck_short",
    "car",
    "bike",
    "foot",
})


@invariant(
    id="RTE-008",
    title="Route profile is valid",
    description=(
        "Profile must be one of: truck, truck_fast, truck_safe, "
        "truck_cheap, truck_short, car, bike, foot. "
        "An invalid profile indicates a data corruption or unsupported routing request."
    ),
    category=InvariantCategory.ROUTES,
    modules=["routes"],
    severity=MEDIUM,
    execution=[COMMIT],
    rationale="The routing engine only supports these profiles. "
    "Invalid profiles cause routing failures or undefined behaviour.",
)
def check_profile_valid(ctx: InvariantContext) -> InvariantResult:
    """RTE-008: Verify every route has a recognised routing profile."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="RTE-008",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    cursor = ctx.db.execute(
        """
        SELECT id, profile
        FROM routes
        WHERE profile IS NULL OR profile NOT IN ('truck', 'truck_fast', 'truck_safe',
                                                  'truck_cheap', 'truck_short', 'car',
                                                  'bike', 'foot')
        """
    )
    invalid: list[str] = [
        f"Route {row[0]}: profile={row[1]!r}" for row in cursor
    ]

    if invalid:
        return InvariantResult(
            invariant_id="RTE-008",
            status=InvariantStatus.FAIL,
            expected="Route profile is one of: truck, truck_fast, truck_safe, "
            "truck_cheap, truck_short, car, bike, foot",
            actual=f"{len(invalid)} route(s) with invalid or missing profile",
            message="; ".join(invalid),
            affected_modules=["routes"],
        )

    return InvariantResult(
        invariant_id="RTE-008",
        status=InvariantStatus.PASS,
        expected="All routes have a valid routing profile",
        actual="No profile violations found",
    )
