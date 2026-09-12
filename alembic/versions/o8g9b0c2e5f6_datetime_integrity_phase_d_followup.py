"""Datetime integrity — Phase D follow-up — remaining TEXT timestamps → TIMESTAMPTZ.

Scope: the Phase-D Priority-1/2 datetime columns that g8c9d0e1f2f0 did NOT
convert (its ``TIMESTAMP_COLUMNS`` list stops at the operational columns):

    Priority 1: ``trips.deleted_at`` and ``route_history_v2.archived_at``
                (soft-delete / archive markers) plus
                ``trip_status_history.created_at`` (schema_pg.sql ~378
                declares it TEXT NOT NULL).
    Priority 2: ``truck_route_assignments`` — ``assigned_at``, ``started_at``,
                ``completed_at``, ``archived_at`` — now included per the
                product decision.  The repository default ``assigned_at=""``
                is fixed app-side in a companion unit; any legacy ``''``
                rows map to the epoch below.

Conversion semantics:

    * Nullable columns mirror g8c9d0e1f2f0 exactly: ``''`` → NULL,
      date-only ``^\\d{4}-\\d{2}-\\d{2}$`` → ``...T00:00:00Z`` (UTC
      midnight), else ``::TIMESTAMPTZ``.
    * NOT NULL columns (``trip_status_history.created_at`` and the four
      truck_route_assignments columns) map ``''`` to the epoch
      (``'1970-01-01T00:00:00Z'::timestamptz``) instead of NULL — the g8c9
      empty-string → NULL branch would abort on a NOT NULL column if any
      legacy ``''`` row exists (the ALTER revalidates the NOT NULL
      constraint against the NULL the USING clause produced).  Epoch
      fallback for missing timestamps is the repo precedent from
      ``scripts/backfill_updated_at.py`` (``EPOCH = "1970-01-01T00:00:00Z"``).
      NULL stays NULL, date-only → UTC midnight, else ``::TIMESTAMPTZ``.

      Note: per database/schema_pg.sql (~323) only ``assigned_at`` is
      declared NOT NULL; ``started_at``/``completed_at``/``archived_at`` are
      nullable.  All four still map legacy ``''`` uniformly to the epoch
      per the product decision — the g8c9 ``'' → NULL`` mapping would be
      unsafe on ``assigned_at``, and pinning all four at epoch (instead of
      mixing NULL into the three nullable ones) keeps ordering by
      ``COALESCE(started_at, assigned_at)`` consistent for legacy rows.

Idempotent by design: PostgreSQL ``ALTER COLUMN ... TYPE`` is a no-op when
the target type is unchanged, and every ALTER is guarded by
``_column_exists`` (mirrors g8c9d0e1f2f0).

Downgrade reverts exactly these 7 columns to TEXT (their schema_pg.sql
canonical type) via the g8c9 ``TO_CHAR(col AT TIME ZONE 'UTC',
'YYYY-MM-DDTHH24:MI:SS"Z"')`` round-trip pattern.  None of them is an
``updated_at`` column in g8c9's ``_SCHEMA_PG_TIMESTAMPTZ_UPDATED_AT`` set,
so all 7 are reverted.

This revision chains after n7f8a9b0c1d4 (the Stage-1 financial-precision
follow-up, current head when this file was created).

Revision ID: o8g9b0c2e5f6
Revises: n7f8a9b0c1d4
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "o8g9b0c2e5f6"
down_revision: Union[str, Sequence[str], None] = "n7f8a9b0c1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Columns ──────────────────────────────────────────────────────────────

# Nullable soft-delete / archive markers.  Legacy '' means "never
# deleted/archived" → NULL (exactly the g8c9d0e1f2f0 mapping).
NULLABLE_TIMESTAMP_COLUMNS: list[tuple[str, str]] = [
    ("trips", "deleted_at"),
    ("route_history_v2", "archived_at"),
]

# NOT NULL (or product-decision "no missing value allowed") columns.
# Legacy '' cannot become NULL here (NOT NULL revalidation would abort the
# ALTER), so it maps to the epoch instead — repo precedent from
# scripts/backfill_updated_at.py.
NOT_NULL_TIMESTAMP_COLUMNS: list[tuple[str, str]] = [
    ("trip_status_history", "created_at"),
    ("truck_route_assignments", "assigned_at"),
    ("truck_route_assignments", "started_at"),
    ("truck_route_assignments", "completed_at"),
    ("truck_route_assignments", "archived_at"),
]

# Downgrade reverts exactly the 7 columns above.
TIMESTAMP_COLUMNS: list[tuple[str, str]] = (
    NULLABLE_TIMESTAMP_COLUMNS + NOT_NULL_TIMESTAMP_COLUMNS
)


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
    """Convert the Phase-D TEXT timestamp columns to TIMESTAMPTZ.

    Nullable columns mirror g8c9d0e1f2f0: empty strings become NULL.
    NOT NULL columns map empty strings to the epoch instead (NULL would
    abort the ALTER).  Values without timezone offset are treated as UTC.
    """
    # SQLite does not support ALTER COLUMN TYPE — skip the migration there.
    if op.get_bind().dialect.name == "sqlite":
        return

    # Nullable columns: mirror g8c9d0e1f2f0 exactly ('' → NULL).
    for table, column in NULLABLE_TIMESTAMP_COLUMNS:
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

    # NOT NULL columns: legacy '' → epoch (1970-01-01T00:00:00Z), because
    # '' → NULL would violate the NOT NULL constraint on ALTER.  NULL stays
    # NULL (defensive; a NOT NULL column cannot hold NULL), date-only
    # strings → UTC midnight, everything else parses as ISO-8601.
    for table, column in NOT_NULL_TIMESTAMP_COLUMNS:
        if _column_exists(table, column):
            op.execute(f"""
                ALTER TABLE "{table}"
                ALTER COLUMN "{column}" TYPE TIMESTAMPTZ
                USING CASE
                    WHEN "{column}" = '' THEN '1970-01-01T00:00:00Z'::TIMESTAMPTZ
                    WHEN "{column}" IS NULL THEN NULL
                    WHEN "{column}" ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN ("{column}" || 'T00:00:00Z')::TIMESTAMPTZ
                    ELSE "{column}"::TIMESTAMPTZ
                END
            """)


def downgrade() -> None:
    """Revert the 7 Phase-D columns back to TEXT (schema_pg.sql canonical type).

    WARNING: Timezone offsets and time-of-day precision are lost
    in the TEXT round-trip (ISO-8601 format preserved).
    """
    # SQLite does not support the PostgreSQL-specific DDL used here.
    if op.get_bind().dialect.name == "sqlite":
        return

    for table, column in TIMESTAMP_COLUMNS:
        if _column_exists(table, column):
            op.execute(f"""
                ALTER TABLE "{table}"
                ALTER COLUMN "{column}" TYPE TEXT
                USING TO_CHAR("{column}" AT TIME ZONE 'UTC', 'YYYY-MM-DDTHH24:MI:SS"Z"')
            """)
