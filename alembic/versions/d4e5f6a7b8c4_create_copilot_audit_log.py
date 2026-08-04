"""create copilot_audit_log

Revision ID: d4e5f6a7b8c4
Revises: c3d4e5f6a7b3
Create Date: 2026-07-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c4'
down_revision: Union[str, None] = 'c3d4e5f6a7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_audit_log',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=False),
        sa.Column('step_id', sa.Text(), nullable=False),
        sa.Column('tool_name', sa.Text(), nullable=False),
        sa.Column('tool_version', sa.Text(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('permission_checked', sa.Text(), nullable=False),
        sa.Column('permission_granted', sa.Boolean(), nullable=False),
        sa.Column('confidence_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('confirmation_level', sa.SmallInteger(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('model_used', sa.Text(), nullable=False),
        sa.Column('provider_id', sa.Text(), nullable=False),
        sa.Column('prompt_version', sa.Text(), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('corrects_audit_id', sa.UUID(), nullable=True),
    )
    op.create_index('idx_copilot_audit_company_time', 'copilot_audit_log', ['company_id', sa.text('created_at DESC')])
    op.create_index('idx_copilot_audit_conversation', 'copilot_audit_log', ['conversation_id'])


def downgrade() -> None:
    op.drop_index('idx_copilot_audit_conversation', table_name='copilot_audit_log')
    op.drop_index('idx_copilot_audit_company_time', table_name='copilot_audit_log')
    op.drop_table('copilot_audit_log')
