"""add writing phrases

Revision ID: 63b4c5d6e7f8
Revises: 52a3b4c5d6e7
Create Date: 2026-06-26 16:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "63b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "52a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "writing_phrases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("chinese_meaning", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("usage_scene", sa.Text(), nullable=True),
        sa.Column("usage_position", sa.String(length=50), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("examples", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("mistakes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(length=500), nullable=True),
        sa.Column("source_raw_text", sa.Text(), nullable=True),
        sa.Column("register_level", sa.String(length=30), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_writing_phrases_learner_archived", "writing_phrases", ["learner_id", "is_archived"])
    op.create_index("ix_writing_phrases_learner_favorite", "writing_phrases", ["learner_id", "is_favorite"])
    op.create_index("ix_writing_phrases_learner_review", "writing_phrases", ["learner_id", "review_enabled"])

    op.create_table(
        "writing_phrase_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phrase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercise_type", sa.String(length=30), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phrase_id"], ["writing_phrases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_writing_phrase_exercises_learner_id", "writing_phrase_exercises", ["learner_id"])
    op.create_index("ix_writing_phrase_exercises_phrase_id", "writing_phrase_exercises", ["phrase_id"])

    op.create_table(
        "writing_phrase_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phrase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercise_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exercise_type", sa.String(length=30), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phrase_id"], ["writing_phrases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["writing_phrase_exercises.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_writing_phrase_attempts_learner_id", "writing_phrase_attempts", ["learner_id"])
    op.create_index("ix_writing_phrase_attempts_phrase_id", "writing_phrase_attempts", ["phrase_id"])
    op.create_index("ix_writing_phrase_attempts_exercise_id", "writing_phrase_attempts", ["exercise_id"])
    op.create_index("ix_writing_phrase_attempts_learner_phrase", "writing_phrase_attempts", ["learner_id", "phrase_id"])


def downgrade() -> None:
    op.drop_index("ix_writing_phrase_attempts_learner_phrase", table_name="writing_phrase_attempts")
    op.drop_index("ix_writing_phrase_attempts_exercise_id", table_name="writing_phrase_attempts")
    op.drop_index("ix_writing_phrase_attempts_phrase_id", table_name="writing_phrase_attempts")
    op.drop_index("ix_writing_phrase_attempts_learner_id", table_name="writing_phrase_attempts")
    op.drop_table("writing_phrase_attempts")
    op.drop_index("ix_writing_phrase_exercises_phrase_id", table_name="writing_phrase_exercises")
    op.drop_index("ix_writing_phrase_exercises_learner_id", table_name="writing_phrase_exercises")
    op.drop_table("writing_phrase_exercises")
    op.drop_index("ix_writing_phrases_learner_review", table_name="writing_phrases")
    op.drop_index("ix_writing_phrases_learner_favorite", table_name="writing_phrases")
    op.drop_index("ix_writing_phrases_learner_archived", table_name="writing_phrases")
    op.drop_table("writing_phrases")
