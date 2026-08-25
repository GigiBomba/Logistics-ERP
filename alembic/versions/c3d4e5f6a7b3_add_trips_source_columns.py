"""add trips source columns

Revision ID: c3d4e5f6a7b3
Revises: b2c3d4e5f6a2
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b3'
down_revision: Union[str, None] = 'b2c3d4e5f6a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('source', sa.String(), nullable=False, server_default='manual'))
    op.add_column('trips', sa.Column('source_provider_id', sa.String(), nullable=True))
    op.add_column('trips', sa.Column('source_reference_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('trips', 'source_reference_id')
    op.drop_column('trips', 'source_provider_id')
    op.drop_column('trips', 'source')
