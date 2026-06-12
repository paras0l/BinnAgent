import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class VocabularyItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_items"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    phonetic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    meanings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    collocations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    examples: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    source_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
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
