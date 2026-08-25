"""create saved_searches

Revision ID: b2c3d4e5f6a2
Revises: a1b2c3d4e5f1
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'saved_searches',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=False),
        sa.Column('provider_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_saved_searches_company', 'saved_searches', ['company_id'])
    op.create_index('idx_saved_searches_user', 'saved_searches', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_saved_searches_user', table_name='saved_searches')
    op.drop_index('idx_saved_searches_company', table_name='saved_searches')
    op.drop_table('saved_searches')
