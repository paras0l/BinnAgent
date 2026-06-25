"""add textbook rag chunks and exercises

Revision ID: 41a2b3c4d5e6
Revises: 30f1a2b3c4d5
Create Date: 2026-06-25 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "41a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "30f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(150), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunk_source_index"),
    )
    op.create_index("ix_knowledge_chunks_source_id", "knowledge_chunks", ["source_id"])
    op.create_index(
        "ix_knowledge_chunks_curriculum_node_id", "knowledge_chunks", ["curriculum_node_id"]
    )
    op.create_index("ix_knowledge_chunks_page_number", "knowledge_chunks", ["page_number"])
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "exercise_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_type", sa.String(30), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column(
            "options", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_exercise_questions_source_id", "exercise_questions", ["source_id"])
    op.create_index(
        "ix_exercise_questions_curriculum_node_id", "exercise_questions", ["curriculum_node_id"]
    )
    op.create_index(
        "ix_exercise_questions_knowledge_point_id", "exercise_questions", ["knowledge_point_id"]
    )

    op.create_table(
        "exercise_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_answer", sa.Text(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["exercise_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_exercise_attempts_learner_id", "exercise_attempts", ["learner_id"])
    op.create_index("ix_exercise_attempts_question_id", "exercise_attempts", ["question_id"])
    op.create_index("ix_exercise_attempts_session_id", "exercise_attempts", ["session_id"])


def downgrade() -> None:
    op.drop_table("exercise_attempts")
    op.drop_table("exercise_questions")
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
