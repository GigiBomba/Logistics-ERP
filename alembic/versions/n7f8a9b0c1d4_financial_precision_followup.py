"""Financial precision follow-up — repair columns missed by f7b8c9d0e1f8.

This migration repairs two defects left by f7b8c9d0e1f8
(``financial_precision_numeric_types``):

(a) Fresh-PostgreSQL ordering defect.  On a fresh PostgreSQL install the
    migration ran *before* ``db_manager._apply_pg_extra_ddl`` had added the
    runtime invoice columns (``subtotal_net``, ``total_vat``, ``total_gross``,
    ``amount_paid``, ``amount_remaining``), so f7b8's ``_column_exists``
    guard skipped them.  Recent deployments created those five columns as
    ``NUMERIC(12,2)`` and ``exchange_rate`` as ``NUMERIC(12,6)`` via the
    extra DDL (only ``exchange_rate`` diverged from the ``NUMERIC(8,6)``
    target).  This revision re-runs the ALTERs so every invoice column
    reaches the intended type.

(b) Two monetary columns missed by f7b8:
    - ``freight_negotiations.amount_eur`` (double-precision in schema.py /
      schema_pg.sql, absent from f7b8's MONETARY_COLUMNS list)
    - ``expenses.amount`` (the expenses table is created at app level by
      ``db_manager.ensure_expenses_table`` and is only listed in f7b8 under
      a comment; on PostgreSQL the column was never converted because the
      table is added after migrations run)

Existing deployed databases have already stamped and run f7b8, so an in-place
edit of that revision would never reach them.  A follow-up revision (this
file) is the only path that repairs those databases.

Idempotent by design: PostgreSQL's ``ALTER COLUMN ... TYPE`` is a no-op when
the target type is unchanged, so re-running the upgrade (or re-ALTERing a
column f7b8 already converted) is safe.

The six invoice fixups are conditional: a column that already exists is
ALTERed (an idempotent no-op if the type matches), while one that is absent
is added with ``ADD COLUMN IF NOT EXISTS`` and the schema_pg.sql default.
The latter closes the one-jump upgrade path for a PostgreSQL database
created in the pre-extra-DDL era (before the invoice columns existed) that
upgrades straight to this build — without it, those invoices would be
permanently missing the columns and every invoice INSERT would fail.

Revision ID: n7f8a9b0c1d4
Revises: m6e7f8a9b0c3
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "n7f8a9b0c1d4"
down_revision: Union[str, Sequence[str], None] = "m6e7f8a9b0c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Columns ──────────────────────────────────────────────────────────────

# Columns to (re)fix on upgrade.  Each tuple is (table, column, target_type).
# Columns that f7b8 already converted to the same type are harmless no-ops.
FIXUP_COLUMNS: list[tuple[str, str, str]] = [
    # Missed by f7b8 entirely (see module docstring).
    ("freight_negotiations", "amount_eur", "NUMERIC(12,2)"),
    ("expenses", "amount", "NUMERIC(12,2)"),
    # Fresh-PG ordering defect: exchange_rate landed as NUMERIC(12,6) and the
    # five runtime invoice columns landed as NUMERIC(12,2) because the
    # f7b8 migration ran before _apply_pg_extra_ddl added them.  On upgrade,
    # these six are ALTERed if present, or ADDed (IF NOT EXISTS) if absent.
    ("invoices", "exchange_rate", "NUMERIC(8,6)"),
    ("invoices", "subtotal_net", "NUMERIC(12,2)"),
    ("invoices", "total_vat", "NUMERIC(12,2)"),
    ("invoices", "total_gross", "NUMERIC(12,2)"),
    ("invoices", "amount_paid", "NUMERIC(12,2)"),
    ("invoices", "amount_remaining", "NUMERIC(12,2)"),
]

# Defaults used when ADD-ing an absent invoice FIXUP column on PostgreSQL.
# These close the pre-extra-DDL one-jump upgrade hole: a PG database created
# before the 6 columns existed (via _apply_pg_extra_ddl) would otherwise end
# up with invoices permanently missing them.  The values match the
# schema_pg.sql CREATE TABLE declaration exactly.
INVOICE_ADD_DEFAULTS: dict[str, str] = {
    "exchange_rate": "1.0",
    "subtotal_net": "0",
    "total_vat": "0",
    "total_gross": "0",
    "amount_paid": "0",
    "amount_remaining": "0",
}

# Only the columns whose pre-fixup (extra-DDL / db_manager) state differed
# from the f7b8-era targets are reverted on downgrade.  The five runtime
# invoice columns never existed before f7b8/this revision, so they keep
# their NUMERIC(12,2) form and are intentionally NOT in this list.
DOWNGRADE_COLUMNS: list[tuple[str, str, str]] = [
    ("freight_negotiations", "amount_eur", "DOUBLE PRECISION"),
    ("expenses", "amount", "DOUBLE PRECISION"),
    ("invoices", "exchange_rate", "NUMERIC(12,6)"),
]


# ── Helpers ──────────────────────────────────────────────────────────────


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


# ── Migration ────────────────────────────────────────────────────────────


def upgrade() -> None:
    """(Re)fix invoice monetary columns and the two columns f7b8 missed.

    The six invoice FIXUP columns are handled conditionally: an existing
    column is ALTERed to its target type (a no-op if already correct), while
    an absent one is ADDed with ``ADD COLUMN IF NOT EXISTS`` and the
    schema_pg.sql default — closing the pre-extra-DDL one-jump upgrade path
    where invoices would otherwise be permanently missing those columns.
    ``freight_negotiations.amount_eur`` and ``expenses.amount`` always exist
    on the app-managed tables and are ALTER-only.  Each statement is guarded
    by ``_column_exists`` so the migration continues if a table/column does
    not exist (e.g. tables created at app level after migrations run).
    """
    # SQLite does not support ALTER COLUMN TYPE — skip the migration there.
    if op.get_bind().dialect.name == "sqlite":
        return

    for table, column, target_type in FIXUP_COLUMNS:
        if _column_exists(table, column):
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{column}" TYPE {target_type} '
                f'USING "{column}"::{target_type}'
            )
        elif table == "invoices" and column in INVOICE_ADD_DEFAULTS:
            op.execute(
                f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" '
                f'{target_type} DEFAULT {INVOICE_ADD_DEFAULTS[column]}'
            )


def downgrade() -> None:
    """Revert the three columns whose pre-fixup state differed.

    ``freight_negotiations.amount_eur`` and ``expenses.amount`` return to
    DOUBLE PRECISION and ``invoices.exchange_rate`` returns to NUMERIC(12,6)
    (its fresh-PG extra-DDL state before this revision).  The other five
    invoice columns did not exist before this revision's upgrade path and
    keep their NUMERIC(12,2) type.
    """
    # SQLite does not support ALTER COLUMN TYPE — skip the migration there.
    if op.get_bind().dialect.name == "sqlite":
        return

    for table, column, target_type in DOWNGRADE_COLUMNS:
        if _column_exists(table, column):
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{column}" TYPE {target_type} '
                f'USING "{column}"::{target_type}'
            )
