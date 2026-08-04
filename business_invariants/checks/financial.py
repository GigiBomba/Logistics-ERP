"""
Operion ERP — Financial Business Invariants (FIN-001 through FIN-015)

Every invariant in this module encodes a fundamental financial truth that must
never be silently broken by refactors, AI patches, migrations, or any other
code change. All checks register automatically via the @invariant decorator.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from business_invariants.decorators import invariant
from business_invariants.models import (
    ExecutionFrequency,
    InvariantCategory,
    InvariantContext,
    InvariantResult,
    InvariantStatus,
    Severity,
)

# ---------------------------------------------------------------------------
# Shorthands
# ---------------------------------------------------------------------------
COMMIT = ExecutionFrequency.COMMIT
PR = ExecutionFrequency.PR
NIGHTLY = ExecutionFrequency.NIGHTLY
WEEKLY = ExecutionFrequency.WEEKLY
RELEASE = ExecutionFrequency.RELEASE
AFTER_MIGRATION = ExecutionFrequency.AFTER_MIGRATION


# ===================================================================
# FIN-001 — Invoice subtotal + VAT = total
# ===================================================================
@invariant(
    id="FIN-001",
    title="Invoice subtotal + VAT = total",
    description=(
        "For every invoice, total_gross must equal "
        "subtotal_net + total_vat within €0.01 rounding precision."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["invoicing"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, NIGHTLY, RELEASE],
    rationale=(
        "Core financial truth: invoice totals must balance or "
        "accounting is broken."
    ),
)
def check_invoice_total_matches(ctx: InvariantContext) -> InvariantResult:
    """FIN-001: total_gross == subtotal_net + total_vat (within 0.01)."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, invoice_number, total_gross, subtotal_net, total_vat
        FROM invoices
        WHERE ROUND(total_gross, 2) != ROUND(subtotal_net + total_vat, 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-001",
            status=InvariantStatus.PASS,
            expected="total_gross == subtotal_net + total_vat for all invoices",
            actual="All invoices balance correctly",
            message="All invoice totals match within rounding precision",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-001",
        status=InvariantStatus.FAIL,
        expected="total_gross == subtotal_net + total_vat",
        actual=f"{len(bad_rows)} invoices with mismatched totals: {', '.join(_ids[:5])}",
        message=f"Found {len(bad_rows)} invoice(s) where total_gross != subtotal_net + total_vat",
        root_cause="Invoice total fields were updated inconsistently",
        suggested_fix=(
            "Recalculate totals for each affected invoice: "
            "SET total_gross = subtotal_net + total_vat"
        ),
        affected_modules=["invoicing"],
        details={"mismatched_ids": _ids[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-002 — Invoice totals cannot become negative
# ===================================================================
@invariant(
    id="FIN-002",
    title="Invoice totals cannot become negative",
    description=(
        "Every invoice must have non-negative values for total_gross, "
        "subtotal_net, total_vat, and amount_remaining."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["invoicing"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, NIGHTLY],
    rationale="Negative monetary values indicate data corruption or logic errors.",
)
def check_invoice_totals_non_negative(ctx: InvariantContext) -> InvariantResult:
    """FIN-002: total_gross >= 0, subtotal_net >= 0, total_vat >= 0, amount_remaining >= 0."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, invoice_number,
               total_gross, subtotal_net, total_vat, amount_remaining
        FROM invoices
        WHERE total_gross < 0
           OR subtotal_net < 0
           OR total_vat < 0
           OR amount_remaining < 0
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-002",
            status=InvariantStatus.PASS,
            expected="All monetary fields >= 0",
            actual="All invoices have non-negative totals",
            message="No negative values found on any invoice",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    violations = []
    for r in bad_rows:
        for col in ("total_gross", "subtotal_net", "total_vat", "amount_remaining"):
            val = r.get(col)
            if val is not None and val < 0:
                violations.append(f"#{r['id']}.{col}={val}")
    return InvariantResult(
        invariant_id="FIN-002",
        status=InvariantStatus.FAIL,
        expected="total_gross >= 0, subtotal_net >= 0, total_vat >= 0, amount_remaining >= 0",
        actual=f"{len(bad_rows)} invoice(s) with negative value(s)",
        message=f"Found {len(bad_rows)} invoice(s) containing negative monetary fields",
        root_cause="Data corruption, incorrect manual adjustment, or bug in invoice update logic",
        suggested_fix="Review affected invoices and correct negative values; add CHECK constraints",
        affected_modules=["invoicing"],
        details={"violations": violations[:20], "total_violations": len(violations)},
    )


# ===================================================================
# FIN-003 — Discount never exceeds line total
# ===================================================================
@invariant(
    id="FIN-003",
    title="Discount never exceeds line total",
    description=(
        "For every invoice line item, discount_amount must be less than "
        "or equal to gross_value."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["invoicing"],
    severity=Severity.HIGH,
    execution=[COMMIT, NIGHTLY],
    rationale="A discount larger than the line total is a logical impossibility.",
)
def check_discount_within_line_total(ctx: InvariantContext) -> InvariantResult:
    """FIN-003: discount_amount <= gross_value for every invoice line item."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT ili.id AS line_id, ili.invoice_id, ili.description,
               ili.gross_value, ili.discount_amount
        FROM invoice_line_items ili
        WHERE ili.discount_amount > ili.gross_value
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-003",
            status=InvariantStatus.PASS,
            expected="discount_amount <= gross_value for all line items",
            actual="All line items have valid discounts",
            message="No line item has a discount exceeding its gross value",
        )

    lines = [
        f"line#{r['line_id']} inv#{r['invoice_id']}: discount={r['discount_amount']} > gross={r['gross_value']}"
        for r in bad_rows
    ]
    return InvariantResult(
        invariant_id="FIN-003",
        status=InvariantStatus.FAIL,
        expected="discount_amount <= gross_value",
        actual=f"{len(bad_rows)} line item(s) with discount exceeding gross value",
        message=f"Found {len(bad_rows)} line item(s) where discount exceeds the line total",
        root_cause="Discount applied without validating against line gross value",
        suggested_fix=(
            "Cap discount_amount to gross_value for each affected line; "
            "add a CHECK(discount_amount <= gross_value) constraint"
        ),
        affected_modules=["invoicing"],
        details={"violating_lines": lines[:20], "total_violations": len(bad_rows)},
    )


# ===================================================================
# FIN-004 — Credit notes balance correctly
# ===================================================================
@invariant(
    id="FIN-004",
    title="Credit notes balance correctly",
    description=(
        "Credit note totals must be less than or equal to the totals of the "
        "original invoices they reference."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["invoicing"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, PR, NIGHTLY],
    rationale="Credit notes that exceed the original invoice represent a financial leak.",
)
def check_credit_notes_balance(ctx: InvariantContext) -> InvariantResult:
    """FIN-004: Credit note totals <= original invoice totals."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT cn.id AS credit_note_id,
               cn.credit_note_number,
               cn.total_gross AS cn_total,
               inv.id AS original_invoice_id,
               inv.invoice_number,
               inv.total_gross AS inv_total
        FROM invoices cn
        JOIN invoices inv ON cn.credit_note_for_id = inv.id
        WHERE cn.type = 'credit_note'
          AND ROUND(cn.total_gross, 2) > ROUND(inv.total_gross, 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-004",
            status=InvariantStatus.PASS,
            expected="credit_note_total <= original_invoice_total",
            actual="All credit notes balance correctly against their invoices",
            message="No credit note exceeds its original invoice total",
        )

    details = [
        f"CN#{r['credit_note_id']} ({r['credit_note_number']}) "
        f"€{r['cn_total']} > INV#{r['original_invoice_id']} ({r['invoice_number']}) "
        f"€{r['inv_total']}"
        for r in bad_rows
    ]
    return InvariantResult(
        invariant_id="FIN-004",
        status=InvariantStatus.FAIL,
        expected="credit_note total <= original invoice total",
        actual=f"{len(bad_rows)} credit note(s) exceed original invoice total(s)",
        message=f"Found {len(bad_rows)} credit note(s) with totals exceeding the referenced invoice",
        root_cause="Credit note amount entered without validating against original invoice balance",
        suggested_fix=(
            "Reduce credit note totals to <= original invoice totals; "
            "enforce application-level check before saving credit notes"
        ),
        affected_modules=["invoicing"],
        details={"violations": details[:20], "total_violations": len(bad_rows)},
    )


# ===================================================================
# FIN-005 — Currency conversions preserve precision
# ===================================================================
@invariant(
    id="FIN-005",
    title="Currency conversions preserve precision",
    description=(
        "An amount converted from EUR to another currency and back to EUR "
        "must round-trip to within €0.01 of the original value."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["currency"],
    severity=Severity.HIGH,
    execution=[COMMIT, NIGHTLY, WEEKLY],
    rationale="Lossy currency conversions silently destroy financial accuracy over time.",
)
def check_currency_round_trip(ctx: InvariantContext) -> InvariantResult:
    """FIN-005: EUR → X → EUR round-trip within 0.01."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT
            from_currency,
            to_currency,
            rate,
            inv_rate AS inverse_rate,
            ROUND(ABS(1.0 - (rate * inv_rate)), 6) AS round_trip_error
        FROM exchange_rates
        WHERE from_currency != 'EUR'
          AND inv_rate IS NOT NULL
          AND ROUND(ABS(1.0 - (rate * inv_rate)), 6) > 0.0001
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-005",
            status=InvariantStatus.PASS,
            expected="rate * inverse_rate ≈ 1.0 (within 0.01 on a reference amount of €100)",
            actual="All exchange rate pairs are consistent",
            message="No currency rate round-trip errors detected",
        )

    return InvariantResult(
        invariant_id="FIN-005",
        status=InvariantStatus.FAIL,
        expected="EUR -> X -> EUR round-trip error <= 0.01",
        actual=f"{len(bad_rows)} exchange rate pair(s) with round-trip error > 0.0001",
        message=f"Found {len(bad_rows)} exchange rate pair(s) that fail the round-trip check",
        root_cause="Exchange rate inverses are not properly maintained or calculated",
        suggested_fix=(
            "Recalculate inverse rates for each affected pair; "
            "validate that rate * inv_rate ≈ 1.0"
        ),
        affected_modules=["currency"],
        details={"violating_pairs": [dict(r) for r in bad_rows]},
    )


# ===================================================================
# FIN-006 — Exchange rates relative to EUR
# ===================================================================
@invariant(
    id="FIN-006",
    title="Exchange rates relative to EUR",
    description="The EUR rate must always be exactly 1.0. All other rates are relative to EUR.",
    category=InvariantCategory.FINANCIAL,
    modules=["currency"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="EUR is the base currency; any deviation breaks conversion calculations.",
)
def check_eur_rate_is_one(ctx: InvariantContext) -> InvariantResult:
    """FIN-006: EUR rate must be 1.0."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, from_currency, to_currency, rate
        FROM exchange_rates
        WHERE from_currency = 'EUR'
          AND to_currency = 'EUR'
          AND ROUND(rate, 6) != 1.0
        LIMIT 5
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-006",
            status=InvariantStatus.PASS,
            expected="EUR rate == 1.0",
            actual="EUR/EUR rate is 1.0",
            message="Base EUR exchange rate is correctly set to 1.0",
        )

    return InvariantResult(
        invariant_id="FIN-006",
        status=InvariantStatus.FAIL,
        expected="EUR/EUR rate = 1.0",
        actual=f"{bad_rows[0]['rate']}",
        message=f"Found {len(bad_rows)} row(s) where EUR/EUR rate != 1.0",
        root_cause="Exchange rate table has an incorrect EUR self-rate",
        suggested_fix="SET rate = 1.0 WHERE from_currency = 'EUR' AND to_currency = 'EUR'",
        affected_modules=["currency"],
        details={"violating_rows": [dict(r) for r in bad_rows]},
    )


# ===================================================================
# FIN-007 — Payment totals equal outstanding balance
# ===================================================================
@invariant(
    id="FIN-007",
    title="Payment totals equal outstanding balance",
    description=(
        "For each invoice, amount_remaining must equal "
        "total_gross - amount_paid."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["payments", "invoicing"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, NIGHTLY],
    rationale="The outstanding balance drives collections, dunning, and financial reporting.",
)
def check_payment_balance(ctx: InvariantContext) -> InvariantResult:
    """FIN-007: amount_remaining == total_gross - amount_paid."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-007",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, invoice_number, total_gross, amount_paid, amount_remaining,
               ROUND(total_gross - COALESCE(amount_paid, 0), 2) AS calculated_remaining
        FROM invoices
        WHERE ROUND(amount_remaining, 2) != ROUND(total_gross - COALESCE(amount_paid, 0), 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-007",
            status=InvariantStatus.PASS,
            expected="amount_remaining == total_gross - amount_paid",
            actual="All invoices have correct outstanding balances",
            message="Payment balances are consistent across all invoices",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-007",
        status=InvariantStatus.FAIL,
        expected="amount_remaining == total_gross - amount_paid",
        actual=f"{len(bad_rows)} invoice(s) with balance mismatch",
        message=f"Found {len(bad_rows)} invoice(s) where amount_remaining is incorrect",
        root_cause="Payment applied without updating amount_remaining, or manual edit to totals",
        suggested_fix=(
            "Recalculate amount_remaining = total_gross - amount_paid "
            "for each affected invoice"
        ),
        affected_modules=["payments", "invoicing"],
        details={"mismatched_ids": _ids[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-008 — Invoice due date >= issue date
# ===================================================================
@invariant(
    id="FIN-008",
    title="Invoice due date >= issue date",
    description="The due_date must be on or after the issue_date for every invoice.",
    category=InvariantCategory.FINANCIAL,
    modules=["invoicing"],
    severity=Severity.CRITICAL,
    execution=[COMMIT],
    rationale="A due date before the issue date is a logical impossibility.",
)
def check_due_date_not_before_issue(ctx: InvariantContext) -> InvariantResult:
    """FIN-008: due_date >= issue_date for all invoices."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-008",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, invoice_number, issue_date, due_date
        FROM invoices
        WHERE due_date < issue_date
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-008",
            status=InvariantStatus.PASS,
            expected="due_date >= issue_date for all invoices",
            actual="All invoices have valid date ranges",
            message="All invoice due dates are on or after their issue dates",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-008",
        status=InvariantStatus.FAIL,
        expected="due_date >= issue_date",
        actual=f"{len(bad_rows)} invoice(s) with due_date < issue_date",
        message=f"Found {len(bad_rows)} invoice(s) where due_date precedes issue_date",
        root_cause="Data entry error or bug in invoice date assignment logic",
        suggested_fix=(
            "Set due_date >= issue_date for each affected invoice; "
            "add CHECK(due_date >= issue_date) constraint to the table"
        ),
        affected_modules=["invoicing"],
        details={"violating_ids": _ids[:20], "total_violations": len(bad_rows)},
    )


# ===================================================================
# FIN-009 — Payment batch totals match
# ===================================================================
@invariant(
    id="FIN-009",
    title="Payment batch totals match",
    description=(
        "For every payment batch, the batch total must equal "
        "the sum of its individual payment amounts."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["payments"],
    severity=Severity.HIGH,
    execution=[COMMIT, PR],
    rationale="Batch-level and payment-level totals must agree for reconciliation.",
)
def check_payment_batch_totals(ctx: InvariantContext) -> InvariantResult:
    """FIN-009: Batch total == sum of individual payment amounts."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-009",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT pb.id AS batch_id,
               pb.batch_reference,
               pb.total_amount AS batch_total,
               COALESCE(SUM(p.amount), 0) AS sum_payments
        FROM payment_batches pb
        LEFT JOIN payments p ON p.batch_id = pb.id
        GROUP BY pb.id, pb.batch_reference, pb.total_amount
        HAVING ROUND(pb.total_amount, 2) != ROUND(COALESCE(SUM(p.amount), 0), 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-009",
            status=InvariantStatus.PASS,
            expected="batch_total == SUM(payments.amount)",
            actual="All payment batches reconcile correctly",
            message="All payment batch totals match the sum of their payments",
        )

    _refs = [str(r["batch_id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-009",
        status=InvariantStatus.FAIL,
        expected="batch_total == SUM(payments.amount)",
        actual=f"{len(bad_rows)} batch(es) with mismatched totals",
        message=f"Found {len(bad_rows)} payment batch(es) where totals do not reconcile",
        root_cause="Payment added or removed from batch without updating batch total",
        suggested_fix=(
            "Recalculate batch_total = SUM(amount) for each affected batch; "
            "consider a DB trigger to keep the total in sync"
        ),
        affected_modules=["payments"],
        details={"mismatched_batch_ids": _refs[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-010 — Proforma grand total matches line items
# ===================================================================
@invariant(
    id="FIN-010",
    title="Proforma grand total matches line items",
    description=(
        "For every proforma invoice, grand_total must equal "
        "subtotal - discount_amount + tax_amount within €0.01."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["proforma"],
    severity=Severity.HIGH,
    execution=[COMMIT],
    rationale="Proforma totals must be accurate for customer-facing quotes.",
)
def check_proforma_grand_total(ctx: InvariantContext) -> InvariantResult:
    """FIN-010: grand_total == subtotal - discount_amount + tax_amount (within 0.01)."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-010",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, proforma_number, grand_total, subtotal,
               discount_amount, tax_amount
        FROM proforma_invoices
        WHERE ROUND(grand_total, 2) !=
              ROUND(subtotal - COALESCE(discount_amount, 0) + COALESCE(tax_amount, 0), 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-010",
            status=InvariantStatus.PASS,
            expected="grand_total == subtotal - discount_amount + tax_amount",
            actual="All proforma invoices match their line totals",
            message="All proforma grand totals are correctly calculated",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-010",
        status=InvariantStatus.FAIL,
        expected="grand_total == subtotal - discount_amount + tax_amount",
        actual=f"{len(bad_rows)} proforma(s) with incorrect grand total",
        message=f"Found {len(bad_rows)} proforma invoice(s) with mismatched grand_total",
        root_cause="Manual override of grand_total or line item change without recalculation",
        suggested_fix=(
            "Recalculate grand_total = subtotal - discount_amount + tax_amount "
            "for each affected proforma"
        ),
        affected_modules=["proforma"],
        details={"mismatched_ids": _ids[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-011 — Receipt totals match
# ===================================================================
@invariant(
    id="FIN-011",
    title="Receipt totals match",
    description=(
        "For every receipt, total must equal amount + vat_amount."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["receipts"],
    severity=Severity.HIGH,
    execution=[COMMIT],
    rationale="Receipt totals must reconcile for expense tracking and VAT reporting.",
)
def check_receipt_total(ctx: InvariantContext) -> InvariantResult:
    """FIN-011: total == amount + vat_amount for every receipt."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-011",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, receipt_number, total, amount, vat_amount
        FROM receipts
        WHERE ROUND(total, 2) != ROUND(COALESCE(amount, 0) + COALESCE(vat_amount, 0), 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-011",
            status=InvariantStatus.PASS,
            expected="total == amount + vat_amount",
            actual="All receipt totals balance",
            message="All receipt totals correctly equal amount + vat_amount",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-011",
        status=InvariantStatus.FAIL,
        expected="total == amount + vat_amount",
        actual=f"{len(bad_rows)} receipt(s) with mismatched total",
        message=f"Found {len(bad_rows)} receipt(s) where total != amount + vat_amount",
        root_cause="Receipt total entered manually without correct sum of amount and VAT",
        suggested_fix=(
            "Update total = amount + vat_amount for each affected receipt; "
            "consider auto-calculating the total field"
        ),
        affected_modules=["receipts"],
        details={"mismatched_ids": _ids[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-012 — Trips net_profit = price - total_costs
# ===================================================================
@invariant(
    id="FIN-012",
    title="Trips net_profit = price - total_costs",
    description=(
        "For every trip, net_profit must equal "
        "price_eur - (fuel_cost + toll_cost + salary_cost + extra_costs)."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["trips", "analytics"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, NIGHTLY],
    rationale="Profitability reporting relies on accurate trip-level P&L.",
)
def check_trip_net_profit(ctx: InvariantContext) -> InvariantResult:
    """FIN-012: net_profit == price_eur - (fuel_cost + toll_cost + salary_cost + extra_costs)."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-012",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, trip_number, price_eur,
               fuel_cost, toll_cost, salary_cost, extra_costs,
               net_profit,
               ROUND(
                   price_eur - (
                       COALESCE(fuel_cost, 0) +
                       COALESCE(toll_cost, 0) +
                       COALESCE(salary_cost, 0) +
                       COALESCE(extra_costs, 0)
                   ), 2
               ) AS calculated_profit
        FROM trips
        WHERE ROUND(net_profit, 2) != ROUND(
                  price_eur - (
                      COALESCE(fuel_cost, 0) +
                      COALESCE(toll_cost, 0) +
                      COALESCE(salary_cost, 0) +
                      COALESCE(extra_costs, 0)
                  ), 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-012",
            status=InvariantStatus.PASS,
            expected="net_profit == price_eur - total_costs",
            actual="All trip profits are correctly calculated",
            message="All trips have consistent net_profit values",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-012",
        status=InvariantStatus.FAIL,
        expected="net_profit == price_eur - (fuel_cost + toll_cost + salary_cost + extra_costs)",
        actual=f"{len(bad_rows)} trip(s) with incorrect net_profit",
        message=f"Found {len(bad_rows)} trip(s) where net_profit does not match calculated value",
        root_cause="Cost or price updated without recalculating net_profit",
        suggested_fix=(
            "Recalculate net_profit = price_eur - total_costs "
            "for each affected trip; consider a computed column in the DB"
        ),
        affected_modules=["trips", "analytics"],
        details={"mismatched_ids": _ids[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-013 — Trips margin is consistent
# ===================================================================
@invariant(
    id="FIN-013",
    title="Trips margin is consistent",
    description=(
        "If price_eur > 0, the margin percentage must equal "
        "(net_profit / price_eur) * 100 within 0.01 precision."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["trips", "analytics"],
    severity=Severity.MEDIUM,
    execution=[NIGHTLY],
    rationale="Margin is a key KPI; stale or incorrect margins mislead management.",
)
def check_trip_margin_consistency(ctx: InvariantContext) -> InvariantResult:
    """FIN-013: If price_eur > 0: margin == (net_profit / price_eur) * 100."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-013",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT id, trip_number, price_eur, net_profit, margin,
               ROUND((net_profit / price_eur) * 100, 2) AS calculated_margin
        FROM trips
        WHERE price_eur > 0
          AND ROUND(margin, 2) != ROUND((net_profit / price_eur) * 100, 2)
        LIMIT 20
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-013",
            status=InvariantStatus.PASS,
            expected="margin == (net_profit / price_eur) * 100 (when price_eur > 0)",
            actual="All trip margins are consistent",
            message="All trip margin percentages are correctly calculated",
        )

    _ids = [str(r["id"]) for r in bad_rows]
    return InvariantResult(
        invariant_id="FIN-013",
        status=InvariantStatus.FAIL,
        expected="margin == (net_profit / price_eur) * 100",
        actual=f"{len(bad_rows)} trip(s) with inconsistent margin",
        message=f"Found {len(bad_rows)} trip(s) where margin does not match (net_profit / price_eur) * 100",
        root_cause="net_profit or price_eur updated without recalculating margin",
        suggested_fix=(
            "Recalculate margin = (net_profit / price_eur) * 100 "
            "for each affected trip where price_eur > 0"
        ),
        affected_modules=["trips", "analytics"],
        details={"mismatched_ids": _ids[:20], "total_mismatches": len(bad_rows)},
    )


# ===================================================================
# FIN-014 — Monetary values stored as NUMERIC(12,2)
# ===================================================================
@invariant(
    id="FIN-014",
    title="Monetary values stored as NUMERIC(12,2)",
    description=(
        "All monetary columns must use proper decimal precision "
        "(NUMERIC(12,2) or equivalent), not DOUBLE PRECISION / REAL / FLOAT."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["database", "financial"],
    severity=Severity.CRITICAL,
    execution=[AFTER_MIGRATION, RELEASE],
    rationale="Floating-point types cause rounding errors in financial calculations.",
)
def check_monetary_column_types(ctx: InvariantContext) -> InvariantResult:
    """FIN-014: All monetary columns use NUMERIC(12,2), not DOUBLE/REAL/FLOAT."""
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-014",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    # Probe the information schema for suspect column types
    # We check common financial tables and column patterns
    bad_columns = _run_query(
        ctx.db,
        """
        SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
          AND data_type IN ('double precision', 'real', 'float', 'float4', 'float8')
          AND (
               LOWER(column_name) LIKE '%price%'
            OR LOWER(column_name) LIKE '%total%'
            OR LOWER(column_name) LIKE '%amount%'
            OR LOWER(column_name) LIKE '%cost%'
            OR LOWER(column_name) LIKE '%vat%'
            OR LOWER(column_name) LIKE '%tax%'
            OR LOWER(column_name) LIKE '%discount%'
            OR LOWER(column_name) LIKE '%gross%'
            OR LOWER(column_name) LIKE '%net%'
            OR LOWER(column_name) LIKE '%paid%'
            OR LOWER(column_name) LIKE '%remaining%'
            OR LOWER(column_name) LIKE '%profit%'
            OR LOWER(column_name) LIKE '%margin%'
            OR LOWER(column_name) LIKE '%fee%'
            OR LOWER(column_name) LIKE '%charge%'
            OR LOWER(column_name) LIKE '%rate%'
            OR LOWER(column_name) LIKE '%fine%'
            OR LOWER(column_name) LIKE '%penalty%'
            OR LOWER(column_name) LIKE '%compensation%'
            OR column_name LIKE '%_eur'
            OR column_name LIKE '%_usd'
            OR column_name LIKE '%_currency%'
          )
        ORDER BY table_name, column_name
        LIMIT 50
        """,
    )

    if not bad_columns:
        return InvariantResult(
            invariant_id="FIN-014",
            status=InvariantStatus.PASS,
            expected="All monetary columns use NUMERIC(12,2) or equivalent DECIMAL type",
            actual="No monetary columns use floating-point types",
            message="All financial columns use proper decimal precision",
        )

    col_summary = [
        f"{r['table_name']}.{r['column_name']} ({r['data_type']})"
        for r in bad_columns
    ]
    return InvariantResult(
        invariant_id="FIN-014",
        status=InvariantStatus.FAIL,
        expected="NUMERIC(12,2) for all monetary columns",
        actual=f"{len(bad_columns)} column(s) use floating-point types",
        message=(
            f"Found {len(bad_columns)} monetary column(s) using floating-point "
            f"types instead of NUMERIC(12,2)"
        ),
        root_cause=(
            "Migration or schema change introduced DOUBLE/REAL/FLOAT "
            "for monetary data"
        ),
        suggested_fix=(
            "ALTER each affected column to NUMERIC(12,2); "
            "ensure application code writes Decimal values, not floats"
        ),
        affected_modules=["database", "financial"],
        details={"bad_columns": col_summary[:50], "total_bad_columns": len(bad_columns)},
    )


# ===================================================================
# FIN-015 — VAT rate is within valid range
# ===================================================================
@invariant(
    id="FIN-015",
    title="VAT rate is within valid range",
    description=(
        "vat_percent must be one of the standard EU VAT rates: "
        "{0, 5, 9, 19, 20, 21, 22, 24, 25, 27}."
    ),
    category=InvariantCategory.FINANCIAL,
    modules=["invoicing"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Invalid VAT rates cause incorrect tax reporting and regulatory non-compliance.",
)
def check_vat_rate_valid(ctx: InvariantContext) -> InvariantResult:
    """FIN-015: vat_percent in {0, 5, 9, 19, 20, 21, 22, 24, 25, 27}."""
    VALID_VAT_RATES = {0, 5, 9, 19, 20, 21, 22, 24, 25, 27}

    if ctx.db is None:
        return InvariantResult(
            invariant_id="FIN-015",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    bad_rows = _run_query(
        ctx.db,
        """
        SELECT DISTINCT vat_percent
        FROM invoices
        WHERE vat_percent IS NOT NULL
          AND vat_percent NOT IN (0, 5, 9, 19, 20, 21, 22, 24, 25, 27)
        ORDER BY vat_percent
        """,
    )

    if not bad_rows:
        return InvariantResult(
            invariant_id="FIN-015",
            status=InvariantStatus.PASS,
            expected=f"vat_percent in {sorted(VALID_VAT_RATES)}",
            actual="All VAT rates are within the valid range",
            message="All invoice VAT rates are standard EU rates",
        )

    invalid_rates = sorted({r["vat_percent"] for r in bad_rows})
    return InvariantResult(
        invariant_id="FIN-015",
        status=InvariantStatus.FAIL,
        expected=f"vat_percent in {sorted(VALID_VAT_RATES)}",
        actual=f"Invalid VAT rate(s) found: {invalid_rates}",
        message=(
            f"Found {len(bad_rows)} distinct invalid VAT rate(s): {invalid_rates}. "
            f"Valid rates: {sorted(VALID_VAT_RATES)}"
        ),
        root_cause="Non-standard VAT rate entered into invoice",
        suggested_fix=(
            "Update vat_percent to a valid EU rate for any invoice "
            "with an invalid value; consider a CHECK constraint"
        ),
        affected_modules=["invoicing"],
        details={"invalid_rates": invalid_rates},
    )


# ===================================================================
# Internal helpers
# ===================================================================


def _run_query(db: Any, sql: str) -> list[dict[str, Any]]:
    """
    Execute a raw SQL query and return results as a list of dicts.

    Works with common Python DB-API 2.0 connections as well as
    SQLAlchemy connections/engines.  Returns an empty list on any
    query error so that a failing query does not bring down the
    invariant run.
    """
    try:
        # SQLAlchemy-style connection
        if hasattr(db, "execute"):
            result = db.execute(sql)
            # SQLAlchemy ResultProxy / CursorResult
            if hasattr(result, "mappings"):
                return [dict(row) for row in result.mappings()]
            # Fallback for raw DB-API cursor
            if hasattr(result, "fetchall"):
                rows = result.fetchall()
                columns = [desc[0] for desc in result.description or []]
                return [dict(zip(columns, row)) for row in rows]
            return []

        # DB-API 2.0 raw connection
        if hasattr(db, "cursor"):
            cursor = db.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description or []]
            rows = cursor.fetchall()
            cursor.close()
            return [dict(zip(columns, row)) for row in rows]

        return []
    except Exception:
        # If the query fails (e.g. table doesn't exist), return empty
        return []
