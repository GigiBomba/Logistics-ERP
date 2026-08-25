"""create user_workflow_familiarity

Revision ID: a9b0c1d2e3f4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-16
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_workflow_familiarity',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('workflow_id', sa.Text(), nullable=False),
        sa.Column('times_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('familiarity_level', sa.Text(), nullable=False, server_default='new'),
        sa.UniqueConstraint('company_id', 'user_id', 'workflow_id', name='uq_user_workflow_familiarity'),
    )
    op.create_index('idx_user_wf_company', 'user_workflow_familiarity', ['company_id'])
    op.create_index('idx_user_wf_user', 'user_workflow_familiarity', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_user_wf_user', table_name='user_workflow_familiarity')
    op.drop_index('idx_user_wf_company', table_name='user_workflow_familiarity')
    op.drop_table('user_workflow_familiarity')
