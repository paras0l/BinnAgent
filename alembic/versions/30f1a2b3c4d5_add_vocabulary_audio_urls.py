"""add vocabulary audio urls

Revision ID: 30f1a2b3c4d5
Revises: 29e0f1a2b3c4
Create Date: 2026-06-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "30f1a2b3c4d5"
down_revision: str | None = "29e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vocabulary_items", sa.Column("audio_url", sa.String(500), nullable=True))
    op.add_column("vocabulary_items", sa.Column("audio_uk", sa.String(500), nullable=True))
    op.add_column("vocabulary_items", sa.Column("audio_us", sa.String(500), nullable=True))
    op.execute(
        """
        UPDATE vocabulary_items
        SET phonetic = NULL,
            phonetic_uk = NULL,
            phonetic_us = NULL,
            meanings = '[]'::jsonb,
            dictionary_senses = '[]'::jsonb,
            word_forms = '{}'::jsonb,
            dictionary_tags = '[]'::jsonb,
            collocations = '[]'::jsonb,
            examples = '[]'::jsonb,
            dictionary_provider = NULL,
            dictionary_enriched_at = NULL
        WHERE dictionary_provider ILIKE '%baidu%'
        """
    )
    op.execute(
        """
        UPDATE vocabulary_item_sources
        SET context_snapshot = context_snapshot - 'dictionary_provider'
        WHERE context_snapshot->>'dictionary_provider' ILIKE '%baidu%'
        """
    )


def downgrade() -> None:
    op.drop_column("vocabulary_items", "audio_us")
    op.drop_column("vocabulary_items", "audio_uk")
    op.drop_column("vocabulary_items", "audio_url")
