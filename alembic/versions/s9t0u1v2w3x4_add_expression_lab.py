"""add expression lab sessions and activity tables

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-07-10 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def upgrade() -> None:
    created_at, updated_at = _timestamps()
    op.create_table(
        "expression_lab_sessions",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "source_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("input_type", sa.String(length=40), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("context", sa.String(length=80), nullable=True),
        sa.Column("style_goal", sa.String(length=80), nullable=True),
        sa.Column("current_level", sa.String(length=40), nullable=True),
        sa.Column("needs_practice", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="generating"),
        sa.Column(
            "ui_spec_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "grading_spec_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "diagnostics_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("model_id", sa.String(length=160), nullable=True),
        sa.Column("prompt_id", sa.String(length=160), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("generation_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _id_column(),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_expression_lab_sessions_learner_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["agent_episodes.id"],
            name="fk_expression_lab_sessions_episode_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expression_lab_sessions_learner_id", "expression_lab_sessions", ["learner_id"])
    op.create_index("ix_expression_lab_sessions_episode_id", "expression_lab_sessions", ["episode_id"])
    op.create_index(
        "ix_expression_lab_sessions_learner_status",
        "expression_lab_sessions",
        ["learner_id", "status"],
    )
    op.create_index(
        "ix_expression_lab_sessions_learner_updated",
        "expression_lab_sessions",
        ["learner_id", "updated_at"],
    )
    op.create_index(
        "ix_expression_lab_sessions_source_ref",
        "expression_lab_sessions",
        ["source_type", "source_ref"],
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "expression_lab_actions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_id", sa.String(length=120), nullable=True),
        sa.Column("spec_action_id", sa.String(length=120), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "editable_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("confirmed_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("applied_target_type", sa.String(length=80), nullable=True),
        sa.Column("applied_target_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        _id_column(),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["expression_lab_sessions.id"],
            name="fk_expression_lab_actions_session_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "spec_action_id", name="uq_expression_lab_action_session_spec"
        ),
    )
    op.create_index("ix_expression_lab_actions_session_id", "expression_lab_actions", ["session_id"])
    op.create_index(
        "ix_expression_lab_actions_session_status",
        "expression_lab_actions",
        ["session_id", "status"],
    )
    op.create_index(
        "ix_expression_lab_actions_session_block",
        "expression_lab_actions",
        ["session_id", "block_id"],
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "expression_lab_attempts",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercise_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("block_id", sa.String(length=120), nullable=False),
        sa.Column("question_id", sa.String(length=120), nullable=False),
        sa.Column(
            "answer_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "feedback_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "next_recommendations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        _id_column(),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["expression_lab_sessions.id"],
            name="fk_expression_lab_attempts_session_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exercise_attempt_id"],
            ["exercise_attempts.id"],
            name="fk_expression_lab_attempts_exercise_attempt_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "block_id",
            "question_id",
            "attempt_number",
            name="uq_expression_lab_attempt_sequence",
        ),
    )
    op.create_index("ix_expression_lab_attempts_session_id", "expression_lab_attempts", ["session_id"])
    op.create_index(
        "ix_expression_lab_attempts_exercise_attempt_id",
        "expression_lab_attempts",
        ["exercise_attempt_id"],
    )
    op.create_index(
        "ix_expression_lab_attempts_session_question",
        "expression_lab_attempts",
        ["session_id", "question_id"],
    )

    op.create_table(
        "expression_lab_events",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        _id_column(),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["expression_lab_sessions.id"],
            name="fk_expression_lab_events_session_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expression_lab_events_session_id", "expression_lab_events", ["session_id"])
    op.create_index(
        "ix_expression_lab_events_session_occurred",
        "expression_lab_events",
        ["session_id", "occurred_at"],
    )
    op.create_index(
        "ix_expression_lab_events_session_type",
        "expression_lab_events",
        ["session_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_expression_lab_events_session_type", table_name="expression_lab_events")
    op.drop_index("ix_expression_lab_events_session_occurred", table_name="expression_lab_events")
    op.drop_index("ix_expression_lab_events_session_id", table_name="expression_lab_events")
    op.drop_table("expression_lab_events")
    op.drop_index(
        "ix_expression_lab_attempts_session_question", table_name="expression_lab_attempts"
    )
    op.drop_index(
        "ix_expression_lab_attempts_exercise_attempt_id", table_name="expression_lab_attempts"
    )
    op.drop_index("ix_expression_lab_attempts_session_id", table_name="expression_lab_attempts")
    op.drop_table("expression_lab_attempts")
    op.drop_index("ix_expression_lab_actions_session_block", table_name="expression_lab_actions")
    op.drop_index("ix_expression_lab_actions_session_status", table_name="expression_lab_actions")
    op.drop_index("ix_expression_lab_actions_session_id", table_name="expression_lab_actions")
    op.drop_table("expression_lab_actions")
    op.drop_index("ix_expression_lab_sessions_source_ref", table_name="expression_lab_sessions")
    op.drop_index("ix_expression_lab_sessions_learner_updated", table_name="expression_lab_sessions")
    op.drop_index("ix_expression_lab_sessions_learner_status", table_name="expression_lab_sessions")
    op.drop_index("ix_expression_lab_sessions_episode_id", table_name="expression_lab_sessions")
    op.drop_index("ix_expression_lab_sessions_learner_id", table_name="expression_lab_sessions")
    op.drop_table("expression_lab_sessions")
