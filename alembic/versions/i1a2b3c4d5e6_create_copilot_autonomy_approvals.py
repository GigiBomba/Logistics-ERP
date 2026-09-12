"""create copilot_autonomy_approvals

Pre-approved workflow table for Autonomous Mode (§21 Ph.4 item 4, §23.1).

Each row opts one company's workflow (a plan ``intent.name``) into executing
without the manual confirmation step.  The planner's autonomous path consults
``is_approved`` only AFTER the tier feature flag and circuit-breaker checks.

Revision ID: i1a2b3c4d5e6
Revises: h0a1b2c3d4e1
Create Date: 2026-08-27
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "i1a2b3c4d5e6"
down_revision: Union[str, None] = "h0a1b2c3d4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    """True when *table* already exists in the database.

    S3-NF-PGT (Stage 3 verification remediation): ``schema_pg.sql`` creates
    ``copilot_autonomy_approvals`` (CREATE TABLE IF NOT EXISTS — it is an
    explicit mirror of this migration, see database/schema_pg.sql ~1637)
    BEFORE Alembic runs on the deployment path
    (``DatabaseManager._init_pg_schema_locked`` → ``_init_pg_schema`` →
    ``_run_alembic_upgrade``).  An unconditional ``op.create_table`` here
    therefore aborts the whole chain on a fresh PostgreSQL database —
    PostgreSQL's transactional DDL then rolls back every earlier migration
    (including the g8c9/o8g9 TIMESTAMPTZ conversions) and ``alembic_version``
    never gets stamped.  On such databases this migration must be a no-op;
    on pure-Alembic databases (no schema_pg.sql) it creates the table.  This
    mirrors the idempotent guards used by j2b3c4d5e6f0 / k4c5d6e7f8a1 /
    l5d6e7f8a9b2 / m6e7f8a9b0c3 / n7f8a9b0c1d4.
    """
    from sqlalchemy import inspect

    conn = op.get_bind()
    try:
        return table in inspect(conn).get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    # See _table_exists: schema_pg.sql pre-creates this table on the
    # deployment path, so skip (the indexes below already exist there too).
    if _table_exists("copilot_autonomy_approvals"):
        return
    op.create_table(
        "copilot_autonomy_approvals",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("workflow", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Unique (company_id, workflow) — the repository's ON CONFLICT upsert
    # targets this index on both PostgreSQL and SQLite.
    op.create_index(
        "uq_copilot_autonomy_approvals_company_workflow",
        "copilot_autonomy_approvals",
        ["company_id", "workflow"],
        unique=True,
    )
    op.create_index(
        "idx_copilot_autonomy_approvals_company",
        "copilot_autonomy_approvals",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_copilot_autonomy_approvals_company", table_name="copilot_autonomy_approvals")
    op.drop_index("uq_copilot_autonomy_approvals_company_workflow", table_name="copilot_autonomy_approvals")
    op.drop_table("copilot_autonomy_approvals")