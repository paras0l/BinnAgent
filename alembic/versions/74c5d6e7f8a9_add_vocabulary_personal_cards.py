"""add vocabulary personal cards

Revision ID: 74c5d6e7f8a9
Revises: 63b4c5d6e7f8
Create Date: 2026-06-26 18:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "74c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "63b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.add_column("vocabulary_item_sources", sa.Column("reason", sa.String(80), nullable=True))
    op.add_column(
        "vocabulary_item_sources",
        sa.Column("priority", sa.Float(), nullable=False, server_default="0.5"),
    )

    op.create_table(
        "vocabulary_user_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vocabulary_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_form_override", sa.String(255), nullable=True),
        sa.Column(
            "meaning_overrides",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "hidden_meaning_ids",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("user_understanding", sa.Text(), nullable=True),
        sa.Column(
            "user_examples",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "user_collocations",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("preferred_accent", sa.String(10), nullable=False, server_default="auto"),
        sa.Column("review_preference", sa.String(30), nullable=False, server_default="normal"),
        sa.Column("excluded_from_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manual_mastery", sa.String(30), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"], ["vocabulary_items.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "vocabulary_item_id", "learner_id", name="uq_vocabulary_override_item_learner"
        ),
    )
    op.create_index(
        "ix_vocabulary_user_overrides_learner_id",
        "vocabulary_user_overrides",
        ["learner_id"],
    )
    op.create_index(
        "ix_vocabulary_user_overrides_vocabulary_item_id",
        "vocabulary_user_overrides",
        ["vocabulary_item_id"],
    )
    op.create_index(
        "ix_vocabulary_overrides_learner_item",
        "vocabulary_user_overrides",
        ["learner_id", "vocabulary_item_id"],
    )

    op.create_table(
        "vocabulary_mastery_vectors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vocabulary_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recognition", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recall", sa.Float(), nullable=False, server_default="0"),
        sa.Column("spelling", sa.Float(), nullable=False, server_default="0"),
        sa.Column("listening", sa.Float(), nullable=False, server_default="0"),
        sa.Column("context_use", sa.Float(), nullable=False, server_default="0"),
        sa.Column("production", sa.Float(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"], ["vocabulary_items.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "vocabulary_item_id", "learner_id", name="uq_vocabulary_mastery_item_learner"
        ),
    )
    op.create_index(
        "ix_vocabulary_mastery_vectors_learner_id",
        "vocabulary_mastery_vectors",
        ["learner_id"],
    )
    op.create_index(
        "ix_vocabulary_mastery_vectors_vocabulary_item_id",
        "vocabulary_mastery_vectors",
        ["vocabulary_item_id"],
    )
    op.create_index(
        "ix_vocabulary_mastery_learner_item",
        "vocabulary_mastery_vectors",
        ["learner_id", "vocabulary_item_id"],
    )

    op.create_table(
        "vocabulary_mistakes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vocabulary_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mistake_type", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vocabulary_item_id"], ["vocabulary_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["vocabulary_attempts.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_vocabulary_mistakes_learner_id", "vocabulary_mistakes", ["learner_id"])
    op.create_index(
        "ix_vocabulary_mistakes_vocabulary_item_id",
        "vocabulary_mistakes",
        ["vocabulary_item_id"],
    )
    op.create_index("ix_vocabulary_mistakes_attempt_id", "vocabulary_mistakes", ["attempt_id"])
    op.create_index(
        "ix_vocabulary_mistakes_learner_item",
        "vocabulary_mistakes",
        ["learner_id", "vocabulary_item_id"],
    )
    op.create_index(
        "ix_vocabulary_mistakes_active",
        "vocabulary_mistakes",
        ["learner_id", "active"],
    )


def downgrade() -> None:
    op.drop_table("vocabulary_mistakes")
    op.drop_table("vocabulary_mastery_vectors")
    op.drop_table("vocabulary_user_overrides")
    op.drop_column("vocabulary_item_sources", "priority")
    op.drop_column("vocabulary_item_sources", "reason")
