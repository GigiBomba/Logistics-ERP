"""Financial precision — migrate monetary columns from DOUBLE PRECISION to NUMERIC.

This migration converts all monetary and financial columns from IEEE-754
``DOUBLE PRECISION`` to exact ``NUMERIC`` types, eliminating floating-point
rounding errors in ERP financial calculations.

Revision ID: f7b8c9d0e1f8
Revises: a9b0c1d2e3f4, a9b0c1d2e3f5
Create Date: 2026-07-21
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "f7b8c9d0e1f8"
down_revision: Union[str, Sequence[str], None] = (
    "a9b0c1d2e3f4",
    "a9b0c1d2e3f5",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers ────────────────────────────────────────────────────────────────

# Columns grouped for clarity: each tuple is (table, column, target_type)
MONETARY_COLUMNS: list[tuple[str, str, str]] = [
    # ── trips ──────────────────────────────────────────────────────
    ("trips", "total_price_eur", "NUMERIC(12,2)"),
    ("trips", "rate_per_km", "NUMERIC(12,6)"),
    ("trips", "gross_per_km", "NUMERIC(12,6)"),
    ("trips", "net_profit", "NUMERIC(12,2)"),
    ("trips", "extra_costs", "NUMERIC(12,2)"),
    ("trips", "fuel_cost", "NUMERIC(12,2)"),
    ("trips", "toll_cost", "NUMERIC(12,2)"),
    ("trips", "salary_cost", "NUMERIC(12,2)"),
    ("trips", "price_pre_vat", "NUMERIC(12,2)"),
    ("trips", "vat_percent", "NUMERIC(5,2)"),
    # ── invoices ───────────────────────────────────────────────────
    ("invoices", "total_amount", "NUMERIC(12,2)"),
    ("invoices", "exchange_rate", "NUMERIC(8,6)"),
    ("invoices", "subtotal_net", "NUMERIC(12,2)"),
    ("invoices", "total_vat", "NUMERIC(12,2)"),
    ("invoices", "total_gross", "NUMERIC(12,2)"),
    ("invoices", "amount_paid", "NUMERIC(12,2)"),
    ("invoices", "amount_remaining", "NUMERIC(12,2)"),
    # ── proforma_invoices ───────────────────────────────────────────
    ("proforma_invoices", "subtotal", "NUMERIC(12,2)"),
    ("proforma_invoices", "discount_value", "NUMERIC(12,2)"),
    ("proforma_invoices", "discount_amount", "NUMERIC(12,2)"),
    ("proforma_invoices", "tax_rate", "NUMERIC(5,2)"),
    ("proforma_invoices", "tax_amount", "NUMERIC(12,2)"),
    ("proforma_invoices", "grand_total", "NUMERIC(12,2)"),
    # ── trucks ─────────────────────────────────────────────────────
    ("trucks", "monthly_rate", "NUMERIC(12,2)"),
    # ── drivers ─────────────────────────────────────────────────────
    ("drivers", "monthly_salary", "NUMERIC(12,2)"),
    # ── clients ─────────────────────────────────────────────────────
    ("clients", "credit_limit_eur", "NUMERIC(12,2)"),
    ("clients", "default_rate_per_km", "NUMERIC(12,6)"),
    # ── route_history ───────────────────────────────────────────────
    ("route_history", "fuel_cost", "NUMERIC(12,2)"),
    ("route_history", "toll_cost", "NUMERIC(12,2)"),
    ("route_history", "total_cost", "NUMERIC(12,2)"),
    ("route_history", "price_recommended", "NUMERIC(12,2)"),
    # ── maintenance_records ─────────────────────────────────────────
    ("maintenance_records", "cost", "NUMERIC(12,2)"),
    # ── receipts ────────────────────────────────────────────────────
    ("receipts", "amount", "NUMERIC(12,2)"),
    ("receipts", "vat_rate", "NUMERIC(5,2)"),
    ("receipts", "vat_amount", "NUMERIC(12,2)"),
    ("receipts", "total", "NUMERIC(12,2)"),
    ("receipts", "mileage", "NUMERIC(12,2)"),
    ("receipts", "fuel", "NUMERIC(12,2)"),
    ("receipts", "accommodation", "NUMERIC(12,2)"),
    ("receipts", "meals", "NUMERIC(12,2)"),
    ("receipts", "parking", "NUMERIC(12,2)"),
    ("receipts", "tolls", "NUMERIC(12,2)"),
    ("receipts", "other_expense", "NUMERIC(12,2)"),
    # ── contracts ──────────────────────────────────────────────────
    ("contracts", "value_eur", "NUMERIC(12,2)"),
    # ── truck_health_scores ─────────────────────────────────────────
    ("truck_health_scores", "compliance_pct", "NUMERIC(5,2)"),
    # ── document_pipeline_runs ──────────────────────────────────────
    ("document_pipeline_runs", "match_confidence", "NUMERIC(5,4)"),
    # ── expenses (created at app level by db_manager.ensure_expenses_table) ─
    ("expenses", "amount", "NUMERIC(12,2)"),
]


# ── Migration ──────────────────────────────────────────────────────────────


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in the current database.

    Uses SQLAlchemy's Inspector (works across SQLite and PostgreSQL).
    Returns False when the table does not exist.
    """
    from sqlalchemy import inspect

    conn = op.get_bind()
    try:
        insp = inspect(conn)
        columns = [c["name"] for c in insp.get_columns(table)]
        return column in columns
    except Exception:
        return False


def upgrade() -> None:
    """Migrate all monetary columns from DOUBLE PRECISION to NUMERIC.

    Each ALTER COLUMN is wrapped in a PL/pgSQL block with EXCEPTION
    handling so the migration continues if a column does not exist
    (e.g. tables that were created before certain migration columns
    were added).
    """
    for table, column, target_type in MONETARY_COLUMNS:
        if _column_exists(table, column):
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{column}" TYPE {target_type} '
                f'USING "{column}"::{target_type}'
            )


def downgrade() -> None:
    """Revert monetary columns back to DOUBLE PRECISION.

    WARNING: This is a destructive downgrade.  NUMERIC values that
    exceed DOUBLE PRECISION precision (approx. 15-17 significant digits)
    will lose precision.  For Operion's financial data (max ~10^7 EUR),
    this is safe.
    """
    for table, column, target_type in MONETARY_COLUMNS:
        if _column_exists(table, column):
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{column}" TYPE DOUBLE PRECISION '
                f'USING "{column}"::DOUBLE PRECISION'
            )
