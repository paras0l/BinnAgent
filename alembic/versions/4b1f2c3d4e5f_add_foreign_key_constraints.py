"""add foreign key constraints

Revision ID: 4b1f2c3d4e5f
Revises: d92b8a1e392d
Create Date: 2026-06-12 19:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4b1f2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "d92b8a1e392d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_index(
        "uq_vocabulary_items_learner_lower_word",
        "vocabulary_items",
        ["learner_id", sa.text("lower(word)")],
        unique=True,
    )

    op.create_foreign_key(
        "fk_learning_sessions_learner_id",
        "learning_sessions",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_learning_tasks_learner_id",
        "learning_tasks",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_learning_tasks_session_id",
        "learning_tasks",
        "learning_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_vocabulary_items_learner_id",
        "vocabulary_items",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_review_schedules_learner_id",
        "review_schedules",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_error_patterns_learner_id",
        "error_patterns",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_agent_threads_learner_id",
        "agent_threads",
        "learners",
        ["learner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_agent_runs_thread_id",
        "agent_runs",
        "agent_threads",
        ["thread_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_agent_runs_session_id",
        "agent_runs",
        "learning_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_agent_events_run_id",
        "agent_events",
        "agent_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_tool_calls_run_id",
        "tool_calls",
        "agent_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_model_call_logs_run_id",
        "model_call_logs",
        "agent_runs",
        ["run_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_model_call_logs_run_id", "model_call_logs", type_="foreignkey")
    op.drop_constraint("fk_tool_calls_run_id", "tool_calls", type_="foreignkey")
    op.drop_constraint("fk_agent_events_run_id", "agent_events", type_="foreignkey")
    op.drop_constraint("fk_agent_runs_session_id", "agent_runs", type_="foreignkey")
    op.drop_constraint("fk_agent_runs_thread_id", "agent_runs", type_="foreignkey")
    op.drop_constraint("fk_agent_threads_learner_id", "agent_threads", type_="foreignkey")
    op.drop_constraint("fk_error_patterns_learner_id", "error_patterns", type_="foreignkey")
    op.drop_constraint("fk_review_schedules_learner_id", "review_schedules", type_="foreignkey")
    op.drop_constraint("fk_vocabulary_items_learner_id", "vocabulary_items", type_="foreignkey")
    op.drop_constraint("fk_learning_tasks_session_id", "learning_tasks", type_="foreignkey")
    op.drop_constraint("fk_learning_tasks_learner_id", "learning_tasks", type_="foreignkey")
    op.drop_constraint("fk_learning_sessions_learner_id", "learning_sessions", type_="foreignkey")
    op.drop_index("uq_vocabulary_items_learner_lower_word", table_name="vocabulary_items")
