import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LearningMemoryEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_memory_events"
    __table_args__ = (
        Index("ix_learning_memory_events_learner_occurred", "learner_id", "occurred_at"),
        Index("ix_learning_memory_events_learner_skill", "learner_id", "skill", "subskill"),
        Index("ix_learning_memory_events_source", "source_type", "source_id"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    subskill: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="private")
    created_by: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MemoryOperation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_operations"
    __table_args__ = (
        Index("ix_memory_operations_learner_created", "learner_id", "created_at"),
        Index("ix_memory_operations_target", "target_type", "target_id"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    before: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    after: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(30), nullable=False, default="user")


class WritingPhraseMastery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "writing_phrase_masteries"
    __table_args__ = (
        UniqueConstraint("learner_id", "phrase_id", name="uq_writing_phrase_mastery_learner_phrase"),
        Index("ix_writing_phrase_masteries_learner_status", "learner_id", "status"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phrase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("writing_phrases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(50), nullable=False, default="writing")
    subskill: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="learning")
    recognition: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    context_use: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    production: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recommended_drill: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class MemoryContextLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_context_logs"
    __table_args__ = (
        Index("ix_memory_context_logs_learner_created", "learner_id", "created_at"),
        Index("ix_memory_context_logs_reason", "retrieval_reason"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    retrieval_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    loaded_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    excluded_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    token_cost: Mapped[int] = mapped_column(nullable=False, default=0)


class LearnerMemorySettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learner_memory_settings"
    __table_args__ = (
        UniqueConstraint("learner_id", name="uq_learner_memory_settings_learner"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emotion_rhythm_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inferred_preferences_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    low_confidence_memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
