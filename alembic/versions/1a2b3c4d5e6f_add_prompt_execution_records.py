"""add prompt execution records

Revision ID: 1a2b3c4d5e6f
Revises: f0a1b2c3d4e5
Create Date: 2026-07-03 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_execution_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("source_module", sa.String(length=120), nullable=False),
        sa.Column("prompt_id", sa.String(length=160), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input_schema", sa.String(length=160), nullable=True),
        sa.Column("output_schema", sa.String(length=160), nullable=True),
        sa.Column(
            "model_policy_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("langfuse_trace_id", sa.String(length=255), nullable=True),
        sa.Column("langfuse_observation_id", sa.String(length=255), nullable=True),
        sa.Column("schema_validation_status", sa.String(length=30), nullable=False),
        sa.Column("schema_error_summary", sa.Text(), nullable=True),
        sa.Column("repair_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("parse_mode", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["agent_episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prompt_execution_records_prompt",
        "prompt_execution_records",
        ["prompt_id", "prompt_version"],
    )
    op.create_index(
        "ix_prompt_execution_records_learner_created",
        "prompt_execution_records",
        ["learner_id", "created_at"],
    )
    op.create_index(
        "ix_prompt_execution_records_episode_id",
        "prompt_execution_records",
        ["episode_id"],
    )
    op.create_index(
        "ix_prompt_execution_records_source_module",
        "prompt_execution_records",
        ["source_module"],
    )
    op.create_index(
        "ix_prompt_execution_records_decision",
        "prompt_execution_records",
        ["decision"],
    )
    op.create_index(
        "ix_prompt_execution_records_schema_validation_status",
        "prompt_execution_records",
        ["schema_validation_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prompt_execution_records_schema_validation_status",
        table_name="prompt_execution_records",
    )
    op.drop_index("ix_prompt_execution_records_decision", table_name="prompt_execution_records")
    op.drop_index("ix_prompt_execution_records_source_module", table_name="prompt_execution_records")
    op.drop_index("ix_prompt_execution_records_episode_id", table_name="prompt_execution_records")
    op.drop_index("ix_prompt_execution_records_learner_created", table_name="prompt_execution_records")
    op.drop_index("ix_prompt_execution_records_prompt", table_name="prompt_execution_records")
    op.drop_table("prompt_execution_records")
