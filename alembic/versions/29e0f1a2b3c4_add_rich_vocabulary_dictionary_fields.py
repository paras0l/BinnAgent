"""add rich vocabulary dictionary fields

Revision ID: 29e0f1a2b3c4
Revises: 18d9e0f1a2b3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "29e0f1a2b3c4"
down_revision: str | None = "18d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vocabulary_items", sa.Column("phonetic_uk", sa.String(255)))
    op.add_column("vocabulary_items", sa.Column("phonetic_us", sa.String(255)))
    op.add_column(
        "vocabulary_items",
        sa.Column("dictionary_senses", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "vocabulary_items", sa.Column("word_forms", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "vocabulary_items", sa.Column("dictionary_tags", postgresql.JSONB(), nullable=True)
    )
    op.execute("UPDATE vocabulary_items SET dictionary_senses='[]'::jsonb WHERE dictionary_senses IS NULL")
    op.execute("UPDATE vocabulary_items SET word_forms='{}'::jsonb WHERE word_forms IS NULL")
    op.execute("UPDATE vocabulary_items SET dictionary_tags='[]'::jsonb WHERE dictionary_tags IS NULL")


def downgrade() -> None:
    op.drop_column("vocabulary_items", "dictionary_tags")
    op.drop_column("vocabulary_items", "word_forms")
    op.drop_column("vocabulary_items", "dictionary_senses")
    op.drop_column("vocabulary_items", "phonetic_us")
    op.drop_column("vocabulary_items", "phonetic_uk")
