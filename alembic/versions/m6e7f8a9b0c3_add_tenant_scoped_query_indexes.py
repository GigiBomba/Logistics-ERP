"""add tenant-scoped query indexes on trips/drivers/trucks/assignments

Adds five indexes that speed up company-scoped (multi-tenant) reads and
the route-history JOIN:

  - ``trips(route_history_v2_id)`` (``idx_trips_route_history_v2_id``)
      Supports ``RouteRepository.get_by_trip_id``
      (repositories/route_repository.py:119) — ``JOIN trips t ON
      t.route_history_v2_id = r.id WHERE t.id = ?`` currently SCANs the
      trips table because ``route_history_v2_id`` is only added at runtime
      by ``db_manager`` with no index behind it.
  - ``trips(company_id, status)`` (``idx_trips_company_status``)
      Supports ``TripRepository.get_by_statuses``
      (repositories/trip_repository.py:212-222) — company-scoped
      ``WHERE status IN (...) AND company_id = ?``.  schema.py declares
      this constant but it is never executed anywhere (dead code), and
      schema_pg.sql has no ``idx_trips_company_status``.
  - ``drivers(company_id)`` (``idx_drivers_company``)
  - ``trucks(company_id)`` (``idx_trucks_company``)
  - ``driver_truck_assignments(company_id)`` (``idx_dta_company``)
      Plain company-scoped lookups.  Fresh SQLite installs receive these
      three via ``db_manager``'s tenant-table loop and fresh PostgreSQL
      installs via ``schema_pg.sql``, so ``IF NOT EXISTS`` makes this
      migration a no-op there; existing databases that predate those
      paths (or where the guard skipped them) are brought in line here.

Each index is created ``IF NOT EXISTS`` (idempotent against databases
that already have it) and guarded by a table/column-exists check so the
migration is safe on partial databases.  Downgrade uses ``IF EXISTS`` and
reverses exactly what the upgrade created.

Revision ID: m6e7f8a9b0c3
Revises: l5d6e7f8a9b2
Create Date: 2026-09-05
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "m6e7f8a9b0c3"
down_revision: Union[str, None] = "l5d6e7f8a9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (index name, table, columns) — column names verified against schema.py
# and schema_pg.sql.  `trips.company_id`/`trips.route_history_v2_id` are
# added at runtime by db_manager._run_column_migrations (the tenant and
# trips column migrations), so they exist on any fully-initialized DB.
INDEXES: list[tuple[str, str, list[str]]] = [
    ("idx_trips_route_history_v2_id", "trips", ["route_history_v2_id"]),
    ("idx_trips_company_status", "trips", ["company_id", "status"]),
    ("idx_drivers_company", "drivers", ["company_id"]),
    ("idx_trucks_company", "trucks", ["company_id"]),
    ("idx_dta_company", "driver_truck_assignments", ["company_id"]),
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