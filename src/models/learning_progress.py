import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LearningProgressItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_progress_items"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "skill",
            "item_id",
            name="uq_learning_progress_learner_skill_item",
        ),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="opened")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opened_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    learned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    def __repr__(self) -> str:
        return f"<LearningProgressItem {self.skill}/{self.item_id} learner={self.learner_id}>"
