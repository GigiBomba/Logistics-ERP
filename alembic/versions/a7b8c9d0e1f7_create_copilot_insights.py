"""create copilot_insights

Revision ID: a7b8c9d0e1f7
Revises: f6a7b8c9d0e6
Create Date: 2026-07-14
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a7b8c9d0e1f7'
down_revision: Union[str, None] = 'f6a7b8c9d0e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_insights',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('insight_type', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False, server_default='low'),
        sa.Column('status', sa.Text(), nullable=False, server_default='new'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_copilot_insights_company', 'copilot_insights', ['company_id', 'created_at'])
    op.create_index('idx_copilot_insights_type', 'copilot_insights', ['insight_type'])


def downgrade() -> None:
    op.drop_index('idx_copilot_insights_type', table_name='copilot_insights')
    op.drop_index('idx_copilot_insights_company', table_name='copilot_insights')
    op.drop_table('copilot_insights')
