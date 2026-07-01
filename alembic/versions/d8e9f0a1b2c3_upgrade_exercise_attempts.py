"""upgrade exercise attempts for global targets

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-07-01 15:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercise_attempts", sa.Column("exercise_id", sa.String(length=255), nullable=True))
    op.add_column("exercise_attempts", sa.Column("target_type", sa.String(length=40), nullable=True))
    op.add_column("exercise_attempts", sa.Column("target_id", sa.String(length=255), nullable=True))
    op.add_column("exercise_attempts", sa.Column("target_label", sa.String(length=255), nullable=True))
    op.add_column("exercise_attempts", sa.Column("answer", sa.Text(), nullable=True))
    op.add_column("exercise_attempts", sa.Column("result", sa.String(length=20), nullable=True))
    op.add_column(
        "exercise_attempts",
        sa.Column("metadata", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "exercise_attempts",
        sa.Column(
            "source_context",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "exercise_attempts",
        sa.Column("should_update_mastery", sa.Boolean(), nullable=True, server_default=sa.true()),
    )
    op.add_column(
        "exercise_attempts",
        sa.Column(
            "should_create_error_pattern",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "exercise_attempts",
        sa.Column(
            "should_create_memory_evidence",
            sa.Boolean(),
            nullable=True,
            server_default=sa.true(),
        ),
    )

    op.execute(
        """
        UPDATE exercise_attempts AS attempt
        SET
            exercise_id = COALESCE(attempt.exercise_id, question.id::text),
            target_type = COALESCE(attempt.target_type, 'curriculum_node'),
            target_id = COALESCE(attempt.target_id, question.curriculum_node_id::text),
            target_label = COALESCE(attempt.target_label, node.title, '课程知识库练习'),
            answer = COALESCE(attempt.answer, attempt.submitted_answer),
            result = COALESCE(
                attempt.result,
                CASE WHEN attempt.correct THEN 'correct' ELSE 'incorrect' END
            ),
            metadata = COALESCE(attempt.metadata, '{}'::jsonb) || jsonb_build_object(
                'question_id', question.id::text,
                'question_type', question.question_type,
                'knowledge_point_id', question.knowledge_point_id::text
            ),
            source_context = COALESCE(attempt.source_context, '{}'::jsonb) || jsonb_build_object(
                'source', 'knowledge_base',
                'question_id', question.id::text,
                'curriculum_node_id', question.curriculum_node_id::text
            )
        FROM exercise_questions AS question
        LEFT JOIN curriculum_nodes AS node ON node.id = question.curriculum_node_id
        WHERE attempt.question_id = question.id
        """
    )
    op.execute(
        """
        UPDATE exercise_attempts
        SET
            exercise_id = COALESCE(exercise_id, question_id::text, id::text),
            target_type = COALESCE(target_type, 'curriculum_node'),
            target_id = COALESCE(target_id, question_id::text, id::text),
            target_label = COALESCE(target_label, '课程知识库练习'),
            answer = COALESCE(answer, submitted_answer),
            result = COALESCE(result, CASE WHEN correct THEN 'correct' ELSE 'incorrect' END),
            metadata = COALESCE(metadata, '{}'::jsonb),
            source_context = COALESCE(source_context, '{}'::jsonb),
            should_update_mastery = COALESCE(should_update_mastery, true),
            should_create_error_pattern = COALESCE(should_create_error_pattern, NOT correct),
            should_create_memory_evidence = COALESCE(should_create_memory_evidence, true)
        """
    )

    op.alter_column("exercise_attempts", "question_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("exercise_attempts", "exercise_id", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("exercise_attempts", "target_type", existing_type=sa.String(length=40), nullable=False)
    op.alter_column("exercise_attempts", "target_id", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("exercise_attempts", "target_label", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("exercise_attempts", "answer", existing_type=sa.Text(), nullable=False)
    op.alter_column("exercise_attempts", "result", existing_type=sa.String(length=20), nullable=False)
    op.alter_column("exercise_attempts", "metadata", existing_type=postgresql.JSONB(), nullable=False)
    op.alter_column("exercise_attempts", "source_context", existing_type=postgresql.JSONB(), nullable=False)
    op.alter_column("exercise_attempts", "should_update_mastery", existing_type=sa.Boolean(), nullable=False)
    op.alter_column(
        "exercise_attempts",
        "should_create_error_pattern",
        existing_type=sa.Boolean(),
        nullable=False,
    )
    op.alter_column(
        "exercise_attempts",
        "should_create_memory_evidence",
        existing_type=sa.Boolean(),
        nullable=False,
    )
    op.create_index(
        "ix_exercise_attempts_exercise_id",
        "exercise_attempts",
        ["exercise_id"],
    )
    op.create_index(
        "ix_exercise_attempts_target_type",
        "exercise_attempts",
        ["target_type"],
    )
    op.create_index(
        "ix_exercise_attempts_target_id",
        "exercise_attempts",
        ["target_id"],
    )
    op.create_index(
        "ix_exercise_attempts_learner_target_created",
        "exercise_attempts",
        ["learner_id", "target_type", "target_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_exercise_attempts_learner_target_created", table_name="exercise_attempts")
    op.drop_index("ix_exercise_attempts_target_id", table_name="exercise_attempts")
    op.drop_index("ix_exercise_attempts_target_type", table_name="exercise_attempts")
    op.drop_index("ix_exercise_attempts_exercise_id", table_name="exercise_attempts")
    op.execute("DELETE FROM exercise_attempts WHERE question_id IS NULL")
    op.alter_column("exercise_attempts", "question_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("exercise_attempts", "should_create_memory_evidence")
    op.drop_column("exercise_attempts", "should_create_error_pattern")
    op.drop_column("exercise_attempts", "should_update_mastery")
    op.drop_column("exercise_attempts", "source_context")
    op.drop_column("exercise_attempts", "metadata")
    op.drop_column("exercise_attempts", "result")
    op.drop_column("exercise_attempts", "answer")
    op.drop_column("exercise_attempts", "target_label")
    op.drop_column("exercise_attempts", "target_id")
    op.drop_column("exercise_attempts", "target_type")
    op.drop_column("exercise_attempts", "exercise_id")
