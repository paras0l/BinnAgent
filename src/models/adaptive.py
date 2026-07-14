import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_evidence"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_assessment_evidence_attempt"),
        Index("ix_assessment_evidence_learner_point", "learner_id", "knowledge_point_id"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercise_attempts.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome_score: Mapped[float] = mapped_column(Float, nullable=False)
    independent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hint_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    semantic_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    item_difficulty_prior: Mapped[float] = mapped_column(Float, nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updates_learning_state: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class KnowledgeStateUpdate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_state_updates"
    __table_args__ = (UniqueConstraint("evidence_id", name="uq_knowledge_state_update_evidence"),)

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercise_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_evidence.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    new_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_success: Mapped[float] = mapped_column(Float, nullable=False)
    ability: Mapped[float] = mapped_column(Float, nullable=False)
    item_difficulty: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)


class FSRSReviewState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fsrs_review_states"
    __table_args__ = (UniqueConstraint("learner_id", "knowledge_point_id", name="uq_fsrs_review_state"),)

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    last_evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_evidence.id", ondelete="RESTRICT"), nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    stability_days: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    retrievability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_rating: Mapped[str] = mapped_column(String(10), nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)


class DKTShadowPrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dkt_shadow_predictions"
    __table_args__ = (UniqueConstraint("evidence_id", name="uq_dkt_shadow_prediction_evidence"),)

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_evidence.id", ondelete="CASCADE"), nullable=False)
    predicted_success: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_event_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    shadow_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TeachingPolicyDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teaching_policy_decisions"
    __table_args__ = (UniqueConstraint("evidence_id", name="uq_teaching_policy_decision_evidence"),)

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercise_attempts.id", ondelete="CASCADE"), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_evidence.id", ondelete="CASCADE"), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dkt_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DecisionTrace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "adaptive_decision_traces"
    __table_args__ = (UniqueConstraint("attempt_id", name="uq_adaptive_decision_trace_attempt"),)

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learners.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exercise_attempts.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_evidence.id", ondelete="CASCADE"), nullable=False)
    state_update_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_state_updates.id", ondelete="SET NULL"), nullable=True)
    policy_decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("teaching_policy_decisions.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    trace_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
