"""create freight_exchange_connections

Revision ID: a1b2c3d4e5f1
Revises: None
Create Date: 2026-07-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'freight_exchange_connections',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('provider_id', sa.String(), nullable=False),
        sa.Column('credentials_encrypted', sa.Text(), nullable=False),
        sa.Column('session_state', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='disconnected'),
        sa.Column('last_health_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_health_check_status', sa.String(), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('company_id', 'provider_id'),
    )
    op.create_index('idx_freight_connections_company', 'freight_exchange_connections', ['company_id'])


def downgrade() -> None:
    op.drop_index('idx_freight_connections_company', table_name='freight_exchange_connections')
    op.drop_table('freight_exchange_connections')
