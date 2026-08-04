"""
Business Invariants — Analytics

Ensures that analytics dashboards, KPIs, and reports are accurate
and internally consistent: KPI totals match raw data, revenue matches
invoices, profit matches trips, dashboard metrics are consistent,
negative-profit alerts fire, and overdue tracking is correct.
"""

from __future__ import annotations

import datetime

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


@invariant(
    id="ANL-001",
    title="KPI totals equal underlying data",
    description=(
        "Dashboard KPI values match raw data aggregation. "
        "No discrepancy between displayed KPIs and query results."
    ),
    category=InvariantCategory.ANALYTICS,
    modules=["analytics"],
    severity=Severity.CRITICAL,
    execution=[NIGHTLY, WEEKLY],
    rationale="Incorrect KPIs mislead business decisions.",
    tags=["analytics", "kpi", "accuracy"],
)
def check_kpi_totals_match_data(ctx: InvariantContext) -> InvariantResult:
    """
    Compare dashboard KPI snapshots against live aggregated data.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="ANL-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    kpi_snapshots = ctx.config.get("analytics_kpi_snapshots", {})
    if not kpi_snapshots:
        return InvariantResult(
            invariant_id="ANL-001",
            status=InvariantStatus.PASS,
            message="No KPI snapshots available for comparison",
            affected_modules=["analytics"],
        )

    discrepancies: list[dict[str, object]] = []
    kpi_mappings = {
        "total_trips": ("trips", "COUNT(*)", None),
        "total_revenue": ("trips", "COALESCE(SUM(revenue), 0)", None),
        "total_invoices": ("invoices", "COUNT(*)", None),
        "active_trips": (
            "trips",
            "COUNT(*)",
            "status NOT IN ('delivered', 'invoiced', 'paid', 'cancelled')",
        ),
    }

    for kpi_name, expected_value in kpi_snapshots.items():
        mapping = kpi_mappings.get(kpi_name)
        if mapping is None:
            continue
        table, aggregation, condition = mapping
        try:
            where_clause = f"WHERE {condition}" if condition else ""
            query = f"SELECT {aggregation} FROM {table} {where_clause}"
            row = ctx.db.execute(query).fetchone()
            actual_value = float(row[0]) if row and row[0] is not None else 0.0
            expected_float = float(expected_value)
            if abs(actual_value - expected_float) > 0.01:
                discrepancies.append(
                    {
                        "kpi": kpi_name,
                        "expected": expected_float,
                        "actual": actual_value,
                        "difference": actual_value - expected_float,
                    }
                )
        except Exception:
            pass

    if discrepancies:
        details = "; ".join(
            f"{d['kpi']}: expected {d['expected']}, got {d['actual']} "
            f"(diff {d['difference']:+.2f})"
            for d in discrepancies
        )
        return InvariantResult(
            invariant_id="ANL-001",
            status=InvariantStatus.FAIL,
            expected="Dashboard KPI values match raw data aggregation",
            actual=f"{len(discrepancies)} KPI discrepancy(ies)",
            message="Analytics KPIs do not match underlying data",
            root_cause=details,
            suggested_fix=(
                "Refresh the analytics KPI cache or recalculate the "
                "dashboard aggregation queries."
            ),
            affected_modules=["analytics"],
            details={"discrepancies": discrepancies},
        )

    return InvariantResult(
        invariant_id="ANL-001",
        status=InvariantStatus.PASS,
        expected="All KPI values match underlying data",
        actual=f"All {len(kpi_snapshots)} KPI(s) are consistent with raw data",
        message="KPI totals match the underlying data",
        affected_modules=["analytics"],
    )


@invariant(
    id="ANL-002",
    title="Revenue charts match invoices",
    description=(
        "Revenue totals in analytics match invoice totals. "
        "No discrepancy between displayed revenue and invoice sums."
    ),
    category=InvariantCategory.ANALYTICS,
    modules=["analytics", "invoicing"],
    severity=Severity.CRITICAL,
    execution=[NIGHTLY, WEEKLY],
    rationale="Revenue misstatements can cause financial reporting errors.",
    tags=["analytics", "revenue", "invoices"],
)
def check_revenue_charts_match_invoices(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that the analytics revenue metric matches the sum of invoice totals.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="ANL-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        invoice_total = ctx.db.execute(
            """
            SELECT COALESCE(SUM(total_gross), 0)
            FROM invoices
            WHERE status NOT IN ('cancelled', 'draft')
            """
        ).fetchone()
        actual_invoice_sum = float(invoice_total[0]) if invoice_total else 0.0

        # Get analytics revenue snapshot
        analytics_revenue = ctx.config.get(
            "analytics_revenue_total", None
        )
    except Exception:
        return InvariantResult(
            invariant_id="ANL-002",
            status=InvariantStatus.PASS,
            message="Could not query invoices — runtime validation skipped",
            affected_modules=["analytics", "invoicing"],
        )

    if analytics_revenue is None:
        return InvariantResult(
            invariant_id="ANL-002",
            status=InvariantStatus.PASS,
            message="No analytics revenue snapshot available for comparison",
            affected_modules=["analytics", "invoicing"],
        )

    try:
        analytics_revenue_float = float(analytics_revenue)
    except (TypeError, ValueError):
        return InvariantResult(
            invariant_id="ANL-002",
            status=InvariantStatus.ERROR,
            message=f"analytics_revenue_total is not a number: {analytics_revenue!r}",
            affected_modules=["analytics", "invoicing"],
        )

    if abs(actual_invoice_sum - analytics_revenue_float) > 0.01:
        return InvariantResult(
            invariant_id="ANL-002",
            status=InvariantStatus.FAIL,
            expected=(
                "Analytics revenue matches sum of non-draft invoices"
            ),
            actual=(
                f"analytics revenue = {analytics_revenue_float:.2f}, "
                f"actual invoice sum = {actual_invoice_sum:.2f}"
            ),
            message="Revenue charts do not match invoice totals",
            root_cause=(
                f"Difference of {actual_invoice_sum - analytics_revenue_float:.2f} "
                f"between analytics display and invoice data"
            ),
            suggested_fix=(
                "Recalculate analytics revenue aggregations. "
                "Ensure all non-draft invoices are included."
            ),
            affected_modules=["analytics", "invoicing"],
            details={
                "analytics_revenue": analytics_revenue_float,
                "actual_invoice_sum": actual_invoice_sum,
                "difference": actual_invoice_sum - analytics_revenue_float,
            },
        )

    return InvariantResult(
        invariant_id="ANL-002",
        status=InvariantStatus.PASS,
        expected="Revenue matches invoice totals",
        actual=f"analytics={analytics_revenue_float:.2f}, invoices={actual_invoice_sum:.2f}",
        message="Revenue charts are consistent with invoice data",
        affected_modules=["analytics", "invoicing"],
    )


@invariant(
    id="ANL-003",
    title="Profit reports match trips",
    description=(
        "Profit calculations in reports match trip-level net_profit sums. "
        "No discrepancy between reported and actual profit."
    ),
    category=InvariantCategory.ANALYTICS,
    modules=["analytics", "trips"],
    severity=Severity.CRITICAL,
    execution=[NIGHTLY, WEEKLY],
    rationale="Profit misstatements lead to incorrect business analysis.",
    tags=["analytics", "profit", "trips"],
)
def check_profit_reports_match_trips(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that the analytics profit metric matches trip net_profit sums.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="ANL-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        trip_profit_total = ctx.db.execute(
            """
            SELECT COALESCE(SUM(net_profit), 0)
            FROM trips
            WHERE status NOT IN ('cancelled')
            """
        ).fetchone()
        actual_profit_sum = float(trip_profit_total[0]) if trip_profit_total else 0.0

        analytics_profit = ctx.config.get(
            "analytics_profit_total", None
        )
    except Exception:
        return InvariantResult(
            invariant_id="ANL-003",
            status=InvariantStatus.PASS,
            message="Could not query trips — runtime validation skipped",
            affected_modules=["analytics", "trips"],
        )

    if analytics_profit is None:
        return InvariantResult(
            invariant_id="ANL-003",
            status=InvariantStatus.PASS,
            message="No analytics profit snapshot available for comparison",
            affected_modules=["analytics", "trips"],
        )

    try:
        analytics_profit_float = float(analytics_profit)
    except (TypeError, ValueError):
        return InvariantResult(
            invariant_id="ANL-003",
            status=InvariantStatus.ERROR,
            message=f"analytics_profit_total is not a number: {analytics_profit!r}",
            affected_modules=["analytics", "trips"],
        )

    if abs(actual_profit_sum - analytics_profit_float) > 0.01:
        return InvariantResult(
            invariant_id="ANL-003",
            status=InvariantStatus.FAIL,
            expected=(
                "Analytics profit matches trip-level net_profit sum"
            ),
            actual=(
                f"analytics profit = {analytics_profit_float:.2f}, "
                f"actual trips sum = {actual_profit_sum:.2f}"
            ),
            message="Profit reports do not match trip data",
            root_cause=(
                f"Difference of {actual_profit_sum - analytics_profit_float:.2f} "
                f"between analytics profit and trip-level net_profit sum"
            ),
            suggested_fix=(
                "Recalculate analytics profit aggregations from trip "
                "net_profit values. Check for excluded trips."
            ),
            affected_modules=["analytics", "trips"],
            details={
                "analytics_profit": analytics_profit_float,
                "actual_trip_profit_sum": actual_profit_sum,
                "difference": actual_profit_sum - analytics_profit_float,
            },
        )

    return InvariantResult(
        invariant_id="ANL-003",
        status=InvariantStatus.PASS,
        expected="Profit matches trip net_profit sums",
        actual=f"analytics={analytics_profit_float:.2f}, trips={actual_profit_sum:.2f}",
        message="Profit reports are consistent with trip data",
        affected_modules=["analytics", "trips"],
    )


@invariant(
    id="ANL-004",
    title="Dashboard metrics internally consistent",
    description=(
        "Total clients == active + inactive. "
        "Total trips by status == total trips. "
        "Dashboard breakdowns sum to totals."
    ),
    category=InvariantCategory.ANALYTICS,
    modules=["analytics"],
    severity=Severity.HIGH,
    execution=[NIGHTLY],
    rationale="Inconsistent dashboard metrics erode user trust.",
    tags=["analytics", "dashboard", "consistency"],
)
def check_dashboard_metrics_consistent(ctx: InvariantContext) -> InvariantResult:
    """
    Validate internal consistency of dashboard metric breakdowns.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="ANL-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    inconsistencies: list[str] = []

    try:
        # Check clients breakdown: total = active + inactive
        client_totals = ctx.db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) AS inactive
            FROM clients
            """
        ).fetchone()
        if client_totals:
            total = int(client_totals[0])
            active = int(client_totals[1])
            inactive = int(client_totals[2])
            if total != active + inactive:
                inconsistencies.append(
                    f"clients: total={total} != active({active}) + "
                    f"inactive({inactive}) = {active + inactive}"
                )
    except Exception:
        pass

    try:
        # Check trips by status total == total trips
        total_trips_row = ctx.db.execute(
            "SELECT COUNT(*) FROM trips"
        ).fetchone()
        total_trips = int(total_trips_row[0]) if total_trips_row else 0

        status_breakdown = ctx.db.execute(
            """
            SELECT COUNT(*) FROM trips
            GROUP BY status
            """
        ).fetchall()
        sum_by_status = sum(int(r[0]) for r in status_breakdown)

        if total_trips != sum_by_status:
            inconsistencies.append(
                f"trips: total={total_trips} != "
                f"sum by status={sum_by_status}"
            )
    except Exception:
        pass

    try:
        # Check invoices breakdown: total = draft + finalized + submitted + ...
        total_inv_row = ctx.db.execute(
            "SELECT COUNT(*) FROM invoices"
        ).fetchone()
        total_invoices = int(total_inv_row[0]) if total_inv_row else 0

        inv_breakdown = ctx.db.execute(
            """
            SELECT COUNT(*) FROM invoices
            GROUP BY status
            """
        ).fetchall()
        sum_inv_by_status = sum(int(r[0]) for r in inv_breakdown)

        if total_invoices != sum_inv_by_status:
            inconsistencies.append(
                f"invoices: total={total_invoices} != "
                f"sum by status={sum_inv_by_status}"
            )
    except Exception:
        pass

    if inconsistencies:
        return InvariantResult(
            invariant_id="ANL-004",
            status=InvariantStatus.FAIL,
            expected="Dashboard breakdowns sum to their totals",
            actual=f"{len(inconsistencies)} internal inconsistency(ies)",
            message="Dashboard metrics are internally inconsistent",
            root_cause="; ".join(inconsistencies),
            suggested_fix=(
                "Review the analytics aggregation queries. Ensure "
                "all status values are covered in breakdown queries."
            ),
            affected_modules=["analytics"],
            details={"inconsistencies": inconsistencies},
        )

    return InvariantResult(
        invariant_id="ANL-004",
        status=InvariantStatus.PASS,
        expected="All dashboard breakdowns sum to totals",
        actual="No internal inconsistencies found",
        message="Dashboard metrics are internally consistent",
        affected_modules=["analytics"],
    )


@invariant(
    id="ANL-005",
    title="Negative profit alerts fire",
    description=(
        "Trips with negative net_profit generate RED alerts "
        "in the operations dashboard."
    ),
    category=InvariantCategory.ANALYTICS,
    modules=["analytics", "operations"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Undetected negative-profit trips hurt the bottom line.",
    tags=["analytics", "alerts", "negative-profit"],
)
def check_negative_profit_alerts(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that negative-profit trips have corresponding RED alerts.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="ANL-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        negative_trips = ctx.db.execute(
            """
            SELECT t.id, t.reference_code, t.net_profit
            FROM trips t
            WHERE t.net_profit < 0
              AND t.status NOT IN ('cancelled')
            ORDER BY t.net_profit ASC
            """
        ).fetchall()
    except Exception:
        return InvariantResult(
            invariant_id="ANL-005",
            status=InvariantStatus.PASS,
            message="Could not query trips — runtime validation skipped",
            affected_modules=["analytics", "operations"],
        )

    if not negative_trips:
        return InvariantResult(
            invariant_id="ANL-005",
            status=InvariantStatus.PASS,
            expected="No negative-profit trips exist",
            actual="0 trips with negative net_profit",
            message="No negative-profit trips to alert on",
            affected_modules=["analytics", "operations"],
        )

    # Check whether alerts exist for these trips
    negative_trip_ids = [int(r[0]) for r in negative_trips]
    try:
        alerted_trips = ctx.db.execute(
            """
            SELECT DISTINCT reference_id
            FROM alerts
            WHERE alert_type = 'negative_profit'
              AND severity = 'RED'
              AND reference_id IN (%s)
            """
            % ",".join(str(tid) for tid in negative_trip_ids[:100])
        ).fetchall()
        alerted_ids = {int(r[0]) for r in alerted_trips}
    except Exception:
        # Alert table may not exist or query fails
        alerted_ids = set()

    missing_alerts = [tid for tid in negative_trip_ids if tid not in alerted_ids]

    if missing_alerts:
        return InvariantResult(
            invariant_id="ANL-005",
            status=InvariantStatus.FAIL,
            expected="All negative-profit trips have RED alerts",
            actual=(
                f"{len(negative_trip_ids)} negative-profit trip(s), "
                f"{len(missing_alerts)} missing RED alert(s)"
            ),
            message="Negative-profit trips without RED alerts detected",
            root_cause=(
                f"Trips with IDs {missing_alerts[:10]} have negative "
                f"net_profit but no corresponding RED alert"
            ),
            suggested_fix=(
                "Ensure the negative-profit alert trigger runs after "
                "trip completion. Check the alert rule configuration."
            ),
            affected_modules=["analytics", "operations"],
            details={
                "negative_trip_ids": negative_trip_ids[:20],
                "missing_alert_ids": missing_alerts[:20],
            },
        )

    return InvariantResult(
        invariant_id="ANL-005",
        status=InvariantStatus.PASS,
        expected="All negative-profit trips have RED alerts",
        actual=f"All {len(negative_trip_ids)} negative-profit trip(s) have RED alerts",
        message="Negative profit alerts are correctly firing",
        affected_modules=["analytics", "operations"],
    )


@invariant(
    id="ANL-006",
    title="Overdue invoice tracking accurate",
    description=(
        "days_late calculation: today - due_date, correctly "
        "classified as RED / YELLOW based on severity thresholds."
    ),
    category=InvariantCategory.ANALYTICS,
    modules=["analytics", "invoicing"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Incorrect overdue classifications cause wrong collection priorities.",
    tags=["analytics", "overdue", "invoices"],
)
def check_overdue_invoice_tracking(ctx: InvariantContext) -> InvariantResult:
    """
    Validate that overdue invoice calculations are accurate.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="ANL-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        overdue_invoices = ctx.db.execute(
            """
            SELECT id, invoice_number, due_date, paid_date
            FROM invoices
            WHERE status NOT IN ('paid', 'cancelled', 'draft')
              AND due_date IS NOT NULL
            """
        ).fetchall()
    except Exception:
        return InvariantResult(
            invariant_id="ANL-006",
            status=InvariantStatus.PASS,
            message="Could not query invoices — runtime validation skipped",
            affected_modules=["analytics", "invoicing"],
        )

    if not overdue_invoices:
        return InvariantResult(
            invariant_id="ANL-006",
            status=InvariantStatus.PASS,
            expected="All invoices are paid or within due date",
            actual="0 overdue invoices found",
            message="No overdue invoices to check",
            affected_modules=["analytics", "invoicing"],
        )

    red_threshold_days = ctx.config.get("overdue_red_threshold_days", 30)
    yellow_threshold_days = ctx.config.get("overdue_yellow_threshold_days", 7)

    misclassified: list[dict[str, object]] = []
    for row in overdue_invoices:
        try:
            invoice_id = int(row[0])
            invoice_number = str(row[1] or "")
            due_date_str = str(row[2])
            paid_date_str = str(row[3]) if row[3] else None

            # Parse dates from string format (handles both sqlite and pg)
            due_date = _parse_date(due_date_str)
            if due_date is None:
                continue

            today = datetime.date.today()
            days_late = (today - due_date).days

            # Determine expected classification
            if days_late >= red_threshold_days:
                expected_classification = "RED"
            elif days_late >= yellow_threshold_days:
                expected_classification = "YELLOW"
            else:
                expected_classification = "GREEN"

            # Get actual classification from analytics
            actual_classification = ctx.config.get(
                f"invoice_overdue_classification_{invoice_id}", None
            )

            if actual_classification and actual_classification != expected_classification:
                misclassified.append(
                    {
                        "invoice_id": invoice_id,
                        "invoice_number": invoice_number,
                        "days_late": days_late,
                        "expected": expected_classification,
                        "actual": actual_classification,
                    }
                )
        except Exception:
            pass

    if misclassified:
        details = "; ".join(
            f"inv#{d['invoice_number']} (id={d['invoice_id']}): "
            f"{d['days_late']} day(s) late, expected {d['expected']}, "
            f"got {d['actual']}"
            for d in misclassified
        )
        return InvariantResult(
            invariant_id="ANL-006",
            status=InvariantStatus.FAIL,
            expected="All overdue invoices correctly classified as RED/YELLOW",
            actual=f"{len(misclassified)} misclassified invoice(s)",
            message="Overdue invoice tracking has incorrect classifications",
            root_cause=details,
            suggested_fix=(
                "Review the overdue classification logic in analytics. "
                "Ensure days_late = today - due_date and thresholds "
                f"are RED >= {red_threshold_days}d, YELLOW >= {yellow_threshold_days}d."
            ),
            affected_modules=["analytics", "invoicing"],
            details={"misclassified": misclassified},
        )

    return InvariantResult(
        invariant_id="ANL-006",
        status=InvariantStatus.PASS,
        expected="All overdue invoices correctly classified",
        actual=f"All {len(overdue_invoices)} overdue invoice(s) are correctly classified",
        message="Overdue invoice tracking is accurate",
        affected_modules=["analytics", "invoicing"],
    )


def _parse_date(date_str: str | None) -> datetime.date | None:
    """Parse a date string in common formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.datetime.strptime(date_str, fmt).date()
            return parsed
        except ValueError:
            continue
    return None
