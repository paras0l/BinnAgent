"""add learning graph checkpoints

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-07-02 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_graph_checkpoints",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(length=120), nullable=True),
        sa.Column("checkpoint_key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("resume_from", sa.String(length=120), nullable=True),
        sa.Column("state_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("required_input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["agent_episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_graph_checkpoints_learner_id",
        "learning_graph_checkpoints",
        ["learner_id"],
    )
    op.create_index(
        "ix_learning_graph_checkpoints_episode_id",
        "learning_graph_checkpoints",
        ["episode_id"],
    )
    op.create_index(
        "ix_learning_graph_checkpoints_checkpoint_key",
        "learning_graph_checkpoints",
        ["checkpoint_key"],
    )
    op.create_index(
        "ix_learning_graph_checkpoints_status",
        "learning_graph_checkpoints",
        ["status"],
    )
    op.create_index(
        "uq_learning_graph_checkpoints_active_waiting_episode",
        "learning_graph_checkpoints",
        ["episode_id"],
        unique=True,
        postgresql_where=sa.text("status = 'waiting_user'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_learning_graph_checkpoints_active_waiting_episode",
        table_name="learning_graph_checkpoints",
    )
    op.drop_index("ix_learning_graph_checkpoints_status", table_name="learning_graph_checkpoints")
    op.drop_index(
        "ix_learning_graph_checkpoints_checkpoint_key",
        table_name="learning_graph_checkpoints",
    )
    op.drop_index("ix_learning_graph_checkpoints_episode_id", table_name="learning_graph_checkpoints")
    op.drop_index("ix_learning_graph_checkpoints_learner_id", table_name="learning_graph_checkpoints")
    op.drop_table("learning_graph_checkpoints")
