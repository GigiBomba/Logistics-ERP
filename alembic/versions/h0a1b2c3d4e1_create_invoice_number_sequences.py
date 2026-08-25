"""create invoice_number_sequences

Revision ID: h0a1b2c3d4e1
Revises: g8c9d0e1f2f0
Create Date: 2026-08-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h0a1b2c3d4e1"
down_revision: Union[str, None] = "g8c9d0e1f2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the invoice_number_sequences table.

    Mirrors the raw SQL in ``db_manager._pg_extra_ddl`` / the SQLite
    ``_run_column_migrations`` path: repositories (InvoiceRepository,
    ProformaRepository, ReceiptRepository) maintain a per-(series, year)
    counter here for race-condition-safe number generation.
    """
    op.create_table(
        "invoice_number_sequences",
        sa.Column("series", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("series", "year"),
    )


def downgrade() -> None:
    op.drop_table("invoice_number_sequences")
