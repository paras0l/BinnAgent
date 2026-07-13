import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SandboxPermissionPolicy(TimestampMixin, Base):
    __tablename__ = "sandbox_permission_policies"

    scope: Mapped[str] = mapped_column(String(40), primary_key=True, default="global")
    profile: Mapped[str] = mapped_column(String(40), nullable=False, default="strict")
    allowed_domains: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ExpressionLabSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expression_lab_sessions"
    __table_args__ = (
        Index("ix_expression_lab_sessions_learner_status", "learner_id", "status"),
        Index("ix_expression_lab_sessions_learner_updated", "learner_id", "updated_at"),
        Index("ix_expression_lab_sessions_source_ref", "source_type", "source_ref"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    episode_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_episodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    source_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_type: Mapped[str] = mapped_column(String(40), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    style_goal: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    current_level: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    needs_practice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generating")
    ui_spec_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    grading_spec_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    diagnostics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    generation_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ExpressionLabAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expression_lab_actions"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "spec_action_id", name="uq_expression_lab_action_session_spec"
        ),
        Index("ix_expression_lab_actions_session_status", "session_id", "status"),
        Index("ix_expression_lab_actions_session_block", "session_id", "block_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expression_lab_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    spec_action_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    editable_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_target_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    applied_target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    failure_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ExpressionLabAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expression_lab_attempts"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "block_id",
            "question_id",
            "attempt_number",
            name="uq_expression_lab_attempt_sequence",
        ),
        Index(
            "ix_expression_lab_attempts_session_question",
            "session_id",
            "question_id",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expression_lab_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercise_attempts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    block_id: Mapped[str] = mapped_column(String(120), nullable=False)
    question_id: Mapped[str] = mapped_column(String(120), nullable=False)
    answer_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    feedback_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    next_recommendations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class ExpressionLabEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "expression_lab_events"
    __table_args__ = (
        Index("ix_expression_lab_events_session_occurred", "session_id", "occurred_at"),
        Index("ix_expression_lab_events_session_type", "session_id", "event_type"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expression_lab_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
