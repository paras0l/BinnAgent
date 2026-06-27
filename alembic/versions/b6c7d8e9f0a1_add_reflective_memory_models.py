"""add reflective memory models

Revision ID: b6c7d8e9f0a1
Revises: 85d6e7f8a9b0
Create Date: 2026-06-27 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "85d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_episodes",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("reflection_key", sa.String(length=255), nullable=False),
        sa.Column("episode_type", sa.String(length=80), nullable=False),
        sa.Column("skill", sa.String(length=50), nullable=False),
        sa.Column("subskill", sa.String(length=80), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("observed_patterns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("source_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "reflection_key", name="uq_learning_episode_reflection_key"),
    )
    op.create_index("ix_learning_episodes_episode_type", "learning_episodes", ["episode_type"])
    op.create_index("ix_learning_episodes_learner_id", "learning_episodes", ["learner_id"])
    op.create_index(
        "ix_learning_episodes_learner_created",
        "learning_episodes",
        ["learner_id", "created_at"],
    )
    op.create_index(
        "ix_learning_episodes_learner_skill",
        "learning_episodes",
        ["learner_id", "skill", "subskill"],
    )
    op.create_index("ix_learning_episodes_session_id", "learning_episodes", ["session_id"])

    op.create_table(
        "learner_model_memories",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("model_type", sa.String(length=80), nullable=False),
        sa.Column("skill", sa.String(length=50), nullable=False),
        sa.Column("subskill", sa.String(length=80), nullable=True),
        sa.Column("claim_key", sa.String(length=160), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_reflected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learner_id",
            "model_type",
            "skill",
            "subskill",
            "claim_key",
            name="uq_learner_model_memory_claim",
        ),
    )
    op.create_index("ix_learner_model_memories_learner_id", "learner_model_memories", ["learner_id"])
    op.create_index(
        "ix_learner_model_memories_learner_skill",
        "learner_model_memories",
        ["learner_id", "skill", "subskill"],
    )
    op.create_index(
        "ix_learner_model_memories_learner_status",
        "learner_model_memories",
        ["learner_id", "status"],
    )

    op.create_table(
        "teaching_strategy_memories",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("strategy", sa.String(length=120), nullable=False),
        sa.Column("skill", sa.String(length=50), nullable=False),
        sa.Column("subskill", sa.String(length=80), nullable=True),
        sa.Column("when_to_use", sa.Text(), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effect_summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "strategy", "skill", name="uq_teaching_strategy_memory"),
    )
    op.create_index(
        "ix_teaching_strategy_memories_learner_id",
        "teaching_strategy_memories",
        ["learner_id"],
    )
    op.create_index(
        "ix_teaching_strategy_memories_learner_skill",
        "teaching_strategy_memories",
        ["learner_id", "skill", "subskill"],
    )
    op.create_index(
        "ix_teaching_strategy_memories_learner_status",
        "teaching_strategy_memories",
        ["learner_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_teaching_strategy_memories_learner_status", table_name="teaching_strategy_memories")
    op.drop_index("ix_teaching_strategy_memories_learner_skill", table_name="teaching_strategy_memories")
    op.drop_index("ix_teaching_strategy_memories_learner_id", table_name="teaching_strategy_memories")
    op.drop_table("teaching_strategy_memories")
    op.drop_index("ix_learner_model_memories_learner_status", table_name="learner_model_memories")
    op.drop_index("ix_learner_model_memories_learner_skill", table_name="learner_model_memories")
    op.drop_index("ix_learner_model_memories_learner_id", table_name="learner_model_memories")
    op.drop_table("learner_model_memories")
    op.drop_index("ix_learning_episodes_session_id", table_name="learning_episodes")
    op.drop_index("ix_learning_episodes_learner_skill", table_name="learning_episodes")
    op.drop_index("ix_learning_episodes_learner_created", table_name="learning_episodes")
    op.drop_index("ix_learning_episodes_learner_id", table_name="learning_episodes")
    op.drop_index("ix_learning_episodes_episode_type", table_name="learning_episodes")
    op.drop_table("learning_episodes")
