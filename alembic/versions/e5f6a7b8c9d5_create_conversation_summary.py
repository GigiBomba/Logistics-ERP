"""create conversation_summary

Revision ID: e5f6a7b8c9d5
Revises: d4e5f6a7b8c4
Create Date: 2026-07-14
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d5'
down_revision: Union[str, None] = 'd4e5f6a7b8c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_summary',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('turn_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('pinned_provider_id', sa.Text(), nullable=False),
        sa.Column('pinned_model_id', sa.Text(), nullable=False),
        sa.Column('pinned_prompt_version', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_conversation_summary_company', 'conversation_summary', ['company_id', sa.text('started_at DESC')])
    op.create_index('idx_conversation_summary_user', 'conversation_summary', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_conversation_summary_user', table_name='conversation_summary')
    op.drop_index('idx_conversation_summary_company', table_name='conversation_summary')
    op.drop_table('conversation_summary')
