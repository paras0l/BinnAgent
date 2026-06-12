import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LearningSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_sessions"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    session_type: Mapped[str] = mapped_column(String(50), nullable=False)
    active_skill: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    today_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<LearningSession {self.session_type} learner={self.learner_id}>"


class LearningTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_tasks"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    skill: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    output_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    feedback_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<LearningTask {self.title} learner={self.learner_id}>"
