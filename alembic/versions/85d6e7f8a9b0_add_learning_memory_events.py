"""add learning memory events

Revision ID: 85d6e7f8a9b0
Revises: 74c5d6e7f8a9
Create Date: 2026-06-26 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "85d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "74c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("error_patterns", sa.Column("subskill", sa.String(length=80), nullable=True))
    op.add_column(
        "error_patterns",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "error_patterns",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
    )
    op.add_column(
        "error_patterns", sa.Column("last_intervention", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "error_patterns",
        sa.Column(
            "intervention_effectiveness",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "error_patterns",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE error_patterns SET first_seen_at = COALESCE(last_seen_at, created_at)")
    op.alter_column("error_patterns", "confidence", server_default=None)
    op.alter_column("error_patterns", "status", server_default=None)

    op.create_table(
        "learning_memory_events",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("skill", sa.String(length=50), nullable=False),
        sa.Column("subskill", sa.String(length=80), nullable=True),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("thread_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("visibility", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_threads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_memory_events_event_type", "learning_memory_events", ["event_type"])
    op.create_index("ix_learning_memory_events_learner_id", "learning_memory_events", ["learner_id"])
    op.create_index(
        "ix_learning_memory_events_learner_occurred",
        "learning_memory_events",
        ["learner_id", "occurred_at"],
    )
    op.create_index(
        "ix_learning_memory_events_learner_skill",
        "learning_memory_events",
        ["learner_id", "skill", "subskill"],
    )
    op.create_index(
        "ix_learning_memory_events_session_id", "learning_memory_events", ["session_id"]
    )
    op.create_index(
        "ix_learning_memory_events_source",
        "learning_memory_events",
        ["source_type", "source_id"],
    )
    op.create_index("ix_learning_memory_events_thread_id", "learning_memory_events", ["thread_id"])

    op.create_table(
        "memory_operations",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_operations_learner_id", "memory_operations", ["learner_id"])
    op.create_index(
        "ix_memory_operations_learner_created", "memory_operations", ["learner_id", "created_at"]
    )
    op.create_index("ix_memory_operations_target", "memory_operations", ["target_type", "target_id"])

    op.create_table(
        "writing_phrase_masteries",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("phrase_id", sa.UUID(), nullable=False),
        sa.Column("skill", sa.String(length=50), nullable=False),
        sa.Column("subskill", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("recognition", sa.Float(), nullable=False),
        sa.Column("recall", sa.Float(), nullable=False),
        sa.Column("context_use", sa.Float(), nullable=False),
        sa.Column("production", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recommended_drill", sa.String(length=100), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phrase_id"], ["writing_phrases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "phrase_id", name="uq_writing_phrase_mastery_learner_phrase"),
    )
    op.create_index("ix_writing_phrase_masteries_learner_id", "writing_phrase_masteries", ["learner_id"])
    op.create_index(
        "ix_writing_phrase_masteries_learner_status",
        "writing_phrase_masteries",
        ["learner_id", "status"],
    )
    op.create_index("ix_writing_phrase_masteries_phrase_id", "writing_phrase_masteries", ["phrase_id"])

    op.create_table(
        "memory_context_logs",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.UUID(), nullable=True),
        sa.Column("retrieval_reason", sa.String(length=80), nullable=False),
        sa.Column("loaded_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("excluded_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_cost", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_threads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_context_logs_learner_id", "memory_context_logs", ["learner_id"])
    op.create_index(
        "ix_memory_context_logs_learner_created",
        "memory_context_logs",
        ["learner_id", "created_at"],
    )
    op.create_index("ix_memory_context_logs_reason", "memory_context_logs", ["retrieval_reason"])
    op.create_index("ix_memory_context_logs_thread_id", "memory_context_logs", ["thread_id"])

    op.create_table(
        "learner_memory_settings",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("emotion_rhythm_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("inferred_preferences_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("low_confidence_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", name="uq_learner_memory_settings_learner"),
    )
    op.create_index("ix_learner_memory_settings_learner_id", "learner_memory_settings", ["learner_id"])


def downgrade() -> None:
    op.drop_index("ix_learner_memory_settings_learner_id", table_name="learner_memory_settings")
    op.drop_table("learner_memory_settings")
    op.drop_index("ix_memory_context_logs_thread_id", table_name="memory_context_logs")
    op.drop_index("ix_memory_context_logs_reason", table_name="memory_context_logs")
    op.drop_index("ix_memory_context_logs_learner_created", table_name="memory_context_logs")
    op.drop_index("ix_memory_context_logs_learner_id", table_name="memory_context_logs")
    op.drop_table("memory_context_logs")
    op.drop_index("ix_writing_phrase_masteries_phrase_id", table_name="writing_phrase_masteries")
    op.drop_index("ix_writing_phrase_masteries_learner_status", table_name="writing_phrase_masteries")
    op.drop_index("ix_writing_phrase_masteries_learner_id", table_name="writing_phrase_masteries")
    op.drop_table("writing_phrase_masteries")
    op.drop_index("ix_memory_operations_target", table_name="memory_operations")
    op.drop_index("ix_memory_operations_learner_created", table_name="memory_operations")
    op.drop_index("ix_memory_operations_learner_id", table_name="memory_operations")
    op.drop_table("memory_operations")
    op.drop_index("ix_learning_memory_events_thread_id", table_name="learning_memory_events")
    op.drop_index("ix_learning_memory_events_source", table_name="learning_memory_events")
    op.drop_index("ix_learning_memory_events_session_id", table_name="learning_memory_events")
    op.drop_index("ix_learning_memory_events_learner_skill", table_name="learning_memory_events")
    op.drop_index("ix_learning_memory_events_learner_occurred", table_name="learning_memory_events")
    op.drop_index("ix_learning_memory_events_learner_id", table_name="learning_memory_events")
    op.drop_index("ix_learning_memory_events_event_type", table_name="learning_memory_events")
    op.drop_table("learning_memory_events")
    op.drop_column("error_patterns", "first_seen_at")
    op.drop_column("error_patterns", "intervention_effectiveness")
    op.drop_column("error_patterns", "last_intervention")
    op.drop_column("error_patterns", "status")
    op.drop_column("error_patterns", "confidence")
    op.drop_column("error_patterns", "subskill")
