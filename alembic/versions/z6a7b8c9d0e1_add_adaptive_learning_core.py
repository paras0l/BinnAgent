"""add adaptive learning evidence and decision models

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "z6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "y5z6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("exercise_questions", sa.Column("difficulty_prior", sa.Float(), nullable=True))
    op.execute("UPDATE exercise_questions SET difficulty_prior = difficulty")
    op.alter_column(
        "exercise_questions",
        "difficulty_prior",
        existing_type=sa.Float(),
        nullable=False,
        server_default="0.3",
    )
    op.add_column("exercise_questions", sa.Column("difficulty_calibrated", sa.Float(), nullable=True))
    op.add_column("exercise_questions", sa.Column("difficulty_model_version", sa.String(80), server_default="irt-prior-v1", nullable=False))
    op.add_column("learner_knowledge_states", sa.Column("ability", sa.Float(), server_default="0", nullable=False))
    op.add_column("learner_knowledge_states", sa.Column("predicted_success", sa.Float(), nullable=True))
    op.add_column("learner_knowledge_states", sa.Column("dkt_shadow_prediction", sa.Float(), nullable=True))
    op.add_column("learner_knowledge_states", sa.Column("state_model_version", sa.String(80), server_default="irt-1pl-v1", nullable=False))

    op.create_table(
        "assessment_evidence",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.String(255), nullable=False),
        sa.Column("evidence_mode", sa.String(30), nullable=False),
        sa.Column("outcome_score", sa.Float(), nullable=False),
        sa.Column("independent", sa.Boolean(), nullable=False),
        sa.Column("hint_count", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_tags", postgresql.JSONB(), nullable=False),
        sa.Column("semantic_confidence", sa.Float(), nullable=False),
        sa.Column("item_difficulty_prior", sa.Float(), nullable=False),
        sa.Column("interaction_type", sa.String(30), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("updates_learning_state", sa.Boolean(), nullable=False),
        sa.Column("decision_reason", sa.String(160), nullable=False),
        sa.Column("evidence_ref", sa.String(255), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exercise_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", name="uq_assessment_evidence_attempt"),
    )
    op.create_index("ix_assessment_evidence_learner_point", "assessment_evidence", ["learner_id", "knowledge_point_id"])

    op.create_table(
        "knowledge_state_updates",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_mastery", sa.Float(), nullable=False),
        sa.Column("new_mastery", sa.Float(), nullable=False),
        sa.Column("predicted_success", sa.Float(), nullable=False),
        sa.Column("ability", sa.Float(), nullable=False),
        sa.Column("item_difficulty", sa.Float(), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exercise_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["assessment_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", name="uq_knowledge_state_update_evidence"),
    )
    op.create_index("ix_knowledge_state_updates_learner_id", "knowledge_state_updates", ["learner_id"])
    op.create_index("ix_knowledge_state_updates_attempt_id", "knowledge_state_updates", ["attempt_id"])
    op.create_index("ix_knowledge_state_updates_knowledge_point_id", "knowledge_state_updates", ["knowledge_point_id"])

    op.create_table(
        "fsrs_review_states",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("difficulty", sa.Float(), nullable=False),
        sa.Column("stability_days", sa.Float(), nullable=False),
        sa.Column("retrievability", sa.Float(), nullable=False),
        sa.Column("last_rating", sa.String(10), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_evidence_id"], ["assessment_evidence.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "knowledge_point_id", name="uq_fsrs_review_state"),
    )
    op.create_index("ix_fsrs_review_states_learner_id", "fsrs_review_states", ["learner_id"])
    op.create_index("ix_fsrs_review_states_knowledge_point_id", "fsrs_review_states", ["knowledge_point_id"])
    op.create_index("ix_fsrs_review_states_next_review_at", "fsrs_review_states", ["next_review_at"])

    op.create_table(
        "dkt_shadow_predictions",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicted_success", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("input_event_refs", postgresql.JSONB(), nullable=False),
        sa.Column("shadow_mode", sa.Boolean(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["assessment_evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", name="uq_dkt_shadow_prediction_evidence"),
    )
    op.create_index("ix_dkt_shadow_predictions_learner_id", "dkt_shadow_predictions", ["learner_id"])
    op.create_index("ix_dkt_shadow_predictions_knowledge_point_id", "dkt_shadow_predictions", ["knowledge_point_id"])

    op.create_table(
        "teaching_policy_decisions",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("compiler_version", sa.String(80), nullable=False),
        sa.Column("dkt_applied", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exercise_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["assessment_evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", name="uq_teaching_policy_decision_evidence"),
    )
    op.create_index("ix_teaching_policy_decisions_learner_id", "teaching_policy_decisions", ["learner_id"])
    op.create_index("ix_teaching_policy_decisions_knowledge_point_id", "teaching_policy_decisions", ["knowledge_point_id"])

    op.add_column(
        "prompt_execution_records",
        sa.Column("adaptive_policy_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "prompt_execution_records",
        sa.Column("teaching_policy_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_prompt_execution_teaching_policy_decision",
        "prompt_execution_records",
        "teaching_policy_decisions",
        ["teaching_policy_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "adaptive_decision_traces",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state_update_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(160), nullable=False),
        sa.Column("trace_payload", postgresql.JSONB(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exercise_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["assessment_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["state_update_id"], ["knowledge_state_updates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_decision_id"], ["teaching_policy_decisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", name="uq_adaptive_decision_trace_attempt"),
    )
    op.create_index("ix_adaptive_decision_traces_learner_id", "adaptive_decision_traces", ["learner_id"])


def downgrade() -> None:
    op.drop_table("adaptive_decision_traces")
    op.drop_constraint("fk_prompt_execution_teaching_policy_decision", "prompt_execution_records", type_="foreignkey")
    op.drop_column("prompt_execution_records", "teaching_policy_decision_id")
    op.drop_column("prompt_execution_records", "adaptive_policy_snapshot")
    op.drop_table("teaching_policy_decisions")
    op.drop_table("dkt_shadow_predictions")
    op.drop_table("fsrs_review_states")
    op.drop_table("knowledge_state_updates")
    op.drop_table("assessment_evidence")
    for column in ("state_model_version", "dkt_shadow_prediction", "predicted_success", "ability"):
        op.drop_column("learner_knowledge_states", column)
    for column in ("difficulty_model_version", "difficulty_calibrated", "difficulty_prior"):
        op.drop_column("exercise_questions", column)
