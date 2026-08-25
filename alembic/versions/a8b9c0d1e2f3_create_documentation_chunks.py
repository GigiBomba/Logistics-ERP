"""create documentation_chunks

Revision ID: a8b9c0d1e2f3
Revises: a7b8c9d0e1f7
Create Date: 2026-07-16
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'a7b8c9d0e1f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documentation_chunks',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('article_id', sa.Text(), nullable=False),
        sa.Column('title_key', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('language', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),  # placeholder for pgvector; TEXT until extension is enabled
        sa.Column('corpus_version', sa.Text(), nullable=False, server_default='1.0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_doc_chunks_lang', 'documentation_chunks', ['language'])
    op.create_index('idx_doc_chunks_article', 'documentation_chunks', ['article_id'])


def downgrade() -> None:
    op.drop_index('idx_doc_chunks_article', table_name='documentation_chunks')
    op.drop_index('idx_doc_chunks_lang', table_name='documentation_chunks')
    op.drop_table('documentation_chunks')
