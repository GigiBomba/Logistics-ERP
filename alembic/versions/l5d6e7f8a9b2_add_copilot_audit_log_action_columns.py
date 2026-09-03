"""add action/entity-tracking columns to copilot_audit_log

The original ``copilot_audit_log`` migration (d4e5f6a7b8c4) never declared
the six columns the repository writes on every audit entry — ``action``,
``entity_type``, ``entity_id``, ``old_value``, ``new_value`` and
``performed_by``.  CopilotAuditRepository.log_action() / log_step_execution()
INSERT them unconditionally, and SQLite already has them via
database/schema.py TABLE_COPILOT_AUDIT_LOG (CREATE TABLE IF NOT EXISTS), so
PostgreSQL databases failed at runtime with ``column "X" of relation
"copilot_audit_log" does not exist`` while SQLite worked.

This migration adds the six nullable TEXT columns (matching the SQLite schema
column order/types), closing the SQLite/PostgreSQL parity gap.  Each column is
guarded with a column-exists check so the migration is safe to run against
databases that already received them (e.g. via a manual schema sync).

Revision ID: l5d6e7f8a9b2
Revises: k4c5d6e7f8a1
Create Date: 2026-08-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "l5d6e7f8a9b2"
down_revision: Union[str, None] = "k4c5d6e7f8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (column, type) — order/type mirrors database/schema.py TABLE_COPILOT_AUDIT_LOG.
ADDED_COLUMNS: list[tuple[str, sa.Text]] = [
    ("action", sa.Text()),
    ("entity_type", sa.Text()),
    ("entity_id", sa.Text()),
    ("old_value", sa.Text()),
    ("new_value", sa.Text()),
    ("performed_by", sa.Text()),
]


def _column_exists(table: str, column: str) -> bool:
    """True when *column* exists on *table* (works on SQLite and PostgreSQL).

    Returns False when the table does not exist; the caller must ensure the
    table exists before ADD COLUMN (in this chain it is created by the
    ancestor migration d4e5f6a7b8c4).  The guard primarily makes the
    migration idempotent against databases that already received the
    columns via a manual schema sync.
    """
    from sqlalchemy import inspect

    conn = op.get_bind()
    try:
        existing = {c["name"] for c in inspect(conn).get_columns(table)}
        return column in existing
    except Exception:
        return False


def upgrade() -> None:
    for column, type_ in ADDED_COLUMNS:
        if not _column_exists("copilot_audit_log", column):
            op.add_column("copilot_audit_log", sa.Column(column, type_, nullable=True))


def downgrade() -> None:
    for column, _ in reversed(ADDED_COLUMNS):
        if _column_exists("copilot_audit_log", column):
            op.drop_column("copilot_audit_log", column)