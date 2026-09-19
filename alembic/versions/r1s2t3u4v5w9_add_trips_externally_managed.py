"""add trips.externally_managed (Trans.eu dispatch gate)

Adds the ``trips.externally_managed`` flag (TransEU_Architecture.md §9.3):

    - New column ``externally_managed: bool`` on trips: when true, dispatch
      changes are read-only in Operion (Trans.eu owns the assignment)

``externally_managed = 1`` marks trips whose dispatch assignment is owned
by Trans.eu (Trans.eu-managed orders).  Operion's manual dispatch path
(``TripService.update``) rejects truck/driver/status edits on such trips;
the Trans.eu sync services (``TransportSyncService`` /
``OrderSyncService``) write via raw SQL and are intentionally outside the
gate.

Idempotent by design (mirrors q0r1s2t3u4v8):
  - the column add is guarded by ``_column_exists`` —
    ``database/schema_pg.sql`` pre-creates the column on the PostgreSQL
    deployment path BEFORE Alembic runs, so an unconditional
    ``op.add_column`` would abort the chain on a fresh PostgreSQL database.

Revision ID: r1s2t3u4v5w9
Revises: q0r1s2t3u4v8
Create Date: 2026-09-19
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r1s2t3u4v5w9"
down_revision: Union[str, Sequence[str], None] = "q0r1s2t3u4v8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers ────────────────────────────────────────────────────────────────


def _column_exists(table: str, column: str) -> bool:
    """True when *column* already exists on *table* (engine-agnostic)."""
    from sqlalchemy import inspect

    conn = op.get_bind()
    try:
        insp = inspect(conn)
        columns = [c["name"] for c in insp.get_columns(table)]
        return column in columns
    except Exception:
        return False


# ── Migration ──────────────────────────────────────────────────────────────


def upgrade() -> None:
    """Add trips.externally_managed — guarded so a pre-created column (the
    schema_pg.sql deployment path) is not added twice."""
    if not _column_exists("trips", "externally_managed"):
        op.add_column(
            "trips",
            sa.Column(
                "externally_managed",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    """Drop trips.externally_managed if present."""
    if _column_exists("trips", "externally_managed"):
        op.drop_column("trips", "externally_managed")