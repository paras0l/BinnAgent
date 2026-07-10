"""add persistent exercise generation pool

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-07-09 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, Sequence[str], None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exercise_questions",
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.72"),
    )
    op.add_column(
        "exercise_questions",
        sa.Column("quality_status", sa.String(length=20), nullable=False, server_default="accepted"),
    )
    op.add_column(
        "exercise_questions",
        sa.Column("generator_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "exercise_questions",
        sa.Column("quality_dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        """
        UPDATE exercise_questions
        SET generator_version = COALESCE(metadata ->> 'generator_version', 'curated-v1')
        WHERE generator_version IS NULL
        """
    )
    op.alter_column(
        "exercise_questions",
        "generator_version",
        nullable=False,
        server_default="curated-v1",
    )
    op.create_index(
        "ix_exercise_questions_quality_score",
        "exercise_questions",
        ["quality_score"],
    )
    op.create_index(
        "ix_exercise_questions_quality_status",
        "exercise_questions",
        ["quality_status"],
    )
    op.create_index(
        "ix_exercise_questions_generator_version",
        "exercise_questions",
        ["generator_version"],
    )

    op.create_table(
        "exercise_generation_runs",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("generator_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("requested_count", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.ForeignKeyConstraint(
            ["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_learner_id"], ["learners.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exercise_generation_runs_source_id",
        "exercise_generation_runs",
        ["source_id"],
    )
    op.create_index(
        "ix_exercise_generation_runs_curriculum_node_id",
        "exercise_generation_runs",
        ["curriculum_node_id"],
    )
    op.create_index(
        "ix_exercise_generation_runs_requested_by_learner_id",
        "exercise_generation_runs",
        ["requested_by_learner_id"],
    )
    op.create_index(
        "ix_exercise_generation_runs_input_hash",
        "exercise_generation_runs",
        ["input_hash"],
    )
    op.create_index(
        "ix_exercise_generation_runs_generator_version",
        "exercise_generation_runs",
        ["generator_version"],
    )
    op.create_index(
        "ix_exercise_generation_runs_status",
        "exercise_generation_runs",
        ["status"],
    )
    op.create_index(
        "ix_exercise_generation_runs_claim",
        "exercise_generation_runs",
        ["status", "priority", "created_at"],
    )
    op.create_index(
        "uq_exercise_generation_runs_active_dedupe",
        "exercise_generation_runs",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_table("exercise_generation_runs")
    op.drop_index("ix_exercise_questions_generator_version", table_name="exercise_questions")
    op.drop_index("ix_exercise_questions_quality_status", table_name="exercise_questions")
    op.drop_index("ix_exercise_questions_quality_score", table_name="exercise_questions")
    op.drop_column("exercise_questions", "quality_dimensions")
    op.drop_column("exercise_questions", "generator_version")
    op.drop_column("exercise_questions", "quality_status")
    op.drop_column("exercise_questions", "quality_score")
