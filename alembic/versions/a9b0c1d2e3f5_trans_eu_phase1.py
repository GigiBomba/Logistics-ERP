"""Trans.eu Phase 1 — user tokens, freight offers, webhook tables.

Revision ID: a9b0c1d2e3f5
Revises: f6a7b8c9d0e6
Create Date: 2026-07-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a9b0c1d2e3f5'
down_revision: Union[str, None] = 'f6a7b8c9d0e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add user_id column to freight_exchange_connections
    op.add_column(
        'freight_exchange_connections',
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
    )

    # 2. Create trans_eu_user_tokens — per-user OAuth token storage
    op.create_table(
        'trans_eu_user_tokens',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('trans_eu_account_id', sa.String(), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False, server_default=''),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False, server_default=''),
        sa.Column('client_secret_encrypted', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('company_id', 'user_id'),
    )

    # 3. Create trans_eu_freight_offers — freight object tracking
    op.create_table(
        'trans_eu_freight_offers',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('trans_eu_freight_id', sa.Integer(), nullable=False),
        sa.Column('trans_eu_reference_number', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('publication_status', sa.String(), nullable=True),
        sa.Column('publication_type', sa.String(), nullable=True),
        sa.Column('origin', sa.String(), nullable=False),
        sa.Column('destination', sa.String(), nullable=False),
        sa.Column('pickup_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pickup_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('price_amount', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('price_currency', sa.String(), nullable=True, server_default='EUR'),
        sa.Column('distance_km', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('trailer_type', sa.String(), nullable=True),
        sa.Column('adr', sa.Boolean(), nullable=True, server_default=sa.text('FALSE')),
        sa.Column('weight_kg', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('externally_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('operion_trip_id', sa.BigInteger(), sa.ForeignKey('trips.id'), nullable=True),
        sa.Column('trans_eu_order_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_trans_eu_freight_offers_company', 'trans_eu_freight_offers', ['company_id'])
    op.create_index('idx_trans_eu_freight_offers_freight_id', 'trans_eu_freight_offers', ['trans_eu_freight_id'])

    # 4. Create trans_eu_webhook_events — idempotency table
    op.create_table(
        'trans_eu_webhook_events',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('trans_eu_event_id', sa.String(), nullable=False),
        sa.Column('event_name', sa.String(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='received'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('trans_eu_event_id'),
    )

    # 5. Create trans_eu_webhook_events_failed — dead letter queue
    op.create_table(
        'trans_eu_webhook_events_failed',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.BigInteger(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('trans_eu_event_id', sa.String(), nullable=False),
        sa.Column('event_name', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('error_type', sa.String(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('trans_eu_webhook_events_failed')
    op.drop_table('trans_eu_webhook_events')
    op.drop_index('idx_trans_eu_freight_offers_freight_id', table_name='trans_eu_freight_offers')
    op.drop_index('idx_trans_eu_freight_offers_company', table_name='trans_eu_freight_offers')
    op.drop_table('trans_eu_freight_offers')
    op.drop_table('trans_eu_user_tokens')
    op.drop_column('freight_exchange_connections', 'user_id')
