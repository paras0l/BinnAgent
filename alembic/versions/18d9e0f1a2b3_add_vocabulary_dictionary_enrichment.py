"""add vocabulary dictionary enrichment metadata

Revision ID: 18d9e0f1a2b3
Revises: 07c8d9e0f1a2
Create Date: 2026-06-21 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "18d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "07c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vocabulary_items",
        sa.Column("dictionary_provider", sa.String(80), nullable=True),
    )
    op.add_column(
        "vocabulary_items",
        sa.Column("dictionary_enriched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("""
        UPDATE vocabulary_items AS item
        SET dictionary_provider = source.context_snapshot->>'dictionary_provider',
            dictionary_enriched_at = now()
        FROM vocabulary_item_sources AS source
        WHERE source.vocabulary_item_id = item.id
          AND source.context_snapshot->>'dictionary_provider' IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("vocabulary_items", "dictionary_enriched_at")
    op.drop_column("vocabulary_items", "dictionary_provider")
