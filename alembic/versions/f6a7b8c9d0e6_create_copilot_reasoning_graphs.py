"""create copilot_reasoning_graphs

Revision ID: f6a7b8c9d0e6
Revises: e5f6a7b8c9d5
Create Date: 2026-07-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f6a7b8c9d0e6'
down_revision: Union[str, None] = 'e5f6a7b8c9d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_reasoning_graphs',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('plan_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='building'),
        sa.Column('root_node_id', sa.Text(), nullable=False),
        sa.Column('graph', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_copilot_reasoning_company_time', 'copilot_reasoning_graphs', ['company_id', sa.text('created_at DESC')])
    op.create_index('idx_copilot_reasoning_conversation', 'copilot_reasoning_graphs', ['conversation_id'])
    op.create_index('idx_copilot_reasoning_graph_gin', 'copilot_reasoning_graphs', ['graph'], postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('idx_copilot_reasoning_graph_gin', table_name='copilot_reasoning_graphs', postgresql_using='gin')
    op.drop_index('idx_copilot_reasoning_conversation', table_name='copilot_reasoning_graphs')
    op.drop_index('idx_copilot_reasoning_company_time', table_name='copilot_reasoning_graphs')
    op.drop_table('copilot_reasoning_graphs')
