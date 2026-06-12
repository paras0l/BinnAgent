import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Learner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learners"

    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    profile: Mapped[Optional["LearnerProfile"]] = relationship(
        back_populates="learner", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Learner {self.nickname}>"


class LearnerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learner_profiles"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    target_exam: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    exam_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    daily_time_budget_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    preferred_study_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    interest_topics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    weak_skills: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)

    learner: Mapped["Learner"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return f"<LearnerProfile learner_id={self.learner_id}>"
