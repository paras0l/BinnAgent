"""add agent episode runtime

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-07-02 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_episodes",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("entrypoint", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("task_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("memory_context_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rag_chunk_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_call_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("verification_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_type", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_episodes_learner_id", "agent_episodes", ["learner_id"])
    op.create_index("ix_agent_episodes_source", "agent_episodes", ["source"])
    op.create_index("ix_agent_episodes_status", "agent_episodes", ["status"])

    op.create_table(
        "learning_events",
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("source_module", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["agent_episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_events_episode_id", "learning_events", ["episode_id"])
    op.create_index("ix_learning_events_learner_id", "learning_events", ["learner_id"])
    op.create_index("ix_learning_events_event_type", "learning_events", ["event_type"])

    op.create_table(
        "tool_call_records",
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["agent_episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_call_records_episode_id", "tool_call_records", ["episode_id"])
    op.create_index("ix_tool_call_records_tool_name", "tool_call_records", ["tool_name"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_records_tool_name", table_name="tool_call_records")
    op.drop_index("ix_tool_call_records_episode_id", table_name="tool_call_records")
    op.drop_table("tool_call_records")
    op.drop_index("ix_learning_events_event_type", table_name="learning_events")
    op.drop_index("ix_learning_events_learner_id", table_name="learning_events")
    op.drop_index("ix_learning_events_episode_id", table_name="learning_events")
    op.drop_table("learning_events")
    op.drop_index("ix_agent_episodes_status", table_name="agent_episodes")
    op.drop_index("ix_agent_episodes_source", table_name="agent_episodes")
    op.drop_index("ix_agent_episodes_learner_id", table_name="agent_episodes")
    op.drop_table("agent_episodes")
