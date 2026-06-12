import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ErrorPattern(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "error_patterns"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frequency: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    evidence_refs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    recommended_drill: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ErrorPattern {self.pattern} learner={self.learner_id}>"
