"""initial tables

Revision ID: d92b8a1e392d
Revises:
Create Date: 2026-06-12 15:14:11.591411

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d92b8a1e392d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # --- learners ---
    op.create_table(
        "learners",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # --- learner_profiles ---
    op.create_table(
        "learner_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("target_exam", sa.String(50), nullable=True),
        sa.Column("target_score", sa.SmallInteger, nullable=True),
        sa.Column("exam_date", sa.Date, nullable=True),
        sa.Column("current_level", sa.String(20), nullable=True),
        sa.Column("daily_time_budget_minutes", sa.SmallInteger, nullable=True),
        sa.Column("preferred_study_time", sa.String(50), nullable=True),
        sa.Column(
            "interest_topics",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "weak_skills", postgresql.JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
    )

    # --- learning_sessions ---
    op.create_table(
        "learning_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("session_type", sa.String(50), nullable=False),
        sa.Column("active_skill", sa.String(50), nullable=True),
        sa.Column("today_goal", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_learning_sessions_learner_id"), "learning_sessions", ["learner_id"])

    # --- learning_tasks ---
    op.create_table(
        "learning_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("skill", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("estimated_minutes", sa.SmallInteger, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("input_ref", sa.String(500), nullable=True),
        sa.Column("output_ref", sa.String(500), nullable=True),
        sa.Column("feedback_ref", sa.String(500), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_learning_tasks_learner_id"), "learning_tasks", ["learner_id"])
    op.create_index(op.f("ix_learning_tasks_session_id"), "learning_tasks", ["session_id"])

    # --- vocabulary_items ---
    op.create_table(
        "vocabulary_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("phonetic", sa.String(255), nullable=True),
        sa.Column("level", sa.String(20), nullable=True),
        sa.Column(
            "meanings", postgresql.JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "collocations", postgresql.JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "examples", postgresql.JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'learning'")),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("review_count", sa.SmallInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_vocabulary_items_learner_id"), "vocabulary_items", ["learner_id"])

    # --- review_schedules ---
    op.create_table(
        "review_schedules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(20), nullable=True),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("confidence_before", sa.Float, nullable=True),
        sa.Column("confidence_after", sa.Float, nullable=True),
        sa.Column("recommended_next_drill", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_review_schedules_learner_id"), "review_schedules", ["learner_id"])

    # --- error_patterns ---
    op.create_table(
        "error_patterns",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill", sa.String(50), nullable=False),
        sa.Column("pattern", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("frequency", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column(
            "evidence_refs", postgresql.JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("recommended_drill", sa.String(100), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_error_patterns_learner_id"), "error_patterns", ["learner_id"])

    # --- agent_threads ---
    op.create_table(
        "agent_threads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "metadata", postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_agent_threads_learner_id"), "agent_threads", ["learner_id"])

    # --- agent_runs ---
    op.create_table(
        "agent_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("graph_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'running'")),
        sa.Column(
            "model_usage", postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("cost", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_agent_runs_thread_id"), "agent_runs", ["thread_id"])

    # --- agent_events ---
    op.create_table(
        "agent_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("node_name", sa.String(100), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_agent_events_run_id"), "agent_events", ["run_id"])

    # --- tool_calls ---
    op.create_table(
        "tool_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_name", sa.String(100), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("input_summary", sa.Text, nullable=True),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'success'")),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_tool_calls_run_id"), "tool_calls", ["run_id"])

    # --- model_call_logs ---
    op.create_table(
        "model_call_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_name", sa.String(100), nullable=True),
        sa.Column("task_type", sa.String(50), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("local_only", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("prompt_chars", sa.Integer, nullable=True),
        sa.Column("completion_chars", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'success'")),
        sa.Column("retry_count", sa.SmallInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("fallback_from", sa.String(50), nullable=True),
        sa.Column("fallback_reason", sa.String(100), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(op.f("ix_model_call_logs_run_id"), "model_call_logs", ["run_id"])


def downgrade() -> None:
    op.drop_table("model_call_logs")
    op.drop_table("tool_calls")
    op.drop_table("agent_events")
    op.drop_table("agent_runs")
    op.drop_table("agent_threads")
    op.drop_table("error_patterns")
    op.drop_table("review_schedules")
    op.drop_table("vocabulary_items")
    op.drop_table("learning_tasks")
    op.drop_table("learning_sessions")
    op.drop_table("learner_profiles")
    op.drop_table("learners")
