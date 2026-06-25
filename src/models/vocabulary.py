import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class VocabularyItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_items"
    __table_args__ = (
        UniqueConstraint("learner_id", "canonical_key", name="uq_vocabulary_learner_key"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="word")
    preferred_accent: Mapped[str] = mapped_column(String(10), nullable=False, default="auto")
    phonetic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phonetic_uk: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phonetic_us: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    audio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_uk: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    audio_us: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    meanings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    dictionary_senses: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    word_forms: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    dictionary_tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    collocations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    examples: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    source_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dictionary_provider: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    dictionary_enriched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="learning")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<VocabularyItem {self.word} learner={self.learner_id}>"


class VocabularyItemSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_item_sources"
    __table_args__ = (
        UniqueConstraint(
            "vocabulary_item_id",
            "source_type",
            "source_id",
            "curriculum_node_id",
            name="uq_vocabulary_item_source",
        ),
        Index("ix_vocabulary_sources_learner_type", "learner_id", "source_type"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vocabulary_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vocabulary_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    curriculum_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_label: Mapped[str] = mapped_column(String(120), nullable=False)
    context_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)


class VocabularyPracticeSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_practice_sessions"
    __table_args__ = (Index("ix_vocabulary_sessions_learner_status", "learner_id", "status"),)

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="audio")
    accent: Mapped[str] = mapped_column(String(10), nullable=False, default="uk")
    curriculum_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    item_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    current_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    hinted_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    revealed_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class VocabularyAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_attempts"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_vocabulary_attempt_idempotency"),
        Index("ix_vocabulary_attempts_learner_item", "learner_id", "vocabulary_item_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vocabulary_practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vocabulary_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vocabulary_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    drill_type: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    letter_diff: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hint_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    replay_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_schedules"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recommended_next_drill: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<ReviewSchedule {self.item_type} learner={self.learner_id}>"
