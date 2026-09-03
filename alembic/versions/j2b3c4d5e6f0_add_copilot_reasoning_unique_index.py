"""add unique (company_id, conversation_id) on copilot_reasoning_graphs

The pre-fix ``upsert`` used ``INSERT OR REPLACE`` with no uniqueness
constraint on ``conversation_id``, so re-runs APPENDED duplicate graph rows
per conversation and ``get_by_conversation`` (LIMIT 1, no ORDER BY) returned
an arbitrary one.  This migration dedupes existing rows (keeping the most
recent graph per ``(company_id, conversation_id)``) and then imposes the
unique index the repository's ``ON CONFLICT`` upsert now targets.

Revision ID: j2b3c4d5e6f0
Revises: i1a2b3c4d5e6
Create Date: 2026-08-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "j2b3c4d5e6f0"
down_revision: Union[str, None] = "i1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dedupe_sql(dialect_name: str) -> str:
    """Delete duplicate reasoning-graph rows, keeping one per (company, conv).

    PostgreSQL: primary keys are UUIDs and ``DISTINCT ON`` keeps the most
    recently created row.  SQLite: integer ``rowid`` + ``MIN(rowid)`` keeps
    the oldest surviving row (identical outcome — one row per pair).
    """
    if dialect_name == "postgresql":
        return (
            "DELETE FROM copilot_reasoning_graphs WHERE id NOT IN ("
            "  SELECT DISTINCT ON (company_id, conversation_id) id "
            "  FROM copilot_reasoning_graphs "
            "  ORDER BY company_id, conversation_id, created_at DESC)"
        )
    return (
        "DELETE FROM copilot_reasoning_graphs WHERE rowid NOT IN ("
        "  SELECT MIN(rowid) FROM copilot_reasoning_graphs "
        "  GROUP BY company_id, conversation_id)"
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = getattr(bind, "dialect", None)
    dialect_name = getattr(dialect, "name", "sqlite")

    # 1. Dedupe legacy duplicates before the unique index can be created.
    op.execute(_dedupe_sql(dialect_name))

    # 2. Impose the unique constraint (IF NOT EXISTS tolerates databases
    #    that already received the index via db_manager._pg_extra_ddl).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_copilot_reasoning_company_conversation "
        "ON copilot_reasoning_graphs (company_id, conversation_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_copilot_reasoning_company_conversation")