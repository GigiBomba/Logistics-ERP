"""Datetime integrity — convert TEXT timestamps to TIMESTAMPTZ.

Revision ID: g8c9d0e1f2f0
Revises: f7b8c9d0e1f8
Create Date: 2026-07-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "g8c9d0e1f2f0"
down_revision: Union[str, Sequence[str], None] = "f7b8c9d0e1f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Columns ──────────────────────────────────────────────────────────────

# Priority 1: Operational timestamp columns
TIMESTAMP_COLUMNS: list[tuple[str, str]] = [
    # ── trips ──────────────────────────────────────────────────────
    ("trips", "created_at"),
    ("trips", "start_date"),
    ("trips", "end_date"),
    ("trips", "payment_date"),
    # ── invoices ───────────────────────────────────────────────────
    ("invoices", "issue_date"),
    ("invoices", "due_date"),
    ("invoices", "created_at"),
    ("invoices", "updated_at"),
    # ── route_history_v2 ───────────────────────────────────────────
    ("route_history_v2", "created_at"),
    ("route_history_v2", "last_calculated_at"),
    # ── gps_telemetry ──────────────────────────────────────────────
    ("gps_telemetry", "recorded_at"),
    ("gps_telemetry", "created_at"),
    # ── operation_events ───────────────────────────────────────────
    ("operation_events", "created_at"),
    # ── alerts ─────────────────────────────────────────────────────
    ("alerts", "created_at"),
    ("alerts", "resolved_at"),
    # ── documents ──────────────────────────────────────────────────
    ("documents", "uploaded_at"),
    ("documents", "updated_at"),
    ("documents", "expiry_date"),
    # ── drivers ────────────────────────────────────────────────────
    ("drivers", "created_at"),
    ("drivers", "updated_at"),
    ("drivers", "license_expiry"),
    ("drivers", "medical_expiry"),
    ("drivers", "hire_date"),
    # ── proforma_invoices ──────────────────────────────────────────
    ("proforma_invoices", "created_at"),
    ("proforma_invoices", "updated_at"),
    ("proforma_invoices", "issue_date"),
    ("proforma_invoices", "valid_until"),
    # ── clients ────────────────────────────────────────────────────
    ("clients", "created_at"),
    ("clients", "updated_at"),
    # ── contracts ──────────────────────────────────────────────────
    ("contracts", "created_at"),
    ("contracts", "updated_at"),
    ("contracts", "start_date"),
    ("contracts", "end_date"),
    # ── receipts ───────────────────────────────────────────────────
    ("receipts", "created_at"),
    ("receipts", "updated_at"),
    ("receipts", "issue_date"),
    ("receipts", "payment_date"),
    # ── companies ──────────────────────────────────────────────────
    ("companies", "created_at"),
    ("companies", "updated_at"),
    # ── users ──────────────────────────────────────────────────────
    ("users", "created_at"),
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


# ── Generated-column handling ──────────────────────────────────────────
# ``trips.month`` is a GENERATED column defined by schema_pg.sql as
# ``SUBSTRING(created_at, 1, 7)`` over a TEXT ``created_at``.  PostgreSQL
# forbids ALTERing the type of a column referenced by a generated column,
# so the migration drops ``month`` (and its index) before converting
# ``created_at`` to TIMESTAMPTZ, then recreates it with an immutable
# expression that is valid for TIMESTAMPTZ.  Downgrade reverses this.

_MONTH_INDEX = "idx_trips_month"


def _drop_trips_month() -> None:
    """Drop the ``trips.month`` generated column and its index (PG only)."""
    conn = op.get_bind()
    conn.execute(sa.text(f'DROP INDEX IF EXISTS "{_MONTH_INDEX}"'))
    conn.execute(sa.text('ALTER TABLE "trips" DROP COLUMN IF EXISTS "month"'))


def _recreate_trips_month_timestamptz() -> None:
    """Recreate ``trips.month`` as a generated column over a TIMESTAMPTZ
    ``created_at``, using an immutable expression (UTC month, YYYY-MM)."""
    op.execute(sa.text(
        'ALTER TABLE "trips" ADD COLUMN "month" TEXT GENERATED ALWAYS AS '
        "(EXTRACT(YEAR FROM created_at AT TIME ZONE 'UTC')::text || '-' || "
        "lpad(EXTRACT(MONTH FROM created_at AT TIME ZONE 'UTC')::text, 2, '0')) STORED"
    ))
    op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS "{_MONTH_INDEX}" ON "trips" ("month")'))


def _recreate_trips_month_text() -> None:
    """Recreate ``trips.month`` as a generated column over a TEXT
    ``created_at`` (the original schema_pg.sql definition)."""
    op.execute(sa.text(
        'ALTER TABLE "trips" ADD COLUMN "month" TEXT GENERATED ALWAYS AS '
        "(SUBSTRING(created_at, 1, 7)) STORED"
    ))
    op.execute(sa.text(f'CREATE INDEX IF NOT EXISTS "{_MONTH_INDEX}" ON "trips" ("month")'))


def upgrade() -> None:
    """Convert TEXT timestamp columns to TIMESTAMPTZ.

    Empty strings are converted to NULL.  Values without timezone
    offset are treated as UTC.
    """
    # SQLite does not support ALTER COLUMN TYPE, CREATE FUNCTION,
    # or PostgreSQL triggers — skip the migration entirely.
    if op.get_bind().dialect.name == "sqlite":
        return

    # ``trips.month`` depends on ``created_at``; drop it before the ALTER.
    if _column_exists("trips", "month"):
        _drop_trips_month()

    # ``documents.expiry_date`` has ``DEFAULT ''`` in schema_pg.sql, which
    # PostgreSQL cannot auto-cast to TIMESTAMPTZ.  Drop the default before
    # the ALTER; the empty-string → NULL conversion below preserves the
    # "no expiry" semantics.  (The current_timestamp defaults used elsewhere
    # auto-cast cleanly, so only this column needs handling.)
    if _column_exists("documents", "expiry_date"):
        op.execute(sa.text('ALTER TABLE "documents" ALTER COLUMN "expiry_date" DROP DEFAULT'))

    # Create the updated_at trigger function.
    # NOTE: NOW() returns TIMESTAMPTZ; assigning directly preserves
    # the timezone.  DO NOT use NOW() AT TIME ZONE 'UTC' — that
    # strips the timezone offset and produces a bare timestamp that
    # PostgreSQL re-interprets through the session timezone, storing
    # the wrong absolute instant.
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Convert each column
    for table, column in TIMESTAMP_COLUMNS:
        if _column_exists(table, column):
            op.execute(f"""
                ALTER TABLE "{table}"
                ALTER COLUMN "{column}" TYPE TIMESTAMPTZ
                USING CASE
                    WHEN "{column}" = '' OR "{column}" IS NULL THEN NULL
                    WHEN "{column}" ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN ("{column}" || 'T00:00:00Z')::TIMESTAMPTZ
                    ELSE "{column}"::TIMESTAMPTZ
                END
            """)

    # Add updated_at triggers to tables that have updated_at
    for table, column in TIMESTAMP_COLUMNS:
        if column == "updated_at" and _column_exists(table, column):
            trigger_name = f"trg_{table}_updated_at"
            op.execute(f"""
                DROP TRIGGER IF EXISTS {trigger_name} ON "{table}"
            """)
            op.execute(f"""
                CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON "{table}"
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """)

    # Recreate the ``trips.month`` generated column now that created_at is
    # TIMESTAMPTZ (dropped at the top of upgrade()).
    if _column_exists("trips", "created_at"):
        _recreate_trips_month_timestamptz()


def downgrade() -> None:
    """Revert TIMESTAMPTZ columns back to TEXT.

    WARNING: Timezone offsets and time-of-day precision are lost
    in the TEXT round-trip (ISO-8601 format preserved).
    """
    # SQLite does not support the PostgreSQL-specific DDL used here.
    if op.get_bind().dialect.name == "sqlite":
        return

    # Drop the ``trips.month`` generated column (timestamptz-based) before
    # converting ``created_at`` back to TEXT.
    if _column_exists("trips", "month"):
        _drop_trips_month()

    for table, column in TIMESTAMP_COLUMNS:
        if _column_exists(table, column):
            op.execute(f"""
                ALTER TABLE "{table}"
                ALTER COLUMN "{column}" TYPE TEXT
                USING TO_CHAR("{column}" AT TIME ZONE 'UTC', 'YYYY-MM-DDTHH24:MI:SS"Z"')
            """)

    # Drop triggers
    for table, column in TIMESTAMP_COLUMNS:
        if column == "updated_at" and _column_exists(table, column):
            op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{table}"')

    # Recreate ``trips.month`` with the original TEXT-based expression.
    if _column_exists("trips", "created_at"):
        _recreate_trips_month_text()

    # Restore the schema_pg.sql ``DEFAULT ''`` on documents.expiry_date.
    if _column_exists("documents", "expiry_date"):
        op.execute(sa.text("ALTER TABLE documents ALTER COLUMN expiry_date SET DEFAULT ''"))

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
