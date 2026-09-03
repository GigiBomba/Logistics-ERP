"""add covering indexes for company-scoped hot queries (DB4/DB5/DB6)

Adds three indexes that eliminate full-table scans on tenant-scoped reads:

  - ``expenses(company_id)``
      Company-scoped expense queries currently scan the whole table on
      SQLite (schema.py has no expenses index; PostgreSQL already receives
      ``idx_expenses_company`` from schema_pg.sql, so ``IF NOT EXISTS``
      makes this a no-op there).
  - ``maintenance_records(company_id, truck_id, date)``
      Composite covering index for company-scoped fleet maintenance reads
      filtered by truck and date (``company_id`` is added to the table at
      runtime by ``db_manager._run_column_migrations``).
  - ``tacho_driver_activity(company_id, driver_id, activity_date)``
      Composite covering index for company-scoped tacho analytics
      (``idx_tacho_driver_date`` exists but is not company-led).

``trips.driver_name`` (the analytics ``GROUP BY COALESCE(NULLIF(driver_name,
''),'Unassigned')`` pattern) is intentionally NOT added here: schema.py and
schema_pg.sql already create ``idx_trips_driver_name ON trips(driver_name)``
at init time on both engines, and that plain index covers the GROUP BY.

Each index is created ``IF NOT EXISTS`` so databases that already received
the index via ``db_manager``/``schema_pg.sql`` are tolerated; downgrade uses
``IF EXISTS`` and reverses exactly what this migration added.

Revision ID: k4c5d6e7f8a1
Revises: j2b3c4d5e6f0
Create Date: 2026-08-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "k4c5d6e7f8a1"
down_revision: Union[str, None] = "j2b3c4d5e6f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (index name, table, columns) — column names verified against schema.py.
INDEXES: list[tuple[str, str, list[str]]] = [
    ("idx_expenses_company", "expenses", ["company_id"]),
    (
        "idx_maintenance_records_company_truck_date",
        "maintenance_records",
        ["company_id", "truck_id", "date"],
    ),
    (
        "idx_tacho_driver_activity_company_driver_date",
        "tacho_driver_activity",
        ["company_id", "driver_id", "activity_date"],
    ),
]


def _table_has_columns(table: str, columns: list[str]) -> bool:
    """True when *table* exists and has every column in *columns*.

    Uses SQLAlchemy's Inspector so it works on both SQLite and PostgreSQL.
    Returns False when the table does not exist (e.g. a fresh database that
    has not yet run the application's schema init) or lacks a column, so the
    migration is safe on partial databases.
    """
    from sqlalchemy import inspect

    conn = op.get_bind()
    try:
        existing = {c["name"] for c in inspect(conn).get_columns(table)}
        return existing.issuperset(columns)
    except Exception:
        return False


def upgrade() -> None:
    for name, table, columns in INDEXES:
        if _table_has_columns(table, columns):
            op.create_index(name, table, columns, if_not_exists=True)


def downgrade() -> None:
    for name, table, columns in reversed(INDEXES):
        if _table_has_columns(table, columns):
            op.drop_index(name, table_name=table, if_exists=True)